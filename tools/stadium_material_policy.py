"""Authored shader policies for the optional stadium shell (no game assets)."""

CROWD_FRAMES = 16
CROWD_FPS = 8
CROWD_PERIOD = CROWD_FRAMES / CROWD_FPS

# Static stadium atlas: UV1.x stores the integer tile ID through FBX's V flip.
# Repeated UV0 is kept within a 240px tile, surrounded by an 8px wrap gutter.
ATLAS_UV = r'''
float tile = floor(Tile.x + 0.5);
float row = floor(tile * 0.25);
float2 origin = float2(tile - row * 4.0, row) * 256.0 + 8.0;
return (origin + frac(UV) * 240.0) / 1024.0;
'''

# The owned sheet contains sixteen vertical animation frames, not sixteen
# different crowd rows. Existing geometry used an 8:1 still; one new frame is
# 16:1, so halve its U span. Sample inside each 64-pixel frame to avoid bleeding.
CROWD_UV = r'''
float frame = floor(Clock * 8.0);
frame = frame - floor(frame / 16.0) * 16.0;
return float2(UV.x * 0.5, (frame + lerp(0.5 / 64.0, 63.5 / 64.0, saturate(UV.y))) / 16.0);
'''

# Camera-to-player clearance for the imported shell only, in UE centimetres.
# The protected box covers the pitch and celebration apron (not the stands).
# A shell fragment is hidden when its camera ray reaches this box AFTER the
# fragment. Shell behind the box stays visible. Unlike a fixed lens radius,
# this also clears a wall between a distant/high camera and a corner player.
# No camera-height gate, world-side exception, translucency or extra pass.
CAMERA_BOX_MIN = (-5800., -4000., -50.)
CAMERA_BOX_MAX = (5800., 4000., 260.)
CAMERA_MASK = r'''
float3 ray = World - Camera;
// Clear the surrounding foreground wall too, not only a player-shaped hole.
// Height does not inflate this radius: a high aerial view keeps its bowl.
float2 outside = max(abs(Camera.xy) - float2(5250.0, 3400.0), 0.0);
float lensRadius = length(outside) + 600.0;
if (dot(ray, ray) < lensRadius * lensRadius) return 0.0;
// The ray/box cutaway is contained in the convex hull of camera and box.
// Most stand/roof fragments are outside even that hull's AABB. Reject that
// possibility before the three component divisions, preserving exact rays
// for the small foreground region that can actually cover a player.
float3 hullMin = min(Camera, float3(-5800.0, -4000.0, -50.0));
float3 hullMax = max(Camera, float3(5800.0, 4000.0, 260.0));
if (all(abs(ray) >= 0.001) && (any(World < hullMin) || any(World > hullMax))) return 1.0;
float3 safeRay = float3(abs(ray.x) < 0.001 ? 0.001 : ray.x,
                       abs(ray.y) < 0.001 ? 0.001 : ray.y,
                       abs(ray.z) < 0.001 ? 0.001 : ray.z);
float3 a = (float3(-5800.0, -4000.0, -50.0) - Camera) / safeRay;
float3 b = (float3(5800.0, 4000.0, 260.0) - Camera) / safeRay;
float3 lo = min(a, b), hi = max(a, b);
float entry = max(lo.x, max(lo.y, lo.z));
float leave = min(hi.x, min(hi.y, hi.z));
return leave >= max(1.0, entry) ? 0.0 : 1.0;
'''

# Conservative vertex-stage rejection. A box shared by a small spatial
# cluster encloses every triangle. Collapse it only when the WHOLE box is
# inside the existing lens sphere. The farthest box corner test is cheap;
# leave the exact camera ray/pitch-box intersection in the pixel policy for
# partial triangles and celebrations, avoiding extra work on all far vertices.
CAMERA_CULL = r'''
float3 delta = Centre - Camera;
float2 outside = max(abs(Camera.xy) - float2(5250.0, 3400.0), 0.0);
float lensRadius = length(outside) + 600.0;
float3 farCorner = abs(delta) + HalfSize;
if (dot(farCorner, farCorner) < lensRadius * lensRadius)
    return Centre - World;
return float3(0.0, 0.0, 0.0);
'''


def camera_box_hidden(centre, half_size, camera):
    """Host counterpart of the conservative vertex cull, all units centimetres."""
    import math
    radius = math.hypot(*[max(abs(c)-b, 0.) for c, b in zip(camera[:2], (5250., 3400.))]) + 600
    if sum((abs(p-c)+h)**2 for p, c, h in zip(centre, camera, half_size)) < radius**2:
        return True
    return False


def crowd_uv(u, v, seconds):
    import math
    frame = math.floor((seconds % CROWD_PERIOD) * CROWD_FPS) % CROWD_FRAMES
    return u * .5, (frame + (.5 + 63 * max(0., min(1., v))) / 64) / CROWD_FRAMES


def camera_visible(world, camera):
    import math
    ray = [w-c for w, c in zip(world, camera)]
    outside = [max(abs(c)-bound, 0.) for c, bound in zip(camera[:2], (5250., 3400.))]
    lens_radius = math.hypot(*outside)+600
    if sum(d*d for d in ray) < lens_radius*lens_radius:
        return False
    if all(abs(d) >= .001 for d in ray) and any(w < min(c, lo) or w > max(c, hi)
           for w, c, lo, hi in zip(world, camera, CAMERA_BOX_MIN, CAMERA_BOX_MAX)):
        return True
    ray = [d if abs(d) >= .001 else .001 for d in ray]
    a = [(lo-c)/d for lo, c, d in zip(CAMERA_BOX_MIN, camera, ray)]
    b = [(hi-c)/d for hi, c, d in zip(CAMERA_BOX_MAX, camera, ray)]
    entry = max(min(x, y) for x, y in zip(a, b))
    leave = min(max(x, y) for x, y in zip(a, b))
    return leave < max(1., entry)
