#!/usr/bin/env python3
"""Rasterize the credited Switch button SVGs at UI-friendly resolution."""

from io import BytesIO
from pathlib import Path

import cairosvg
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "art" / "SwitchButton" / "source"
ART = ROOT / "art" / "SwitchButton"
DATA = ROOT / "data"
BUTTONS = {
    "a": "A_Button",
    "b": "B_Button",
    "x": "X_Button",
    "y": "Y_Button",
    "l": "L_Button",
    "r": "R_Button",
    "zl": "ZL_Button",
    "zr": "ZR_Button",
    "sl": "SL_Button",
    "sr": "SR_Button",
    "ls": "LeftStick_Default_CORE",
    "rs": "RightStick_Default_CORE",
    "right": "Directional_Button_Right",
    "up": "Directional_Button_Up",
    "down": "Directional_Button_Down",
    "left": "Directional_Button_Left",
}


def main() -> None:
    for key, name in BUTTONS.items():
        svg = SOURCE / f"{name}.svg"
        high_resolution = cairosvg.svg2png(
            url=str(svg), output_width=320, output_height=320
        )
        with Image.open(BytesIO(high_resolution)) as rendered:
            icon = rendered.convert("RGBA").resize(
                (80, 80), Image.Resampling.LANCZOS
            )
            icon.save(ART / f"{name}.png", optimize=True)
        png = (ART / f"{name}.png").read_bytes()
        if key in ("a", "b"):
            (DATA / f"main_menu_button_{key}.bin").write_bytes(png)
        else:
            (DATA / f"switch_button_{key}.bin").write_bytes(png)


if __name__ == "__main__":
    main()
