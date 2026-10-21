# Native player-name lookup and missing-name policy v58

The per-team batch has finished staging 1,020 identity-validated players and
6,434 recordings. That is audio preparation, not a mounted runtime bank or
playback acceptance. The accepted Yamal/Raphinha candidate and 609 independently
proved native voices remain the baseline to preserve.

This audit reads the compatible Mobile library with SHA-256
`a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187`.
The REA session had no configured native analysis provider. The findings use
local ELF/relocation parsing, Capstone inspection, and bounded Unicorn calls of
the original ARM64 methods. They are not REA runtime Evidence, full application
execution, Switch playback, or a frame-rate measurement. Raw instructions and
probe authoring remain ignored under `local-debug/commentary-native-fallback-v58`.

## Established lookup contract

| Native method/data | RVA | Observed purpose |
| --- | --- | --- |
| Player-name creator | `0x6cd0bf4` | Generates candidate labels and keeps only labels reported present by the sound interface. |
| Command-to-name-type conversion | `0x6cc2238` | Command 1 selects type 0; command 25 selects type 24. |
| Name-type string table | `0x9430e78` | Type 0 is `A1_P0`; type 24 is `B1_P0`. |
| Command player-name accessor | `0x6cc10f8` | Converts the command, then calls the typed accessor through its PLT entry. |
| Typed player-name accessor | `0x6cc1140` | Finds the exact player and requested context; returns null for an empty context pack. |
| Name request assembly | `0x6cbbe24` | Handles a null name with the native generic-label or rejection route. |

The typed accessor matches `common::PlayerId` against at most 23 team entries.
The carrier's native owner component is read at byte offset 4; when that value
is nonzero, its low 16-bit component is also compared. This full carrier
comparison must not be replaced by a masked or truncated donor lookup. A name
pack is 32 bytes at player-unit offset `0x10 + type * 32`; its vector's begin
and end are at pack offsets 8 and 16. An empty pack returns null before any
division or string access. A missing context does not automatically borrow
another player's name or fall back from P1/P0A to P0.

For a null name, request assembly queues the original, nonempty
`SysParamData` generic label when `AdditionalPartsType` is zero. If that label
is empty, or the additional-parts type is 1 or 2, it rejects the name request.
The native generic selector and audio remain responsible for what is heard.
There is no need to fabricate a silence HCA, rename another player's cue, or
invent a generic recording. A bounded direct-call scan of the sound region
also found PA announcements and player-name availability checks reaching the
command accessor, which reaches the same typed accessor.

Ten native-byte oracle cases corroborate empty packs, exact A1/B1 P0 labels,
mismatched player IDs, and generic/rejection branches for pre/post commands.
Mutex, roster accessors, registry services and queue output use explicit test
fixtures. The fixture generic string proves unchanged queueing, not the
presence of that fixture string in a shipped audio bank. Indirect or inlined
callers outside the audited sound region remain unproved.

## The six-digit staging domain is insufficient

The creator calls the native pure-player-ID helper, takes the upper 32 bits,
then calls a same-person helper that is a no-op in this library. With a test
carrier placing the native ID in those upper bits, the pure-ID helper changes
68 of the 1,020 staged owners. For example, Ao Tanaka's native owner 562751
becomes label-domain value 38463 under that carrier model. The ordinary
six-digit range check in the stager does not prove native label reachability.

Those 68 rows are explicit **runtime label-translation holds**. Their staged
audio and identity checks remain valid and do not need to be rerun. Actual
registry-produced carriers, correct label reachability, or an explicit
identity-bound translation still need proof. The private report records every
changed owner and any other active roster owner sharing its pure-ID value.
Twelve held rows share that value with another active native owner; this is a
catalog collision audit, not proof those players appear in the same match.
That value is never permission to attach a recording to the other slot.

## Minimal runtime integration proposal

The typed accessor has the conceptual ABI
`const char *lookup(accessor, const HomeAway *, const PlayerId *,
PlayerNameType, DBAccessType)`. A narrowly scoped filter can preserve the
native missing-name route:

- For the accepted canaries and independently verified native owners, retain
  the original lookup for all contexts.
