"""Cold-cache asynchronous portraits and native pending substitution projection."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from test_gameplan_editor import function, struct

ROOT = Path(__file__).resolve().parents[1]


class PauseV19Tests(unittest.TestCase):
    def run_c(self, source):
        compiler = shutil.which('gcc') or shutil.which('clang')
        if not compiler:
            self.skipTest('Host C compiler required')
        with tempfile.TemporaryDirectory(prefix='pes-pause-v19-') as folder:
            cfile, exe = Path(folder) / 'test.c', Path(folder) / 'test.exe'
            cfile.write_text(source, encoding='utf-8')
            subprocess.run([compiler, '-std=c11', str(cfile), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)

    def test_portraits_load_with_cold_cache_without_blocking(self):
        hooks = (ROOT / 'source/ue4_hooks.c').read_text(encoding='utf-8')
        header = (ROOT / 'source/ue4_hooks.h').read_text(encoding='utf-8')
        code = r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#define debugPrintf(...) ((void)0)
#define LIVE_PORTRAIT_CACHE_CAPACITY 80u
#define LIVE_PORTRAIT_READS 4u
#define PREMATCH_GAMEPLAN_PORTRAIT_MAX_BYTES (1024u*1024u)
static uint64_t now, exhibition_gameplan_portrait_retry_tick[2];
static uint64_t armGetSystemTick(void) {return now;}
static uint64_t armTicksToNs(uint64_t t) {return t;}
typedef struct {int used,busy,error; uint32_t id; unsigned char body[8];} File;
static File files[4]; static unsigned creates, releases, starts, missing_checks;
static int exhibition_sys_file_exists(const char *path) {
 unsigned id=0; assert(sscanf(path,"common/player/%u.png",&id)==1);
 if(id==3) missing_checks++;
 return id<100 && id!=3;
}
static void *exhibition_sys_file_create(const char *path, int mode) {
 assert(mode==0xc01); unsigned id=0; sscanf(path,"common/player/%u.png",&id);
 for(unsigned i=0;i<4;i++) if(!files[i].used) {
  File *f=&files[i]; memset(f,0,sizeof(*f)); f->id=id; f->used=f->busy=1;
  const unsigned char png[]={0x89,'P','N','G',13,10,26,10}; memcpy(f->body,png,8);
  creates++; return f;
 }
 assert(0); return NULL;
}
static void exhibition_sys_file_release(void *p) { File *f=p; assert(f->used); f->used=0; releases++; }
static void exhibition_sys_file_read_start(void *p) {assert(((File*)p)->used); starts++;}
static int exhibition_sys_file_busy(void *p) {return ((File*)p)->busy;}
static int exhibition_sys_file_error(void *p) {return ((File*)p)->error;}
static void exhibition_sys_file_error_stop(void *p,int stop) {assert(stop==0);}
static void exhibition_sys_file_post_wait(void *p,int wait) {assert(wait==0);}
static void *exhibition_sys_file_get_body(void *p) {assert(!((File*)p)->busy); return ((File*)p)->body;}
static size_t exhibition_sys_file_get_size(void *p) {return 8;}
'''
        code += struct(header, 'PesPrematchGameplanPortraitPng') + '\n'
        code += struct(hooks, 'LivePortraitRead') + r'''
static LivePortraitRead live_portrait_reads[4];
static uint32_t live_portrait_failed[80], live_portrait_failed_count;
static PesPrematchGameplanPortraitPng *live_portrait_cache[80];
static uint64_t live_portrait_cache_stamp[80],live_portrait_cache_clock;
'''
        code += '\n'.join(function(hooks, name) for name in (
            'live_gameplan_cache_portrait', 'live_gameplan_cancel_portraits',
            'live_gameplan_portrait_failed', 'live_gameplan_request_portrait',
            'live_gameplan_poll_portraits'))
        code += r'''
int main(void) {
 live_gameplan_request_portrait(1); live_gameplan_request_portrait(1);
 live_gameplan_request_portrait(3); live_gameplan_request_portrait(3);
 live_gameplan_request_portrait(2); live_gameplan_request_portrait(4); live_gameplan_request_portrait(5);
 live_gameplan_request_portrait(6);
 assert(creates==4 && starts==4 && missing_checks==1);
 live_gameplan_poll_portraits(); assert(!releases && !live_portrait_cache[0]);
 for(unsigned i=0;i<4;i++) if(files[i].id==1) files[i].busy=0;
 live_gameplan_poll_portraits(); assert(releases==1);
 assert(live_portrait_cache[0] && live_portrait_cache[0]->portrait_id==1);
 assert(live_portrait_cache[0]->byte_count==8);
 live_gameplan_request_portrait(6); assert(creates==5);
 for(unsigned i=0;i<4;i++) {
  if(files[i].id==2) files[i].error=1;
  if(files[i].id==4) { files[i].busy=0; files[i].body[0]=0; }
 }
 live_gameplan_poll_portraits(); assert(releases==3);
 now=6000000000ULL; live_gameplan_poll_portraits(); assert(releases==5);
 live_gameplan_request_portrait(2); live_gameplan_request_portrait(4); live_gameplan_request_portrait(5);
 assert(creates==5); // failed assets do not repeatedly hammer native IO
 live_gameplan_cancel_portraits(); assert(!live_portrait_failed_count);
 live_gameplan_request_portrait(0x00100009); assert(creates==6); // verified variant path
 live_gameplan_cancel_portraits(); assert(releases==6); // safely release a busy job on Back
 assert(live_portrait_cache[0]->portrait_id==1); // cache survives UI reset
 for(unsigned i=0;i<80;i++) free(live_portrait_cache[i]);
 return 0;
}
'''
        self.run_c(code)

    def test_pending_substitutions_project_without_native_roster_mutation(self):
        hooks = (ROOT / 'source/ue4_hooks.c').read_text(encoding='utf-8')
        code = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#define PREMATCH_GAMEPLAN_MAX_PLAYERS 40u
'''
        code += '\n'.join(struct(hooks, name) for name in (
            'TmpdbFormationValue', 'TmpdbMatchPlanSettingsValue',
            'PrematchGameplanPlayer', 'PrematchGameplanSide'))
        code += r'''
typedef struct { uint32_t reserved[40], formation, substitutions; } Native;
static uint32_t live_squad_reserved_member(const void *p,uint32_t id) {return ((const Native*)p)->reserved[id];}
'''
        code += function(hooks, 'live_gameplan_project_reservations')
        code += r'''
int main(void) {
 Native native={0}; for(unsigned i=0;i<40;i++) native.reserved[i]=i;
 native.formation=433; native.substitutions=3;
 PrematchGameplanSide base={0}; base.squad_data=&native; base.player_count=4;
 // Nontrivial vector order: bench appears before its paired starter.
 unsigned members[]={14,8,10,12};
 for(unsigned i=0;i<4;i++) {
  PrematchGameplanPlayer *p=&base.players[i]; p->member_id=members[i];
  p->player_id[0]=members[i]; p->portrait_id=1000+members[i];
  p->starting=(i==1 || i==2); p->order_no=p->starting ? i : 11+i;
  p->role=i+1; p->pitch_x=30+i; p->pitch_y=60+i;
 }
 native.reserved[8]=14; native.reserved[14]=8;
 native.reserved[10]=12; native.reserved[12]=10;
 Native saved=native; PrematchGameplanSide state=base;
 live_gameplan_project_reservations(&state);
 assert(!memcmp(&native,&saved,sizeof(native)));
 assert(state.players[0].starting && state.players[0].order_no==1);
 assert(!state.players[1].starting && state.players[1].order_no==11);
 assert(state.players[0].role==base.players[1].role && state.players[0].pitch_y==61);
 assert(state.players[3].starting && !state.players[2].starting);
 for(unsigned i=0;i<4;i++) {
  assert(state.players[i].member_id==members[i]);
  assert(state.players[i].player_id[0]==members[i]);
  assert(state.players[i].portrait_id==1000+members[i]);
 }
 // A fresh refresh is idempotent; cancellation/already-applied native state
 // returns the original member and must not project a second substitution.
 PrematchGameplanSide again=base; live_gameplan_project_reservations(&again);
 assert(!memcmp(&again,&state,sizeof(state)));
 for(unsigned i=0;i<40;i++) native.reserved[i]=i;
 state=base; live_gameplan_project_reservations(&state);
 assert(!memcmp(&state,&base,sizeof(base)));
 native.reserved[8]=255; state=base; live_gameplan_project_reservations(&state);
 assert(!memcmp(&state,&base,sizeof(base)));
 return 0;
}
'''
        self.run_c(code)

    def test_lifecycle_wires_cache_miss_poll_and_close(self):
        hooks = (ROOT / 'source/ue4_hooks.c').read_text(encoding='utf-8')
        read = function(hooks, 'prematch_gameplan_load_portrait')
        self.assertLess(read.index('live_gameplan_request_portrait(portrait_id)'),
                        read.index('exhibition_sys_file_sync_read(file)'))
        self.assertIn('live_gameplan_poll_portraits()', function(hooks, 'exhibition_gameplan_process_pending'))
        self.assertIn('live_gameplan_cancel_portraits()', function(hooks, 'exhibition_gameplan_reset'))
        self.assertIn('live_gameplan_cancel_portraits()', function(hooks, 'prematch_gameplan_process_root'))
        refresh = function(hooks, 'prematch_gameplan_refresh_side')
        self.assertLess(refresh.index('live_gameplan_project_reservations(state)'),
                        refresh.index('prematch_gameplan_sort_players(state)'))

    def test_bench_swap_commits_native_reservation_and_refreshes_preview(self):
        hooks = (ROOT / 'source/ue4_hooks.c').read_text(encoding='utf-8')
        header = (ROOT / 'source/ue4_hooks.h').read_text(encoding='utf-8')
        code = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#define debugPrintf(...) ((void)0)
#define PREMATCH_GAMEPLAN_MAX_PLAYERS 40u
#define PREMATCH_GAMEPLAN_NO_SELECTION UINT32_MAX
'''
        code += '\n'.join(line for line in header.splitlines()
                          if line.startswith('#define PES_PREMATCH_GAMEPLAN_AREA_')) + '\n'
        code += '\n'.join(struct(hooks, name) for name in (
            'TmpdbFormationValue', 'TmpdbMatchPlanSettingsValue',
            'PrematchGameplanPlayer', 'PrematchGameplanSide'))
        code += r'''
static PrematchGameplanSide exhibition_gameplan_sides[2], authoritative;
static void *live_gameplan_window=(void*)1;
static unsigned allowed=1,reserves,saves,replacements,pending;
static uint32_t match_squad_data_get_order_no(void *s,const void *key) {return *(const unsigned char*)key==8 ? 8 : 14;}
static uint32_t match_squad_data_get_member_id(void *s,const void *key) {return *(const unsigned char*)key;}
static void match_swap_member_info_construct(void *p,uint32_t o,uint32_t m,const void *k) {}
static void match_replace_squad_player(void *s,const void *a,const void *b) {replacements++;}
static int live_squad_can_reserve(void *s,uint32_t out,uint32_t in) {
 assert((out==8 && in==14)||(out==14 && in==8)); return allowed;
}
static int live_squad_reserve(void *s,uint32_t out,uint32_t in) {reserves++; pending=!pending; return 1;}
static uint32_t live_squad_reserved_member(const void *s,uint32_t id) {return pending ? (id==8 ? 14 : 8) : id;}
'''
        code += function(hooks, 'prematch_gameplan_nth_player')
        code += function(hooks, 'live_gameplan_project_reservations')
        code += r'''
static void prematch_gameplan_save_and_refresh(uint32_t side) {
 saves++;
 // Native order is unchanged while a reservation is pending, as in the log.
 exhibition_gameplan_sides[side]=authoritative;
 live_gameplan_project_reservations(&exhibition_gameplan_sides[side]);
}
'''
        code += function(hooks, 'prematch_gameplan_swap')
        code += r'''
int main(void) {
 authoritative.squad_data=&pending; authoritative.player_count=2;
 authoritative.selected_area=PES_PREMATCH_GAMEPLAN_AREA_FIELD;
 authoritative.selected_index=0;
 for(unsigned i=0;i<2;i++) {
  PrematchGameplanPlayer *p=&authoritative.players[i];
  p->member_id=i ? 14 : 8; p->player_id[0]=p->member_id;
  p->starting=!i; p->order_no=i ? 14 : 8;
 }
 exhibition_gameplan_sides[0]=authoritative;
 prematch_gameplan_swap(0);
 assert(reserves==1 && saves==1 && pending && replacements==0);
 assert(!exhibition_gameplan_sides[0].players[0].starting);
 assert(exhibition_gameplan_sides[0].players[1].starting);
 // Same two displayed players selected again cancels the pending change.
 prematch_gameplan_swap(0);
 assert(reserves==2 && saves==2 && !pending && replacements==0);
 assert(exhibition_gameplan_sides[0].players[0].starting);
 allowed=0; prematch_gameplan_swap(0);
 assert(reserves==2 && saves==2 && !pending && replacements==0);
 // Before-match still uses the ordinary roster edit, not live reservations.
 live_gameplan_window=NULL; prematch_gameplan_swap(0);
 assert(replacements==1 && reserves==2 && saves==3);
 return 0;
}
'''
        self.run_c(code)


if __name__ == '__main__':
    unittest.main()
