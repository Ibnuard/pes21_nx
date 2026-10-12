"""Prepare bounded material pages from locally owned shell textures.

This is an asset conversion, not generated artwork. Source files stay read-only.
UV0 retains repeating source coordinates; UV1.x carries an integer tile ID.
Separating cutout masks lets Android ETC1 compress RGB AND alpha independently
instead of silently expanding every cutout texture to BGRA8.
"""
import argparse
import json
from pathlib import Path

PAGE = 1024
CELL = 256
GUTTER = 8
INNER = CELL - 2 * GUTTER
TILES = (PAGE // CELL) ** 2

def atlas_uv(u, v, tile):
    import math
    if not 0 <= tile < TILES:
        raise ValueError('Tile outside atlas')
    return ((tile % 4 * CELL + GUTTER + (u - math.floor(u)) * INNER) / PAGE,
            (tile // 4 * CELL + GUTTER + (v - math.floor(v)) * INNER) / PAGE)


def prepare(profile_path, output):
    from PIL import Image
    import numpy as np
    profile_path = Path(profile_path).resolve(strict=True)
    profile = json.loads(profile_path.read_text())
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    groups = {}
    for name in profile['material_slots']:
        if name == 'M_crowd_seated':
            continue
        path = Path(profile.get('texture_files', {}).get(name) or
                    profile_path.parent / 'textures' / (name[2:] + '.png'))
        # Match the prior material's explicit concrete fallback in linear RGB.
        im = (Image.open(path).convert('RGBA') if path.is_file() else
              Image.new('RGBA', (16, 16), (153, 153, 149, 255)))
        policy = profile.get('material_policies', {}).get(name, {})
        masked = policy.get('masked', im.getextrema()[3][0] < 128)
        two_sided = policy.get('two_sided', True)
        groups.setdefault((masked, two_sided), []).append((name, path, im))
    pages, mapping = [], {}
    for (masked, two_sided), sources in sorted(groups.items()):
        for start in range(0, len(sources), TILES):
            name = 'M_atlas_' + ('cutout_' if masked else 'solid_') + ('two_' if two_sided else 'one_') + str(start // TILES)
            rgb = Image.new('RGB', (PAGE, PAGE), (153, 153, 149))
            mask = Image.new('RGB', (PAGE, PAGE), (255, 255, 255))
            for tile, (source_name, source_path, im) in enumerate(sources[start:start + TILES]):
                # Wrap borders prevent neighbouring tiles bleeding at normal
                # mip levels; preserve repeated UVs, including negative values.
                small = np.asarray(im.resize((INNER, INNER), Image.Resampling.LANCZOS))
                padded = np.pad(small, ((GUTTER, GUTTER), (GUTTER, GUTTER), (0, 0)), mode='wrap')
                xy = (tile % 4 * CELL, tile // 4 * CELL)
                rgb.paste(Image.fromarray(padded[:, :, :3]), xy)
                # The material is a cutout at 0.4, not translucent. Resolve
                # that coverage before ETC1: broad panes authored near 0.4
                # otherwise toggle whole areas when compression rounds alpha.
                coverage = np.where(padded[:, :, 3] >= 102, 255, 0).astype('uint8')
                mask.paste(Image.fromarray(coverage).convert('RGB'), xy)
                mapping[source_name] = dict(material=name, tile=tile, source=str(source_path),
                                            source_size=list(im.size), masked=masked)
            rgb_path = output / (name[2:] + '.png')
            rgb.save(rgb_path)
            row = dict(material=name, color=str(rgb_path), max_texture_size=PAGE, masked=masked, two_sided=two_sided)
            if masked:
                mask_path = output / (name[2:] + '_mask.png')
                mask.save(mask_path)
                row['mask'] = str(mask_path)
            pages.append(row)
    # Preserve all sixteen native animation frames at their existing size.
    if 'M_crowd_seated' in profile['material_slots']:
        name = 'M_crowd_seated'
        path = Path(profile.get('texture_files', {}).get(name) or
                    profile_path.parent / 'textures/crowd_seated.png')
        im = Image.open(path).convert('RGBA')
        if im.size != (1024, 1024) or not profile.get('crowd_flipbook'):
            raise ValueError('Expected the verified native 16-frame crowd sheet')
        color, mask = output / 'crowd_seated.png', output / 'crowd_seated_mask.png'
        im.convert('RGB').save(color)
        im.getchannel('A').convert('RGB').save(mask)
        pages.append(dict(material=name, color=str(color), mask=str(mask),
                          max_texture_size=1024, animated=True, masked=True))
    result = dict(version=1, source_profile=str(profile_path), pages=pages, mapping=mapping,
                  page_size=PAGE, cell_size=CELL, gutter=GUTTER,
                  static_mask_policy='binary coverage at alpha >= 102/255 before ETC1',
                  old_materials=len(profile['material_slots']), new_materials=len(pages))
    (output / 'atlas.local.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    result = prepare(a.profile, a.output)
    print('Material sections: %d -> %d' % (result['old_materials'], result['new_materials']))
