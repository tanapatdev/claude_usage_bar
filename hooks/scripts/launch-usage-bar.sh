#!/bin/bash
# เปิด Claude Usage.app ถ้ายังไม่ได้รันอยู่ — เรียกจาก SessionStart hook ทุกครั้งที่เปิด Claude Code
set -uo pipefail

APP_PATH="$CLAUDE_PLUGIN_ROOT/dist/Claude Usage.app"

if [ ! -d "$APP_PATH" ]; then
  exit 0
fi

if ! pgrep -f "Claude Usage.app/Contents/MacOS/Claude Usage" > /dev/null 2>&1; then
  open -a "$APP_PATH" > /dev/null 2>&1 &
fi

exit 0
