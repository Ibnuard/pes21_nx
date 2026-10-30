# Online Game Plan owned roster v118

The live TEST collection contains 24 owned players, including six PACK players.
The saved Game Plan correctly contains eleven starters and seven substitutes.
v117 loaded the collection but projected only those eighteen into the native
renderer. Additional players required a separate Reserves popup, so the ordinary
Substitute list appeared to omit purchases.

## Client correction

- Build the editor roster from the saved eighteen followed by every remaining
  owned instance. Formation, coordinates, tactics and set-piece duties still
  come from the saved server plan.
- Supply the complete roster count and all identities to the existing native
  Exhibition renderer. Its seven visible bench rows scroll over the entire
  collection outside the starting eleven. The header displays the owned count;
  a scrollbar indicates the remaining rows.
- Keep root-button focus outside the bounded player-index range. Player 19 and
  later can no longer collide with the four action buttons.
- Preserve bench scroll position while moving focus onto the field. Load
  portraits for the current viewport. Existing tap/hold-drag controls remain.
- Swaps into the starting eleven or first seven bench slots update only the
  local draft. B returns from Substitute to the action buttons; B Save & Back
  sends one PUT when dirty. Replaced players remain owned and visible.
- Save only the active eighteen, with the existing revision/idempotency guards.
  The backend v117 transaction already persists this squad with the plan; no
  additional backend change or database migration is needed.

## Verification

Controller tests reach purchases by scrolling the native bench route, swap them
into both starting and substitute slots, count zero requests while editing,
save once, clear caches and reload the saved plan plus complete collection.
A boundary case covers the 128th owned player and the four root controls.
Renderer-adapter tests cover complete counts, purchased-player identities,
selection markers and scroll retention when choosing an on-field target.
Existing save-failure, exact retry, keeper, drag and offline editor tests remain
part of the focused suite. Live collection and plan responses are also fed to
the production C parser. Host previews are not physical Switch acceptance.
