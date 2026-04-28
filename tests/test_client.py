"""Tests for the Etsy HTTP client.

All tests use a mocked `requests.Session`, no live HTTP, no real
credentials. Synthetic fixtures defined in tests/fixtures.py.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest
import requests

from etsy_mcp.client import EtsyClient, EtsyError, _parse_period_days
from tests.fixtures import (
    SAMPLE_ACTIVE_LISTINGS_PAGE_1,
    SAMPLE_ACTIVE_LISTINGS_PAGE_2,
    SAMPLE_INVENTORY,
    SAMPLE_LISTING,
    SAMPLE_LISTING_SEARCH,
    SAMPLE_RECEIPT_DETAIL,
    SAMPLE_RECEIPTS_PAGE_1,
    SAMPLE_RECEIPTS_PAGE_2,
    SAMPLE_SHOP,
    SAMPLE_TOKEN_RESPONSE,
    SANDBOX_SHOP_PRIMARY,
)

TOKEN_URL = "https://api.etsy.invalid/v3/public/oauth/token"


def _ok_response(json_body: dict, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.ok = 200 <= status < 400
    resp.json.return_value = json_body
    return resp


def _err_response(status: int) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.ok = False
    resp.json.return_value = {}
    return resp


def _token_post_responder(url, data=None, json=None, headers=None, timeout=None):
    if "oauth/token" in url:
        return _ok_response(SAMPLE_TOKEN_RESPONSE)
    raise AssertionError(f"Unexpected POST: {url}")


def _make_client(session: MagicMock) -> EtsyClient:
    return EtsyClient(
        base_url="https://api.etsy.invalid/v3/application/",
        api_key="sandbox-api-key",
        refresh_token="sandbox-refresh-token",
        timeout=5,
        max_retries=3,
        session=session,
        token_url=TOKEN_URL,
    )


# ---- token / auth ------------------------------------------------------


def test_token_acquired_on_first_request():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response({"results": [], "count": 0})

    client = _make_client(session)
    client.search_listings(query="anything")

    assert session.post.call_count == 1
    # Subsequent call reuses the cached access token
    client.search_listings(query="anything")
    assert session.post.call_count == 1


def test_token_failure_raises_etsy_error():
    session = MagicMock()
    session.post.return_value = _err_response(401)
    client = _make_client(session)
    with pytest.raises(EtsyError, match="Failed to refresh Etsy access token"):
        client.search_listings(query="x")


def test_token_response_missing_access_token():
    session = MagicMock()
    session.post.return_value = _ok_response({"expires_in": 3600})
    client = _make_client(session)
    with pytest.raises(EtsyError, match="missing 'access_token'"):
        client.search_listings(query="x")


def test_token_response_rotates_refresh_token():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response({"results": [], "count": 0})
    client = _make_client(session)
    client.search_listings(query="x")
    # SAMPLE_TOKEN_RESPONSE includes a rotated refresh_token
    assert client._refresh_token == "test-refresh-token-rotated"


def test_401_during_request_refreshes_token_and_retries():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.side_effect = [
        _err_response(401),
        _ok_response(SAMPLE_LISTING_SEARCH),
    ]
    client = _make_client(session)
    result = client.search_listings(query="widget")
    assert result["count"] == 2
    # First token + refresh = 2 POSTs
    assert session.post.call_count == 2
    assert session.request.call_count == 2


def test_headers_include_api_key_and_bearer():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response({"results": [], "count": 0})
    client = _make_client(session)
    client.search_listings(query="x")
    headers = session.request.call_args.kwargs["headers"]
    assert headers["x-api-key"] == "sandbox-api-key"
    assert headers["Authorization"].startswith("Bearer ")


# ---- error / retry handling -------------------------------------------


def test_500_response_retries_then_raises(monkeypatch):
    import etsy_mcp.client as client_module

    monkeypatch.setattr(client_module.time, "sleep", lambda *_: None)
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _err_response(500)
    client = _make_client(session)
    with pytest.raises(EtsyError, match="Transient Etsy error"):
        client.search_listings(query="x")
    assert session.request.call_count == 3  # max_retries


def test_429_is_retried(monkeypatch):
    import etsy_mcp.client as client_module

    monkeypatch.setattr(client_module.time, "sleep", lambda *_: None)
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.side_effect = [
        _err_response(429),
        _ok_response(SAMPLE_LISTING_SEARCH),
    ]
    client = _make_client(session)
    result = client.search_listings(query="widget")
    assert result["count"] == 2


def test_connection_error_retries(monkeypatch):
    import etsy_mcp.client as client_module

    monkeypatch.setattr(client_module.time, "sleep", lambda *_: None)

    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.side_effect = [
        requests.ConnectionError("boom"),
        _ok_response(SAMPLE_LISTING_SEARCH),
    ]
    client = _make_client(session)
    result = client.search_listings(query="x")
    assert result["count"] == 2


def test_404_does_not_retry():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _err_response(404)
    client = _make_client(session)
    with pytest.raises(EtsyError) as exc_info:
        client.search_listings(query="x")
    assert exc_info.value.status_code == 404
    assert session.request.call_count == 1


# ---- read endpoints ----------------------------------------------------


def test_search_listings_global():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(SAMPLE_LISTING_SEARCH)
    client = _make_client(session)

    result = client.search_listings(query="widget")
    args, kwargs = session.request.call_args
    assert args[0] == "GET"
    assert args[1].endswith("/listings/active")
    assert kwargs["params"]["keywords"] == "widget"
    assert result["count"] == 2


def test_search_listings_shop_scoped():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(SAMPLE_LISTING_SEARCH)
    client = _make_client(session)

    client.search_listings(query="widget", shop_id=SANDBOX_SHOP_PRIMARY)
    args, _ = session.request.call_args
    assert args[1].endswith(f"/shops/{SANDBOX_SHOP_PRIMARY}/listings/active")


def test_search_listings_clamps_limit():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(SAMPLE_LISTING_SEARCH)
    client = _make_client(session)
    client.search_listings(query="x", limit=999)
    assert session.request.call_args.kwargs["params"]["limit"] == 100


def test_get_listing_returns_record():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(SAMPLE_LISTING)
    client = _make_client(session)
    result = client.get_listing(listing_id=1234567890)
    assert result is not None
    assert result["listing_id"] == 1234567890


def test_get_listing_returns_none_on_404():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _err_response(404)
    client = _make_client(session)
    assert client.get_listing(listing_id=99999999) is None


def test_get_shop_returns_record():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(SAMPLE_SHOP)
    client = _make_client(session)
    result = client.get_shop(shop_id=SANDBOX_SHOP_PRIMARY)
    assert result is not None
    assert result["shop_name"] == "LoremIpsumStudio"


def test_get_shop_returns_none_on_404():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _err_response(404)
    client = _make_client(session)
    assert client.get_shop(shop_id=999) is None


def test_search_receipts_handles_pagination():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.side_effect = [
        _ok_response(SAMPLE_RECEIPTS_PAGE_1),
        _ok_response(SAMPLE_RECEIPTS_PAGE_2),
    ]
    client = _make_client(session)

    out = list(
        client.search_receipts(
            shop_id=SANDBOX_SHOP_PRIMARY,
            date_from=date(2026, 4, 25),
            date_to=date(2026, 4, 26),
        )
    )
    assert len(out) == 3
    assert {r["receipt_id"] for r in out} == {5550001, 5550002, 5550003}


def test_search_receipts_passes_unix_timestamps():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response({"results": [], "count": 0})
    client = _make_client(session)
    list(
        client.search_receipts(
            shop_id=SANDBOX_SHOP_PRIMARY,
            date_from=date(2026, 4, 26),
            date_to=date(2026, 4, 26),
        )
    )
    params = session.request.call_args.kwargs["params"]
    assert isinstance(params["min_created"], int)
    assert isinstance(params["max_created"], int)
    assert params["max_created"] > params["min_created"]


def test_search_receipts_passes_status_filter():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response({"results": [], "count": 0})
    client = _make_client(session)
    list(
        client.search_receipts(
            shop_id=SANDBOX_SHOP_PRIMARY,
            date_from=date(2026, 4, 26),
            date_to=date(2026, 4, 26),
            status="open",
        )
    )
    params = session.request.call_args.kwargs["params"]
    assert params["status"] == "open"


def test_search_receipts_rejects_inverted_range():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    client = _make_client(session)
    with pytest.raises(ValueError, match="date_from must be <= date_to"):
        list(
            client.search_receipts(
                shop_id=SANDBOX_SHOP_PRIMARY,
                date_from=date(2026, 4, 26),
                date_to=date(2026, 4, 25),
            )
        )


def test_get_receipt_returns_detail():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(SAMPLE_RECEIPT_DETAIL)
    client = _make_client(session)
    result = client.get_receipt(shop_id=SANDBOX_SHOP_PRIMARY, receipt_id=5550001)
    assert result is not None
    assert result["receipt_id"] == 5550001
    assert len(result["transactions"]) == 2


def test_get_receipt_returns_none_on_404():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _err_response(404)
    client = _make_client(session)
    assert client.get_receipt(shop_id=SANDBOX_SHOP_PRIMARY, receipt_id=99) is None


def test_get_listing_inventory():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(SAMPLE_INVENTORY)
    client = _make_client(session)
    inv = client.get_listing_inventory(listing_id=1234567890)
    assert inv is not None
    assert len(inv["products"]) == 2
    assert inv["products"][0]["sku"] == "LOREM-WIDGET-RED"


def test_get_listing_inventory_404():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _err_response(404)
    client = _make_client(session)
    assert client.get_listing_inventory(listing_id=999) is None


def test_get_active_listings_paginates():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.side_effect = [
        _ok_response(SAMPLE_ACTIVE_LISTINGS_PAGE_1),
        _ok_response(SAMPLE_ACTIVE_LISTINGS_PAGE_2),
    ]
    client = _make_client(session)
    out = list(client.get_active_listings(shop_id=SANDBOX_SHOP_PRIMARY, limit=500))
    assert len(out) == 3


def test_get_active_listings_respects_soft_limit():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(SAMPLE_ACTIVE_LISTINGS_PAGE_1)
    client = _make_client(session)
    out = list(client.get_active_listings(shop_id=SANDBOX_SHOP_PRIMARY, limit=1))
    assert len(out) == 1


def test_get_shop_stats_composes_view():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    # First request for get_shop, then a single page of receipts.
    session.request.side_effect = [
        _ok_response(SAMPLE_SHOP),
        _ok_response(SAMPLE_RECEIPTS_PAGE_1),
        _ok_response(SAMPLE_RECEIPTS_PAGE_2),
    ]
    client = _make_client(session)
    stats = client.get_shop_stats(shop_id=SANDBOX_SHOP_PRIMARY, period="30d")
    assert stats["shop_id"] == SANDBOX_SHOP_PRIMARY
    assert stats["period"] == "30d"
    assert stats["period_days"] == 30
    assert stats["favorers"] == 314
    assert stats["active_listings"] == 87
    assert stats["orders"] == 3
    assert stats["currency_code"] == "USD"
    # 5998 + 1250 + 19900 = 27148 cents
    assert stats["revenue_minor_units"] == 27148


def test_parse_period_days():
    assert _parse_period_days("7d") == 7
    assert _parse_period_days("30d") == 30
    assert _parse_period_days("90D") == 90
    with pytest.raises(ValueError):
        _parse_period_days("")
    with pytest.raises(ValueError):
        _parse_period_days("1week")
    with pytest.raises(ValueError):
        _parse_period_days("0d")
    with pytest.raises(ValueError):
        _parse_period_days("400d")


def test_base_url_normalization():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response({"results": [], "count": 0})
    client = EtsyClient(
        base_url="https://api.etsy.invalid/v3/application",  # no trailing slash
        api_key="k",
        refresh_token="r",
        session=session,
        token_url=TOKEN_URL,
    )
    client.search_listings(query="x")
    assert client.base_url.endswith("/")


def test_max_retries_clamped_to_minimum_one():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response({"results": [], "count": 0})
    client = EtsyClient(
        base_url="https://api.etsy.invalid/v3/application/",
        api_key="k",
        refresh_token="r",
        max_retries=0,
        session=session,
        token_url=TOKEN_URL,
    )
    client.search_listings(query="x")  # should succeed once
