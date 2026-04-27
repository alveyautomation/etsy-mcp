# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in `etsy-mcp`, please report it
responsibly. Do **not** open a public GitHub issue for security concerns.

**Contact:** open a private security advisory on the GitHub repository (path TBD
post-launch), or email the maintainer directly. We aim to respond to reports
within 72 hours.

## Scope

In scope:

- The MCP server entry point (`etsy_mcp/server.py`)
- The Etsy HTTP client (`etsy_mcp/client.py`)
- Configuration and credential handling (`etsy_mcp/config.py`)
- Packaged dependencies and their pinned versions

Out of scope:

- The upstream Etsy Open API itself (report directly to Etsy, Inc.)
- The MCP protocol specification or the official MCP Python SDK
- Bugs that require an attacker to already control the host running the server

## Credential handling

This project never logs Etsy API keys, refresh tokens, or access tokens.
Credentials are read only from environment variables, kept in memory for the
lifetime of the process, and refreshed on `401`. If a rotated refresh token is
returned by Etsy during access-token refresh, the new value is adopted in
memory only and is **not** persisted to disk by this server.

If you find a code path that violates this, report it as a security issue.

## OAuth scope guidance

`etsy-mcp` v0.1 only calls `GET` endpoints. When provisioning the OAuth
refresh token used by the server, request the **minimum** read-only scopes
needed:

- `listings_r` — read listings and inventory
- `shops_r` — read shop info
- `transactions_r` — read receipts and transactions

Do **not** grant write scopes (`*_w`) to the server's refresh token. v0.1
cannot use them; v0.2's write tools (when shipped) will document an explicit
opt-in.

## Disclosure timeline

Our default policy is coordinated disclosure: we will work with the reporter to
ship a fix and credit the discovery on a timeline that gives users time to
upgrade. The default embargo is 30 days from confirmed reproduction.
