# Claude Usage Bar (โหมดแม่นยำ)

แอปเมนูบาร์ macOS ที่โชว์ % การใช้งาน Claude Code แบบ **ตรงกับคำสั่ง `/usage`
เป๊ะ** — ไม่ใช่ค่าประมาณ

แผง dropdown จะโชว์ plan ที่ใช้อยู่ด้วย (อ่านจาก `~/.claude.json` →
`oauthAccount.organizationType` + `organizationRateLimitTier` เช่น "Max 20x")

Title ของแผง default เป็น "Claude Usage" — ถ้าตั้งชื่อมาสคอตเองผ่าน setup
wizard (เช่น "Affa") title จะเปลี่ยนเป็น "Affa Usage" ให้อัตโนมัติ

UI ทั้งหมด (setup wizard + แผง dropdown) แสดงผลเป็นภาษาอังกฤษล้วน
เพื่อให้ใช้งานได้กับผู้ใช้ทั่วไปเวลาเผยแพร่ต่อ

## หลักการทำงาน

ตั้งแต่ Claude Code v2.1.80 เป็นต้นไป ทุกครั้งที่ Claude Code อัปเดต
status line ระหว่างมี session ที่ active อยู่ มันจะส่ง JSON เข้าทาง stdin
ของสคริปต์ statusline ที่คุณตั้งไว้ ซึ่ง JSON นี้มี field `rate_limits`
ติดมาด้วย:

```json
{
  "rate_limits": {
    "five_hour": { "used_percentage": 42, "resets_at": 1742651200 },
    "seven_day": { "used_percentage": 18, "resets_at": 1743120000 }
  }
}
```

ตัวเลขนี้ดึงมาจาก `anthropic-ratelimit-*` response header ของเซิร์ฟเวอร์
จริง ๆ — เป็นข้อมูลตัวเดียวกับที่คำสั่ง `/usage` ใช้แสดงผล ไม่ใช่การประมาณ

แอปนี้เลยแบ่งเป็น 3 ส่วน:

1. **`statusline_bridge.py`** — สคริปต์เล็ก ๆ ที่ Claude Code เรียกทุกครั้ง
   ที่อัปเดต status line มันจะดักข้อมูล `rate_limits` (รวมถึง token count
   ของ context window จริง ๆ) แล้วเขียนลงไฟล์ cache ที่
   `~/.claude-usage-bar/rate_limits.json` (พร้อมกับพิมพ์ status line
   ปกติกลับไปให้ terminal โชว์ต่อ ไม่ทำให้แถบสถานะหายไป)
2. **`claude_usage_bar.py`** — แอป menu bar (native, เขียนด้วย PyObjC —
   `AppKit` + `WebKit`) ที่อ่านไฟล์ cache นั้นมาโชว์แบบ real-time เป็นไอคอน
   มาสคอตพิกเซลบน status bar + แผงข้อมูลแบบ dropdown เมื่อคลิก
3. **`menu_panel.html`** — หน้าตาของแผง dropdown (มาสคอตเคลื่อนไหว,
   แถบ progress, ปุ่ม Refresh/Config/Quit) ตามดีไซน์ใน
   `design/Claude Menu Bar.dc.html` — รองรับทั้งธีมมืด/สว่างอัตโนมัติ

## ⚠️ ข้อจำกัดเดียวที่มี

ข้อมูลจะอัปเดต **เฉพาะตอนที่ Claude Code กำลังทำงานอยู่** (status line
ต้องถูกเรียกก่อนถึงจะมีข้อมูลใหม่) ถ้าคุณปิด Claude Code ไปแล้วหลายชั่วโมง
ตัวเลขในเมนูบาร์จะเป็นค่าล่าสุดที่เคยจับได้ แอปจะขึ้นเตือน
"⚠️ อาจไม่ทันสมัย" ให้เองถ้าข้อมูลเก่าเกิน 20 นาที — เปิด Claude Code
ทำงานสักครู่แล้วค่าจะรีเฟรชอัตโนมัติ

ถ้ายังไม่ได้ตั้งค่า statusline hook เลย แอปจะ fallback ไปเป็น "โหมดประมาณ"
(คำนวณจาก token ใน transcript log) และติดป้ายเตือนไว้ชัดเจนว่าไม่แม่นยำ

## ติดตั้ง

### ขั้นที่ 1 — ติดตั้ง statusline hook (ทำให้ได้ข้อมูลแม่นยำ)

```bash
mkdir -p ~/.claude/hooks
cp statusline_bridge.py ~/.claude/hooks/statusline_bridge.py
chmod +x ~/.claude/hooks/statusline_bridge.py
```

จากนั้นเปิด `~/.claude/settings.json` (ถ้ายังไม่มีไฟล์ให้สร้างใหม่) แล้ว
เพิ่ม key `statusLine` เข้าไป — ดูตัวอย่างที่ `settings_snippet.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 ~/.claude/hooks/statusline_bridge.py"
  }
}
```

**ถ้า settings.json มีค่าอื่นอยู่แล้ว** ให้เพิ่มเฉพาะ key `statusLine`
เข้าไปในไฟล์เดิม อย่าทับไฟล์ทั้งหมด

