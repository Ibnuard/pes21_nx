# Optional podium spark fountains v89

The supplied PC `end_trophy_01_fx.fdc` contains four type-3 records. The supported
Mobile binary does not render them: its effect change/delete/camera/clear methods
are return stubs. Restoring that PC filename to the cut table cannot establish a
visible port. The optional v89 effect is an authored approximation of gold spark
fountains, with the unchanged native trophy animation and podium placement.

Four fountains share 128 spark trajectories in a single static mesh, material and
primitive: 1,024 authored vertices and 512 triangles. Two crossing quads represent
each spark. An unlit, masked, depth-tested material supplies gold colour and a
bounded ballistic vertex offset. It adds no texture assets, fragment texture
fetches, lights, shadow maps, collision, per-particle actors or CPU vertex uploads.
Both the trajectory and conservative bounds rotate with the podium's captured
world pose. This is a bounded implementation cost, not a measured Switch FPS
guarantee or acceptance of the effect's appearance.

The exact live podium UE callback must already prove the native kind, owner
generation and component-bound mesh. `fixdemo_trophy_sparks_observe` receives only
that callback's actor/component, along with its epoch/generation and the admitted
atomic UI token. A loading callback captures weak actor/component references
without allocating. Tick requires the same active UI and PLAYING epochs before
resolving the weak component and capturing its final physical world pose. This
covers a one-shot loading callback without using an early/default transform. The exported native
`USceneComponent::K2_GetComponentToWorld` getter copies the supported Android
40-byte transform; its complete code fingerprint is checked before optional
bindings are enabled. The original native getter is also exercised against owned
fake storage by the optional isolated host proof. No UObject offset is guessed
for the podium transform, and no saved native PES or UEObject pointer is walked
from the UE thread.

The effect copies the podium translation/rotation once after PLAYING, uses physical centimetres
with unit scale, and weakly tracks the current world, podium and its own actor.
Camera pan, zoom and cuts do not relocate airborne sparks. Only UE's native world
tick advances the component material clock. Skip, End, failure, replacement,
native owner retirement or stadium teardown must invalidate the epoch before the
next tick; a metadata-only current podium-generation check remains required even
if a native cached actor is still a valid UObject. Weak retirement and a 60-second
safety bound also stop the effect. A missing optional PAK, failed spawn, rejected
mesh or missing dynamic material leaves native trophy playback unchanged and is
attempted only once per observed owner generation.

Integration uses a separate TrophySparks PAK. The silver trophy/platform PAK, its
marker, cinematic CPK and manifest remain exact. Runtime integration includes the
spark implementation after `fixdemo_trophy_note` is declared and before the props
UE callback; optional prepare runs only after the trophy package/ELF canary is
admitted. Observe is called after the original bound podium callback. Tick runs
after the original UWorld tick and before weather's early returns, with a current
atomic PLAYING epoch, current podium owner-generation proof and Skip state. Reset
runs from the existing stadium retirement callback on the UE thread.

The authoring, packing and tests are public project source. OBJ, editor project,
cooked assets, proprietary PC FX evidence and generated PAKs stay ignored on D.
The package requires an exact member allowlist, UnrealPak Test, independent unpack,
independent cooked mesh counts and embedded ES2/ES3.1 shader checks before delivery.
Device playback, placement, brightness and FPS remain separate evidence.

The first isolated cook produced a 26,149-byte optional PAK with SHA-256
`dd08f07e8c0519e4cc1ed7c9aa852bf3ed0406c6d971600d1a2aaed3f1ff9c3e`.
Independent UModel export confirms 512 cooked triangles, 1,024 vertices and one
primitive. Six embedded fragment records contain zero image fetches; all 48
fragment and 64 vertex macro-variant compilations pass the independent GLSL
validator. UnrealPak Test and a second unpack through the native engine reader
verify the four-member allowlist and every cooked member hash. Four focused host
tests pass, including original-native transform execution, loading capture without
allocation, fixed pose, optional rollback, weak retirement and metadata retirement
while the native cached actor remains valid. These checks do not establish device
appearance or performance.
