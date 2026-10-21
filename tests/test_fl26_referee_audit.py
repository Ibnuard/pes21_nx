"""Synthetic hostile/truncated archive coverage; no game data is required."""
import struct

import pytest

from tools.audit_fl26_referee import gani_metadata, inspect_mtar


def gani(frames=30):
    data = bytearray(176)
    struct.pack_into("<III", data, 0, 201106130, 32, len(data))
    struct.pack_into("<Ib", data, 156, frames, 10)
    return bytes(data)


def mtar(entries):
    data = bytearray(32 + len(entries) * 16)
    struct.pack_into("<II", data, 0, 0x0BFFA89C, len(entries))
    for i, (key, payload) in enumerate(entries):
        struct.pack_into("<QII", data, 32 + i * 16, key, len(data), len(payload))
        data.extend(payload)
    return data


def test_full_64_bit_identity_and_unrequested_records():
    data = mtar([(0x1000000000001, gani()), (1, gani(40))])
    found = inspect_mtar(data, {1: "wanted"})
    assert set(found) == {"wanted"}
    assert found["wanted"]["frames"] == 40


def test_duplicate_motion_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        inspect_mtar(mtar([(1, gani()), (1, gani())]), {1: "wanted"})


@pytest.mark.parametrize("offset,size", [(0, 176), (47, 176), (48, 177), (300, 1), (48, 0)])
def test_mtar_payload_bounds(offset, size):
    data = mtar([(1, gani())])
    struct.pack_into("<II", data, 40, offset, size)
    with pytest.raises(ValueError, match="bounds"):
        inspect_mtar(data, {1: "wanted"})


@pytest.mark.parametrize("data", [b"", bytes(31), struct.pack("<II", 0, 1) + bytes(40),
                                  struct.pack("<II", 0x0BFFA89C, 100001) + bytes(40),
                                  struct.pack("<II", 0x0BFFA89C, 2) + bytes(40)])
def test_mtar_index_bounds(data):
    with pytest.raises(ValueError):
        inspect_mtar(data, {})


@pytest.mark.parametrize("frames", [1, 601])
def test_unsupported_timing(frames):
    with pytest.raises(ValueError, match="timing"):
        gani_metadata(gani(frames))


def test_clip_header_length_and_scale():
    data = bytearray(gani())
    struct.pack_into("<I", data, 8, len(data) + 1)
    with pytest.raises(ValueError, match="header"):
        gani_metadata(data)
    data = bytearray(gani())
    data[160] = 9
    with pytest.raises(ValueError, match="timing"):
        gani_metadata(data)
