# Claude Usage Bar

A macOS menu bar app that shows your Claude Code usage % **exactly matching the `/usage` command** — not an estimate.

The dropdown panel also shows your current plan (read from `~/.claude.json` → `oauthAccount.organizationType` + `organizationRateLimitTier`, e.g. "Max 20x").

The panel's title defaults to "Claude Usage" — if you name the mascot yourself through the setup wizard (e.g. "Affa"), the title automatically becomes "Affa Usage".

The whole UI (setup wizard + dropdown panel) is English-only, so it works for anyone if you pass it along.

## How it works

Since Claude Code v2.1.80, every time Claude Code updates the status line during an active session, it sends JSON over stdin to whatever statusline script you've configured. That JSON includes a `rate_limits` field:

```json
{
  "rate_limits": {
    "five_hour": { "used_percentage": 42, "resets_at": 1742651200 },
    "seven_day": { "used_percentage": 18, "resets_at": 1743120000 }
  }
}
```

These numbers come straight from the server's `anthropic-ratelimit-*` response headers — the same data `/usage` displays, not an estimate.

The app is split into four parts:

1. **`statusline_bridge.py`** — a small script Claude Code calls every time it updates the status line. It captures the `rate_limits` field (plus the real context-window token count) and writes it to a cache file at `~/.claude-usage-bar/rate_limits.json` (while printing the normal status line back out, so the terminal's status bar doesn't disappear).
2. **`claude_usage_bar.py`** — the native menu bar app (PyObjC — `AppKit` + `WebKit`) that reads that cache file and shows it in real time: a pixel-mascot icon in the status bar, plus a dropdown panel on click.
3. **`menu_panel.html`** — the dropdown panel's UI (animated mascot, progress bars, Refresh/Setup/Config/Quit buttons), based on the design in `design/Claude Menu Bar.dc.html` — supports both dark and light themes automatically.
4. **`setup_wizard.html`** — the first-run setup wizard for naming the mascot and picking a color.

## The one real limitation

Data only updates **while Claude Code is actively running** (the status line has to be called before new data exists). If you've had Claude Code closed for hours, the menu bar will show the last value it ever captured — the app will show "⚠️ May be stale" on its own if the cached data is older than 20 minutes. Use Claude Code for a moment and the numbers refresh automatically.

If the statusline hook hasn't been set up at all yet, the app falls back to "estimate mode" (computed from tokens in the transcript log), clearly labeled as not precise.

## Install

### Recommended: install as a Claude Code plugin (auto-launches every session)

```bash
bash scripts/install.sh
```

or install directly from GitHub:

```bash
curl -fsSL https://raw.githubusercontent.com/tanapatdev/claude_usage_bar/main/scripts/install.sh | bash
```

This registers the repo as a local marketplace and installs the plugin at user scope. From then on, the menu bar app auto-launches at the start of every Claude Code session, in any project. The first launch sets up a private venv and installs Python dependencies in the background (~20-60s depending on your network), so the app may take a moment to appear the very first time.

Once installed:
- **`/claude-usage-bar:run`** — manually relaunch the app anytime without waiting for a new session (e.g. after quitting it mid-session)
- Click **"Enable Precise"** in the panel to wire up real `/usage` data (see below) — shows a confirm dialog before touching anything on disk

### Manual install via `claude plugin marketplace`

`scripts/install.sh` is just a wrapper around these two commands:

```bash
claude plugin marketplace add <source>
claude plugin install claude-usage-bar@claude-usage-bar-marketplace
```

Where `<source>` is either:
- **A local directory path** — `claude plugin marketplace add /path/to/claude_usage` (useful for a local clone, no push required)
- **The GitHub URL** — `claude plugin marketplace add https://github.com/tanapatdev/claude_usage_bar.git`

Either way, restart Claude Code afterward (exit and run `claude` again) — plugins and hooks only load at session start, never mid-session.

If the plugin is already installed and you want to force-refresh it to the latest marketplace content, `claude plugin install` alone won't do it (it no-ops when already installed), and `claude plugin update` only refreshes when `.claude-plugin/plugin.json`'s `version` field has changed. To guarantee a fresh copy regardless, uninstall first:

