"""Resumable front-view screening, not appearance or device approval.

Consumes an explicit candidate snapshot and never modifies its inputs. Full-size
images retain candidate and renderer hashes; contact sheets identify every head.
Known regressions still require exact-key rejection before TEST packaging.
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from realface_batch import command, valid_cache
from realface_batch_inventory import read, write
from realface_native_hair_trial import HERE
from realface_pipeline import sha


def screen(config, report, work):
    work = Path(work).resolve()
    if not work.is_relative_to(HERE.parent / 'local-debug') or work == HERE.parent / 'local-debug':
        raise ValueError('Screening requires a dedicated ignored output directory')
    rows = read(report)
    if len({r['base_id'] for r in rows}) != len(rows):
        raise ValueError('Select exactly one candidate per identity')
    if any(r.get('status') != 'candidate_visual_hold' for r in rows):
        raise ValueError('Only exported geometry candidates may enter this screening')
    work.mkdir(parents=True, exist_ok=True)
    renderer = HERE / 'blender_preview_realface.py'
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 13)
    for start in range(0, len(rows), 36):
        page = rows[start:start + 36]; targets = []; pending = []
        for row in page:
            folder = Path(row['folder'])
            if not valid_cache(folder, row['cache_key']):
                raise ValueError('Candidate bytes changed before screening')
            image = work / (str(row['base_id']) + '.png'); stamp = image.with_suffix('.json')
            proof = dict(candidate_key=row['cache_key'], renderer_sha256=sha(renderer),
                         view='front', resolution=300, samples=4, ortho_scale=36,
                         target=[0, 4, 173], mesh_stage='prepared_fbx', hardware_capture=False)
            if image.exists() and stamp.exists() and read(stamp) == dict(proof, image_sha256=sha(image)):
                continue
            targets.append(dict(recipe=dict(ue=read(folder / 'ue-profile.json'), native_rig=config['native_rig'],
                cooked_rig=config['cooked_rig'], view_offset=[0, 90, 0], target=proof['target'],
                resolution=300, samples=4, ortho_scale=36), output=str(image)))
            pending.append((image, stamp, proof))
        request = work / ('targets-%02d.json' % (start // 36 + 1))
        write(request, targets)
        if targets:
            command([config['blender'], '--background', '--threads', '1', '--python-exit-code', '1',
                     '--python', renderer, '--', request], request.with_suffix('.log'))
            for image, stamp, proof in pending:
                write(stamp, dict(proof, image_sha256=sha(image)))
        sheet = Image.new('RGB', (1260, ((len(page) + 5) // 6) * 246 + 36), '#30343a')
        draw = ImageDraw.Draw(sheet)
        draw.text((10, 8), 'FRONT SCREEN ONLY - prepared mesh/textures; no device or appearance approval',
                  font=font, fill='white')
        for number, row in enumerate(page):
            x = number % 6 * 210; y = 36 + number // 6 * 246
            with Image.open(work / (str(row['base_id']) + '.png')) as image:
                image.thumbnail((210, 210)); sheet.paste(image, (x, y))
            draw.text((x + 4, y + 212), row['name'][:25], font=font, fill='white')
            draw.text((x + 4, y + 229), str(row['base_id']) + ' / ' + str(row['triangles']), font=font, fill='#8CD5F7')
        sheet.save(work / ('sheet-%02d.png' % (start // 36 + 1)))
        write(work / 'STATUS.json', dict(rendered=min(start + 36, len(rows)), target=len(rows),
              last_sheet=start // 36 + 1, approved=False, hardware_capture=False))
        print(dict(rendered=min(start + 36, len(rows)), target=len(rows)), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True); parser.add_argument('--report', required=True)
    parser.add_argument('--work-dir', required=True)
    args = parser.parse_args(); screen(read(args.config), args.report, args.work_dir)
