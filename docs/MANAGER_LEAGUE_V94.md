# Manager League v94

The Switch local preview reuses Master League presentation and its native office
Game Plan. It is not connected to an account, shop or competition server.

## Registration and identity

The landing page shows the exact native unknown-club shield and a neutral name.
League and club selection are separate pages rendered with Master League rows.
Team name, User ID and password are separate inputs, followed directly by the
three-tab hub and first-visit introduction. The weekly schedule is a scrollable
seven-day preparation/match-day/result list with three large tiles visible.
Each Match Day shows individual opponent rows with crests, kickoff times and
home/away status, and opens that day's fixtures. Dates and kickoff times remain visible, with the device
timezone sampled at open. It does not display a month calendar. User ID is local profile metadata;
global uniqueness is not claimed. The password is masked, never serialized or
logged, and cleared after completion or leaving registration.

The immutable v1 fixture archive is retained. A separately checked v2 profile
binds canonical BaseIds, native/portrait policy and the current native fingerprint
provenance. The existing career catalog/save binding is unchanged. Starter squads
contain 18 actual catalog players with strength 60-69, two keepers and balanced
outfield groups. Initial starters require a verified real portrait. Native
ability details are shown by Game Plan; the profile never invents abilities from
simulation strength. Opponent badges and names use real club identities with
independent generated starter squads.

## Native Game Plan and storage

Strategy opens the same native squad initializer and Game Plan as Master League.
Both initial tactics are seeded to a valid 4-3-3 with the actual natural keeper.
The current canonical plan, roster order and preparation lineup are committed in
one Manager profile transaction; named presets use Manager-only A/B files.
Captain, takers and attacking assignments are remapped by saved player identity
when native MemberIds change. Normal per-team and career presets remain separate.
A failed write keeps the editor or selection open for retry.

The week lineup locks once Match Day starts. Returning to an earlier demo clock
state cannot rewrite the frozen lineup. Shop registration is closed during Match
Day. An editor already open at the deadline may save its club plan for later;
it cannot rewrite the locked competition lineup.

## Club selection packs

The latest confirmed rule is manual selection, superseding random draws:
Lite selects 2 of 5, Medium 4 of 6, Jumbo 5 of 8. Focused pack artwork pans within
its original atlas cell. Opening has a bounded 1.2-second reveal, followed by a
player selection grid and an explicit Confirm button below the panel. Selecting
a card shows a small circular tick; unselected cards have no empty checkbox.
Selecting a card does not debit or grant anything. Confirm requires the exact unique count,
an open window, sufficient balance and capacity, then saves debit, chosen players
and receipt together. Reopening a receipt does not charge or select again.

The three local offers cost 1000/2200/3000 points for UI testing. These are not
approved production prices. Pools are bound to the paired catalog and initial
owned roster. The collection is separate from the registered 25-player squad;
a reserve can be replaced from Collection before opening Game Plan. Replaced
players remain owned. Production offer rotation and receipt validation still
require the planned backend/API.

## Broadcast and verification

The saved match event tape drives continuous player and ball paths. Passes end
at a receiver, shots travel towards goal, and saves end at the keeper. Sampling
is deterministic for late joins, seeking and replay; no per-frame random offsets
or event-boundary teleports are used. Real player names follow the frozen lineup.
Results are still authored local simulation tapes, not native AI matches or a
validated tactics/strength model.

Live audio uses an optional, bounded native HCA bank with individually reviewed
generic recordings. Replay permits supporter and ball/reaction audio only.
Seeking, switching modes, leaving and stale publication stop owned commentary;
there is no historical speech backlog. See MANAGER_LEAGUE_AUDIO_V94.md. Host
checks verify ABI, decode and ownership; device audibility remains unconfirmed.

Host previews record the actual C presentation geometry and use the paired
local portraits/crests when --native-assets is selected. GIFs show the focus and
opening animations. They are not Switch captures. Controller input, keyboard,
Game Plan teardown, audible mixing and frame pacing require device acceptance.
The accelerated 3+3+1 week, sample overall reputation and absence of weekly server
settlement remain local-preview limitations.
