"""Aggregate-only packet/art allowlists; optional ignored reviewed fixtures."""
from pathlib import Path
import sys
import struct

import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import refine_scoreboard_aggregate_v90 as tool
from afp_score_layout import read_movies,placements,swap_fields
from afp_texture_patch import read_atlas
from build_efootball10_scoreboard_v2 import region_bounds
from pack_runtime_assets import read_archive,checksum

STAGE=ROOT/'local-debug/presentation-v90/aggregate-01/candidate'
BEFORE=ROOT/'local-debug/presentation-v90/banner-01/candidate'


def fixture_packet(key):
    path=BEFORE/f'c{key}.nxsb'
    if not path.is_file():pytest.skip('reviewed ignored v90 lower-banner fixture required')
    return path.read_bytes()


def test_aggregate_plate_and_supported_cohort():
    image=tool.aggregate_plate()
    assert image.size==(144,32) and image.getextrema()[3]==(255,255)
    assert len(tool.KEYS)==len(set(tool.KEYS))==23
    assert tool.REGION==(0,464,144,496)


def test_target_binding_rejects_corruption():
    with pytest.raises(ValueError,match='truncated'):tool.patch_packet(b'',1000)
    packet=bytearray(fixture_packet(1000));packet[-1]^=1
    with pytest.raises(ValueError,match='target binding'):tool.patch_packet(packet,1000)


@pytest.mark.parametrize('key',tool.KEYS)
def test_all_native_aggregate_movie_allowlists(key):
    packet=fixture_packet(key);before=packet[tool.HEADER.size:]
    movies=read_movies(before);movie=next(m for m in movies if m.name==tool.MOVIE)
    output,report=tool.patch_movie(movie.data,key)
    mask=bytearray(len(output))
    for edit in report['edits']:
        mask[edit['offset']:edit['offset']+edit['bytes']]=b'\1'*edit['bytes']
    assert all(a==b or mask[i] for i,(a,b) in enumerate(zip(movie.data,output)))
    old,new=placements(movie.data),placements(output)
    assert len(old)==len(new)==534
    pairs={(28,52),(20,1),(20,6),(21,2)}
    for a,b in zip(old,new):
        if (a['parent'],a['depth']) not in pairs:assert a==b
        else:
            assert {k:v for k,v in a.items() if k!='translate'}=={k:v for k,v in b.items() if k!='translate'}
    assert swap_fields(swap_fields(output,movie.info),movie.info)==output
    # Native one/two-digit child scripts/transforms and shared clock glyphs stay exact.
    assert [r for r in old if r['parent'] in (16,19)]==[r for r in new if r['parent'] in (16,19)]
    assert any(r.get('source')==8 and r['parent']==21 for r in old)
    assert struct.unpack_from('<HH',output,tool.image_binding(movie.data))==(216,48)


def test_terminal_composed_archive_and_every_atlas_allowlist():
    final=STAGE/'ASSET-REPORT.json'
    if not final.is_file():pytest.skip('completed ignored aggregate candidate required')
    _,before=read_archive(BEFORE/'FootballNX.assets')
    _,after=read_archive(STAGE/'FootballNX.assets')
    expected={'scoreboards/c'+str(k)+'.nxsb' for k in tool.KEYS}
    assert set(before)==set(after)
    assert {n for n in before if before[n]!=after[n]}==expected
    assert before['scoreboards/banner-textures.nxsb']==after['scoreboards/banner-textures.nxsb']
    for key in tool.KEYS:
        packet=(STAGE/f'c{key}.nxsb').read_bytes();old=fixture_packet(key)
        h1,h2=tool.HEADER.unpack_from(old),tool.HEADER.unpack_from(packet)
        assert h1[:2]==h2[:2] and h1[3]==h2[3]
        assert h2[2]==len(packet)-tool.HEADER.size and checksum(packet[tool.HEADER.size:])==h2[4]
        a,regions,_=read_atlas(old[tool.HEADER.size:]);b,changed,_=read_atlas(packet[tool.HEADER.size:])
        pa=np.frombuffer(a[64:],np.uint8).reshape(512,1024,4)
        pb=np.frombuffer(b[64:],np.uint8).reshape(512,1024,4)
        mask=np.ones((512,1024),bool);mask[464:496,:144]=False
        assert np.array_equal(pa[mask],pb[mask])
        assert np.array_equal(pb[464:496,:144],np.asarray(tool.aggregate_plate())[:,:,[3,0,1,2]])
        for r,s in zip(regions,changed):
            if r['name']!=tool.PLATE:assert r==s
            else:assert region_bounds(s)==tool.REGION
        oldmovies=read_movies(old[tool.HEADER.size:]);newmovies=read_movies(packet[tool.HEADER.size:])
        for m,n in zip(oldmovies,newmovies):
            assert (m.name,m.size,m.info)==(n.name,n.size,n.info)
            if m.name!=tool.MOVIE:assert m.data==n.data
        assert tool.digest(next(m for m in newmovies if m.name=='game2d_scoreDemo').data)==tool.LOWER_SHA
