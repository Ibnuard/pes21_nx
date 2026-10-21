# Referee presentation follow-up v57

The v56 device report no longer reproduced first-launch blinking. It did show
the optional visual referee running during a kickoff whistle and holding a
frozen live pose during replay. This change addresses those two presentation
issues. It does not change match decisions or establish complete FL26 AI parity.

## Kickoff and return from presentation

An acknowledged native HalfStart/KickOff warp now places the optional actor at
the requested near centre-circle/halfway intersection, `(0, 0, 9.15)` in native
metres. Its first model load arms the same placement because the initial native
warp can finish before the optional actor exists. This is the user's chosen
presentation position, not the different PC kickoff formula documented in
[the FL26 audit](REFEREE_PC_TARGET_AUDIT_V54.md).

The stance remains planted while the ball is at centre, and through the native
motion bank's measured mouth/whistle contact interval if the ball moves during
that signal. Native audio is forwarded once. A kickoff reset also consumes the
current OutOfPlay event serial; resetting that serial to zero previously
restarted an old signal at subsequent kickoffs.

Native replay, celebration and demo/skip owners hide the optional actor. It
stays allocated with the same loading and lifetime ownership, but publishes no
frozen pose into those presentations. Ordinary pause menus may retain the live
pose. Native entrance officials are not disabled by this rule.

On return to live play, the actor stays hidden until a valid ball/registry
snapshot exists. It chooses the existing live/restart destination using fresh
field and player scalars, clears elapsed movement, and publishes a full new
pose and transform before becoming visible. A bounded set of nearby positions
avoids a ball/player overlap where possible. Old cinematic transforms and
signals do not override that return. The existing native kickoff placement
takes precedence when a native warp is pending.

## FL26 AI and assistant referee scope

The existing [native animation audit](REFEREE_FL26_AUDIT_V53.md) establishes
shared PES21 skeleton/motion data, not shared executable AI. The current main
referee retains the native v54 motion bank, Mobile event/audio authority, and
the two translated FL26 live-target constraints. Trajectory selection,
acceleration, avoidance and integration remain wrapper policies.

Assistant appearances are not absent: the reported native entrance has three
officials, and the bounded Mobile symbol inventory contains `AddReferee`,
`CreateHumanReferee` and assistant-prop setters. The owned PC inventory also has
referee-flag materials and the FL26 executable has a distinct `RefereeLinesman`
class. However, the inspected Mobile `LinesmanMove::Execute`,
`LinesmanAction::Execute` and their animation-update exports are leaf stubs.
Neither those model/prop symbols nor a PC vtable supply a verified live Mobile
controller, flag animation/attachment contract, or actor lifetime policy.

No additional live assistant actors are spawned by this patch. A future port
must establish those contracts and compare the two added renderers' cost on
device. This is a controller/integration gap, not proof that assistant models
are unavailable. No PC executable code or proprietary payload is copied into
the repository.

## Verification

The focused host run passes 9 tests and 89 subtests across scene canaries,
motion rules, native hook contracts and projection. It covers repeated kickoff
warps, kickoff before the optional actor loads, a fast first pass, whistle
contact while planted, replay/demo hiding, invalid registry on return, fresh
position before display, unchanged player memory and asynchronous lifetimes.

These are host checks. On Switch, check the initial kickoff and a goal-to-
kickoff transition, replay and foul/out demos, pause/resume, halftime, rematch,
and another stadium. Confirm the point and heading against the user's image,
no frozen optional actor in replay, and a valid return without a new loading
stall. Device appearance and frame-rate acceptance remain unverified.
