#!/usr/bin/env python3
"""Generate a 1024x1024 app icon PNG from the pixel mascot art."""
from pathlib import Path

from AppKit import NSImage, NSColor, NSBezierPath, NSMakeRect, NSMakeSize, NSBitmapImageRep

GRID = [
    [0,0,1,1,1,1,1,1,1,1,1,1,1,1,0,0],
    [0,0,1,1,1,1,1,1,1,1,1,1,1,1,0,0],
    [0,0,1,1,2,1,1,1,1,1,1,2,1,1,0,0],
    [0,0,1,1,2,1,1,1,1,1,1,2,1,1,0,0],
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
    [0,0,1,1,1,1,1,1,1,1,1,1,1,1,0,0],
    [0,0,1,1,1,1,1,1,1,1,1,1,1,1,0,0],
    [0,0,0,3,0,4,0,0,0,0,3,0,4,0,0,0],
    [0,0,0,3,0,4,0,0,0,0,3,0,4,0,0,0],
]
ROWS, COLS = len(GRID), len(GRID[0])

CANVAS = 1024
PLATE_MARGIN = 90
PLATE_RADIUS = 210
BODY_COLOR = NSColor.colorWithSRGBRed_green_blue_alpha_(0xD7/255, 0x77/255, 0x57/255, 1.0)
PLATE_COLOR = NSColor.colorWithSRGBRed_green_blue_alpha_(0x20/255, 0x1E/255, 0x1B/255, 1.0)
EYE_COLOR = NSColor.colorWithSRGBRed_green_blue_alpha_(0xF5/255, 0xEE/255, 0xE8/255, 1.0)

image = NSImage.alloc().initWithSize_(NSMakeSize(CANVAS, CANVAS))
image.lockFocus()

plate_rect = NSMakeRect(PLATE_MARGIN, PLATE_MARGIN, CANVAS - 2 * PLATE_MARGIN, CANVAS - 2 * PLATE_MARGIN)
plate_path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(plate_rect, PLATE_RADIUS, PLATE_RADIUS)
PLATE_COLOR.set()
plate_path.fill()

mascot_pad_ratio = 0.16
inner = plate_rect.size.width * (1 - 2 * mascot_pad_ratio)
cell = inner / COLS
grid_w = cell * COLS
grid_h = cell * ROWS
origin_x = plate_rect.origin.x + (plate_rect.size.width - grid_w) / 2
origin_y = plate_rect.origin.y + (plate_rect.size.height - grid_h) / 2 - cell * 0.3

for r, row in enumerate(GRID):
    for c, v in enumerate(row):
        if v == 0:
            continue
        x = origin_x + c * cell
        y = origin_y + (ROWS - 1 - r) * cell
        rect = NSMakeRect(x, y, cell + 0.5, cell + 0.5)
        (EYE_COLOR if v == 2 else BODY_COLOR).set()
        NSBezierPath.fillRect_(rect)

image.unlockFocus()

tiff = image.TIFFRepresentation()
bitmap = NSBitmapImageRep.imageRepWithData_(tiff)
png_data = bitmap.representationUsingType_properties_(4, None)
out_path = Path(__file__).resolve().parent.parent / "icon_1024.png"
png_data.writeToFile_atomically_(str(out_path), True)
print("saved", out_path)
