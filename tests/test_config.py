"""Tests for etsy_mcp.config.Settings."""

from __future__ import annotations

import pytest

from etsy_mcp.config import Settings


def test_settings_from_env_happy_path(monkeypatch):
    monkeypatch.setenv("ETSY_API_URL", "https://api.etsy.invalid/v3/application/")
    monkeypatch.setenv("ETSY_API_KEY", "sandbox-api-key")
    monkeypatch.setenv("ETSY_REFRESH_TOKEN", "sandbox-refresh-token")
    monkeypatch.setenv("ETSY_DEFAULT_SHOP_ID", "90001")
    monkeypatch.setenv("ETSY_HTTP_TIMEOUT", "45")
    monkeypatch.setenv("ETSY_MAX_RETRIES", "5")

    s = Settings.from_env()
    assert s.api_url == "https://api.etsy.invalid/v3/application/"
    assert s.api_key == "sandbox-api-key"
    assert s.refresh_token == "sandbox-refresh-token"
    assert s.default_shop_id == 90001
    assert s.http_timeout == 45
    assert s.max_retries == 5


def test_settings_appends_trailing_slash(monkeypatch):
    monkeypatch.setenv("ETSY_API_URL", "https://api.etsy.invalid/v3/application")
    monkeypatch.setenv("ETSY_API_KEY", "k")
    monkeypatch.setenv("ETSY_REFRESH_TOKEN", "r")

    s = Settings.from_env()
    assert s.api_url.endswith("/")


def test_settings_default_api_url(monkeypatch):
    monkeypatch.delenv("ETSY_API_URL", raising=False)
    monkeypatch.setenv("ETSY_API_KEY", "k")
    monkeypatch.setenv("ETSY_REFRESH_TOKEN", "r")

    s = Settings.from_env()
    assert s.api_url == "https://api.etsy.com/v3/application/"


def test_settings_missing_credentials_raises(monkeypatch):
    monkeypatch.delenv("ETSY_API_KEY", raising=False)
    monkeypatch.delenv("ETSY_REFRESH_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="Missing required environment variables"):
        Settings.from_env()


def test_settings_missing_only_refresh_token(monkeypatch):
    monkeypatch.setenv("ETSY_API_KEY", "k")
    monkeypatch.delenv("ETSY_REFRESH_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="ETSY_REFRESH_TOKEN"):
        Settings.from_env()


def test_settings_optional_shop_id_blank(monkeypatch):
    monkeypatch.setenv("ETSY_API_KEY", "k")
    monkeypatch.setenv("ETSY_REFRESH_TOKEN", "r")
    monkeypatch.setenv("ETSY_DEFAULT_SHOP_ID", "")

    s = Settings.from_env()
    assert s.default_shop_id is None


def test_settings_invalid_int(monkeypatch):
    monkeypatch.setenv("ETSY_API_KEY", "k")
    monkeypatch.setenv("ETSY_REFRESH_TOKEN", "r")
    monkeypatch.setenv("ETSY_HTTP_TIMEOUT", "not-a-number")

    with pytest.raises(ValueError, match="must be an integer"):
        Settings.from_env()


def test_settings_default_timeout_and_retries(monkeypatch):
    monkeypatch.setenv("ETSY_API_KEY", "k")
    monkeypatch.setenv("ETSY_REFRESH_TOKEN", "r")
    monkeypatch.delenv("ETSY_HTTP_TIMEOUT", raising=False)
    monkeypatch.delenv("ETSY_MAX_RETRIES", raising=False)

    s = Settings.from_env()
    assert s.http_timeout == 60
    assert s.max_retries == 3
