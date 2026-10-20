# v51: copy-ready package and fresh boot evidence

The device test restored the player walkout in v50; that is accepted evidence
that the walkout assets were in use. Winning the Cup final still did not show
the trophy scene. The user copied the complete update manually. Do not infer
that v49 was running, or that a file was omitted, from the trophy journal alone.

The supplied v50 trophy journal is byte-identical to v49's startup-only journal
(243 bytes), while the scene journal contains the new v50 entrance message.
Two reporting defects prevent this from establishing the trophy activation
state: a missing or unreadable marker returned before resetting the old trophy
journal, and the stadium installer reset the scene journal after the package
status had been written. These are reporting defects, not proof of the reason
the trophy was absent on the device.

## Runtime changes

The scene journal now begins once, before package checks. Trophy startup rotates
one bounded prior journal before reading the marker and records the executing
build ID and boot tick in both journals. Marker I/O, full-loose mode, file I/O,
hash mismatches and final ABI activation have distinct outcomes. Failure to
create a new trophy journal never appends to the old one. It is reported in the
scene journal and does not silently disable an otherwise valid canary.
The final-only eligibility and native ending adapter remain as in v50.

A separate actual-source replay reproduced a renderer cache defect:
`glProgramBinary` and its OES alias bypassed the wrapper's program-generation
invalidation. Loading a shader binary can reset uniform values and replace
locations. The wrapper could therefore skip restoring unchanged `nx*` values
or later write an obsolete location. Both dynamic procedure routes now publish
invalidation after the driver call, including conservative invalidation after
a rejected call. They preserve arguments, unsupported lookups and pending
driver errors without status queries, waits or forced flushes.

This repairs a demonstrated wrapper-uniform defect. Its connection to the
reported first-launch real-face hair spikes, disappearance or blinking is still
unproven. Native bone uniform calls remain direct. No face recook, triangle-cap
change, stadium-quality downgrade or allocator change is included.

## Delivery and test

The primary delivery is a folder containing `switch/pes21_nx` with all five
verified update files. Copy its `switch` directory into the SD root and replace
matching files, then launch `sdmc:/switch/pes21_nx/pes21_nx.nro`. It contains no
save, OBB, previous device logs or complete runtime archive. The existing game
installation remains required. No installer script is required.

The canonical package also retains an optional installer. Its read-only
`-VerifyInstalled` checks actual installed files and the full runtime baseline;
it never infers the executing NRO from a log. Exact installed candidates are a
no-op. Upgrade identities are pinned separately for the delivered v49 and v50.

Test MU versus Barca immediately after replacing the files, then win an actual
Cup final in normal time and let the ending finish. Preserve the current and
previous `scene-runtime` and `trophy-runtime` journals before another launch.
Confirm that the player walkout remains present. Trophy playback and removal
of first-launch geometry defects remain device acceptance items.

## Reproduction

Build serially with `build-wsl.ps1`, the accepted v48 runtime-pair inputs
(`e861c583ec78e9ae`) and an isolated v51 output directory. Keep all cache and
temporary output on D. Reuse the validated combined cinematic report under
`local-debug/combined-cinematics-v50`; no new donor extraction or OBB copy is
needed. Pass both delivered packages through repeated `--upgrade-package`
arguments. The optional `--sd-copy-output` argument creates the SD directory
layout and independently checked ZIP from the canonical package.

Generated artifacts, local input identities and device logs remain ignored.

## Local validation

The actual bootstrap and marker suites passed 38 tests, including production
scene-journal integration, an explicit build ID and the missing-macro fallback.
The package suite passed 60 tests, covering all five corrupt payloads, installed
v49/v50 upgrades, read-only verification, exact SD layout and a ZIP whose CRCs
are valid but whose payload differs from the proof.

Renderer, pool, journal, installer and prematch regressions passed 20 tests and
44 subtests. The final program-binary change additionally passed the nine-test
focused suite, including concurrent procedure lookup, binary reload on a shared
context, reset values, replaced locations and driver-error preservation. Trophy
result/prop, identity and composition checks passed 36 tests. Seven further
ceremony, quality and compositor tests passed; the native quality chooser was
also run separately with Python's Windows fault handler disabled because
Unicorn's handled memory exceptions generated misleading crash diagnostics in
the combined output. Its native assertions and process exit still passed.

The public-tree audit passed for 1,136 files, and the whitespace check passed.
These checks do not establish Switch rendering or trophy visibility.

## Generated delivery

The serial build succeeded. The executing image contains build ID
`74bfbebcde962ead9504e80b80e349aa046bf337`, matching its ELF GNU build-ID note.
The NRO also matches all linked ELF load segments. Independent verification
checked both archive member sets and CRCs, each loose/archived runtime payload,
the build sources and selected inputs, and the unchanged supplied device logs.

The ready-copy directory is
`local-debug/trophy-runtime-v51/FootballNX-v51-SIAP-COPY`, with a same-named ZIP
beside it. The canonical package with optional diagnostics is
`local-debug/trophy-runtime-v51/FootballNX-Trophy-Walkout-v51-TEST`.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| v51 NRO | 83,895,199 | `27ffaee2220453fbc0d2e0f094ee905c819592f10f7ce9b5e53c059e49bee8a0` |
| v51 SD-root ZIP | 70,867,590 | `153434b3649e40fdeb4a89cc6f0b9b5248532325c9971494efd198d52433ea16` |

The combined CPK, manifest, prop PAK and marker are byte-identical to the v50
delivery. This preserves the walkout assets confirmed by the user; the new
runtime reports why trophy activation succeeds or fails without relying on an
old journal. No live SD installation or hardware acceptance was performed here.

## Subsequent device test

The supplied device journal now identifies the expected v51 build and confirms
asset validation, both hook installations and final-only activation. It records
one match token, two `result-rejected caller-lifetime-or-live-final` events and
the token ending. There is no `ending-entry`, factory snapshot or candidate
creation. The user reports going directly from full time to match overview.
The broad result rejection does not distinguish a missing call scope, a caller
or scene mismatch, a lifetime mismatch or unavailable live Cup-final context.
This evidence establishes that package activation succeeded, but not which
result condition rejected this match. Trophy hardware acceptance still fails.
