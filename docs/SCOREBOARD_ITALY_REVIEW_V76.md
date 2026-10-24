# Serie A plate height review v76

The supplied Switch screenshot shows the native team initials and scores
pressed against the bottom of the shallow blue Serie A strip. The adaptation
resized a 44px source strip to 30px while sizing text separately. V76 changes
the blue/white strip to 40px, keeping its 320px width and the existing font
scale. Name, score and team-colour positions move down by 5px with the same
three-pixel optical lift. This adds room rather than shrinking the native font.

The lower clock and conditional added time move down 10px. The event stack
likewise follows the taller board, preserving its full native appearance/exit
timeline. Native scripts, labels, bindings and conditional added-time ownership
are unchanged; the ordinary duplicate white plate stays offscreen. Other
league packets are untouched.

The packet is rebuilt from the pinned owned Mobile and FL26 Italy inputs. The
ignored proof under `local-debug/review-v76/` records native packet/corruption
admission and the actual C archive reader. Only `scoreboards/c10.nxsb` changes
among the 1,833 members of the current unified `FootballNX.assets`. This data
update requires no NRO rebuild and preserves all commentary/referee members.

Focused tests cover all authored native text keyframes, placement inside the
taller band, clock separation, conditional added time and event relocation.
The host sample uses stand-in text; exact native glyph ink, event playback and
Switch appearance still need device confirmation.
