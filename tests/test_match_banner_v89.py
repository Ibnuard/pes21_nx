"""Bounded lower-banner art, fixture-title and original-native ABI evidence."""
from pathlib import Path
import hashlib
import faulthandler
import shutil
import struct
import subprocess
import sys

import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import build_footballnx27_match_banner as banner
import build_footballnx27_banner_textures as wave
from afp_score_layout import placements,read_movies
from afp_texture_patch import read_atlas
from build_efootball10_scoreboard_v2 import region_bounds
from test_fixdemo_trophy_result import ELF_SHA256,Probe


@pytest.fixture(scope="module")
def art():
    path=ROOT/"local-debug/scoreboard-v57/mobile-game2dPes.bin"
    if not path.is_file():
        pytest.skip("optional ignored Mobile UI fixture required")
    before=path.read_bytes()
    after,report=banner.build(before)
    return before,after,report


def test_protected_movies_atlas_and_native_timeline(art):
    before,after,report=art
    movies=read_movies(before)
    for a,b in zip(movies,read_movies(after)):
        assert (a.name,a.size,a.info)==(b.name,b.size,b.info)
        if a.name != banner.MOVIE:
            assert a.data==b.data
            continue
        old,new=placements(a.data),placements(b.data)
        for x,y in zip(old,new):
            for key in x:
                if key not in ("mult8","flags"):
                    assert x[key]==y[key]
            if x["parent"] != 22 or x["depth"] not in banner.TEXT_DEPTHS:
                assert x==y  # includes all six complete native wave tracks
        mask=bytearray(len(a.data))
        for change in report["edits"]:
            mask[change["offset"]:change["offset"]+4]=b"\1"*4
        assert all(x==y or mask[i] for i,(x,y) in enumerate(zip(a.data,b.data)))
    a,regions,_=read_atlas(before)
    b,other,_=read_atlas(after)
    assert regions==other and a[:64]==b[:64]
    w,h=struct.unpack_from(">HH",a,16)
    x=np.frombuffer(a[64:],np.uint8).reshape(h,w,4)
    y=np.frombuffer(b[64:],np.uint8).reshape(h,w,4)
    mask=np.zeros((h,w),bool)
    for region in regions:
        if region["name"]==banner.PLATE:
            l,t,r,bottom=region_bounds(region);mask[t:bottom,l:r]=True
    np.testing.assert_array_equal(x[~mask],y[~mask])
    assert len(report["protected_movies"])==7


def test_packet_source_identity_and_key0_top_scorebar_exact(art):
    original,_,_=art
    packet,report=banner.default_packet(original)
    magic,size,target,source_hash,target_hash=banner.HEADER.unpack_from(packet)
    assert magic==b"NXSB01\0\0" and size==len(banner.txp(original))
    assert source_hash==banner.checksum(banner.txp(original))
    assert target==len(packet)-32 and target_hash==banner.checksum(packet[32:])
    score=lambda p:next(x.data for x in read_movies(p) if x.name=="game2d_score")
    assert score(original)==score(packet[32:])
    malformed=bytearray(packet);malformed[-1]^=1
    with pytest.raises(ValueError,match="binding"):
        banner.patch_packet(bytes(malformed))


def test_each_current_top_theme_and_all_other_movies_protected():
    base=ROOT/"local-debug/footballnx27-lower-banner"
    originals=sorted((base/"current-packets").glob("*.nxsb"))
    if not originals:
        pytest.skip("optional current scoreboard packet fixtures required")
    for path in originals:
        changed=base/"patched"/path.name
        if not changed.is_file():
            pytest.skip("generate current patched packet cohort first")
        a,b=path.read_bytes(),changed.read_bytes()
        assert a[:12]==b[:12] and a[16:24]==b[16:24]
        for old,new in zip(read_movies(a[32:]),read_movies(b[32:])):
            assert (old.name,old.info,old.size)==(new.name,new.info,new.size)
            if old.name!=banner.MOVIE:
                assert old.data==new.data


