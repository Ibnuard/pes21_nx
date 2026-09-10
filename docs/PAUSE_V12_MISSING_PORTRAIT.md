# Pause v12 diagnostic candidate

The v11 hardware log reaches `refreshing existing live squads`, then reports
`AAsset: open(common/player/65533.png) -> MISSING`, with no refresh-complete or
custom-activated message. This identifies synchronous portrait IO as the next
blocking operation, rather than missing Pause route dispatch.

Disable synchronous portrait reads throughout live editor opening and use.
Missing portraits use the existing placeholder; pre-match portrait loading is
unchanged. This intentionally prioritizes an operable editor over live portraits.
The guard is at the reader entry, covering initial refresh and periodic retries.

Show the existing fullscreen Pause page from the controller Pause request,
before native controls become ready. Opening cover expires in five seconds if
the request is rejected; normal heartbeat takes over when ready. It clears on
action dispatch and Pause destruction. Controls remain gated on native readiness.

Existing OBB, full-page layout and confirmed prematch loading release unchanged.
Hardware validation required: early cover, live editor opening, P1/2P edits,
return/resume. Supply diagnostic log if activation still does not complete.
