#!/usr/bin/env python3
"""
statusline_bridge.py
=====================
สคริปต์นี้ถูก Claude Code เรียกทุกครั้งที่ต้องอัปเดต status line
(ระหว่างมี session ที่ active อยู่) โดย Claude Code จะส่ง JSON
เข้ามาทาง stdin ซึ่งตั้งแต่เวอร์ชัน 2.1.80 เป็นต้นไป จะมี field
"rate_limits" ติดมาด้วย — เป็นข้อมูลตัวเดียวกับที่คำสั่ง /usage ใช้
(ดึงจาก anthropic-ratelimit-* response headers ฝั่งเซิร์ฟเวอร์จริง)

หน้าที่ของสคริปต์นี้:
  1. อ่าน JSON จาก stdin
  2. เขียน rate_limits ที่ได้ลงไฟล์ cache ที่ ~/.claude-usage-bar/rate_limits.json
     เพื่อให้ claude_usage_bar.py (แอป menu bar) เอาไปอ่านต่อ
  3. พิมพ์ status line ปกติออกไปที่ stdout (เพื่อไม่ให้แถบสถานะใน
     terminal ของ Claude Code หายไป)

ติดตั้ง: ดูขั้นตอนใน README.md
"""

import json
import sys
import time
from pathlib import Path

CACHE_DIR = Path.home() / ".claude-usage-bar"
CACHE_PATH = CACHE_DIR / "rate_limits.json"


def main() -> None:
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except Exception:
        # ไม่มี JSON ที่ใช้ได้ ก็แค่ไม่พิมพ์อะไร ปล่อยให้ status line ว่าง
        print("")
        return

    rate_limits = data.get("rate_limits") or {}
    model_name = (data.get("model") or {}).get("display_name", "Claude")
    ctx_window = data.get("context_window") or {}
    ctx_pct = ctx_window.get("used_percentage")

    ctx_total_tokens = None
    input_tok = ctx_window.get("total_input_tokens")
    output_tok = ctx_window.get("total_output_tokens")
    if input_tok is not None and output_tok is not None:
        ctx_total_tokens = input_tok + output_tok

    # -- เขียน cache ให้ menu bar app อ่าน -----------------------------------
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(
            json.dumps(
                {
                    "rate_limits": rate_limits,
                    "model": model_name,
                    "context_used_percentage": ctx_pct,
                    "context_total_tokens": ctx_total_tokens,
                    "captured_at": time.time(),
                }
            ),
            encoding="utf-8",
        )
    except OSError:
        pass

    # -- พิมพ์ status line ปกติกลับไปให้ Claude Code แสดงในเทอร์มินัล ----------
    parts = [model_name]
    if ctx_pct is not None:
        parts.append(f"ctx {ctx_pct:.0f}%")

    five = (rate_limits.get("five_hour") or {}).get("used_percentage")
    week = (rate_limits.get("seven_day") or {}).get("used_percentage")
    if five is not None:
        parts.append(f"5h {five:.0f}%")
    if week is not None:
        parts.append(f"7d {week:.0f}%")

    print(" | ".join(parts))


if __name__ == "__main__":
    main()
