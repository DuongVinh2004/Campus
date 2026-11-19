"""Draw the app icons (a white "C" on a blue rounded square) as PNG files with the standard library only.

  python scripts/make_pwa_icons.py [--out apps/web/public/icons]

The icon is the product's own mark, not the university's logo: Campus 24/7 is not an official school service. The maskable icon keeps the
mark inside the central 80 % so a phone can crop it to any shape. The result is deterministic, so running it twice gives the same bytes.
"""
from __future__ import annotations

import argparse
import math
import struct
import zlib
from pathlib import Path

BLUE = (29, 78, 216, 255)
WHITE = (255, 255, 255, 255)
SAMPLES = 3  # per axis, for smooth edges


def png(width: int, height: int, rows: list[bytes]) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + row for row in rows)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def inside_icon(x: float, y: float, size: int, *, scale: float, rounded: bool) -> tuple[int, int, int, int]:
    """The colour of the point (x, y) in a size x size icon. `scale` shrinks the mark; `rounded` rounds the square's corners."""
    centre, radius = size / 2, size * 0.5
    if rounded:
        corner = size * 0.22
        dx, dy = max(abs(x - centre) - (radius - corner), 0), max(abs(y - centre) - (radius - corner), 0)
        if math.hypot(dx, dy) > corner:
            return (0, 0, 0, 0)
    # The "C": a ring of outer radius R and inner radius 0.62 R, open towards the right (the gap spans +-38 degrees).
    ring_outer, ring_inner = size * 0.30 * scale, size * 0.30 * scale * 0.62
    dist = math.hypot(x - centre, y - centre)
    angle = math.degrees(math.atan2(-(y - centre), x - centre))
    if ring_inner <= dist <= ring_outer and abs(angle) > 38:
        return WHITE
    # Rounded ends of the ring so the gap does not look cut.
    middle = (ring_outer + ring_inner) / 2
    thickness = (ring_outer - ring_inner) / 2
    for end in (38, -38):
        ex, ey = centre + middle * math.cos(math.radians(end)), centre - middle * math.sin(math.radians(end))
        if math.hypot(x - ex, y - ey) <= thickness:
            return WHITE
    return BLUE


def render(size: int, *, scale: float = 1.0, rounded: bool = True) -> bytes:
    rows = []
    step = 1 / SAMPLES
    for py in range(size):
        row = bytearray()
        for px in range(size):
            total = [0, 0, 0, 0]
            for sy in range(SAMPLES):
                for sx in range(SAMPLES):
                    r, g, b, a = inside_icon(px + (sx + 0.5) * step, py + (sy + 0.5) * step, size, scale=scale, rounded=rounded)
                    total[0] += r * a
                    total[1] += g * a
                    total[2] += b * a
                    total[3] += a
            alpha = total[3] / (SAMPLES * SAMPLES)
            if total[3] == 0:
                row += bytes((0, 0, 0, 0))
            else:
                row += bytes((round(total[0] / total[3]), round(total[1] / total[3]), round(total[2] / total[3]), round(alpha)))
        rows.append(bytes(row))
    return png(size, size, rows)


ICONS = {"icon-192.png": (192, 1.0, True), "icon-512.png": (512, 1.0, True), "icon-maskable-512.png": (512, 0.8, False)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "apps/web/public/icons")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for name, (size, scale, rounded) in ICONS.items():
        (args.out / name).write_bytes(render(size, scale=scale, rounded=rounded))
        print("wrote", args.out / name)


if __name__ == "__main__":
    main()
