"""Execute the production identity bridge with disposable native squad copies.

The important boundary is MemberId, not vector index or pitch order. Native
match tactics/eligibility/reservations must survive identity hydration.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_gameplan_editor import function, struct

ROOT = Path(__file__).resolve().parents[1]


class LiveIdentityTests(unittest.TestCase):
    def test_capture_and_restore_across_native_rebuild(self):
        compiler = shutil.which('gcc') or shutil.which('clang')
        if not compiler:
            self.skipTest('Host C compiler required')
        hooks = (ROOT / 'source/ue4_hooks.c').read_text(encoding='utf-8')
        header = (ROOT / 'source/ue4_hooks.h').read_text(encoding='utf-8')
        source = r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#define debugPrintf(...) ((void)0)
#define PREMATCH_GAMEPLAN_MAX_PLAYERS 40u
#define LIVE_PORTRAIT_CACHE_CAPACITY 80u
typedef struct { unsigned char bytes[52]; char name[48]; } Player;
typedef struct { uint32_t member; Player parameter[2]; uint32_t stamina, eligible; } Member;
typedef struct { uint32_t count, formation, reservations; Member members[40]; } Squad;
static Squad captured[2], active[2];
static void *exhibition_pre_strategy_squad_snapshot[2] = {&captured[0], &captured[1]};
static uint32_t exhibition_pre_strategy_squad_snapshot_valid[2] = {1, 1};
static uint32_t exhibition_home_team_id = 108, exhibition_away_team_id = 109;
static unsigned char manager_bytes[80], editor;
static uint32_t my_side = 1, updates, ignore_setter;
static Player database[2][40];
static uint64_t player_id(const Player *p) { uint64_t id; memcpy(&id,p->bytes+44,8); return id; }
static void set_player(Player *p, uint64_t id, const char *name) {
 memset(p,0,sizeof(*p)); memcpy(p->bytes+44,&id,8); snprintf(p->name,sizeof(p->name),"%s",name);
}
static unsigned char *exhibition_get_squad_edit(void) { return &editor; }
static void *exhibition_tmpdb_manager_get_instance(void) { return manager_bytes; }
static void *exhibition_squad_edit_get_squad_data(void *e, uint32_t side) { return &active[side]; }
static uint32_t exhibition_squad_data_get_player_count(void *s) { return ((Squad*)s)->count; }
static void *exhibition_squad_data_get_player_by_index(void *s, const uint32_t *i) { return &((Squad*)s)->members[*i]; }
static uint32_t match_squad_data_get_member_id(void *s, const void *key) { return ((const Member*)key)->member; }
static void *match_squad_data_get_tmpdb_player(void *s, const void *key) { return (void *)&((const Member*)key)->parameter[0]; }
static const char *match_tmpdb_player_get_name(const void *p) { return ((const Player*)p)->name; }
static uint32_t exhibition_squad_edit_get_my_side(void *e) { return my_side; }
static void exhibition_squad_edit_set_my_side(void *e,const uint32_t *side) { my_side=*side; }
static void *exhibition_commonwork_update_player(void *work,uint64_t id) {
 for(unsigned s=0;s<2;s++) for(unsigned i=0;i<40;i++)
  if(player_id(&database[s][i])==id) return &database[s][i];
 return NULL;
}
static void exhibition_squad_edit_update_player(void *e,const void *key,const void *p,uint32_t type) {
 Member *m=(Member*)key;
 assert(m>=active[my_side].members && m<active[my_side].members+40);
 if(ignore_setter) return;
 m->parameter[type]=*(const Player*)p; updates++;
}
'''
        source += '\n' + struct(hooks, 'LiveGameplanIdentity') + r'''
static LiveGameplanIdentity live_gameplan_identity[2][40];
static uint32_t live_gameplan_identity_count[2],live_gameplan_identity_team[2];
'''
        source += '\n'.join(function(hooks, name) for name in (
            'live_gameplan_capture_identity', 'live_gameplan_restore_identity'))
        source += '\n' + struct(header, 'PesPrematchGameplanPortraitPng') + r'''
static PesPrematchGameplanPortraitPng *live_portrait_cache[80];
static uint64_t live_portrait_cache_stamp[80], live_portrait_cache_clock;
'''
        source += function(hooks, 'live_gameplan_cache_portrait')
        source += r'''
int main(void) {
 void *work=database; memcpy(manager_bytes+64,&work,sizeof(work));
 for(unsigned s=0;s<2;s++) {
  Squad *sq=&captured[s]; sq->count=30;
  for(unsigned i=0;i<30;i++) {
   char name[48]; snprintf(name,sizeof(name),"AUTHENTIC_%u_%u",s,i);
   set_player(&database[s][i],((uint64_t)(10000+s*100+i)<<32)|123,name);
   sq->members[i].member=i; sq->members[i].parameter[0]=database[s][i];
  }
 }
 live_gameplan_capture_identity();
 assert(live_gameplan_identity_count[0]==30 && live_gameplan_identity_count[1]==30);
 // The native child exposes 18 players in a different vector/starting order.
 for(unsigned s=0;s<2;s++) {
  active[s].count=18; active[s].formation=433; active[s].reservations=2;
  for(unsigned i=0;i<18;i++) {
   Member *m=&active[s].members[i]; m->member=(i*7)%30;
   m->stamina=31+i; m->eligible=i%2;
   set_player(&m->parameter[0],65533,s ? "C. TRUSSARDI" : "");
   m->parameter[1]=m->parameter[0];
  }
  assert(live_gameplan_restore_identity(s)==18);
  assert(my_side==1 && active[s].formation==433 && active[s].reservations==2);
  for(unsigned i=0;i<18;i++) {
   Member *m=&active[s].members[i];
   for(unsigned t=0;t<2;t++) assert(!memcmp(&m->parameter[t],&database[s][m->member],sizeof(Player)));
   assert(m->stamina==31+i && m->eligible==i%2 && m->member==(i*7)%30);
  }
 }
 assert(updates==72);
 // A silently rejected native write must not be counted as restored.
 set_player(&active[1].members[0].parameter[0],65533,"DUMMY");
 active[1].members[0].parameter[1]=active[1].members[0].parameter[0];
 ignore_setter=1;
 assert(live_gameplan_restore_identity(1)==17);
 ignore_setter=0;
 assert(live_gameplan_restore_identity(1)==18);
 // Reopening/substituting cannot shift identity to the current pitch slot.
 active[0].members[0].member=29; active[0].reservations=3;
 assert(live_gameplan_restore_identity(0)==18);
 assert(player_id(&active[0].members[0].parameter[1])==player_id(&database[0][29]));
 assert(active[0].reservations==3);
 // Unknown/sentinel member IDs and a changed fixture are not guessed.
 active[0].members[0].member=255;
 assert(live_gameplan_restore_identity(0)==17);
 exhibition_home_team_id=110;
 assert(live_gameplan_restore_identity(0)==0);
 // Capture refreshes the map even for the same club; no stale valid map.
 captured[0].count=0;
 live_gameplan_capture_identity();
 assert(live_gameplan_identity_count[0]==0 && !live_gameplan_identity[0][1].common_player_id);
 assert(live_gameplan_identity_count[1]==30);
 // Ambiguous member IDs reject the entire side rather than mislabel a player.
 captured[1].members[1].member=0;
 live_gameplan_capture_identity();
 assert(live_gameplan_identity_count[1]==0);
 // The cache holds BOTH complete squads, including repeated refreshes.
 PesPrematchGameplanPortraitPng *png=malloc(sizeof(*png)+1); png->byte_count=1;
 for(unsigned i=1;i<=80;i++) { png->portrait_id=i; png->bytes[0]=(unsigned char)i; live_gameplan_cache_portrait(png); }
 for(unsigned repeat=0;repeat<4;repeat++) for(unsigned i=1;i<=40;i++) {
  png->portrait_id=i; live_gameplan_cache_portrait(png);
 }
 for(unsigned i=0;i<80;i++) assert(live_portrait_cache[i]->portrait_id==i+1);
 // A-vs-B then A-vs-C must discard B, not the refreshed A entries.
 for(unsigned i=81;i<=120;i++) { png->portrait_id=i; live_gameplan_cache_portrait(png); }
 for(unsigned i=0;i<80;i++) {
  assert(live_portrait_cache[i]->portrait_id==(i<40 ? i+1 : i+41));
  free(live_portrait_cache[i]);
 }
 free(png);
 return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='pes-live-identity-') as folder:
            cfile, exe = Path(folder) / 'test.c', Path(folder) / 'test.exe'
            cfile.write_text(source, encoding='utf-8')
            subprocess.run([compiler, '-std=c11', str(cfile), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)

    def test_capture_lifetime_and_hydration_order(self):
        hooks = (ROOT / 'source/ue4_hooks.c').read_text(encoding='utf-8')
        setup = function(hooks, 'pes_exhibition_match_setup_data_entry')
        self.assertLess(setup.index('exhibition_restore_pre_strategy_squad_snapshot()'),
                        setup.index('live_gameplan_capture_identity()'))
        self.assertLess(setup.index('live_gameplan_capture_identity()'),
                        setup.index('exhibition_discard_pre_strategy_squad_snapshot()'))
        child = function(hooks, 'pes_match_squad_edit_update_entry')
        self.assertEqual(child.count('matchplan_squad_load()'), 1)
        for side in (0, 1):
            self.assertLess(child.index('matchplan_squad_load()'),
                            child.index(f'live_gameplan_restore_identity({side})'))
            self.assertLess(child.index(f'live_gameplan_restore_identity({side})'),
                            child.index(f'prematch_gameplan_refresh_side({side})'))
        reset = function(hooks, 'exhibition_gameplan_reset')
        self.assertNotIn('live_gameplan_identity', reset)
        self.assertNotIn('match_gameplan_players[legacy]', function(hooks, 'prematch_gameplan_refresh_side'))
        self.assertLess(child.index('&live_gameplan_returning_to_pause'),
                        child.index('if (from_pause)'))
        self.assertLess(child.index('&exhibition_gameplan_custom_active, 1'),
                        child.index('&pause_editor_transition_tick, 0'))

    def test_latest_log_proves_prematch_assets_exist(self):
        log_path = ROOT / 'local-debug/pause-console-v16-diagnostic/debug.log'
        if not log_path.exists():
            self.skipTest('User hardware log is local-only')
        log = log_path.read_text(encoding='utf-8', errors='replace')
        self.assertIn('refreshed squad stats side=0 team=108 players=30/30', log)
        self.assertIn('refreshed squad stats side=1 team=109 players=30/30', log)
        self.assertIn('portrait side=0 slot=0 id=141038', log)
        self.assertIn('portrait side=1 slot=0 id=44383', log)
        self.assertIn('name=PLAYER 1', log)
        self.assertIn('name=C. TRUSSARDI', log)


if __name__ == '__main__':
    unittest.main()
