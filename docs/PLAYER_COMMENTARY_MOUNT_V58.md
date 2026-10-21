# Selected-roster commentary mount contract audit v58

This audit supplies the runtime boundary for the completed per-team staging
workflow. It does not add a runtime bank, change the accepted Yamal/Raphinha
payload, or claim Switch playback. The current v53 replacement is mounted
without selected-roster inputs. A replacement selected only at `MountData`
would be insufficient because the native commentary banks persist between
matches.

## Observed native lifecycle

The evidence is bounded local ELF/Capstone inspection of the owned compatible
Mobile library. REA reports no configured native decompiler on this host;
these findings are not REA execution or device observations. Raw instructions,
function byte hashes, direct-branch references and the seven-bank metadata
table remain ignored under `local-debug/commentary-roster-runtime-v58/`.
The checked ELF contains no GNU build-ID note, so the receipt does not invent
one. It binds the inspected function bytes and file identity separately.

| Entry point | Native RVA | Observed contract |
| --- | --- | --- |
| `sound::sys::Load::Request` | `0x6d00d78` | Six-entry dispatcher. Labels 2/3 load gameplay groups; label 4 unloads commentary group `0x43f0000000`, requests its seven banks, then updates commentary volume. |
| `sound::sys::Load::requestComment` | `0x6d02b84` | Resolves current commentary language, builds language-specific ACB/AWB paths, and queues seven existing bank entries. `10_PLAYER` is kind 29, not an arbitrary new bank kind. |
| `sound::sys::Interface::postInit` | call at `0x6d00a54` | Requests label 4 during sound initialization, before any selected-roster publication exists in wrapper source. |
| `TitleDataDownloadCommon::ProcLoadCommentary` | `0x684cce4` | Requests label 4 once, then waits on `Load::IsBusy(4)` before completing its state machine. |
| `process::SoundSelect::Main` | call at `0x6cb0be4` | Also requests label 4 after its native sound-selection path. |
| `game_mode::MatchListener::MatchLoadSound` | call at `0x7bf8dd0` | Requests label 2 through `MatchInterface::Load`; this is gameplay loading, not commentary reloading. |
| `sound::sys::MatchInterface::Load` | `0x6d037a8` | Admits only labels 2/3 and passes them to `Load::Request`. It cannot be used with label 4. |
| `sound::sys::Load::UnloadGame` | `0x6d031b8` | Unloads gameplay groups `0x300fffbe40` and `0x0800000030`; it does not unload the commentary group. |
| `sound::sys::load::Manager::Update` | `0x6d0b0f0` | Waits for queued file completion, then calls `mountData`. The request and mount are separate phases. |
| `sound::sys::load::Manager::mountData` | `0x6d0b220` | Calls the existing hooked `CInfBase::MountData` PLT with bank data, binder, path, flags and an output mount ID. No team or registry pointer is passed. |
| `sound::sys::Load::IsBusy` | `0x6d03230` | Label 4 checks the commentary group's queued work. False is completion of pending work, not proof that a replacement mounted successfully. |
| `sound::sys::load::Manager::GetMountID` | `0x6d0b968` | Copies the mount ID for a supplied kind under the native loader mutex; loader initialization success alone does not prove a valid ID. Inspect kind 29's returned ID as well as wrapper-owned outcome. |

Direct B/BL references were searched across the ELF executable sections.
Indirect calls and runtime timing remain outside that static search. Native
`MatchInterface::IsLoading` checks gameplay labels 2/3 and cheer work; it is
not a commentary label-4 barrier.

## Wrapper selection and ownership

In `source/ue4_hooks.c`, `pes_sound_mount_data` and
`pes_sound_unmount_data` own the current bank lifecycle. Each bank family has
four slots with `free -> reserved -> mounted` state. A successful patched
mount publishes its native ID and retains its writable ACB buffer. A patched
mount failure frees only the replacement and retries the original arguments.
A successful native unmount frees the exact reserved owner; an unsuccessful
unmount restores its mounted state. Slot exhaustion retains the original
bank. These properties must survive the roster extension.

`exhibition_home_team_id` and `exhibition_away_team_id` are independently
written by the custom selector and `exhibition_select_team`. The tutorial
bootstrap explicitly clears them. Two atomic reads therefore do not prove
a coherent, final pair, and the existing bank-load hook can run before either
is set. Do not call arbitrary registry, tmpdb or selector methods from the
audio mount thread to compensate.

`exhibition_refresh_selected_tmpdb` resolves the two rosters, installs their
effective players and publishes teams to tmpdb only after both sides contain
at least eleven players. `exhibition_find_roster` can return career overlays,
and `exhibition_roster_player_allowed` can filter club assignments. A static
team ID alone is therefore insufficient to bind a future bank to the actual
match. The selected player set must include substitutes; a starting-eleven
snapshot would omit valid later calls. Current prematch player storage is
bounded at forty per side.

