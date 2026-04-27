"""MCP server entry point.

Exposes eight read-only tools that wrap Etsy's Open API v3. The server
uses stdio transport, which is the standard MCP transport for desktop
Claude clients (Claude Code, Claude Desktop, IDE extensions).

Run via `python -m etsy_mcp` or the `etsy-mcp` CLI command.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from .client import EtsyClient, EtsyError
from .config import Settings

logger = logging.getLogger(__name__)

mcp = FastMCP("etsy-mcp")

# Lazy singletons. We don't want to require credentials at import time —
# the MCP host may launch the server with a degenerate environment for
# capability discovery.
_settings: Optional[Settings] = None
_client: Optional[EtsyClient] = None


def _get_client() -> EtsyClient:
    global _settings, _client
    if _client is None:
        _settings = Settings.from_env()
        _client = EtsyClient(
            base_url=_settings.api_url,
            api_key=_settings.api_key,
            refresh_token=_settings.refresh_token,
            timeout=_settings.http_timeout,
            max_retries=_settings.max_retries,
        )
    return _client


def _resolve_shop_id(shop_id: Optional[int]) -> int:
    if shop_id is not None:
        return shop_id
    if _settings is None:
        # Trigger lazy init; updates _settings as a side effect.
        _get_client()
    assert _settings is not None
    if _settings.default_shop_id is None:
        raise ValueError(
            "shop_id is required. Set ETSY_DEFAULT_SHOP_ID to skip this "
            "argument on every call."
        )
    return _settings.default_shop_id


def _ok(data: Any) -> str:
    return json.dumps({"ok": True, "data": data}, default=_json_default, indent=2)


def _err(message: str) -> str:
    return json.dumps({"ok": False, "error": message}, indent=2)


def _json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _parse_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"{field_name} must be an ISO date (YYYY-MM-DD); got {value!r}"
        ) from exc


# ---- tools -------------------------------------------------------------


@mcp.tool()
def etsy_search_listings(
    query: str,
    shop_id: Optional[int] = None,
    limit: int = 50,
) -> str:
    """Search active Etsy listings by keyword.

    Args:
        query: Free-text keyword search across listing title and tags.
        shop_id: Optional Etsy ShopID to scope the search to a single shop.
            When omitted, queries the global active-listings index.
        limit: Cap on returned results (max 100 enforced by Etsy).

    Returns:
        JSON envelope: {"ok": true, "data": {"results": [...], "count": N}}.
    """
    if not query or not query.strip():
        return _err("query is required and must be non-empty")
    try:
        result = _get_client().search_listings(
            query=query.strip(),
            shop_id=shop_id,
            limit=max(1, min(limit, 100)),
        )
        return _ok(
            {
                "results": result.get("results") or [],
                "count": result.get("count", 0),
                "shop_id": shop_id,
                "limit": limit,
            }
        )
    except (ValueError, EtsyError, RuntimeError) as exc:
        return _err(str(exc))


@mcp.tool()
def etsy_get_listing(listing_id: int) -> str:
    """Fetch the full record for a single listing.

    Args:
        listing_id: Etsy ListingID (integer).

    Returns:
        JSON envelope. `data` is the listing record, or null if not found.
    """
    if not isinstance(listing_id, int) or listing_id <= 0:
        return _err("listing_id must be a positive integer")
    try:
        listing = _get_client().get_listing(listing_id=listing_id)
        return _ok(listing)
    except (ValueError, EtsyError, RuntimeError) as exc:
        return _err(str(exc))


@mcp.tool()
def etsy_get_shop(shop_id: int) -> str:
    """Fetch the shop record for a single shop.

    Args:
        shop_id: Etsy ShopID (integer).

    Returns:
        JSON envelope. `data` is the shop record (with name, currency_code,
        listing_active_count, num_favorers, etc.), or null if not found.
    """
    if not isinstance(shop_id, int) or shop_id <= 0:
        return _err("shop_id must be a positive integer")
    try:
        shop = _get_client().get_shop(shop_id=shop_id)
        return _ok(shop)
    except (ValueError, EtsyError, RuntimeError) as exc:
        return _err(str(exc))


@mcp.tool()
def etsy_search_orders(
    date_from: str,
    date_to: str,
    shop_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 200,
) -> str:
    """Search receipts (orders) created in the inclusive [date_from, date_to]
    window for a shop.

    Args:
        date_from: ISO date (YYYY-MM-DD), start of window.
        date_to: ISO date (YYYY-MM-DD), end of window.
        shop_id: Etsy ShopID to scope the search to. Falls back to
            ETSY_DEFAULT_SHOP_ID if omitted.
        status: Optional receipt status filter ('open', 'unshipped',
            'unpaid', 'completed', 'processing', 'all').
        limit: Cap on yielded receipts (default 200, max 1000). Etsy
            caps page size at 100 per request; pagination is handled
            transparently.

    Returns:
        JSON envelope. `data.orders` is the list of receipt records.
    """
    try:
        df = _parse_date(date_from, "date_from")
        dt = _parse_date(date_to, "date_to")
        sid = _resolve_shop_id(shop_id)
        capped_limit = max(1, min(limit, 1000))
        client = _get_client()
        out: list[dict] = []
        for receipt in client.search_receipts(
            shop_id=sid,
            date_from=df,
            date_to=dt,
            status=status.strip() if status else None,
        ):
            out.append(receipt)
            if len(out) >= capped_limit:
                break
        return _ok(
            {
                "orders": out,
                "count": len(out),
                "date_from": df.isoformat(),
                "date_to": dt.isoformat(),
                "shop_id": sid,
                "limit_reached": len(out) >= capped_limit,
            }
        )
    except (ValueError, EtsyError, RuntimeError) as exc:
        return _err(str(exc))


@mcp.tool()
def etsy_get_order(receipt_id: int, shop_id: Optional[int] = None) -> str:
    """Fetch full receipt (order) detail including transactions.

    Args:
        receipt_id: Etsy ReceiptID (integer).
        shop_id: Etsy ShopID. Falls back to ETSY_DEFAULT_SHOP_ID if omitted.

    Returns:
        JSON envelope. `data` is the receipt record, or null if missing.
    """
    if not isinstance(receipt_id, int) or receipt_id <= 0:
        return _err("receipt_id must be a positive integer")
    try:
        sid = _resolve_shop_id(shop_id)
        receipt = _get_client().get_receipt(shop_id=sid, receipt_id=receipt_id)
        return _ok(receipt)
    except (ValueError, EtsyError, RuntimeError) as exc:
        return _err(str(exc))


@mcp.tool()
def etsy_get_inventory(listing_id: int) -> str:
    """Fetch the current inventory record (variations + offerings) for a listing.

    Args:
        listing_id: Etsy ListingID.

    Returns:
        JSON envelope. `data` is the inventory record (with `products[]`
        carrying property values, SKU, price, and `offerings[]` with
        quantity), or null if absent.
    """
    if not isinstance(listing_id, int) or listing_id <= 0:
        return _err("listing_id must be a positive integer")
    try:
        inv = _get_client().get_listing_inventory(listing_id=listing_id)
        return _ok(inv)
    except (ValueError, EtsyError, RuntimeError) as exc:
        return _err(str(exc))


@mcp.tool()
def etsy_get_shop_stats(
    shop_id: int,
    period: str = "30d",
) -> str:
    """Return aggregated stats (orders, favorers, active listings, revenue)
    for a shop over the given period.

    Args:
        shop_id: Etsy ShopID.
        period: Lookback window in the form '<N>d', e.g. '7d', '30d', '90d'.
            Maximum 365 days.

    Returns:
        JSON envelope. `data` is a dict with `orders`, `favorers`,
        `active_listings`, `revenue_minor_units`, `currency_code`, and
        the resolved `date_from` / `date_to`.
    """
    if not isinstance(shop_id, int) or shop_id <= 0:
        return _err("shop_id must be a positive integer")
    try:
        stats = _get_client().get_shop_stats(shop_id=shop_id, period=period)
        return _ok(stats)
    except (ValueError, EtsyError, RuntimeError) as exc:
        return _err(str(exc))


@mcp.tool()
def etsy_get_active_listings(
    shop_id: int,
    limit: int = 200,
) -> str:
    """List active listings for a shop, paginating transparently.

    Args:
        shop_id: Etsy ShopID.
        limit: Soft cap on yielded listings (default 200, max 1000).

    Returns:
        JSON envelope. `data.listings` is the list of active-listing records.
    """
    if not isinstance(shop_id, int) or shop_id <= 0:
        return _err("shop_id must be a positive integer")
    try:
        capped_limit = max(1, min(limit, 1000))
        out: list[dict] = []
        for listing in _get_client().get_active_listings(
            shop_id=shop_id, limit=capped_limit
        ):
            out.append(listing)
            if len(out) >= capped_limit:
                break
        return _ok(
            {
                "listings": out,
                "count": len(out),
                "shop_id": shop_id,
                "limit_reached": len(out) >= capped_limit,
            }
        )
    except (ValueError, EtsyError, RuntimeError) as exc:
        return _err(str(exc))


def main() -> None:
    """CLI entry point — runs the MCP server over stdio."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    mcp.run()


if __name__ == "__main__":
    main()
