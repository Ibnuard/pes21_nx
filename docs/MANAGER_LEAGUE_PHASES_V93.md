# Manager League hub phases v93

The three hub tabs remain Home, Squad and Competition. A separate weekly
state selects their content and available actions:

| State | Weekly days | Hub and market |
| --- | --- | --- |
| Pre-League | 1–3 | Prepare Your Club opens strategy; squad and Shop available |
| Match Day | 4–6 | Next Broadcast opens the match centre; Shop purchases closed |
| Result | 7 | Season Results opens the final table; champion, replays and Shop available |

Production uses the requested three days of registration/preparation, three
days of matches and one results day. The offline dummy accelerates each day
to nine minutes, retaining the 180-second matches and four-minute rounds.
Seven rounds span the three match days as 3/2/2 kickoff groups. New joins
receive three accelerated preparation days before the first broadcast.
The first weekly boundary is rounded to the next device-clock minute.
This is a demonstration clock, not a server or production weekly scheduler.

Hub X cycles through Pre-League, live minute 30, half time, first full time,
the second match day, the third match day and Result. These explicit test
controls change only the saved dummy clock offset. They never resimulate
matches, change kickoff timestamps or award points. Moving the test clock
backwards also moves the displayed phase backwards.

The phase projection uses the earliest kickoff and latest broadcast end
across all 21 saved fixtures. Boundaries are half-open. A postponed fixture
keeps Match Day open until it finishes; Result cannot publish a champion
from incomplete future games. Shop reopens at Result, not at the first
full-time whistle or between rounds. The phase is recomputed when checking
a purchase, so an already-open Shop cannot bypass the cutoff.

The dedicated v1 dummy save schema, 21 fixture tapes, balances and native
saves are unchanged. Existing v91/v92 archives keep their original kickoff
times and gain the phase projection without migration or reroll. Result
remains available with that archive; automatic next-week enrollment and
settlement are not implemented. Sample ranking projection is separate from
the wallet, and no reward payout is minted by entering Result.

Tests check every day boundary and the preceding millisecond, phase-based
Shop admission, phase-dependent Home navigation, postponed/unsorted fixture
times, immutable rendering, persistence and the existing live/replay rules.
The actual C renderer previews all three phases and all three match days.
Switch playback, controller interaction and performance need device testing.

The serial production Switch build and its ready-copy ZIP are verified under
`D:/PESNX-Cache/Deliveries/FootballNX27-v93-MANAGER-LEAGUE-PHASES-SIAP-COPY`.
Only the NRO changes from v92; all 17 other runtime payloads are byte-identical,
including the 1,638 heads and 436 existing skin corrections. ELF/NRO segments,
24 CPKs through the overlay and actual native C validator, ZIP CRC and all
member hashes pass. Focused tests pass 4 tests and 36 preview subtests.
The existing unrelated League save-slot label assertion remains documented
in the local baseline limitation report. No active runtime is installed.
