# Manager currency, profiles and twice-weekly leagues v98

NX Cash names the spendable wallet throughout Manager League. The wallet is
shown at the right of the header, including the shop, sealed pack, opening,
selection, receipt, club pages, native editable Game Plan and dot broadcast.
The hub's lower Club Profile tile instead shows the actual League Point from
completed fixtures. Reputation remains a separate ranking value.

All Manager notices use the existing one-action informational popup. A notice
owns controller input until A or B acknowledges it; that press cannot activate
the page behind it. Introductory and logout/next-league errors stay in their
existing modal. PIN errors appear above the keypad. No Manager status line is
drawn at the bottom left. This does not replace unrelated native game dialogs
or Master League's existing top notification banner.

## Club navigation

Club Profile opens a club overview with its name, crest, power, mean starting
rating, league position and reputation. Its scrollable menu opens registered
players, league standings, club fixtures/replays, overall ranking, Game Plan
and league rewards. Other-club links from News, the table, ranking and club
list open this overview. My Squad remains a direct squad shortcut.

An opponent's Game Plan uses a centered one-club pitch with portraits and a
reserve list. It has no edit transactions or mutation controls, no visible
"View Only" label and no four action buttons. The centered message reads
"USING THE LATEST SAVED TEAM DATA". These local
opponent entries retain their registered default 4-3-3; a future connected API
must supply each actual opponent's saved plan. Opening the view does not read
an original-club donor lineup or change the saved local club. The own-club
Game Plan opens the existing native editor and returns to its opening page.

## Calendar and entry cash

New seasons follow the agreed fixed Asia/Jakarta calendar:

| Day | Phase |
| --- | --- |
| Monday | League A preparation |
| Tuesday / Wednesday | League A matches |
| Thursday | League B preparation |
| Friday / Saturday | League B matches |
| Sunday | Day off and overview |

Each seven-team league retains 21 games across seven rounds. The first match
day has four round slots at 12:00, 15:00, 18:00 and 20:00 WIB; the second has
three at 12:00, 15:00 and 18:00. Games last two real five-minute halves. A club
cannot overlap games. Results become available after the final broadcast;
Sunday remains an overview day, rather than an additional match day.

Joining after a preparation day schedules the next preparation window.
Joining a successor cannot schedule the same window again. Existing saved
seasons and archived replays retain their exact old kickoff times and tapes;
they switch to the new calendar only when their successor is joined. The
scrolling weekly schedule shows dates, times, opponents and Live badges, and
can fit four own-club games on one day. Other-cycle opponents are not invented
before that league is joined. Archived leagues remain in Match Centre.

New accounts start with 5,000 NX Cash. Every league entry adds 1,500, including
the first entry (6,500 total before purchases). Once the final broadcast ends,
first place earns an additional 5,000, second 4,000 and third 3,000. Other
participants keep their entry bonus without an additional finishing award.
The prize uses the completed table's points, goal difference and goals scored.

Current-season entry and settlement flags use reserved high bits of the
existing save field; the low three legacy purchase bits are unchanged. A full
before/after save/profile journal, `manager-league-wallet-v98.dat`, is verified
before either active record changes. Recovery accepts only the corresponding
account pair; a corrupt or stale journal preserves files and blocks writes.
It cannot undo a later purchase. Roster locking is normalized before the
journal is sealed. Even a zero-prize finish is marked settled, so retrying,
reloading or recovering cannot issue the award twice.

The completed league is settled and archived before joining its successor.
The existing season-transition journal owns the successor's 1,500 entry bonus.
An existing current league without an entry marker receives its participation
bonus once on login; archived old leagues do not receive retrospective cash.
Existing receipts, players and pack purchase limits persist. Save structure
sizes remain unchanged, but older binaries cannot read the new flags/calendar;
retain the previous binary's matching saves when rolling back.

The present Manager implementation is still a local fixture preview, with
local credentials and saves. It does not implement a live authoritative
backend. Its `MANAGER_LEAGUE_DEV_CLOCK` compile option defaults to 1 for this
preview (Makefile and standalone host builds). Y advances to the next kickoff
or the end of a current live fixture. At Result Y opens Next Week instead;
after joining, Y again advances preview time. A connected build must set the
option to 0. X remains Logout in every hub phase.

## Verification boundary

Focused host checks exercise fixed independent calendar timestamps, both
weekly cycles, non-overlapping games, exact podium awards, once-only grants,
interrupted entry/payout/rollover recovery, stale/corrupt journals, unchanged
old tapes, PIN/login flows, popup input consumption,
read-only opponent views, and both dev-clock settings. Actual C renderer
captures cover the new profile, history, Game Plan, rewards and notice pages.
These are host previews, not Switch screenshots or online-service acceptance.

Pitch changes and Signal stand repair are documented separately in
[pitch alignment](STADIUM_PITCH_ALIGNMENT_V98.md) and
[Signal surfaces](STADIUM_SIGNAL_SURFACES_V98.md). No COM-versus-COM work is
included.
