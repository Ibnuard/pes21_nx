"""Author bounded precipitation geometry (centimetres), without game assets.

Each drop has two intersecting quads. UV0's integer U encodes its starting
height; fractional U/V describe the visible shape. The UE material animates
height, so no per-drop actor, tick, collision, texture or CPU upload is needed.
"""
import argparse
import json
from pathlib import Path
import random

HEIGHT = 1800.0
PHASES = 128


def field(snow=False,light=False,world=False):
    if world and not light:raise ValueError('World field requires bounded light policy')
    rng = random.Random(0x4E58534E if snow else 0x4E585241)
    count = 256 if light else 640 if snow else 768
    vertices, uvs, faces = [], [], []
    for _ in range(count):
        extent_x,extent_y=(5250,3350) if world else (2800,2100)
        x, y = rng.uniform(-extent_x, extent_x), rng.uniform(-extent_y, extent_y)
        phase = rng.randrange(PHASES)
        z = (phase + 0.5) / PHASES * HEIGHT
        width, length = ((6, 6) if snow else (2.5, 32)) if light else (18, 18) if snow else (9, 72)
        for plane in range(2):
            start = len(vertices)
            for side, up, u, v in ((-1, -1, .1, .1), (1, -1, .9, .1),
                                    (1, 1, .9, .9), (-1, 1, .1, .9)):
                vertices.append((x + (side * width / 2 if plane == 0 else 0) + (up*length*.05 if light and not snow else 0),
                                 y + (side * width / 2 if plane == 1 else 0) + (up*length*.0125 if light and not snow else 0),
                                 z + up * length / 2))
                uvs.append((phase + u, v))
            faces.extend(((start, start + 1, start + 2), (start, start + 2, start + 3)))
    return vertices, uvs, faces


def write(output, snow=False,light=False,world=False):
    vertices, uvs, faces = field(snow,light,world)
    output.parent.mkdir(parents=True, exist_ok=True)
    # UE4's OBJ importer preserves Z-up axes (unlike its FBX scene conversion).
    with output.open('w', newline='\n') as stream:
        stream.write('# FootballNX authored precipitation, centimetres, Z up\no WeatherField\n')
        for v in vertices:
            stream.write('v %.7f %.7f %.7f\n' % v)
        for uv in uvs:
            stream.write('vt %.7f %.7f\n' % uv)
        for f in faces:
            stream.write('f ' + ' '.join('%d/%d' % (i + 1, i + 1) for i in f) + '\n')
    return {'vertices': len(vertices), 'triangles': len(faces), 'phases': PHASES,
            'height_cm': HEIGHT, 'kind': 'Snow' if snow else 'Rain','light':light,'world':world}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--light-rain',action='store_true')
    mode.add_argument('--light-snow',action='store_true')
    mode.add_argument('--world-field',action='store_true')
    args = parser.parse_args()
    report = {name: write(args.output / (name + 'Field.obj'), name == 'Snow',args.light_rain or args.light_snow or args.world_field,args.world_field)
              for name in (('Snow',) if args.light_snow else ('Rain',) if args.light_rain else ('Rain', 'Snow'))}
    print(json.dumps(report, indent=2))
