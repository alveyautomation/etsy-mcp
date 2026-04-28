# 5-Minute Demo Script

Use this script to record a Loom walkthrough of `etsy-mcp` for the launch posts. Total target: **5 minutes**.

Record in 1080p, monospace terminal at 14pt minimum. Use a sandbox / test Etsy account or a personal shop with no sensitive customer data on screen, never expose real buyer info.

## Setup before hitting record

- Fresh terminal window (cleared scrollback).
- `.env` populated with sandbox credentials. Test that `etsy-mcp` runs and Claude Code sees the tools.
- Have the README open in a second tab for the cold open.
- Have one listing, one receipt, and one period range pre-identified in the sandbox so live queries return non-empty results.
- Blur or crop any buyer names / addresses that appear in receipt detail before publishing.

## Script

### 0:00. 0:30  Cold open

> "If you sell on Etsy and you've ever wanted Claude to just *know* what's in your shop, this is for you. I built `etsy-mcp`, the first production-grade MCP server for Etsy. Read-only, MIT-licensed, takes about 90 seconds to install."

Show the README hero section. Pan slowly through the tool table.

### 0:30. 1:30  Install and configure

Show in the terminal:

```bash
pip install etsy-mcp
cp .env.example .env
# edit .env: paste keystring + refresh token + shop_id
```

Then show the Claude Code MCP config block, paste it into `~/.claude/claude_code_config.json`. Restart Claude Code. Show the new tools appearing in a new session.

> "Three env vars and one config block. That's it."

### 1:30. 2:30  Live demo: shop scan

Open a fresh Claude Code session. Type:

> "Use etsy to search my shop for active listings with the word 'widget' and tell me which ones are below quantity 5."

Watch Claude call `etsy_search_listings`, return results, then chain into `etsy_get_inventory` for low-stock variants. Read off the count.

### 2:30. 3:30  Live demo: orders

> "Show me yesterday's orders. Group by buyer and tell me the total revenue."

Claude calls `etsy_search_orders`, gets a list, groups them. Show the resulting summary in the chat.

> "Notice that I never wrote any code. Claude is reading Etsy directly through the MCP server."

### 3:30. 4:30  Live demo: combined operation

> "Pull a 30-day stats rollup for the shop, and then for the top-grossing listing in that period, tell me how much inventory is left across all variations."

Claude calls `etsy_get_shop_stats`, then chains `etsy_search_orders` + `etsy_get_inventory` to identify and report on the listing. Highlight the multi-step reasoning happening over the MCP surface.

> "This is the unlock. Claude can chain reads across listings, orders, inventory, and shop stats in one conversation. Without an SDK. Without any code I had to write."

### 4:30. 5:00  Close

Show the GitHub repo briefly. Mention:

- MIT-licensed, free to use
- Read-only in v0.1, write tools coming in v0.2
- Open to issues + PRs
- Star + share if it's useful

> "Repo link in the description. v0.2 with write tools is a few weeks out, leave a comment if there's a specific endpoint you'd like exposed first."

End on the README hero shot.

## Post-recording

- Trim silence at start/end.
- Add captions (Loom auto-caption is fine, just review for brand-name accuracy).
- Thumbnail: a screenshot of the multi-step demo with the tool calls visible.
- Double-check no buyer PII or real shipping addresses are visible in any frame.

## Distribution

After recording, the launch posts go to:

1. **Twitter/X**, single thread, 6-8 tweets, embed the Loom in tweet 1.
2. **Reddit r/MCP**, title: *"etsy-mcp: first production-grade MCP server for Etsy (read-only, MIT)"*. Body: short framing + Loom + GitHub link.
3. **Reddit r/EtsySellers**, different framing, lead with the use case (*"Use Claude to query your Etsy shop, listings, and orders"*), Loom + GitHub link.

Draft copy for all three lives in `LAUNCH_POSTS.md` (to be created).
