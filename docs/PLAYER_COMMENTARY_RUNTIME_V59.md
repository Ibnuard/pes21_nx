# Selected-roster player commentary v59

Latest integration: [v61 hub and consolidated assets](MATCH_HUB_ASSETS_V61.md).
It retains the v60 startup mapping fix and the v59 audio/catalog policy, while
reading the accepted seed and roster audio from `FootballNX.assets`.

The staged FL26 recordings now have a runtime adapter: pressing Play freezes the
actual home and away squads, builds one bounded player bank, and explicitly
reloads native commentary before continuing to Strategy. A completed staging
receipt alone never enables a voice. The candidate still needs Switch playback
acceptance; desktop decoding and native-byte oracles do not prove device sound.

## Startup correction v60

The reported device log stops during hook installation, before the commentary
armed marker. `install_ue4_hooks` runs before `so_finalize`: the future
`load_virtbase` mapping cannot be read or executed yet. The v59 installer read
three guard prologues through `so_find_addr_rx`, and retained the typed getter's
RW backing address as a future callable. Both violate the loader lifecycle.

The v60 installer resolves optional RX symbol addresses as metadata, validates
their ranges, converts them to RW backing offsets for every instruction read,
and patches the typed PLT in that backing image. All four future callable
pointers retain RX aliases for use after mapping. A missing or out-of-range
symbol disables the optional extension. No native function is called during
installation. Startup logging distinguishes the backing guard stage and success.

The earlier host fixture made both addresses readable and failed to represent
this boundary. It now reserves the future RX region as PAGE_NOACCESS/PROT_NONE;
all installer tests run against separate RW/RX addresses and check each stored
call target. The 39 glue cases include invalid image/symbol ranges. These tests
prove the host mapping contract, not hardware boot acceptance. Audio, accepted
canary payloads and protected v58 gameplay remain unchanged.

## Scope and identity

The audited catalog contains 394 teams and 10,433 distinct roster identities.
Staging produced 6,434 decoded recordings for 1,020 new players. The first runtime
policy admits 937 new owners / 1,774 own A1/B1 P0 recordings. It preserves 609
identity-proved native voices and the two accepted Yamal/Raphinha canaries.
There are 68 carrier-label translation holds and 15 additional missing-P0 holds;
the latter excludes the overlapping label hold. Other source/identity holds
remain distinct from runtime eligibility. No global playback coverage is claimed.

Every compiled row binds BaseId, NativePES21Id, fingerprint and exact active row
hash to the pinned runtime pair. The snapshot reads every actual registered
player, including reserves, up to 40 per side. It compares the full 64-bit Match
record carrier with the team registry and preserves side and locator bits.
Native MatchSetup, OrderInfo, sound DB and the normal query Target preserve this
carrier; the pure-ID mask belongs to a separate field. Special unproved query
paths fail closed rather than relaxing identity matching.

The typed accessor returns an own cue only for admitted P0 types 0/24 present in
that mounted generation. Verified native/canary owners retain native context
behavior. Unknown, held, missing-context or mismatched owners return NULL, which
the audited native request path handles as generic/omitted name. No silence
recording, donor slot or context alias is manufactured. An absent optional pack
or rejected startup ABI retains the old v53 behavior and does not claim to fix
names in that fallback session.

## Bank construction and costs

`tools/build_player_commentary_roster_pack.py` emits an ignored intermediate
`Commentary/players-v59.nxpa` archive and a metadata-only build header. V61 merges
its unchanged members under `Commentary/players-v59/` in `FootballNX.assets`,
together with the unchanged accepted v53 delta; no nested archive is shipped.
The public header is empty. `build-wsl.ps1 -PlayerCommentaryCatalog ...` overrides
it only in the isolated checkout. The small archive marker checks availability;
compiled per-recording payload/header fingerprints bind the actual audio read
later.

The C builder starts from the exact accepted v53 full-bank replacement, preserves
its 27 embedded recordings and unaffected cue graphs, and reads one selected
recording at a time. It builds no pair matrix on disk. All 77,421 distinct catalog
pairs fit the unchanged 8-MiB bank/delta and 16-bit cue-index limits. The metadata
size sweep is arithmetic; four corner banks were also constructed by the actual
C implementation and compared with independent Python graph/audio parsing.

The largest measured bank is 7,739,602 bytes; its equivalent full delta is
7,739,650. The maximum builder allocation accounting is 15,093,093 bytes. This
excludes the caller's 7,368,350-byte seed delta, old mounted banks and native
loader allocations. A successful native mount owns its own fresh writable copy;
four slots bound overlap. The temporary preparation is freed only after all
mount leases finish. These bounds are not a device memory or FPS measurement.

## Reload, menu and ownership

The final Play action commits squads/settings/uniforms once, then captures an
immutable generation. It uses the guarded native `Load::Request(4)`, polls
`IsBusy(4)` and checks kind 29 through static `GetMountID(kind, out)`. It never
calls `MatchInterface::Load(4)`, writes a native queue, or patches a live bank.
The matching owned slot must still be mounted with accepted generation policy
at dispatch, so reuse of a native mount ID cannot admit stale proof.

The existing Strategy continuation resumes once after this barrier and skips a
second squad-save transaction. Timeout, stale selection, failed preparation or
unproved mount restores the usable setup hub. A failed generation cannot open
Play under a different bank. Cancellation drains an outstanding native request
before another generation can start. Rematch and Select Team invalidate the
old intent through their normal new-match/selector path.

Mount callbacks borrow immutable preparation through tickets, clone a fresh ACB,
and report/release only after the final native result. Native unmount failure
retains that slot; successful unmount retires its metadata and buffer. The short
policy lock covers metadata only, with no native calls, allocation or I/O under
it. Cue names live in the immutable compiled catalog. Decoder cipher-table
clearing is limited to complete 96-byte fingerprints in a currently accepted
mounted bank, including split-header reads; unrelated headers retain native
behavior.

## Validation and candidate testing

Focused tests compile the actual builder, reload coordinator, lookup policy and
production wrappers. They exercise identity, graphs, cue caps, malformed input,
four concurrent leases, once-only dispatch, timeout/cancel/drain, rematch-style
generation changes, fallback, header splits/corruption and mount ownership.
The integration harness exercises the actual roster/menu glue. Production
Switch compilation uses the pinned private catalog and the v58 gameplay inputs.

For commentary-only work, the gameplay functions/files listed in the ignored
`PROTECTED-GAMEPLAY-SECTIONS.json` remain hash-identical to v58 unless the human
authorizes a gameplay change. V61 records its requested hub/editor and referee
changes separately while retaining the unaffected pins. Candidate
packaging verifies NRO/ZIP payloads and preserves the referee animation/token
and v53 commentary delta byte-for-byte. No OBB, face PAK or proprietary source is
duplicated. Test the candidate on Switch with (1) Barca/MU canaries, (2) a pair
with newly admitted names, (3) substitutions, (4) Rematch and Select Team and
(5) an unavailable-name owner. Logs distinguish preparation, mount outcome and
continuation; only heard device names establish playback acceptance.
