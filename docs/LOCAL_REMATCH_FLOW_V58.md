# Local Rematch native transition admission v58

The supplied v57 device journal reaches `native frontend ready` and `new match
bootstrap dispatched`, but never records the next TutorialMatch initialization.
The existing frontend receipt therefore does not establish native transition
admission. Ordinary Exhibition startup and Top to Menu remain user-accepted.

The compatible Mobile ELF establishes a concrete lifecycle hazard:

- `FlowTransition::DirectSet` constructs transition data and calls `AddFlow`.
  It returns void and queues work; calling it does not prove entry to a new
  TutorialMatch object.
- `FlowTransition::Main` tracks its step at offset 8 and its transition vector
  at offsets `0x40` and `0x48`. Step 0 is the native `MAIN_STEP_NEXT_FLOW`.
- During fade completion, Main destroys all current vector entries and resets
  its end pointer before entering its fade-in wait. An entry appended before
  that cleanup can disappear with the preceding transition. SetupWindow can
  already have completed while that owner is still active.

The wrapper now retains the local request until the actual current listener's
transition is at step 0 **and** its vector is empty. It only reads these fields;
it never writes a step, clears a native queue, uses a fixed delay, or retries a
dispatched transition. Installation checks the exact native step read, vector
read and completion-clear instructions before relying on these offsets.
If the compatibility guard differs, only the new automatic result actions are
disabled with a journal note; ordinary manual Exhibition startup remains
unchanged. The result menu cannot offer those actions without this guard.
Unavailable listeners, a nonempty queue or any other step leave the request
pending. A single bounded journal note identifies that wait. Dispatch still
happens once, followed by the existing TutorialMatch data initializer and
identity-checked Game Plan restoration.

This retains the automatic native teardown and subsequent match creation.
It does not ask the user to manually enter Home, and it is not an in-place
reset of a running match. The bounded Mobile menu symbol inventory did not
establish a native Exhibition Rematch entry. The native `Retry` routines found
in match/debug and step-up tutorial contexts do not establish a safe substitute
for the complete Exhibition lifecycle; the wrapper does not call them.

The optional owned-ELF oracle decodes the actual completion block and replays
its destructor-loop stride and end-pointer write: a second queued entry is
destroyed with the previous one. The actual-source host harness retains a
request through every native step
1–6, models the preceding fade's whole-vector discard, waits for step 0 with an
empty vector, and dispatches once. It also checks an unavailable listener or
binding, queued-data states, both controller modes, failed bootstrap admission,
and repeated matches. All native transition reads remain unmodified.

The native queue hazard is statically established. The device log does not
record native step/queue contents and cannot uniquely prove which internal
condition stalled v57. V58 still needs the complete on-device sequence:
finish Exhibition → Rematch → finish again → Select Team → start a new match.
The new bounded wait note separates waiting for native ownership from actual
bootstrap dispatch and initialization. No successful Switch rematch is claimed
from the host harness alone.

REA native decompiler providers were unavailable in this session. The focused
native inspection used the exact local compatible ELF, its symbols, segment
mapping and Capstone; proprietary disassembly and the local inspection receipt
remain ignored under `local-debug/match-followup-v58/`.
