# FL26 generic adboards v76

The first port replaces the native `bill_myclub` Texture2D payload with four
locally decoded FL26 generic adboard images: FL26, Copilot, Hisense and Qatar
Airways. It retains the Mobile mesh, materials, UVs, package metadata and
native atlas animation. It does not install the PC movie player, XML routing,
league selection or complete PC advertising sequence.

## Observed source and target contracts

The owned FL26 `dt90_x64.cpk` inventory has 522 billboard FTEX entries and 26
USM movies. Many `90systemAd_face_*` textures are identical myClub placeholders;
those filenames do not establish the visible sponsor content. The selected
`p_global` movie has two 1536x144 MPEG1 video streams at 30fps. The first stream
contains two horizontal advertising strips, so whole-frame resizing would mix
unrelated strips. Four explicit frame indices and complete logotype crops are
bound to the source member SHA256 before conversion. The movie is read directly
from its CPK byte range, without copying the CPK, OBB or full movie.

The target is the native
`/Game/Assets/bg_lighting_AM1/Billboard/bill_myclub` texture: 512x256 ETC1,
ten mips, 87,400 total compressed mip bytes. Independent UModel export of
`mobile_bill_myclub` confirms `M_billled_myclub` uses this texture. The primary
LED rectangle has approximately 5.3036:1 physical aspect while each atlas panel
is 256x128 texels. The conversion compensates for that sampling geometry;
the atlas preview is intentionally taller than the physical board preview.

The existing cooked material uses `View_GameTime/5` and `/10` for vertical
atlas motion. Its two rows and two columns remain in place. The port preserves
that native animation rather than claiming to reproduce PC USM playback.
No material/mesh shader is rewritten and no runtime adapter is added.

## Builder and verification

`tools/build_fl26_adboards.py` accepts explicit paths to an extracted native
billboard folder, the owned CPK, ffmpeg, ETC1 encoder, repak, UnrealPak and
UModel. It requires an explicit source member SHA256 and pins all three native
Texture2D split fingerprints. Run `--help` for arguments. Generated source
frames, PNG previews, cooked assets, PAKs and reports stay ignored.

Each mip is encoded at its original dimensions. The builder verifies that all
bytes outside mip payload ranges, including `.uasset`, metadata, offsets and
padding, remain identical. It rereads the generated Texture2D and compares its
decoded pixels against an independent UModel export. The PAK allowlist is
exactly `bill_myclub.uasset`, `.uexp` and `.ubulk` in the original namespace.
UnrealPak Test and independent unpack/member hashes are mandatory.

The completed local candidate is under
`local-debug/adboards-v76/candidate-01/`, with `VERIFICATION.json`,
`panels-physical-aspect.png` and `atlas-etc1-roundtrip.png`. Its PAK is
29,990 bytes; ten focused host tests passed. The first build reached a healthy
UnrealPak result but stopped on an overly literal success-log parser; the
parser now checks the exact archive path, three member paths and native summary.
Final verification resumed from the already encoded files and successful test
log, without recooking or changing the payload.

## Integration and limits

The optional `PesMobile-FL26-Adboards-v76-Android_ETC1_P.pak` belongs in the
existing `PesMobile/Content/Paks` folder. It adds one native texture override,
not an additional texture object. Texture dimensions, compressed GPU payload
size, sampling, draw calls and per-frame CPU behavior are unchanged by this
patch. Other packages that override the same three native members must not be
installed simultaneously. Removing this PAK restores the native atlas after
restart. Existing face PAKs, consolidated assets, CPKs and NRO are untouched.

The physical-aspect and decoded-atlas previews received host layout review.
Actual mounting, appearance during animation transitions, mip clarity, Day and
Night behavior and frame time still require Switch testing. This is a generic
four-panel port, not automatic league-specific coverage or hardware acceptance.
