"""Verify reviewed source stair faces in an independently exported cooked mesh.

Only local, owned intermediates are read. Triangle positions, per-corner UVs,
and atlas tile/material must agree; matching a broad silhouette is insufficient.
The report contains fingerprints and counts, never the proprietary geometry.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from audit_stadium_optimization import accessor
from stadium_assets import material_key
from stadium_surface_policy import preserved_source_faces


def match_source_triangles(source, cooked, *, position_tolerance=2e-5,
                           uv_tolerance=2e-5):
    """Match source corners in Fox metres/Y-up after the actual UE round trip.

    The complete Fox-to-Blender-to-UE-to-UModel round trip preserves the Fox
    UV convention. Corner order can change, so bind each UV to its position.
    """
    actuals = np.asarray([triangle for triangle, _ in cooked])
    textures = np.asarray([uv for _, uv in cooked])
    centres = actuals.mean(axis=1) if len(actuals) else np.empty((0, 3))
    missing = []
    maximum_position_error = maximum_uv_error = 0.
    subnormal_uv_export_components = 0
    for index, (triangle, uv) in enumerate(source):
        triangle = np.asarray(triangle);uv = np.asarray(uv)
        matches = []
        # A rounded spatial hash can put a source value just below a cell
        # boundary and its valid float32 round trip just above that boundary.
        # Use the measured tolerance directly, then verify every corner.
        candidates = np.flatnonzero(abs(centres-triangle.mean(axis=0)).max(axis=1)
                                    <= position_tolerance)
        for candidate in candidates:
            actual, texture = actuals[candidate], textures[candidate]
            order = [int(np.linalg.norm(actual - p, axis=1).argmin()) for p in triangle]
            if len(set(order)) != 3:
                continue
            position_error = float(abs(triangle - actual[order]).max())
            difference = abs(uv-texture[order])
            uv_error = float(difference.max())
            # The local UModel export's half-subnormal representation is
            # sign(x)*(2^-15+abs(x)/2), including zero -> 2^-15. Recognize
            # only that measured representation below 2^-14; do not relax
            # normal UVs. The raw difference is <0.008 atlas texel.
            exported_subnormal = np.copysign(1./32768+abs(uv)*.5, uv)
            subnormal = ((abs(uv) < 1./16384) &
                         (abs(texture[order]-exported_subnormal) < 1e-10))
            if (position_error <= position_tolerance and
                    np.all((difference <= uv_tolerance) | subnormal)):
                matches.append((position_error, uv_error, int(subnormal.sum())))
        if len(matches) != 1:
            missing.append(index)
        else:
            maximum_position_error = max(maximum_position_error, matches[0][0])
            maximum_uv_error = max(maximum_uv_error, matches[0][1])
            subnormal_uv_export_components += matches[0][2]
    return dict(source_triangles=len(source), matched_triangles=len(source)-len(missing),
                missing_or_ambiguous_triangles=missing,
                maximum_position_error_m=maximum_position_error,
                maximum_uv_error=maximum_uv_error,
                subnormal_uv_export_components=subnormal_uv_export_components,
                passed=bool(source) and not missing)


def read_gltf(path):
    document = json.loads(path.read_text())
    if any(any(k in node for k in ('matrix', 'translation', 'rotation', 'scale'))
           for node in document['nodes']):
        raise ValueError('Expected the recorded native-axis mesh without node transforms')
    if len(document['buffers']) != 1:
        raise ValueError('Expected one local glTF buffer')
    uri = Path(document['buffers'][0]['uri'])
    if uri.is_absolute() or uri.name != str(uri):
        raise ValueError('Unsafe glTF buffer path')
    buffer = path.parent / uri
    blob = buffer.read_bytes()
    if len(blob) != document['buffers'][0]['byteLength']:
        raise ValueError('glTF buffer length changed')
    fingerprints = {str(path): hashlib.sha256(path.read_bytes()).hexdigest(),
                    str(buffer): hashlib.sha256(blob).hexdigest()}
    return document, blob, fingerprints


def audit(source_folder, cooked_path, atlas_path, manifest_path, key):
    recipe = next(r for r in json.loads(manifest_path.read_text())['stadiums'] if r['key'] == key)
    rules = [r for r in recipe['source_face_rules'] if r['kind'] == 'central_stair_access']
    if not rules or len({r['material'] for r in rules}) != len(rules):
        raise ValueError('Expected unique reviewed central access materials')
    sources = {r['material']: ([], []) for r in rules}
    inputs = {}
    for path in sorted(source_folder.glob('*.gltf')):
        document, blob, fingerprints = read_gltf(path)
        if document['asset']['generator'] != 'PES 2021 NX FMDL intermediate exporter':
            raise ValueError('Source is not the original Fox intermediate')
        for mesh in document['meshes']:
            for primitive in mesh['primitives']:
                material = document['materials'][primitive['material']]
                texture = material.get('pbrMetallicRoughness', {}).get('baseColorTexture')
                if texture is None:
                    continue
                image = document['images'][document['textures'][texture['index']]['source']]['uri']
                name = material_key('M_' + Path(image).stem +
                    ('_cut' if material['extras']['nxMasked'] else '_solid') +
                    ('_two' if material['extras']['nxTwoSided'] else '_one'))
                if name not in sources:
                    continue
                ids = accessor(document, blob, primitive['indices']).reshape(-1, 3)
                positions, textures = sources[name]
                positions.extend(accessor(document, blob, primitive['attributes']['POSITION'])[ids])
                textures.extend(accessor(document, blob, primitive['attributes']['TEXCOORD_0'])[ids])
                inputs.update(fingerprints)
    atlas = json.loads(atlas_path.read_text())['mapping']
    document, blob, fingerprints = read_gltf(cooked_path);inputs.update(fingerprints)
    cooked = {}
    for mesh in document['meshes']:
        for primitive in mesh['primitives']:
            name = document['materials'][primitive['material']]['name']
            if name not in {atlas[r['material']]['material'] for r in rules}:
                continue
            ids = accessor(document, blob, primitive['indices']).reshape(-1, 3)
            tile = accessor(document, blob, primitive['attributes']['TEXCOORD_1'])[:, 0]
            p = accessor(document, blob, primitive['attributes']['POSITION'])
            uv = accessor(document, blob, primitive['attributes']['TEXCOORD_0'])
            for tile_id in set(round(float(t)) for t in tile):
                selected = ids[np.all(abs(tile[ids]-tile_id) < .001, axis=1)]
                cooked.setdefault((name, tile_id), []).extend(zip(p[selected], uv[selected]))
    reports = []
    for rule in rules:
        positions, textures = sources[rule['material']]
        fox = np.asarray(positions)
        blender = fox[:, :, [0, 2, 1]].copy();blender[:, :, 1] *= -1
        selected = preserved_source_faces(blender.reshape(-1, 3),
            np.arange(blender.size//3).reshape(-1, 3), [rule])
        source = [(fox[i], textures[i]) for i in selected]
        entry = atlas[rule['material']]
        report = match_source_triangles(source, cooked.get((entry['material'], entry['tile']), []))
        report.update(material=rule['material'], rule=rule,
                      atlas_material=entry['material'], atlas_tile=entry['tile'])
        reports.append(report)
    result = dict(source_triangles=sum(r['source_triangles'] for r in reports),
                  matched_triangles=sum(r['matched_triangles'] for r in reports),
                  maximum_position_error_m=max(r['maximum_position_error_m'] for r in reports),
                  maximum_uv_error=max(r['maximum_uv_error'] for r in reports),
                  subnormal_uv_export_components=sum(r['subnormal_uv_export_components'] for r in reports),
                  materials=reports, passed=all(r['passed'] for r in reports))
    for path in (manifest_path, atlas_path):
        inputs[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    result.update(key=key, inputs=inputs, hardware_tested=False)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--cooked-gltf', type=Path, required=True)
    parser.add_argument('--atlas', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--key', default='SignalIdunaPark')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.source, args.cooked_gltf, args.atlas, args.manifest, args.key)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report), flush=True)
    if not report['passed']:
        raise SystemExit(1)
