# Pause Game Plan v19 — cold portrait cache and pending substitutions

Status: diagnostic, not yet verified on Switch. Keep the existing OBB and stable
`dist` package. The successful v18 MemberId identity restoration is retained.

## Evidence from the supplied v18 hardware log

- Both sides restore 18/18 authentic player identities.
- Both sides report `cachedFaces=0`; no earlier custom portrait reads occurred
  in this session. A cache-only live renderer therefore cannot show faces when
  the pre-match custom Game Plan was skipped.
- Three Harvey Barnes/Jacob Murphy operations reach the success message, and
  each is preceded by a native match-plan save. The custom page still rendered
  the unchanged native starting order, hiding the pending substitution.

## Changes

Portrait cache misses start bounded asynchronous reads through native `sys::File`:
check the archive path, disable error-stop and post-wait, then `ReadStart`.
Poll `IsBusy`/`IsError` on subsequent UI frames, validate the completed PNG, cache
it by portrait ID, and let the existing render-thread handoff upload it. There
are at most four concurrent reads. Missing, malformed, errored, or timed-out
assets are not repeatedly requested during the same editor visit. Reads are
cancelled/released on Back or UI reset. No `SyncRead` or `SyncFinish` occurs on
the live path. Native Release's cancellation/zombie ownership was audited in
the supplied `libUE4.so`; this avoids freeing in-flight native objects directly.

The custom pitch and bench now project pending substitutions using native
`SquadData::GetReservedMemberId(MemberId)`. Only displayed slot attributes are
exchanged: player identities and native squad storage remain unchanged. Native
`CanReserved`/`SetMemberChangeReserved` still enforce eligibility and substitution
limits; native Save/Footer/resume still own actual application. Re-selecting the
pair follows native cancellation, and applied reservations are not projected
again. Rejected requests are logged rather than silently appearing successful.

## Validation and build

Host tests execute the production asynchronous loader with an empty cache,
duplicates, full queue, missing file, variant lookup, read errors, invalid PNG,
timeout, and Back cancellation. Other tests execute the production bench-swap
handler and pending projection for acceptance, cancellation, rejection, reversed
vector order, identity preservation, and native-state preservation.

```powershell
python -m unittest discover -s tests -p 'test_pause*.py' -v
python -m unittest discover -s tests -p 'test_live_gameplan*.py' -v
python -m unittest discover -s tests -p 'test_gameplan_editor.py' -v
.\build-wsl.ps1 -OutputDirectory local-debug/pause-console-v19-diagnostic -Diagnostics -Jobs 8
```

## Hardware test

1. Fully restart with `local-debug/pause-console-v19-diagnostic/pes21_nx.nro`.
2. Start a match **without opening pre-match Game Plan**, then Pause → Game Plan.
   Portraits may appear progressively as the asynchronous reads finish.
3. Select a starter and a substitute. The incoming player should appear on the
   custom pitch immediately. Back/resume and verify the actual substitution
   occurs at the native allowed moment; reopen and verify the new lineup.
4. Also check cancellation before resume, two-human mode, and a second fixture.

Relevant log lines: `pause-v19: portrait queued/absent/completed` and
`pause-v19: substitution ... allowed=... reserved=...`. If an asset is truly
absent from the OBB it stays blank; this build does not fabricate player faces.
Send the resulting log if portraits or substitutions still fail.
