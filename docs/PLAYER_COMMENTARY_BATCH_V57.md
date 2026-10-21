# Per-team player commentary continuation v57

Latest continuation: [selected-roster runtime v59](PLAYER_COMMENTARY_RUNTIME_V59.md)
implements bank construction, explicit native reload and identity-safe P0
lookup. A production test candidate has been built and its ELF/NRO, protected
v58 gameplay and ZIP payloads verified. The focused host suite passed 184 tests
(one optional legacy canary-regeneration fixture was not enabled), plus 30
actual-glue tests. Switch playback for the newly admitted voices is still
pending. Staging below is complete and must not be repeated to resume runtime
work. The local handoff points to the delivered ready-copy candidate.

The user confirmed that Yamal and Raphinha are called correctly on Switch and
requested an automated team -> player -> validated identity -> FL26 call port
workflow. This continuation covers every team in the active local selector
catalog, including national teams. A shared club/national player is processed
once by BaseId, then referenced by each team; team assignments do not create
duplicate players or recordings.

## Reproducible detached staging

The CLI is `tools/batch_player_commentary.py`. Its local configuration is
`local-debug/commentary-batch-v57/config.local.json`, and its bounded summary
is `RUN-STATUS.json` in that work directory. The configuration references the
owned original PES21 Player.bin, active Player.bin CPK and identity state,
selector roster include and catalog, FL26 database and English audio CPKs,
the accepted v53 report/delta, and the local FFmpeg executable. These optional
ignored inputs are not repository guarantees.

```powershell
. D:/PESNX-Cache/use-cache.ps1
python -B tools/batch_player_commentary.py audit --config local-debug/commentary-batch-v57/config.local.json
python -B tools/batch_player_commentary.py run --config local-debug/commentary-batch-v57/config.local.json
python -B tools/batch_player_commentary.py status --config local-debug/commentary-batch-v57/config.local.json
```

`--max-teams N` is an optional bounded smoke run; a later unbounded run reuses
completed player/audio receipts. `audit` performs no extraction. `run` owns
an OS-held exclusive lock, indexes the source AWB once, reads one recording
at a time, and runs one desktop decoder at a time. All generated output stays
under the configured ignored directory on D. It does not duplicate an OBB,
extract the complete AWB, edit source CPKs, or replace `dist`/SD data.

Each run hashes its database/identity/selector inputs and authoring recipe,
both exact ACB members and the source AWB index. Every selected recording is
then hashed per player immediately before staging or cache reuse.
The large sound containers also retain their path, size and modification time;
unrelated recordings are not scanned on each resume. Each immutable plan binds
all bytes actually used to the runtime pair. For every team, the runner reads the
actual compiled selector roster, resolves a unique active BaseId/native-ID
owner, recomputes its canonical fingerprint, and compares the active row's
hash with the registry state. An existing native call is preserved only if
the original PES21 record independently establishes the current owner's name
and nationality, the registry explicitly pins that commentary owner, and the
Mobile bank actually has calls for it. The accepted Yamal/Raphinha delta and
its active identities are pinned separately and never regenerated.

Other calls require a direct FL26 BaseId record with the owner's canonical
name/recorded aliases, nationality, height, preferred foot and age agreement.
A numeric ID alone or a similar surname is insufficient. Each accepted source
cue must be a supported direct HCA waveform. Its manifest retains the original
source cue and wave ID, adds an explicit native cue name, and hashes the exact
audio. Native IDs outside the separately audited six-digit label domain are
held, not silently truncated or guessed. The runner never edits player IDs.

Every newly staged recording passes a full serial FFmpeg decode, exact hash
readback, and a provenance-bound receipt. This verifies desktop decoding; it
does not prove native HCA synthesis or Switch playback. Content-addressed audio
is shared across teams. Cached completed payloads are hash checked on resume.
Deterministic source/decoder holds are retained rather than retried unchanged.

`plans/<input-key>/PLAN.json` records all audited players and their team
assignments; `teams/<input-key>/<team-id>.json` is each team's checkpoint;
`players/<BaseId>/<player-key>/complete.json` binds a staged player to source,
identity and cue mappings. `audio/` contains local copyrighted recordings and
must remain ignored. Only project-authored tools, tests and documentation may
be committed.

## Progress and automation

Report audited unique players, preserved native calls, the two accepted
canaries, staged/desktop-decoded new players and recordings, missing source,
identity/translation conflicts, and runtime acceptance separately. Completed
team checkpoints are workflow progress; they are not accepted runtime banks.

The thread heartbeat must check `OWNER.json`, the real process command/start
time, OS lock ownership, `RUN-STATUS.json`, and current stdout/stderr log. While
the runner is alive and making progress, do not start a duplicate or edit its
recipe/config. If it exits, inspect the failure, change the input/recipe when
needed, then resume the same CLI/checkpoints. Do not retry a deterministic
hold unchanged, assign a donor, install files, or claim playback automatically.
Once staging is complete, continue bounded runtime integration and validation;
do not keep rerunning the audit as a substitute for a port.

The completed run processed 394/394 teams and all 10,433 distinct roster
players. It staged and desktop-decoded 6,434 recordings for 1,020 source-valid
new players; 609 verified native owners and the two accepted canaries remain
preserved. There are 5,536 local-source absences, 1,820 identity holds and 1,446
source/translation holds. These categories remain separate from runtime gates.
No wider runtime bank has been installed or accepted from those counts.

## Native integration findings after staging

