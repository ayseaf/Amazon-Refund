#!/usr/bin/env python3
"""Draw the Phase 1 app icon with the standard library. No third-party image package."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

INK = (30, 44, 40, 255)
COPPER = (196, 98, 45, 255)
PAPER = (255, 253, 248, 255)


def write_png(path: Path, size: int) -> bytes:
    raw = bytearray()
    for y in range(size):
        raw.append(0)
        for x in range(size):
            raw.extend(pixel(x, y, size))
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
    path.write_bytes(png)
    return png


def chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def pixel(x: int, y: int, size: int) -> tuple[int, int, int, int]:
    center = (size - 1) / 2
    dx = x - center
    dy = y - center
    radius = size * 0.46
    if dx * dx + dy * dy > radius * radius:
        return (0, 0, 0, 0)
    bar_left = size * 0.30
    bar_right = size * 0.70
    bar_top = size * 0.42
    bar_bottom = size * 0.58
    if bar_left <= x <= bar_right and bar_top <= y <= bar_bottom:
        return PAPER
    stem_left = size * 0.46
    stem_right = size * 0.54
    stem_top = size * 0.28
    stem_bottom = size * 0.72
    if stem_left <= x <= stem_right and stem_top <= y <= stem_bottom:
        return PAPER
    return COPPER if dy < size * 0.08 else INK


def write_ico(path: Path, png: bytes, size: int) -> None:
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", size if size < 256 else 0, size if size < 256 else 0, 0, 0, 1, 32, len(png), 22)
    path.write_bytes(header + entry + png)


def main() -> None:
    destination = Path(__file__).resolve().parents[1] / "src-tauri" / "icons"
    destination.mkdir(parents=True, exist_ok=True)
    write_png(destination / "32x32.png", 32)
    write_png(destination / "128x128.png", 128)
    png_256 = write_png(destination / "128x128@2x.png", 256)
    write_ico(destination / "icon.ico", png_256, 0)


if __name__ == "__main__":
    main()