def test_clean_white_edges_and_balanced_native_fields(art):
    _,after,_=art
    image=np.asarray(banner.half_plate())
    assert np.all(image[:,:,:3]==255) and np.all(image[:,:,3]==255)
    movie=next(m.data for m in read_movies(after) if m.name==banner.MOVIE)
    imports=banner.image_imports(movie)
    assert imports[7]["name"]=="hudTexPes-waves-5"
    assert imports[12]["name"]=="hudTexPes-waves-0"
    assert imports[13]["exported_size"]==[843,192]
    g=banner.geometry(movie)
    def cx(key):return (g[key][0]+g[key][2])/2
    def cy(key):return (g[key][1]+g[key][3])/2
    assert abs(g["home_crest"][0]-(1124-g["away_crest"][2]))<.01
    assert abs(cx("home_crest")+cx("away_crest")-1124)<.01
    assert abs(cx("home_name")+cx("away_name")-1124)<.02
    assert abs((cx("home_score")+cx("away_score"))/2-562)<.01
    assert abs(cx("competition")-562)<.01
    fields=("home_crest","away_crest","home_name","away_name","home_score","away_score")
    assert max(cy(k) for k in fields)-min(cy(k) for k in fields)<.02
    # Original image import tags put waves0..2 at the RIGHT and waves3..5
    # at the LEFT; avoid an inferred/reversed index mapping.
    right=wave.WAVES["hudTexPes-waves-0"]
    left=wave.WAVES["hudTexPes-waves-5"]
    assert right[2]>right[0] and left[0]>left[2]


def test_wave_pixels_alpha_and_import_tables_exact():
    path=ROOT/"local-debug/footballnx27-lower-banner/mobile-licenceTexturePes.bin"
    if not path.is_file():
        pytest.skip("optional ignored compatible licenceTexturePes fixture required")
    original=path.read_bytes()
    packet,report=wave.build(original)
    assert len(report["regions"])==6
    a=wave.read(original);b=wave.read(packet[32:])
    assert len(packet)<2_000_000 and report["all_alpha_exact"]
    assert a[5]==b[5]
    for index,(x,y) in enumerate(zip(a[3],b[3])):
        assert x[:64]==y[:64]
        w,h=struct.unpack_from(">HH",x,16)
        x=np.frombuffer(x[64:],np.uint8).reshape(h,w,4)
        y=np.frombuffer(y[64:],np.uint8).reshape(h,w,4)
        mask=np.zeros((h,w),bool)
        for region in a[5]:
            if region["rect"][0]!=index or region["name"] not in wave.WAVES:
                continue
            l,t,r,bottom=region_bounds(region);mask[t:bottom,l:r]=True
            np.testing.assert_array_equal(y[t:bottom,l:r,1:],wave.wave_rgb(region["name"],r-l,bottom-t))
            rgb=y[t:bottom,l:r,1:]
            wave_index=int(region["name"].rsplit("-",1)[1])
            if wave_index<3:
                assert np.all(rgb[:,:,2]==255)
                assert np.all(rgb[:,:,0]<=rgb[:,:,1]) and np.all(rgb[:,:,1]<=rgb[:,:,2])
            else:
                assert np.all(rgb[:,:,0]>=rgb[:,:,2]) and np.all(rgb[:,:,2]>=rgb[:,:,1])
        np.testing.assert_array_equal(x[:,:,0],y[:,:,0])
        np.testing.assert_array_equal(x[~mask],y[~mask])
    # Metadata before first atlas is byte-identical except two compressed
    # offset/length entries and declared TXP2 size; no imports are redirected.
    first=min(x[2] for x in a[4]);allowed=set(range(12,16))
    for index in range(2):allowed.update(range(a[2]+index*12+4,a[2]+index*12+12))
    assert all(x==y or i in allowed for i,(x,y) in enumerate(zip(a[1][:first],b[1][:first])))


