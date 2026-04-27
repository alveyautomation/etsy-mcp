"""Shared pytest fixtures and helpers."""

from __future__ import annotations

import os
from typing import Iterator
from unittest.mock import MagicMock

import pytest

from etsy_mcp.client import EtsyClient
from tests.fixtures import SAMPLE_TOKEN_RESPONSE


@pytest.fixture(autouse=True)
def _reset_server_singletons():
    """Each test starts with a fresh server-module singleton state.

    The MCP server lazily caches a Settings + EtsyClient instance.
    Reset between tests so env-var changes take effect and one test's
    mock client doesn't leak into the next.
    """
    from etsy_mcp import server as srv

    srv._settings = None
    srv._client = None
    yield
    srv._settings = None
    srv._client = None


@pytest.fixture
def env_credentials(monkeypatch) -> Iterator[None]:
    monkeypatch.setenv(
        "ETSY_API_URL", "https://api.etsy.invalid/v3/application/"
    )
    monkeypatch.setenv("ETSY_API_KEY", "sandbox-api-key")
    monkeypatch.setenv("ETSY_REFRESH_TOKEN", "sandbox-refresh-token")
    monkeypatch.setenv("ETSY_DEFAULT_SHOP_ID", "90001")
    yield


@pytest.fixture
def mock_session() -> MagicMock:
    """A mocked `requests.Session` that returns canned token + JSON bodies."""
    session = MagicMock()

    def post(url, data=None, json=None, headers=None, timeout=None):
        if "oauth/token" in url:
            resp = MagicMock()
            resp.status_code = 200
            resp.ok = True
            resp.json.return_value = SAMPLE_TOKEN_RESPONSE
            return resp
        raise AssertionError(f"Unexpected POST: {url}")

    session.post.side_effect = post
    return session


@pytest.fixture
def client(mock_session) -> EtsyClient:
    return EtsyClient(
        base_url="https://api.etsy.invalid/v3/application/",
        api_key="sandbox-api-key",
        refresh_token="sandbox-refresh-token",
        timeout=10,
        max_retries=2,
        session=mock_session,
        token_url="https://api.etsy.invalid/v3/public/oauth/token",
    )


def _integration_enabled() -> bool:
    return os.environ.get("ETSY_INTEGRATION_TESTS") == "1"


integration_only = pytest.mark.skipif(
    not _integration_enabled(),
    reason="Integration tests require ETSY_INTEGRATION_TESTS=1 + valid creds",
)
