# Stadium / High diagnostic candidate — 2026-09-17

## Stadium Lite v5: runtime material coverage and warm apron (2026-10-09)

**Accepted checkpoint:** the user tested v5 and approved both Day and Night
on 2026-10-09 ("day dan nightnya perfect sementara"). Preserve this NRO plus
the separate perimeter PAK as the current visual reference. No numerical FPS
measurement was supplied; acceptance is the user's visual/device assessment.

The v4 device test accepts the roof pattern but rejects faded Day grass,
unshaded players and the remaining green Night floor/skin. V4 is not an
accepted lighting fix. This revision preserves its exact analytic roof
geometry and the zero-cascade High Day budget.

The new audit follows the native body mesh's actual material dependency:
`BaseAssets/body_base`, not `TestPlayer/M_test_body`. The former has 84 lit
fragment permutations; v4 covered only 42. `face_tablet_phone` has 84 and
`hair_parts_tablet_ss` has 42 lit permutations, all previously missed.
`body_base_low`'s 42 were already covered. This is a concrete coverage defect,
not proof of which individual permutation rendered every supplied screenshot.
It also explains why the accepted realface material could improve while
generic faces and arms did not. The native skinned vertex shader supplies
translated world position; subtracting `View_PreViewTranslation` gives the
same roof coordinate system as the pitch, after bone/local-to-world transforms.

The fingerprint allowlist now covers these four runtime families as well as
the nine previously audited families: 276 unique character/perimeter body
hashes, 628 lit variants, and 18 excluded masked depth variants. The actual
hair shader's `v3` CSM branch also skips PCF during High Day; the prior policy
only covered `v2`. Direct, sky, SH and decoded reflection light are corrected
before albedo multiplication. Skin/kit/hair samples, normals, alpha, bones,
UVs and animation are preserved. Night/Low/Standard gates are unchanged.

Day pitch albedo has a green-only `(0.82, 1.18, 0.74)` RGB grade before its
existing zero-centred detail modulation. This restores saturation lost when
neutral light replaces the green/yellow irradiance. White paint is excluded;
Night pitch remains byte-exact and the installed custom pitch PAK is untouched.

The separate floor patch is deliberately texture-specific. The owned
`st029_pitch_2` StaticMaterials array assigns `M_field_ed` to outer-apron
section 0; sections 3/4 use `MI_Pitch_L/R`. `M_field_ed` references only the
128x128 ETC1 `st029_field_bsm`. The crew atlas `PitchSide_st029_bsm` is unrelated
and must not be recoloured. `tools/build_stadium_perimeter.py` converts all
eight apron mips to restrained ochre at 80% of the original linear luminance,
preserving grain, dimensions, format, bulk layout and every metadata byte.
The decoded ETC1 luminance is 80.7–82.9% of native across mips; smallest solid
mips quantize R/G equally but never favour green. A separate three-member PAK
contains the unchanged header plus the two modified texture payload files.
This affects the apron in both Day and Night/all qualities; it does not change
the playing surface or prove that the floor physically caused bounced light.

Install both the candidate NRO and `PesMobile-StadiumPerimeter-Android_ETC1_P.pak`;
keep the existing full v3 pitch PAK. Roll back by restoring the previous NRO
and removing only the new perimeter PAK. Accepted Yamal V19C/Raphinha V1 and
Indonesia commentary remain pinned. Day/Night visuals are accepted for this
checkpoint; future lighting changes should be compared against this version.

Production v5 passes 55 focused tests / 1,198 subtests and 2,592 native/patched
GLSL compiles (648 lit variants, both clip-space definitions). The 126 audited
ES3 skinned vertex variants all supply translated world position. Binary checks
confirm the new allowlist/helpers, zero Day cascades, production diagnostics
off, accepted full-loose runtime pair, and byte-identical v4 roof geometry.
The 681-file public-tree audit and `git diff --check` pass. The known broader
legacy test failures recorded for v3 are not claimed fixed by this change.

Accepted local build: `local-debug/stadium-lite-v5/release/FootballNX-Stadium-Lite-v5.zip`
(43,652,700 bytes), SHA-256
`efef1f8de14b4aca6a2a7edc1dcf3283b9b0d61a310670dd179f20e66f618d58`.
NRO: `5c0d1d3a62ae7146eef1242261104d02eef01d3553dbc29e2a5c2aecdfe2b304`.
Perimeter PAK: `b131aa9c33c7b1a873b43f7453796db648f3db44c58189889f7412de0031144e`.
The ZIP is reopened and every member hash checked after packaging; accepted
face/audio and the installed custom pitch hashes are unchanged.

## Stadium Lite v4: neutral light and Day detail (2026-10-09)

**Partially rejected on device; v5 retains only the accepted roof pattern.**

