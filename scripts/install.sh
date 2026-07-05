#!/bin/bash
# ติดตั้ง Claude Usage Bar เป็น Claude Code plugin (global scope — auto-launch
# ทุกครั้งที่เปิด Claude Code session ใหม่ ไม่ว่าจะอยู่โปรเจกต์ไหน)
#
# ใช้งาน:
#   bash scripts/install.sh                        (รันจากใน repo ที่ clone ไว้แล้ว)
#   curl -fsSL <raw-url>/scripts/install.sh | bash  (ติดตั้งตรงจาก GitHub เลย)
set -euo pipefail

REPO_URL="https://github.com/tanapatdev/claude_usage_bar.git"
MARKETPLACE_NAME="claude-usage-bar-marketplace"
PLUGIN_ID="claude-usage-bar@${MARKETPLACE_NAME}"

if [[ "$(uname)" != "Darwin" ]]; then
  echo "Claude Usage Bar is macOS-only (uses AppKit/WebKit via PyObjC)." >&2
  exit 1
fi

if ! command -v claude &> /dev/null; then
  echo "Claude Code CLI not found. Install it first: https://claude.com/claude-code" >&2
  exit 1
fi

if ! command -v python3 &> /dev/null; then
  echo "python3 not found. Install Python 3 first (e.g. brew install python3)." >&2
  exit 1
fi

echo "-> Adding marketplace ($REPO_URL)..."
claude plugin marketplace add "$REPO_URL"

echo "-> Refreshing marketplace cache..."
claude plugin marketplace update "$MARKETPLACE_NAME"

# `claude plugin install` no-ops if the plugin is already installed, and
# `claude plugin update` only refreshes when plugin.json's version field was
# bumped — neither guarantees the latest marketplace content actually lands.
# Force it: uninstall (ignore failure if not installed yet) then install fresh.
echo "-> Installing plugin ($PLUGIN_ID)..."
claude plugin uninstall "$PLUGIN_ID" &> /dev/null || true
claude plugin install "$PLUGIN_ID"

cat <<'EOF'

Installed. Restart Claude Code (exit and run `claude` again) to activate —
the menu bar app auto-launches at the start of your next session.

First launch sets up a venv and installs Python dependencies in the
background (~20-60s depending on your network), so the app may take a
moment to appear the very first time.

Manual control once installed:
  - /claude-usage-bar:run  — relaunch it anytime without a new session
  - Click "Enable Precise" in the app's panel to wire up real /usage data
    (falls back to an estimate from local transcripts until then)
EOF
