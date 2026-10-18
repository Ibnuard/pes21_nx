"""Surface isolation regressions; synthetic assets except an optional local audit."""
from pathlib import Path
import struct
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import realface_surface_patch as surface
from cooked_texture import Texture


def header(names, checksum=1):
    data = bytearray(64)
    data[:4] = b'\xc1\x83\x2a\x9e'
    struct.pack_into('<i', data, 28, 1)
    struct.pack_into('<ii', data, 37, len(names), 64)
    for name in names:
        raw = name.encode('ascii') + b'\0'
        data.extend(struct.pack('<i', len(raw))+raw+struct.pack('<I', checksum))
    return bytes(data)+b'UNRELATED-EXPORT-TABLE'


def source_fixture():
    player = dict(base_id=7, native_player_id=17, name='Authored fixture',
                  face_triangles=1600, hair_triangles=400, triangles=2000, sections=2)
    owner = dict(base_id=7, native_player_id=17, fingerprint='identity-A', status='validated', triangles=2000)
    report = dict(players=[player], unpack_hashes_match=True,
                  asset_hashes={name: 'placeholder' for name in surface.asset_names(17)})
    state = dict(identities={'ef:7': dict(owner, status='active')})
    return report, [owner], state


def test_triangle_cap_includes_face_and_hair_and_identity_is_preserved():
    report, verified, state = source_fixture()
    assert surface.validate_source(report, verified, state)[7]['fingerprint'] == 'identity-A'
    report['players'][0]['hair_triangles'] += 1
    report['players'][0]['triangles'] += 1
    verified[0]['triangles'] += 1
    with pytest.raises(ValueError, match='2000-triangle'):
        surface.validate_source(report, verified, state)


def test_cached_identity_row_uses_verified_release_counts():
    report, verified, state = source_fixture()
    verified[0]['status'] = 'validated_cached'
    del verified[0]['triangles']
    assert surface.validate_source(report, verified, state)
    report['players'][0]['triangles'] = 1999
    with pytest.raises(ValueError, match='2000-triangle'):
        surface.validate_source(report, verified, state)


@pytest.mark.parametrize('issue', ['fingerprint', 'native', 'duplicate_slot', 'duplicate_base', 'section', 'held', 'shared_asset'])
def test_source_rejects_unsafe_baselines(issue):
    report, verified, state = source_fixture()
    if issue == 'fingerprint': verified[0]['fingerprint'] = 'identity-B'
    if issue == 'native': state['identities']['ef:7']['native_player_id'] = 18
    if issue == 'duplicate_slot': state['identities']['ef:8'] = dict(state['identities']['ef:7'], base_id=8)
    if issue == 'duplicate_base': report['players'] *= 2
    if issue == 'section': report['players'][0]['sections'] = 3
    if issue == 'held': verified[0]['status'] = 'held_geometry'
    if issue == 'shared_asset': report['asset_hashes'][surface.BASE+surface.PARENT+'.uasset'] = 'bad'
    with pytest.raises(ValueError):
        surface.validate_source(report, verified, state)


def test_header_relink_keeps_exports_and_all_other_name_entries(tmp_path):
    source = tmp_path/'old.uasset'
    original_names = ['untouched', surface.PARENT, surface.GAME+surface.PARENT]
    source.write_bytes(header(original_names))
    source.with_suffix('.uexp').write_bytes(b'opaque cooked material instance')
    target = tmp_path/'new.uasset'
    replacements = {surface.PARENT: surface.NEW_PARENT, surface.GAME+surface.PARENT: surface.GAME+surface.NEW_PARENT}
    template = header([surface.NEW_PARENT, surface.GAME+surface.NEW_PARENT], checksum=9)
    changes = surface.patch_names(source, target, replacements, template)
    assert len(changes) == 2
    assert target.with_suffix('.uexp').read_bytes() == source.with_suffix('.uexp').read_bytes()
    masked = bytearray(target.read_bytes())
    for row in changes:
        masked[row['start']:row['end']] = source.read_bytes()[row['start']:row['end']]
    assert bytes(masked) == source.read_bytes()
    with pytest.raises(ValueError, match='equal-length'):
        surface.patch_names(source, tmp_path/'bad.uasset', {surface.PARENT: 'too short'}, header(['too short']))
    assert not (tmp_path/'bad.uasset').exists()


