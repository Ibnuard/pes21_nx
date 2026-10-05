from pathlib import Path
import struct
import shutil
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from package_loose_update import check_nro_payload, package_update
from prepare_loose_cpk import FULL_NAMES, PATCH_OBB, digest, extract_full, update, verify, write_manifest
from test_loose_cpk import cpk

BUILD = '0123456789abcdef'


def executable():
    data = bytearray(768)
    data[16:20] = b'NRO0'
    struct.pack_into('<I', data, 24, len(data))
    for header, offset in zip((32, 40, 48), (0, 256, 512)):
        struct.pack_into('<II', data, header, offset, 256)
    value = BUILD.encode() + b'\0'
    data[300:300 + len(value)] = value
    loads = [(offset, bytes(data[offset:offset + 256])) for offset in (0, 256, 512)]
    return data, (300, value), loads


def test_nro_is_matched_to_actual_compiled_symbol_and_all_load_segments():
    data, symbol, loads = executable()
    check_nro_payload(data, BUILD, symbol, loads)
    # Conversion-only bytes are allowed to differ.
    data[100] ^= 1
    check_nro_payload(data, BUILD, symbol, loads)
    for offset in (150, 450, 600):
        corrupt = bytearray(data)
        corrupt[offset] ^= 1
        with pytest.raises(ValueError, match='does not match'):
            check_nro_payload(corrupt, BUILD, symbol, loads)


def test_nro_rejects_old_build_even_if_new_id_occurs_in_appended_asset():
    data, symbol, loads = executable()
    data.extend(b'fedcba9876543210\0')
    with pytest.raises(ValueError, match='build ID'):
        check_nro_payload(data, 'fedcba9876543210', symbol, loads)


@pytest.mark.parametrize('kind', ['magic', 'size', 'segments', 'address'])
def test_nro_rejects_invalid_headers_and_elf_layout(kind):
    data, symbol, loads = executable()
    if kind == 'magic':
        data[16:20] = b'NOPE'
    elif kind == 'size':
        struct.pack_into('<I', data, 24, 900)
    elif kind == 'segments':
        struct.pack_into('<I', data, 40, 240)
    else:
        loads[1] = (250, loads[1][1])
    with pytest.raises(ValueError):
        check_nro_payload(data, BUILD, symbol, loads)


@pytest.fixture
def packages(tmp_path):
    source = tmp_path / 'source.obb'
    source.write_bytes(cpk({name: cpk({'asset': name.encode()}) for name in FULL_NAMES}))
    baseline, intermediate, candidate = [tmp_path / n for n in ('base', 'intermediate', 'candidate')]
    for index, path in enumerate((baseline, intermediate, candidate)):
        extract_full(source, path, f'{index + 1:016x}')
    replacement = tmp_path / 'replacement.cpk'
    replacement.write_bytes(cpk({'asset': b'updated portraits'}))
    for path in (intermediate, candidate):
        update(path, 'dt241_mobile_all.cpk', replacement)
    replacement.write_bytes(cpk({'asset': b'updated lineups'}))
    update(candidate, 'dt200_mobile_all.cpk', replacement)
    for name in ('pes21_nx.nro', 'pes21_nx.elf', 'audit.json', 'roster-master.db'):
        (candidate / name).write_bytes(name.encode())
    nro = candidate / 'pes21_nx.nro'
    # The ELF/NRO byte checks above are independent of package selection/copy.
    with patch('package_loose_update.verify_nro', return_value=dict(
            size=nro.stat().st_size, sha256=digest(nro))):
        yield baseline, intermediate, candidate


def test_payload_contains_only_union_of_required_install_files(packages, tmp_path):
    baseline, intermediate, candidate = packages
    before = [verify(path) for path in packages]
    output = tmp_path / 'copy-ready'
    result = package_update(candidate, [baseline, intermediate], output)
    expected = {'pes21_nx.nro', 'LooseCpk/dt200_mobile_all.cpk',
                'LooseCpk/dt241_mobile_all.cpk', 'LooseCpk/manifest.txt'}
    assert {p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()} == expected
    assert result['supported_baseline_build_ids'] == ['0000000000000001', '0000000000000002']
    for row in result['files']:
        assert digest(output / row['path']) == row['sha256']
    assert [verify(path) for path in packages] == before
    for index, source in enumerate((baseline, intermediate)):
        installed = tmp_path / f'installed-{index}'
        shutil.copytree(source, installed)
        shutil.copytree(output, installed, dirs_exist_ok=True)
        assert verify(installed) == before[2]


def test_changed_dummy_is_included_when_a_baseline_requires_it(packages, tmp_path):
    baseline, _, candidate = packages
    manifest = verify(candidate)
    dummy = candidate / PATCH_OBB
    dummy.write_bytes(dummy.read_bytes() + b'\0' * 16)
    manifest.update(parent_obb_bytes=dummy.stat().st_size, parent_obb_sha256=digest(dummy))
    write_manifest(candidate, manifest)
    output = tmp_path / 'copy-ready'
    result = package_update(candidate, [baseline], output)
    assert any(row['path'] == PATCH_OBB for row in result['files'])
    assert (output / PATCH_OBB).read_bytes() == dummy.read_bytes()


def test_delta_does_not_include_already_installed_portraits(packages, tmp_path):
    _, intermediate, candidate = packages
    output = tmp_path / 'copy-ready'
    result = package_update(candidate, [intermediate], output)
    assert len(result['files']) == 3
    assert not (output / 'LooseCpk/dt241_mobile_all.cpk').exists()
    assert not (output / PATCH_OBB).exists()


def test_refuses_existing_output_nested_output_and_missing_baseline(packages, tmp_path):
    baseline, _, candidate = packages
    with pytest.raises(FileExistsError):
        package_update(candidate, [baseline], baseline)
    with pytest.raises(ValueError, match='outside'):
        package_update(candidate, [baseline], candidate / 'copy-ready')
    with pytest.raises(ValueError, match='baseline'):
        package_update(candidate, [], tmp_path / 'copy-ready')


def test_rejects_header_native_would_not_accept(packages, tmp_path):
    baseline, _, candidate = packages
    manifest = candidate / 'LooseCpk/manifest.txt'
    manifest.write_bytes(b' ' + manifest.read_bytes())
    with pytest.raises(ValueError, match='canonical native'):
        package_update(candidate, [baseline], tmp_path / 'copy-ready')
    assert not (tmp_path / 'copy-ready').exists()


def test_rejects_corruption_or_binary_mismatch_before_publishing(packages, tmp_path):
    baseline, _, candidate = packages
    with patch('package_loose_update.verify_nro', side_effect=ValueError('build ID mismatch')):
        with pytest.raises(ValueError, match='build ID'):
            package_update(candidate, [baseline], tmp_path / 'copy-ready')
    (baseline / 'LooseCpk/dt200_mobile_all.cpk').write_bytes(b'bad')
    with pytest.raises(ValueError, match='corrupt'):
        package_update(candidate, [baseline], tmp_path / 'copy-ready')
    assert not (tmp_path / 'copy-ready').exists()
