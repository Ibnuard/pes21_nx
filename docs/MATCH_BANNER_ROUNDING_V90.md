# Lower banner rounding and competition title spacing

Device feedback on v89 identified square white corners around the native
rounded animated pattern, and a competition label too close to the scores.
The v90 patch changes actual native resources rather than only its preview.

The original `game2dPes-scoreDemo-plate-half` already contains the correct
antialiased rounded alpha plane: 142 pixels are fully transparent in each
562×128 half, while the main native body has alpha224. V89 authored an opaque
white rectangle over that region, losing the original shape. V90 restores
the original alpha bytes exactly and retains white RGB. Its mirrored half
therefore matches both ends of the native pattern. The original translucent
body is retained deliberately; the source alpha is not normalized or painted
over. The native `vi` clip/mask placement and all six wave image bindings,
animation tracks, texture alpha and layered RGB grades remain unchanged.

The actual `competitionName` placement receives a smaller vertical scale,
from399/1024 to277/1024, and a constant+12px Y translation on every native
keyframe. The horizontal scale, centred827.995px field, string binding,
colour/opacity fades and entry/exit motion are unchanged. The conservative
native UIR field bounds leave at least8.988px between the score and title
during their visible overlap, and11.988px when settled. The smaller field
ends at122.034px inside the128px panel. Full long competition strings still
use the original wide native field and existing text-fit policy.

`tools/refine_match_banner_v90.py` binds the accepted v89 lower-movie digest
and validates the original Mobile UI before reading its alpha. It patches
all23 current default/licensed theme packets without changing their source
identity binding. Other movies, including the top scorebar and existing
footers, remain exact. The shared `banner-textures.nxsb` is preserved exactly.
An outer AFP header is used only while recompressing the atlas, so bounded
TXP2 expansion cannot write a little-endian size into a raw big-endian TXP2
header. Every resulting packet is re-read and source/target checksummed.

The host preview uses the real restored plate, rounded alpha, shared wave
rasters, placement/opacity tracks and new competition geometry. Its wave
preview is clipped to coverage derived from the original rounded alpha;
the shipped animation uses the unchanged native clip/mask. Text and crest
marks remain sample proxies for native UIR fonts and live team emblems.
Preview images are layout evidence, not Switch captures or proof of device
playback/FPS acceptance. V89 delivery and reports are not modified.

Focused tests compare the entire restored alpha against its original,
unrelated atlas pixels, every non-title placement and script byte, title
keyframe scale/translation and visible frame gaps, packet identity and
checksums, preview corner coverage and whole archive member deltas. Aggregate
scorebar work composes separately in `game2d_score`; it must preserve these
lower-movie and plate results when the final v90 assets are combined.
