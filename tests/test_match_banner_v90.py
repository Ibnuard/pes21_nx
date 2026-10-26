"""Device-regression fixes use original alpha and actual native title fields."""
from pathlib import Path
import hashlib
import struct
import sys

import numpy as np
from PIL import Image,ImageFont
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import refine_match_banner_v90 as v90
from afp_score_layout import placements,read_movies
from afp_texture_patch import read_atlas
from build_footballnx27_banner_textures import wave_images


@pytest.fixture(scope="module")
def art():
    native=ROOT/"local-debug/scoreboard-v57/mobile-game2dPes.bin"
    packet=ROOT/"local-debug/footballnx27-lower-banner/patched/c0.nxsb"
    if not native.is_file() or not packet.is_file():
        pytest.skip("optional ignored accepted original/v89 banner fixtures required")
    original=native.read_bytes();before=packet.read_bytes()
    after,report=v90.patch_packet(before,original)
    return original,before,after,report


def test_original_rounded_alpha_restored_and_other_pixels_exact(art):
    original,before,after,report=art
    target,details=v90.plate_pixels(after[32:])
    native,_=v90.plate_pixels(original)
    np.testing.assert_array_equal(target[:,:,0],native[:,:,0])
    assert np.count_nonzero(target[:,:,0]==0)==142
    assert target[0,0,0]==target[-1,0,0]==0
    assert 0<target[0,14,0]<255 and target[64,100,0]==224
    old,(a,regions,pixels,(l,t,r,b))=v90.plate_pixels(before[32:])
    np.testing.assert_array_equal(target[:,:,1:],old[:,:,1:])
    other,after_regions,_=read_atlas(after[32:])
    assert a[:64]==other[:64] and regions==after_regions
    w,h=struct.unpack_from(">HH",other,16)
    new=np.frombuffer(other[64:],np.uint8).reshape(h,w,4)
    mask=np.zeros((h,w),bool);mask[t:b,l:r]=True
    np.testing.assert_array_equal(new[~mask],pixels[~mask])
    assert report["native_wave_clip_and_imports_exact"]


def test_only_native_competition_geometry_changes(art):
    _,before,after,report=art
    movies=read_movies(before[32:]);changed=read_movies(after[32:])
    for old,new in zip(movies,changed):
        assert (old.name,old.size,old.info)==(new.name,new.size,new.info)
        if old.name!=v90.MOVIE:
            assert old.data==new.data
            continue
        mask=bytearray(len(old.data))
        for edit in report["edits"]:mask[edit["offset"]:edit["offset"]+8]=b"\1"*8
        assert all(a==b or mask[i] for i,(a,b) in enumerate(zip(old.data,new.data)))
        for a,b in zip(placements(old.data),placements(new.data)):
            if (a["parent"],a["depth"])!=(22,20):
                assert a==b  # complete native vi mask/wave/crest/score tracks
                continue
            for key in a:
                if key not in ("scale","translate"):assert a[key]==b[key]
            if "translate" in a:
                assert b["translate"]==(a["translate"][0],a["translate"][1]+12)
            if "scale" in a:
                assert b["scale"]==(a["scale"][0],277/1024)
    assert report["minimum_visible_field_gap"]>=8
    assert report["settled_field_gap"]>=11.9
    bounds=report["geometry"]["competition"]
    assert abs((bounds[0]+bounds[2])/2-562)<.01
    assert abs(bounds[2]-bounds[0]-827.9947916666667)<.01
    assert bounds[1]==104 and bounds[3]<=123


def test_packet_source_binding_kept_and_unknown_movie_rejected(art):
    native,before,after,_=art
    assert before[:12]==after[:12] and before[16:24]==after[16:24]
    _,_,size,_,target=v90.HEADER.unpack_from(after)
    assert size==len(after)-32 and target==v90.checksum(after[32:])
    with pytest.raises(ValueError,match="accepted v89"):
        v90.patch_movie(b"unknown native revision")
    assert hashlib.sha256(native).hexdigest()==v90.MOBILE_SHA256


def test_host_preview_clips_actual_wave_pixels_at_rounded_corners(art):
    native,_,packet,_=art
    source=ROOT/"local-debug/footballnx27-lower-banner/patched/banner-textures.nxsb"
    if not source.is_file():pytest.skip("optional accepted shared-wave packet required")
    waves=wave_images(source.read_bytes()[32:])
    background=Image.new("RGB",(1280,720),(32,64,32))
    image=v90.preview(packet,native,background,waves,70,"UEFA CHAMPIONS LEAGUE")
    for x,y in ((78,548),(1201,548),(78,675),(1201,675)):
        assert image.getpixel((x,y))==(32,64,32)
    font_path=Path("C:/Windows/Fonts/arialbd.ttf")
    if font_path.is_file():
        font=ImageFont.truetype(str(font_path),round(20*277/399))
        # Full names stay in the original wide native field; no title truncation.
        assert font.getlength("THE CUSTODIAN OF THE TWO HOLY MOSQUES CUP")<828


def test_staged_cohort_keeps_shared_waves_and_all_other_assets():
    path=ROOT/"local-debug/presentation-v90/banner-01/candidate/ASSET-REPORT.json"
    if not path.is_file():pytest.skip("generate optional v90 banner stage first")
    import json
    report=json.loads(path.read_text())
    assert len(report["changed_members"])==23
    assert all(name.startswith("scoreboards/c") for name in report["changed_members"])
    assert "scoreboards/banner-textures.nxsb" in report["protected_members"]
    assert report["protected_members"]["scoreboards/banner-textures.nxsb"]=="b1d222e3e22815e5573030fa8b6ab67b5bb48f3a3622bcdf3ca8fead38dc108c"
    assert len(report["protected_members"])==1812
