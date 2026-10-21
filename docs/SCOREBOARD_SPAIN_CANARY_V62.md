# Spain scoreboard layout canary

The separate local Spain candidate now follows the human's corrected **text**
reference. It is one compact rectangle with three columns and two equal rows:
white league mark on red above a white clock cell, stacked native team
initials in a dark middle column, and stacked white score cells with a thin
divider. The prior stepped panel and top clock are superseded.

The output is a host-validated Mobile adaptation canary. Its motion is authored
in native Mobile fields; PC animation is not imported. It is not installed in
the runtime or verified by native/device playback.

## Evidence and conversion boundary

The starting evidence remains
[the v57 contract](SCOREBOARD_FL26_CONTRACT_V57.md) and its pinned local index.
This pass uses a local format-aware parser because the previously inspected
REA provider was unconfigured; its results are not REA provider evidence.
Only the previously selected owned UI members were read. No general extraction,
native game execution, full PC atlas decode, CPK/OBB repack, title build, or deployment
was performed.

The corrected reference image is pinned by SHA-256
`640d95ebd1322aa76e3c113d4f191012b2325ce26f234ae9003d96689e4c6332`.
Its 70:50:44 column proportions are authored at 1.5x as **105:75:66 pixels**,
giving a 246 x 132 panel with 66-pixel rows. The red rectangle and complete
lower-left white clock cell are part of this panel.

The owned PC `game2dSpain.bin` atlas crop `(485,1902)-(725,2028)` supplies only
the league-mark alpha mask. The red glyph is isolated from its dark background
and rendered white on the corrected red cell. The old stepped PC background
is not copied into the candidate. Only 120,960 ARGB source bytes are retained.
The LZSS reader uses a 4,096-byte history window and a 2 MiB crop budget; it
walks the required compressed prefix without allocating the 38,420,064-byte
PC texture. Distant broadcaster graphics are excluded.

The authored panel is repacked into unused Mobile atlas space at `(570,256)`.
The existing 1024 x 512 atlas and 2,097,216 decoded bytes remain unchanged in
size. Other region mappings remain identical. The old 124-pixel clock tile
is made transparent because it would exceed the new 105-pixel clock cell.
Its white background comes from the main panel instead. Native digit alpha
is retained with dark ink. Player, statistics and demo tiles are preserved.

## Native text, geometry and motion

Team text still comes from
`main.scoreGroup.teamName_home` and `main.scoreGroup.teamName_away`, the existing
native UIR team-initial bindings used by the accepted square scoreboard.
There are no hardcoded team abbreviations in the runtime candidate. The host
preview uses `RMA`/`VAL` samples only. Exact selected-team abbreviation contents
remain a native data/playback check.

Names and scores are stacked 66 pixels apart. Native kit-tinted identity
strips sit at the right edge of the name cells. Both mutually exclusive clock
states share the lower-left cell. Injury-time progression, aggregate,
additional time and cards retain their hierarchy, with the auxiliary fields
below the main panel. Digit-selection children are unchanged.

The builder checks **66 native placement updates** against separate cells,
including measured glyph spans for one-, two- and three-digit minute states.
The clock digits stay inside `(6,86)-(111,152)`; names and score bounds remain
inside their separate rows throughout the authored appearance movement.
This is a host geometry check, not observed rendering.

Existing Mobile appearance payloads provide a vertical plate unfold and
staggered score/name movement. Exit alpha uses an authored curve with the
existing frame endpoints. Script/label bytes, placement flags, source
identities, frame counts, instance hierarchy, tag lengths, and endian
descriptors are preserved. Seven other movies are byte-identical. Every
score-movie edit records its offset and old/new bytes, and the builder checks
equality everywhere outside those fields. This preserves the event contract
structurally; it does not observe event delivery or playback.

The corrected NXSB packet is **412,382 bytes**, below the unchanged
2,000,000-byte runtime limit. Its SHA-256 is
`94f58d8d2ff10c9aeb2437c5288803c857ddc1aad5fbf10c3d5421c1f3e49372`.
Its header requires the pinned original Mobile TXP: 411,822 bytes, checksum
`37cf41891957f365`. It must not be applied to another source revision.

## Reproduce and inspect locally

Use explicit owned members and a new ignored output directory:

```powershell
python tools/build_fl26_scoreboard_canary.py `
  --mobile <owned-mobile-cpk> `
  --mobile-member common/menu/licence/game2dPes.bin `
  --spain 'D:/Games/SP Football Life 2026/Data/dt11_x64.cpk' `
  --spain-member common/menu/licence/game2dSpain.bin `
  --output local-debug/scoreboard-v62/spain-canary
```

The tool pins exact Mobile and Spain input hashes and rejects other revisions.
The existing local `spain-canary` contains the corrected `.nxsb`, unpacked
candidate UI, authored panel PNG, labelled host preview, and validation report.
All proprietary outputs remain ignored. The preview uses sample host text;
it is not a game capture. The source UI members and active runtime are unchanged.

The focused suite passed **25 tests and 10 subtests**:

```powershell
python -m pytest tests/test_fl26_scoreboard_canary.py tests/test_fl26_scoreboard_contract.py tests/test_score_layout.py -q
```

Tests cover sparse LZSS bounds/history/truncation, format rejection, crop
budgets, out-of-envelope payloads, the complete rectangular design and glyph
mask, clock overflow rejection, native field invariance, region overlap
rejection, other-movie identity, and accurate unverified status. Owned-fixture
checks skip clearly if their ignored inputs are unavailable.

The actual packet also passed a compiled C admission check using the current
`source/scoreboard_runtime.inc`: `scoreboard_payload` admitted 412,350 target
TXP bytes and rejected truncated input, corrupt packet data, and a mismatched
Mobile source. The existing C runtime ownership/fallback test passed across
101 calls. `local-debug/scoreboard-v62/HOST-PARSER-PROOF.json` pins these sources
and results. Host parser admission does not prove native UI rendering.

## Remaining native proof

The candidate still requires native visual and playback checks for panel
alignment and font metrics; appearance/exit motion; 0/45/90/100+ minute clocks;
injury time; aggregate; cards; penalties; goal/replay events; and next-match
theme restoration. Frame-time and memory measurements remain device work.
England and the remaining league adaptations are separate unfinished work.
