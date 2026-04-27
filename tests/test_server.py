"""Tests for the MCP server tool layer.

We exercise the tool functions directly (their underlying Python callable)
to avoid spinning up a real MCP transport in unit tests. The functions
return JSON-encoded envelopes; we decode and assert on shape.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from etsy_mcp import server as srv
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
    SANDBOX_SHOP_PRIMARY,
)


def _call(tool, **kwargs):
    """Invoke a FastMCP-registered tool's underlying Python function."""
    func = getattr(tool, "fn", None) or tool
    return func(**kwargs)


def _decode(envelope: str) -> dict:
    return json.loads(envelope)


def _install_fake_client(monkeypatch, **methods):
    """Replace the lazy-instantiated client with a MagicMock."""
    fake = MagicMock()
    for name, value in methods.items():
        getattr(fake, name).return_value = value if not callable(value) else None
        if callable(value) and not isinstance(value, MagicMock):
            getattr(fake, name).side_effect = value
    monkeypatch.setattr(srv, "_get_client", lambda: fake)
    from etsy_mcp.config import Settings

    monkeypatch.setattr(
        srv,
        "_settings",
        Settings(
            api_url="https://api.etsy.invalid/v3/application/",
            api_key="k",
            refresh_token="r",
            default_shop_id=SANDBOX_SHOP_PRIMARY,
            http_timeout=10,
            max_retries=2,
        ),
    )
    return fake


# ---- search_listings --------------------------------------------------


def test_search_listings_happy(monkeypatch):
    _install_fake_client(monkeypatch, search_listings=SAMPLE_LISTING_SEARCH)
    out = _decode(_call(srv.etsy_search_listings, query="widget"))
    assert out["ok"] is True
    assert out["data"]["count"] == 2
    assert out["data"]["results"][0]["listing_id"] == 1234567890


def test_search_listings_rejects_blank_query(monkeypatch):
    _install_fake_client(monkeypatch)
    out = _decode(_call(srv.etsy_search_listings, query="   "))
    assert out["ok"] is False
    assert "query is required" in out["error"]


def test_search_listings_passes_shop_id(monkeypatch):
    fake = _install_fake_client(monkeypatch, search_listings=SAMPLE_LISTING_SEARCH)
    _call(srv.etsy_search_listings, query="widget", shop_id=SANDBOX_SHOP_PRIMARY)
    fake.search_listings.assert_called_once()
    assert (
        fake.search_listings.call_args.kwargs["shop_id"]
        == SANDBOX_SHOP_PRIMARY
    )


def test_search_listings_clamps_limit(monkeypatch):
    fake = _install_fake_client(monkeypatch, search_listings=SAMPLE_LISTING_SEARCH)
    _call(srv.etsy_search_listings, query="x", limit=999)
    assert fake.search_listings.call_args.kwargs["limit"] == 100


# ---- get_listing -------------------------------------------------------


def test_get_listing_happy(monkeypatch):
    _install_fake_client(monkeypatch, get_listing=SAMPLE_LISTING)
    out = _decode(_call(srv.etsy_get_listing, listing_id=1234567890))
    assert out["ok"] is True
    assert out["data"]["listing_id"] == 1234567890


def test_get_listing_missing_returns_null(monkeypatch):
    _install_fake_client(monkeypatch, get_listing=None)
    out = _decode(_call(srv.etsy_get_listing, listing_id=99))
    assert out["ok"] is True
    assert out["data"] is None


def test_get_listing_rejects_non_positive(monkeypatch):
    _install_fake_client(monkeypatch)
    out = _decode(_call(srv.etsy_get_listing, listing_id=0))
    assert out["ok"] is False


# ---- get_shop ---------------------------------------------------------


def test_get_shop_happy(monkeypatch):
    _install_fake_client(monkeypatch, get_shop=SAMPLE_SHOP)
    out = _decode(_call(srv.etsy_get_shop, shop_id=SANDBOX_SHOP_PRIMARY))
    assert out["ok"] is True
    assert out["data"]["shop_name"] == "LoremIpsumStudio"


