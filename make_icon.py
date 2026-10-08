"""
make_icon.py
------------
Generate the Automata Tutor app icon with Pillow — no SVG toolchain needed.

Design (v2): a bold accepting double-ring state wrapping a monogram "A" that
doubles as a state node, with a start arrow entering from the left and a
transition arrowhead on the outer ring. Drawn on a purple-to-dark rounded
square. We render at 4x and downsample for crisp anti-aliasing, then emit:

    icon.png   — 256x256 (used for the Tk window icon on all platforms)
    icon.ico   — multi-size Windows icon (used by PyInstaller for the .exe)

Run:  python make_icon.py
Requires: Pillow  (pip install pillow)
"""

from __future__ import annotations

import math

from PIL import Image, ImageDraw

# --- palette ---
BG_TOP = (58, 47, 92)       # #3a2f5c  (purple)
BG_BOT = (30, 31, 41)       # #1e1f29  (near-black)
RING_A = (196, 167, 231)    # #c4a7e7  (accent purple)
RING_B = (156, 207, 216)    # #9ccfd8  (start cyan)
ACCEPT = (166, 227, 161)    # #a6e3a1  (green inner ring)
GLYPH = (224, 222, 244)     # #e0def4  (near-white)
START = (156, 207, 216)     # #9ccfd8

SIZE = 256
SS = 4                      # supersampling factor
S = SIZE * SS


def _lerp(a, b, t):
    return (int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


def _diag_gradient(c0, c1) -> Image.Image:
    """Top-left -> bottom-right linear gradient."""
    g = Image.new("RGB", (S, S), c0)
    px = g.load()
    for y in range(S):
        for x in range(S):
            t = (x + y) / (2 * S)
            px[x, y] = _lerp(c0, c1, t)
    return g


def _ring_gradient(c0, c1) -> Image.Image:
    """Diagonal gradient used to color the outer accepting ring."""
    g = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    px = g.load()
    for y in range(S):
        for x in range(S):
            t = (x + y) / (2 * S)
            r, gg, b = _lerp(c0, c1, t)
            px[x, y] = (r, gg, b, 255)
    return g


def _arrowhead(d, tip, ang, size, fill):
    tx, ty = tip
    left = (tx - size * math.cos(ang - 0.5), ty - size * math.sin(ang - 0.5))
    right = (tx - size * math.cos(ang + 0.5), ty - size * math.sin(ang + 0.5))
    d.polygon([tip, left, right], fill=fill)


def build() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    # Rounded-rect background with a diagonal purple->dark gradient.
    radius = int((56 / 256) * S)
    grad = _diag_gradient(BG_TOP, BG_BOT).convert("RGBA")
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1],
                                           radius=radius, fill=255)
    img.paste(grad, (0, 0), mask)

    d = ImageDraw.Draw(img)

    def sc(v: float) -> float:
        return v * SS

    cx, cy = sc(128), sc(128)

    # --- outer accepting ring, filled from a diagonal gradient via a mask ---
    outer_r = sc(78)
    ring_w = sc(10)
    ring_mask = Image.new("L", (S, S), 0)
    md = ImageDraw.Draw(ring_mask)
    md.ellipse([cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r],
               outline=255, width=int(ring_w))
    img.paste(_ring_gradient(RING_A, RING_B), (0, 0), ring_mask)
    d = ImageDraw.Draw(img)  # refresh draw handle after paste

    # --- inner green ring (the "accepting" double-ring) ---
    inner_r = sc(63)
    d.ellipse([cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r],
              outline=ACCEPT, width=int(sc(6)))

    # --- monogram "A" as a bold state glyph ---
    lw = int(sc(15))
    d.line([sc(103), sc(162), sc(128), sc(92), sc(153), sc(162)],
           fill=GLYPH, width=lw, joint="curve")
    # round the apex/feet
    for (x, y) in [(sc(103), sc(162)), (sc(128), sc(92)), (sc(153), sc(162))]:
        rr = lw / 2
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=GLYPH)
    d.line([sc(113), sc(138), sc(143), sc(138)], fill=GLYPH, width=lw)

    # --- incoming start arrow (left) ---
    d.line([sc(20), sc(128), sc(44), sc(128)], fill=START, width=int(sc(10)))
    _arrowhead(d, (sc(64), sc(128)), 0.0, sc(20), START)

    # --- transition arrowhead riding the outer ring (upper right) ---
    _arrowhead(d, (sc(210), sc(74)), math.radians(55), sc(20), RING_A)

    return img.resize((SIZE, SIZE), Image.LANCZOS)


def main() -> None:
    icon = build()
    icon.save("icon.png")
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128),
             (256, 256)]
    icon.save("icon.ico", sizes=sizes)
    print("Wrote icon.png (256x256) and icon.ico (multi-size).")


if __name__ == "__main__":
    main()
