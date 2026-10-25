# Cup ceremony and custom overview ordering (v86)

The supplied v85 device journals identify the expected build and admit the
current Cup final, but never record `StartDemoEvent`. The candidate stays at
manager 3 / cut 2 with no queued or native Skip, then fails 15,030 ms after
creation and releases the ordinary overview. This is a loading failure, not
evidence that the user pressed a button. The v85 input correction remains.

The custom result APIs also did not observe the existing ceremony UI token.
A live result window could publish the custom overview, transition cover or
confirmation dialog while the native pre-result process was held. V86 makes
those queries return inactive during the same loading/playback token lifetime,
keeps the original native result update running, and drains pending result
actions without activating the result cursor or saving competition results.
Ordinary result rendering resumes after native cleanup releases the token.
Half-time and non-final matches do not acquire this ceremony token.

The previous journal suppressed changes to load masks if the manager state
stayed unchanged. V86 includes those masks in change detection and terminal
records. The current native IsReadyCut invocation reports bounded changes to
its cut number, first flag, native readiness, data state and work phase.
The complete native Exec/CreateWork fingerprints bind the two scalar offsets.
It never follows a saved cut pointer or changes a load/readiness field.
Prop creation and a terminal metadata-only wait snapshot distinguish missing
object creation, unbound UE identity, pending mesh, and timeout. No raw pointer
or model path is journaled, and repeated stable frames produce no output.

Native inspection confirms that cut loading and precreation can proceed
before Start. The supplied v85 journal does not identify the cut data stage or
registered prop identities, so it cannot establish a particular FDC/prop
failure yet. V86 fixes the custom overlay ordering and provides the missing
observations; successful trophy playback still requires device evidence.
Both component-bound prop meshes, current identity/final/winner, native FPS
restoration, deadlines and owner cleanup remain required.

No cinematic CPK, manifest, marker, prop PAK, scoreboard, stadium, weather,
commentary or real-face payload changes are required by this revision.
