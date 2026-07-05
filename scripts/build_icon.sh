#!/bin/bash
# สร้าง app_icon.icns จาก icon_1024.png (ต้องมี icon_1024.png อยู่แล้ว —
# รัน scripts/generate_icon.py ก่อนถ้ายังไม่มี)
set -euo pipefail
cd "$(dirname "$0")/.."

ICONSET=icon.iconset
rm -rf "$ICONSET"
mkdir -p "$ICONSET"

sips -z 16 16     icon_1024.png --out "$ICONSET/icon_16x16.png" > /dev/null
sips -z 32 32     icon_1024.png --out "$ICONSET/icon_16x16@2x.png" > /dev/null
sips -z 32 32     icon_1024.png --out "$ICONSET/icon_32x32.png" > /dev/null
sips -z 64 64     icon_1024.png --out "$ICONSET/icon_32x32@2x.png" > /dev/null
sips -z 128 128   icon_1024.png --out "$ICONSET/icon_128x128.png" > /dev/null
sips -z 256 256   icon_1024.png --out "$ICONSET/icon_128x128@2x.png" > /dev/null
sips -z 256 256   icon_1024.png --out "$ICONSET/icon_256x256.png" > /dev/null
sips -z 512 512   icon_1024.png --out "$ICONSET/icon_256x256@2x.png" > /dev/null
sips -z 512 512   icon_1024.png --out "$ICONSET/icon_512x512.png" > /dev/null
cp icon_1024.png "$ICONSET/icon_512x512@2x.png"

iconutil -c icns "$ICONSET" -o app_icon.icns
rm -rf "$ICONSET"
echo "built app_icon.icns"
