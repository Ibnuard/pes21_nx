# Cup ceremony input rearming, v85

The supplied v84 trophy and scene journals identify executing build
`f32148833407c74ae4b24866c416d60825331921`. They show successful final-result
admission and a real cut object being loaded, with native suppression zero.
At 1,883 ms after construction, the wrapper publishes `requested=1` while the
manager is still at cut state 2, start permission zero, and `started=0`.
The listener applies native Skip and the manager terminates. The journal's
`reason=skip` establishes a wrapper-queued cancellation during loading.
It does not identify which physical HID bit caused that request. The user
previously reported leaving the controller untouched.

The production cinematic helper accepted every rising bit in the HID button
word. That word also includes synthesized stick directions/status. The input
context transition clears previous samples, so a held bit can become a new
edge on the next poll. The old path also accepted queued requests as soon as
the result UI was held, before candidate construction or StartDemoEvent.
These are source-confirmed admission defects; the exact physical device bit
remains unknown.

The Cup adapter now consumes loading-time requests without queuing or
forwarding them to another native demo owner. A token-only playing state is
published after the checked native StartDemoEvent returns. No borrowed manager
or renderer pointer is accessed by input. During Cup playback the HID helper
requires a neutral sample after that transition, then a fresh logical A/B/X/Y
or Plus edge. Stick-direction, status and shoulder bits cannot skip the Cup
ceremony. A held button, profile/context generation change or reconnect must
pass the release gate. Both controller samples already feed the helper in
logical profile order, including horizontal Joy-Con button aliases.

Ordinary native cinematics retain their existing input path. Cup final/END,
team and winner checks, both prop readiness gates, load timeout, derived
destruction, native FPS restoration and overview ownership remain intact.
Intentional Cup Skip is available once the scene has started and controls have
been released; pressing while loading no longer cancels it. No native load,
suppression, scene-state or readiness field is forced.

Regression coverage runs the actual production HID helper and actual C Cup
adapter. The previous helper fails the loading/noise fixture. The corrected
helper covers loading, held input, ignored bits, neutral release, fresh face
and Plus edges, generation changes, an observed disconnect/reconnect and
ordinary cinematic input.
The adapter fixture reproduces the recorded cut-state/loading/request timing,
keeps the candidate alive, then exercises readiness, Start and deliberate Skip
through native-owner cleanup and overview. Host checks establish this input
correction, not trophy rendering or device performance.

The focused trophy/input suite passes 72 tests. A broader legacy gamepad/UI
suite also encounters eight source-text expectation failures. All eight were
reproduced against checkpoint `aeb2b5138a505f47d3557cf2da584c22714cf258`;
their old UI expectations are outside this correction. The separate optional
native execution probe is not run; the pinned native ABI/static checks are run.

Packaging changes only the NRO from the verified v84 baseline. All thirteen
other runtime files remain exact, including the v83 added-time scoreboard,
1,638 heads, 436 body-selector corrections, cinematic CPK/manifest/marker and
prop PAK. The recorded premature Skip is corrected at the input boundary;
successful lifting, camera/props and eventual overview still require a Switch
test. Retain both runtime journals before relaunching if another loading
failure appears.
