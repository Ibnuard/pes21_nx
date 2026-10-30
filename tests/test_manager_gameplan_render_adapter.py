"""The offline renderer reads online identities/coordinates without engine writes."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class RenderAdapterTests(unittest.TestCase):
    def test_server_snapshot_native_fallback_and_readonly_focus(self):
        compiler=shutil.which('gcc')
        if not compiler:self.skipTest('Host C compiler unavailable')
        adapter=(ROOT/'source/manager_gameplan_render_adapter.inc').read_text()
        declarations=re.findall(r'static (uint32_t|int|const char \*) manager_render_(\w+)\(([^)]*)\).*?return (pes_controller_\w+)\(([^)]*)\);}',adapter)
        self.assertGreater(len(declarations),15)
        stubs='\n'.join(f'{typ} {name}({args}){{'+('return "native";' if typ=='const char *' else 'return 77;')+'}' for typ,_,args,name,_ in declarations)
        source='''#include <assert.h>
#include <string.h>
#include "manager_league_dummy.h"
#define PES_PREMATCH_GAMEPLAN_PAGE_FORMATION 2u
#define PES_PREMATCH_GAMEPLAN_PAGE_ROOT 0u
#define PES_PREMATCH_GAMEPLAN_PAGE_SUBSTITUTE 1u
static MdView fake;
void manager_client_view(MdView *out){*out=fake;}
static unsigned requested,ids[5];
static unsigned gameplan_portrait_texture(unsigned id){return id==500?1:0;}
void pes_controller_league_request_scorer_portrait(unsigned slot,unsigned id){assert(slot<5);ids[slot]=id;requested++;}
'''+stubs+'''
#include "manager_gameplan_render_adapter.inc"
int main(void){
 assert(manager_render_field_count(0)==77);
 fake.page=MD_CLUB_PLAN;fake.online=1;fake.plan_editable=1;fake.focus=2;fake.plan_pick=UINT32_MAX;
 for(unsigned i=0;i<18;i++){fake.plan_players[i].portrait=500+i;fake.plan_players[i].rating=60+i;fake.plan_players[i].role=i%13;}
 fake.plan_dots[2].x=.25f;fake.plan_dots[2].y=.75f;
 manager_render_plan_snapshot(1);
 manager_render_plan_queue_portraits();assert(requested==5&&ids[0]==501);
 assert(manager_render_plan_active&&manager_render_page(0)==1);
 assert(manager_render_root_focus(0)<4&&manager_render_field_count(0)==11&&manager_render_bench_count(0)==7);
 assert(manager_render_player_portrait_id(0,1,2)==502&&manager_render_player_portrait_id(0,0,6)==517);
 assert(manager_render_player_overall(0,0,6)==77);
 assert(manager_render_player_pitch_x(0,2)==64&&manager_render_player_pitch_y(0,2)==191);
 assert(manager_render_substitute_focus(0,0)==2&&!manager_render_substitute_selected(0,0,2));
 fake.plan_move=2;fake.plan_condition=1;manager_render_plan_snapshot(1);assert(manager_render_drag_state(0)==2&&manager_render_condition_mode(0)==1);
 fake.plan_move=1;manager_render_plan_snapshot(1);assert(manager_render_drag_state(0)==1);
 fake.plan_pick=2;fake.focus=MD_PLAN_PLAYERS+2;manager_render_plan_snapshot(1);
 assert(manager_render_root_focus(0)==2&&manager_render_substitute_selected(0,0,2));
 fake.plan_count=26;fake.focus=25;fake.plan_pick=25;fake.plan_players[25].portrait=900;fake.plan_players[25].rating=90;
 manager_render_plan_snapshot(1);
 assert(manager_render_page(0)==1&&manager_render_bench_count(0)==15);
 assert(manager_render_player_portrait_id(0,0,14)==900&&manager_render_player_overall(0,0,14)==90);
 assert(manager_render_substitute_focus(0,1)==14&&manager_render_substitute_selected(0,1,14));
 fake.focus=2;fake.plan_bench_focus=14;manager_render_plan_snapshot(1);
 assert(manager_render_substitute_focus(0,1)==14); /* Keep scrolled reserves visible while choosing a starter. */
 fake.plan_count=18;fake.plan_bench_focus=0;
 fake.plan_editable=0;manager_render_plan_snapshot(1);
 fake.now_ms=250;manager_render_plan_snapshot(1);requested=0;manager_render_plan_queue_portraits();assert(requested==5&&ids[0]==505);
 assert(manager_render_page(0)==0&&!manager_render_substitute_selected(0,0,2)&&manager_render_substitute_focus(0,0)==UINT32_MAX);
 assert(!manager_render_plan_player(0,UINT32_MAX)->portrait);
 manager_render_plan_snapshot(0);assert(!manager_render_plan_active&&manager_render_player_pitch_x(0,2)==77);
 return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='manager-render-adapter-') as tmp:
            path=Path(tmp);(path/'adapter.c').write_text(source)
            result=subprocess.run([compiler,'-std=c11','-Wall','-Werror','-Wno-unused-function','-I',str(ROOT/'source'),str(path/'adapter.c'),'-o',str(path/'test.exe')],capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
            self.assertEqual(subprocess.run([str(path/'test.exe')]).returncode,0)
