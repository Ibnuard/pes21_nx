# Stadium atmosphere and compact corner panels v73

The v72 device screenshots show mist on the grass with clear stands. Its
endpoint-height gate faded to zero at 650 cm, and the original allowlist did
not cover stadium crowds. V73 integrates a bounded density along the viewing
ray using three height samples. Density declines gradually over tens of metres,
so raised stands remain in the atmosphere. The brighter Day and darker Night
haze are bounded to 42% and 32%; nearby geometry stays clear. Fine and Cloudy
return the original colour exactly.

Existing audited pitch/character materials retain their native reads, alpha,
depth and lighting. Additional colour-only fog covers 194 exact native stadium
and audience body fingerprints plus the existing authored stadium-shell
allowlist. Native depth-only, unknown, screen-space and unsupported varyings
remain untouched. Scope is determined before the existing shell clip/floor
rewrites. No fullscreen fog draw, scene copy or new fog texture is added.

The user also requested light 3D rainfall. The former v11 mesh field rendered
on Switch but was rejected as large bright bars. This candidate uses a distinct
WeatherLight namespace: 256 thin tapered drops, two intersecting quads each,
1,024 triangles total. One ordinary UE mesh component, one masked unlit
material and one clock animate the field; there are no per-drop actors, physics,
image textures, lights, shadows or CPU vertex-buffer uploads. Scene depth
occludes the rain. Summer Rain starts after the first live frame; Winter keeps
the accepted stationary remnants. The previous 768-drop/Snow assets are not
reactivated. A new optional PAK is required; a missing asset retains gameplay.
The component is retired on unload and the clock pauses with the game.

Both corner panels now share a bottom baseline and a 1.2% screen-edge inset.
One player keeps the right corner. Two local players retain their left/right
owner positions when either menu closes, with independent closed-menu entries.
The compact panel is 333x155 at 1280x720, previously 448x215. Main choice text
keeps its 12 px size; icons, button padding and empty space shrink. Actual C
draw-recorder previews are synthetic, not game screenshots.

Build/cook must run serially with the active face factory. A temporary owned
process suspension preserves its in-memory import and checkpoint without
changing the recipe, reports or source snapshot. Always resume the exact PID/
creation-time owners recorded in the local v73 receipt after the build, including
failure. Never suspend or terminate unrelated work. The final candidate retains
all six protected v72 payloads, adds the rain PAK, and changes the NRO. Device
fog/rain visibility and frame time remain separate from host shader/mesh checks;
neither a fixed FPS nor zero rendering cost is claimed.
