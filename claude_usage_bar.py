#!/usr/bin/env python3
"""
Claude Code Usage — macOS menu bar app (โหมดแม่นยำ)
======================================================
แสดง % การใช้งาน 5 ชั่วโมง / 7 วัน ของ Claude Code แบบ "ตรงกับ /usage เป๊ะ"
โดยอ่านข้อมูลจากไฟล์ cache ที่ statusline_bridge.py เขียนไว้
(ข้อมูลนี้มาจาก field rate_limits ที่ Claude Code ส่งมาจริง ๆ
ระหว่างมี session ที่ active อยู่ — เป็นตัวเดียวกับที่ /usage ใช้)

UI เป็น custom NSStatusItem + borderless panel ที่ฝัง WKWebView
(เรนเดอร์ menu_panel.html) เพื่อให้ได้หน้าตาตาม design/Claude Menu Bar.dc.html
(มาสคอตพิกเซลเคลื่อนไหว, การ์ดโค้งมน, ธีมมืด/สว่างอัตโนมัติ)

ต้องติดตั้ง statusline hook ก่อน (ดู README.md) ไม่งั้นแอปนี้จะไม่มี
ข้อมูลให้อ่าน และจะ fallback ไปเป็นค่าประมาณจาก transcript log แทน
พร้อมติดป้าย "ประมาณ" ให้ชัดเจนว่าไม่ใช่ตัวเลขทางการ

ติดตั้ง:
    pip3 install -r requirements.txt

รัน:
    python3 claude_usage_bar.py
"""

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from AppKit import (
    NSApplication,
    NSApp,
    NSStatusBar,
    NSVariableStatusItemLength,
    NSImage,
    NSColor,
    NSBezierPath,
    NSMakeRect,
    NSMakeSize,
    NSMakePoint,
    NSWindow,
    NSBackingStoreBuffered,
    NSWindowStyleMaskBorderless,
    NSWindowStyleMaskTitled,
    NSWindowStyleMaskClosable,
    NSApplicationActivationPolicyAccessory,
    NSPopUpMenuWindowLevel,
    NSEvent,
    NSFont,
    NSScreen,
    NSAlert,
    NSAlertFirstButtonReturn,
)
from Foundation import NSObject, NSTimer, NSURL
from WebKit import WKWebView, WKWebViewConfiguration, WKUserContentController

try:
    from AppKit import NSEventMaskLeftMouseDown, NSEventMaskRightMouseDown
except ImportError:  # ชื่อ constant อาจไม่ถูก export ใน pyobjc บางเวอร์ชัน
    NSEventMaskLeftMouseDown = 1 << 1
    NSEventMaskRightMouseDown = 1 << 3

# ---------------------------------------------------------------------------
# พาธไฟล์
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
PANEL_HTML_PATH = BASE_DIR / "menu_panel.html"
WIZARD_HTML_PATH = BASE_DIR / "setup_wizard.html"
HOOK_SOURCE_PATH = BASE_DIR / "statusline_bridge.py"

CLAUDE_DIR = Path.home() / ".claude"
PROJECTS_DIR = CLAUDE_DIR / "projects"
CLAUDE_HOOKS_DIR = CLAUDE_DIR / "hooks"
HOOK_DEST_PATH = CLAUDE_HOOKS_DIR / "statusline_bridge.py"
CLAUDE_SETTINGS_PATH = CLAUDE_DIR / "settings.json"
CONFIG_DIR = Path.home() / ".claude-usage-bar"
CONFIG_PATH = CONFIG_DIR / "config.json"
RATE_LIMITS_CACHE = CONFIG_DIR / "rate_limits.json"
CLAUDE_ACCOUNT_JSON = Path.home() / ".claude.json"

# ถ้า cache เก่ากว่านี้ (วินาที) จะถือว่า "อาจไม่ทันสมัย" และเตือนผู้ใช้
STALE_AFTER_SECONDS = 20 * 60  # 20 นาที