def normal_texture(path):
    # A project-authored 8x8 ETC1 fixture with four inline mips.
    data = bytearray(b'SYNTHETIC-PREFIX!')
    pixel_format = b'PF_ETC1\0'
    data += struct.pack('<4I', 8, 8, 1, len(pixel_format)) + pixel_format + struct.pack('<2I', 0, 4)
    for width in (8, 4, 4, 4):
        size = width*width//2
        data += struct.pack('<4Iq', 1, 0x40, size, size, 0)
        data += bytes(size) + struct.pack('<3I', width, width, 1)
    path.write_bytes(data+b'UNCHANGED-TRAILER')


def test_neutral_normal_is_flat_in_every_mip_and_preserves_bulk_metadata(tmp_path, monkeypatch):
    path = tmp_path/'normal.uexp'
    normal_texture(path)
    original = path.read_bytes()
    before = Texture(path)
    # Encoded constant RGB(128,128,255), authored with Android's ETC1 encoder.
    monkeypatch.setattr(surface, 'etc1', lambda *args: bytes.fromhex('8080f826ffff0000'))
    proof = surface.neutralize(path, 'unused', tmp_path)
    assert len(proof['mips']) == 4
    assert all(mip['max_tilt_degrees'] < .32 for mip in proof['mips'])
    after = bytearray(path.read_bytes())
    for mip in before.mips:
        after[mip.offset:mip.offset+mip.size] = original[mip.offset:mip.offset+mip.size]
    assert bytes(after) == original


def test_wrong_normal_encoding_fails_validation(tmp_path, monkeypatch):
    path = tmp_path/'normal.uexp'
    normal_texture(path)
    monkeypatch.setattr(surface, 'etc1', lambda *args: bytes(8))
    with pytest.raises(ValueError, match='not spatially neutral'):
        surface.neutralize(path, 'unused', tmp_path)


def stage_fixture(tmp_path):
    report, _, _ = source_fixture()
    for name in report['asset_hashes']:
        path = tmp_path/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'authored '+name.encode())
    instance = tmp_path/surface.FACE/'face_17.uasset'
    instance.write_bytes(header([surface.PARENT, surface.GAME+surface.PARENT]))
    hashes = surface.hash_tree(tmp_path)
    instance.write_bytes(header([surface.NEW_PARENT, surface.GAME+surface.NEW_PARENT]))
    for stem, suffixes in ((surface.NEW_PARENT, ('.uasset', '.uexp')),
                           (surface.NEW_NORMAL, ('.uasset', '.uexp', '.ubulk'))):
        for suffix in suffixes:
            path = tmp_path/surface.BASE/(stem+suffix)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'authored private resource')
    return hashes, report['players']


def test_material_only_patch_rejects_geometry_changes_or_global_overrides(tmp_path):
    hashes, players = stage_fixture(tmp_path)
    _, proof = surface.validate_stage(tmp_path, hashes, players)
    assert proof['per_player_files_identical'] == 11
    assert proof['mesh_files_byte_identical'] == 4
    mesh = tmp_path/surface.FACE/'17_face.uexp'
    original = mesh.read_bytes()
    mesh.write_bytes(original+b'unwanted geometry change')
    with pytest.raises(ValueError, match='Geometry'):
        surface.validate_stage(tmp_path, hashes, players)
    mesh.write_bytes(original)
    (tmp_path/surface.BASE/(surface.NORMAL+'.uexp')).write_bytes(b'unwanted global override')
    with pytest.raises(ValueError, match='global material override'):
        surface.validate_stage(tmp_path, hashes, players)


def test_native_shader_evidence_from_optional_local_fixture():
    path = Path(__file__).resolve().parents[1]/'local-debug/lamine-yamal-face-canary/audit-v8/native'/surface.BASE/(surface.PARENT+'.uexp')
    if not path.is_file():
        pytest.skip('Requires ignored local PES21 material fixture; regenerate from legally obtained runtime')
    if surface.sha(path) != surface.NATIVE_HASHES[surface.PARENT+'.uexp']:
        pytest.skip('Local material fixture is a different native revision')
    proof = surface.audit_native_shader(path)
    assert proof['unique_gles_pixel_shaders'] == 96
    assert proof['direct_same_uv_variants'] == 12