def test_get_shop_rejects_non_positive(monkeypatch):
    _install_fake_client(monkeypatch)
    out = _decode(_call(srv.etsy_get_shop, shop_id=0))
    assert out["ok"] is False


# ---- search_orders -----------------------------------------------------


def test_search_orders_happy(monkeypatch):
    fake = _install_fake_client(monkeypatch)
    fake.search_receipts.return_value = iter(
        SAMPLE_RECEIPTS_PAGE_1["results"] + SAMPLE_RECEIPTS_PAGE_2["results"]
    )
    out = _decode(
        _call(
            srv.etsy_search_orders,
            date_from="2026-04-25",
            date_to="2026-04-26",
            shop_id=SANDBOX_SHOP_PRIMARY,
        )
    )
    assert out["ok"] is True
    assert out["data"]["count"] == 3
    assert {o["receipt_id"] for o in out["data"]["orders"]} == {
        5550001,
        5550002,
        5550003,
    }


def test_search_orders_rejects_bad_date(monkeypatch):
    _install_fake_client(monkeypatch)
    out = _decode(
        _call(
            srv.etsy_search_orders,
            date_from="not-a-date",
            date_to="2026-04-26",
        )
    )
    assert out["ok"] is False
    assert "ISO date" in out["error"]


def test_search_orders_uses_default_shop_id(monkeypatch):
    fake = _install_fake_client(monkeypatch)
    fake.search_receipts.return_value = iter([])
    _call(srv.etsy_search_orders, date_from="2026-04-26", date_to="2026-04-26")
    fake.search_receipts.assert_called_once()
    assert fake.search_receipts.call_args.kwargs["shop_id"] == SANDBOX_SHOP_PRIMARY


def test_search_orders_respects_limit(monkeypatch):
    fake = _install_fake_client(monkeypatch)
    fake.search_receipts.return_value = iter(
        SAMPLE_RECEIPTS_PAGE_1["results"] + SAMPLE_RECEIPTS_PAGE_2["results"]
    )
    out = _decode(
        _call(
            srv.etsy_search_orders,
            date_from="2026-04-26",
            date_to="2026-04-26",
            limit=2,
        )
    )
    assert out["data"]["count"] == 2
    assert out["data"]["limit_reached"] is True


def test_search_orders_passes_status_filter(monkeypatch):
    fake = _install_fake_client(monkeypatch)
    fake.search_receipts.return_value = iter([])
    _call(
        srv.etsy_search_orders,
        date_from="2026-04-26",
        date_to="2026-04-26",
        status="open",
    )
    assert fake.search_receipts.call_args.kwargs["status"] == "open"


# ---- get_order ---------------------------------------------------------


def test_get_order_happy(monkeypatch):
    _install_fake_client(monkeypatch, get_receipt=SAMPLE_RECEIPT_DETAIL)
    out = _decode(_call(srv.etsy_get_order, receipt_id=5550001))
    assert out["ok"] is True
    assert out["data"]["receipt_id"] == 5550001


def test_get_order_rejects_non_positive(monkeypatch):
    _install_fake_client(monkeypatch)
    out = _decode(_call(srv.etsy_get_order, receipt_id=0))
    assert out["ok"] is False


def test_get_order_missing_returns_null(monkeypatch):
    _install_fake_client(monkeypatch, get_receipt=None)
    out = _decode(_call(srv.etsy_get_order, receipt_id=999))
    assert out["ok"] is True
    assert out["data"] is None


# ---- get_inventory -----------------------------------------------------


def test_get_inventory_happy(monkeypatch):
    _install_fake_client(monkeypatch, get_listing_inventory=SAMPLE_INVENTORY)
    out = _decode(_call(srv.etsy_get_inventory, listing_id=1234567890))
    assert out["ok"] is True
    assert len(out["data"]["products"]) == 2


