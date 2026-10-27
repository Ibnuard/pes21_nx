# Manager League four-digit PIN v97

New registration and login use User ID plus exactly four decimal digits. Team
name and User ID retain the Switch keyboard. The PIN uses a controller keypad
drawn with the shared Master League panels, focus frames and typography.
Entered digits are always masked; render views receive only the count.

Choose digits with the D-pad and A. X or the Delete key removes one digit; B
cancels and wipes the unfinished input. Confirm is reachable only after four
digits and never submits automatically. Creating a PIN requires a second entry
and explicit confirmation. Registration still has a separate Create Club
action. Login still has a separate Login action.

## Existing accounts

- A v95 profile with no credential record sets and confirms a PIN directly.
  Its club, players, points and fixtures are preserved.
- A v96 password credential remains version 1 and must be verified once before
  PIN setup. The migration page explains this exception; only that page opens
  a password keyboard. A session already authenticated against the old record
  may set the replacement PIN without entering the old password again.
- Cancelling migration clears its temporary authorization. A failed PIN write
  preserves the original password record, so migration can be retried.
- Corrupt, unreadable or directory credential paths remain closed. They never
  become an unprotected legacy-profile adoption route.

The same account path now writes credential version 2, with a new random
16-byte salt and PBKDF2-HMAC-SHA256 at 120,000 rounds. The persisted verifier
remains bound to the normalized User ID and account seed. No raw PIN, password
or session is written into account, profile or fixture files. Temporary input
is wiped after authentication, cancellation and logout.

Five unsuccessful login submissions start the existing 30-second cooldown;
leaving the popup or login page does not reset it. It is process-local. A
four-digit PIN is a convenience gate on this offline device, not server
authentication or protection against somebody replacing local files. Server
rate limiting, unique IDs, recovery and authoritative account state remain
backend work.

## Host verification

Production C handlers cover zero-prefixed PINs, exact format validation,
create/confirm mismatch, masked views, delete/cancel, incomplete Confirm focus,
wrong PIN, cooldown, logout/save preservation, migration verification,
migration cancellation, an already authenticated session, failed migration
writes, corrupt credential records and failed club registration saves.
SHA256 and PBKDF2 retain independent hashlib known-answer checks.

The actual C preview driver captures registration, PIN creation, masked entry,
confirmation, login and PIN login using native assets when available. These
are host layout previews; Switch input feel and timing still need a device
test. The source changes do not require deleting or resetting SaveData.
