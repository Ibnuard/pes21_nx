"""Audit actual UE cooked meshes/textures against an optimized FBX profile.

Requires locally supplied UModel and cooked assets. Exports remain ignored.
Checks section count, triangle count, per-triangle atlas IDs, compressed masks,
native crowd coverage and cutout threshold drift after ETC1 compression.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess


def accessor(document, blob, index):
    import numpy as np
    a = document['accessors'][index]
    view = document['bufferViews'][a['bufferView']]
    n = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}[a['type']]
    kind = np.dtype({5126: '<f4', 5125: '<u4', 5123: '<u2', 5121: 'u1'}[a['componentType']])
    stride = view.get('byteStride', kind.itemsize * n)
    values = np.ndarray((a['count'], n), dtype=kind, buffer=blob,
        offset=view.get('byteOffset', 0) + a.get('byteOffset', 0), strides=(stride, kind.itemsize))
    return values.astype(float)/np.iinfo(kind).max if a.get('normalized') else values


def audit(profile_path, cooked, umodel, output):
    import numpy as np
    from PIL import Image
    profile = json.loads(profile_path.read_text())
    key = profile['key']
    content = cooked / 'PesMobile/Content'
    assets = content / 'FootballNX/Stadiums' / key
    exported = output / 'FootballNX/Stadiums' / key
    if exported.exists():
        raise FileExistsError('Use a fresh audit output: ' + str(exported))
    output.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([str(umodel), '-export', '-gltf', '-png', '-game=ue4.22',
        '-path=' + str(content), '-out=' + str(output), key + 'Shell'], capture_output=True, check=True)
    (output / (key + '.log')).write_bytes(result.stdout + result.stderr)
    if b'ERROR:' in result.stdout + result.stderr:
        raise RuntimeError('Mesh export failed: ' + key)
    gltf = json.loads((exported / (key + 'Shell.gltf')).read_text())
    blob = (exported / gltf['buffers'][0]['uri']).read_bytes()
    slots, triangles, crowd = [], 0, 0
    minimum_bound_margin = float('inf')
    maximum_shade_error = 0.
    atlas = json.loads((profile_path.parent / 'textures/atlas.local.json').read_text())
    for primitive in gltf['meshes'][0]['primitives']:
        name = gltf['materials'][primitive['material']]['name']
        slots.append(name)
        expected_uvs = 5 if profile.get('vertex_camera_cull') else 2
        if sum(k.startswith('TEXCOORD_') for k in primitive['attributes']) != expected_uvs:
            raise ValueError('Cooked UV count differs from the camera policy: '+name)
        ids = accessor(gltf, blob, primitive['indices']).reshape(-1, 3)
        triangles += len(ids)
        if profile.get('baked_hemisphere'):
            color = accessor(gltf, blob, primitive['attributes']['COLOR_0'])
            normal = accessor(gltf, blob, primitive['attributes']['NORMAL'])
            # UModel's static-mesh export uses (UE X,Z,Y).
            expected = .65 + .30*np.clip(normal @ np.array([.25,.90,.35]),0,1)
            error = float(np.max(np.abs(color[:, 0]-expected)))
            if error > .008 or not np.allclose(color[:, :3], color[:, :1], atol=1/255):
                raise ValueError('Cooked vertex light differs from the source normals: '+name+' '+str(error))
            maximum_shade_error = max(maximum_shade_error, error)
        uv = accessor(gltf, blob, primitive['attributes']['TEXCOORD_1'])
        tile = uv[:, 0]
        if not np.all(np.isfinite(uv)) or np.max(np.abs(tile - np.round(tile))) > .001:
            raise ValueError('Corrupted atlas tile channel: ' + name)
        if not np.all(np.ptp(tile[ids], axis=1) == 0):
            raise ValueError('Atlas tile interpolates across a triangle: ' + name)
        if profile.get('vertex_camera_cull'):
            xy = accessor(gltf, blob, primitive['attributes']['TEXCOORD_2'])
            ze = accessor(gltf, blob, primitive['attributes']['TEXCOORD_3'])
            yz = accessor(gltf, blob, primitive['attributes']['TEXCOORD_4'])
            bounds = np.concatenate((xy, ze, yz), axis=1)*32768
            if not np.isfinite(bounds).all() or (bounds[:, 3:] <= 0).any():
                raise ValueError('Invalid cooked cluster bounds: ' + name)
            if np.any(np.ptp(bounds[ids], axis=1) > .001):
                raise ValueError('Vertex decisions differ within one triangle: ' + name)
            # UModel static glTF uses metres, (UE X, UE Z, UE Y).
            pos = accessor(gltf, blob, primitive['attributes']['POSITION'])
            pos = pos[:, [0, 2, 1]]*100
            margin = bounds[:, 3:] - np.abs(pos-bounds[:, :3])
            if np.min(margin) < 1:
                raise ValueError('Quantized bound no longer encloses its geometry: ' + name)
            minimum_bound_margin = min(minimum_bound_margin, float(np.min(margin)))
        if name == 'M_crowd_seated':
            crowd += len(ids)
        else:
            valid = {v['tile'] for v in atlas['mapping'].values() if v['material'] == name}
            if set(np.round(tile).astype(int)) - valid:
                raise ValueError('Unknown atlas tile in cooked mesh: ' + name)
    if set(slots) != set(profile['material_slots']) or len(slots) != len(set(slots)):
        raise ValueError('Missing or duplicate cooked material sections')
    if crowd != profile['crowd']['triangles'] or triangles - crowd != profile['shell_triangles']['reduced']:
        raise ValueError('Cook changed shell/crowd triangle count')
    formats = {s.decode() for f in assets.glob('T_*.uexp') for s in re.findall(rb'PF_[A-Z0-9_]+', f.read_bytes())}
    if formats != {'PF_ETC1'}:
        raise ValueError('Texture silently expanded instead of ETC1: ' + str(formats))
    masks = {}
    for material, path in profile.get('mask_files', {}).items():
        source = np.asarray(Image.open(path).convert('RGB'))[:, :, 0]
        decoded = np.asarray(Image.open(exported / ('T_' + material[2:] + '_mask.png')).convert('RGB'))[:, :, 0]
        if source.shape != decoded.shape:
            raise ValueError('Mask dimension changed in cook: ' + material)
        mismatch = float(np.mean((source >= 102) != (decoded >= 102)))
        if mismatch > .02:
            raise ValueError('ETC1 cutout error exceeds 2%: ' + material)
        masks[material] = mismatch
    # Count only live dependencies recorded by the independently checked PAK.
    allowed = {key + 'Shell'} | set(profile['material_slots'])
    allowed |= {'T_crowd_flipbook_v16' if n == 'M_crowd_seated' else 'T_' + n[2:] for n in slots}
    allowed |= {'T_' + n[2:] + '_mask' for n in profile['mask_files']}
    files = [f for f in assets.iterdir() if f.stem in allowed]
    return dict(key=key, materials=len(slots), triangles=triangles, crowd_triangles=crowd,
        vertex_camera_cull=bool(profile.get('vertex_camera_cull')), uv_channels=expected_uvs,
        baked_light_max_error=maximum_shade_error if profile.get('baked_hemisphere') else None,
        camera_bound_min_margin_cm=minimum_bound_margin if profile.get('vertex_camera_cull') else None,
        all_atlas_triangles_constant=True, texture_formats=sorted(formats), mask_clip_mismatch=masks,
        cooked_payload_bytes=sum(f.stat().st_size for f in files), cooked_files=len(files),
        cooked_texture_bulk_bytes=sum(f.stat().st_size for f in files if f.suffix == '.ubulk'))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    config = json.loads(a.config.read_text())
    cooked = Path(config['project']).resolve().parent / 'Saved/Cooked/Android_ETC1'
    reports = []
    for profile in sorted((a.work.resolve() / 'prepared').glob('*/fbx.local.json')):
        report = audit(profile, cooked, Path(config['umodel']).resolve(), a.output.resolve())
        reports.append(report)
        print('COOK VERIFIED', report['key'], report['cooked_payload_bytes'], flush=True)
    (a.work / 'cooked-audit.json').write_text(json.dumps(reports, indent=2) + '\n')


if __name__ == '__main__':
    main()
