# Visual v9 — uniform pitch, set-piece helpers, player cursor

Candidate: `local-debug/visual-v9-20260831/install/`. **Host/build validated;
Switch test pending.** Visual v8 is the user-confirmed stable baseline and is
kept intact. This candidate does not replace the scoreboard/roster OBB.

## Pitch: same width everywhere

- 20 equal bands over the playable pitch, 10 per half, instead of 6 bands over
  each padded texture. No local stretching/compression around either goal.
- Audited stock left texture: goal line x254, small-box line x331/332, midfield
  x1024. Uniform width is 77 texture pixels: the first boundary is x331.
  The penalty-area line x493/494 is near the third boundary x485, not exactly
  coincident. Equal bands cannot align every differently spaced marking at
  once; do not claim exact alignment to every box edge.
- Low_R retains v8's separate `pitch_n_bsm_alp`, complementary phase and original
  mirrored shader. Left midfield remains light, right midfield dark. No central
  correction sliver and no changes to white lines or mesh/UVs.
- Same v8 colors/grain gain. Six diffuse textures (26 mip payloads) regenerated;
  all protected native paint blocks preserved. Material headers/exports, shaders,
  specular masks and tiled detail unchanged. PAK still 27 files, 19 identical.

## Set-piece helpers

`ButtonSetplay::UpdatePreControlWindowSub` still executes natively and still
dispatches the existing Joy-Con actions. Only that window's own visual root
(`Window::GetRoot`, as used by native `SetupSwf`) Node alpha is
set to zero. `NeedDisp`, visibility, button cooldown, input and taker selector
are not disabled. Covers goal kick, throw-in, corner and free kick.

Bottom-right key badges now use navy circles/yellow symbols with white labels.
The old generic white-text batch also covered badge geometry/key glyphs and
repainted the colored pass. Badge drawing is now excluded from that batch.

## Match Settings: PLAYER CURSOR — SHOW / HIDE

Fifth row in the existing custom matchmaking settings, accessible via D-pad,
A/left/right, and physical tap. Default SHOW. Choice is stored as
`player_cursor_show 1` or `0` in `pes21_nx.cfg`; no new config needs copying.

HIDE runs the original Model::Manager::Action and then sets only the assist
draw objects invisible. It does not stop native updates, read/write gameplay
input, or retain model pointers between matches. Manager state must be 2.

The native model-path table was inspected, not guessed from UI labels:

| Slots | Models | HIDE |
| --- | --- | --- |
| 0..9 | target; input/stop/run/sliding/pass-go guide | hidden |
| 10 | offside line | unchanged |
| 11..14 | pass/cross/PK trajectory; crossing area | hidden |
| 15..16 | `d2_shoot_gauge`, `d2_shoot_base` | **unchanged** |

Screen/Flash names, overhead markers, stamina UI and other HUD are not hooked.
Power shoot gauge/base are explicitly preserved even though they are 3D models.
SHOW delegates normal visibility to the game, rather than forcing everything on.

## Remaining console-mode audit

Evidence from the owned library (SHA256 `a2793956...dcc8d187`, identical to dist):

- Only two dynamic symbols contain `MasterLeague`: database helpers
  `GetMasterLeagueDefaultTeamId` and `ListingMasterLeagueDefault`. These do not
  establish a working career/season/transfer/save loop or a launchable ML menu.
- `ModeInfo::IsCup` at 0x0680a3ac and `IsGroupLeague` at 0x0680a3bc are 8-byte
  functions returning false unconditionally. `game_mode::GetLeagueRank` at
  0x07bf0b90 returns -1. Tournament-round conversion code also exists.
- MyClub Local League menus/processes remain, but their polling code calls
  `onlinemode::CommandBase::Send`; this is not evidence of console offline Cup.

Conclusion: some common-engine/data remnants remain, but no ready-to-enable
Master League/Cup is established by this audit. A custom offline Cup wrapper
around exhibition (fixtures, bracket, results, save) is a plausible separate
project, not an implemented/unlocked mode in this package. No mode flags changed.

## Runtime and validation

Built in `runtime-release/` from `local-debug/v198-stable-player-build`, applying
only the six visual/config source-file changes. Camera, render loop, polling,
mmap/FriendPress implementation, rosters, portraits, Makefile and data unchanged.
Version basis remains 0.1.98; `DIAGNOSTICS=0 PERF_TRACE=0`. `dist/` untouched.

- 13 Python tests pass, including all equal-width bands and phase checks.
- C test with UBSan passes: SHOW/HIDE, lifecycle states, null slots, fresh match
  pointers, offside/shoot gauge preservation and config roundtrip.
- Native prologues and vtable verified including AArch64 ABS64 relocations
  (Manager::Action slot 2). Raw on-disk vtable zeros are not missing functions.
- PAK packed and independently unpacked/revalidated: headers, material payloads,
  paint blocks and phase checks pass.
- v8 PAK and OBB hashes rechecked, unchanged.

These are not Switch runtime tests. Test all four set pieces, SHOW/HIDE through
two consecutive matches, power shooting, names/HUD, midfield and both goals.

Reproduction (new output directories; all inputs must be locally owned):

```powershell
python -m pip install -r tools/visual-patch-requirements.txt -r tools/native-audit-requirements.txt
python -m unittest discover -s tests -v
python tools/build_uniform_pitch_patch.py --output local-debug/rebuild-v9/pitch
python tools/validate_visual_runtime.py --output local-debug/rebuild-v9/native-validation.json
```

For v9 itself use the complete preserved `runtime-release/` snapshot and its
`build-wsl.ps1`, without diagnostic flags. Do not reconstruct v9 from bare
`git diff`: committed features are omitted. As of 1 September the staging helper
requires explicit `--baseline` and `--delta-base` arguments for new experiments;
see [Native Pad Lab V2](local-debug/native-pad-lab-v2-20260901/README.md).
Run `tests/run_match_visual_policy.sh` in WSL for the C/UBSan test.

## Copy / rollback

See [candidate README](local-debug/visual-v9-20260831/README.md). Only NRO and PAK
are new. Keep the v8 OBB. For isolation, test the NRO with v8 pitch first, then
the v9 PAK. For rollback restore your previous NRO and the v8 PAK; no SaveData
needs deletion. The earlier NRO is also available in
`local-debug/stability-test-20260830/pes21_nx.nro` if that was the installed build.