User testing of native stadium v3 confirms the detailed Day roof returns but
FPS drops and yellow light clashes with the custom grass. Night improves, yet
hands/arms remain yellow-green. V3 is therefore not an accepted final fix.

V4 removes the green-dominance threshold from the nine audited material
families' light correction. Yellow-green light with R close to G could pass
the old `G > max(R,B) * 1.08` test; neutralizing each decoded positive light
term at equal luminance also covers that case. This is a scoped compensation,
not proof that this was the only remaining on-device cause. Albedo, skin/kit
textures, normals, RGBM encoding and alpha remain native. Accepted face and
commentary files are unchanged. Night pitch shaders still pass byte-exact.

High Day has a separate saved-quality/time gate. Its pitch shader retains
the accepted diffuse/detail reads, UVs, mips, stripes and paint. The existing
detail alpha supplies a zero-centred 16% albedo modulation only on green turf;
white paint is excluded. No additional texture sample is needed. Two additive
yellow material tints are bypassed, and the yellow grazing highlight becomes
a weak neutral sheen (6% of its previous luminance), shaded by the roof.
Direct, indirect and sky lighting are neutralized before albedo multiplication.
The original soft roof mask no longer supplies the Day highlight silhouette.

The same analytic roof visibility feeds direct and ambient light for pitch,
skin, kits, hair, boots and supported pitch-side/perimeter materials. See
[STADIUM_ROOF_CAMERA.md](STADIUM_ROOF_CAMERA.md) for geometry and cost scope.
Native Low/Standard and Night retain their shadow path. This candidate changes
no PAK/CPK/OBB payload and does not replace the visible stadium mesh.

Unknown sources, segmented shader submissions and nine masked hair depth
variants are refused by the rewrite. The 20 Day pitch variants plus 376
character/perimeter variants compile under both clip-space settings before
and after rewriting (1,584 compiles). Host tests undo only the allowed edits
and compare the rest of each shader byte-for-byte. Numeric tests execute the
emitted helper math, covering skylights, beams, receiver height, light/skin hue,
paint exclusion and disabled identity. Hardware appearance and FPS are pending.

## Native stadium v3: production quality gate (2026-10-09)

**Superseded by v4 after the user's partial Night improvement / Day FPS report.**

The latest Night screenshot still shows green skin; v2 is not an accepted
lighting fix. A concrete production bug was found: `main_menu_video_graphics`
starts at Standard (1). Saved High quality was refreshed only by opening Video
Settings, or by a once-per-match block compiled under `PERF_TRACE`. Release
builds can therefore render native High while leaving `nxNightIndirect=0`.
This also explains why v2's High-only Day receiver could remain disabled.
It is a verified code defect, not proof of the state in the supplied screenshot.

`pes_exhibition_match_setup_data_entry` now refreshes the saved graphics quality
on the game thread for every prepared match, independent of diagnostics and
without opening settings. The getter is not called on the render thread or
polled each frame. Invalid/missing getter results retain the last known value;
Day and Low/Standard still disable Night compensation. The cold-start test
reproduces Standard-in-memory / High-in-save and verifies activation, followed
by all Day/Night/quality combinations.

The Night candidate neutralizes only green-dominant positive light at equal
luminance: reconstructed SH, sky irradiance, decoded lightmap/cubemap radiance,
and later direct/sky/indirect colour multipliers. The 180 known material body
fingerprints cover 376 owned character/perimeter fragment variants. Nine masked
hair depth variants remain unchanged. Encoded RGBM, signed SH coefficients,
albedo, skin/kit/grass texture reads, alpha and output geometry stay native.
There is no floor recolouring, Day mask receiver, or added sampler. The native
pitch materials pass through byte-exact. Host checks undo only the allowed
light insertions and compare the complete remaining shader body to its source;
actual emitted helper math preserves identity with the Night gate disabled.

The 376 variants compile before/after under both clip-space macro settings
(1,504 successful GLSL compiles). These checks verify the implementation;
remaining green cast, final brightness and performance need Switch testing.
Test a fresh launch with High already saved, entering a Night match directly
without visiting Video Settings, then repeat after Day and Low/High changes.

For original Day roof restoration and the two material entries restored in
the complete custom pitch PAK, see [STADIUM_ROOF_CAMERA.md](STADIUM_ROOF_CAMERA.md).

## Stadium review v2: neutral Night perimeter — 2026-10-09

**Rejected on device; superseded by native stadium v3 above.**

New device screenshots show a neon-green perimeter and green cameramen even
with the restored v5/v8 lighting policy. The user requests neutral ground and
white-looking illumination. This is a new candidate, not renewed acceptance
of the previous cast correction.

The audit found that 14 complete ground shader variants are byte-identical to
test-face shaders. A material-body fingerprint alone cannot safely recolour
their diffuse sample. The new floor treatment therefore additionally checks
world-space height (within 20 cm of the ground) and position outside the
105 x 68 m playing rectangle. Only those floor fragments receive a restrained
warm-neutral albedo; raised faces and the pitch's own material are excluded.
Camera/view position is removed through `View_PreViewTranslation`.

