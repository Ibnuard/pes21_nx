# v52: Cup-final result ordering

The v51 device journals identify the expected executable and confirm that the
combined cinematic assets and both canary hook groups were accepted. The user
still went from the end of a Cup final directly to match overview. The trophy
journal contains two rejected Result factory calls and no ending-factory entry
or candidate creation. Package activation is therefore established; copying
the same package again does not address the missing scene.

## Confirmed native route

Static inspection of the pinned Mobile ELF found a second caller of
`FixDemoResult::Create`: `MatchListener::MatchHalfTimeDemo`. Despite its name,
the native listener also uses this presenter for the full-time result. After
the result event, `WaitSendMatchResult` selects listener state 19, which invokes
that presenter. Its Result call is outside the invocation scope accepted by
the v51 adapter. The earlier `match::FixDemo::CreateFixDemo` boundary remains a
separate route and must not be generalized to accept arbitrary Result calls.

Result UI timing also matters. `WaitSendMatchResult` enables the result UI;
`ProcessMatchPreHalfTime::Main` consumes that signal and proceeds to the
overview. Merely substituting a trophy manager at the second factory does not
establish that the trophy will be visible before the overview. The wrapper's
own result overlay follows the native stats/menu lifecycle, so presentation
must be ordered at the native boundary rather than hidden with a render hack.

These findings come from local static inspection and controlled native
function probes. They do not establish successful playback on Switch.

## Runtime change

The additional listener adapter has its own caller and ownership checks. It
requires a current standalone Cup final, actual END phase, matching live teams,
fresh match/shootout scores and the native result request. It does not change
the existing Flow or ending-factory eligibility rules, and it does not infer
a winner from a saved champion or a result-page label.

The native result-UI process is held before it consumes the enable signal.
The listener then owns the trophy candidate and its execution. Only token
values cross into the input/UI callbacks; they never dereference saved native
manager pointers. A native completion or Skip restores the ordinary result
background before releasing the overview. Candidate failure uses the same
handoff. A missing ordinary result allocation takes the separately audited
empty-background close path, rather than borrowing the ending scene's state
numbers. Pending UI waits are bounded and failed tokens cannot rearm.

The controller bridge treats an active ceremony as the cinematic surface,
ahead of stale goal/replay heartbeats. Existing button-edge handling requests
Skip, and the listener applies it at its next owned invocation. After release,
the original native controller priorities resume. Competition score recording,
bracket updates and save ownership remain on the existing result-exit path.

Startup identifies revision v52 and the executing build ID. Bounded runtime
events distinguish the first native result-readiness state, UI hold, listener
factory rejection, mesh readiness, ceremony start/end and return to overview.
Readiness logging is limited to the first observation and first ready state
per match. The old combined rejection is split into scope, caller, request,
lifetime and final-context outcomes.

## Preserved baseline and device acceptance

The build retains the accepted player walkout and the v51 renderer,
stadium-quality and face-budget source and build inputs. The supplied scene log contains
11,925 measured frames, with a mean interval of 16,666.62 microseconds. That is
evidence for this recorded session, not a performance guarantee for another
build or every game mode.

The delivery contains the complete `switch/pes21_nx` update tree in a ready-copy
directory and matching ZIP. It retains the validated cinematic assets and
excludes saves, base game archives and old logs. No installer is required.

Hardware acceptance requires a real Cup final: allow full time to finish
without immediately skipping, observe the winning side lifting the trophy,
then confirm that match overview and the Cup result continue normally. Also
check that the prematch player walkout remains. Preserve the current scene and
trophy journals before relaunching. A successful host test or package check
does not count as hardware acceptance.

## Local verification

The final focused result, policy, controller bridge, configuration, journal,
result-menu and Cup frontend run passed 58 tests.

The actual runtime include and policy tests cover the halftime-to-END route,
current side/team/winner validation, natural completion, Skip before and after
Start, missing-factory timeout, timeout during allocation, late prop failure
and ordinary-result allocation failure. The timeout and factory atomically
claim the same waiting token, preventing overview from appearing while a
candidate is still being constructed.

The exact ELF fingerprints, eight PLT sites and result-process vtable slot are
checked against the compatible local native library. The controlled native
suite retains the previous result/ending and fade probes and adds 25 listener
lifecycle cases, including execution with null context, start permission,
completion/Skip and the distinct listener cleanup steps. A separate executable
test exercises the production controller bridge and restores the normal
goal/replay/demo priorities after the ceremony releases input.

Renderer/prop/composition regressions passed 34 tests. Controller, HUD and
prematch regressions passed 23 tests; one separate optional native HUD test
was unavailable because its ignored binary fixture was absent. Package tests
cover the pinned v51 upgrade baseline and the ready-copy ZIP. The full
repository suite and Switch rendering have not been claimed as tested.

## Generated delivery

The isolated serial build succeeded with the accepted runtime-pair inputs
(`e861c583ec78e9ae`). The executing image contains build ID
`772649f8a0c4ad39f108b54ed8dafa534ca3a5d8`, matching its ELF note, and all NRO
load segments match the linked ELF.

The ready-copy directory is
`local-debug/trophy-runtime-v52/FootballNX-v52-SIAP-COPY`; the same-named ZIP
is beside it. The canonical package with the optional installer is
`local-debug/trophy-runtime-v52/FootballNX-Trophy-Walkout-v52-TEST`.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| v52 NRO | 83,903,391 | `2e2362d34034573492e8ac81386f7562f9bab30f27f8859a75787f8797ef6372` |
| v52 SD-root ZIP | 70,870,199 | `e9c5f135f82b9ceb2b6537beb17ab746303b8d27a378323cc89a48cbcf74a9ac` |

Independent verification checked both archive member sets and CRCs, every
loose and archived runtime file, 155 build-source identities, selected inputs
and unchanged supplied device logs. The four cinematic payloads are
byte-identical to v51. The five runtime targets are the NRO, combined CPK,
paired manifest, prop PAK and canary marker. No active runtime was replaced
and the device test remains pending.

Reproduce with `build-wsl.ps1`, the accepted runtime-pair inputs and `Jobs=1`,
then `tools/build_trophy_test_package.py` using entrance policy `walkout`, the
combined v50 cinematic report, repeated v49/v50/v51 `--upgrade-package`
arguments and a fresh `--sd-copy-output` directory. Keep temporary output on D.

## Subsequent device report, 2026-10-20

The user still reports no trophy animation after winning and requests that
ceremony work be deferred while referee/commentary work proceeds. Hardware
acceptance has not passed. No new v52 journals accompanied this report, so the
exact executing package and failing lifecycle boundary have not been rechecked.
