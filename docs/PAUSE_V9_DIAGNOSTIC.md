# Pause v9 diagnostic candidate

Not a stable checkpoint. Hardware verification required; no emulator run.
Uses the existing scoreboard-square-v2 OBB unchanged (1,401,395,200 bytes).

Changes:
- Run the concrete MyClubSquadEdit hook after native Update completes, preserving
  its return and callee-saved registers. Previously custom initialization/root
  alpha ran before native update, which could overwrite it.
- Treat a detected Pause-origin editor as a custom-open request, including native
  input paths that did not pass through the custom button handler.
- Do not auto-Play from the Strategy wrapper while a live custom editor is open.
- Observe native DemoMatchCard::NeedDisp without changing its return. Release VS
  cover when the native prematch card becomes visible, instead of relying solely
  on late skip/input eligibility. Stadium entrance before the card still requires
  verification; this is not evidence of exact first-frame loading handoff.
- Rate-limited `pause-v9:` logs report hook installation, input dispatch, editor
  entry prerequisites, squad counts, activation and loading release.

Known remaining work: console header relocation and truly translucent stats
panel. The existing opaque cover is intentionally unchanged in this diagnostic
candidate; removing it before proving native rendering suppression would expose
the original buttons again.

Manual test: start a match and observe prematch; open Pause > Game Plan; check
custom editor, B return, resume; check 2P ownership separately. Supply debug.log
after reproducing an issue. Host regression checks do not prove runtime hooks
are reached on hardware.