The light treatment is separate from albedo. At Night/High, green-dominant
lighting (G above 1.08 times max(R,B)) becomes neutral with the same luminance.
Other light colours remain unchanged. It operates on positive reconstructed
SH, decoded lightmap/cubemap radiance, sky irradiance and the subsequent
sky/direct/indirect colour multipliers. Encoded RGBM, alpha, shadow depth,
signed SH coefficients and kit/skin diffuse textures remain native. Correcting
only the initial cube/SH sample allowed later green light multipliers to
reintroduce colour. This is a bounded renderer compensation; the screenshots
do not establish a physical UV defect or prove that ground albedo itself
causes a runtime lighting bounce.

The shared policy recognizes 180 normalized body fingerprints across 376
owned ES3 variants of nine character/perimeter families. Nine hair depth-only
variants and main-pitch shaders pass unchanged through this policy. Unknown
sources are refused. Day and Low disable the Night colour correction; Day/High
receivers have their own runtime gate. Public code contains hashes and authored
rewrite logic, never the proprietary shader bodies.

All 396 changed scene/pitch variants compile before/after with both clip-space
settings (1,584 glslang compiles). Host tests exercise actual emitted helper
math, projection, alpha preservation, scoped floor behaviour, texture-unit
restoration and cache lifetime. These checks do not establish the active
Switch permutation, final appearance or FPS. Compare Night/High at both
corners and behind each goal, including cameramen and close-ups. Keep the
accepted checkpoint for NRO-only rollback.

## v8 restores the v5 lighting baseline — 2026-10-09

Device feedback rejects v6/v7's lighting expansion: at Night/High the area
behind the goal becomes bright green again, including the cameramen. The
user explicitly prefers the less-green v5 perimeter, while noting that v5
still has some residual cast. Accepted pitch markings and the installed
patch PAK remain the reference.

v8 restores the v5 material scope and insertion sites: 106 normalized body
fingerprints, 193 patched variants, cubemap RGB compensation immediately
after sampling, SH/cache and sky compensation at their original sites.
The 57 reflection-only variants pass through, and baked lightmaps receive
no new correction. The Night/High gate, pitch policy and result UI remain.
This is a rollback of the reported visual regression, not a claim that all
remaining green cast has been eliminated or that an underlying UV defect
has been identified.

A local Unicorn audit executed `glShaderSource_pitch` from the retained v5
ELF with host stubs for allocation/string calls and captured the GL input.
For all 250 owned fragment variants in the six audited families, the restored
source produces byte-identical output to that v5 binary (193 changed, 57
unchanged). No proprietary shader bodies or disassembly are public fixtures.
Focused tests retain unknown-source rejection, unchanged main-pitch bodies,
disabled identity, source preservation, and uniform lifetime checks.

The native packet-reader regression for Indonesia commentary is separate;
see [TEAM_COMMENTARY.md](TEAM_COMMENTARY.md). Keep the installed PAK and
compare v8 versus v5 under the same Night/High stadium and camera conditions.
On-device visual acceptance is still required.

Candidate: `local-debug/review-v8-production/pes21_nx.nro`, 82,781,087 bytes,
SHA-256 `b02a4fa32e054610ebeceb90dc170133bd700813f8dc911376163b5beb68d251`.
Production diagnostics/PerfTrace are off. Native build and embedded icon
validation passed, as did 31 focused tests (250 shader subtests) and all
772 glslang compiles for the 193 patched variants before/after rewriting
with both clip-space macro values. The audio delta is byte-identical to v7.

## v6 decoded-light coverage follow-up — 2026-10-09

Hardware feedback now confirms v5 at Night/High still shows green casts on
players, varying by field side/view direction. The user accepts the pitch
markings/textures. The screenshots do not identify a specific draw, UV defect
or light; the v5 compensation is therefore not a confirmed solution.

An audit of the same six local material families found two concrete coverage
gaps: 57 reflection-only fragment variants were omitted by v5's SH/skylight
eligibility test, and the static perimeter's directional-lightmap branch was
not corrected. v6 allows all 250 audited fragment variants (132 normalized
main fingerprints). Twelve variants reconstruct baked RGB by decoding its
log luminance and direction; compensation now follows that reconstruction,
before multiplying by diffuse material colour.

Cubemap compensation now follows the common decoded radiance destination
after both the tinted linear-RGB and RGBM branches. Previously it modified the
encoded sample before sky tint or RGBM squaring. Cubemap alpha/encoding bytes
are untouched. This changes coverage and insertion location, not the 1.05
excess-green limit. Direct lighting, shadow comparisons, base textures, pitch
shaders, Day and Low retain their prior behavior. No PAK change is required.

