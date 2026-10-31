"""Build the GUI header logo from the final logo image (dev-only, needs Pillow).

Takes the jester hat + brain + suit marks (not the wordmark), and turns every
inked pixel into one flat color on a transparent background. The thin white
gaps of the original drawing become transparent, so the shapes stay readable.

    python tools/make_gui_logo.py
"""

from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "LOGO" / "final_logo" / "FAE1A6B4-AC48-48E0-81B2-9BA75F4FB841.PNG"
TARGET = ROOT / "joker" / "gui" / "static" / "logo.png"
COLOR = (246, 201, 69)            # --sun in style.css
CROP = (110, 60, 1145, 840)       # icon only, above the "JOKER" wordmark
HEIGHT = 160                      # shown at 56 px; 160 keeps it sharp on hi-dpi screens


def main() -> None:
    r, g, b = Image.open(SOURCE).convert("RGB").crop(CROP).split()
    darkest = ImageChops.darker(ImageChops.darker(r, g), b)
    # ink = darkest channel well below white; the ramp gives smooth edges
    alpha = darkest.point(lambda v: max(0, min(255, (235 - v) * 255 // 90)))
    out = Image.new("RGBA", alpha.size, COLOR)
    out.putalpha(alpha)
    out = out.crop(out.getbbox())
    width = round(out.width * HEIGHT / out.height)
    out.resize((width, HEIGHT), Image.LANCZOS).save(TARGET)
    print(f"wrote {TARGET} ({width}x{HEIGHT})")


if __name__ == "__main__":
    main()
