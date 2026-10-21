# FL26 referee behavior and asset audit

The 20 October 2026 request asks whether the optional referee can use FL26
PES21 behavior instead of EF10. The trophy ceremony remains a separate,
unaccepted device task. This audit changes no runtime or referee renderer.

## Observations

The current optional referee already uses a PES21 Mobile `draw::Human` and
native referee appearance, uniform loading, renderer and bone buffer. Its
positioning is authored in `source/referee_motion.h`. The game supplies match
decisions, restart context, whistle events, demo positioning and kickoff warp
events; the wrapper supplies a separate visual follower. The EF10 contribution
is an offline pose bake, not EF10 AI or executable code running on Switch.
See [v18 lifecycle and performance limits](MATCH_REVIEW_V18.md).

The locally installed FL26 Sider configuration enables `common/referee.lua`.
That module selects uniform files using competition maps and live CPK file
redirection. Its registered callbacks do not implement referee movement,
fouls, collisions or decisions. The PC gameplay implementation resides in its
native executable, not this kit module.

The owned FL26 `Data/dt13_all.cpk` and the prepared Mobile
`dt230_mobile_all.cpk` both contain 416 members. The three decoded body
skeleton/rig members and all ten decoded `body_anime_file0..9.mtar` archives
are byte-identical. The animation and render skeletons both have 20 bones.
Their SHA-256 values are respectively
`f541c0718c3346846ac8653d2d01773d723ff42113e50409be6b0e7b866c6ed2`
and `7c4279fbbc20e16df86290a18a069c8c0ada81b03ed1dd262e2a0f4cbc761c0b`.
The rig hash is
`52a57782e6be065a5a3b6ed251bdcf28f6a0068557a65d8934df5fc101574e49`.

All eight names used by the probe exist in that native bank:

| Motion | MTAR number | Frames |
|---|---:|---:|
| `referee_stand_0` | 6 | 30 |
| `walk_1_1` | 8 | 36 |
| `run_2_2` | 6 | 22 |
| `run_3_3` | 7 | 21 |
| `referee_stand_0_whistle` | 6 | 64 |
| `referee_hand_up_0` | 6 | 30 |
| `referee_1_0_000_hand_middle_point_000` | 6 | 112 |
| `referee_hand_up_0_hand_down` | 6 | 40 |

Their containers have the GANI version and frame scale expected by the
existing converter. This verifies record presence and headers, not successful
pose sampling or animation appearance.

The compatible Mobile library has SHA-256
`a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187`.
A bounded static check of its exported referee-related functions found:

- `GetRefereeFromPlayerNo` at RVA `0x7ae9880` returns a constant value of 4.
- `PitchSound::GetRefereePos` at `0x6cc08c0` returns a zero position.
- `match::anime::action::Referee::UpdateAnimeInfo` at `0x65cc8d4` copies an
  action byte into animation metadata; it calculates no position.
- The exported `LinesmanMove::Execute` and `LinesmanAction::Execute` are
  one-instruction leaves. Penalty referee-position helpers exist, but are
  set-piece position calculations rather than a live referee controller.

No callable live `RefereeAI`/think/movement controller was established by this
bounded export audit. Export absence alone does not prove that no related
internal code exists. These are ordinary static/parser observations and a
bounded offline replay of the string-hash leaf, not REA runtime Evidence or a
device execution trace. The available REA native provider remained unavailable
because Ghidra was not configured; no provider was installed for this audit.
Raw native output remains ignored and local.

## Decision and next step

Copying the full FL26 motion bank would duplicate data already present. A PC
x86-64 gameplay DLL/executable cannot be loaded as Android arm64 code by this
wrapper. Sharing PES21 ancestry does not establish binary layout or ABI
compatibility, and this audit found no verified native AI switch to enable.

The smallest practical follow-up is to bake the existing PES21 motions into
the current bounded 19-slot pose-bank format, prove decoding and visual pose
continuity, then compare the bank with the EF10 bake using the same follower,
actor and native events. This removes the newer skeleton retargeting dependency
without importing PC executable code. It does not remove the actor's native
render/GPU cost or promise a frame-rate improvement. Any later live-native-AI
integration needs its own call-site, object-lifetime and event audit.

## Reproduction

`tools/audit_fl26_referee.py` reports only sizes, hashes and format metadata.
It does not extract payloads, sample poses, modify runtime data or start a game:

```powershell
python -B tools/audit_fl26_referee.py `
  --fl26-cpk '<owned-FL26>/Data/dt13_all.cpk' `
  --mobile-cpk '<prepared-runtime>/LooseCpk/dt230_mobile_all.cpk' `
  --output local-debug/referee-fl26-audit-v53/comparison.local.json
python -B -m pytest tests/test_fl26_referee_audit.py -q
```

The synthetic tests check full 64-bit identities, duplicate motions,
truncated tables, payload bounds, declared GANI lengths and unsupported timing.
Local inputs are optional and must not be committed.
