#!/usr/bin/env python3
"""
Generate placeholder Tauri icons using only Python stdlib.
Run from jarvis/ : python gen_icons.py

Replace later with a real source image:
  npm run tauri icon path/to/icon.png
"""

import os
import struct
import zlib

# Jarvis color — dark navy matching bg-surface (#0a0a14)
R, G, B = 10, 10, 20


def _chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def make_png(width: int, height: int) -> bytes:
    """Solid-color RGB PNG, no external deps."""
    # IHDR: 13 bytes — width(4) height(4) bitdepth(1) colortype=2/RGB(1) compress(1) filter(1) interlace(1)
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    # IDAT: filter byte 0 per row + RGB pixels
    raw = (b"\x00" + bytes([R, G, B]) * width) * height
    idat = _chunk(b"IDAT", zlib.compress(raw, 9))
    iend = _chunk(b"IEND", b"")
    return b"\x89PNG\r\n\x1a\n" + ihdr + idat + iend


def make_ico(sizes: list[int]) -> bytes:
    """ICO file embedding a PNG per size (Vista+ PNG-in-ICO format)."""
    images = [(s, make_png(s, s)) for s in sizes]

    # ICO header: reserved=0, type=1, count
    header = struct.pack("<HHH", 0, 1, len(images))

    # Directory entries (16 bytes each), then image data
    data_offset = 6 + len(images) * 16
    entries = b""
    blob = b""
    for size, png in images:
        w = 0 if size >= 256 else size   # 0 encodes 256 in ICO spec
        h = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(png), data_offset)
        data_offset += len(png)
        blob += png

    return header + entries + blob


def main():
    icons_dir = os.path.join(os.path.dirname(__file__), "src-tauri", "icons")
    os.makedirs(icons_dir, exist_ok=True)

    pngs = {
        "32x32.png":      (32,  32),
        "128x128.png":    (128, 128),
        "128x128@2x.png": (256, 256),
    }

    for filename, (w, h) in pngs.items():
        path = os.path.join(icons_dir, filename)
        with open(path, "wb") as f:
            f.write(make_png(w, h))
        print(f"  created  src-tauri/icons/{filename}  ({w}×{h})")

    ico_path = os.path.join(icons_dir, "icon.ico")
    with open(ico_path, "wb") as f:
        f.write(make_ico([16, 32, 48, 64, 128, 256]))
    print("  created  src-tauri/icons/icon.ico  (16/32/48/64/128/256)")

    print()
    print("Done. To replace with a real icon later:")
    print("  npm run tauri icon path/to/source.png")


if __name__ == "__main__":
    main()