Host tests exercise every audited variant, including all 57 previously
excluded reflection-only bodies and all 12 lightmapped bodies. They verify
the decoded destination, unchanged encoded samples, byte preservation outside
insertions, disabled identity and refusal of unrecognized/pitch sources.
This establishes source coverage, not which native permutation was used on
the user's device or whether the cast is resolved. Compare v5/v6 in the same
Night/High celebration/replay at both ends and camera directions, then Day/
High and Night/Low. Keep the accepted original patch PAK for that comparison.

Candidate: `local-debug/review-v6-production/pes21_nx.nro`, 82,781,087 bytes,
SHA-256 `47a1dad98e2032e49dba180889c48d50b45a30a8e11114d210b7579f43e68144`.
Production diagnostics/PerfTrace are off. Native build and embedded-icon
verification passed; glslang compiled all 250 variants before/after patching
with both RHI clip-space macro values (1,000 compiles). Hardware acceptance
is pending. Only the NRO is replaced, with v5 retained for comparison.

## v5 Night/High indirect-light candidate — 2026-10-09

The new candidate is `local-debug/review-v5-production/pes21_nx.nro`:
82,776,991 bytes, SHA-256
`216e4870d32b5bfccbd143ac7f254407030c4c32560449bd0d60d45e19eb9385`.
Diagnostics and PerfTrace are off. Keep the currently installed PAK; this
candidate does not create or require another PAK, and does not combine the
older day-shadow PAK control with a lighting experiment. The active runtime,
OBB, LooseCpk, saves and original patch PAK were not overwritten.

Read-only inspection of the owned Night/High level found a skylight using
`ARSkyLightNF`, intensity 4 and indirect-light intensity 10. Its decoded cube
has green-dominant lower/side faces; the downward face's mean RGB is about
(47, 90, 15). The corresponding Low level lacks that extra skylight/light
setup. High also contains green-tinted static spotlights; the separately
identified green pointlights explicitly have `bAffectsWorld=false` and must
not be cited as active lights. The perimeter diffuse texture is not neon.
These are asset observations, not proof of which draw caused the screenshot.

The audited perimeter and player material variants consume reconstructed
indirect irradiance, skylight irradiance and environment cubemaps. Static
lighting may be baked, so changing a serialized actor's colour alone does not
establish a rebake; Unreal's [indirect-lighting documentation](https://dev.epicgames.com/documentation/en-us/unreal-engine/4.3---indirect-lighting?application_version=4.27)
describes the lightmap/cache distinction. No light actors, material hex colours,
baked maps or textures are changed here.

`source/night_lighting_policy.h` is a bounded compatibility compensation, not
a confirmed root-cause repair. It allows 106 whitespace-normalized fragment
main fingerprints from six audited perimeter/people/face/body material
families (193 cooked variants). After reconstructing indirect/environment RGB,
it caps only excess green to 1.05 times the stronger red/blue channel. It never
increases green. Direct lights, red/blue channels, diffuse material/kit colours,
alpha, depth and shadow code are left intact. Main-pitch bodies are excluded.
The `nxNightIndirect` uniform enables this only at Night with Graphics=High;
Day and Low are identity paths. Unknown sources pass through unchanged.

Both imported and dynamically resolved GL calls reach the same hooks. Program
locations are cached, the Night uniform is updated on a value change, and
delete/relink invalidates the cache. No render targets, texture decoding,
per-frame file IO or readbacks are added. The existing High compositor stays
unchanged. A diagnostic build can emit `night-light: indirect balance` when
a material matches; production logs are disabled.

Host checks cover the quality/time gate, disabled identity, bounded colour
math, source refusal/idempotence, exact preservation outside insertion sites,
and uniform updates on reused programs. glslang compiled all 193 variants both
before and after rewriting, for both clip-space macro branches (772 compiles).
The offline harness supplies the two RHI macros absent from cooked sources;
this verifies syntax, not the Switch driver's output or visual correctness.
Fixtures remain optional local user-owned data, never committed shader dumps.

Hardware acceptance is still pending. Back up the installed NRO, replace only
the NRO, then compare Night/High behind the goals and in replays/celebrations,
including skin, white/coloured kits and perimeter brightness. Check Day/High,
Night/Low, another stadium and repeated matches/menu returns. If the cast is
unchanged or ambient lighting becomes too dark, retain the PAK and restore
the prior NRO; do not stack another blind tint adjustment. The earlier Low+
High slowdown report is separate and is not declared solved by this shader.

## Latest hardware feedback and control handoff — 2026-10-09

The latest user screenshots still show a neon-green perimeter behind the goal
and green casts on players. The High-only lighting report is distinct from the
persistent post-match slowdown, which the user also reproduces on Low and can
clear only by restarting. The v4 NRO changes buffer-pool retention and HUD
portrait ownership, not stadium material colours or High composition.