def test_layered_wave_rgb_gradient_keeps_text_side_light():
    for index in range(6):
        name=f"hudTexPes-waves-{index}"
        rgb=wave.wave_rgb(name,256,4)
        outside,inside=(rgb[0,-1],rgb[0,0]) if index<3 else (rgb[0,0],rgb[0,-1])
        assert np.all(inside>=outside)
        if index in (0,3):
            np.testing.assert_array_equal(outside,wave.WAVES[name])
        assert np.any(inside>outside)
        assert rgb.min()>=0 and rgb.max()<=255
    assert wave.WAVE_STRENGTHS==(1.0,.55,.22,1.0,.55,.22)


def test_actual_fixture_title_callback_and_borrowed_string(tmp_path):
    compiler=shutil.which("gcc") or shutil.which("clang")
    if not compiler:pytest.skip("host C compiler required")
    harness=r'''
#define _GNU_SOURCE
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <assert.h>
static int ml,cup,league,original_calls,set_calls;
static const char *ml_name="UEFA CHAMPIONS LEAGUE",*cup_name="COPPA ITALIA",*league_name="SERIE A";
static unsigned char screen[128],root[256];
static int ml_frontend_match_active(void){return ml;}
static int competition_frontend_cup_match_active(void){return cup;}
static int competition_frontend_league_match_active(void){return league;}
static const char *ml_frontend_match_competition_name(void){return ml_name;}
static const char *competition_frontend_cup_name(void){return cup_name;}
static const char *competition_frontend_league_name(void){return league_name;}
#define PESNX_MATCH_BANNER_HOST_TEST
#include "match_banner_runtime.inc"
static const char *borrow(const unsigned char *v,size_t *length){
 if(v[0]&1){const char *p;uint64_t n;memcpy(&n,v+8,8);memcpy(&p,v+16,8);*length=n;return p;}
 *length=v[0]>>1;return (const char *)v+1;
}
static void original(void *s){++original_calls;if(s){void *p=root;memcpy((char *)s+0x10,&p,8);}}
static void set(void *s,void *holder,const void *key,const void *value){
 assert(original_calls>set_calls && s==screen && holder==root+0x90);size_t n;
 const char *p=borrow(key,&n);assert(n==15&&!memcmp(p,"competitionName",15));
 p=borrow(value,&n);assert(strlen(match_banner_competition_name())==n);
 assert(!memcmp(p,match_banner_competition_name(),n));++set_calls;
}
int main(void){
 match_banner_setup_original=original;match_banner_set_text=set;
 for(unsigned bits=0;bits<8;++bits){ml=bits&1;cup=bits&2;league=bits&4;
  const char *expected=ml?ml_name:cup?cup_name:league?league_name:"Exhibition";
  assert(!strcmp(match_banner_competition_name(),expected));
  memset(screen,0,sizeof(screen));match_banner_setup(screen);
 }
 assert(original_calls==8&&set_calls==8);
 unsigned char value[24];char long_text[256];memset(long_text,'A',255);long_text[255]=0;
 for(unsigned n=1;n<=255;++n){long_text[n]=0;assert(match_banner_borrow_string(value,long_text));
  size_t length;const char *p=borrow(value,&length);assert(length==n&&!memcmp(p,long_text,n));long_text[n]='A';}
 long_text[255]=0;assert(match_banner_borrow_string(value,long_text));
 assert(!match_banner_borrow_string(value,NULL)&&!match_banner_borrow_string(value,""));
 char oversized[257];memset(oversized,'x',256);oversized[256]=0;assert(!match_banner_borrow_string(value,oversized));
 return 0;
}
'''
    path,exe=tmp_path/"banner.c",tmp_path/"banner.exe"
    path.write_text(harness,encoding="utf-8")
    built=subprocess.run([compiler,"-std=c11","-Wall","-Wextra","-Werror","-I",str(ROOT/"source"),str(path),"-o",str(exe)],capture_output=True,text=True,timeout=60)
    assert built.returncode==0,built.stdout+built.stderr
    ran=subprocess.run([str(exe)],capture_output=True,text=True,timeout=10)
    assert ran.returncode==0,ran.stdout+ran.stderr


