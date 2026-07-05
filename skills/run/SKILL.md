---
name: run
description: This skill should be used when the user asks to "run claude usage bar", "restart the usage bar", "relaunch claude usage", "reopen claude usage bar", "start the usage bar manually", or wants to manually launch or relaunch the Claude Usage menu bar app (for example after quitting it) without waiting for the next new Claude Code session.
allowed-tools: Bash
---

# Run Claude Usage Bar

Manually launch (or relaunch) the Claude Usage menu bar app, the same way the SessionStart hook does.

## Steps

1. Resolve the actual installed plugin directory. This is the versioned cache Claude Code installs plugins into (`~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`) — NOT the marketplace registration's `source.path` in `settings.json`, which refers to where the marketplace itself was registered from (a local directory or a git clone) and can point somewhere stale or unrelated to what's actually active.

   ```bash
   PLUGIN_ROOT=$(find "$HOME/.claude/plugins/cache/claude-usage-bar-marketplace/claude-usage-bar" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | sort -V | tail -1)
   # Fallback for a directory-sourced marketplace with no versioned cache
   if [ -z "$PLUGIN_ROOT" ]; then
     PLUGIN_ROOT=$(jq -r '.extraKnownMarketplaces["claude-usage-bar-marketplace"].source.path // empty' ~/.claude/settings.json)
   fi
   ```

2. If `$PLUGIN_ROOT` is empty, or `"$PLUGIN_ROOT/hooks/scripts/launch-usage-bar.sh"` does not exist, tell the user the plugin doesn't appear to be installed (`claude plugin install claude-usage-bar@claude-usage-bar-marketplace`) and stop.

3. Otherwise, run the plugin's own launch dispatcher directly, explicitly passing `CLAUDE_PLUGIN_ROOT` as an environment variable — the script references that exact variable name internally (it normally gets it from the hook runtime, which isn't the case here), so it must be set on the invocation itself, not just as a differently-named local variable:

   ```bash
   CLAUDE_PLUGIN_ROOT="$PLUGIN_ROOT" bash "$PLUGIN_ROOT/hooks/scripts/launch-usage-bar.sh"
   ```

   This script exits almost immediately either way: it silently no-ops if `claude_usage_bar.py` is already running (checked via `pgrep -f claude_usage_bar.py`), otherwise it dispatches the actual setup (venv creation on first run, then the app itself) as a fully detached background job.

4. Report the result in one short sentence — e.g. "Launched Claude Usage — check your menu bar" or "Already running, nothing to do." Do not claim to have visually confirmed the menu bar icon; the script's exit code only confirms the launch was dispatched, not that the app window is actually visible on screen.
