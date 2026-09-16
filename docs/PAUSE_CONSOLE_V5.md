# Pause console v5 — hardware test candidate

Not a stable checkpoint. Keep the previously verified NRO/OBB as rollback.

## Package

- NRO: `local-debug/pause-console-v5-production/pes21_nx.nro` (production, diagnostics disabled).
- OBB: `local-debug/scoreboard-square-v2/patch.305030001.jp.nyan2021.pesam.obb`.
- OBB size remains 1,401,395,200 bytes; no change to the loose runtime size contract.
- Do not replace the stable dist files until hardware validation passes.

## Changes

- Timer: move the actual clock placements 77/78 together with the widened plate. The older 14/33 IDs no longer represented the active clock.
- Pause: native team/score header retained; stats panel below it, three horizontal actions, footer helper. No additional full-screen dimming layer.
- Statistics: native RecordInfo GetMatchStats getters preserve their audited return address calculation. A throttled numeric snapshot reads native all-match possession, shots, fouls, corners, free kicks, passes, tackles and saves. No registry pointer is retained by the renderer. Before a snapshot exists, values display `--`, never fabricated zero values. Snapshot validity resets at MatchSetup.
- Game Plan: native Pause still owns opening/closing its squad child. The child is covered with the existing split custom editor, using live squad data rather than the pre-match bootstrap. Its heartbeat preserves modal input isolation; virtual pointer synthesis is disabled while custom controls are active.
- Live substitutions call CanReserved and SetMemberChangeReserved, matching the native in-match drag path. They are pending substitutions, not pre-match immediate roster swaps. Match-plan save includes the native reservation records.
- In 2P both sides mark Ready/Back before returning to Pause. In vs COM only P1 edits. Bulk Auto Line Up is visibly locked during the match because its pre-match path bypasses live substitution rules.

## Validation required on hardware

1. Timer centering at 0:00, 9:59, 10:00 and stoppage time.
2. Pause after several shots/passes: compare stats with native halftime stats. Check that header logos/score stay undimmed and only one menu exists.
3. Open custom Game Plan, change formation, back to Pause, resume, reopen. Verify persistence and no cursor/underlying gameplay input.
4. Reserve a substitute, resume through the next stoppage and verify the actual on-field change. Exhaust the native substitution limit; further changes must be rejected. Check red cards and already substituted players.
5. 2P: open Pause from either controller, independently edit both sides, Ready on each side, resume. Single-player: COM remains read-only.
6. Camera Settings, Top Menu confirmation/cancel, celebration and pause during set plays must remain stable.

The 3D hub reference is feasibility-only, not implemented here. Native player-preview actors/cameras, texture readiness and memory cost require a separate prototype.