รีสตาร์ท Claude Code (หรือเปิด session ใหม่) แล้วยืนยัน trust prompt
ถ้าขึ้นมา — status line ด้านล่าง terminal จะเปลี่ยนไปโชว์
`โมเดล | ctx % | 5h % | 7d %`

### ขั้นที่ 2 — รันแอป menu bar

**แบบรันจาก source (สำหรับ dev):**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 claude_usage_bar.py
```

เปิด Claude Code ใช้งานสักครู่ (พิมพ์อะไรสักข้อความ) เพื่อให้ statusline
hook เขียน cache ครั้งแรก จากนั้นเมนูบาร์จะขึ้นตัวเลขแม่นยำทันที

**แบบ `.app` (สำหรับแจกจ่ายให้คนอื่น) — build ครั้งเดียว รันได้โดยไม่ต้องมี
Python/venv บนเครื่องปลายทาง:**

```bash
source venv/bin/activate
pip install py2app
python3 setup.py py2app
open "dist/Claude Usage.app"
```

ได้ไฟล์ `dist/Claude Usage.app` แบบ self-contained (~38MB, มี Python
runtime + dependency ครบในตัว) ลาก drag ไปที่ `/Applications` แล้วเปิดได้เลย
— ไม่ต้องตั้งค่า statusline hook เองด้วยมือแล้ว เพราะแอปมีปุ่ม
**"Enable Precise"** ในแผง (โผล่มาเฉพาะตอนยังอยู่โหมดประมาณ) ให้กดติดตั้ง
hook + แก้ `settings.json` ให้อัตโนมัติ พร้อม dialog ยืนยันก่อนทุกครั้ง

⚠️ **หมายเหตุเรื่อง Gatekeeper**: แอปนี้ยังไม่ได้ sign ด้วย Apple Developer ID
และไม่ได้ notarize ถ้าส่งไฟล์ `.app` ให้คนอื่นผ่านเน็ต (ไม่ใช่ copy ตรง ๆ ในเครื่อง
เดียวกัน) macOS จะติด quarantine flag แล้ว Gatekeeper จะเตือนว่า "ไม่สามารถ
ตรวจสอบนักพัฒนาได้" — ผู้ใช้ต้อง คลิกขวา → Open ครั้งแรก (แทนการดับเบิลคลิก)
เพื่อข้าม warning นี้ หรือรัน `xattr -cr "Claude Usage.app"` ก่อนเปิด ถ้าจะ
แจกจ่ายวงกว้างแบบไม่มี friction เลย ต้องมี Apple Developer Program
($99/ปี) แล้ว codesign + notarize ด้วย `xcrun notarytool`

### รันตอนเปิดเครื่องอัตโนมัติ (ถ้าต้องการ)

เพิ่ม `Claude Usage.app` เป็น Login Item ที่
System Settings → General → Login Items

## ทดสอบ statusline hook ด้วยมือ (ไม่ต้องเปิด Claude Code)

```bash
echo '{"model":{"display_name":"Claude"},"context_window":{"used_percentage":10},"rate_limits":{"five_hour":{"used_percentage":42,"resets_at":1900000000},"seven_day":{"used_percentage":18,"resets_at":1900500000}}}' \
  | python3 ~/.claude/hooks/statusline_bridge.py
cat ~/.claude-usage-bar/rate_limits.json
```

ถ้าเห็น JSON ที่มี `rate_limits` ใน `rate_limits.json` แปลว่า hook ทำงานถูกต้อง

## ปรับแต่ง

แก้ไฟล์ `~/.claude-usage-bar/config.json`:

```json
{
  "refresh_seconds": 15,
  "session_window_hours": 5,
  "weekly_window_days": 7,
  "session_token_ceiling": null,
  "mascot_color": "#D77757"
}
```

`mascot_color` ใช้เปลี่ยนสีมาสคอต/แถบ progress/badge ทั้งแอป (ทั้งไอคอนบน
status bar และในแผง dropdown) — ใส่เป็น hex string เช่น `"#D2794F"`

`session_window_hours` / `weekly_window_days` / `session_token_ceiling`
มีผลเฉพาะตอนอยู่ใน "โหมดประมาณ" (fallback) เท่านั้น — ตอนอยู่ในโหมดแม่นยำ
แอปใช้ตัวเลขจาก Claude Code ตรง ๆ ไม่ต้องตั้งอะไรเพิ่ม

## ต่อยอดได้

- เพิ่มการแจ้งเตือน (`NSUserNotificationCenter`/`UNUserNotificationCenter`
  ผ่าน PyObjC) เมื่อ 5h หรือ 7d ใกล้ 90%
- โชว์ countdown reset time แบบนับถอยหลังสดในตัว title menu bar เอง
- ดึง `cost.total_cost_usd` / `cost.total_lines_added` /
  `cost.total_lines_removed` มาโชว์เพิ่มในแผง (มีมาจริงใน JSON ของ
  Claude Code แล้ว แค่ยังไม่ได้ผูกเข้า UI)
