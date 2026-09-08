# PESDB club-membership cleanup

`tools/clean_pes21_memberships.py` derives current club ownership exclusively
from PESDB eFootball Authentic rosters. PES21 is used only for the binary
`PlayerAssignment.bin` schema and physical player/team slots; EF10 is not a
player-membership authority in this release path.

The packaged candidate replaces every integrated physical club roster with
the exact PESDB order and shirt numbers, removes stale membership from old
clubs, and preserves national-team membership. Release generation fails if a
PESDB player is unresolved, maps to more than one physical slot, belongs to
multiple current clubs, or would leave an invalid roster.

Current candidate result:

- 53 integrated PESDB clubs and 1 held-back club.
- 1,630 current PESDB memberships inserted.
- 1,913 stale club memberships removed from 221 clubs.
- 154 national-team memberships preserved.
- Zero unresolved PESDB memberships and zero duplicate current club owners.

The runtime roster table carries the same PESDB physical-slot ownership map.
When an old fallback club is selected, any slot now owned by another PESDB
club is omitted; national teams are explicitly exempt from this filter.