## Proposed runtime API and state machine

This is a proposal for the next integration, not an existing parser or source
implementation. The offline container schema is intentionally not frozen by
this audit. Before authoring it, agree its byte layout with the offline
builder and generic-name fallback policy.

1. On the menu/game thread, prepare an immutable `PlayerCommentarySelection`
   after successful roster installation and final Play admission. It contains
   a monotonically increasing generation, runtime-pair/content identities,
   logical and physical team IDs, and the deduplicated effective home/away
   player set. Every player references its validated BaseId/native-ID/
   fingerprint entry in the pinned catalog. Preserve full accepted canary
   calls and independently proved native calls. Unavailable identities are
   explicit holds governed by the separately proved generic fallback policy.
2. `selection_publish(snapshot)` publishes both sides as one transaction.
   `selection_invalidate(reason)` runs before a new bootstrap, Select Team,
   abandoned Play transaction, or career roster mutation. Changing selection
   must not mutate or free any already mounted bank.
3. Before native match sound/AI initialization, prepare and validate the
   selected bank, or its bounded reconstruction inputs, without unloading the
   currently accepted bank. The result and temporary work each have explicit
   caps; the result remains at most 8 MiB, with 16-bit cue bounds. No all-pairs
   files or source extraction occurs on Switch.
4. With no live match using the banks, request native `Load::Request(4)` once
   for that generation. Use the existing commentary-group lifecycle instead
   of directly freeing banks or calling `MatchInterface::Load(4)`. This reload
   also passes the other six banks, including `00_TEAM`, through their ordinary
   native paths. Indonesia handling must remain intact.
5. The existing `MountData` boundary acquires only the immutable published
   snapshot and pinned package view. It verifies the exact base, selection,
   graph, size and recipe identities before using one of the four player slots.
   A failed or unavailable optional extension uses the documented accepted
   v53/original fallback policy; it must never be reported as corrected names.
6. A pending-load state polls `Load::IsBusy(4)` without blocking the game loop.
   Once false, require kind-29's native mount ID plus the wrapper's recorded
   generation/outcome. Completion alone is not replacement acceptance. A
   finite timeout or rejection releases the custom loading state and permits
   the usable native fallback/menu path; it must not create infinite loading.
7. Each player slot owns `{bank, byte_count, generation, mount_id, outcome,
   exact_plaintext_header_set}` until native unmount succeeds. Publish all
   fields before `mounted` state, and keep header data immutable. Decoder
   approval requires the exact recognized 96-byte header to belong to a
   currently mounted player slot. A team slot, reserved slot or future
   selection cannot approve it. Do not install a global allowlist for every
   staged source recording or clear the global cipher.
8. Unmount reserves the exact owner before native ID reuse. On native success,
   retire its bank and header set together; on failure restore both. A new
   generation can coexist only in a different bounded slot. Never force-free
   a failed-unmount owner to make room for a rematch.

The actual safe point before match sound/AI initialization, label-4 reload's
interaction with still playing menu commentary, and the bounded native loader
completion/failure path must be confirmed in integration. Source evidence
justifies the native lifecycle to reuse; it does not prove that an arbitrary
new Play hook is safe. Current read-only metadata estimates are not an
accepted reconstructed bank.

## Required focused tests before a runtime candidate

- Exercise the real wrapper mount/unmount code with a selected generation:
  exact base acceptance, missing/corrupt container, wrong runtime pair or
  roster fingerprint, graph/index overflow, allocation failure and 8-MiB
  rejection. Preserve all native call arguments and original fallback.
- Drive startup with no selection, select home then away, cancel selection,
  rematch with the same sides, swap sides, select a different opponent, and
  career roster changes. Assert one coherent generation, all substitutes,
  shared-player deduplication and no stale previous-pair bank.
- Reproduce the native Request/IsBusy distinction in an actual-function
  harness: label 4 requested once; queued completion cannot be mistaken for
  successful kind-29 mount; native rejection and timeout cannot trap Play
  under a custom loading cover. Repeated menu callbacks cannot duplicate loads.
- Test four overlapping slots, a fifth fallback, failed then successful
  unmount, and mount-ID reuse during unmount. No premature bank/header free,
  borrowed mutable ACB, or cross-generation replacement is allowed.
- For every accepted new header, test all 97 possible two-span splits,
  truncated/negative input lengths, all one-byte corruptions, encrypted and
  unrelated headers, and team/player isolation. After the last matching
  player owner unmounts, that dynamic header must no longer clear a table.
- Independently verify selected cue graphs, unchanged valid native calls,
  byte-identical accepted canary audio, actual generic fallback for held
  owners, full selected recording decode, worst-pair reconstructed size and
  temporary/retained memory. Native packet checks do not prove sound output.
