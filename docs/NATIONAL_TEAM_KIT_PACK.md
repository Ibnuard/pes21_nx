# All-region national-team kit pack

## Candidate

The detached Switch candidate is in `local-debug/national-team-all-kits-v2`.
It is layered on the Serie A candidate and must be tested as an NRO/OBB pair.

| File | Bytes | SHA-256 |
|---|---:|---|
| `pes21_nx.nro` | 51,134,669 | `4fc456c25eb5178f88436d93a51e70a7ff550d69c9c2b035473be690749e52aa` |
| `patch.305030001.jp.nyan2021.pesam.obb` | 1,410,308,096 | `847dd543dc51117de640622e42e9156bfb411ea9d63e67aed22db1f90efecf33` |

## Coverage

The generated manifest follows every national team exposed by the custom
exhibition selector. No physical team ID is aliased or replaced.

| Region | Teams |
|---|---:|
| Europe | 42 |
| Africa | 14 |
| North America | 6 |
| South America | 10 |
| Asia / Oceania | 17 |
| **Total** | **89** |

All 89 teams have converted home, away, and first goalkeeper kits: 267 kit
variants in total. The conversion completed without a missing native team slot,
descriptor, or source texture. Existing Team.bin rows and rosters are preserved;
only the real-kit flags are normalized.

## Validation

- The final OBB replaces only `dt120_mobile_all.cpk` and
  `dt200_mobile_all.cpk`; the other 22 outer members are byte-identical.
- The focused automated suite passes 14 tests.
- The production NRO was built without diagnostic logging and contains the
  explicit 1,410,308,096-byte OBB contract.
- Final visual confirmation of every region still requires an on-device pass.

Relevant local reports:

- `local-debug/national-team-all-kits-v2/asset-report.json`
- `local-debug/national-team-all-kits-v2/validation-report.json`