def test_get_inventory_missing(monkeypatch):
    _install_fake_client(monkeypatch, get_listing_inventory=None)
    out = _decode(_call(srv.etsy_get_inventory, listing_id=999))
    assert out["ok"] is True
    assert out["data"] is None


def test_get_inventory_rejects_non_positive(monkeypatch):
    _install_fake_client(monkeypatch)
    out = _decode(_call(srv.etsy_get_inventory, listing_id=0))
    assert out["ok"] is False


# ---- get_shop_stats ---------------------------------------------------


def test_get_shop_stats_happy(monkeypatch):
    fake_stats = {
        "shop_id": SANDBOX_SHOP_PRIMARY,
        "period": "30d",
        "period_days": 30,
        "date_from": "2026-03-27",
        "date_to": "2026-04-26",
        "favorers": 314,
        "active_listings": 87,
        "orders": 3,
        "revenue_minor_units": 27148,
        "currency_code": "USD",
    }
    _install_fake_client(monkeypatch, get_shop_stats=fake_stats)
    out = _decode(_call(srv.etsy_get_shop_stats, shop_id=SANDBOX_SHOP_PRIMARY))
    assert out["ok"] is True
    assert out["data"]["orders"] == 3
    assert out["data"]["revenue_minor_units"] == 27148


def test_get_shop_stats_rejects_non_positive(monkeypatch):
    _install_fake_client(monkeypatch)
    out = _decode(_call(srv.etsy_get_shop_stats, shop_id=0))
    assert out["ok"] is False


def test_get_shop_stats_propagates_period_error(monkeypatch):
    fake = _install_fake_client(monkeypatch)
    fake.get_shop_stats.side_effect = ValueError("period must be of the form '<N>d'")
    out = _decode(
        _call(srv.etsy_get_shop_stats, shop_id=SANDBOX_SHOP_PRIMARY, period="bad")
    )
    assert out["ok"] is False
    assert "period" in out["error"]


# ---- get_active_listings ----------------------------------------------


def test_get_active_listings_happy(monkeypatch):
    fake = _install_fake_client(monkeypatch)
    fake.get_active_listings.return_value = iter(
        SAMPLE_ACTIVE_LISTINGS_PAGE_1["results"]
        + SAMPLE_ACTIVE_LISTINGS_PAGE_2["results"]
    )
    out = _decode(
        _call(srv.etsy_get_active_listings, shop_id=SANDBOX_SHOP_PRIMARY)
    )
    assert out["ok"] is True
    assert out["data"]["count"] == 3


def test_get_active_listings_respects_limit(monkeypatch):
    fake = _install_fake_client(monkeypatch)
    fake.get_active_listings.return_value = iter(
        SAMPLE_ACTIVE_LISTINGS_PAGE_1["results"]
        + SAMPLE_ACTIVE_LISTINGS_PAGE_2["results"]
    )
    out = _decode(
        _call(
            srv.etsy_get_active_listings,
            shop_id=SANDBOX_SHOP_PRIMARY,
            limit=2,
        )
    )
    assert out["data"]["count"] == 2
    assert out["data"]["limit_reached"] is True


def test_get_active_listings_rejects_non_positive(monkeypatch):
    _install_fake_client(monkeypatch)
    out = _decode(_call(srv.etsy_get_active_listings, shop_id=0))
    assert out["ok"] is False


# ---- env-driven init --------------------------------------------------


def test_resolve_shop_id_raises_without_default(monkeypatch):
    from etsy_mcp.config import Settings

    monkeypatch.setattr(
        srv,
        "_settings",
        Settings(
            api_url="https://api.etsy.invalid/v3/application/",
            api_key="k",
            refresh_token="r",
            default_shop_id=None,
            http_timeout=10,
            max_retries=2,
        ),
    )
    with pytest.raises(ValueError, match="shop_id is required"):
        srv._resolve_shop_id(None)