The original external PAK path is no longer present locally. The canonical
ignored checkpoint at `local-debug/day-shadow-material-v3/install/` was
rehashed and matches the previously supplied PAK exactly (`d7b294b4...`). The
control below was also rehashed (`0cf11f8f...`). Neither was overwritten.
The control cancels only the two old day material colour edits. Night instances
have a different parent and the perimeter bitmap is not neon, so a Night fix
is not established. No global green suppression or guessed light hex edit is
included in v4.

Test v4 NRO with the current PAK first. Then fully close the game, back up the
installed patch outside the mounted Paks folder, and compare the control at
`PesMobile/Content/Paks/PesMobile-Android_ETC1_P.pak` with the same NRO, Night/
High stadium, teams and replay camera. Mount only one `_P.pak`. Check Day too;
restore the original if Night is unchanged or Day regresses. OBB, LooseCpk and
saves are not part of this A/B. Hardware comparison is still pending.

## Night/High neon-perimeter follow-up — 2026-10-08

User reports neon green around the perimeter and green casts in replays,
only with **High**, not Low. They recall the earlier yellow-to-green shadow
colour edit. The supplied installed PAK is 3,613,319 bytes with SHA-256
`d7b294b455c974ef8ad72c959ada4b7878450557a99d27aa6ddb7a1226b2543f`,
exactly the accepted 31-member v19/day-shadow-material-v3 package below.
The different 11-member PAK in this checkout's old `dist/` is NOT the user's
installed baseline and must not be promoted.

History confirms the colour edit in `eebc27c`: the day highlight changed from
RGB (0.875554, 1, 0) to (0.60, 1, 0.29), with an additional green/blue grade.
The highlight was disabled in `4bc72b5`, and the post-light grade removed in
`5c11db0`. Current production source contains neither the old `nxGrass` nor
`nxTint` grade. The two PAK day material `shadowColor` overrides remain:
original (0.03125, 0.023696, 0, 1), green candidate approximately
(0.01638846, 0.02731409, 0.00792109, 1).

Read-only inspection of owned native material imports shows both Night
instances parent `M_Pitch_Default_night`, not the patched day instances. Their
own shadow colour is still the original. `M_field_ed` uses `st029_field_bsm`;
the pitch-side people material uses `PitchSide_st029_bsm/nrm`. None of these
materials or textures is overridden in the supplied PAK. Decoded perimeter
turf is RGB 40–74 / 65–107 / 0–17, not a neon-green bitmap. Host shader tests
verify that every available Night, Low-Night, perimeter-turf and pitch-side
people variant refuses the day hue rewrite. These findings narrow the scope;
they do not establish the runtime source of the High-only green cast.

`tools/audit_stadium_perimeter.py` reproduces this local audit without writing
the input. `tools/build_pitch_shadow_control.py` creates a diagnostic A/B:

- Output: `local-debug/night-tint-control/PesMobile-Android_ETC1_P.pak`
- SHA-256: `0cf11f8f0f5c5f8ebf71ef5d5bdd24169b63e00c1399987ac64225b24bf110a6`
- All 31 members retained; 29 byte-identical. Only the two day `.uexp` colour
  tuples are restored, yielding byte-identical native material exports.
  Textures, custom stripes/grain, Night materials and all other bytes remain.
- V8A/Zlib package unpack/compare verified. Original supplied PAK unchanged.
- **Not a confirmed lighting fix.** Compare original/control using the same
  NRO, teams, stadium and Night/High camera. Keep the original backup outside
  the mounted Paks folder, and install only one `_P.pak` at a time. If Night
  stays identical, do not widen the recolour; investigate High lighting and
  composition with a device trace. Check Day too before retaining the control.

## Accepted High + shadow + pitch checkpoint

User confirmed the v3 material result fits the pitch and requested commit/push
on 2026-09-17. Tag: `checkpoint-high-shadow-pitch-v19`.
Accepted combination (keep both together):

- NRO: `local-debug/day-pitch-tint-v2/pes21_nx.nro`
  SHA-256 `21c99d7db2c33adbfc064dbb3333c784dbc06aa7f3f192d374b759f93842da14`.
- PAK: `local-debug/day-shadow-material-v3/install/PesMobile-Android_ETC1_P.pak`
  SHA-256 `d7b294b455c974ef8ad72c959ada4b7878450557a99d27aa6ddb7a1226b2543f`.
- High 3D rendering, pitch color/pattern/grain and corrected day shadow hue
  accepted in the tested scenario. Stadium shadows remain enabled; the
  conditional shadow-removal fallback is no longer needed for this issue.
- This is not certification of every stadium, complete native postprocessing
  fidelity, or a release-performance build: diagnostics remain enabled.