- On Switch, test two unrelated team pairs, Barcelona/MU, substitutes, rematch,
  Select Team and commentary language changes. Record staged, reconstructed,
  mounted and heard counts separately; keep device playback/FPS unclaimed
  until observed.

No runtime source, accepted audio, proprietary input or active installation
was changed by this audit.

## v59 implementation continuation

The lifecycle component now exists in `source/player_commentary_reload.h` and
`source/player_commentary_reload.inc`. This is implementation and host test
progress, not a delivered or device-accepted runtime candidate. The original
native evidence above is reused; no new decompilation is claimed.

`pc_selection_build` accepts both effective native rosters, their actual full
64-bit carriers, logical/physical team IDs and the pinned `PcBankCatalog`.
Each side requires 11–40 distinct players, including substitutes. The
carrier's upper word must equal its supplied native ID; all lower locator bits
are retained. Shared club/national identities are deduplicated only for source
selection. Both complete side arrays remain available for lookup bindings.
The catalog must have strictly sorted unique native owners. Proved owner rows
require their BaseId, 20-digit fingerprint and exact 64-digit row hash;
unknown/unproved owners remain explicit generic holds. No alternate numeric
owner or donor is selected. `pc_reload_begin` reconstructs the canonical
selection and checks its key instead of trusting caller-edited owner pointers.

The game-thread API is `pc_reload_init`, `pc_reload_begin`, `pc_reload_tick`
and `pc_reload_cancel`. A new admitted Play action supplies a fresh nonzero
intent token. Repeated begins during a pending operation are blocked; an
already completed intent cannot dispatch again. Before preparing, the
coordinator checks that no other native label-4 load is pending. It then calls
the bounded builder callback with the immutable selection, validates the
prepared bank's size, selected owner set, baseline header prefix, cue references
and scratch bound, and only then issues native Request(4) exactly once.
The request callback reports guarded call admission, not native load success.
`STARTED` transfers one loading-release obligation to the coordinator, which
can complete synchronously on preparation rejection. `BLOCKED`/`REJECTED`
transfer no such obligation: root must retain or restore the usable hub and
must not start a duplicate Play or re-arm loading after an immediate callback.

The mount callback obtains a `PcReloadBorrow` through `pc_reload_borrow`.
Its ticket pins both `const PcBankResult` and `const PcSelection`; the wrapper
must copy the bank, header/lookup metadata and all required carriers into its
fresh per-mount owner. It reports the actual selected/v53/original/failed mount
outcome with `pc_reload_report`, then ends the exact ticket with
`pc_reload_release`. Up to four tickets can coexist. Cancel, timeout, stale
tickets and duplicate release cannot free another generation's preparation.
The main thread retires the shared preparation only after every borrower ends.
Mounted writable copies remain owned by the wrapper until their native unmount
succeeds; this component never frees them.

`pc_reload_tick` requires both IsBusy(4) completion and the reported generation's
successful kind-29 mount ID before calling the original Play continuation.
It also checks the original Play intent is still valid. The default failure
policy releases custom loading and returns to a usable hub/menu. Native/v53
fallback may continue only when explicitly enabled and that generation has
actually reported the matching fallback mount. Missing preparation, missing
mount proof, ABI rejection or timeout never silently dispatch an unproved
previous bank. An absent optional package can instead leave the feature
inactive in the root glue, retaining the ordinary v53 startup path.

Cancel/timeout notifies the menu once and enters a drain state after an issued
request. Late native mounts cannot borrow its retired preparation. A new
generation remains blocked until native label-4 work is quiescent and all old
tickets end; an audio worker retaining a lease never leaves the user under a
permanent custom loading cover. No callback runs while the policy lock is held.

The root integration point is the final Play branch of
`main_menu_2p_prematch_hub_process_pending`, after both sides' saved plans and
settings/uniforms are applied, before the hub is cleared or Strategy DirectSet
is queued. Root is responsible for capturing actual tmpdb carriers there,
guarding the three native APIs, connecting the existing per-mount ownership and
lookup policy, polling on the game thread, and resuming the unchanged Play tail
once. These hooks do not belong in the protected v58 gameplay helper bodies.

`tests/test_player_commentary_reload.py` compiles the actual component as C.
It covers full 80-player snapshots, lower carrier bits, canonical and unknown
owners, preparation-before-request ordering, separate load/mount proof,
reentrant and duplicate dispatch prevention, bounded failure/fallback behavior,
wrap-safe timeout, cancel/drain, stale tickets and four actual concurrent
pthread borrowers. These synthetic tests contain no proprietary bank/audio.
Builder/lookup integration, native packet checks and representative Switch
playback remain separate requirements before packaging.