DEFAULT_CONFIG = {
    "refresh_seconds": 15,
    "session_window_hours": 5,     # ใช้เฉพาะตอน fallback เป็นโหมดประมาณ
    "weekly_window_days": 7,       # ใช้เฉพาะตอน fallback เป็นโหมดประมาณ
    "session_token_ceiling": None,
    "mascot_color": "#D77757",     # สี Claude orange ตาม design
    "mascot_name": "Pip",          # ชื่อมาสคอต ตั้งได้จาก setup wizard ตอนเปิดแอปครั้งแรก
    "onboarding_done": False,      # ผ่าน setup wizard แล้วหรือยัง
    "_max_session_seen": 0,
}

DEFAULT_TITLE_NAME = "Claude"


def get_title_label(mascot_name: str) -> str:
    """title ของแผง — ใช้ mascot_name ที่ผู้ใช้ตั้งจาก setup wizard เป็นตัวนำ
    (เช่น 'Affa' -> 'Affa Usage') ถ้ายังไม่เคยตั้ง (ยังเป็นค่า default 'Pip')
    ให้ default เป็น 'Claude Usage'"""
    name = (mascot_name or "").strip()
    if not name or name == "Pip":
        name = DEFAULT_TITLE_NAME
    return f"{name} Usage"

PANEL_WIDTH = 280
PANEL_HEIGHT = 520
WIZARD_WIDTH = 340
WIZARD_HEIGHT = 480


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config() -> dict:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_PATH.exists():
        try:
            saved = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return {**DEFAULT_CONFIG, **saved}
        except Exception:
            pass
    CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
    return dict(DEFAULT_CONFIG)


def save_config(cfg: dict) -> None:
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# อ่าน cache ที่ statusline_bridge.py เขียนไว้ (โหมดแม่นยำ)
# ---------------------------------------------------------------------------

def read_rate_limit_cache():
    """คืนค่า dict ที่ statusline_bridge.py เขียนไว้ หรือ None ถ้ายังไม่มี/อ่านไม่ได้"""
    if not RATE_LIMITS_CACHE.exists():
        return None
    try:
        return json.loads(RATE_LIMITS_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return None


def fmt_reset(epoch_seconds) -> str:
    if not epoch_seconds:
        return "—"
    try:
        dt = datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).astimezone()
    except Exception:
        return "—"
    now = datetime.now().astimezone()
    delta = dt - now
    if delta.total_seconds() <= 0:
        return "Resets now"
    hours, rem = divmod(int(delta.total_seconds()), 3600)
    minutes = rem // 60
    if hours:
        return f"Resets in {hours}h {minutes}m ({dt.strftime('%a %H:%M')})"
    return f"Resets in {minutes}m ({dt.strftime('%a %H:%M')})"


def get_plan_label():
    """ป้าย plan ที่โชว์ข้าง username — derive จาก ~/.claude.json ->
    oauthAccount.organizationType (เช่น 'claude_max' -> 'Max') บวก multiplier
    จาก organizationRateLimitTier ถ้ามี (เช่น '..._20x' -> 'Max 20x')
    ไม่ hardcode รายชื่อ tier เพราะไม่ยืนยันว่ามีค่าไหนบ้างนอกจาก claude_max"""
    try:
        data = json.loads(CLAUDE_ACCOUNT_JSON.read_text(encoding="utf-8"))
        oauth = data.get("oauthAccount") or {}
    except Exception:
        return None

    org_type = (oauth.get("organizationType") or "").strip()
    if not org_type:
        return None

    label = org_type[len("claude_"):] if org_type.startswith("claude_") else org_type
    label = label.replace("_", " ").strip().title()
    if not label:
        return None

    tier = (oauth.get("organizationRateLimitTier") or oauth.get("userRateLimitTier") or "").strip()
    match = re.search(r"(\d+x)$", tier)
    if match:
        label = f"{label} {match.group(1)}"
    return label


def fmt_tokens(n) -> str:
    if n is None:
        return "—"
    if n >= 1000:
        return f"{n / 1000:.1f}k tokens"
    return f"{n} tokens"


