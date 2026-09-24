"""Generates SmartApp's Android launcher icons from the same geometry as
lib/widgets/smartapp_logo.dart (indigo rounded square, 2x2 app grid,
highlighted "match" tile with a cyan core).

Run from the project root:  python tool/generate_launcher_icon.py
Requires Pillow. Draws at 8x and downsamples for smooth edges.
"""
from pathlib import Path

from PIL import Image, ImageDraw

INDIGO = (79, 107, 255, 255)
CYAN = (34, 184, 207, 255)
WHITE = (255, 255, 255, 255)
SOFT_WHITE = (255, 255, 255, 140)

CORNER, INSET, TILE, GAP = 0.28, 0.24, 0.22, 0.08

SIZES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}


def draw(size: int) -> Image.Image:
    scale = 8
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * CORNER), fill=INDIGO)

    overlay = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    o = ImageDraw.Draw(overlay)
    a, b, t = s * INSET, s * (INSET + TILE + GAP), s * TILE
    r = int(s * 0.06)
    for x, y in ((a, a), (a, b), (b, b)):
        o.rounded_rectangle([x, y, x + t, y + t], radius=r, fill=SOFT_WHITE)
    img = Image.alpha_composite(img, overlay)

    d = ImageDraw.Draw(img)
    cx, cy = b + t / 2, a + t / 2
    rr = t * 0.62
    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=WHITE)
    rc = t * 0.24
    d.ellipse([cx - rc, cy - rc, cx + rc, cy + rc], fill=CYAN)
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    res = Path(__file__).resolve().parent.parent / "android" / "app" / "src" / "main" / "res"
    for density, size in SIZES.items():
        out = res / f"mipmap-{density}" / "ic_launcher.png"
        draw(size).save(out)
        print(f"wrote {out} ({size}px)")


if __name__ == "__main__":
    main()