- Reproduce the 27-member pitch with `recreate_custom_pitch.py` at diffuse
  scale 0.98, then apply `tune_day_pitch_material.py` to produce the 31-member
  stage. Package as V8A/Zlib. Game payloads stay local and ignored.

Historical candidate notes below record the investigation, not the latest
acceptance status.

## Day pitch highlight tint candidate

### v3 material experiment — first of two remaining hardware attempts

User reports v2 remains yellow; log confirms `tint=grass-v2` on shader 136.
Do not interpret compilation as coverage of every visible pitch draw.
The day instances MI_Pitch_L and MI_Pitch_R both serialize shadowColor as
RGBA (0.03125, 0.023696, 0, 1): an explicitly yellow additive material color.
V3 targets this value directly instead of escalating the framebuffer grade.
`tools/tune_day_pitch_material.py` changes its RGB ratio to 0.60:1:0.29 with
weighted luminance retained. It patches a unique 16-byte float tuple, verifies
the result through UAssetGUI decoding, and retains original package headers
and all other export bytes. Left lightColor is deliberately unchanged.

The complete PAK contains the accepted 27 files unchanged plus four files
for the two day material instances. Night material files are unchanged.
Artifact: `local-debug/day-shadow-material-v3/install/PesMobile-Android_ETC1_P.pak`.
Use current v2 NRO for a single-variable comparison; replace PAK only. No
new NRO build. Actual runtime material usage and visual improvement require
hardware confirmation; this is not a claim of a solved tint.

User permits two further visual attempts starting here. If both fail, their
requested fallback is removal of stadium shadow for day matches. Do not
silently remove player/contact shadows along with it. The current experiment
retains all shadows. Rollback PAK is the accepted pitch-day-soft-v1 artifact.

### v2 after hardware feedback

The supplied runtime log contains `tint=grass-v1` for shader 136, proving the
v1 rewrite was applied; the user still observes yellow/olive turf. The additive
highlight correction is therefore insufficient, not an established hook miss.
V2 adds a pitch-local post-lighting RGB grade (0.82, 1, 1.12), normalized to
preserve weighted linear luminance, with a green-dominance mask fading out
on neutral paint. Alpha/depth, textures, shadow kernel and night bodies remain
unchanged. This is an artistic compensation, not a proven correction of the
underlying lighting uniforms. It may need adjustment after hardware review.

Install only `local-debug/day-pitch-tint-v2/pes21_nx.nro`; keep v18 PAK.
Log marker: `tint=grass-v2`. Compare day shadow and sunlit areas, white paint,
then night. Checkpoint v18 remains the rollback; no new commit requested.

After v18 acceptance, inspection found a fixed yellow-green additive grazing
highlight in the owned day fragment shader. It is added after the shadowed
direct and ambient lighting terms, so its hue can remain visible in shadow.
This is a concrete contributor, not proof that all observed olive tint comes
from this term. Night material variants do not contain that constant.

`pitch_shadow_policy.h` now replaces only this highlight color in the same
eight fingerprint-allowlisted day variants: RGB (0.875554, 1, 0) becomes
(0.60, 1, 0.29), approximately the accepted diffuse palette's channel ratio.
Peak green and highlight strength/mask/view dependence are retained; this is
an artistic candidate, not a calibrated color-space conversion. The v18
shadow slope remains 0.85. Base diffuse, grain, stripes, direct/ambient light,
night shaders and all other material sources are unchanged. Unknown sources
pass through. Non-allowlisted day permutations are not covered by this test.

Install NRO only: `local-debug/day-pitch-tint-v1/pes21_nx.nro`. Keep the
accepted v18 PAK. Log `tint=grass-v1 rgb=0.60,1.00,0.29` confirms application.
Check High day with the same stadium/camera and both shadowed/sunlit turf,
then night for regression. The change does not address spatial shadow jaggies.
Host tests: 41 tests and 30 subtests passed. Hardware color acceptance pending.
Rollback NRO: `local-debug/day-shadow-soft-v1/pes21_nx.nro`.

Checkpoint: user confirmed High renders 3D without the prior crash and accepted
the reconstructed pitch pattern/grain (2026-09-17). This is not confirmation
of complete High postprocessing fidelity or all camera scenarios.

## Accepted checkpoint and next visual review

### Pitch color/pattern/grain acceptance (subsequent checkpoint)

User accepted the `pitch-day-soft-v1` pitch color, pattern and grain on
2026-09-17. Tag: `checkpoint-pitch-color-pattern-grain-v18` (local only).
This acceptance does not establish that the experimental day shadow slope
fixes edge aliasing or the olive/yellow tint.

- NRO: `local-debug/day-shadow-soft-v1/pes21_nx.nro`, SHA-256
  `d6112900431b689e2e6b4d56ca51f62d92d81970904db253497b0210484868c5`.
