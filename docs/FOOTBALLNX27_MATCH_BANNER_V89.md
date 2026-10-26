# FootballNX27 animated lower match banner

The native full-team score banner uses `DemoScoreVersus` and
`game2d_scoreDemo` in `game2dPes`. It already owns live full names, both crests,
scores, competition title, goal-scorer groups and entry/hold/exit animation.
The wrapper keeps that renderer and its scripts. The 562×128 half plate is
authored plain white with clean edges; the original movie mirrors
it into the same 1124×128 field. No static wrapper replacement is drawn.

`build_footballnx27_match_banner.py` changes that plate and bounded colour
fields for the score, names, title and both goal-scorer groups. The native
transforms, image bindings, script bytes, frame labels/counts and all six wave
animation tracks remain exact. Payload-less native colour resets would turn
text white again, so their colour-reset bit is cleared and the immediately
preceding final entry fade completes at full opacity. Other fade samples and
the complete exit timeline stay intact. Each current NXSB packet is patched;
the licensed/generic top scorebar movie and every other movie remain exact.
`c0.nxsb` provides the lower skin while retaining the stock top scorebar when
there is no selected theme. The existing runtime checks both source and target
packet hashes before expansion.

The imported waves are coloured source pixels in the separate native
`common/menu/licence/licenceTexturePes.bin`, not white masks. Multiplying them
by red/blue would produce dark or mixed colours. The bounded companion tool
`build_footballnx27_banner_textures.py` changes only RGB in six named regions
across its two original atlases. Every per-pixel alpha value, other pixel,
region mapping and import remains exact. Wave RGB uses three ribbon depths
at 100%, 55% and 22% brand strength, with a smooth RGB grade toward white at
the centre-facing end for dark-text readability. Alpha is never weakened.
Native image import tags prove that
waves 0–2 occupy the right side and receive blue, while waves 3–5 occupy the
left side and receive red. No mirrored blue end polygon or full-length
coloured border remains. The native pattern still moves and fades on the
original tracks, with stronger sporty colour at each outside end.
`banner-textures.nxsb` uses the same source/target checksum transport and is
admitted only for that exact resource leaf. Other native UI using those six
shared wave regions receives the same consistent colour rebrand.

The title override is a guarded `DemoScoreVersus::SetupInfo` virtual callback.
It runs the original setup first, then uses the original
`Base::SetTextByString` on the current root holder's `competitionName`. It
does not retain a native node or change global native Match data. Priority is
the active Master League fixture, active standalone Cup, active standalone
League, then `Exhibition`. Exhibition/2P does not become a league merely
because both teams select a licensed top scorebar. Master League uses the
pending event's league, domestic Cup, continental, regional, qualifier, World
Cup or friendly name through its read-only frontend API. Long names use a
bounded borrowed Cobra string, synchronously copied by the native setter;
there is no 22-character truncation or native destructor on borrowed storage.
The original wide centred title field and its text-fit policy remain native.

Native evidence pins the full compatible library SHA and original SetupInfo
and text-setter digests; its relocation table places SetupInfo at virtual slot
20. Readable startup instruction guards use RW backing, while calls retain RX
targets. Missing exports, an incompatible ABI or absent slot retain native
behaviour. A bounded original AArch64 text-setter execution test proves the
named-node lookup and synchronous SetStr call, while a host fixture test runs
the production wrapper for all frontend priorities and string lengths.

The full score banner's native `NeedDisp` admits DemoInfo types 9/10.
`DemoScoreVersus` itself gathers goal events and drives the scorer groups.
`DemoGoalAssist` separately selects `game2d_goal` or `game2d_player`; these
scorer/assist notifications are not the full-team scoreboard banner and their
movies remain unchanged. This change follows every native display of the
full score banner. Static resource coverage does not prove the timing of
every kickoff, goal and full-time transition on a Switch.

Local preview frames sample the actual patched plate, all six patched native
wave rasters and their native placement/opacity tracks at frames 20, 70 and
105, over a user-supplied 720p screenshot. Team/score text and H/A crest blocks
are illustrative proxies for native UIR fonts and live emblems. These are
host layout previews, not Switch captures or device event/FPS acceptance.
Game-derived inputs, packets, previews and archive reports stay ignored.

Focused checks cover unchanged non-banner movies, precise atlas pixel masks,
all six unchanged wave tracks, all alpha masks, source/target packet hashes,
every current top theme, the original native text setter, live-root callback
ordering, full title lengths, read-only Master League selection and whole
archive member deltas. The archive adds only c0 and shared-wave packets,
changes existing scoreboard packets, and verifies every other member exact.
