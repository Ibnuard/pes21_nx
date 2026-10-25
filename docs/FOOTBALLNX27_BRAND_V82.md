# FootballNX27 brand and generic scoreboard

The generic FootballNX Cup and League previously used unrelated brown/gold
and green skins, with a text badge such as CUP. Both now use one authored
white/blue/red FootballNX27 family and the supplied stacked wordmark, updated
from 26 to 27. Licensed competition skins and the continental fallback remain
separate. Native competition selection still chooses the correct key.

The current brand source is `art/main_menu/brand-logo-source-v27.png`; its
generation and renderer colour policy are documented in `BRAND_V27.md` beside
it. `build_main_menu_assets.py --brand-only` updates only the linked brand PNG.
On white custom pages the letters are charcoal. On dark pages they are white.
Blue X and red wedge remain coloured. The launcher name is FootballNX 27.

`tools/build_footballnx27_scoreboard.py` requires the pinned accepted 404×48
Mobile UI. It emits the same own-brand packet for generic Cup 1000 and League
1001. Names occupy 78px white cells, scores occupy 40px blue cells, the clock
occupies 80px, and the full wordmark occupies 80px. The footprint stays 404×48.
Team colour strips use two 4×14px native tiles, inset and centred with 10px
top/bottom margins. The native backing rectangle scales with those tiles.
Native name and score fields keep their sizes, y positions and opacity fades;
their settled x positions are centred in the new cells. Native clock glyph
coverage remains exact, with 1-, 2- and 3-digit minute bounds checked.

Only exposed transform/colour fields in `game2d_score` change. The native
conditional added-time clip uses the previously verified 48×24 white plate;
the ordinary duplicate clock background is moved offscreen. Script bytes,
labels, frame counts, bindings and other movies remain exact. No PC playback
script is imported. Goal/card/substitution and aggregate logic remain native.
The aggregate anchor moves with the score pair. Runtime theme parsing retains
source/target checksums and rejects truncated or corrupted data.

The two packets replace only `scoreboards/c1000.nxsb` and
`scoreboards/c1001.nxsb` inside the current archive. Every other member is
compared byte-for-byte. Runtime packaging starts from the verified v81 set;
only NRO and FootballNX.assets change. All 1,638 heads, 436 skin corrections,
stadium fixes, adboards, weather, commentary, referee, CPKs and manifests remain
exact. The active runtime is not installed or modified.

Host checks include native packet rejection/admission, archive-reader checks,
atlas roundtrip, field bounds and fade integrity, production C menu previews,
actual overlay shader compile/link, frozen production build inputs, payload
hashes, the native 24-CPK validator and ZIP CRC/member hashes. Host preview
images are synthetic layout evidence; Switch appearance, lifecycle and FPS
are not established by those checks.