```bash
claude plugin marketplace update claude-usage-bar-marketplace
claude plugin uninstall claude-usage-bar@claude-usage-bar-marketplace
claude plugin install claude-usage-bar@claude-usage-bar-marketplace
```

### Precise mode: the statusline hook

Whether or not you install via the plugin, precise mode needs the statusline hook installed. The easiest way is the **"Enable Precise"** button in the app's panel — it copies `statusline_bridge.py` to `~/.claude/hooks/` and adds a `statusLine` entry to `~/.claude/settings.json`, after you confirm.

To do it manually instead:

```bash
mkdir -p ~/.claude/hooks
cp statusline_bridge.py ~/.claude/hooks/statusline_bridge.py
chmod +x ~/.claude/hooks/statusline_bridge.py
```

Then open `~/.claude/settings.json` (create it if it doesn't exist) and add the `statusLine` key — see `settings_snippet.json` for reference:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 ~/.claude/hooks/statusline_bridge.py"
  }
}
```

**If `settings.json` already has other content**, only add the `statusLine` key to the existing file — don't overwrite the whole thing.

Restart Claude Code (or start a new session) and confirm the trust prompt if it appears — the status line at the bottom of the terminal should now show `model | ctx % | 5h % | 7d %`.

### Alternative: run directly from source (for development)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 claude_usage_bar.py
```

Use Claude Code for a moment (send any message) so the statusline hook writes its first cache entry — the menu bar will then show precise numbers immediately.

### Alternative: build a standalone `.app` (for sharing outside the plugin system)

```bash
source venv/bin/activate
pip install py2app
python3 setup.py py2app
open "dist/Claude Usage.app"
```

This produces a self-contained `dist/Claude Usage.app` (~38MB, bundles its own Python runtime and dependencies) — drag it to `/Applications` and open it directly, no Python/venv needed on the target machine.

⚠️ **Gatekeeper note**: this app isn't signed with an Apple Developer ID and isn't notarized. If you send the `.app` to someone over the network (not a direct same-machine copy), macOS will quarantine it and Gatekeeper will warn that it "cannot verify the developer" — the recipient needs to **right-click → Open** the first time (instead of double-clicking) to bypass this, or run `xattr -cr "Claude Usage.app"` before opening. For frictionless wide distribution you'd need an Apple Developer Program membership ($99/year) and to codesign + notarize with `xcrun notarytool`.

### Auto-launch at login (optional)

The plugin's `SessionStart` hook already auto-launches the app whenever you use Claude Code, which covers most use cases. If you also want it running even when you're not using Claude Code, add `Claude Usage.app` as a Login Item at System Settings → General → Login Items.

## Manually test the statusline hook (without opening Claude Code)

```bash
echo '{"model":{"display_name":"Claude"},"context_window":{"used_percentage":10},"rate_limits":{"five_hour":{"used_percentage":42,"resets_at":1900000000},"seven_day":{"used_percentage":18,"resets_at":1900500000}}}' \
  | python3 ~/.claude/hooks/statusline_bridge.py
cat ~/.claude-usage-bar/rate_limits.json
```

If you see JSON containing `rate_limits` in `rate_limits.json`, the hook is working correctly.

## Customize

Edit `~/.claude-usage-bar/config.json`:

```json
{
  "refresh_seconds": 15,
  "session_window_hours": 5,
  "weekly_window_days": 7,
  "session_token_ceiling": null,
  "mascot_color": "#D77757"
}
```

`mascot_color` changes the mascot/progress-bar/badge color throughout the app (both the status bar icon and the dropdown panel) — use a hex string like `"#D2794F"`.

`session_window_hours` / `weekly_window_days` / `session_token_ceiling` only take effect in "estimate mode" (the fallback). In precise mode, the app uses Claude Code's own numbers directly — nothing extra to configure.

## Ideas for extending this

- Add notifications (`NSUserNotificationCenter`/`UNUserNotificationCenter` via PyObjC) when 5h or 7d usage nears 90%
- Show a live countdown to the reset time right in the menu bar title
- Pull in `cost.total_cost_usd` / `cost.total_lines_added` / `cost.total_lines_removed` to show in the panel (already present in Claude Code's JSON, just not wired into the UI yet)
