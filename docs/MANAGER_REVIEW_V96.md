# Manager League device review v96

Source review and host previews; no v96 Switch build or hardware acceptance yet.
The v95 checkpoint remains commit `8995a9c` and its delivery is unchanged.

## Device feedback addressed

- Successful saves no longer publish persistent diagnostic text. The broadcast
  hides stale page notices and the optional FPS overlay; Local Preview and
  Demo Clock wording/actions are removed from Manager pages and tutorials.
- Competition's five visible cards now open their corresponding destination,
  including both Overall Ranking cards and Match Centre. Controller tests
  activate every card and verify its return focus.
- Pack selection uses a centered count subtitle and native-role color badges.
  Disabled Confirm cannot receive focus; an incomplete last row retains a
  visible player cursor. Moving down from a missing grid cell selects the
  nearest player rather than losing the cursor.
- Weekly Schedule and Match Centre show an explicit red LIVE badge, retaining
  dates, times and separate fixtures for multiple games on one date.
- New matches have two real five-minute halves and a richer deterministic
  football action tape. Old fixtures retain their original duration and scores.
  Result provides a confirmed Next Week action; archived weeks retain their
  original roster and can be selected in Match Centre with L/R. See
  [timing and archive handling](MANAGER_TIMING_ARCHIVE_V96.md).
- Old Trafford uses measured native paint anchors and 20 near-uniform strips.
  Its six-yard and penalty fronts no longer rely on ideal regulation positions;
  the six other supported stadium patterns are preserved. See
  [pitch alignment evidence](STADIUM_PITCH_ALIGNMENT_V96.md).

## Local account gate

The landing page exposes Login and Register. A new club registers once; the hub
offers X Logout with Cancel selected initially. Logout clears raw credentials,
pending editor/action state and the active replay view without deleting the
club or granting another starting balance. Reopening the application requires
login; leaving the mode within an authenticated process retains that session.

Local credentials are bound to the account seed and canonical case-insensitive
User ID, with a random 16-byte salt and PBKDF2-HMAC-SHA256 at 120,000 rounds.
The credential record stores a verifier, never the raw password. Inputs and
temporary hashes are wiped. SHA256 boundary vectors and PBKDF2 outputs are
checked against Python's independent hashlib implementation. Wrong-password,
legacy adoption, logout, corrupted credentials, credential directories and
registration-save failures are exercised through production C handlers.

The earlier prototype never stored a password. When neither credential file
exists, its owner must set and confirm a local password before entering the
existing club. An unreadable, corrupt or indeterminate credential path is not
treated as absence and cannot silently open that adoption route. A failed
registration save restores the pre-registration league state.

This is an offline device gate, not server authentication, encrypted save data
or tamper-proof economy. A device owner who can replace local files is outside
its security boundary. There is one active local club, so global User ID
uniqueness and multiple remote accounts are not established by this prototype.

## Audio and genuine 3D watching

The supplied v95 log shows admitted audio requests but retired long-lived
handles before 100 ms. Thus the audible menu music was not evidence of working
Manager commentary. v96 uses a bounded dedicated native WAVE pool and a PCM16
bank made from the same 13 individually reviewed recordings. Native codec
probes establish sample integrity and format compatibility, not speaker output.
The global menu playlist is preserved. Listening, balance and native voice
allocation still require Switch testing. Details:
[PCM candidate and evidence](MANAGER_LEAGUE_AUDIO_V96.md).

COM-versus-COM 3D is a plausible separate native prototype. Existing control
ownership must first be changed and verified for both sides. The native online
Watching path depends on sessions and sync; starting a native game late cannot
reconstruct the precomputed fixture state. No experimental watch hook is enabled.
[Feasibility and remaining proof](MANAGER_NATIVE_WATCH_FEASIBILITY_V96.md).

## Remaining online work

- Backend authentication, account recovery and a global unique-ID constraint.
- Authoritative wallet/purchase/reward transactions, idempotent requests and
  durable ranking settlement. Current overall reputation and offers remain
  offline fixtures; Next Week does not claim or reset rewards/offer receipts.
- Enrollment/group sizing above seven teams and a real server calendar.
- API-supplied packs and other managers' purchase journals.
- A simulator that derives outcomes from players and strategy, or a validated
  native capture/playback service for consistent 3D live entry and replay.

These are explicit implementation gaps. Client checksums and a successful
local login must never be accepted as server authority for them.
