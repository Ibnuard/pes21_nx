# Cup prop admission and native result footer (v87)

The supplied v86 journals bind the expected executing build. The native cut
reaches data state 4 / work phase 3 and loaded mask 0x1f within one second,
without Start or Skip. The one observed object creation matches neither
configured prop path. At the 15-second deadline both registered-owner and UE
identity masks remain zero. The black screen with native blue Next is recorded
device evidence; it is not successful trophy playback.

Two loader errors explain the missing prop admission:

- The native model-path conversion adds `cpk_dat/` before replacing `.fpk`
  with `.xml`. The adapter expected an unprefixed path. V87 requires the two
  exact prefixed paths; it does not introduce fuzzy matching, basename aliases,
  traversal or an extension rewrite inside the adapter.
- The staged ending variant omitted the FX file by leaving its slot empty,
  ahead of the retained podium file. Native GetFileName ends at that first
  empty slot, so the podium was excluded. V87 places the four retained files
  contiguously, with all unused slots at the end.

Bounded execution of the original hash-pinned native functions corroborates
these findings. The old file vector returns three entries; the corrected one
returns four including the podium. Native platform-path conversion produces
exactly one `cpk_dat/` prefix for the two prop paths. Separate static checks
bind the subsequent path/extension calls and constants. These are isolated
function proofs, not an execution of the full match on Switch.

The public repair utility accepts only the reviewed Cup scene, cut, captain,
timing, condition and file-vector layouts. It changes only that vector in
`common/demo/fixdemo/end/table_end.bin`. All other 2,547 CPK members retain
their stored bytes, order and IDs, including player walkout and animations.
The rebuilt CPK remains 34,215,936 bytes; its measured SHA-256 is
`3c2bc88b75211f08356f777d56b11e3430d3ea81815b4d165e35418da634c9a2`.
The exact native activation pin follows that measured candidate. The current
full loose manifest is composed around it and the marker is regenerated from
measured CPK, manifest and unchanged prop-PAK hashes.

V86 suppressed the custom result but returned before hiding an already-created
native result window. V87 resolves and hides its current live surface/root
during the hold, drains result input, and clears only result cursor contexts.
Constructors do not inspect uninitialized nodes. Native result updates and
resume addresses remain intact; result UI resumes after native owner cleanup.
The actual C harness reproduces the old visible-native-node failure.

The package must carry the new NRO, cinematic CPK, composed manifest and trophy
marker together. The other ten runtime payloads remain byte-identical to v86,
including all 1,638 heads, 436 skin corrections, scoreboards, stadiums, weather,
commentary, referee and the cooked prop PAK. No prop/head recook, save change,
active-runtime installation, forced readiness, FPS override or deadline removal
is part of this repair. Native lifting, cameras and final result continuation
still require Switch acceptance evidence.

The subsequent user screenshots show the winning team lifting the trophy.
That confirms visible scene playback in the reported v87 test, while the cup
material is bright green and the native blue Next button remains visible.
Material appearance and the custom controller Skip helper are the next repair
scope; the screenshots do not establish their acceptance or full scene exit.
