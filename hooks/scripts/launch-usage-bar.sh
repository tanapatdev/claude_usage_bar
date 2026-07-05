#!/bin/bash
# ตรวจสอบว่า claude_usage_bar.py กำลังรันอยู่แล้วหรือยัง — ถ้ายัง ให้เรียก
# setup-and-launch.sh แบบ detached background ทันที (ไม่ block SessionStart hook
# แม้ว่าครั้งแรกจะต้องสร้าง venv + ติดตั้ง dependency ซึ่งใช้เวลา 20-60 วินาที)
set -uo pipefail

PLUGIN_DIR="$CLAUDE_PLUGIN_ROOT"

if pgrep -f "claude_usage_bar.py" > /dev/null 2>&1; then
  exit 0
fi

nohup bash "$PLUGIN_DIR/hooks/scripts/setup-and-launch.sh" > /tmp/claude-usage-bar-launch.log 2>&1 &
disown

exit 0
