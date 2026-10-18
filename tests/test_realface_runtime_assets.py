"""Runtime-regression audit must inspect every mip and reject changed input."""
from pathlib import Path
import struct
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from audit_realface_runtime_assets import texture_evidence, validate_manifest, sha, import_names
from cooked_texture import Texture


def test_import_fname_numeric_suffix_is_not_a_missing_dependency():
    data=bytearray(128)
    data[:4]=b'\xc1\x83\x2a\x9e'
    struct.pack_into('<i',data,28,5)
    names=['face','/Game/Assets/character/RealFace/face','Package']
    struct.pack_into('<ii',data,41,len(names),128)
    for name in names:
        raw=name.encode('ascii')+b'\0'
        data+=struct.pack('<i',len(raw))+raw+b'\0'*4
    struct.pack_into('<ii',data,65,3,len(data))
    for index,number in ((0,162115),(1,162115),(2,0)):
        data+=struct.pack('<7i',2,0,2,0,0,index,number)
    assert import_names(data)=={'face_162114','/Game/Assets/character/RealFace/face_162114','Package'}
    with pytest.raises(ValueError,match='truncated'):
        import_names(data[:-1])


def bgra_texture(folder, alphas):
    path = folder / 'sample.uexp'
    tag = b'PF_B8G8R8A8\0'
    size = 1 << (len(alphas) - 1)
    data = b'xxxx' + struct.pack('<4I', size, size, 1, len(tag)) + tag + struct.pack('<2I', 0, len(alphas))
    for i, a in enumerate(alphas):
        w = size >> i
        payload = bytes((40, 80, 120, a)) * (w * w)
        data += struct.pack('<4Iq', 1, 0x40, len(payload), len(payload), 0) + payload
        data += struct.pack('<3I', w, w, 1)
    path.write_bytes(data)
    return path


def test_distant_mask_disappearance_is_reported(tmp_path):
    result = texture_evidence(Texture(bgra_texture(tmp_path, [255, 120, 0])))
    assert result['fully_discarded_mips'] == [2]
    assert result['mips'][0]['visible_fraction_at_native_cutoff'] == 1
    assert result['mips'][2]['visible_fraction_at_native_cutoff'] == 0
    assert not result['every_mip_opaque']


def test_native_cutoff_boundary_and_all_mips_retained(tmp_path):
    result = texture_evidence(Texture(bgra_texture(tmp_path, [84, 85, 255])))
    assert result['fully_discarded_mips'] == [0]
    assert result['mip_count'] == 3
    assert result['gpu_payload_bytes'] == (16 + 4 + 1) * 4


def test_truncated_mip_payload_is_not_accepted(tmp_path):
    path = bgra_texture(tmp_path, [255, 255])
    path.write_bytes(path.read_bytes()[:-16])
    with pytest.raises((ValueError, struct.error)):
        Texture(path)


def test_manifest_detects_changed_missing_and_unexpected_files(tmp_path):
    (tmp_path / 'changed').write_bytes(b'original')
    digest = sha(tmp_path / 'changed')
    (tmp_path / 'changed').write_bytes(b'changed')
    (tmp_path / 'extra').write_bytes(b'payload')
    result = validate_manifest(tmp_path.resolve(), {'changed': digest, 'missing': digest})
    assert {(r['asset'], r['reason']) for r in result} == {
        ('changed', 'hash_mismatch'), ('missing', 'missing'), ('extra', 'unexpected')}


def test_manifest_cannot_read_outside_stage(tmp_path):
    with pytest.raises(ValueError, match='escapes'):
        validate_manifest(tmp_path.resolve(), {'../other': '0' * 64})
