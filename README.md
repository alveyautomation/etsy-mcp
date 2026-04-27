# etsy-mcp

> The first production-grade Model Context Protocol server for Etsy. Plug Claude into your Etsy shop's listings, inventory, orders, and stats â€” read-only, in five minutes.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-1.x-purple.svg)](https://modelcontextprotocol.io)

## Why this exists

Etsy's Open API v3 is well-documented and stable, but every seller who wants to put an LLM on top of their shop ends up writing the same OAuth-and-pagination glue from scratch. Existing MCP integrations are thin demos, missing token refresh, retry logic, and the per-shop pagination Etsy actually requires.

If you sell on Etsy and you've ever wanted Claude (or any MCP-aware AI assistant) to *just know* what's in your shop â€” what's listed, what shipped yesterday, what's running low â€” that gap is the difference between *"summarize today's orders"* working out of the box and *"summarize today's orders"* requiring a custom integration.

`etsy-mcp` closes that gap. It's a tiny, well-tested, MIT-licensed MCP server that exposes eight read-only Etsy endpoints to any MCP client. Built from years of running production ecommerce automation at scale.

## What you can do with it

Wire this server into Claude Code, Claude Desktop, or any MCP host, then ask things like:

- *"Search my shop for any listing with the word `vintage` in the title and tell me how many are below quantity 5."*
- *"How many orders did I get yesterday? Group by buyer and total revenue."*
- *"Pull receipt 5550001 and tell me which transactions shipped â€” and what's left to ship."*
- *"What were my shop stats over the last 30 days? Compare orders, favorers, and active listings."*
- *"For listing 1234567890, show me every variation, its SKU, and current quantity."*

Claude reads your shop directly. No copy-paste, no spreadsheets, no custom pipelines.

## Tools (v0.1, all read-only)

| Tool                        | What it does                                                  |
| --------------------------- | ------------------------------------------------------------- |
| `etsy_search_listings`      | Keyword search across active listings, optionally shop-scoped. |
| `etsy_get_listing`          | Fetch one listing by ID.                                       |
| `etsy_get_shop`             | Fetch the shop record (name, currency, counts, vacation).      |
| `etsy_search_orders`        | List receipts (orders) in a date window for one shop.          |
| `etsy_get_order`            | Fetch one receipt by ID, including line-item transactions.     |
| `etsy_get_inventory`        | Variation-level inventory (SKU, quantity, price) for a listing.|
| `etsy_get_shop_stats`       | Composed period rollup: orders, favorers, revenue, listings.   |
| `etsy_get_active_listings`  | Paginated list of every active listing in a shop.              |

Write endpoints (create draft listing, update inventory, mark receipt shipped) are intentionally **not** in v0.1. They are planned for v0.2 once read-only ergonomics settle.

## Install

```bash
pip install etsy-mcp
```

> v0.1 ships from this repository. PyPI publication is pending â€” for now, install with `pip install git+https://github.com/alveyautomation/etsy-mcp` or clone and run `pip install -e .` locally.

## Configure credentials

The server reads everything from environment variables. Copy `.env.example` to `.env` and fill in your tenant:

```bash
ETSY_API_URL=https://api.etsy.com/v3/application/   # default; usually leave alone
ETSY_API_KEY=your-keystring-from-etsy-developers
ETSY_REFRESH_TOKEN=oauth2-refresh-token-for-your-shop
ETSY_DEFAULT_SHOP_ID=                               # optional fallback
ETSY_HTTP_TIMEOUT=60                                # optional, seconds
ETSY_MAX_RETRIES=3                                  # optional
```

### Getting an Etsy API key

1. Visit <https://www.etsy.com/developers/your-apps> and register an app.
2. Copy the **Keystring** â€” that's `ETSY_API_KEY`.
3. Configure the redirect URI for your one-time OAuth bootstrap (e.g. `http://localhost:3000/callback`).

### Getting a refresh token

Etsy uses **OAuth 2.0 with PKCE**. To bootstrap, run any standard OAuth-PKCE flow once with these parameters:

- `response_type=code`
- `client_id=<your keystring>`
- `redirect_uri=<your registered URI>`
- `scope=listings_r shops_r transactions_r` (read-only â€” the minimum this server needs)
- `state=<random>`
- `code_challenge=<PKCE>` and `code_challenge_method=S256`

Exchange the resulting authorization code at `POST https://api.etsy.com/v3/public/oauth/token` for an access + refresh token. Save the **refresh token** as `ETSY_REFRESH_TOKEN`. The server will use it to mint short-lived access tokens automatically.

> **Use minimum-scope read tokens.** v0.1 only calls `GET` endpoints, but defense in depth means you should never grant write scopes (`*_w`) to the server's refresh token. When v0.2 lands with write tools, opt-in by minting a fresh higher-scope token â€” never the other way around.

## Wire into Claude Code

