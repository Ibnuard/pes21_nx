# England scoreboard device review v68

The user reported condensed team initials and a blank white box below the
England scoreboard, with no readable added minutes. The requested added-time
position is immediately to the right of the ordinary clock. No new Switch
capture or journal is available for this pass.

The v66 builder inherited Spain's extra horizontal compression of the native
78-pixel UIR name field to 60 pixels before the common two-thirds size change.
England now retains the full field width at the same compact height. HOME and
AWAY are recentered in their existing cells. This changes native text aspect
and spacing; it does not import a PC font or bake selected-team initials.

The white box also had a concrete structural explanation: scoreGroup depth 13
is the ordinary clock's background instance. Moving it below the board did
not make it conditional added-time UI. Its image is shared with the separate
`losstime.plate_lossTime` clip. England now keeps the ordinary instance outside
the viewport, retains the shared image for the native conditional clip, and
places its 48 x 24 plate directly against the clock's right edge. The native
loss-time event, number binding, show/hide endpoints and exit fade remain.

Atlas ink alone does not recolour the dynamic UIR number. The loss-time content
wrapper now multiplies it to black while the separate plate stays white. One
payload-less colour reset at frame 24 is disabled so the number cannot revert
to white there; the preceding reveal keyframe supplies full alpha. The field
validator permits exactly that flag-bit change in the verified loss-time
hierarchy and rejects changes elsewhere. Scripts, labels, strings, source
IDs, frame counts and byteswap descriptors are unchanged. This addresses a
source-consistent cause of unreadable digits, rather than proving which draw
was observed on the user's device.

Focused tests exercise actual pinned owned timeline data, including field
aspect/centering, placement relative to the clock, offscreen legacy background,
dynamic white-glyph contrast, show/hide colour updates, full reveal alpha,
forbidden flag edits and bytecode protection. Host sample artwork is only a
layout composition with stand-in text, not native font or event playback.

The ready-copy update replaces only `scoreboards/c9.nxsb` inside the consolidated
`FootballNX.assets`. Every other member, including the other three scoreboards,
commentary and referee payloads, must match v66/v67 exactly. The NRO is unchanged;
continue using v67. Actual C packet admission, archive readback, typed limits,
corrupt-input rejection, ZIP CRC and payload hashes are required before delivery.

Device acceptance remains open: check team initials, 45/90 minutes with and
without announced added time, number visibility throughout appearance/fade,
and disappearance after the half ends. Existing loose `Scoreboards` files take
precedence over the archive and should be renamed as a backup if still present.

## Vertical text follow-up, v68-r2

The user also recalled that native team initials and scores looked too low.
England now applies a three-pixel optical lift to both names and both scores,
after the authored appearance envelope. Every translated keyframe receives the
same lift, retaining the movement curve, horizontal centering, wider name
fields and added-time correction. The other native placement records remain
byte-identical to v68. A regression compares against the pinned v68 packet and
rejects any change beyond those four instances' vertical translations.

Three pixels is a bounded calibration in the requested direction, not a
measurement from a new screenshot. The field bounds remain inside their cells;
native glyph ink centering still needs confirmation on Switch. The host preview
uses a stand-in font and must not be treated as that confirmation. The r2 assets
update supersedes v68 and continues to use the same v67 NRO.