- PAK: `local-debug/pitch-day-soft-v1/install/PesMobile-Android_ETC1_P.pak`,
  SHA-256 `d493a9f09f1dd14fbe1c6bb07348e73504c0dd684278b4742ca65f7e7d19ee82`.
- Reproduce with `tools/recreate_custom_pitch.py --diffuse-scale 0.98`
  and the previously documented owned native inputs/encoder/GUI.
- Next task: investigate pitch-only daylight lighting tint so it blends with
  the accepted grass. The user's observation that stock grass is yellower is
  a plausible explanation, not yet verified as the shader-level cause.
  Preserve the accepted night look, stripe geometry and grain.

### Earlier High-render checkpoint

- NRO SHA-256: `e514b94d01d63e3b40e5d44a65ec9b60caed4e49ef43aecefd1e930566a54d33`
- PAK SHA-256: `f25e26d1b5e6bb08156485663ba43f33efb6779521d29d4c08a538e2505ee946`
- Pitch backup: `local-inputs/custom-pitch-v17/PesMobile-Android_ETC1_P.pak`
  (ignored, never publish the cooked game payload).
- High renders successfully in the supplied hardware screenshots. Night pitch
  pattern and grain accepted; user requests only a very slight darkening next.
- Day stadium shadow appears olive/yellow with jagged edges. Screenshot alone
  does not isolate shadow-map filtering, lighting/material tint, or the fallback
  color transform. Inspect those independently before changing shader behavior.
- Next candidate should preserve stripe separation and grain, reduce pitch
  luminance by roughly 2–3% as a starting experiment, and isolate day shadow
  changes from the accepted night look. No such tuning is in this checkpoint.
- 40 tests and 30 subtests passed; full 27-member PAK roundtrip verified.

## Follow-up v4: source identified; complete pitch reconstruction

The v3 hardware trace shows FBO 8 / texture 85 at 1024x576 with nonzero RGB
(sample 768/115/22372), while FBO 10 / texture 297 at 256x144 is black.
The final three-index draw (program 19) binds texture 297 on unit 0 and texture
85 on unit 1. This is direct evidence that the old unit-0-only compositor
does not recognize High's scene source. Numeric IDs are diagnostic evidence,
not constants used by the fix.

V4 records completed color+depth targets within the current frame. On a
three-vertex presentation draw, a unit-1 source must match a recorded target
and the full destination viewport dimensions. It then uses the existing
fullscreen fallback with that source and sampler, restoring unit 0 and the
active texture afterwards. Targets expire at swap and after consumption.
This bypasses the native final bloom composition; it does not claim complete
High postprocessing fidelity. Other shader stages and High quality selection
remain enabled. User has confirmed scene rendering; broader hardware coverage
and postprocessing parity remain unverified.

The previous 11-member pitch candidate was rejected by the user: it removed
the custom overrides. Do not deploy that PAK again. With no backup available,
`tools/recreate_custom_pitch.py` rebuilds all 27 members from the owned native
PAK. Shader hashes and same-length name-table changes are verified using the
existing Low_R pipeline. White-line blocks at every mip are retained; six
diffuse textures, neutral specular masks and a soft detail texture are present.
Grain is explicitly seeded procedural, not falsely described as recovered EF10
grain. Palette/phase validation verifies 18 bands, opposite Low_R phase, and
unchanged native marking blocks. This is a reconstruction, not backup recovery.

Artifacts: `local-debug/high-compositor-v4/pes21_nx.nro` and
`local-debug/pitch-recreate/install/PesMobile-Android_ETC1_P.pak`.

## Follow-up v3: High reaches gameplay but scene is black

User confirms v2 no longer crashes. The next hardware log records successful
vertex-only completion, no shader compile/link failures, and about 920,700
offscreen indices per sampled gameplay frame. This proves draw submission,
not correctly shaded geometry. Its offscreen samples repeatedly inspect only
FBO 10, texture 232, viewport 256x144, with zero RGB. The scene-sized 1024x576
allocation exists but is not sampled at its intermediate transition.

`local-debug/high-compositor-v3/pes21_nx.nro` is a diagnostic-only follow-up,
not a claimed black-screen fix. It samples transitions between non-default
FBOs as well as the final transition to screen, throttled per target rather
than globally (avoids sampling cadence aliasing a fixed multipass sequence).
It records default-target draw textures even when the preceding sample is
black. No guessed scene texture, shader replacement, or High-to-Standard
downgrade is added. V2's guarded link compatibility remains.

Copy NRO only; leave the pitch PAK unchanged. Reproduce High kickoff, allow
about 10 seconds of gameplay, then collect debug.log before another launch.
Inspect intermediate RGB samples and final sampler identities to choose the
next compositor change. Debug readbacks can reduce performance.

## Follow-up v2

The supplied hardware log ends with `program lacks a fragment shader` for
program 72, then `AndroidThunkJava_ForceQuit`. The preceding 4096x2048 depth
allocation returns. This identifies a link failure, not an established OOM.
The shadow/depth-pass attribution is still an inference.