Add to `~/.claude/claude_code_config.json` (or your project's MCP config):

```json
{
  "mcpServers": {
    "etsy": {
      "command": "etsy-mcp",
      "env": {
        "ETSY_API_KEY": "your-keystring",
        "ETSY_REFRESH_TOKEN": "your-refresh-token",
        "ETSY_DEFAULT_SHOP_ID": "12345678"
      }
    }
  }
}
```

Restart Claude Code. The eight `etsy_*` tools will appear in any new session.

## Wire into Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows) and add the same `mcpServers` block as above. Restart the desktop app.

## Tool reference

Every tool returns a JSON envelope:

```json
{ "ok": true,  "data": { ... } }
{ "ok": false, "error": "human-readable message" }
```

### `etsy_search_listings`

```python
etsy_search_listings(
    query: str,                          # required
    shop_id: int | None = None,          # scope to a single shop
    limit: int = 50,                     # max 100 (Etsy server cap)
)
```

When `shop_id` is provided, this hits `/shops/{shop_id}/listings/active`. Otherwise it hits the global `/listings/active` index.

### `etsy_get_listing`

```python
etsy_get_listing(listing_id: int)
```

Returns the listing record, or `data: null` on 404.

### `etsy_get_shop`

```python
etsy_get_shop(shop_id: int)
```

The shop record includes `shop_name`, `currency_code`, `listing_active_count`, `num_favorers`, `is_vacation`, and more.

### `etsy_search_orders`

```python
etsy_search_orders(
    date_from: str,                      # ISO date "YYYY-MM-DD"
    date_to: str,                        # ISO date "YYYY-MM-DD"
    shop_id: int | None = None,          # falls back to default
    status: str | None = None,           # 'open' | 'unshipped' | 'completed' | 'all'
    limit: int = 200,                    # max 1000
)
```

Etsy caps page size at 100; pagination is transparent. The response includes `limit_reached: true` when `limit` was the truncation point.

### `etsy_get_order`

```python
etsy_get_order(receipt_id: int, shop_id: int | None = None)
```

Returns the full receipt (with `transactions[]`), or `data: null` on 404.

### `etsy_get_inventory`

```python
etsy_get_inventory(listing_id: int)
```

Returns `products[]` with `sku`, `property_values`, and `offerings[]` (quantity, price, enabled). Use the offering quantity as the canonical "qty I can sell" number per variation.

### `etsy_get_shop_stats`

```python
etsy_get_shop_stats(shop_id: int, period: str = "30d")
```

A composed rollup. Etsy doesn't expose a first-class `shop/stats` endpoint at v3, so this synthesizes one from the shop record (favorers, active-listing count) and the receipts in the window. Returned shape:

```json
{
  "shop_id": 12345678,
  "period": "30d",
  "period_days": 30,
  "date_from": "2026-03-27",
  "date_to": "2026-04-26",
  "favorers": 314,
  "active_listings": 87,
  "orders": 42,
  "revenue_minor_units": 152400,
  "currency_code": "USD"
}
```

`period` accepts `<N>d` form, max 365 days.

### `etsy_get_active_listings`

```python
etsy_get_active_listings(shop_id: int, limit: int = 200)
```

Paginated dump of every active listing in a shop. Useful for catalog-wide reasoning ("audit my titles for missing keywords"). Soft cap is 1000 to keep one tool invocation bounded.

## Local development

```bash
git clone https://github.com/alveyautomation/etsy-mcp
cd etsy-mcp
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest                                                # 49 tests, ~3s
```

Pre-commit hooks (gitleaks, trufflehog, ruff, formatter, tenant-fingerprint scrubber):

```bash
pip install pre-commit
pre-commit install
```

Integration tests against a real Etsy sandbox are gated behind `ETSY_INTEGRATION_TESTS=1`. They are not required for normal contribution.

## Troubleshooting

**`Failed to refresh Etsy access token`** â€” your refresh token expired or was revoked. Etsy refresh tokens last 90 days from issue, but only if used regularly. Re-run the OAuth-PKCE bootstrap to mint a new one.

**`Missing required environment variables`** â€” the server tried to start before its `.env` was loaded. Either export the vars in the parent shell, or ensure your MCP host config includes them in the `env` block.

**`HTTP 403` on receipts/transactions** â€” the refresh token's scopes are missing `transactions_r`. Re-bootstrap with the read scopes listed above.

**Empty results despite known data** â€” confirm the `shop_id`. Etsy's `/shops/{shop_id}/...` endpoints only return data for shops the OAuth token has been authorized against.

**Pagination feels slow** â€” Etsy caps page size at 100 per request, not us. For large date windows (long order histories), expect multiple round-trips. Lower the `limit` argument to bound the call.

## Contributing

Issues and pull requests welcome. Please:

- Run `pytest` before opening a PR (`pip install -e ".[dev]"`).
- Run `pre-commit run --all-files`.
- Keep additions to v0.1 scope read-only. Write endpoints land in v0.2.
- Synthetic data only in tests â€” no real shop names, listing IDs, or receipt numbers.

## License

MIT â€” see [LICENSE](LICENSE).

## Disclaimer

`etsy-mcp` is an unofficial, third-party integration. It is **not endorsed by, affiliated with, or supported by Etsy, Inc.** "Etsy" is a trademark of Etsy, Inc. Use at your own risk; verify behavior against your shop before depending on it for production decisions.

