"""Payload boundaries, native layout and own-source binding for adboard baking."""
from pathlib import Path
from types import SimpleNamespace
import sys

from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_fl26_adboards as boards


def test_quadrants_follow_native_slot_order_and_panel_aspect():
    colors = [(210, 10, 10), (10, 210, 10), (10, 10, 210), (210, 180, 10)]
    frames = [Image.new('RGB', (1536, 144), c) for c in colors]
    atlas, physical = boards.compose_atlas(frames)
    assert atlas.size == (512, 256)
    assert [p.size for p in physical] == [(509, 96)]*4
    for i, color in enumerate(colors):
        assert atlas.getpixel(((i%2)*256+128, (i//2)*128+64)) == color
    assert boards.SAMPLES[0]['frame'] < boards.SAMPLES[1]['frame'] < boards.SAMPLES[2]['frame'] < boards.SAMPLES[3]['frame']


@pytest.mark.parametrize('images', [[], [Image.new('RGB', (512,256))]*4,
                                    [Image.new('RGB', (1536,144))]*3])
def test_incompatible_source_layout_refused(images):
    with pytest.raises(ValueError, match='Four decoded'):
        boards.compose_atlas(images)


def test_all_splits_metadata_and_padding_remain_exact():
    before = dict(uexp=b'HEADER1234TAIL', ubulk=b'BULKabcdefghEND')
    mips = [SimpleNamespace(file='uexp', offset=6, size=4),
            SimpleNamespace(file='ubulk', offset=4, size=8)]
    after = dict(uexp=b'HEADER5678TAIL', ubulk=b'BULKABCDEFGHEND')
    boards.assert_payload_only(before, after, mips)
    after['uexp'] = b'hEADER5678TAIL'
    with pytest.raises(ValueError, match='metadata or padding'):
        boards.assert_payload_only(before, after, mips)


@pytest.mark.parametrize('changed', [dict(uexp=b'XYZ'), dict(uexp=b'ABCD', ubulk=b'X')])
def test_split_sizes_and_members_cannot_change(changed):
    with pytest.raises(ValueError, match='split'):
        boards.assert_payload_only(dict(uexp=b'ABCD'), changed, [])


def test_source_fingerprint_checked_without_copying_movie(tmp_path, monkeypatch):
    path = tmp_path/'owned.cpk'
    path.write_bytes(b'HEADERmovie-bodyTRAILER')
    row = dict(DirName='common/bg/model/bg/bill/p_global/movie',
               FileName='bill_p_global.usm', FileOffset=6, FileSize=10, ExtractSize=10)
    monkeypatch.setattr(boards, 'cpk_layout', lambda _: ({}, [row], 0))
    digest = boards.sha(b'movie-body')
    binding = boards.checked_source(path, digest)
    assert binding == dict(member=boards.SOURCE_MEMBER, offset=6, bytes=10, sha256=digest)
    assert path.read_bytes() == b'HEADERmovie-bodyTRAILER'
    with pytest.raises(ValueError, match='fingerprint mismatch'):
        boards.checked_source(path, '0'*64)
    row['ExtractSize'] = 20
    with pytest.raises(ValueError, match='compressed'):
        boards.checked_source(path, digest)


def test_wrong_native_revision_refused_before_output_created(tmp_path):
    member = tmp_path/'native'/boards.MEMBER
    member.parent.mkdir(parents=True)
    for suffix in boards.NATIVE_HASHES:
        member.with_suffix(suffix).write_bytes(b'not-the-native-asset')
    output = tmp_path/'output'
    with pytest.raises(ValueError, match='Native billboard revision'):
        boards.build(tmp_path/'native', Path('unused'), '0'*64, *([Path('unused')]*5), output)
    assert not output.exists()


def test_native_unrealpak_healthy_summary_is_exact_path_and_members():
    pak = Path('D:/local/own.pak')
    expected = {'a.uasset': 'hash', 'a.uexp': 'hash', 'a.ubulk': 'hash'}
    log = '\n'.join('LogPakFile: Display: "%s" OK. [Zlib]' % n for n in expected)
    log += '\nLogPakFile: Display: Pak file "%s" healthy, 3 files checked.' % pak
    assert boards.healthy_test_log(log, pak, expected)
    assert not boards.healthy_test_log(log, Path('D:/local/wrong.pak'), expected)
    assert not boards.healthy_test_log(log.replace('a.ubulk', 'unrelated.ubulk'), pak, expected)
    assert not boards.healthy_test_log(log.replace('3 files', '2 files'), pak, expected)
