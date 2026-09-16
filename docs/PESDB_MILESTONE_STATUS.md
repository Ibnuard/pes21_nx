# PESDB milestone status

Player identity and gameplay data in this candidate are sourced only from
`https://pesdb.net/efootball` Authentic mode. PES21 supplies the binary schema
and reusable physical slots; EF10 supplies team/league identity and visual
assets. Missing or unverified PESDB fields fail closed instead of falling back
to PES21 or EF10 player values.

| Milestone | State | Current result |
|---|---|---|
| Famous EF10 teams/leagues missing from PES21 | Candidate ready | 10 external teams are selectable: Inter Miami plus nine detachable famous-team additions. Al-Ahli `17733` remains held back because its physical/kit route is not verified. |
| Current player data from PESDB eFootball | Candidate ready for hardware test | 3,231/3,231 mapped players received PESDB name, registered position, and all 25 verified gameplay abilities. OVR is calculated by the game from those abilities. |
| Global legacy club-membership cleanup | Candidate ready for hardware test | 1,913 stale club memberships were removed from the packaged database. Runtime ownership additionally filters 117 stale fallback memberships across 89 clubs while preserving national-team membership. |

## Current release evidence

- Selector catalog: 480 teams in 33 categories; 464 shared, 6 legacy, and 10
  external PESDB-rostered teams.
- PESDB runtime rosters: 53 clubs, 1,630 current memberships, 100% mapped,
  zero unresolved memberships, and zero cross-club duplicate PESDB targets.
- PESDB player patch: 3,231 applied, zero skipped, and 100% verified coverage
  for the fields currently proven writable in PES21 Mobile.
- Detachable v6 data candidate content ID: `ab9716eaac05bf0b`; only `dt120`,
  `dt200`, and `dt240` payloads differ from the stable base.
- The hardware v6 package layers the detached FC Barcelona/Real Madrid
  licensing and kit canary over those three CPKs. Its OBB SHA-256 is
  `17fdefc5e9004eb74724a5b31fa6798d6f149da42e59c661480ea59ad905621d`.
- Stable `dist/` remains untouched until hardware validation passes.

## Deliberate limits

PESDB exposes more data than the currently proven PES21 Mobile layout can
safely encode. Player skills, AI styles, stronger foot, form, injury
resistance, body fields, height/weight, and nationality remain report-only.
They are not copied from PES21 or EF10 and will be enabled only after their
packed offsets are verified. Direct OVR is also not written because the game
derives it from the verified ability values.
