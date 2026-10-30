# Registration, COM ownership, corner helper and menu playlist v120

The subsequent Switch test reported severe stuttering after enabling Custom
Playlist. The earlier host checks below did not model native mute attenuation.
See [the v121 correction and remaining hardware limit](CUSTOM_PLAYLIST_V121.md).

Online registration now projects its league/club choices into the existing
Master League settings drawer renderer (`ml_ui_primary`). Its list rows,
crests, focus frame, scrollbar and panel geometry are shared with the active
career setup, rather than a second approximation of that picker. The left
panel contains only the two relevant registration fields. Online L/R moves
five entries; B returns from club to league, then registration, preserving the
selection. Returning from account details restores the selected club.

The paired selector's `NATIONAL <region>` categories are excluded. The same
catalog-membership check guards account submission, so an obsolete national
selection cannot bypass the filter. Team numbers are not used to infer club
identity. This changes new account selection, not existing accounts or saves.

## Native gameplay corrections

- [COM ownership](COM_DEFENCE_V120.md): finalize one-player AWAY cursors with
  both pad `-1` and the CPU flag. Native predicate emulation reproduced the
  stale-human condition and verified that AWAY becomes CPU while HOME remains
  human. This fixes a concrete cause consistent with an idle selected defender;
  it is not a claim that every passive-defending situation has one cause.
- [Corner helper](CORNER_HELPER_V120.md): rendering, HID handling and queued
  native actions share the inverse nameplate-readiness boundary. Starting live
  play closes the helper and clears pending input, including a kick that begins
  between selection and command consumption. The cosmetic Show Nameplate option
  does not change gameplay eligibility.

## Custom Playlist

Initial Settings now has **CUSTOM PLAYLIST**, default OFF and persisted in
`pes21_nx.cfg`. Put user-supplied `.mp3` files directly in
`sdmc:/switch/pes21_nx/playlist/`. The first 128 valid filenames play in sorted,
case-insensitive order and loop. Switch OFF then ON to rescan. ZL opens the
playlist instructions; B returns to Settings. No audio files are bundled.

Playback is menu-only as requested. The native owner excludes launch
transitions, live gameplay, match pause/results and Manager broadcasts. The
worker pauses consumption outside menus; returning resumes the playlist.
Output also requires a fresh menu heartbeat, so stale UI state cannot leave
the stream playing indefinitely. OFF, missing/empty folders, unsupported or
invalid files, failed decoder initialization and missing native category APIs
fall back to native menu music.

A bounded worker decodes MP3 into a two-second 48 kHz stereo PCM16 ring. The
existing AAudio output mixes it after native PCM; the callback does no file
I/O, allocation, decoding or blocking lock. A 10 ms attack avoids abrupt resume.
Only `OptVol_Menu_Music` is muted, and only after playable PCM is ready and the
mute is verified. Its prior mute state is restored on exit or fallback.
Custom gain follows the native menu music category and default gain. Effects,
commentary and match audio keep their existing paths. The supported native
ELF exports and category mapping were inspected locally; CRI's
[category API reference](https://game.criware.jp/manual/native/adx2_en/latest/group__ATOMEXLIB__CATEGORY.html)
documents the mute/volume interfaces used by the adapter.

## Verification

- Online registration tests enumerate every category and team, reject national
  submission, and cover page controls and back navigation. Existing purchase,
  owned-player Game Plan, session and hub-back regressions also pass.
- The focused online/dummy/playlist/COM batch passed 83 tests and 135 subtests;
  the Windows real-libmpg123 integration is unavailable there and was executed
  separately on Linux instead.
- A generated 44.1 kHz mono MP3 passed through the production worker and real
  Linux libmpg123 to nonzero 48 kHz stereo output. Menu exit stopped mixing.
  Stub tests also exercise bad files, generation changes, stale heartbeat,
  gain/saturation, native mute ownership, audio restart and persisted settings.
- The frontend/audio batch passed 25 tests and 335 subtests, including three
  playlist adapter tests also covered in the focused batch. Production-renderer
  previews of registration, Settings and playlist instructions were inspected.
- Corner/HUD regression passed 85 tests; one older optional native-binary
  fixture was unavailable. The public-tree audit passed for 1,572 files.
  The broader legacy `test_native_gamepad_lab.py` also run during investigation
  has 12 failing whole-source text assertions in this checkout (52 passed).
  It is not presented as a passing suite; focused executed cursor routing and
  native predicate checks provide the ownership evidence described above.
  Final build evidence is under ignored `local-debug/manager-v120/`.

The build retains the v119 paired runtime assets (`e861c583ec78e9ae`, dummy
patch OBB 53,248 bytes), with release diagnostics disabled. This is a client
update; no backend deployment, database migration, roster update or save reset
is required. Host tests, native predicate emulation and NRO compilation do not
replace physical Switch acceptance of COM behavior, corner timing and audio.

Release build completed successfully: NRO 86,844,319 bytes, SHA-256
`35a15853cce248feaa5fe40a828d70e638e07f894b12473b524891a37174be98`,
build ID `ad1ece061cc1f65a207246b5822618fcffdc77f0`. All 249 pinned source/build
files stayed unchanged during compilation; all nine paired inputs equal v119.
Three ELF load segments and the embedded icon match the NRO byte-for-byte.
The delivery ZIP was reopened and every entry checksum verified. It contains
the NRO, installation notes, verification metadata and a playlist README only.
