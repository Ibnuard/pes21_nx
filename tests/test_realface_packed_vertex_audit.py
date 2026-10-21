"""Synthetic byte layouts only; no proprietary cooked fixture required."""
from pathlib import Path
import struct
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from realface_packed_vertex_audit import audit_core_streams


def fixture(*, distinct=None, full=False, high=False, extra=False, channels=1,
            unused=False, bad_index=False, nonfinite=None, index_size=2):
    count = 4 if unused else 3
    positions = [(1., 2., 3.), (1., 2., 3.), (4., 5., 6.), (7., 8., 9.)][:count]
    if distinct == 'position': positions[1] = (1.1, 2., 3.)
    if nonfinite == 'position': positions[0] = (float('nan'), 2., 3.)
    indices = [0, 1, 99 if bad_index else 2]
    data = bytearray(b'synthetic-independent-prefix')
    data += bytes([index_size]) + struct.pack('<II3' + ('H' if index_size == 2 else 'I'),
                                             index_size, 3, *indices)
    data += struct.pack('<IH', 1, 0) + struct.pack('<I3H', 3, 0, 1, 2)
    data += struct.pack('<4I', 12, count, 12, count)
    for row in positions: data += struct.pack('<3f', *row)
    data += b'\x01\x00' + struct.pack('<4I', channels, count, int(full), int(high))
    stride = 16 if high else 8
    data += struct.pack('<II', stride, count)
    for i in range(count):
        value = bytearray([127] * stride)
        if i == 1 and distinct == 'normal': value[-2] = 126
        if i == 1 and distinct == 'tangent': value[0] = 126
        if i == 1 and distinct == 'handedness': value[-1] = 0
        data += value
    stride = 8 if full else 4
    data += struct.pack('<II', stride, count * channels)
    for i in range(count):
        for channel in range(channels):
            uv = (.25, .5)
            if i == 1 and distinct == 'uv' and channel == channels-1: uv = (.75, .5)
            if i == 0 and nonfinite == 'uv': uv = (float('inf'), .5)
            data += struct.pack('<2f' if full else '<2e', *uv)
    data += b'\x01\x00' + struct.pack('<II', int(extra), count)
    influences = 8 if extra else 4
    data += struct.pack('<II', influences*2, count)
    for i in range(count):
        bones = bytearray(influences); weights = bytearray([255] + [0]*(influences-1))
        if i == 1 and distinct == 'bone': bones[0] = 1
        if i == 1 and distinct == 'weight': weights[0:2] = b'\x80\x7f'
        data += bones + weights
    data += b'unknown-additional-semantics-not-authorized'
    return bytes(data), count


def test_equal_core_records_never_authorize_merge():
    raw, n = fixture()
    result = audit_core_streams(raw, n, 1)
    assert result['duplicate_core_vertices'] == 1
    assert result['duplicate_core_group_sizes'] == [2]
    assert not result['no_exact_full_record_merge_possible']
    assert not result['additional_vertex_semantics_verified']
    assert not result['merge_authorized'] and not result['data_changed']
    assert result['index_buffer']['referenced_vertices'] == n


@pytest.mark.parametrize('attribute', ['position', 'normal', 'tangent', 'handedness', 'uv', 'bone', 'weight'])
def test_every_stored_core_attribute_preserves_its_seam(attribute):
    raw, n = fixture(distinct=attribute)
    result = audit_core_streams(raw, n, 1)
    assert result['duplicate_core_vertices'] == 0
    assert result['no_exact_full_record_merge_possible']
    assert not result['merge_authorized']


@pytest.mark.parametrize('full,high,extra,channels', [(True, False, False, 1), (False, True, False, 1),
                                                   (False, False, True, 1), (False, False, False, 2)])
def test_supported_precisions_and_all_uv_weight_channels(full, high, extra, channels):
    raw, n = fixture(full=full, high=high, extra=extra, channels=channels, distinct='uv')
    result = audit_core_streams(raw, n, 1)
    assert result['uv_channels'] == channels
    assert result['full_precision_uvs'] == full
    assert result['high_precision_tangent_basis'] == high
    assert result['extra_bone_influences'] == extra
    assert result['duplicate_core_vertices'] == 0


def test_unreferenced_vertex_is_reported_without_authorizing_removal():
    raw, n = fixture(unused=True)
    result = audit_core_streams(raw, n, 1)
    assert result['index_buffer']['unused_vertices'] == 1
    assert not result['merge_authorized']


@pytest.mark.parametrize('size', [2, 4])
def test_primary_index_precision_is_read_from_its_bound_header(size):
    raw, n = fixture(index_size=size)
    result = audit_core_streams(raw, n, 1)
    assert result['index_buffer']['index_size'] == size
    assert result['index_buffer']['referenced_vertices'] == n
    assert not result['merge_authorized']


def test_invalid_skin_weight_sum_rejected():
    raw, n = fixture()
    result = audit_core_streams(raw, n, 1)
    offset = result['spans']['bone_indices_weights']['offset']
    broken = bytearray(raw)
    broken[offset + 4] = 254
    with pytest.raises(ValueError): audit_core_streams(bytes(broken), n, 1)


@pytest.mark.parametrize('kind', ['position', 'uv'])
def test_nonfinite_streams_rejected(kind):
    raw, n = fixture(nonfinite=kind)
    with pytest.raises(ValueError): audit_core_streams(raw, n, 1)


def test_index_range_and_expected_triangle_count_are_bound():
    raw, n = fixture(bad_index=True)
    with pytest.raises(ValueError): audit_core_streams(raw, n, 1)
    raw, n = fixture()
    with pytest.raises(ValueError): audit_core_streams(raw, n, 2)


def test_ambiguous_or_truncated_chains_rejected():
    raw, n = fixture()
    with pytest.raises(ValueError): audit_core_streams(raw+raw, n, 1)
    with pytest.raises(ValueError): audit_core_streams(raw[:70], n, 1)


@pytest.mark.parametrize('n,t', [(0, 1), (3, 0), (True, 1), (3, True), (65536, 1)])
def test_expected_counts_are_bounded(n, t):
    with pytest.raises(ValueError): audit_core_streams(b'', n, t)
