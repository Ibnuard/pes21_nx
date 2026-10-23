# Switch button icons

The SVG files in `source/` are from **Switch Button Icons [Essential pack]
0.9**, © 2023 Gioele Casazza, licensed under [Creative Commons Attribution
4.0](https://creativecommons.org/licenses/by/4.0/). The PNG files are
project-generated 80×80 derivatives for in-game rendering.

Run `python tools/render_switch_buttons.py` to regenerate the PNGs and their
packaged `.bin` copies. This requires Pillow and CairoSVG. The icons were
previously rasterized at 32×32; the larger derivatives retain detail when
scaled in the 1280×720 UI.

`B_Button_Dark` and `X_Button_Dark` are project colour derivatives of the
same credited SVGs: navy fill and a pale glyph, with the original paths and
alpha silhouette retained. `python tools/render_switch_buttons.py --dark-only`
regenerates only those two variants without changing the white icons.