def test_master_league_title_uses_pending_fixture_without_mutation(tmp_path):
    from test_gameplan_editor import function
    compiler=shutil.which("gcc") or shutil.which("clang")
    if not compiler:pytest.skip("host C compiler required")
    production=function((ROOT/"source/master_league_frontend.c").read_text(encoding="utf-8"),
                        "ml_frontend_match_competition_name")
    harness=r'''
#include <assert.h>
#include <string.h>
#include <stdint.h>
enum { ML_EVENT_NONE,ML_EVENT_LEAGUE,ML_EVENT_CUP,ML_EVENT_CONTINENTAL,ML_EVENT_FRIENDLY,ML_EVENT_QUALIFIER,ML_EVENT_WORLD_CUP,ML_EVENT_REGIONAL,ML_EVENT_SEASON_END };
static int match_active,plan_editor;
static struct { unsigned kind; } pending;
static struct { unsigned char bytes[4096]; } career;
static int ml_event_is_match(unsigned kind){return kind>ML_EVENT_NONE&&kind<ML_EVENT_SEASON_END;}
static const char *ml_world_name(const void *c,unsigned kind){assert(c==&career);return kind==ML_EVENT_FRIENDLY?"PRESEASON FRIENDLY":kind==ML_EVENT_QUALIFIER?"WORLD CUP QUALIFIERS":kind==ML_EVENT_WORLD_CUP?"WORLD CUP":kind==ML_EVENT_REGIONAL?"UEFA EURO":"UEFA CHAMPIONS LEAGUE";}
static const char *ml_cup_name(void){return "COPPA ITALIA";}
static const char *ml_competition_name(void){return "SERIE A";}
'''+production+r'''
int main(void){
 memset(&career,0x37,sizeof(career));unsigned char before[sizeof(career)];memcpy(before,&career,sizeof(career));
 for(unsigned active=0;active<2;++active)for(unsigned editor=0;editor<2;++editor)
  for(unsigned kind=ML_EVENT_NONE;kind<=ML_EVENT_SEASON_END;++kind){
   match_active=active;plan_editor=editor;pending.kind=kind;
   const char *name=ml_frontend_match_competition_name();
   const char *expected=!active||editor||!ml_event_is_match(kind)?"":kind>=ML_EVENT_CONTINENTAL?ml_world_name(&career,kind):kind==ML_EVENT_CUP?ml_cup_name():ml_competition_name();
   assert(!strcmp(name,expected)&&!memcmp(before,&career,sizeof(career)));
   assert(match_active==(int)active&&plan_editor==(int)editor&&pending.kind==kind);
  }
 return 0;
}
'''
    path,exe=tmp_path/"ml-banner.c",tmp_path/"ml-banner.exe"
    path.write_text(harness,encoding="utf-8")
    built=subprocess.run([compiler,"-std=c11","-Wall","-Wextra","-Werror",str(path),"-o",str(exe)],capture_output=True,text=True,timeout=60)
    assert built.returncode==0,built.stdout+built.stderr
    ran=subprocess.run([str(exe)],capture_output=True,text=True,timeout=10)
    assert ran.returncode==0,ran.stdout+ran.stderr


