"""HTTP client for the Etsy Open API v3.

Etsy's Open API v3 (https://developers.etsy.com/documentation/) uses
OAuth 2.0 with PKCE. The seller (or a one-time setup script) completes
the OAuth authorization-code flow and stores the resulting refresh token.
This client uses the refresh token to mint short-lived access tokens at
runtime, refreshing them transparently when they expire or are rejected.

Every request also carries an `x-api-key` header, the keystring from the
Etsy app registration page. Public read endpoints accept the keystring
alone; OAuth-scoped endpoints (receipts, inventory) require both the
keystring AND a valid bearer token.

The client is deliberately small and dependency-light: only `requests` is
required at runtime. State is per-instance, there is no module-level
mutable state, so multiple clients can run in the same process against
different shops without interfering.

This module is a clean rewrite for public release. It does not import or
inherit any seller-specific configuration; everything that depends on a
particular Etsy account is supplied by the caller.
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterator, Optional

import requests

logger = logging.getLogger(__name__)

# Etsy's receipt and listing endpoints accept up to 100 per page. Stay
# below the cap so we never trip a server-side limit revision.
RECEIPT_PAGE_SIZE = 100
LISTING_PAGE_SIZE = 100

# Refresh the bearer token a couple of minutes before Etsy expires it,
# to avoid a tight race on long-running calls. Etsy access tokens last
# 3600 seconds.
_TOKEN_TTL_SECONDS = 3300

# Etsy's OAuth token endpoint is on the public api host, NOT the v3
# application path.
_TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"

# Status codes that warrant a retry. 401 is handled separately (token
# refresh + single retry). 429 (rate limit) is also retryable with backoff.
_RETRY_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class EtsyError(Exception):
    """Wraps a non-recoverable Etsy response so the MCP layer can
    surface a clean message instead of leaking the raw HTTP exception."""

    def __init__(self, message: str, *, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class EtsyClient:
    """Thin REST wrapper. Construct once per (shop, credential) pair."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        refresh_token: str,
        *,
        timeout: int = 60,
        max_retries: int = 3,
        session: Optional[requests.Session] = None,
        token_url: str = _TOKEN_URL,
    ):
        if not base_url.endswith("/"):
            base_url = base_url + "/"
        self.base_url = base_url
        self._api_key = api_key
        self._refresh_token = refresh_token
        self._timeout = timeout
        self._max_retries = max(1, max_retries)
        self._session = session or requests.Session()
        self._token_url = token_url

        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    # ---- auth -----------------------------------------------------------

    def _get_access_token(self) -> str:
        now = datetime.now(timezone.utc)
        if (
            self._access_token
            and self._token_expires_at
            and now < self._token_expires_at
        ):
            return self._access_token

        # Etsy OAuth refresh: POST x-www-form-urlencoded.
        resp = self._session.post(
            self._token_url,
            data={
                "grant_type": "refresh_token",
                "client_id": self._api_key,
                "refresh_token": self._refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self._timeout,
        )
        if resp.status_code != 200:
            raise EtsyError(
                f"Failed to refresh Etsy access token: HTTP {resp.status_code}",
                status_code=resp.status_code,
            )
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise EtsyError("Etsy token response missing 'access_token'")
        self._access_token = token
        # Etsy may return a rotated refresh token, adopt it if present so
        # long-running processes don't lose access on the next refresh.
        new_refresh = data.get("refresh_token")
        if new_refresh:
            self._refresh_token = new_refresh
        self._token_expires_at = now + timedelta(seconds=_TOKEN_TTL_SECONDS)
        return token

    def _headers(self) -> dict:
        return {
            "x-api-key": self._api_key,
            "Authorization": f"Bearer {self._get_access_token()}",
            "Accept": "application/json",
        }

    # ---- request loop --------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        *,
        json_body: Optional[dict] = None,
    ) -> Any:
        url = f"{self.base_url}{path.lstrip('/')}"
        last_exc: Optional[Exception] = None

        for attempt in range(1, self._max_retries + 1):
            try:
                resp = self._session.request(
                    method,
                    url,
                    headers=self._headers(),
                    params=params,
                    json=json_body,
                    timeout=self._timeout,
                )
            except (requests.ConnectionError, requests.Timeout) as exc:
                last_exc = exc
                self._sleep_backoff(attempt)
                continue

            # Token expired mid-request: refresh once and retry inline.
            if resp.status_code == 401:
                self._access_token = None
                self._token_expires_at = None
                try:
                    resp = self._session.request(
                        method,
                        url,
                        headers=self._headers(),
                        params=params,
                        json=json_body,
                        timeout=self._timeout,
                    )
                except (requests.ConnectionError, requests.Timeout) as exc:
                    last_exc = exc
                    self._sleep_backoff(attempt)
                    continue

            if resp.status_code in _RETRY_STATUS_CODES:
                last_exc = EtsyError(
                    f"Transient Etsy error: HTTP {resp.status_code}",
                    status_code=resp.status_code,
                )
                self._sleep_backoff(attempt)
                continue

            if not resp.ok:
                raise EtsyError(
                    f"Etsy {method} {path} failed: HTTP {resp.status_code}",
                    status_code=resp.status_code,
                )

            try:
                return resp.json()
            except ValueError as exc:
                raise EtsyError(
                    f"Etsy {method} {path} returned non-JSON body"
                ) from exc

        if last_exc is not None:
            raise EtsyError(
                f"Etsy {method} {path} failed after "
                f"{self._max_retries} attempts: {last_exc}"
            ) from last_exc
        raise EtsyError(f"Etsy {method} {path} failed for unknown reason")

    @staticmethod
    def _sleep_backoff(attempt: int) -> None:
        # Exponential backoff with a small floor: 0.5s, 1s, 2s, 4s ...
        delay = 0.5 * (2 ** (attempt - 1))
        time.sleep(min(delay, 8.0))

    # ---- public read endpoints -----------------------------------------

    def search_listings(
        self,
        query: str,
        *,
        shop_id: Optional[int] = None,
        limit: int = 50,
    ) -> dict:
        """Search active listings by keyword.

        When `shop_id` is provided, search is scoped to that shop's active
        listings (`/shops/{shop_id}/listings/active`). Otherwise it queries
        the global active-listings endpoint.
        """
        capped = max(1, min(limit, LISTING_PAGE_SIZE))
        if shop_id is not None:
            params = {"keywords": query, "limit": capped}
            return self._request(
                "GET", f"shops/{shop_id}/listings/active", params=params
            )
        params = {"keywords": query, "limit": capped}
        return self._request("GET", "listings/active", params=params)

    def get_listing(self, listing_id: int) -> Optional[dict]:
        """Return the full record for one listing, or None if not found."""
        try:
            return self._request("GET", f"listings/{listing_id}")
        except EtsyError as exc:
            if exc.status_code == 404:
                return None
            raise

    def get_shop(self, shop_id: int) -> Optional[dict]:
        """Return the shop record, or None if not found."""
        try:
            return self._request("GET", f"shops/{shop_id}")
        except EtsyError as exc:
            if exc.status_code == 404:
                return None
            raise

    def search_receipts(
        self,
        shop_id: int,
        date_from: date,
        date_to: date,
        *,
        status: Optional[str] = None,
    ) -> Iterator[dict]:
        """Yield every receipt (order) created in the inclusive
        [date_from, date_to] window for the given shop.

        Etsy caps page size at 100 regardless of the requested value, so
        callers should expect transparent pagination via offset.
        """
        if date_from > date_to:
            raise ValueError("date_from must be <= date_to")

        # Etsy uses unix epoch seconds for `min_created` / `max_created`.
        min_created = int(
            datetime(
                date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc
            ).timestamp()
        )
        max_created = int(
            datetime(
                date_to.year,
                date_to.month,
                date_to.day,
                23,
                59,
                59,
                tzinfo=timezone.utc,
            ).timestamp()
        )

        offset = 0
        while True:
            params: dict[str, Any] = {
                "min_created": min_created,
                "max_created": max_created,
                "limit": RECEIPT_PAGE_SIZE,
                "offset": offset,
            }
            if status:
                params["status"] = status

            data = self._request(
                "GET", f"shops/{shop_id}/receipts", params=params
            )
            results = data.get("results") or []
            count = data.get("count", 0)

            for receipt in results:
                yield receipt

            offset += len(results)
            if not results or offset >= count:
                return

    def get_receipt(self, shop_id: int, receipt_id: int) -> Optional[dict]:
        """Return full receipt detail (with transactions), or None on 404."""
        try:
            return self._request(
                "GET", f"shops/{shop_id}/receipts/{receipt_id}"
            )
        except EtsyError as exc:
            if exc.status_code == 404:
                return None
            raise

    def get_listing_inventory(self, listing_id: int) -> Optional[dict]:
        """Return the inventory record (variations + offerings) for a listing."""
        try:
            return self._request("GET", f"listings/{listing_id}/inventory")
        except EtsyError as exc:
            if exc.status_code == 404:
                return None
            raise

    def get_shop_stats(
        self, shop_id: int, *, period: str = "30d"
    ) -> dict:
        """Return aggregated views / favorites / orders for a shop.

        Etsy does not expose a single first-class "shop stats" endpoint at
        v3; this method composes the requested rollup by reading the shop
        record (favorers, listing_active_count) and counting receipts in
        the period window. The returned shape is deliberately stable so
        callers don't have to know which sub-endpoints power it.
        """
        days = _parse_period_days(period)
        today = datetime.now(timezone.utc).date()
        date_from = today - timedelta(days=days)

        shop = self.get_shop(shop_id) or {}
        receipts = list(
            self.search_receipts(
                shop_id=shop_id, date_from=date_from, date_to=today
            )
        )
        revenue_minor = 0
        currency = None
        for r in receipts:
            grand = r.get("grandtotal") or {}
            amt = grand.get("amount") or 0
            divisor = grand.get("divisor") or 100
            currency = currency or grand.get("currency_code")
            # Normalize to minor units (cents) for safe summation
            try:
                revenue_minor += int(round(amt * 100 / divisor))
            except (TypeError, ValueError):
                continue

        return {
            "shop_id": shop_id,
            "period": period,
            "period_days": days,
            "date_from": date_from.isoformat(),
            "date_to": today.isoformat(),
            "favorers": shop.get("num_favorers", 0),
            "active_listings": shop.get("listing_active_count", 0),
            "orders": len(receipts),
            "revenue_minor_units": revenue_minor,
            "currency_code": currency,
        }

    def get_active_listings(
        self, shop_id: int, *, limit: int = 200
    ) -> Iterator[dict]:
        """Yield every active listing for a shop, paging transparently.

        `limit` is a soft cap on yielded results; Etsy's hard page-size
        ceiling is 100 per request.
        """
        capped_total = max(1, min(limit, 1000))
        page_size = min(LISTING_PAGE_SIZE, capped_total)
        offset = 0
        yielded = 0
        while yielded < capped_total:
            params: dict[str, Any] = {
                "limit": page_size,
                "offset": offset,
            }
            data = self._request(
                "GET", f"shops/{shop_id}/listings/active", params=params
            )
            results = data.get("results") or []
            count = data.get("count", 0)

            for listing in results:
                yield listing
                yielded += 1
                if yielded >= capped_total:
                    return

            offset += len(results)
            if not results or offset >= count:
                return


def _parse_period_days(period: str) -> int:
    """Parse a period string like '7d', '30d', '90d' into integer days."""
    if not period:
        raise ValueError("period must be a non-empty string like '30d'")
    value = period.strip().lower()
    if value.endswith("d") and value[:-1].isdigit():
        days = int(value[:-1])
        if days <= 0:
            raise ValueError(f"period must be positive; got {period!r}")
        if days > 365:
            raise ValueError(f"period cannot exceed 365 days; got {period!r}")
        return days
    raise ValueError(
        f"period must be of the form '<N>d' (e.g. '7d', '30d'); got {period!r}"
    )
