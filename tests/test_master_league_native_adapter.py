"""Execute the production career preset identity bridge without game payloads."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_gameplan_editor import function, struct

ROOT = Path(__file__).resolve().parents[1]


class MasterLeagueNativeAdapterTests(unittest.TestCase):
    def test_canonical_ids_survive_new_match_encryption_and_preserve_base_presets(self):
        cc = shutil.which('gcc') or shutil.which('clang')
        if not cc:
            self.skipTest('Host C compiler unavailable')
        hooks = (ROOT/'source/ue4_hooks.c').read_text(encoding='utf-8')
        declarations = r'''
#include <stdint.h>
#include <string.h>
#include <assert.h>
#include <stdio.h>
#include "master_league_frontend.h"
#define PREMATCH_GAMEPLAN_MAX_PLAYERS 40u
'''
        stubs = r'''
static PrematchGameplanSide exhibition_gameplan_sides[2];
static uint32_t exhibition_home_team_id=101u, exhibition_away_team_id=102u;
static void *live_gameplan_window;
static int active=1, base_reads, base_writes, saved_current;
static uint32_t crypt_key=0x13579bdfu;
static GameplanPreset saved;
static uint32_t get_key(void) { return crypt_key; }
static uint32_t (*exhibition_common_get_crypt_key)(void)=get_key;
static TmpdbFormationValue get_formation(const void *s,uint32_t t) {
  assert(s); TmpdbFormationValue f; memset(&f,(int)(t+1u),sizeof(f)); return f;
}
static TmpdbMatchPlanSettingsValue get_settings(const void *s) {
  assert(s); TmpdbMatchPlanSettingsValue v; memset(&v,7,sizeof(v)); return v;
}
static TmpdbFormationValue (*match_squad_data_get_formation)(const void *,uint32_t)=get_formation;
static TmpdbMatchPlanSettingsValue (*match_squad_data_get_settings)(const void *)=get_settings;
int ml_frontend_match_active(void) { return active; }
int ml_frontend_preset_read(uint32_t team,uint32_t slot,GameplanPreset *out) {
  if(team!=101u || slot>3u) return 0; *out=saved;return 1;
}
int ml_frontend_preset_write(uint32_t team,uint32_t slot,const GameplanPreset *p) {
  assert(team==101u && slot<3u); saved=*p;saved_current=0;return 1;
}
int ml_frontend_store_current_plan(const GameplanPreset *p) { saved=*p;saved_current=1;return 1; }
int gameplan_preset_read(uint32_t team,uint32_t slot,GameplanPreset *out) {
  (void)team;(void)slot;*out=saved;base_reads++;return 1;
}
int gameplan_preset_write(uint32_t team,uint32_t slot,const GameplanPreset *p) {
  (void)team;(void)slot;(void)p;base_writes++;return 1;
}
static void populate(uint8_t nonce) {
  PrematchGameplanSide *s=&exhibition_gameplan_sides[0];
  memset(s,0,sizeof(*s));s->squad_data=s;s->player_count=40u;s->tactics=1u;
  for(uint32_t i=0;i<40u;i++) {
    memset(s->players[i].player_id,nonce,16u);
    uint32_t id=(90000u+i)^crypt_key;
    memcpy(s->players[i].player_id+4u,&id,4u);
    s->players[i].order_no=i<18u ? i : 0xffu;
  }
}
'''
        cases = r'''
int main(void) {
  populate(0x17u);
  assert(prematch_gameplan_save_preset(0u,2u));
  assert(!saved_current && !base_reads && !base_writes);
  for(uint32_t i=0;i<40u;i++) {
    uint32_t id;memcpy(&id,saved.players[i].player_id,4u);
    assert(id==90000u+i && saved.players[i].order_no==i);
    for(uint32_t j=4u;j<16u;j++) assert(!saved.players[i].player_id[j]);
  }
  assert(saved.formation[0][100]==1u && saved.formation[1][100]==2u);
  assert(saved.settings[20]==7u && saved.tactics==1u);
  assert(prematch_gameplan_save_preset(0u,ML_CURRENT_PLAN_SLOT) && saved_current);
  crypt_key=0x2468ace0u;populate(0xa9u); /* a different native match/session */
  GameplanPreset restored;
  assert(prematch_gameplan_read_preset(0u,ML_CURRENT_PLAN_SLOT,&restored));
  for(uint32_t i=0;i<40u;i++)
    assert(!memcmp(restored.players[i].player_id,exhibition_gameplan_sides[0].players[i].player_id,16u));
  assert(!prematch_gameplan_read_preset(1u,0u,&restored));
  memset(exhibition_gameplan_sides[0].players[39].player_id,0,16u);
  assert(!prematch_gameplan_read_preset(0u,0u,&restored)); /* no stale ID fallback */
  live_gameplan_window=&saved;
  assert(!prematch_gameplan_save_preset(0u,0u));
  live_gameplan_window=NULL;active=0;populate(0xa9u);
  assert(prematch_gameplan_read_preset(0u,1u,&restored) && base_reads==1);
  assert(prematch_gameplan_save_preset(0u,1u) && base_writes==1);
  puts("career native adapter: canonical IDs, match rekey, tactics, base isolation OK");
  return 0;
}
'''
        code = '\n'.join([declarations,
            *[struct(hooks, name) for name in ('TmpdbFormationValue',
               'TmpdbMatchPlanSettingsValue', 'PrematchGameplanPlayer', 'PrematchGameplanSide')],
            stubs, *[function(hooks, name) for name in (
                'prematch_gameplan_team_id', 'prematch_gameplan_read_preset',
                'prematch_gameplan_save_preset')], cases])
        with tempfile.TemporaryDirectory(prefix='pes-career-adapter-') as temp:
            path=Path(temp)/'adapter.c';path.write_text(code,encoding='utf-8')
            exe=Path(temp)/'adapter.exe'
            result=subprocess.run([cc,'-std=c11','-Wall','-Wextra',
                '-Werror=incompatible-pointer-types','-I',str(ROOT/'source'),
                str(path),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            subprocess.run([str(exe)],check=True,cwd=temp)


if __name__=='__main__':
    unittest.main()
