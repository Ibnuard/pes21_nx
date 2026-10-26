"""Exercise production Match seeding without rebuilding or changing live scores."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT=Path(__file__).resolve().parents[1]


def test_actual_prematch_seeds_previous_leg_order_only(tmp_path):
    compiler=shutil.which('gcc') or shutil.which('clang')
    if not compiler:pytest.skip('host C compiler required')
    hooks=(ROOT/'source/ue4_hooks.c').read_text(encoding='utf-8')
    start=hooks.index('  /* The native flow already understands first/second leg aggregate scores.')
    end=hooks.index('  if (exhibition_match_set_max_substitutions)',start)
    # Extract the production block so the real caller/header wiring is tested.
    block=hooks[start:end]
    text=r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "scoreboard_aggregate_policy.h"
static uint32_t leg,leg_type,leg_calls,away_calls,extra_away_calls,score_calls;
static uint8_t current_first[2],stored[2];
static uint32_t competition_frontend_match_leg(uint8_t *h,uint8_t *a) {
  *h=current_first[0];*a=current_first[1];return leg;
}
static void set_leg(void *m,const uint32_t *v) {
  assert(m==(void*)1);leg_type=*v;++leg_calls;
}
static void set_score(void *m,uint32_t side,uint8_t v) {
  assert(m==(void*)1 && side<2);stored[side]=v;++score_calls;
}
static void set_away(void *m,uint32_t v) {assert(m==(void*)1 && !v);++away_calls;}
static void set_extra(void *m,uint32_t v) {assert(m==(void*)1 && !v);++extra_away_calls;}
static void (*exhibition_match_set_leg_type)(void*,const uint32_t*)=set_leg;
static void (*exhibition_match_set_first_leg_score)(void*,uint32_t,uint8_t)=set_score;
static void (*exhibition_match_set_away_goal)(void*,uint32_t)=set_away;
static void (*exhibition_match_set_ex_away_goal)(void*,uint32_t)=set_extra;
static void apply(void *match) {
''' + block + r'''
}
int main(void) {
  for(leg=0;leg<=2;++leg) {
    current_first[0]=3;current_first[1]=1;stored[0]=stored[1]=99;
    apply((void*)1);
    assert(leg_type==(leg ? leg-1 : 2));
    assert(stored[0]==(leg==2 ? 1 : 0));
    assert(stored[1]==(leg==2 ? 3 : 0));
  }
  leg=2;current_first[0]=2;current_first[1]=4;apply((void*)1);
  assert(stored[0]==4 && stored[1]==2);
  /* Original Manager reads [1] for current HOME and [0] for current AWAY.
   * It alone adds live goals. Prematch never adds these or alters live score. */
  assert(stored[1]+0==2 && stored[0]+3==7);
  assert(leg_calls==4 && score_calls==8 && away_calls==4 && extra_away_calls==4);
  exhibition_match_set_leg_type=0;exhibition_match_set_first_leg_score=0;
  exhibition_match_set_away_goal=0;exhibition_match_set_ex_away_goal=0;
  apply((void*)1);
  assert(leg_calls==4 && score_calls==8 && away_calls==4 && extra_away_calls==4);
  return 0;
}
'''
    source=tmp_path/'aggregate-glue.c';exe=tmp_path/'aggregate-glue.exe'
    source.write_text(text,encoding='utf-8')
    built=subprocess.run([compiler,'-std=c11','-Wall','-Wextra','-Werror','-I',str(ROOT/'source'),str(source),'-o',str(exe)],capture_output=True,text=True,timeout=60)
    assert built.returncode==0,built.stdout+built.stderr
    ran=subprocess.run([str(exe)],capture_output=True,text=True,timeout=10)
    assert ran.returncode==0,ran.stdout+ran.stderr