The compatibility candidate retries only that exact driver error with exactly
one attached, compiled vertex shader and a recognized GLES source version.
It adds a matching-version fragment stage with no color outputs. Existing
fragment shaders, including masked geometry shaders, are never replaced.
Failed retries preserve failure rather than faking link success. Host tests
cover refusal cases, cleanup, successful retry, and unsuccessful retry.

`local-debug/stadium-high-review-v2/` contains the diagnostic NRO and
`PesMobile-Android_ETC1_P.pak`. Back up the installed NRO and patch PAK first.
Test the NRO alone first to isolate High, then copy the PAK to
`PesMobile/Content/Paks/`. No OBB/CPK/saves changes.

At the user's request the pitch candidate uses the surviving local custom
11-member patch, not an asserted byte-identical copy of their installed PAK.
`tools/soften_pitch_patch.py` rebuilds its three ETC1 diffuse payloads with
the v17 palette and deterministic positive grain. All eight material files
and all detected white-paint ETC blocks remain byte-identical to that local
baseline. Package unpack/repack is independently byte-checked. This is not
a claim of coverage for the unavailable six-texture/27-member baseline.
Pitch lighting and High gameplay still require hardware review.

- Stadium target retains the 14-unit deadzone but smoothly bounds planar
  ball-to-target separation to 18 units instead of retaining 65% of arbitrary
  native prediction error. No velocity prediction or shared trace patch.
- Pause updates reset movement readiness, including the settings-child route.
  Resume must observe fresh ball movement and one native warm-up frame.
- Diagnostic build logs texture storage and renderbuffer allocations before
  and after driver entry. Existing diagnostics and per-line flushing are on;
  profiling is off. These logs help narrow a crash, not prove its cause.
- Pitch recipe `clean-v17` retains v16's RGB midpoint and stripe geometry,
  reduces green stripe separation from 24 to 8, and uses weaker positive-only
  diffuse grain. Runtime generation is pending the actual installed baseline:
  local dist contains an older 11-member patch, not the documented 27-member
  pitch baseline. Do not replace the user's pitch with this old patch.

Candidate NRO: `local-debug/stadium-high-review/pes21_nx.nro`.
Copy only that NRO over the current full-loose-CPK installation for diagnostics.
Keep existing OBB, LooseCpk, PAK and saves. Previous NRO remains in
`local-debug/full-mobile-kit-migration-v1/` for rollback.

Test Standard first: Stadium selected before kickoff; forward/backward passes;
pause > General Settings > resume; repeat camera changes and second match.
Then select High and reproduce entering the field. Copy `debug.log` immediately
after failure, before another launch (the next boot truncates it). Include the
system crash report if available. Diagnostic frame rate is not representative
of release performance. Ultra and 90 FPS are out of scope.
## Day shadow / pitch tuning candidate (2026-09-17)

After checkpoint `checkpoint-high-render-pitch-v17`, the user's two-match
day/night log shows successful composition and no reported compositor GL
errors. Hardware feedback confirms High renders again. Keep that checkpoint
as the accepted baseline; this candidate still needs visual hardware testing.

The owned day pitch shader already performs nine-tap manual depth PCF.
Do not force arbitrary depth samplers to linear. A source hook accepts only
eight audited day-main fingerprints and scales the shadow comparison slope
by 0.85. It retains the native spatial kernel and lighting colors. Audited
night/Low-night bodies and unknown sources pass through unchanged. Runtime
log `pitch-shadow: day slope=0.85` confirms the hook actually matched; absence
means the candidate's shader effect has not been established. This is not a
guaranteed spatial aliasing fix. The olive/yellow tint's cause remains
unisolated, so no global scene color correction is applied.

The complete 27-member pitch is rebuilt with `--diffuse-scale 0.98`:
source diffuse RGB is reduced 2%, preserving protected native paint blocks,
stripe geometry, grain recipe, detail and material bindings. ETC1 quantization
and lighting mean this is not an exact 2% in-game luminance reduction.

Candidate files:
- `local-debug/day-shadow-soft-v1/pes21_nx.nro`
- `local-debug/pitch-day-soft-v1/install/PesMobile-Android_ETC1_P.pak`

Replace only the NRO and the patch PAK under `PesMobile/Content/Paks/`.
Keep OBB, LooseCpk and saves. Accepted pitch backup remains under
`local-inputs/custom-pitch-v17/`; accepted NRO is in
`local-debug/high-compositor-v4/`. Test High day shadow edges and hue, then
night brightness with the same stadium/camera. Diagnostics remain enabled.
Host verification: 41 focused tests and 30 subtests passed; hardware visual
acceptance of the shadow change is pending. The subsequent v18 checkpoint
accepts pitch color/pattern/grain only, as recorded above.
