# EF10 famous-team imports

The curated batch in `data/ef10_famous_team_imports.json` starts with Borussia
Dortmund, selected Saudi/Asian clubs, and major Liga MX clubs missing from the
PES21 selector. Team identity, roster membership, tactics, shirt numbers, and
source assets come from EF10. Current player values must come from
`pesdb.net/efootball/authentic` through the PESDB snapshot pipeline.

`tools/plan_ef10_famous_team_imports.py` is deliberately fail-closed. It emits
an ignored `local-debug/` plan and does not change runtime source, the team
catalog, NRO, OBB, or `dist/`. Every team requires a unique physical PES21
slot plus an EF10 badge and complete uniform definitions before detachable
integration can begin.

The plan also requires a reviewed EF10-to-PESDB identity for every roster
member and a complete `authentic` PESDB eFootball snapshot. Missing or
ambiguous players block that team; PES21 names, ratings, abilities, and skills
are never accepted as fallback data.
