"""Configuration for the Etsy MCP server.

All settings come from environment variables. Nothing is persisted to disk
and nothing is logged. See `.env.example` for the full list of supported
variables.

Etsy's Open API v3 uses OAuth 2.0 with PKCE. The MCP server expects the
seller (or a one-time setup script) to have already completed the OAuth
dance and stored the resulting refresh token. The server uses the refresh
token to mint short-lived access tokens at runtime.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


def _str(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.environ.get(name, default)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer") from exc


def _optional_int(name: str) -> Optional[int]:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer") from exc


@dataclass(frozen=True)
class Settings:
    """Runtime configuration for the MCP server."""

    api_url: str
    api_key: str
    refresh_token: str
    default_shop_id: Optional[int]
    http_timeout: int
    max_retries: int

    @classmethod
    def from_env(cls) -> "Settings":
        api_url = _str("ETSY_API_URL", "https://api.etsy.com/v3/application/")
        api_key = _str("ETSY_API_KEY")
        refresh_token = _str("ETSY_REFRESH_TOKEN")

        missing = [
            name
            for name, value in [
                ("ETSY_API_KEY", api_key),
                ("ETSY_REFRESH_TOKEN", refresh_token),
            ]
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Missing required environment variables: "
                + ", ".join(missing)
                + ". See .env.example for the full list."
            )

        # Trailing slash is required for path joining
        assert api_url is not None
        if not api_url.endswith("/"):
            api_url = api_url + "/"

        return cls(
            api_url=api_url,
            api_key=api_key,  # type: ignore[arg-type]
            refresh_token=refresh_token,  # type: ignore[arg-type]
            default_shop_id=_optional_int("ETSY_DEFAULT_SHOP_ID"),
            http_timeout=_int("ETSY_HTTP_TIMEOUT", 60),
            max_retries=_int("ETSY_MAX_RETRIES", 3),
        )
