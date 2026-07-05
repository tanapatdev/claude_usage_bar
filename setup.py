"""py2app build script.

Build:
    python3 setup.py py2app

Output: dist/Claude Usage.app
"""
from setuptools import setup

APP = ["claude_usage_bar.py"]
DATA_FILES = ["menu_panel.html", "setup_wizard.html", "statusline_bridge.py"]

OPTIONS = {
    "argv_emulation": False,
    "iconfile": "app_icon.icns",
    "includes": ["objc", "AppKit", "Foundation", "WebKit"],
    "plist": {
        "LSUIElement": True,
        "CFBundleName": "Claude Usage",
        "CFBundleDisplayName": "Claude Usage",
        "CFBundleIdentifier": "com.claudeusage.bar",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "NSHumanReadableCopyright": "Claude Usage",
        "NSHighResolutionCapable": True,
    },
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