[The native lookup audit](PLAYER_COMMENTARY_NATIVE_LOOKUP_V58.md) establishes
literal P0 types 0/24, and native NULL-name handling: use the original generic
label where that request permits it, otherwise omit that name request. Ten
native-byte oracle cases corroborate the bounded branches. They do not prove
playback. Filtering must use the raw identity-bound owner, never a masked
numeric slot. Native pure-ID conversion changes 68 staged carriers; twelve
share a pure-domain value with another active owner. These are explicit
runtime label-translation gates, not failed desktop decodes or permission to
attach a recording to the masked owner.

[The mount audit](PLAYER_COMMENTARY_MOUNT_V58.md) establishes that commentary
loads before team selection and normally remains mounted between matches.
Reading two selector globals at MountData therefore cannot establish a
coherent current pair or refresh it on Rematch. Integration needs an immutable
two-roster generation, an explicit native commentary Request(4), its IsBusy(4)
completion barrier and the expected kind-29 mount, with bounded failure and
slot/header lifetime handling. A mere dispatch is not mount acceptance. Read
both audit documents and their ignored evidence indices before implementing;
do not rerun the completed staging recipe.

## Runtime integration boundary

The deployed v53 bank has 64,000 original cues, a 16-bit cue-index domain and
an explicit 8 MiB bank/delta limit. Its accepted rebuilt bank has 64,019 cues
and 7,368,302 bytes. The current policy accepts only its exact compiled hashes
and header allowlist. The detached batch does not enlarge any of these limits
or generate one bank containing every player. Such a bank cannot simply append
all available FL26 context variations.

A next runtime candidate must select only actual home/away roster calls at
bank-load time, reuse native slots where their cue/graph identity permits it,
and budget new cue indices, graph bytes, recordings and mount lifetime before
publishing the bank. Cache keys must include both roster identity fingerprints
and the full source/recipe identities; a lazily cached match selection avoids
prebuilding every possible team pair. Check the worst selected roster, not
only Barcelona/MU. Preserve the accepted canary recordings exactly and keep
valid unrelated native calls.

The existing memory-AWB design has insufficient space for arbitrary long
biographical calls for every possible roster. The initial runtime implementation
will use each validated player's own short A1/B1 P0 recordings, preserving the
full accepted Yamal/Raphinha canary and verified native calls. This scope fits
the user's request for correct player names and avoids increasing the 8 MiB
limit. The staging runner still saves all validated source contexts for later
use; it does not install this policy into the runtime.

The current measured plan has 394 teams and 10,433 distinct native roster
players. It identifies 1,020 source-valid staging candidates, 609 preserved
native voices and two accepted canaries. Other rows remain explicit source or
identity holds, including legacy records without a proved canonical identity.
These audit counts do not mean 10,433 newly ported/accepted players.

All 77,421 distinct team pairs were measured under the current one-cue/one-wave
builder. All available variants can add 7,791,410 bytes for Tottenham/Spain,
making the bank at least 15,159,712 bytes; 18,834 pairs already exceed the cap
before graph/alignment overhead. The short P0 subset's worst pair adds 399,140
bytes for Real Sociedad/Athletic Bilbao, giving 7,767,442 bytes before overhead.
The maximum new cue count is 62 for that subset, versus 1,516 remaining indices.
These numbers are recipe/roster-specific and must be recalculated when those
inputs change. The immutable detailed report is referenced by the local
`ROSTER-COST-LATEST.json`; the runtime continuation is pinned separately in
`RUNTIME-POLICY.json`.

Sixteen otherwise source-valid players have no literal A1/B1 P0 recording.
Keep them held or select a measured, independently established own-source
alternative. Do not invent a context alias from its spelling or inherit a
different player's numeric-slot recording. Native context fallback behavior
must be established before applying aliases or substitutions. For unproved
name owners, the runtime candidate must withhold mismatched donor-name cues
and use verified native generic commentary. An audit hold alone does not fix
an inherited wrong name. Prove the actual native cue lookup and missing-name
fallback contract before implementing suppression; do not fabricate a silence
HCA or assume that cue deletion/renaming is safe. This is an identity release
gate, separate from source availability and byte budgeting. The existing
optional-delta failure path still falls back to the unchanged baseline bank;
that fail-safe behavior must be documented and must not be presented as having
corrected every reused-slot name.

An auxiliary bank's lookup order, lifetime, decode allowlist and fallback need
native evidence before deployment. A match bank must reject capacity overflow
and retain the original bank. Never raise the limit or drop voices silently.

After `LATEST-PLAN.json` exists, this separate read-only audit measures every
distinct active home/away team pair without producing pair packages:

```powershell
python -B tools/audit_commentary_roster_costs.py --config local-debug/commentary-batch-v57/config.local.json
```

`ROSTER-COST-LATEST.json` points to its immutable report. It records exact
selected audio sizes, new cue-name counts, pair extremes and the existing bank
headroom. Shared players are counted once, while each cue embeds one recording
under the current v53 builder. UTF/AWB alignment overhead is extra. A lower
bound above the cap proves that variant cannot fit under that builder. A lower
bound below it is not a reconstructed-bank acceptance. A future shared-wave
graph would need separate native and schema validation.
The literal A1/B1 P0 calculation lists missing players; its byte estimate does
not validate native context aliases or prove a reconstructed bank fits.

The final ready-copy candidate requires the updated runtime lookup/mount
contract, independently reconstructed bank/cue preservation checks, all new
recordings' decode receipts, finite rematch/unmount/failure tests, package hashes
and representative Switch playback. Detached staging alone does not meet that
release criterion.
