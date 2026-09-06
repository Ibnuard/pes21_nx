# eFootball 10 Legacy Player Cleanup

This generated manifest removes stale club membership only when the same
stable player ID belongs to an active EF10 club. National-team membership
is deliberately preserved. Same-name/different-ID matches remain review-only
because unrelated players can share a display name.

## Result

- Cleanup content ID: `b6560bb15cddf9c3`
- Active EF10 rosters: 99
- Active EF10 clubs: 43
- Fallback clubs checked: 338
- Affected fallback clubs: 136
- Stale club memberships removed: 299
- Smallest cleaned roster: 19 players
- Name-only candidates held for review: 2

## Retained legacy teams affected

| Team | Removed | Players after cleanup |
|---|---:|---:|
| BORDEAUX | 2 | 25 |
| FC BAYERN MUNCHEN | 5 | 31 |
| OLYMPIAKOS PIRAEUS | 1 | 34 |
| DYNAMO KYIV | 1 | 36 |
| SPARTAK MOSKVA | 1 | 35 |

## Expected transfer sentinel

- PASS: player ID `40002` is removed from FC Bayern Munchen and retained by FC Barcelona.

The cleanup is consumed by the generated PES21 fallback roster table.
The team catalog generator refreshes this manifest and the fallback table
together whenever the active EF10 roster set changes.

## Name-only review queue

These rows match normalized name, nationality, and registered position,
but use different player IDs. They are not removed without an explicit
identity confirmation.

| Old club | PES21 ID | Name key | EF10 ID | Candidate club |
|---|---:|---|---:|---|
| GOIAS V | 108850 | MATHEUS | 103064 | AFC AJAX |
| ALBACETE BN | 102743 | FRAN GARCIA | 127571 | MADRID CHAMARTIN B |
