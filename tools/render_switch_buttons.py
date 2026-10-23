#!/usr/bin/env python3
"""Rasterize the credited Switch button SVGs at UI-friendly resolution."""

from io import BytesIO
from pathlib import Path
import argparse

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


def render_dark_buttons() -> None:
    """Scoped dark derivatives: preserve the original silhouettes and alpha."""
    for key,name in (("b","B_Button"),("x","X_Button")):
        svg=(SOURCE/f"{name}.svg").read_text()
        assert '#EBEBEB' in svg and '#2D2D2D' in svg
        svg=svg.replace('#EBEBEB','#142139').replace('#2D2D2D','#F8FAFF')
        target=SOURCE/f"{name}_Dark.svg"
        target.write_text(svg)
        rendered=cairosvg.svg2png(bytestring=svg.encode(),output_width=320,output_height=320)
        with Image.open(BytesIO(rendered)) as image:
            icon=image.convert('RGBA').resize((80,80),Image.Resampling.LANCZOS)
            path=ART/f"{name}_Dark.png";icon.save(path,optimize=True)
        (DATA/f"switch_button_{key}_dark.bin").write_bytes(path.read_bytes())

def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dark-only',action='store_true',help='Generate only dark B/X; retain all existing white assets')
    args=parser.parse_args()
    if args.dark_only:
        render_dark_buttons()
        return
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
    render_dark_buttons()


if __name__ == "__main__":
    main()
