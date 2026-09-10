# Square scoreboard asset candidate

Output: `local-debug/scoreboard-square-v1/patch.305030001.jp.nyan2021.pesam.obb`

Use with `local-debug/pause-native-controls-v4-production/pes21_nx.nro`.
The OBB remains 1,401,395,200 bytes, so its runtime size contract is unchanged.
Original stable OBB and dist are not overwritten.

Changes: score cells 48x48 (previously 38x48), native score text recentered,
plate extended by 20 units, all 121 translated scoreboard keyframes lowered
20 units, team-color strips made opaque rectangles, timer glyphs regenerated
from the local eFootballSans-Bold font. Team initials remain native UIR text;
the overlay's stencil font cannot be substituted by this atlas-only patch.

The vertical offset targets the hardware screenshot's approximately 32px left
margin versus 12px top margin. Exact on-device framing still needs manual QA.
Native timing, animation durations, score bindings and non-score movies remain
unchanged. Fixed-slot patching verifies 421 other dt210 members and 23 other
OBB members byte-for-byte, including kits, rosters and faces.

Rebuild with:

```powershell
python tools/build_scoreboard_square.py --obb local-debug/eng-spa-all-kits-v3/patch.305030001.jp.nyan2021.pesam.obb --output local-debug/scoreboard-square-v1
```

The tool requires a new output directory. Validation details are in the output's
`validation.json`. Hardware acceptance: inspect ordinary time, injury time,
goal updates, accents for two kit colors, pause/resume and a second match.
