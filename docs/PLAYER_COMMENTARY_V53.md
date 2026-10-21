# Yamal and Raphinha commentary canary v53

The user reports incorrect or missing player calls after player identities were
migrated into PES21 slots. The first candidate covers Lamine Yamal and Raphinha
only. Trophy playback remains unaccepted and is deferred; the v52 runtime's
ceremony implementation is retained without claiming it works on Switch.

## Identity and native lookup

The persistent registry identifies Raphinha as BaseId/native `110644`, with
fingerprint `a127e8032d5e1bdff42a`, and Lamine Yamal as BaseId/native `162114`,
with fingerprint `a7ded89f5960baa40983`. The accepted runtime-pair roster
`e861c583ec78e9ae` uses those same IDs for Barcelona. Staging checks the live
candidate Player.bin rows against the registry/state fingerprints and checks
the FL26 records' name, nationality, preferred foot, height and age. A numeric
ID alone does not establish the identity.

The audited Mobile player-label creator reads the native PlayerId, extracts
the pure player ID and builds the corresponding cue name. Its same-person
helper is a no-op on the compatible library. Controlled native calls confirm
that these two IDs survive that path. No label hook or global player-ID change
is needed for this candidate. Legacy slot `8957` also has a Yamal name in the
owned Nyan base; that is not permission to attach these recordings to that
slot, and this candidate does not do so.

These findings use ordinary local ELF inspection and controlled native
probes. The REA native providers were unavailable (Ghidra/IDA not configured,
Hopper unsupported on this host); they are not REA runtime Evidence.

## Bank and decoder changes

Mobile's English `10_PLAYER.acb` has 64,000 cues and a sequence/track/synth/wave
graph. FL26 uses a different direct-wave cue schema, so copying its whole bank
is unsuitable. The stager rebuilds the Mobile UTF schema and embeds only the
27 selected FL26 HCA recordings in a memory AWB. Eight exact Raphinha cue names
are replaced and nineteen cues are added, including Yamal. The original
streaming AWB is untouched. All 63,992 unaffected original cue graphs and
waveform records are preserved. Two Mobile-only Raphinha variants remain,
after original PES21 data independently establishes their owner.

The source FL26 HCA recordings are plaintext. Mobile normally installs a cipher
table before decoding every HCA header, including plaintext headers. The
existing Indonesia correction is extended with a separate allowlist of the
27 audited player-header fingerprints, enabled only while an accepted player
bank is mounted. It clears only that decoder instance's inherited table;
unrecognized, truncated and encrypted headers retain native handling. The
global cipher and unrelated team audio are not changed.

The optional delta is accepted only for its exact pinned base/result/patch
identities and runtime-pair ID. The existing team delta remains capped at
1 MiB. A separate 8 MiB player-delta limit accommodates relocated UTF tables;
the reconstructed bank is also capped at 8 MiB. Each player mount owns a fresh
7,368,302-byte buffer until native unmount succeeds. Four bounded slots support
overlapping loads. Missing/corrupt data, exhausted slots or failed patched
mounts use the original bank. Temporary delta memory is freed after loading.
All this work occurs at sound-bank load/unload, with no player/render work per
gameplay frame. This is not a hardware frame-rate or playback guarantee.

## Reproduction and tests

Use owned local inputs and a fresh ignored output directory:

```powershell
python -B tools/stage_player_commentary.py `
  --mobile-cpk dist/pes21_nx/Download/dt510_mobile_eng_all.cpk `
  --fl26-cpk '<owned-FL26>/Data/dt41_eng_all.cpk' `
  --fl26-database-cpk '<owned-FL26>/download/data_s2526c.cpk' `
  --active-database-cpk '<accepted-runtime>/LooseCpk/dt200_mobile_all.cpk' `
  --identity-state '<accepted-candidate>/identity-state.json' `
  --original-player-table '<owned-original>/tables/Player.bin' `
  --policy-header --output local-debug/player-commentary-reproduction
```

The database archive path must be the actual audited FL26 database. The
stager rejects mismatched identities, biographies, cue graphs and unsupported
source waveforms. `--policy-header` emits compatibility metadata, never audio
or keys; review/regenerate the compiled catalog when changing the candidate.
Copy the generated delta to `Commentary/players-v53.nxcp` beside the matching
NRO. Do not replace sound CPKs, player tables or saves.

The final 43-test run passed: synthetic staging/bounds, owned deterministic
regeneration and cue preservation, actual wrapper mount/rematch/failure paths,
all header splits and byte corruptions, player/team isolation, native HCA
packet checks and referee asset audit. All 27 recordings decode through the
installed FFmpeg. Native packet checks sample first/middle/last frames; they
do not verify PCM synthesis or sound-device output. Switch playback remains
pending.
The separate startup/configuration/journal regressions passed 39 tests after
the executing revision was advanced to v53.

## Device check

Copy the complete supplied `switch` directory into the SD root. Play Barcelona
with English commentary and give Yamal and Raphinha possession, passes, shots
and goals. Native context/variation selection still controls when a call is
heard. Check an unrelated team, rematch and Indonesia commentary as well.
The scene journal records whether the v53 player bank mounted or the original
bank was retained. Keep that journal if either name is wrong, silent or
distorted. Roll back by restoring the previous NRO and removing the optional
`Commentary/players-v53.nxcp` file.

## Verified local delivery

The serial isolated build succeeded with the accepted v52 build inputs and
runtime pair `e861c583ec78e9ae`. Renderer, quality, stadium, referee and trophy
result sources are byte-identical to v52; only audio integration and executing
revision reporting change. The NRO matches the ELF load segments and contains
build ID `102004c6dc6686e0a4a993ab273fc4666a5bad77` and the audited player
header allowlist. All 157 build-source identities and selected inputs were
checked again during packaging.

The ready-copy folder is
`local-debug/player-commentary-v53/FootballNX-v53-COMMENTARY-SIAP-COPY`, with
the same-named ZIP beside it. Its three files are the instructions, NRO and
optional player delta. Both loose files and ZIP contents/CRCs were verified.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| NRO | 83,903,391 | `ec49ff301ad95dc49ba3f7c889d25cec392141bd588965fb326a2aac21e33398` |
| Player delta | 7,368,350 | `13a373074c3d93f122440e1687a3a3989e0bbca587e21dc173ace796e9d3368e` |
| SD-root ZIP | 48,468,138 | `805d13cd506939609d56cda5e0323c6357ce52f9a4902b18d7faa7555e6c113d` |

The public-tree audit and whitespace check passed. No game inputs, extracted
banks, generated delta or NRO is part of the public source tree. The active
runtime was not replaced here, and device acceptance is pending.
