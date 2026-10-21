"""Replay the actual native-scene admission precedence for the extra referee."""
from pathlib import Path
import shutil
import unittest
from test_gameplan_editor import function
from test_result_flow import build_and_run

ROOT=Path(__file__).resolve().parents[1]


class RefereePresentationPolicyTests(unittest.TestCase):
    def test_only_recorded_replay_hides_actor_not_generic_stoppage_demos(self):
        compiler=shutil.which('gcc')
        if not compiler:self.skipTest('host C compiler required')
        source=(ROOT/'source/ue4_hooks.c').read_text()
        body=r'''
#include <assert.h>
#include <stdint.h>
enum {MATCH_PHASE_HALFTIME=2,MATCH_PHASE_EX_TIME=4,MATCH_PHASE_EX_INTERVAL=6};
enum {PES_VIRTUAL_CURSOR_NONE=0,PES_VIRTUAL_CURSOR_SET_PIECE_TAKER=7};
static unsigned phase=1,replay,var,goal,cinematic,fixdemo,pause,transition,result,result_transition,cursor;
static uint32_t match_result_current_phase(void){return phase;}
#define FLAG(fn,var) static int fn(void){return var;}
FLAG(pes_controller_replay_active,replay) FLAG(pes_controller_goal_demo_active,goal)
FLAG(pes_controller_cinematic_skip_active,cinematic) FLAG(pes_controller_fix_demo_skip_active,fixdemo)
FLAG(pes_controller_pause_skin_active,pause) FLAG(pes_controller_pause_transition,transition)
FLAG(pes_controller_match_result_skin,result) FLAG(pes_controller_match_result_transition,result_transition)
FLAG(pes_controller_virtual_cursor_context,cursor)
FLAG(referee_offside_presentation_active,var)
'''+function(source,'referee_probe_scene_active')+r'''
int main(void){
 assert(referee_probe_scene_active()==2);
 pause=1;assert(referee_probe_scene_active()==1);
 replay=1;cursor=3;assert(referee_probe_scene_active()==4);
 replay=0;
 unsigned *stoppages[]={&goal,&cinematic,&fixdemo};
 for(unsigned i=0;i<3;i++){
   *stoppages[i]=1;
   /* A pause/cursor may freeze the current visible pose, never hide/reset it. */
   pause=1;cursor=3;assert(referee_probe_scene_active()==1);
   pause=0;cursor=PES_VIRTUAL_CURSOR_NONE;
   assert(referee_probe_scene_active()==2);
   cursor=PES_VIRTUAL_CURSOR_SET_PIECE_TAKER;
   assert(referee_probe_scene_active()==2);
   *stoppages[i]=0;
 }
 pause=1;
 assert(referee_probe_scene_active()==1);
 pause=0;cursor=PES_VIRTUAL_CURSOR_SET_PIECE_TAKER;
 assert(referee_probe_scene_active()==2);
 replay=1;
 unsigned hidden[]={2,4,6,8,0xffffffffu};
 for(unsigned i=0;i<5;i++){phase=hidden[i];assert(!referee_probe_scene_active());}
 phase=1;assert(referee_probe_scene_active()==4);
 replay=0;var=1;assert(referee_probe_scene_active()==4);
 var=0;assert(referee_probe_scene_active()==2);
}
'''
        build_and_run(compiler,body)
