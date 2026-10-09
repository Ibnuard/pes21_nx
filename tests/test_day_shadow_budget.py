"""Day-only native CVar cap integration; no synthetic shadow-map writes."""
from pathlib import Path
import shutil
import unittest

from test_gameplan_editor import function
from test_result_flow import build_and_run

ROOT = Path(__file__).resolve().parents[1]


class DayShadowBudgetTests(unittest.TestCase):
    def test_native_tick_caps_and_restores_without_raising_lower_values(self):
        cc = shutil.which('gcc')
        if not cc:
            self.skipTest('gcc unavailable')
        source = (ROOT / 'source/ue4_hooks.c').read_text(encoding='utf-8')
        policy = (ROOT / 'source/stadium_shadow_budget.h').read_text()
        build_and_run(cc, policy + r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef struct {uintptr_t vtable; int value; uint32_t flags, writes;} CVar;
static CVar vars[3]={{9,2048,0x1000000,0},{9,2048,0x1000000,0},{9,4,0x1000000,0}};
static void *manager=(void*)1, **stadium_console_manager=&manager;
static uintptr_t stadium_int_cvar_vtable=9;
static uint32_t stadium_shadow_budget_requested;
static uint64_t tick;
static uint64_t armGetSystemTick(void) {return tick;}
static uint64_t armTicksToNs(uint64_t n) {return n;}
static void *find(void *m,const uint16_t *name) {
  assert(m==manager);
  char ascii[48]={0}; for(unsigned i=0;name[i];i++) ascii[i]=name[i];
  for(unsigned i=0;i<3;i++) if(!strcmp(ascii,stadium_shadow_limits[i].name)) return &vars[i];
  assert(0); return NULL;
}
static int get(void *c) {return ((CVar*)c)->value;}
static uint32_t flags(void *c) {return ((CVar*)c)->flags;}
static void set(void *c,const uint16_t *digits,uint32_t priority) {
  CVar *v=c; assert(v->vtable==9 && priority==(v->flags&0xff000000));
  int value=0; for(unsigned i=0;digits[i];i++) value=value*10+digits[i]-'0';
  v->value=value; ++v->writes;
}
static void *(*stadium_find_cvar)(void*,const uint16_t*)=find;
static int (*stadium_cvar_int)(void*)=get;
static uint32_t (*stadium_cvar_flags)(void*)=flags;
static void (*stadium_cvar_set)(void*,const uint16_t*,uint32_t)=set;
''' + function(source, 'stadium_shadow_budget_tick') + r'''
static void run(uint32_t mode) {
  tick+=500000000; stadium_shadow_budget_requested=mode; stadium_shadow_budget_tick();
}
int main(void) {
  run(2); // Night must never lower its native settings.
  for(unsigned i=0;i<3;i++) assert(vars[i].writes==0);
  run(1);run(1);
  assert(vars[0].value==2048 && vars[1].value==2048 && vars[2].value==0);
  assert(vars[0].writes==0 && vars[1].writes==0 && vars[2].writes==1);
  run(2); // restore native Night cascades
  assert(vars[2].value==4 && vars[2].writes==2);
  run(1);run(0); // returning to frontdoor also releases our override
  assert(vars[2].value==4 && vars[2].writes==4);
  // Preserve native Low/Standard, including an intentionally disabled cascade.
  vars[0].value=256; vars[1].value=128; vars[2].value=0;
  for(unsigned i=0;i<3;i++)vars[i].writes=0;
  run(1);run(2);run(0);
  assert(vars[0].value==256 && vars[1].value==128 && vars[2].value==0);
  for(unsigned i=0;i<3;i++)assert(vars[i].writes==0);
  for(unsigned i=0;i<3;i++) {vars[i].value=2048;vars[i].vtable=10;}
  run(1); // Wrong native CVar type remains untouched.
  for(unsigned i=0;i<3;i++)assert(vars[i].value==2048 && vars[i].writes==0);

}
''')


if __name__ == '__main__':
    unittest.main()
