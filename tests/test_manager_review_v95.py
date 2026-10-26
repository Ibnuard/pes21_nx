"""Device-feedback regressions: single-team ownership and isolated mixer route."""
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools')]
from test_gameplan_editor import function
from stage_indonesia_commentary import Utf
from repair_manager_league_audio import repair


def test_manager_office_is_single_owner_even_after_a_two_player_session(tmp_path):
    cc=shutil.which('gcc')
    if not cc:pytest.skip('Host C compiler unavailable')
    actual=function((ROOT/'source/ue4_hooks.c').read_text(),'pes_controller_exhibition_single_controller_mode')
    code='''
#include <assert.h>
#include <stdint.h>
static int manager,live_gameplan_open_requested,live_match_single_controller;
static void *live_gameplan_window;
static uint32_t exhibition_session_active,native_gamepad_lab_two_player;
static uint32_t main_menu_2p_prematch_hub_active,exhibition_gameplan_custom_active;
static int manager_dummy_plan_editor(void){return manager;}
'''+actual+'''
int main(void){
 native_gamepad_lab_two_player=1;manager=1;
 assert(pes_controller_exhibition_single_controller_mode());
 manager=0;assert(!pes_controller_exhibition_single_controller_mode());
 native_gamepad_lab_two_player=0;exhibition_session_active=exhibition_gameplan_custom_active=1;
 assert(pes_controller_exhibition_single_controller_mode());
 live_gameplan_open_requested=1;assert(!pes_controller_exhibition_single_controller_mode());
 live_match_single_controller=1;assert(pes_controller_exhibition_single_controller_mode());
 return 0;
}
'''
    source=tmp_path/'ownership.c';source.write_text(code);exe=source.with_suffix('.exe')
    ran=subprocess.run([cc,'-std=c11','-Wall','-Wextra','-Werror',str(source),'-o',str(exe)],capture_output=True)
    assert ran.returncode==0,ran.stderr.decode(errors='replace')
    subprocess.run([str(exe)],check=True,cwd=tmp_path)


def test_route_candidate_preserves_recordings_and_has_one_full_volume_send():
    old=ROOT/'local-debug/manager-league-v94/audio/stage-02/Audio/manager-league-v94.acb'
    if not old.exists():pytest.skip('Optional sealed owned Manager audio bank required')
    before=old.read_bytes();after=repair(before);top=Utf(after);original=Utf(before)
    strings=[r['StringValue'] for r in top.child('StringValueTable').rows]
    import struct
    for i in range(13):
        command=top.child('SeqCommandTable').blob(i,'Command')
        assert command[:7]==original.child('SeqCommandTable').blob(i,'Command')[:7]
        sends=[]
        for offset in (7,14):
            op,size,bus,gain=struct.unpack_from('>HBHH',command,offset)
            assert op==0x6f and size==4;sends.append((strings[bus],gain))
        assert sends==[('MasterOut',0),('BUS8',10000)]
    for field in ('AwbFile','WaveformTable','WaveformExtensionDataTable','CueTable',
                  'SequenceTable','TrackTable','SynthTable','TrackEventTable','AcfMd5Hash'):
        assert original.blob(0,field)==top.blob(0,field)
    with pytest.raises(ValueError,match='identity'):
        repair(before[:-1]+bytes([before[-1]^1]))


def test_motion_remains_continuous_after_restarts_across_possession_tapes(tmp_path):
    cc=shutil.which('gcc')
    if not cc:pytest.skip('Host C compiler unavailable')
    source=tmp_path/'motion.c';exe=source.with_suffix('.exe')
    source.write_text(r'''
#include <assert.h>
#include <math.h>
#include <string.h>
#include "manager_league_dummy.h"
static unsigned next(unsigned *s){return *s=*s*1664525u+1013904223u;}
int main(void){
 const unsigned kinds[29]={MD_PASS,MD_SHOT,MD_SAVE,MD_FOUL,MD_PASS,MD_GOAL,MD_CORNER,
 MD_YELLOW,MD_SHOT,MD_PASS,MD_OFFSIDE,MD_SAVE,MD_FOUL,MD_PASS,MD_HALF,MD_PASS,
 MD_SHOT,MD_CORNER,MD_GOAL,MD_SUB,MD_FOUL,MD_SAVE,MD_SHOT,MD_PASS,MD_SUB,
 MD_OFFSIDE,MD_CORNER,MD_SAVE,MD_SHOT};
 const unsigned offsets[]={0,350,700,900,1000,1500,3000,3150,3300,3650,3900,4200,4550,4600,4950};
 for(unsigned seed=1;seed<=64;seed++){
  MdFixture f={0};f.seed=seed*0x9e3779b9u;unsigned s=f.seed,active[2][11];
  for(unsigned side=0;side<2;side++)for(unsigned n=0;n<11;n++)active[side][n]=n+1;
  for(unsigned i=0;i<29;i++){
   MdEvent *e=&f.events[i];e->at_ms=(i+1)*6000;e->side=next(&s)>>16&1;
   unsigned slot=1+(next(&s)>>16)%10;e->kind=kinds[i];e->player=active[e->side][slot];
   if(e->kind==MD_SUB){e->other=i==19?12:13;active[e->side][slot]=e->other;}
  }
  for(unsigned i=0;i<29;i++)for(unsigned o=0;o<sizeof(offsets)/sizeof(*offsets);o++){
   unsigned t=f.events[i].at_ms+offsets[o];MdDot a[23],b[23],same[23];
   manager_dummy_sample(&f,t-1,a);manager_dummy_sample(&f,t,b);manager_dummy_sample(&f,t,same);
   assert(!memcmp(b,same,sizeof(b)));
   for(unsigned n=0;n<23;n++){
    assert(isfinite(b[n].x)&&isfinite(b[n].y)&&b[n].x>=0&&b[n].x<=1&&b[n].y>=0&&b[n].y<=1);
    assert(fabsf(a[n].x-b[n].x)<.002f&&fabsf(a[n].y-b[n].y)<.002f);
   }
  }
 }
 return 0;
}
''')
    ran=subprocess.run([cc,'-std=c11','-O2','-Wall','-Wextra','-Werror','-I',str(ROOT/'source'),str(source),
        str(ROOT/'source/manager_league_motion.c'),'-lm','-o',str(exe)],capture_output=True)
    assert ran.returncode==0,ran.stderr.decode(errors='replace')
    ran=subprocess.run([str(exe)],cwd=tmp_path,capture_output=True,timeout=30)
    assert ran.returncode==0,ran.stderr.decode(errors='replace')