def install_statusline_hook():
    """คัดลอก statusline_bridge.py ไปที่ ~/.claude/hooks/ แล้วเพิ่ม key 'statusLine'
    เข้า ~/.claude/settings.json (merge แบบไม่แตะ key อื่นที่มีอยู่แล้ว)
    คืนค่า (ok: bool, message: str)"""
    try:
        CLAUDE_HOOKS_DIR.mkdir(parents=True, exist_ok=True)
        HOOK_DEST_PATH.write_text(HOOK_SOURCE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        HOOK_DEST_PATH.chmod(0o755)
    except OSError as e:
        return False, f"Could not install the hook script:\n{e}"

    try:
        if CLAUDE_SETTINGS_PATH.exists():
            settings = json.loads(CLAUDE_SETTINGS_PATH.read_text(encoding="utf-8"))
        else:
            settings = {}
    except Exception as e:
        return False, f"~/.claude/settings.json is not valid JSON — fix it manually first.\n{e}"

    settings["statusLine"] = {
        "type": "command",
        "command": "python3 ~/.claude/hooks/statusline_bridge.py",
    }
    try:
        CLAUDE_SETTINGS_PATH.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    except OSError as e:
        return False, f"Could not write ~/.claude/settings.json:\n{e}"

    return True, "Restart Claude Code (or start a new session) to activate precise tracking."


# ---------------------------------------------------------------------------
# Fallback: ประมาณจาก transcript log (ใช้เมื่อยังไม่ตั้ง statusline hook)
# ---------------------------------------------------------------------------

def iter_assistant_events():
    if not PROJECTS_DIR.exists():
        return
    for jsonl_path in PROJECTS_DIR.glob("**/*.jsonl"):
        try:
            with open(jsonl_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if rec.get("type") != "assistant":
                        continue
                    msg = rec.get("message") or {}
                    usage = msg.get("usage")
                    ts = rec.get("timestamp")
                    if not usage or not ts:
                        continue
                    try:
                        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except ValueError:
                        continue
                    yield dt, msg.get("model", "unknown"), usage
        except OSError:
            continue


def total_tokens(usage: dict) -> int:
    return (
        usage.get("input_tokens", 0)
        + usage.get("output_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0)
        + usage.get("cache_read_input_tokens", 0)
    )


def estimate_from_logs(cfg: dict):
    """คำนวณ % แบบประมาณจาก token ใน log (fallback เมื่อไม่มี cache แม่นยำ)"""
    now = datetime.now(timezone.utc)
    session_cutoff = now - timedelta(hours=cfg["session_window_hours"])
    week_cutoff = now - timedelta(days=cfg["weekly_window_days"])

    session_tokens = week_tokens = 0

    for dt, _model, usage in iter_assistant_events():
        if dt < week_cutoff:
            continue
        tok = total_tokens(usage)
        week_tokens += tok
        if dt >= session_cutoff:
            session_tokens += tok

    max_seen = cfg.get("_max_session_seen", 0)
    if session_tokens > max_seen:
        max_seen = session_tokens
        cfg["_max_session_seen"] = max_seen
        save_config(cfg)

    ceiling = cfg.get("session_token_ceiling") or max_seen or 1
    pct = min(100, round(session_tokens / ceiling * 100)) if ceiling else 0
    return {
        "session_pct": pct,
        "session_tokens": session_tokens,
        "week_tokens": week_tokens,
    }


# ---------------------------------------------------------------------------
# Pixel mascot icon สำหรับ status bar (เวอร์ชัน mini ไม่ animate ตาม design)
# ---------------------------------------------------------------------------

GRID = [
    [0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0],
    [0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0],
    [0, 0, 1, 1, 2, 1, 1, 1, 1, 1, 1, 2, 1, 1, 0, 0],
    [0, 0, 1, 1, 2, 1, 1, 1, 1, 1, 1, 2, 1, 1, 0, 0],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    [0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0],
    [0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0],
    [0, 0, 0, 3, 0, 4, 0, 0, 0, 0, 3, 0, 4, 0, 0, 0],
    [0, 0, 0, 3, 0, 4, 0, 0, 0, 0, 3, 0, 4, 0, 0, 0],
]
ROWS, COLS = len(GRID), len(GRID[0])


def hex_to_nscolor(hex_str: str) -> NSColor:
    hex_str = (hex_str or "#D77757").lstrip("#")
    r = int(hex_str[0:2], 16) / 255.0
    g = int(hex_str[2:4], 16) / 255.0
    b = int(hex_str[4:6], 16) / 255.0
    return NSColor.colorWithSRGBRed_green_blue_alpha_(r, g, b, 1.0)


def build_status_icon(mascot_color: str, cell_size: float = 1.45) -> NSImage:
    w, h = COLS * cell_size, ROWS * cell_size
    image = NSImage.alloc().initWithSize_(NSMakeSize(w, h))
    body_color = hex_to_nscolor(mascot_color)
    eye_color = NSColor.blackColor()
    image.lockFocus()
    for r, row in enumerate(GRID):
        for c, v in enumerate(row):
            if v == 0:
                continue
            x = c * cell_size
            y = (ROWS - 1 - r) * cell_size
            rect = NSMakeRect(x, y, cell_size, cell_size)
            (eye_color if v == 2 else body_color).set()
            NSBezierPath.fillRect_(rect)
    image.unlockFocus()
    image.setTemplate_(False)
    return image


# ---------------------------------------------------------------------------
# App delegate: status item + borderless webview panel
# ---------------------------------------------------------------------------

class AppDelegate(NSObject):

    def applicationDidFinishLaunching_(self, _notification):
        self.cfg = load_config()
        self.panel_open = False
        self.window = None
        self.webview = None
        self.wizard_window = None
        self.wizard_webview = None
        self._wizard_finalized = False
        self._wizard_prefill_pending = False
        self._last_data = None

        self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(
            NSVariableStatusItemLength
        )
        button = self.status_item.button()
        button.setImage_(build_status_icon(self.cfg.get("mascot_color", "#D77757")))
        button.setImagePosition_(2)  # NSImageLeft
        try:
            button.setFont_(NSFont.monospacedDigitSystemFontOfSize_weight_(13.0, 0.0))
        except Exception:
            pass
        button.setTitle_(" —%")
        button.setTarget_(self)
        button.setAction_("toggleClicked:")

        self._build_panel()

        self.global_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            NSEventMaskLeftMouseDown | NSEventMaskRightMouseDown,
            self.handleGlobalClick_,
        )

        interval = float(self.cfg.get("refresh_seconds", 15))
        self.timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            interval, self, "refresh:", None, True
        )
        self.refresh_(None)
        self.maybe_show_setup_wizard()

    def maybe_show_setup_wizard(self):
        if self.cfg.get("onboarding_done"):
            return
        self._open_wizard_window(prefill=False)

    def open_setup_wizard_for_edit(self):
        self._open_wizard_window(prefill=True)

    def _open_wizard_window(self, prefill):
        self._wizard_finalized = False
        self._wizard_prefill_pending = prefill

        rect = NSMakeRect(0, 0, WIZARD_WIDTH, WIZARD_HEIGHT)
        window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            rect,
            NSWindowStyleMaskTitled | NSWindowStyleMaskClosable,
            NSBackingStoreBuffered,
            False,
        )
        window.setTitle_("Claude Usage — Setup")
        window.center()
        window.setReleasedWhenClosed_(False)
        window.setDelegate_(self)

        config = WKWebViewConfiguration.alloc().init()
        ucc = WKUserContentController.alloc().init()
        ucc.addScriptMessageHandler_name_(self, "wizard")
        config.setUserContentController_(ucc)

        webview = WKWebView.alloc().initWithFrame_configuration_(rect, config)
        webview.setNavigationDelegate_(self)
        html_url = NSURL.fileURLWithPath_(str(WIZARD_HTML_PATH))
        base_url = NSURL.fileURLWithPath_(str(BASE_DIR))
        webview.loadFileURL_allowingReadAccessToURL_(html_url, base_url)
        window.setContentView_(webview)

        self.wizard_window = window
        self.wizard_webview = webview

        NSApp.activateIgnoringOtherApps_(True)
        window.makeKeyAndOrderFront_(None)

    def webView_didFinishNavigation_(self, webView, _navigation):
        if webView is self.wizard_webview and self._wizard_prefill_pending:
            self._wizard_prefill_pending = False
            payload = json.dumps({
                "name": self.cfg.get("mascot_name", "Pip"),
                "color": self.cfg.get("mascot_color", "#D77757"),
                "editing": True,
            })
            self.wizard_webview.evaluateJavaScript_completionHandler_(
                f"window.prefill && window.prefill({payload});", None
            )

    def finish_wizard(self, mascot_name, mascot_color):
        if mascot_name:
            self.cfg["mascot_name"] = mascot_name
        if mascot_color:
            self.cfg["mascot_color"] = mascot_color
        self.cfg["onboarding_done"] = True
        save_config(self.cfg)
        self._wizard_finalized = True

        self.status_item.button().setImage_(
            build_status_icon(self.cfg.get("mascot_color", "#D77757"))
        )
        if self.wizard_window is not None:
            self.wizard_window.close()
        self.refresh_(None)

    def cancel_wizard(self, close_window=True):
        # ปิด/ข้ามโดยไม่แก้อะไร — ค่าที่มีอยู่ก่อนหน้า (default หรือที่เคยตั้งไว้) ยังคงเดิม
        self.cfg["onboarding_done"] = True
        save_config(self.cfg)
        self._wizard_finalized = True
        if close_window and self.wizard_window is not None:
            self.wizard_window.close()

    def windowWillClose_(self, notification):
        win = notification.object()
        if win is self.wizard_window and not self._wizard_finalized:
            # หน้าต่างกำลังปิดอยู่แล้ว (เช่นกดปุ่มแดง) ไม่ต้องเรียก .close() ซ้ำ
            self.cancel_wizard(close_window=False)

    def enable_precise_tracking(self):
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Enable Precise Usage Tracking")
        alert.setInformativeText_(
            "This will copy statusline_bridge.py to ~/.claude/hooks/ and add a "
            "\"statusLine\" entry to ~/.claude/settings.json. Existing settings "
            "are preserved — only the statusLine key is added or updated."
        )
        alert.addButtonWithTitle_("Install")
        alert.addButtonWithTitle_("Cancel")
        NSApp.activateIgnoringOtherApps_(True)
        response = alert.runModal()
        if response != NSAlertFirstButtonReturn:
            return

        ok, message = install_statusline_hook()
        result_alert = NSAlert.alloc().init()
        result_alert.setMessageText_("Precise Tracking Enabled" if ok else "Installation Failed")
        result_alert.setInformativeText_(message)
        result_alert.addButtonWithTitle_("OK")
        result_alert.runModal()
        if ok:
            self.refresh_(None)

    def _build_panel(self):
        rect = NSMakeRect(0, 0, PANEL_WIDTH, PANEL_HEIGHT)
        window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            rect, NSWindowStyleMaskBorderless, NSBackingStoreBuffered, False
        )
        window.setOpaque_(False)
        window.setBackgroundColor_(NSColor.clearColor())
        window.setHasShadow_(True)
        window.setLevel_(NSPopUpMenuWindowLevel)
        window.setReleasedWhenClosed_(False)

        config = WKWebViewConfiguration.alloc().init()
        ucc = WKUserContentController.alloc().init()
        ucc.addScriptMessageHandler_name_(self, "bridge")
        config.setUserContentController_(ucc)

        webview = WKWebView.alloc().initWithFrame_configuration_(rect, config)
        try:
            webview.setValue_forKey_(False, "drawsBackground")
        except Exception:
            pass

        html_url = NSURL.fileURLWithPath_(str(PANEL_HTML_PATH))
        base_url = NSURL.fileURLWithPath_(str(BASE_DIR))
        webview.loadFileURL_allowingReadAccessToURL_(html_url, base_url)

        window.setContentView_(webview)

        self.window = window
        self.webview = webview

    # -- WKScriptMessageHandler (JS -> Python bridge) -----------------------

    def userContentController_didReceiveScriptMessage_(self, _controller, message):
        handler_name = str(message.name())

        if handler_name == "wizard":
            data = dict(message.body())
            wizard_action = str(data.get("action") or "submit")
            if wizard_action == "skip":
                self.cancel_wizard()
            else:
                mascot_name = str(data.get("name") or "").strip()
                mascot_color = str(data.get("color") or "").strip()
                self.finish_wizard(mascot_name, mascot_color)
            return

        action = str(message.body())
        if action == "quit":
            NSApp.terminate_(self)
        elif action == "refresh":
            self.refresh_(None)
        elif action == "open_config":
            os.system(f'open "{CONFIG_DIR}"')
        elif action == "setup":
            self.open_setup_wizard_for_edit()
        elif action == "enable_precise":
            self.enable_precise_tracking()

    # -- click handling -------------------------------------------------------

    def toggleClicked_(self, _sender):
        if self.panel_open:
            self.close_panel()
        else:
            self.open_panel()

    def handleGlobalClick_(self, _event):
        if self.panel_open:
            self.close_panel()

    def open_panel(self):
        button = self.status_item.button()
        button_window = button.window()
        if button_window is None:
            return
        screen_frame = button_window.frame()
        x = screen_frame.origin.x + screen_frame.size.width - PANEL_WIDTH + 8
        y = screen_frame.origin.y - PANEL_HEIGHT

        screen = NSScreen.mainScreen().frame()
        max_x = screen.origin.x + screen.size.width - PANEL_WIDTH - 4
        x = min(x, max_x)

        self.window.setFrameOrigin_(NSMakePoint(x, y))
        self.window.orderFront_(None)
        self.panel_open = True
        self.push_data_to_panel()

    def close_panel(self):
        if self.window is not None:
            self.window.orderOut_(None)
        self.panel_open = False

    # -- data / refresh ---------------------------------------------------------

    def refresh_(self, _timer):
        data = self._compute_data()
        self._last_data = data
        button = self.status_item.button()
        button.setTitle_(f" {data['_icon_pct']}%")
        if self.panel_open:
            self.push_data_to_panel()

    def push_data_to_panel(self):
        if not self._last_data or self.webview is None:
            return
        payload = json.dumps(self._last_data)
        js = f"window.renderData && window.renderData({payload});"
        self.webview.evaluateJavaScript_completionHandler_(js, None)

    def _compute_data(self):
        cache = read_rate_limit_cache()
        now_ts = time.time()
        mascot_color = self.cfg.get("mascot_color", "#D77757")
        mascot_name = self.cfg.get("mascot_name", "Pip")
        plan_label = get_plan_label()
        title_label = get_title_label(mascot_name)

        if cache and cache.get("rate_limits"):
            rl = cache["rate_limits"]
            five = rl.get("five_hour") or {}
            week = rl.get("seven_day") or {}
            captured_at = cache.get("captured_at", 0)
            age = now_ts - captured_at
            is_stale = age > STALE_AFTER_SECONDS

            five_pct = five.get("used_percentage")
            week_pct = week.get("used_percentage")
            model = cache.get("model", "Claude")
            ctx_tokens = cache.get("context_total_tokens")

            warn = "⚠️ Data may be stale — open Claude Code to refresh" if is_stale else None

            return {
                "mode": "precise",
                "stale": is_stale,
                "modelName": model,
                "planLabel": plan_label,
                "titleLabel": title_label,
                "mascotColor": mascot_color,
                "sessionPct": five_pct if five_pct is not None else 0,
                "sessionValueLabel": f"{five_pct:.0f}%" if five_pct is not None else "—",
                "sessionResetLabel": fmt_reset(five.get("resets_at")),
                "weekPct": week_pct if week_pct is not None else 0,
                "weekValueLabel": f"{week_pct:.0f}%" if week_pct is not None else "—",
                "weekResetLabel": fmt_reset(week.get("resets_at")),
                "contextLabel": fmt_tokens(ctx_tokens),
                "updatedLabel": "Updated " + datetime.fromtimestamp(captured_at).strftime("%H:%M:%S"),
                "warnLabel": warn,
                "_icon_pct": round(five_pct) if five_pct is not None else 0,
            }

        est = estimate_from_logs(self.cfg)
        return {
            "mode": "estimate",
            "stale": False,
            "modelName": "Claude",
            "planLabel": plan_label,
            "titleLabel": title_label,
            "mascotColor": mascot_color,
            "sessionPct": est["session_pct"],
            "sessionValueLabel": f"~{est['session_pct']}%",
            "sessionResetLabel": f"{est['session_tokens']:,} tokens (est.)",
            "weekPct": None,
            "weekValueLabel": "—",
            "weekResetLabel": f"{est['week_tokens']:,} tokens (est., 7d)",
            "contextLabel": "—",
            "updatedLabel": "Updated " + datetime.now().strftime("%H:%M:%S"),
            "warnLabel": "⚠️ Estimated — statusline hook not installed (see README)",
            "_icon_pct": est["session_pct"],
        }


def main():
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    app.run()


if __name__ == "__main__":
    main()
