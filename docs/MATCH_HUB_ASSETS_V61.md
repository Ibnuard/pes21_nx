# Match hub, referee presentation and consolidated assets v61

The device report identified three separate issues: direct hub Kick Off needed
a prior Game Plan visit, Rematch retained an unusable substitute editor, and
the extra referee appeared in an offside VAR presentation. Commentary was
reported working and its accepted audio must be retained.

## Match preparation and editor ownership

The hub's Play branch now calls the same idempotent MatchPlan preparation used
by Game Plan before capturing/saving both squads and requesting the selected
commentary bank. An accepted audio reload resumes the frozen transaction
without preparing or saving the squads again. Failed preparation or snapshot
capture leaves the setup hub available and does not dispatch Strategy.

A fresh pre-match session clears the previous live editor's open request,
pause route, heartbeats, return state and consumed-substitute locks. The live
in-match reset retains those locks. A closing native editor cannot reacquire
live ownership while the custom pre-match hub or its bootstrap owns the UI.
This separates ordinary pre-match selection from live substitution limits.
The existing native transition-idle and TutorialMatch lifecycle remain intact;
no direct rewrite of the running match or manual Home-entry automation is used.

## Offside presentation

Ordinary offside CameraOffside is constructed by Replay::InitOffside and uses
the existing Replay lifecycle. A distinct offside-goal fixed demo precedes
recorded playback. Its native scene classifier is exactly `0x3017a`.

The added predicate borrows DemoInfo and FixDemoInfo from the current registry.
It requires active fixed-demo execution, that exact owner scene, and the same
current recorded scene. Cancellation clears the recorded scene even when the
execution bit remains stale, so both scene IDs are required. No actor pointer,
elapsed-time guess or general foul/demo owner is retained. Normal throw-ins,
fouls and set pieces keep their existing visible actor behavior.

Optional installation validates the relevant getters, classifier and pointer
layout instructions from the writable backing before executable mapping. An
unknown layout leaves recorded-replay handling available. No native code or
state is patched for this predicate. A local read-only byte oracle checked the
compatible ELF and native clear routes. REA decompiler providers were not
configured; this evidence used local ELF bytes, symbols and Capstone, without
native execution. Switch presentation still requires device verification.

## One optional asset archive

`FootballNX.assets` holds the existing 55 protected members, the approved
referee-motion replacement, its enable token, the accepted v53 player delta,
and 1,774 roster HCA files plus their catalog marker. The candidate contains
1,833 entries and no nested roster archive. Every imported payload is checked
against its pinned input and read back. The old standalone roster archive is
no longer required by this NRO.

Runtime reads only the selected archive member with bounded allocation. The
roster uses `Commentary/players-v59/`; its identity, generation, mount, cue and
bank-size policies remain unchanged. The referee token uses the same optional
asset reader as its motion. Existing explicit loose overrides retain their
normal precedence; no user asset folders are deleted during packaging.

The packer applies typed limits: Indonesia delta 1 MiB, the named accepted player
seed 8 MiB, each roster HCA 2 MiB, marker 64 bytes, motion 512 KiB and referee
token 128 bytes. The archive remains limited to 4,096 entries. A raw standalone
roster archive requires its explicit namespace when verified; this does not
broaden arbitrary archive-member admission.

## Validation

Focused tests execute the actual Play transaction, fresh-editor ownership,
snapshot rollback, roster hydration, lineup synchronization, native rematch
handoff, presentation predicates and guard failures. Commentary tests exercise
the actual runtime glue using a synthetic consolidated archive, including
startup RW/RX separation, mount ownership, fallback, cancellation and release.
Archive tests cover typed caps, corruption, merging and preserved members.

The isolated production build pins the same roster and commentary metadata as
v60. All other v60 source files and the unaffected v58 gameplay pins are checked;
the authorized changes are the hub/editor handling, presentation predicate,
archive reads and version journal. Active runtime, OBB, face PAKs, saves,
proprietary inputs and unrelated dirty work are not modified.

Device sequence: start a new Exhibition and press Kick Off directly; finish,
Rematch, swap a starter with a reserve and Kick Off; then Select Team and start
another pair. Repeat with two controllers. Check ordinary out/foul visibility,
recorded replay, an offside VAR/disallowed-goal presentation and return to play.
Check Yamal/Raphinha and names from the selected teams. Host checks and a linked
NRO do not establish a successful device rematch or 60 FPS.
