# FL26 scoreboard layout and animation compatibility

The current competition themes change Mobile atlas colours/emblems while
retaining its scorebar geometry and animation scripts. They are not a port of
FL26 league-specific layouts. The user has requested the latter. This follow-up
compares the actual local PC resources without replacing runtime files.

## Which files contain the scorebar

The installed `ENG1` and `SPA1` Sider folders provide general `game2d.bin` files.
Each has 18 movies, with no `game2d_score` movie. Copying either general file
would replace unrelated UI and still not supply the requested scorebar.

The owned PC `dt11_x64.cpk` contains licence `game2dEngland.bin` and
`game2dSpain.bin`, as well as `game2dPes.bin`. Those league resources contain
the score movie and different placement values. Their presence is a useful
conversion input; this static audit does not observe PC selection or playback.

| Inspected resource | Score-movie bytes | Placement records | Movie strings | Container movies |
| --- | ---: | ---: | ---: | ---: |
| Prepared Mobile `game2dPes` | 26,460 | 534 | 196 | 8 |
| PC `game2dEngland` | 40,464 | 722 | 276 | 9 |
| PC `game2dSpain` | 40,464 | 722 | 276 | 9 |

## Concrete conversion requirements

All three use the AP2 v11 signature, but that does not make their scripts or
named instances interchangeable. Mobile uses paths such as
`main.scoreGroup.time_set.time_contents.time_min_00` and
`main.scoreGroup.teamName_home`. PC uses a `window.mainGroup` hierarchy,
`time_texts_motion.time_texts.time.numbers_*`, and a `teamNameHome` wrapper
around `teamName_home`. All 18 selected Mobile instance paths are missing from
both PC trees. An equal leaf name at a different path is insufficient.

The AP2 header word at offset `0x0c` also differs (`0x23b` Mobile, `0x3b` PC).
The comparison does not infer unknown feature-bit semantics. Mobile has
`time_on/time_off` strings and PC has `scoreTime_time_show/off` strings among
their differing labels. Initial placement paths, string names and keyframe
counts are static metadata; they do not establish executed ActionScript or
equivalent event handling. Renaming only the movie/root would not validate a
layout or animation conversion.

The texture transport needs conversion too:

| Resource | Atlases | Largest atlas | Advertised decoded bytes for both atlases |
| --- | ---: | --- | ---: |
| Mobile | 1 | 1024 x 512 | 2,097,216 |
| PC England | 2 | 3200 x 2500 | 32,040,448 |
| PC Spain | 2 | 3400 x 2825 | 38,552,928 |

These byte counts come from bounded LZSS header reads, not GPU allocation
measurements. Only 64 decoded header bytes per texture were needed; no large
atlas was decoded or cooked. A texture repack would have to preserve region
links and geometry while bringing those costs within an explicit Mobile budget.

Both PC files declare a TXP2 envelope of 771,912 bytes, but their texture-table
references extend to 4,459,094 bytes for England and 4,881,567 for Spain, relative
to the TXP2 start. The existing NXSB builder copies only the declared envelope;
blind copying would truncate referenced texture data. Copying the full referenced
span would also exceed the current 2,000,000-byte runtime theme-input limit.
Raising that limit alone would not repair textures, bindings or events.

## Smallest useful follow-up

Start with one league and a separate local canary. Repack only its needed plate,
logo and clock graphics; map native Mobile score/clock/added-time/aggregate/card
instances to the intended layout. Preserve Mobile scripts and native events.
Validate the resulting geometry before adapting the corresponding entry,
exit and goal-state placement curves by semantic event, with separate checks for
injury time, three-digit minutes, penalties and the next match.

If PC event semantics cannot be mapped, distinct layouts and motion can instead
be authored in the known Mobile timeline fields. That must be labelled an
authored Mobile adaptation, not an imported FL26 animation. Recolouring the
current plate does not satisfy this layout/animation request.

No scoreboard payload, CPK, assets archive or runtime source is changed by this
audit. There is no validated league-specific FL26 scoreboard candidate yet.
The working competition palettes remain unchanged.

## Reproduction and evidence

`tools/audit_fl26_scoreboard_contract.py` accepts explicit owned UI files or a
bounded CPK member. It reports initial instance paths, placement timeline
metadata, atlas-header dimensions/costs and envelope bounds. It never gives
automatic runtime acceptance, even when the structural blockers are absent.
Reports use new output paths and contain metadata only.

The local evidence index is
`local-debug/scoreboard-v57/EVIDENCE-INDEX.json`; it pins input and report hashes.
The authoritative England/Spain reports are `ENGLAND-CONTRACT-v2.json` and
`SPAIN-CONTRACT-v2.json`. Earlier inspection files are diagnostic snapshots,
not replacement runtime inputs. Proprietary UI bytes remain ignored.

Synthetic host tests cover hierarchy mismatches despite equal leaf names,
ambiguous/recursive paths, missing score movies, a referenced texture tail
beyond a small declared envelope, bounded large-texture header inspection,
timeline metadata, and rejection without false port acceptance. No Switch
appearance, animation or frame-time result is claimed.