- For a validated new owner, admit only its own accepted A1/B1 P0 contexts
  (types 0 and 24). Other contexts return null; do not alias them to P0.
- For a held or unproved current owner, return null instead of exposing a
  reused-slot name. Native request assembly then keeps its normal generic or
  omitted-name behavior.
- Do not identify an owner solely by a pure-ID result. Bind the full native
  owner/carrier to the active roster's BaseId, fingerprint, row identity and
  runtime-pair generation. Translated labels need their own proof; returning
  an owned, immutable exact cue-name string is an option only after the bank
  containing that exact name is successfully mounted and lifetime-bound.

The typed getter's first four words are `f81c0ff8 a9015bf7 a90253f5 a9037bf3`;
its 412-byte body hashes to
`da09f6096b3dc214c69f9c57ae7040bf39e95d2ded9a52b6fafce5a3d08c6c85`.
The command accessor reaches it through PLT `0x3849bc0`. These values are
compatibility guards, not authorization to hook an unmatched library.

The lookup policy must activate only after an accepted home/away bank mount
and a matching roster-policy generation. Its allowlist needs the exact bank,
runtime pair, roster identities, selected cue names and native HCA header
fingerprints. Keep cue strings alive through requests and native unmount,
including overlapping loads and rematches. Missing/corrupt optional data,
failed mounts, exhausted slots and policy-generation changes must have tested
behavior. The current unchanged-bank failure path preserves compatibility
but does not guarantee correction of inherited wrong names.

No runtime hook, new bank, build or installation is performed by this audit.
The next candidate still requires real bank reconstruction, native lookup
reachability and collision checks, bounded cue/memory costs, decoder and
generation/lifetime/rematch/failure tests, and device listening. Do not label
all staged players runtime-ready until those gates pass.

## v59 pure filter and carrier proof

`source/player_commentary_lookup.h` now implements the pure decision component.
It consumes the compiled `PcBankCatalog`, successfully mounted `PcBankResult`,
and immutable `PcLookupSnapshot` of actual full carriers and sides. The mount
owner creates bindings, calls `pc_lookup_accept` only after native mount
success, and calls `pc_lookup_decide` under its policy lock. The result is
`ORIGINAL`, `NULL`, or an exact static catalog cue pointer. Native calls occur
after releasing that lock. Unknown or held owners, wrong side/locator,
unsupported contexts, wrong cue identity, unmounted owner and foreign cue
pointers return null in an active generation. Canary/verified native owners
retain the original lookup. An inactive/mismatched generation deliberately
uses baseline compatibility behavior and cannot be reported as fixing donor
names for that failed/inactive bank.

Additional native-byte fixture execution now follows all 68 held owners with
two different low16 locators each: 136 cases. Native
`tmpdb::util::GetPlayerIdByUniqueId` at `0x6d8bc38` returns the complete stored
carrier without dropping upper native-ID bits. Registry conversion at
`0x7bef3f8` stores the raw carrier at `TeamMemberInfo+0`, separately storing the
pure carrier at `+8`. Native `PlayerParameter::SetPlayerId`,
`MemberInfo::SetPlParameter/GetPlayerId`, and sound player-unit ID storage
preserve the raw carrier. Manager, team and player services use explicit
fixtures; this establishes the native copy/construction contract, not a full
application or device trace. The private `NATIVE-CARRIER-V59.json` binds all
function hashes and cases.

The first v59 filter still holds all 68 new owners above the 18-bit pure-ID
domain, even if accidentally marked `NEW`. This is intentional until the
actual mounted own-name translation is separately accepted; no masked donor
is used. Root integration must capture carriers from actual selected records,
validate against the effective team roster and preserve locator differences
between CommonWork and Match. Constructing `NativeID << 32` is insufficient.
The typed PLT guard words are `d002e4d0 f9401e11 9100e210 d61f0220` at
`0x3849bc0`; the original target is the guarded native function at
`0x6cc1140`. A matching immutable generation, kind-29 mount ID, decoder header
allowlist and successful unmount ownership remain integration requirements.
