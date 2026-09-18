"""Executable host policies; on-device rendering/pacing remains a separate test."""
from pathlib import Path
import shutil
import unittest
from test_gameplan_editor import function
from test_result_flow import build_and_run

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'source/ue4_hooks.c').read_text(encoding='utf-8')


class StadiumV7Tests(unittest.TestCase):
    def run_c(self, source):
        cc = shutil.which('gcc')
        if not cc:
            self.skipTest('gcc unavailable')
        build_and_run(cc, source)

    def test_shadow_resolution_ownership_and_native_quality_changes(self):
        self.run_c('#include <assert.h>\n' +
                   (ROOT / 'source/stadium_shadow_budget.h').read_text() + r'''
int main(void) {
  assert(STADIUM_SHADOW_LIMIT_COUNT==3);
  assert(stadium_shadow_limits[0].cap==512 && stadium_shadow_limits[1].cap==512);
  assert(stadium_shadow_limits[2].cap==0);
  for(unsigned n=0;n<STADIUM_SHADOW_LIMIT_COUNT;n++) {
    StadiumShadowBudget b={0};
    int cap=stadium_shadow_limits[n].cap, native=cap ? 4*cap : 4;
    assert(stadium_shadow_budget_target(&b,0,native,0x1000000,cap)==native);
    assert(stadium_shadow_budget_target(&b,1,native,0x1000000,cap)==cap);
    stadium_shadow_budget_applied(&b,1,native,native,0x1000000,cap); // refused
    assert(!b.owned);
    stadium_shadow_budget_applied(&b,1,native,cap,0x1000000,cap);
    assert(b.owned && b.baseline==native);
    for(int i=0;i<100;i++) {
      assert(stadium_shadow_budget_target(&b,1,cap,0x1000000,cap)==cap);
      assert(b.baseline==native); // polling cannot erase baseline
    }
    assert(stadium_shadow_budget_target(&b,0,cap,0x1000000,cap)==native);
    stadium_shadow_budget_applied(&b,0,cap,cap,0x1000000,cap); // restore refused
    assert(b.owned);
    stadium_shadow_budget_applied(&b,0,cap,native,0x1000000,cap);
    assert(!b.owned);
    assert(stadium_shadow_budget_target(&b,1,0,0x1000000,cap)==0); // never enable shadows
    assert(stadium_shadow_budget_target(&b,1,cap/2,0x1000000,cap)==cap/2);
    stadium_shadow_budget_applied(&b,1,native,cap,0x1000000,cap);
    int external_value=cap?0:1; // distinct from our write, including zero-cascade policy
    assert(stadium_shadow_budget_target(&b,0,external_value,0x1000000,cap)==external_value && !b.owned);
    stadium_shadow_budget_applied(&b,1,native,cap,0x1000000,cap);
    assert(stadium_shadow_budget_target(&b,0,cap,0x2000000,cap)==cap && !b.owned);
    assert(stadium_shadow_budget_target(&b,1,native*2,0x2000000,cap)==cap);
    stadium_shadow_budget_applied(&b,1,native*2,cap,0x2000000,cap);
    assert(stadium_shadow_budget_target(&b,0,cap,0x2000000,cap)==native*2);
  }
}
''')

    def test_game_speed_all_values_leave_live_fps_untouched_until_native_resume(self):
        self.run_c(r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#define PES_PAUSE_INPUT_LEFT 3u
static unsigned char tmp[64], registry[64];
static float live_fps=60;
static uint32_t pause_game_speed_debug_tmpdb, pause_game_speed_debug_registry;
static uint32_t pause_game_speed_debug_target_fps, pause_game_speed_debug_runtime_fps_milli;
static uint32_t pause_game_speed_debug_apply_count;
static unsigned char *pause_settings_tmpdb_system(void) {return tmp;}
static void *pause_settings_registry_system(void) {return registry;}
static void native_set(void *p, uint8_t n) {assert(p==registry+0x14); *(uint8_t*)p=n;}
static uint32_t native_fps(const void *p) {return 21+3*(*(const uint8_t*)p);}
static float native_live(void) {return live_fps;}
static void (*pause_registry_game_speed_set)(void *,uint8_t)=native_set;
static uint32_t (*pause_registry_game_speed_get_fps)(const void *)=native_fps;
static float (*pause_basic_status_get_pes_module_thread_fps)(void)=native_live;
''' + function(SOURCE, 'pause_settings_set_game_speed') + r'''
int main(void) {
  tmp[0x14]=2; registry[0]=77;
  for(unsigned n=0;n<15;n++) {
    unsigned expected=(tmp[0x14]+1)%5;
    live_fps=(n%2)?27:60; // native loading/cinematic owner is intentionally different
    float before=live_fps;
    pause_settings_set_game_speed(9);
    assert(tmp[0x14]==expected && registry[0x14]==expected && registry[0]==77);
    assert(pause_game_speed_debug_target_fps==21+3*expected);
    assert(live_fps==before);
    assert(pause_game_speed_debug_apply_count==n+1);
  }
  tmp[0x14]=0; pause_settings_set_game_speed(PES_PAUSE_INPUT_LEFT);
  assert(tmp[0x14]==4);
  tmp[0x14]=255; pause_settings_set_game_speed(PES_PAUSE_INPUT_LEFT);
  assert(tmp[0x14]==1);
}
''')

    def test_rematch_refresh_restores_night_and_legend_without_importing_defaults(self):
        self.run_c(r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#define EXHIBITION_CPU_LEVEL_COUNT 7
typedef struct {uint64_t words[21];} TmpdbStadiumInitParamValue;
static TmpdbStadiumInitParamValue renderer_init;
static TmpdbStadiumInitParamValue get_init(const void *p) {(void)p; return renderer_init;}
static void set_init(void *p,const TmpdbStadiumInitParamValue *i) {(void)p; renderer_init=*i;}
static TmpdbStadiumInitParamValue (*exhibition_match_get_stadium_init)(const void *)=get_init;
static void (*exhibition_match_set_stadium_init)(void *,const TmpdbStadiumInitParamValue *)=set_init;
static uint32_t exhibition_cpu_level_value=6, exhibition_settings_time_zone=1;
static uint32_t exhibition_settings_match_time=10, exhibition_settings_extra_time=1;
static uint32_t exhibition_settings_penalties=1, exhibition_settings_hub_mode=1;
static void *exhibition_settings_match;
static uint32_t native_match[5], debug_level;
static void *exhibition_get_tmpdb_match(void) {return native_match;}
static void debugPrintf(const char *f,...) {(void)f;}
static void set_level(uint32_t n) {debug_level=n;}
static void set0(void *p,uint32_t n) {((uint32_t*)p)[0]=n;}
static void set1(void *p,uint32_t n) {((uint32_t*)p)[1]=n;}
static void set2(void *p,uint32_t n) {((uint32_t*)p)[2]=n;}
static void set3(void *p,uint32_t n) {((uint32_t*)p)[3]=n;}
static void set4(void *p,uint32_t n) {((uint32_t*)p)[4]=n;}
static uint32_t get0(const void *p) {return ((const uint32_t*)p)[0];}
static uint32_t get1(const void *p) {return ((const uint32_t*)p)[1];}
static uint32_t get2(const void *p) {return ((const uint32_t*)p)[2];}
static uint32_t get3(const void *p) {return ((const uint32_t*)p)[3];}
static uint32_t get4(const void *p) {return ((const uint32_t*)p)[4];}
static void (*exhibition_set_test_match_cpu_level)(uint32_t)=set_level;
static void (*exhibition_match_set_match_level)(void*,uint32_t)=set0;
static void (*exhibition_match_set_time_zone)(void*,uint32_t)=set1;
static void (*exhibition_match_set_match_time)(void*,uint32_t)=set2;
static void (*exhibition_match_set_ex)(void*,uint32_t)=set3;
static void (*exhibition_match_set_pk)(void*,uint32_t)=set4;
static uint32_t (*exhibition_match_get_match_level)(const void*)=get0;
static uint32_t (*exhibition_match_get_time_zone)(const void*)=get1;
static uint32_t (*exhibition_match_get_match_time)(const void*)=get2;
static uint32_t (*exhibition_match_is_ex)(const void*)=get3;
static uint32_t (*exhibition_match_is_pk)(const void*)=get4;
''' + function(SOURCE, 'exhibition_apply_cpu_level') +
                   function(SOURCE, 'exhibition_apply_match_settings') +
                   function(SOURCE, 'exhibition_refresh_match_settings') + r'''
int main(void) {
  for(int match=0;match<3;match++) {
    for(int i=0;i<5;i++) native_match[i]=0; // stock bootstrap: Day / Beginner
    memset(&renderer_init,0xab,sizeof(renderer_init));
    uint32_t default_day=0;
    memcpy((char*)&renderer_init+4,&default_day,4);
    assert(exhibition_refresh_match_settings());
    assert(exhibition_cpu_level_value==6 && exhibition_settings_time_zone==1);
    assert(native_match[0]==6 && native_match[1]==1 && native_match[2]==10);
    assert(native_match[3]==1 && native_match[4]==1 && debug_level==6);
    uint32_t actual; memcpy(&actual,(char*)&renderer_init+4,4); assert(actual==1);
    for(int i=0;i<sizeof(renderer_init);i++)
      if(i<4 || i>=8) assert(((unsigned char*)&renderer_init)[i]==0xab);
    exhibition_settings_time_zone=0; exhibition_apply_match_settings(0);
    memcpy(&actual,(char*)&renderer_init+4,4); assert(actual==0);
    exhibition_settings_time_zone=1;
  }
}
''')
        setup = function(SOURCE, 'pes_exhibition_match_setup_data_entry')
        self.assertIn('&exhibition_session_active', setup)
        self.assertIn('&exhibition_match_settings_armed, 1u', setup)
        self.assertNotIn('exhibition_get_test_match_cpu_level()', function(SOURCE, 'exhibition_open_cpu_level'))

    def test_shadow_budget_uses_native_setter_not_render_target_rewrites(self):
        tick = function(SOURCE, 'stadium_shadow_budget_tick')
        for required in ('500000000ULL', 'stadium_cvar_set(cvar, value, priority)',
                         'vtable != stadium_int_cvar_vtable', 'actual=%d'):
            self.assertIn(required, tick)
        for forbidden in ('glTexImage', 'glViewport', 'r.ShadowQuality'):
            self.assertNotIn(forbidden, tick)
        self.assertIn('mode && profile_match != last_profile_match', tick)

    def test_shadow_tick_main_thread_budget_restore_and_wrong_type_guard(self):
        self.run_c(r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
typedef struct {uintptr_t vtable; int value; uint32_t flags;} Variable;
static Variable vars[3]={{42,2048,0x1000000},{42,2048,0x1000000},{42,4,0x1000000}};
static uint64_t tick=1;
static uint64_t armGetSystemTick(void) {return tick;}
static uint64_t armTicksToNs(uint64_t t) {return t;}
static void *manager=(void*)123;
static void **stadium_console_manager=&manager;
static uintptr_t stadium_int_cvar_vtable=42;
static uint32_t stadium_shadow_budget_requested;
static unsigned writes;
static void *find_var(void *m,const uint16_t *n) {
  assert(m==manager); char name[48]={0};
  for(unsigned i=0;n[i];i++) name[i]=(char)n[i];
  if(!strcmp(name,"r.Shadow.MaxCSMResolution")) return vars;
  if(!strcmp(name,"r.Shadow.MaxResolution")) return vars+1;
  assert(!strcmp(name,"r.Shadow.CSM.MaxCascades")); return vars+2;
}
static int get_int(void *v) {assert(((Variable*)v)->vtable==42);return ((Variable*)v)->value;}
static uint32_t get_flags(void *v) {return ((Variable*)v)->flags;}
static void set(void *v,const uint16_t *n,uint32_t f) {
  Variable *c=v; assert(f==c->flags); int x=0;
  for(unsigned i=0;n[i];i++) {assert(n[i]>='0' && n[i]<='9'); x=x*10+n[i]-'0';}
  c->value=x; ++writes;
}
static void *(*stadium_find_cvar)(void *,const uint16_t*)=find_var;
static int (*stadium_cvar_int)(void*)=get_int;
static uint32_t (*stadium_cvar_flags)(void*)=get_flags;
static void (*stadium_cvar_set)(void*,const uint16_t*,uint32_t)=set;
''' + (ROOT / 'source/stadium_shadow_budget.h').read_text() +
                   function(SOURCE, 'stadium_shadow_budget_tick') + r'''
int main(void) {
  stadium_shadow_budget_tick(); assert(!writes); // idle
  stadium_shadow_budget_requested=1; tick+=500000000;
  stadium_shadow_budget_tick(); assert(writes==3 && vars[0].value==512 && vars[1].value==512 && vars[2].value==0);
  stadium_shadow_budget_requested=2;
  stadium_shadow_budget_tick(); assert(writes==3); // throttled
  tick+=500000000; stadium_shadow_budget_tick();
  assert(writes==6 && vars[0].value==2048 && vars[1].value==2048 && vars[2].value==4);
  stadium_shadow_budget_requested=1;
  vars[0].vtable=99; vars[1].value=256; vars[2].value=0; tick+=500000000;
  stadium_shadow_budget_tick(); assert(writes==6 && vars[0].value==2048 && vars[1].value==256);
}
''')


if __name__ == '__main__':
    unittest.main()
