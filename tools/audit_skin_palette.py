"""Compare local face/neck swatches with native body palettes, without editing images.

The input JSON lists palette textures with normalized sample rectangles and
player face textures/rectangles. Output is measurement only, never permission
to rewrite an appearance table. Review identity and retain accepted overrides
before creating a patch_player_skin policy. Shader/light differences still
require a same-scene device comparison.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
from PIL import Image, ImageStat


def lab(rgb):
    if len(rgb) != 3 or any(not math.isfinite(v) or not 0 <= v <= 255 for v in rgb):
        raise ValueError('Expected three finite sRGB channels in 0..255')
    r, g, b = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in (c/255 for c in rgb)]
    xyz = ((.4124564*r+.3575761*g+.1804375*b)/.95047,
           .2126729*r+.7151522*g+.072175*b,
           (.0193339*r+.119192*g+.9503041*b)/1.08883)
    x, y, z = [v**(1/3) if v > (6/29)**3 else v/(3*(6/29)**2)+4/29 for v in xyz]
    return [116*y-16, 500*(x-y), 200*(y-z)]


def sample(spec):
    roi = spec['roi']
    if len(roi) != 4 or not (0 <= roi[0] < roi[2] <= 1 and 0 <= roi[1] < roi[3] <= 1):
        raise ValueError('Invalid normalized swatch rectangle')
    with Image.open(spec['texture']) as image:
        box = tuple(round(v*image.size[i%2]) for i, v in enumerate(roi))
        if box[2]-box[0] < 2 or box[3]-box[1] < 2:
            raise ValueError('Swatch is too small')
        return ImageStat.Stat(image.convert('RGB').crop(box)).median


def measure(manifest):
    palette = {int(p['skin']): sample(p) for p in manifest['palette']}
    if set(palette) != set(range(1, 7)):
        raise ValueError('All six native palette entries are required')
    players = []
    for player in manifest['players']:
        color = sample(player)
        distances = {skin: math.dist(lab(color), lab(rgb)) for skin, rgb in palette.items()}
        ranked = sorted(distances, key=distances.get)
        players.append(dict(base_id=player['base_id'], rgb=color,
            nearest_skin=ranked[0], delta_e76=distances,
            runner_up_margin=distances[ranked[1]]-distances[ranked[0]]))
    return dict(palette_rgb=palette, players=players, hardware_tested=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    report = measure(json.loads(a.manifest.read_text()))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2)+'\n')
    print(f"Measured {len(report['players'])} faces against six body palettes")


if __name__ == '__main__':
    main()