def test_native_title_abi_original_setter_execution():
    path=ROOT/"dist/pes21_nx/libUE4.so"
    if not path.is_file():pytest.skip("compatible ignored native library required")
    ELFFile=pytest.importorskip("elftools.elf.elffile").ELFFile
    pytest.importorskip("unicorn");pytest.importorskip("capstone")
    setup="_ZN7match2D6Screen15DemoScoreVersus9SetupInfoEv"
    setter="_ZN7match2D6Screen4Base15SetTextByStringEPN10menusystem14NodeRectHolderERKN5cobra3stl12basic_stringIcNSt6__ndk111char_traitsIcEENS6_9AllocatorIcEEEESF_"
    with path.open("rb") as stream:
        assert hashlib.file_digest(stream,"sha256").hexdigest()==ELF_SHA256
        stream.seek(0);elf=ELFFile(stream)
        syms=elf.get_section_by_name(".dynsym");strings=elf.get_section(syms["sh_link"]).data();rows=list(struct.iter_unpack("<IBBHQQ",syms.data()))
        def name(i):
            start=rows[i][0];return strings[start:strings.find(b"\0",start)].decode("ascii","replace")
        names={name(i):(r[4],r[5]) for i,r in enumerate(rows) if r[4]}
        def read(a,n):stream.seek(next(elf.address_offsets(a,n)));return stream.read(n)
        code={setup:read(0x7cbf944,0x394),setter:read(0x7cb86ec,0x64)}
        assert names[setup]==(0x7cbf944,0x394) and names[setter]==(0x7cb86ec,0x64)
        assert hashlib.sha256(code[setup]).hexdigest()=="214a4a41ef5ea8614a5417dcd2db6addfbe74daca9569b9adce4389248b80544"
        assert hashlib.sha256(code[setter]).hexdigest()=="25ac03b3ebe2512715d399f4bb41ece30d677700cf991b661784aa2e486e6f3a"
        vtable=names["_ZTVN7match2D6Screen15DemoScoreVersusE"][0]
        relocs=list(struct.iter_unpack("<QQq",elf.get_section_by_name(".rela.dyn").data()))
        assert any(o==vtable+20*8 and name(i>>32)==setup for o,i,a in relocs)
        plt=elf.get_section_by_name(".plt")["sh_addr"]
        calls={plt+32+i*16:name(r[1]>>32) for i,r in enumerate(struct.iter_unpack("<QQq",elf.get_section_by_name(".rela.plt").data()))}
        contract={"symbols":{setter:names[setter]},"code":{setter:code[setter]},"calls":calls,"constants":{}}
    holder,table,text,key,value=(Probe.BASE+x for x in (0x1000,0x2000,0x3000,0x4000,0x5000))
    count=[]
    def callback(probe,name,args):
        if name=="indirect:0x1230":
            assert args[0]==holder and bytes(probe.vm.mem_read(args[1],16))==b"competitionName\0";return text
        if name=="_ZNK10menusystem12NodeRectText10GetFontStrEv":
            assert args[0]==text;return Probe.BASE+0x6000
        assert name=="_ZN10menusystem12NodeRectText6SetStrERKN5cobra3stl12basic_stringIcNSt6__ndk111char_traitsIcEENS2_9AllocatorIcEEEE"
        assert args[:2]==(text,value);count.append(1)
    # Windows Unicorn uses a handled SEH probe while allocating its JIT
    # mappings. Python's faulthandler otherwise prints a misleading fatal
    # traceback for that internally handled exception. Assertions still run.
    faults=faulthandler.is_enabled()
    faulthandler.disable()
    try:
        probe=Probe(contract,setter,callback)
        probe.put(holder,table);probe.put(table+16,0x1230)
        probe.vm.mem_write(key,b"\x1ecompetitionName\0"+b"\0"*7)
        probe.vm.mem_write(value,b"\x14Exhibition\0"+b"\0"*12)
        probe.run(Probe.BASE+0x7000,holder,key,value)
    finally:
        if faults:faulthandler.enable()
    assert count==[1]
    source=(ROOT/"source/match_banner_runtime.inc").read_text()
    assert "memcmp((void *)setup_rw" in source and "memcmp((void *)setter_rw" in source
    assert "memcmp((void *)setup," not in source and "memcmp((void *)setter," not in source
