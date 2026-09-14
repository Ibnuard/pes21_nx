# Serie A licensing and EF10 player assets

## Candidate

The detached Switch candidate is in `local-debug/serie-a-all-kits-v2`.
It is built on the previously generated English/Spanish kit candidate and has
not yet been promoted to `dist` or declared hardware-stable.

| File | Bytes | SHA-256 |
|---|---:|---|
| `pes21_nx.nro` | 51,134,669 | `4c1ac307975cd88cfb6e91ecf23b8e786ac0c94ab63b76f0c16ee8c817606172` |
| `patch.305030001.jp.nyan2021.pesam.obb` | 1,403,275,264 | `62158c3cd8c225ada761569a9b8253a626da09c57ca1911760c52eee50ba3612` |

Always test these two files as a pair. The NRO contains the matching explicit
OBB-size allowance and rebuilt badge atlas.

## Serie A result

- Football Life competition 10 contains 20 source clubs and all 20 passed the
  name, code, order, descriptor, and source-texture inventory checks.
- The PES21 Mobile database contains native slots for 19 of them. Those 19 now
  have official names/codes, custom-selector crests, native-surface crests,
  real-kit flags, and converted home/away/goalkeeper kits.
- This is 57 runtime kit variants and 19 updated native crest sets. Conversion
  output for Como's three variants is staged but is not packaged as runtime data.
- Como 1907 (`4219`) is the only pending club because there is no native
  `Team.bin` row, selector entry, roster/tactics slot, or native crest member.
  No unrelated physical slot was guessed or overwritten.
- Team.bin keeps 736 rows. Only 19 existing name/code rows and their real-kit
  flags change; the other team rows remain byte-identical to the selected base.

## EF10 player data and portraits

- The packaged `Player.bin` and `TacticsFormation.bin` are byte-identical to
  the validated all-team EF10 conversion: 2,596 unique converted players and
  the existing generated EF10 team rosters.
- The packaged `dt241_mobile_all.cpk` targets all 2,596 converted players.
  There are 2,232 original EF10 portraits and 364 transparent no-photo images
  for EF10 players whose container has no thumbnail; donor portraits do not leak.
- All 1,201 direct-ID transfers have an original EF10 portrait: zero use a
  blank or unrelated donor portrait. The remaining 1,031 real portraits belong
  to surrogate-ID transfers; 364 surrogate players use the transparent fallback.
- Cristiano Ronaldo is verified as direct mapping `4522 -> 4522`, is present in
  the generated EF10 roster data, and `common/player/4522.png` matches the
  normalized original EF10 portrait.

Portrait packaging does not itself prove 3D face or commentary playback. For a
direct ID such as Ronaldo, retaining ID 4522 preserves PES21's existing face and
commentary lookup path, while the merged EF10 Player.bin restores his converted
name/data. Final confirmation still requires an on-device Al Nassr match.

## Validation

- Focused automated suite: 20 passed.
- Final OBB validation confirms only dt120, dt200, dt240, and dt241 payloads
  changed; 20 unrelated outer payloads remain byte-identical.
- The runtime NRO production build completed without diagnostic logging.

Relevant generated reports:

- `local-debug/serie-a-license-pack/validation-report.json`
- `local-debug/serie-a-club-license-integration/report.json`
- `local-debug/serie-a-all-kits-v2/asset-report.json`
- `local-debug/serie-a-all-kits-v2/validation-report.json`
