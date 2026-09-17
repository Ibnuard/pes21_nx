"""Build the minimal AndroSwitch Project splash logo and menu preview."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "art" / "main_menu"
FONT_BOLD = ROOT / "assets" / "fonts" / "efootball" / "eFootballSans-Bold.ttf"
FONT_REGULAR = ROOT / "assets" / "fonts" / "efootball" / "eFootballSans-Regular.ttf"
SCALE = 4
WHITE = (255, 255, 255, 255)
GREEN = (117, 222, 54, 255)


def scaled(points: Iterable[tuple[float, float]]) -> list[tuple[int, int]]:
    return [(round(x * SCALE), round(y * SCALE)) for x, y in points]


def cubic(p0, p1, p2, p3, steps=48):
    points = []
    for index in range(steps + 1):
        t = index / steps
        inv = 1.0 - t
        points.append((
            inv**3 * p0[0] + 3 * inv**2 * t * p1[0] +
            3 * inv * t**2 * p2[0] + t**3 * p3[0],
            inv**3 * p0[1] + 3 * inv**2 * t * p1[1] +
            3 * inv * t**2 * p2[1] + t**3 * p3[1],
        ))
    return points


def centered_text(draw, text, font, center_x, y, fill, tracking=0):
    if tracking <= 0:
        box = draw.textbbox((0, 0), text, font=font)
        width = box[2] - box[0]
        draw.text((center_x - width / 2, y), text, font=font, fill=fill)
        return
    widths = [draw.textlength(char, font=font) for char in text]
    width = sum(widths) + tracking * (len(text) - 1)
    x = center_x - width / 2
    for char, char_width in zip(text, widths):
        draw.text((x, y), char, font=font, fill=fill)
        x += char_width + tracking


def build_logo() -> Image.Image:
    canvas = Image.new("RGBA", (1536 * SCALE, 1024 * SCALE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    stroke = 72 * SCALE

    # The A is deliberately open at the lower right so its descending stroke
    # can hand off to the S instead of reading as two unrelated initials.
    a_path = scaled(((405, 500), (575, 118), (735, 492)))
    draw.line(a_path, fill=WHITE, width=stroke, joint="curve")
    draw.line(scaled(((473, 354), (667, 354))), fill=WHITE,
              width=58 * SCALE)

    # One continuous, forward-moving S curve supplies the cross-platform/play
    # character without literal Android or Switch imagery.
    s_path = []
    s_path += cubic((1048, 156), (944, 92), (758, 105), (752, 228))
    s_path += cubic((746, 320), (1018, 290), (1042, 388), (1030, 424))[1:]
    s_path += cubic((1030, 424), (1005, 532), (818, 532), (724, 447))[1:]
    s_points = scaled(s_path)
    draw.line(s_points, fill=WHITE, width=stroke, joint="curve")
    radius = stroke // 2
    for x, y in (s_points[0], s_points[-1]):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius),
                     fill=WHITE)

    # Sole color accent: a short bridge at the exact A-to-S hand-off.
    accent = scaled(((648, 288), (681, 363)))
    accent_width = 23 * SCALE
    draw.line(accent, fill=GREEN, width=accent_width)

    bold = ImageFont.truetype(str(FONT_BOLD), 126 * SCALE)
    regular = ImageFont.truetype(str(FONT_REGULAR), 55 * SCALE)
    centered_text(draw, "ANDROSWITCH", bold, 768 * SCALE, 590 * SCALE, WHITE)
    centered_text(draw, "PROJECT", regular, 768 * SCALE, 755 * SCALE,
                  GREEN, tracking=25 * SCALE)

    return canvas.resize((1536, 1024), Image.Resampling.LANCZOS)


def main() -> None:
    ART.mkdir(parents=True, exist_ok=True)
    logo = build_logo()
    logo_path = ART / "androswitch-logo-minimal-concept.png"
    logo.save(logo_path, "PNG", optimize=True)

    background = Image.open(ART / "background-v1.png").convert("RGB")
    background = background.resize((1280, 720), Image.Resampling.LANCZOS)
    visible = logo.crop(logo.getchannel("A").getbbox())
    visible.thumbnail((470, 330), Image.Resampling.LANCZOS)
    background.paste(visible,
                     ((1280 - visible.width) // 2,
                      (720 - visible.height) // 2 - 8), visible)
    background.save(ART / "androswitch-logo-minimal-preview.png", "PNG",
                    optimize=True)
    print(logo_path)


if __name__ == "__main__":
    main()
