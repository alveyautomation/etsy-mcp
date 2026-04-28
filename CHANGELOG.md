# Changelog

All notable changes to `etsy-mcp` are documented in this file. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0]. 2026-04-26

Initial public release.

### Added

- MCP server entry point (`etsy_mcp/server.py`) using the official `mcp` Python SDK with `FastMCP`.
- Eight read-only tools:
  - `etsy_search_listings`
  - `etsy_get_listing`
  - `etsy_get_shop`
  - `etsy_search_orders`
  - `etsy_get_order`
  - `etsy_get_inventory`
  - `etsy_get_shop_stats`
  - `etsy_get_active_listings`
- HTTP client (`etsy_mcp/client.py`):
  - OAuth 2.0 refresh-token → bearer-token exchange via Etsy's
    `/v3/public/oauth/token` endpoint, cached with ~55 min TTL.
  - Adopts rotated refresh tokens returned by Etsy in-memory.
  - Dual-credential headers: `x-api-key` keystring + `Authorization: Bearer`.
  - Automatic token refresh on `401`.
  - Exponential backoff retry on transient `5xx`, `429`, and connection errors.
  - Transparent pagination for `search_receipts` and `get_active_listings`.
  - Composed `get_shop_stats` rollup from shop record + receipts in window.
- Configuration via environment variables (`etsy_mcp/config.py`).
- Pytest suite with mocked HTTP responses (49 tests, all synthetic fixtures).
- Pre-commit configuration: gitleaks, trufflehog, ruff, ruff-format, tenant-fingerprint scrubber.
- MIT license, security policy, contributing guidance in README.

### Notes

- v0.1 is read-only by design. Write endpoints (create draft listing, update
  inventory, mark receipt shipped) are planned for v0.2.
- Integration tests against a live Etsy sandbox account are gated by
  `ETSY_INTEGRATION_TESTS=1` and are not exercised by default.
