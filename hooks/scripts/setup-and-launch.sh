#!/bin/bash
# สร้าง venv (ถ้ายังไม่มี) ติดตั้ง dependency แล้วรัน claude_usage_bar.py
# สคริปต์นี้ถูกเรียกแบบ detached จาก launch-usage-bar.sh เสมอ — ไม่ต้องรีบ
set -uo pipefail

PLUGIN_DIR="$CLAUDE_PLUGIN_ROOT"
VENV_DIR="$PLUGIN_DIR/venv"
SCRIPT_PATH="$PLUGIN_DIR/claude_usage_bar.py"

if [ ! -x "$VENV_DIR/bin/python3" ]; then
  python3 -m venv "$VENV_DIR" || exit 1
  "$VENV_DIR/bin/pip" install --quiet --upgrade pip || exit 1
  "$VENV_DIR/bin/pip" install --quiet -r "$PLUGIN_DIR/requirements.txt" || exit 1
fi

exec "$VENV_DIR/bin/python3" "$SCRIPT_PATH"
