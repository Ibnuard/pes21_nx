# Corner helper and nameplate lifecycle

The corner tactics entry now follows the inverse of the shared live nameplate
readiness gate. It is available during a valid waiting corner; when live
nameplates become eligible, both owners' tactics entries and open panels close,
queued choices are discarded, and held gameplay input is released immediately.
The user's Show Nameplate preference does not change this gameplay boundary.

`pes_controller_nameplate_ready` combines the existing native in-play heartbeat,
fresh visible scoreboard and replay, cinematic, pause, result and controller
surface exclusions. Both the stamina/nameplate snapshot and the corner bridge
use it. The corner bridge checks at HID sampling, native observation, command
consumption and overlay composition. Already emitted nameplates also suppress
the corner entry for that render frame, preventing overlap if readiness changes
mid-frame.

`corner_tactics.c` stores only the scalar readiness under its existing mutex.
Either readiness edge clears pending/open/release state and prior availability.
Returning to a hidden nameplate requires a new native corner publication; a
stale pre-kick heartbeat cannot reopen the selector. Repeated identical reads by
the two controllers do not clear legitimate pending choices. Native corner
ownership, animation/context validation, option mapping, lifecycle calls and
bounded ABI checks are retained.

Static inspection of the compatible owned ELF corroborated the existing
`Utility::Info::IsInplayTime` call boundary. No new guessed native offset or
animation value was introduced. REA reported unavailable local deep providers;
the bounded inspection used local ELF/Capstone, not a REA execution result.
Temporary raw inspection output was removed after documenting the findings.

Host checks execute the production state machine, HID and native adapters,
including a kick beginning between selection and consumption, both controllers,
full controllers and horizontal Joy-Cons, immediate input release, fresh-only
re-entry and repeated readiness publications. Shared-gate tests compile the
production readiness functions with controlled heartbeat/scoreboard clocks and
every surface blocker. The focused corner, native leaf, pre-finalize installer,
set-play helper and HUD suite passed 85 tests; one optional legacy native-binary
fixture was unavailable. `git diff --check` passed for the changed corner/HUD
tests and sources. Switch timing and visible kick transitions still require
device confirmation.
