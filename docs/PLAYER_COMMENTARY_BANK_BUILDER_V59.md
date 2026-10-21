# Selected-roster commentary bank construction v59

`source/player_commentary_bank_builder.h` reconstructs an actual CRI player
bank for one immutable selected roster. It is not a bank for every player, a
sound-engine replacement, or evidence of playback on Switch. The caller owns
publication, native commentary reload, lookup policy, generation, mount and
unmount lifetime. See the v58 native lookup and mount contracts.

The public default `player_commentary_roster_catalog.h` is empty. A local build
may replace it with the metadata-only header generated from completed v57
staging receipts. The separate, ignored `Commentary/players-v59.nxpa` is an
FNXAS01 archive of recordings. `catalog-id.txt` contains only the runtime-pair
string followed by a newline; it is an early availability check, not recording
acceptance. Each requested recording still requires its compiled length, full
payload FNV and exact 96-byte header FNV. The archive reader checks its own
index, bounds and checksum as well. Offline SHA-256 receipts bind the staged
audio and decoder proof; FNV is a runtime compatibility fingerprint, not a
cryptographic authenticity claim.

## Local preparation and verification

The CLI consumes the finished per-team staging work. It does not reopen the
source sound CPKs, repeat decoding, install files, or generate all pair banks:

```powershell
. D:/PESNX-Cache/use-cache.ps1
python -B tools/build_player_commentary_roster_pack.py --config local-debug/commentary-batch-v57/config.local.json --output local-debug/commentary-roster-pack-v59 --native-domain local-debug/commentary-native-fallback-v58/NATIVE-LABEL-DOMAIN.json
```

The same command with `--metadata-costs` performs exact UTF/AWB size arithmetic
for distinct catalog pairs, without reading source recordings or constructing
pair banks. `--check-team 196 258` instead executes the production C builder on
one complete home/away roster, then compares every parsed field, graph blob,
recording and unrelated top-level metadata with the independent Python oracle.
`--ensure-marker` adds or verifies the tiny marker without repeating staging or
bank validation. All generated data stays under the explicit ignored D output.

The generated catalog keeps all 10,433 audited raw native roster owners and
their BaseId/fingerprint/current-row identity claims. It preserves the 609
independently verified native owners and two accepted canaries. Of 1,020 newly
staged owners, 937 have eligible literal A1/B1 P0 calls (1,774 recordings), 68
remain native-label translation holds, and 15 further owners lack literal P0.
One of the sixteen total missing-P0 cases overlaps the translation group.
These are runtime policy holds, not invalidated staging results. No recording
is attached through a masked native ID or substituted donor.

## Runtime API and ownership

`player_commentary_types.h` defines the shared immutable metadata and result.

```c
int pc_bank_build(const void *accepted_v53, size_t bytes,
                  const PcBankCatalog *catalog,
                  const uint32_t *raw_native_ids, size_t count,
                  PcBankRead reader, void *context, PcBankResult *result);
void pc_bank_free(PcBankResult *result);
```

The selection is limited to eighty raw native owners and deduplicated before
construction. New owners receive only their own literal types 0 and 24; other
contexts are not renamed or aliased. Every cue name must encode that exact raw
owner and match its type. Cue strings and identity metadata point to the
compiled, immutable catalog; the result never returns temporary string memory.

The complete accepted v53 bank must match its compiled size and FNV. The
builder bounds-checks UTF descriptors, cells, strings and blobs, preserves
unaffected field types/constants and graph values, and appends only the
required cue/sequence/track/command/synth references. A numeric index remains
below 65,535. It merges the original embedded AWB with selected recordings;
an attempted overwrite of an existing embedded recording fails. Accepted
Yamal/Raphinha recordings therefore retain their exact bytes. Streaming AWB
references and unrelated metadata are conserved. Constant fields remain
constant unless a selected value actually differs.

The reader returns one owned recording allocation at a time, at most 2 MiB.
It can directly call `nx_asset_read_archive` with the independent commentary
archive. The builder does not load the whole archive. Failure clears the
result and frees every intermediate allocation. Success transfers one fresh
bank allocation to the caller. It must remain alive until its exact native
mount is successfully unmounted; failed unmount cannot authorize freeing it.
The caller also retains the immutable result header set with that mount.

The result bank and its hypothetical 48-byte replacement-delta envelope each
remain within 8 MiB. All builder-owned allocations, including the result while
intermediates are live and the AWB allocation's reserved padding, are capped at
18 MiB. The caller-owned accepted input is separate: the local input is
7,368,302 bytes. Four simultaneously retained mount slots would add their own
retained banks; this builder cap does not claim a global audio memory budget.

## Measured offline checks

The exact metadata sweep covers 77,421 distinct pairs from the active 394-team
catalog. No pair exceeds bank, delta, eighty-owner or index bounds. Same-team
selections contain a subset of the corresponding distinct-pair owner union.

| Corner | Actual C bank bytes | New cues | Peak builder-owned bytes |
| --- | ---: | ---: | ---: |
| Crystal Palace / Lazio, maximum bank | 7,739,602 | 60 | 15,093,093 |
| Tottenham / Crystal Palace, maximum appended/count | 7,727,726 | 62 | 15,069,357 |
| Real Sociedad / Athletic Bilbao | 7,697,486 | 48 | 15,008,693 |
| Barcelona / Manchester United | 7,507,046 | 26 | 14,627,453 |

The maximum hypothetical delta is 7,739,650 bytes. The maximum resulting cue
count is 64,076 (57 appended). Actual C reconstructions match the independent
Python graphs and preserve all 27 accepted embedded recordings byte for byte.
Private receipts live beside the pack and corner validation files. The
generated source archive is 10,607,433 bytes, including its tiny marker; this
is optional transport storage, not a mounted 10-MiB global bank.

Focused synthetic tests exercise actual C reconstruction, constant promotion,
graph preservation, deduplication, held-owner isolation, corrupt base/audio/
header, missing optional data, wrong owner/context/name/fingerprint, size and
selection limits, malformed UTF, marker idempotence, and the metadata formula
against actual C allocation accounting. These are desktop reconstruction and
full-decode proofs. Native mount, generic fallback, lifetime/rematch and device
listening acceptance belong to the wrapper integration and remain separate.
