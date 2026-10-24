# Cloudy motion visibility follow-up

The user reports no visible moving cloud shade on a Cloudy daytime match. The
source audit identifies two limitations: installing the shared match clock was
conditional on the optional rain/snow PAK being present, and the old cloud math
reduced diffuse colour by only about 8.2% at its strongest sampled points.
The screenshot alone does not establish which limitation caused this run.

V77 installs the guarded native match lifecycle independently of that optional
PAK. Rain/snow still resolve their own asset once after live play begins and
fail safely if absent. Cloudy requires no particle actor. The existing match
clock pauses, retires and resets with its native world. Two bounded motion
notes per match expose clock advancement without GPU readbacks or per-frame
file logging. Native ABI/symbol/prologue checks are unchanged.

The same two broad analytic cloud shapes now move 40/30 cm per second along
and across the pitch, with a 120-second spatial period and a 20% upper bound
on diffuse darkening. This preserves soft edges while increasing contrast and
movement relative to the earlier 20/15 cm-per-second, 10% bound. The quarter-
second uniform cache remains; there are no new fragment operations, texture
fetches, meshes, render passes, shadow maps, or per-frame geometry uploads.
Existing mowing, Rainy, Winter haze, rain/snow world anchors and non-pitch
receivers remain outside this calibration. Fine, Rainy and Night keep their
cloud-free path.

Tests execute the actual install function in an empty fixture directory,
confirm four guarded lifecycle hooks without a weather PAK, and reject an
unknown runtime prologue. The actual world-tick callback is exercised through
cloud-only loading, pause, missing assets, retirement and another match.
Uniform tests retain four-updates-per-second caching and shader math tests
cover bounds, continuity, spatial motion and exact weather exclusions.

Source changes and inputs are frozen for the isolated production build under
`local-debug/review-v77/`. Shader validation is a host check, not proof that the
new shading was displayed on Switch. No cache purge or cache-hit cause is
asserted from the screenshot. Device appearance and frame time remain open.
