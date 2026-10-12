"""Offline camera clearance audit; run with Blender --background --python.

Requires the locally converted .blend, never a committed game fixture. It
casts every layer of shell geometry along camera-to-player rays, including
two-sided front-facing occluders. This is geometry coverage, not device QA.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stadium_material_policy import camera_visible


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blend', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mesh', default='AnfieldShell')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    bpy.ops.wm.open_mainfile(filepath=str(args.blend.resolve()))
    obj = bpy.data.objects[args.mesh]
    tree = BVHTree.FromObject(obj, bpy.context.evaluated_depsgraph_get())
    # Blender export basis is (Fox X, -Fox Z, Fox Y), in metres.
    def ue(point):
        return (point[0]*100, -point[1]*100, point[2]*100)
    anchors = [(x, y) for x in (-55., -52.5, 0., 52.5, 55.)
               for y in (-37., 0., 37.) if x or y]
    rays = 0
    occluded = 0
    masked = Counter()
    failures = []
    old_failures = 0
    for x, y in anchors:
        for radius in (3., 6., 12., 24., 40.):
            for height in (1.6, 3., 6., 12., 20., 32.):
                for degrees in range(0, 360, 15):
                    angle = math.radians(degrees)
                    camera = Vector((x+radius*math.cos(angle), y+radius*math.sin(angle), height))
                    for target_height in (.15, 1.4, 2.4):
                        target = Vector((x, y, target_height))
                        delta = target-camera
                        length = delta.length
                        if length < .01:
                            continue
                        direction = delta.normalized()
                        origin = camera.copy()
                        travelled = 0.
                        hits = 0
                        old_blocked = False
                        rays += 1
                        while travelled < length-.015:
                            point, normal, index, distance = tree.ray_cast(origin, direction, length-travelled-.015)
                            if index is None:
                                break
                            hits += 1
                            material = obj.data.materials[obj.data.polygons[index].material_index].name
                            if camera_visible(ue(point), ue(camera)):
                                failures.append({'camera': list(camera), 'target': list(target),
                                                 'point': list(point), 'material': material})
                            else:
                                masked[material] += 1
                            if not (camera.z < 12 and (point-camera).length_squared < 36):
                                old_blocked = True
                            origin = point+direction*.002
                            travelled = (origin-camera).length
                            if hits > 256:
                                raise RuntimeError('Ray did not progress through shell')
                        occluded += hits > 0
                        old_failures += old_blocked
    report = {'rays': rays, 'blocked_without_cutaway': occluded,
              'blocked_with_v16': old_failures, 'uncleared_fragments': len(failures),
              'masked_by_material': dict(masked), 'failures': failures[:32],
              'scope': 'all quadrants, goal/side/corner apron; 3-40m radius, 1.6-32m camera height; feet/torso/head rays; geometry only'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    if failures:
        raise RuntimeError('Uncleared camera-to-player rays')


if __name__ == '__main__':
    main()
