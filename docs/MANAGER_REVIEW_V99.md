# Manager watch, paid packs and honours v99

This source review follows the v98 device feedback. No NRO is implied by a
passing host preview; the next build remains a separate user-approved step.

## Watch and match navigation

NX Cash is removed from the watch broadcast. Y opens a scrolling Touchline
popup with elapsed tape events, game timestamps, the recorded player or pass
recipient, substitution off/on names, team identity and the running score at
each goal. Future events are never disclosed. Live playback and audio continue
behind the popup; B/Y closes only the popup. L/R pages its event list.

Newly generated tapes retain the same 600-second duration, 99 events and
half-time boundary. Passes now record their actual active receiver in `other`;
possession is retained across passing sequences, shots use attackers, fouls
are attributed to defenders, and goals/saves/offside lead to the appropriate
restart team. The dot sampler uses that receiver and the carrier's existing
lane. Existing recordings with zero pass receivers retain their legacy
sampling fallback; they are not rewritten. This remains a local fixture tape,
not an attribute-driven football engine or synchronized COM-versus-COM match.

Match Centre has three ordered sections: Live, Scheduled and Match Ended.
Entry defaults to Live when available, otherwise Scheduled, otherwise ended.
L/R changes section, X/Y browses archived leagues, and the two-column cards
retain dates, kickoff times, badges and scores. Upcoming games are chronological;
finished games are newest first. The scrolling weekday schedule remains
separate and covers the actual Monday-to-Sunday calendar.

NX Cash on other Manager headers is aligned to the right with the same
20-per-thousand inset as the left crest. Manager notices remain modal; no
bottom-left status/debug line is drawn. The native Game Plan header already
uses right-aligned wallet text.

## Ranking and league champions

The duplicated Competition shortcut is replaced by League Champions. League
Standings describe the current league; Overall Rank describes the ranking
period. Two leagues run per real week, while Overall Rank resets every two
real weeks, Monday at 00:00 WIB. The common calendar anchor is 26 October 2026;
the following boundaries are 9 and 23 November. In this development fixture,
the injected preview clock can also advance across those boundaries.

Arbitrary seeded reputation is removed. Each completed league contributes
the existing 700/600/500/400/300/200/100 RP according to final position. Only
leagues whose final broadcast ends in the current ranking window contribute;
archives and the completed current league are counted once. The next reset
date is shown on Overall Rank. The permanent honours list reads each saved
league's champion, crest, name, final points, results and goals, independently
of the current RP window. Missing archives are reported rather than replaced
by invented winners. Repeated draws use a cached projection rather than
repeated SD-card archive scans. A production service must own these records.

## Pay before opening; recover until selection is complete

The user's latest purchase instruction supersedes the earlier selection-time
debit rule. Open Pack first shows a payment confirmation. Confirm deducts NX
Cash once, then starts the animation. Back is unavailable during the paid
opening/selection; players are granted only after choosing the required subset
and explicitly confirming it. Finishing selection never charges again, even
if Match Day begins in the meantime. A pending paid pack must be completed
before joining the next league.

The new `manager-league-pack-v99.dat` stores immutable canonical pool IDs,
selection progress, account/catalog binding and complete before/after pairs.
It has prepared-debit, paid and prepared-grant phases. Each transition is
checksummed, written to a temporary file, re-read and atomically promoted
before profile changes. Interrupted writes recover the same debit/grant;
paid selection can survive a later legitimate league reward without restoring
an old wallet. Login/shop entry resumes the pending player selection. Invalid
or stale transaction data blocks writes and preserves the wallet/collection.

Reserved high bits of the existing profile receipt mask identify the single
paid pending offer; low bits still identify completed receipts. Profile/save
structure sizes and old completed receipts remain unchanged. Earlier NROs do
not understand the new pending bits or pass receivers; use matching older
saves for rollback. No save deletion or reset is required for this upgrade.

Focused tests exercise payment cancellation, pre-journal failure, interrupted
debit and grant in a new process, interrupted journal rotation, corrupt paid
journals without wallet writes, persisted subset selection, rewards while a
pack is pending, no second debit, period boundaries, persistent honours, match
group ordering, elapsed-only touchline detail and linked pass receivers.

## Audio and stadium evidence

The supplied v98 log identifies a private WAVE pool rejection before playback.
The revised Manager audio uses the unchanged reviewed PCM bank and the existing
working AudioOut submission buffer; see [audio v99](MANAGER_LEAGUE_AUDIO_V99.md).
The custom trophy song is raised another 3 dB with unchanged native routing;
see [trophy v99](TROPHY_AUDIO_GAIN_V99.md). Host sample/decoder checks do not
replace listening on Switch. Signal Iduna's remaining stair portal repair has
separate [source/cooked geometry evidence](STADIUM_SIGNAL_STAIRS_V99.md).
