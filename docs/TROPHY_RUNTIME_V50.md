# Trophy runtime v50: walkout and full-time recovery

This revision addresses two failures observed in the v49 Switch test. The user
completed a Cup final and became champion, but the trophy scene never appeared.
The previously working player walkout also reverted to the stock intro.
The supplied trophy journal confirmed successful library/asset hashes and both
adapter installations. It contained no candidate creation or result snapshot.
Three native entrance starts were recorded in the accompanying scene journal.

## Integration corrections

The v49 archive preserved the stock entrance, not the installed FL26 walkout.
The combined asset tool now uses the reviewed walkout archive as its base and
adds the reviewed trophy ending. It preserves all 50 walkout payloads and all
28 trophy payloads, including each separate scene table. Existing archive IDs,
row order and stored bytes are retained; only the ending table is replaced and
27 trophy dependencies are appended. The 2,520 other walkout members remain
identical. The complete current runtime manifest is composed separately, so
older cinematic manifests cannot roll back physique or roster updates.

The normal native full-time path calls `FixDemoMatch::Create` inside
`MatchListener::MatchEndingDemo`, with the manager owned at listener offset
`0x19018`. The v49 adapter instead intercepted `FixDemoResult::Create` inside
`match::FixDemo::CreateFixDemo`. Successful installation of that hook did not
establish that a normal ending would call it. The new ending integration uses
a distinct checked caller, fresh native phase/teams/scores, live Cup-final
eligibility and native ownership. It does not broaden the old result/halftime
gate or substitute a saved champion for live match evidence. Registered
MatchInfo and RecordInfo components are read only within the active listener
invocation, retaining value snapshots instead of their pointers. On this ABI,
`ReadLock` is a pointer accessor and `ReadUnlock` is a no-op; their names alone
do not establish cross-thread synchronization.

A failed candidate is invalidated before native deletion. Restoring the original
ending preserves its scene, side, environment and Start/Skip permissions. If both
the candidate and ordinary ending cannot be created, the listener's audited
empty-owner steps 6/7 perform the normal result transition. The failure path
cancels only the existing level-1 fade through its checked native virtual method.
Normal initialization creates `ManagerMobile`; relying on the base class's
always-finished fade stub would not establish that this cleanup can complete.

The gameplay renderer and player/stadium quality policy continue to use the
accepted v48 implementation. Cinematic lifecycle evidence is separate from
gameplay pacing; neither a successful asset audit nor a native probe proves
on-device trophy playback.

## Reproduce the combined cinematic archive

Use the existing reviewed local candidates. No donor extraction, OBB copy or
prop recook is needed. These ignored fixture paths are not repository inputs.

```powershell
. D:/PESNX-Cache/use-cache.ps1
python -B tools/stage_trophy_ceremony.py `
  --walkout-report local-debug/entrance-walkout-v1-20261015/walkout-report.json `
  --trophy-report local-debug/trophy-assets-20261015-v1/trophy-report.json `
  --output local-debug/combined-cinematics-v50
```

Use a new output directory for a repeat run. The independent composition check
verifies both pinned input archives and every retained member. The generated
CPK is 34,215,936 bytes, SHA-256
`72db80088df2a1648b6c9be3576a35ee6a14e707cb8304c3c289592fe654fd27`.
This identity is also required by the runtime marker parser. A v49 marker is
rejected by the new NRO.

## Package and installation contract

The package builder requires `--entrance-policy walkout` and the combined
report above. `--upgrade-package` accepts only the exact delivered v49 five-file
identity; user-added runtime logs are ignored and remain untouched. The other
accepted states are the v48 NRO with the current native cinematic manifest, or
that same current manifest with only its cinematic row replaced by the reviewed
walkout CPK. An older walkout manifest with different unrelated rows is not an
upgrade baseline.

The installer checks the complete existing runtime before writing and backs up
the five affected paths on D. It then installs the NRO, cinematic CPK, matching
manifest, prop PAK and activation marker as a single set. Keep these files
together: replacing the NRO alone cannot restore the missing walkout assets.
The marker is written last; rollback restores the actual previous files and
their original absence. No save or OBB is included in the update.

The detached test package is
`local-debug/trophy-runtime-v50/FootballNX-Trophy-Walkout-v50-TEST`, with a
same-named ZIP next to it. Follow its `INSTALL.txt` and `Apply-Update.ps1`;
`VERIFICATION.json` records the accepted baseline and installed-file identities.
The serial `build-wsl.ps1` build succeeded with the accepted v48 runtime-pair
inputs (`e861c583ec78e9ae`) and a separate output directory. The active runtime
was not replaced by the build or packager.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| v50 NRO | 83,887,007 | `9a41ba0049e84a1e5fea8ea74b464a1bbbb1c1f68424f71fba47c993406c6148` |
| v50 test ZIP | 70,871,532 | `aec9558a62a78417c0b31b38ffe568a9698935038f68bdb581d44b5a6d4457ce` |

## Local verification

The result adapter/policy suite passed four tests, including 25 bounded native
result/ending probes and six fade cleanup cases against the compatible local
library. These cover real MatchTop dispatch, the ending factory and owner,
registered reads, winner assignment, first-cut readiness, Skip and null-owner
cleanup. The runtime validates 32 complete function fingerprints and six PLT
signatures before installing the result/ending hooks.

Prop and player/stadium-quality regressions passed 17 tests. Packaging and
cinematic-composition suites passed 91 tests, including install/rollback for all
three supported baselines and rejection of mixed or corrupt states. Prematch
reveal and feature-suspension checks passed three tests; the marker parser test
passed with explicit rejection of v49's old CPK identity. These checks do not
replace a Switch test of trophy visibility and live Cup-final timing.

The actual package passed a fresh CPK composition audit, prop-PAK integrity and
unpack checks, and linked ELF/NRO segment comparison. Independent archive
verification checked CRCs, the exact eight-member list and all five runtime-file
hashes against both the packaged proof and loose package files. Build sources,
selected inputs and the accepted v48 NRO stayed identical across the build and
packaging. The public-tree audit and whitespace check also passed.

## Device acceptance

The normal-time final test comes first because that is the path v49 missed.
Create a disposable Custom Cup with two teams, one human team and one leg.
Check the restored player walkout, win the final in normal time, then let the
trophy scene finish without Skip. Confirm the correct winner/captain, visible
cup and podium, natural return to results and normal gameplay in the next match.
Then cover Skip, a COM win and a penalty shootout; Exhibition, halftime,
semifinals and third place must retain their normal presentation.

Keep `trophy-runtime.log`, `scene-runtime.log` and a short capture from the
candidate under test. v49's startup-only journal cannot distinguish an unused
factory hook from a silent eligibility rejection. The updated journal must
identify the normal ending boundary and its candidate or rejection outcome.
Hardware acceptance remains pending until this combined revision is tested.
