"""Host regressions for kit focus, queued hub return and portrait ownership."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_gameplan_editor import function

ROOT = Path(__file__).resolve().parents[1]


class FrontdoorControlTests(unittest.TestCase):
    def run_c(self, source):
        compiler = shutil.which('gcc') or shutil.which('clang')
        if not compiler:
            self.skipTest('Host C compiler unavailable')
        with tempfile.TemporaryDirectory(prefix='pes-frontdoor-controls-') as folder:
            path, exe = Path(folder) / 'test.c', Path(folder) / 'test.exe'
            path.write_text(source, encoding='utf-8')
            subprocess.run([compiler, '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-I', str(ROOT / 'source'), str(path), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)

    def test_preset_save_and_load_require_explicit_confirmation_per_side(self):
        hooks = (ROOT / 'source/ue4_hooks.c').read_text(encoding='utf-8')
        header = (ROOT / 'source/ue4_hooks.h').read_text(encoding='utf-8')
        definitions = '\n'.join(line for line in header.splitlines()
                                if line.startswith(('#define PES_PAUSE_INPUT_', '#define PES_PREMATCH_GAMEPLAN_PAGE_')))
        code = r'''
#include <stdint.h>
#include <stdio.h>
#include <assert.h>
#include <string.h>
#include "gameplan_preset.h"
typedef struct {
  uint32_t page, preset_step, preset_action, preset_focus, preset_target_slot;
  char preset_status[48];
} PrematchGameplanSide;
static PrematchGameplanSide exhibition_gameplan_sides[2];
static void *live_gameplan_window;
static unsigned saves, loads, refreshes, last_side, last_slot;
static int prematch_gameplan_save_preset(uint32_t side,uint32_t slot) {
  saves++;last_side=side;last_slot=slot;return 1;
}
static int prematch_gameplan_load_preset(uint32_t side,uint32_t slot) {
  loads++;last_side=side;last_slot=slot;return 1;
}
static void prematch_gameplan_refresh_preset_slots(uint32_t side) {(void)side;refreshes++;}
'''
        code += definitions + '\n' + function(hooks, 'prematch_gameplan_process_preset')
        code += r'''
int main(void) {
  for(unsigned side=0;side<2;side++)for(unsigned load=0;load<2;load++) {
    PrematchGameplanSide *s=&exhibition_gameplan_sides[side];
    memset(s,0,sizeof(*s));s->page=PES_PREMATCH_GAMEPLAN_PAGE_PRESET;
    s->preset_step=1;s->preset_action=load;s->preset_focus=2;
    const unsigned before=saves+loads, refreshed=refreshes;
    prematch_gameplan_process_preset(side,PES_PAUSE_INPUT_DECIDE);
    assert(s->preset_step==2 && s->preset_focus==1 && s->preset_target_slot==2);
    assert(saves+loads==before && refreshes==refreshed);
    prematch_gameplan_process_preset(side,PES_PAUSE_INPUT_DECIDE);
    assert(s->preset_step==1 && s->preset_focus==2 && saves+loads==before);
    prematch_gameplan_process_preset(side,PES_PAUSE_INPUT_DECIDE);
    prematch_gameplan_process_preset(side,PES_PAUSE_INPUT_LEFT);
    prematch_gameplan_process_preset(side,PES_PAUSE_INPUT_BACK);
    assert(s->preset_step==1 && s->preset_focus==2 && saves+loads==before);
    prematch_gameplan_process_preset(side,PES_PAUSE_INPUT_DECIDE);
    prematch_gameplan_process_preset(side,PES_PAUSE_INPUT_LEFT);
    prematch_gameplan_process_preset(side,PES_PAUSE_INPUT_DECIDE);
    assert(saves+loads==before+1 && last_side==side && last_slot==2 && refreshes==refreshed+1);
    assert(s->preset_step==1 && s->preset_focus==2);
    /* Further A opens a fresh safe modal, never repeats the write. */
    prematch_gameplan_process_preset(side,PES_PAUSE_INPUT_DECIDE);
    assert(s->preset_focus==1 && saves+loads==before+1);
    prematch_gameplan_process_preset(side,PES_PAUSE_INPUT_BACK);
    live_gameplan_window=(void*)1;
    prematch_gameplan_process_preset(side,PES_PAUSE_INPUT_DECIDE);
    assert(s->preset_step==1 && saves+loads==before+1);
    live_gameplan_window=0;
  }
  assert(saves==2 && loads==2);
  return 0;
}
'''
        self.run_c(code)

    def test_kits_container_then_edit_without_up_down(self):
        self.run_c(r'''
#include <assert.h>
#include "prematch_kit_navigation.h"
int main(void) {
  PesKitNavigation nav = {0, 0};
  assert(pes_kit_navigate(&nav, 1u<<13) == PES_KIT_STAY);
  assert(nav.side == 1 && !nav.editing);
  assert(pes_kit_navigate(&nav, 1u<<1) == PES_KIT_STAY && nav.editing);
  assert(pes_kit_navigate(&nav, 1u<<12) == PES_KIT_PREVIOUS && nav.side == 1);
  assert(pes_kit_navigate(&nav, 1u<<13) == PES_KIT_NEXT && nav.side == 1);
  assert(pes_kit_navigate(&nav, 1u<<1) == PES_KIT_STAY && nav.editing);
  assert(pes_kit_navigate(&nav, 1u<<10) == PES_KIT_STAY && nav.side == 1);
  assert(pes_kit_navigate(&nav, 1u<<11) == PES_KIT_STAY && nav.side == 1);
  assert(pes_kit_navigate(&nav, 1u<<0) == PES_KIT_STAY && !nav.editing);
  assert(pes_kit_navigate(&nav, 1u<<12) == PES_KIT_STAY && nav.side == 0);
  assert(pes_kit_navigate(&nav, 1u<<0) == PES_KIT_BACK);
  return 0;
}
''')

    def test_hub_back_only_queues_native_teardown(self):
        hooks = (ROOT / 'source/ue4_hooks.c').read_text()
        pad = function(hooks, 'pes_controller_2p_prematch_hub_pad_event')
        self.assertNotIn('main_menu_2p_team_selector_close()', pad)
        self.assertIn('&main_menu_2p_team_selector_close_pending, 1u', pad)
        process = function(hooks, 'main_menu_2p_team_selector_process_pending')
        self.assertIn('main_menu_2p_team_selector_process_pending();', function(hooks, 'cobra_pad_apply_input'))
        code = r'''
#include <stdint.h>
#include <assert.h>
#define MAIN_MENU_2P_TRANSITION_NONE 0u
#define debugPrintf(...) ((void)0)
static uint32_t main_menu_2p_team_selector_close_pending, main_menu_2p_team_selector_start_pending;
static uint32_t main_menu_2p_team_selector_exhibition_mode, main_menu_2p_team_selector_active;
static uint32_t main_menu_controller_active, main_menu_2p_transition_active, main_menu_2p_transition_kind;
static unsigned closes, starts;
static void main_menu_2p_team_selector_close(void) {closes++; main_menu_2p_team_selector_start_pending=0;}
static int main_menu_start_exhibition_match(void) {starts++;return 1;}
static int main_menu_start_two_player_match(void) {starts++;return 1;}
'''
        code += process
        code += r'''
int main(void) {
  main_menu_2p_team_selector_close_pending=1;main_menu_2p_team_selector_start_pending=1;
  main_menu_2p_team_selector_process_pending();
  assert(closes==1 && !starts && !main_menu_2p_team_selector_close_pending);
  main_menu_2p_team_selector_process_pending();assert(closes==1 && !starts);
  return 0;
}
'''
        self.run_c(code)

    def test_portrait_renderer_only_publishes_ids_game_thread_owns_cache(self):
        hooks = (ROOT / 'source/ue4_hooks.c').read_text()
        producer = function(hooks, 'pes_controller_league_request_scorer_portrait')
        for forbidden in ('malloc(', 'free(', 'memcpy(', 'live_portrait_cache[', 'live_gameplan_poll_portraits('):
            self.assertNotIn(forbidden, producer)
        self.assertIn('league_process_portrait_requests();', function(hooks, 'cobra_pad_apply_input'))
        code = r'''
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define LIVE_PORTRAIT_CACHE_CAPACITY 2u
typedef struct {uint32_t portrait_id, byte_count; unsigned char bytes[8];} PesPrematchGameplanPortraitPng;
static uint32_t league_portrait_requests[5];
static uintptr_t exhibition_gameplan_portrait_pending[2][40];
static PesPrematchGameplanPortraitPng *live_portrait_cache[2];
static unsigned polls, requested;
static void live_gameplan_poll_portraits(void) {polls++;}
static void live_gameplan_request_portrait(uint32_t id) {requested=id;}
'''
        code += producer + '\n' + function(hooks, 'league_process_portrait_requests')
        code += r'''
int main(void) {
  PesPrematchGameplanPortraitPng cached={42,0,{0}};live_portrait_cache[0]=&cached;
  for(unsigned i=0;i<10000;i++)pes_controller_league_request_scorer_portrait(0,41);
  pes_controller_league_request_scorer_portrait(0,42);
  pes_controller_league_request_scorer_portrait(4,91);
  pes_controller_league_request_scorer_portrait(5,99);
  assert(!polls && !requested && !exhibition_gameplan_portrait_pending[0][35]);
  league_process_portrait_requests();
  assert(polls==1 && requested==91);
  PesPrematchGameplanPortraitPng *copy=(void*)exhibition_gameplan_portrait_pending[0][35];
  assert(copy && copy!=&cached && copy->portrait_id==42);free(copy);
  league_process_portrait_requests();assert(polls==1);
  return 0;
}
'''
        self.run_c(code)

    def test_hud_portraits_use_bounded_game_thread_mailboxes_and_copied_ownership(self):
        hooks = (ROOT / 'source/ue4_hooks.c').read_text()
        code = r'''
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define LIVE_PORTRAIT_CACHE_CAPACITY 2u
typedef struct {uint32_t portrait_id,byte_count;unsigned char bytes[];} PesPrematchGameplanPortraitPng;
static uint32_t match_hud_portrait_requests[2];
static uintptr_t exhibition_gameplan_portrait_pending[2][40];
static PesPrematchGameplanPortraitPng *live_portrait_cache[2];
static uint64_t live_portrait_cache_stamp[2],live_portrait_cache_clock;
static unsigned polls,requested;
static void live_gameplan_poll_portraits(void) {polls++;}
static void live_gameplan_request_portrait(uint32_t id) {requested=id;}
'''
        code += function(hooks, 'pes_controller_hud_request_portrait') + '\n'
        code += function(hooks, 'match_hud_process_portrait_requests') + r'''
int main(void) {
  PesPrematchGameplanPortraitPng *cached=malloc(sizeof(*cached)+8u);
  cached->portrait_id=42;cached->byte_count=8;memset(cached->bytes,93,8);
  live_portrait_cache[0]=cached;
  for(unsigned i=0;i<10000;i++)pes_controller_hud_request_portrait(0,41);
  pes_controller_hud_request_portrait(0,42);
  pes_controller_hud_request_portrait(1,91);
  pes_controller_hud_request_portrait(2,99);
  assert(!polls && !requested && !exhibition_gameplan_portrait_pending[0][0]);
  match_hud_process_portrait_requests();assert(polls==1 && requested==91);
  PesPrematchGameplanPortraitPng *copy=(void *)exhibition_gameplan_portrait_pending[0][0];
  assert(copy && copy!=cached && copy->portrait_id==42 && copy->byte_count==8 && copy->bytes[7]==93);
  assert(live_portrait_cache_stamp[0]==1);
  // A queued copy must survive CPU eviction and a repeated request can safely
  // replace the pending copy without retaining an unbounded linked queue.
  pes_controller_hud_request_portrait(0,42);match_hud_process_portrait_requests();
  copy=(void *)exhibition_gameplan_portrait_pending[0][0];
  free(cached);live_portrait_cache[0]=NULL;
  assert(copy->bytes[7]==93);free(copy);exhibition_gameplan_portrait_pending[0][0]=0;
  match_hud_process_portrait_requests();assert(polls==2);
  pes_controller_hud_request_portrait(0,42);match_hud_process_portrait_requests();
  assert(requested==42 && !exhibition_gameplan_portrait_pending[0][0]);
  return 0;
}
'''
        self.run_c(code)

    def test_resident_portraits_are_not_decoded_or_reuploaded_on_repeated_requests(self):
        overlay = (ROOT/'source/overlay.c').read_text()
        code = r'''
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
typedef int GLint;typedef unsigned GLuint;typedef unsigned GLenum;
#define PREMATCH_GAMEPLAN_PORTRAIT_CACHE_SIZE 3
#define GL_TEXTURE0 100u
#define GL_ACTIVE_TEXTURE 1u
#define GL_TEXTURE_BINDING_2D 2u
#define GL_UNPACK_ALIGNMENT 3u
#define GL_TEXTURE_2D 4u
#define GL_TEXTURE_MIN_FILTER 5u
#define GL_TEXTURE_MAG_FILTER 6u
#define GL_TEXTURE_WRAP_S 7u
#define GL_TEXTURE_WRAP_T 8u
#define GL_LINEAR_MIPMAP_LINEAR 9u
#define GL_LINEAR 10u
#define GL_CLAMP_TO_EDGE 11u
#define GL_RGBA 12u
#define GL_UNSIGNED_BYTE 13u
static struct { GLuint player_portrait_texture[3];uint32_t player_portrait_id[3],player_portrait_stamp[3],player_portrait_clock; } gl;
typedef struct { uint32_t portrait_id,byte_count;unsigned char bytes[]; } PesPrematchGameplanPortraitPng;
static PesPrematchGameplanPortraitPng *pending_png[2][40];
static unsigned decoded,uploaded,mips,generated,active=GL_TEXTURE0+2,binding[3]={91,92,93},unpack=4;
static PesPrematchGameplanPortraitPng *pes_controller_custom_prematch_gameplan_take_portrait_png(unsigned side,unsigned index) {
  PesPrematchGameplanPortraitPng *p=pending_png[side][index];pending_png[side][index]=NULL;return p;
}
static void glGetIntegerv(GLenum name,GLint *out) { *out=name==GL_ACTIVE_TEXTURE?active:name==GL_UNPACK_ALIGNMENT?unpack:binding[active-GL_TEXTURE0]; }
static void glActiveTexture(GLenum value) { active=value; }
static void glPixelStorei(GLenum name,GLint value) { (void)name;unpack=value; }
static void glBindTexture(GLenum target,GLuint value) { (void)target;binding[active-GL_TEXTURE0]=value; }
static void glGenTextures(GLint n,GLuint *out) { assert(n==1);*out=++generated; }
static void glTexParameteri(GLenum a,GLenum b,GLint c) {(void)a;(void)b;(void)c;}
static void glTexImage2D(GLenum a,GLint b,GLint c,GLint d,GLint e,GLint f,GLenum g,GLenum h,const void *p) {
  (void)a;(void)b;(void)c;(void)d;(void)e;(void)f;(void)g;(void)h;assert(p);uploaded++;
}
static void glGenerateMipmap(GLenum a) {(void)a;mips++;}
static int decode_png_memory(const void *bytes,size_t length,unsigned char **out,GLint *w,GLint *h) {
  assert(bytes && length==1);decoded++;*out=malloc(1);*w=*h=128;return 1;
}
static void queue(unsigned side,unsigned index,unsigned id) {
  assert(!pending_png[side][index]);
  PesPrematchGameplanPortraitPng *p=malloc(sizeof(*p)+1);
  p->portrait_id=id;p->byte_count=1;p->bytes[0]=1;pending_png[side][index]=p;
}
'''
        for name in ('gameplan_portrait_cache_slot', 'gameplan_portrait_replacement_slot', 'prepare_gameplan_portraits'):
            code += function(overlay, name) + '\n'
        code += r'''
int main(void) {
  queue(0,0,42);queue(1,0,42);prepare_gameplan_portraits(1);
  assert(decoded==1 && uploaded==1 && mips==1 && generated==1);
  for(unsigned i=0;i<1000;i++) {queue(0,35,42);prepare_gameplan_portraits(1);}
  assert(decoded==1 && uploaded==1 && mips==1 && generated==1);
  assert(active==GL_TEXTURE0+2 && unpack==4 && binding[0]==91 && binding[2]==93);
  queue(0,0,43);queue(0,1,44);queue(0,2,45);prepare_gameplan_portraits(1);
  assert(decoded==4 && generated==3 && gameplan_portrait_cache_slot(42)<0);
  queue(0,0,42);prepare_gameplan_portraits(1);
  assert(decoded==5 && uploaded==5 && mips==5 && generated==3);
  assert(gameplan_portrait_cache_slot(42)>=0 && active==GL_TEXTURE0+2 && unpack==4);
  return 0;
}
'''
        self.run_c(code)
