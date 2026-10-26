"""Native size admission and raw/AFP atlas growth regression coverage."""
from pathlib import Path
import hashlib
import shutil
import struct
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from afp_texture_patch import lzss_encode, read_atlas, replace_atlas
from build_footballnx27_scoreboard import HEADER
from pack_runtime_assets import checksum, read_archive
from repair_scoreboard_payload_v94 import BASELINE_SHA, repair_packet


def synthetic_txp():
    atlas = bytes(64+16*16*4)
    compressed = lzss_encode(atlas)
    result = bytearray(192+8+len(compressed))
    result[:4] = b'TXP2'
    struct.pack_into('>I',result,12,len(result))
    struct.pack_into('>III',result,20,4,1,108)
    struct.pack_into('>III',result,36,1,120,132)
    struct.pack_into('>III',result,108,176,8+len(compressed),192)
    struct.pack_into('>5H',result,120,0,0,0,16,16)
    struct.pack_into('>I',result,148,1)
    struct.pack_into('>I',result,156,160)
    struct.pack_into('>III',result,160,0,0,176)
    result[176:186] = b'synthetic\0'
    struct.pack_into('>II',result,192,len(atlas),len(compressed))
    result[200:] = compressed
    return bytes(result),atlas


@pytest.mark.parametrize('outer_bytes',(0,50))
def test_atlas_growth_keeps_each_length_field_in_its_own_byte_order(outer_bytes):
    txp,atlas = synthetic_txp()
    prefix = bytearray(outer_bytes)
    if prefix:
        prefix[:4]=b'AFP\0'
        struct.pack_into('<I',prefix,12,len(txp))
    source=bytes(prefix)+txp
    # Deterministic noise forces a longer compressed atlas and the growth path.
    noisy=atlas[:64]+b''.join(hashlib.sha256(struct.pack('<I',i)).digest() for i in range(32))
    output=replace_atlas(source,noisy,candidate_limit=4)
    assert read_atlas(output)[:2]==(noisy,read_atlas(source)[1])
    length=struct.unpack_from('>I',output,outer_bytes+12)[0]
    assert 0<=len(output)-outer_bytes-length<16
    if outer_bytes:
        assert struct.unpack_from('<I',output,12)[0]==length
    else:
        assert struct.unpack_from('<I',output,12)[0]!=length


def test_bounded_packet_repair_keeps_source_identity_and_rejects_other_damage():
    payload=bytearray(128)
    payload[:4]=b'TXP2'
    struct.pack_into('<I',payload,12,125)
    original=HEADER.pack(b'NXSB01\0\0',128,128,123,checksum(payload))+payload
    fixed=repair_packet(original)
    assert fixed[:12]==original[:12] and fixed[16:24]==original[16:24]
    assert HEADER.unpack_from(fixed)[2]==125
    assert struct.unpack_from('>I',fixed,44)[0]==125
    assert fixed[32:44]==original[32:44] and fixed[48:]==original[48:157]
    with pytest.raises(ValueError,match='already valid'):
        repair_packet(fixed)
    broken=bytearray(original);broken[-1]=1
    with pytest.raises(ValueError,match='identity'):
        repair_packet(broken)
    struct.pack_into('<Q',broken,24,checksum(broken[32:]))
    with pytest.raises(ValueError,match='measured'):
        repair_packet(broken)


def test_every_sealed_theme_is_accepted_by_the_actual_runtime_parser(tmp_path):
    baseline=Path('D:/PESNX-Cache/Deliveries/FootballNX27-v93-MANAGER-LEAGUE-PHASES-SIAP-COPY/switch/pes21_nx/FootballNX.assets')
    native=ROOT/'local-debug/scoreboard-v57/mobile-game2dPes.bin'
    compiler=shutil.which('gcc')
    if not baseline.is_file() or not native.is_file() or not compiler:
        pytest.skip('optional paired local v93 archive, original UI and host C compiler required')
    assert hashlib.sha256(baseline.read_bytes()).hexdigest()==BASELINE_SHA
    _,members=read_archive(baseline)
    executable=tmp_path/'payload.exe'
    subprocess.run([compiler,'-std=c11','-O2','-I',str(ROOT/'source'),
                    str(ROOT/'tests/test_fl26_scoreboard_payload.c'),'-o',str(executable)],check=True,capture_output=True)
    checked=0
    for name,packet in members.items():
        if not name.startswith('scoreboards/c') or not name.endswith('.nxsb'):
            continue
        repaired=repair_packet(packet)
        path=tmp_path/Path(name).name;path.write_bytes(repaired)
        before,after=packet[32:],repaired[32:]
        assert before[:12]==after[:12] and before[16:len(after)]==after[16:]
        assert not any(before[len(after):])
        subprocess.run([str(executable),str(native),str(path)],check=True,capture_output=True)
        checked+=1
    assert checked==23
