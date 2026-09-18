"""Executable regressions for stamina snapshots and set-piece aim/curve."""
from pathlib import Path
import shutil
import unittest
from test_gameplan_editor import function
from test_result_flow import build_and_run

ROOT = Path(__file__).resolve().parents[1]

class OnfieldTests(unittest.TestCase):
    def test_hud_cached_identity_survives_unavailable_tmpdb(self):
        hooks = (ROOT / 'source/ue4_hooks.c').read_text()
        code = r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#define PREMATCH_GAMEPLAN_MAX_PLAYERS 40
typedef struct { uint32_t side,player_no,portrait_id,badge,shirt_number; char name[48]; } PesStaminaBarSnapshot;
typedef struct { uint64_t common_player_id; char name[48]; uint32_t hud_shirt_number; } LiveGameplanIdentity;
typedef struct { uint32_t team,player_no,portrait_id,badge,shirt_number; uint64_t seen_tick; char name[48]; } MatchHudIdentityCache;
static LiveGameplanIdentity live_gameplan_identity[2][40];
static MatchHudIdentityCache match_hud_identity_cache[2];
static uint32_t live_gameplan_identity_team[2]={106,1589};
static uint32_t exhibition_home_team_id=106,exhibition_away_team_id=1589,member=2;
static uint64_t now=100;
static uint64_t armGetSystemTick(void) { return now; }
static uint64_t armTicksToNs(uint64_t ticks) { return ticks; }
static void match_hud_queue_portrait(uint32_t side,uint32_t order,uint32_t id) {}
static const void *registry(void) { return (void *)1; }
static const void *orders(const void *p,uint32_t side) { return (void *)2; }
static uint32_t get_member(const void *p,uint32_t order) { return member; }
static const void *(*match_global_registry_get_instance)(void)=registry;
static const void *(*match_global_registry_get_order_info)(const void *,uint32_t)=orders;
static uint32_t (*match_order_info_get_member_id)(const void *,uint32_t)=get_member;
static void *(*exhibition_tmpdb_manager_get_instance)(void);
static const void *(*match_tmpdb_match_get_player)(const void *,const uint32_t *,const uint32_t *);
static const char *(*match_tmpdb_player_get_name)(const void *);
static uint32_t (*match_hud_uniform_number)(const void *,const uint32_t *);
static uint32_t (*match_hud_resolve_shirt_number)(uint32_t,uint32_t);
static uint32_t prematch_gameplan_portrait_id(const void *p,const unsigned char *id) {
  uint32_t result=0; if(id) memcpy(&result,id,4); return result;
}
static uint32_t pes_controller_2p_prematch_hub_badge(uint32_t side) { return 7+side; }
''' + function(hooks, 'match_hud_cached_identity') + '\n' + function(
            hooks, 'match_hud_cache_identity') + '\n' + function(
            hooks[hooks.index('static int match_hud_player_info(PesStaminaBarSnapshot *bar) {'):],
            'match_hud_player_info') + r'''
int main(void) {
  live_gameplan_identity[0][2]=(LiveGameplanIdentity){(uint64_t)12345<<32,"Player A",7};
  live_gameplan_identity[0][18]=(LiveGameplanIdentity){(uint64_t)54321<<32,"Substitute",19};
  PesStaminaBarSnapshot bar={0}; bar.player_no=4;
  for(int i=0;i<120;i++) {
    assert(match_hud_player_info(&bar));
    assert(!strcmp(bar.name,"Player A"));
    assert(bar.portrait_id==12345 && bar.shirt_number==7 && bar.badge==7);
  }
  member=UINT32_MAX; now=400;
  assert(match_hud_player_info(&bar));
  assert(!strcmp(bar.name,"Player A"));
  now=600000001; assert(!match_hud_player_info(&bar));
  now=100;
  member=18; assert(match_hud_player_info(&bar));
  assert(!strcmp(bar.name,"Substitute") && bar.shirt_number==19);
  exhibition_home_team_id=999; assert(!match_hud_player_info(&bar));
  member=UINT32_MAX; assert(!match_hud_player_info(&bar));
}
'''
        build_and_run(self.cc, code)

    def test_hud_portraits_use_async_read_and_overlay_upload_queue(self):
        hooks = (ROOT / 'source/ue4_hooks.c').read_text()
        snapshot = function(hooks, 'pes_controller_stamina_bars')
        queue = function(hooks, 'match_hud_queue_portrait')
        self.assertIn('live_gameplan_poll_portraits();', snapshot)
        self.assertIn('live_gameplan_request_portrait(portrait_id);', queue)
        self.assertIn('exhibition_gameplan_portrait_pending[side][order]', queue)
        self.assertNotIn('prematch_gameplan_load_portrait(', queue)

    def test_hud_refresh_uses_live_names_not_disabled_gauges(self):
        hooks = (ROOT / 'source/ue4_hooks.c').read_text()
        names = function(hooks, 'pes_match_cursor_name_get_position')
        gauge = function(hooks, 'pause_stamina_disp')
        self.assertIn('match_stamina_publish_from_model(model, index & 1u)', names)
        self.assertNotIn('match_stamina_publish_from_model', gauge)
        snapshot = function(hooks, 'pes_controller_stamina_bars')
        self.assertLess(snapshot.index('&match_stamina_info_seen_tick[side]'),
                        snapshot.index('const uint64_t now = armGetSystemTick()'))

    def test_custom_hud_ignores_native_gauge_suppression(self):
        hooks = (ROOT / 'source/ue4_hooks.c').read_text()
        code = r'''
#include <stdint.h>
#include <string.h>
#include <assert.h>
#include <stddef.h>
#define HUD_DIAG_EVENT(n) ((void)0)
static uint32_t match_stamina_active_mask, match_stamina_power_milli[2];
static uint32_t match_stamina_player_no[2];
static uint64_t match_stamina_info_seen_tick[2], match_hud_inplay_tick;
static uint64_t armGetSystemTick(void) { return 123; }
static int inplay = 1;
static uint32_t is_inplay(const void *p) { return inplay; }
static uint32_t (*match_utility_info_is_inplay_time)(const void *) = is_inplay;
static const void *get_registry(void) { return (void *)1; }
static const void *get_player(const void *r, uint32_t p) { return (void *)2; }
static uint32_t get_percentage(const void *p) { return 73; }
static const void *(*match_global_registry_get_instance)(void)=get_registry;
static const void *(*match_hud_get_player_info)(const void *, uint32_t)=get_player;
static uint32_t (*match_hud_get_stamina_percentage)(const void *)=get_percentage;
static void match_hud_observe_ball_motion(const void *registry) {(void)registry;}
''' + function(hooks, 'match_stamina_clear_side') + '\n' + function(
            hooks, 'match_stamina_hold_side') + '\n' + function(
            hooks, 'match_stamina_publish_from_model') + r'''
int main(void) {
  unsigned char info[0x1a40]={0}, model[0x20]={0};
  const void *ptr=info;
  memcpy(model+0x18,&ptr,sizeof(ptr));
  uint32_t player=4;
  memcpy(info+0x190,&player,4);
  info[0x194]=0; info[0x195]=255; info[0x1a0]=1;
  /* Native presentation suppression must not disable the custom card. */
  info[0x1a30]=1;
  match_stamina_publish_from_model(model,0);
  assert(match_stamina_active_mask==1);
  assert(match_stamina_player_no[0]==4);
  assert(match_stamina_power_milli[0]==730);
  assert(match_hud_inplay_tick==123);
  inplay=0;
  match_stamina_publish_from_model(model,0);
  assert(!match_stamina_active_mask && !match_hud_inplay_tick);
  inplay=1; info[0x1a0]=0;
  match_stamina_publish_from_model(model,0);
  assert(match_stamina_active_mask==1);
  assert(match_stamina_power_milli[0]==730);
  player=UINT32_MAX;
  memcpy(info+0x190,&player,4);
  memcpy(info+0x490,&player,4);
  match_stamina_publish_from_model(model,0);
  assert(match_stamina_active_mask==1 && match_stamina_info_seen_tick[0]==123);
  match_stamina_publish_from_model(NULL,0);
  assert(!match_hud_inplay_tick && !match_stamina_active_mask);
}
'''
        build_and_run(self.cc, code)

    def test_match_hud_waits_for_real_ball_motion(self):
        hooks = (ROOT / 'source/ue4_hooks.c').read_text()
        code = r'''
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <string.h>
static uint32_t match_hud_play_started;
static uintptr_t match_hud_ball_owner;
static float match_hud_ball_anchor_x,match_hud_ball_anchor_z;
static uint32_t match_hud_ball_anchor_valid;
static const float *ball_trans(const void *p) { return p; }
static const float *(*match_ball_info_get_trans)(const void *)=ball_trans;
''' + function(hooks, 'match_hud_reset_ball_motion') + '\n' + function(
            hooks, 'match_hud_observe_ball_motion') + r'''
int main(void) {
  unsigned char registry[0x98]={0};
  float ball[3]={10.0f,0.0f,20.0f};
  const void *ball_info=ball;
  memcpy(registry+0x90,&ball_info,sizeof(ball_info));
  match_hud_reset_ball_motion();
  match_hud_observe_ball_motion(registry);
  assert(!match_hud_play_started);
  ball[0]+=0.49f; match_hud_observe_ball_motion(registry);
  assert(!match_hud_play_started);
  ball[0]+=0.02f; match_hud_observe_ball_motion(registry);
  assert(match_hud_play_started);
  match_hud_reset_ball_motion();
  assert(!match_hud_play_started && !match_hud_ball_anchor_valid);
}
'''
        build_and_run(self.cc, code)

    def test_player_switch_keeps_last_complete_card_until_identity_is_ready(self):
        hooks = (ROOT / 'source/ue4_hooks.c').read_text()
        snapshot = function(hooks, 'pes_controller_stamina_bars')
        self.assertIn('static PesStaminaBarSnapshot presented[2]', snapshot)
        self.assertIn('*bar = presented[side]', snapshot)
        self.assertIn('presented[side] = *bar', snapshot)
        self.assertIn('match_hud_play_started', snapshot)

    def test_live_hud_gate_rejects_transitions_and_stale_frames(self):
        hooks = (ROOT / 'source/ue4_hooks.c').read_text()
        code = r'''
#include <stdint.h>
#include <assert.h>
#define PES_CONTROLLER_SURFACE_NONE 0
#define PES_MOBILE_CONTROL_UNKNOWN 0
#define PES_VIRTUAL_CURSOR_NONE 0
typedef struct { uint32_t surface; } PesControllerSnapshot;
static uint64_t match_hud_inplay_tick=100, now=100;
static int state, mode=1, blocks[9];
static uint64_t armGetSystemTick(void) { return now; }
static uint64_t armTicksToNs(uint64_t x) { return x; }
static void pes_controller_surface_cached_snapshot(PesControllerSnapshot *s) { s->surface=state; }
static int pes_mobile_control_active_mode(void) { return mode; }
#define pes_controller_replay_active() blocks[0]
#define pes_controller_goal_demo_active() blocks[1]
#define pes_controller_cinematic_skip_active() blocks[2]
#define pes_controller_fix_demo_skip_active() blocks[3]
#define pes_controller_pause_skin_active() blocks[4]
#define pes_controller_pause_transition() blocks[5]
#define pes_controller_match_result_skin() blocks[6]
#define pes_controller_match_result_transition() blocks[7]
#define pes_controller_virtual_cursor_context() blocks[8]
''' + function(hooks, 'pes_controller_match_hud_inplay') + r'''
int main(void) {
  assert(pes_controller_match_hud_inplay());
  for(int i=0;i<9;i++) { blocks[i]=1; assert(!pes_controller_match_hud_inplay()); blocks[i]=0; }
  for(state=1;state<=4;state++) assert(!pes_controller_match_hud_inplay());
  state=0; mode=0; assert(!pes_controller_match_hud_inplay());
  mode=1; now=80000101; assert(!pes_controller_match_hud_inplay());
  now=100; match_hud_inplay_tick=0; assert(!pes_controller_match_hud_inplay());
}
'''
        build_and_run(self.cc, code)

    def setUp(self):
        self.cc = shutil.which("gcc")
        if not self.cc: self.skipTest("host gcc unavailable")

    def test_height_intent_and_native_pitch_owner(self):
        route = (ROOT / 'source/native_pad_lab.inc').read_text()
        code = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
''' + f'#include "{(ROOT / "source/setplay_aim.h").as_posix()}"\n' + r'''
#define NATIVE_LAB_TRAJECTORY_MAX_ELEVATION_DEGREES 18.0f
#define PES_SETPLAY_CORNER 2
#define PES_SETPLAY_FREE_KICK 3
static uint32_t native_lab_free_kick_elevation_mask=1;
static uint32_t native_lab_free_kick_elevation_linger[2]={120,0};
static uint32_t native_lab_free_kick_elevation_bits[2];
static uint32_t native_lab_setplay_flight_curl_bits[2];
static uint32_t native_lab_setplay_flight_context[2];
static uint32_t native_lab_free_kick_player[2]={4,17};
static void (*native_lab_ball_injection_original)(const void*,void*,void*);
''' + function(route, 'native_lab_ball_injection') + r'''
int main(void) {
  assert(pes_setplay_height_intent(0,1));
  assert(pes_setplay_height_intent(0,-1));
  assert(!pes_setplay_height_intent(1,.4f));
  assert(!pes_setplay_height_intent(-1,-.4f));
  assert(!pes_setplay_height_intent(0,0));
  unsigned char input[64]={0};
  float pitch=18, curl=.5f, speed[3]={0,0,20}, rotation[3]={1,0,3};
  memcpy(native_lab_free_kick_elevation_bits,&pitch,4);
  memcpy(native_lab_setplay_flight_curl_bits,&curl,4);
  native_lab_setplay_flight_context[0]=2;
  uint32_t player=17; memcpy(input+0x30,&player,4);
  native_lab_ball_injection(input,speed,rotation);
  assert(speed[1]==0 && native_lab_free_kick_elevation_linger[0]==120);
  player=4; memcpy(input+0x30,&player,4);
  native_lab_ball_injection(input,speed,rotation);
  assert(speed[1]==0 && speed[0]==0 && speed[2]==20);
  assert(rotation[0]==1 && rotation[1]>1.49f && rotation[1]<1.51f && rotation[2]==3);
  native_lab_setplay_flight_context[0]=PES_SETPLAY_FREE_KICK;
  rotation[1]=0;
  native_lab_ball_injection(input,speed,rotation);
  assert(rotation[1]>1.49f && rotation[1]<1.51f);
  speed[1]=.324f; rotation[1]=-12.0f;
  native_lab_ball_injection(input,speed,rotation);
  assert(speed[1]==.324f && rotation[1]>-10.51f && rotation[1]<-10.49f);
  assert(native_lab_free_kick_elevation_linger[0]==120);
  native_lab_free_kick_elevation_mask=0; speed[1]=0;
  native_lab_ball_injection(input,speed,rotation); assert(speed[1]==0);
}
'''
        build_and_run(self.cc, code)

    def test_stamina_overlay_snapshot_uses_native_nameplate_data(self):
        hooks = (ROOT / "source/ue4_hooks.c").read_text()
        header = (ROOT / "source/ue4_hooks.h").read_text()
        publish = function(hooks, "match_stamina_publish_from_model")
        snapshot = function(hooks, "pes_controller_stamina_bars")
        self.assertIn("#define PES_STAMINA_BAR_CAPACITY 2u", header)
        self.assertIn("uint32_t player_no;", header)
        self.assertIn("uint32_t side;", header)
        self.assertIn("match_hud_get_stamina_percentage(player)", publish)
        self.assertNotIn("record[0x194]", publish)
        self.assertNotIn("record[0x1a0]", publish)
        self.assertIn("match_utility_info_is_inplay_time(info)", publish)
        self.assertIn("PES_MOBILE_CONTROL_UNKNOWN", snapshot)
        self.assertIn("PES_CONTROLLER_SURFACE_NONE", snapshot)
        self.assertIn("pause_settings_show_nameplate", snapshot)
        self.assertIn("pes_controller_replay_active()", snapshot)
        self.assertIn("pes_controller_pause_transition()", snapshot)
        self.assertIn("PES_VIRTUAL_CURSOR_NONE", snapshot)
        self.assertNotIn('pause_stamina_get_model_original', hooks)
        self.assertNotIn('_ZN7UCanvas8DrawItemER11FCanvasItem', hooks)

    def test_native_stamina_draw_is_not_intercepted(self):
        hooks = (ROOT / "source/ue4_hooks.c").read_text()
        install = hooks.split('void install_ue4_hooks', 1)[1]
        self.assertNotIn('ModelStaminaGauge8GetModel', install)
        self.assertNotIn('Model2DData4Draw', install)
        self.assertNotIn('stamina_draw_plt', install)

    def test_disabled_stamina_does_not_patch_native_fill_slots(self):
        hooks = (ROOT / 'source/ue4_hooks.c').read_text(encoding='utf-8')
        install = hooks.split('void install_ue4_hooks', 1)[1]
        self.assertNotIn('stamina_color_code', install)
        self.assertNotIn('stamina_exec_code', install)
        self.assertIn('*stamina_disp_slot = (uintptr_t)&pause_stamina_disp;', install)
        self.assertNotIn('_ZN7UCanvas8DrawItemER11FCanvasItem', install)
        self.assertNotIn('PES_STAMINA_FILL_SCALE_Y', hooks)

    def test_custom_stamina_hud_is_live_only_and_animated(self):
        overlay = (ROOT / "source/overlay.c").read_text()
        self.assertNotIn('stamina_outline_first_quad', overlay)
        self.assertIn('stamina_track_first_quad', overlay)
        self.assertIn('stamina_fill_first_quad', overlay)
        self.assertIn('pes_controller_stamina_bars(', overlay)
        self.assertIn('controller_snapshot.surface == PES_CONTROLLER_SURFACE_NONE', overlay)
        self.assertIn('220000000.0f', overlay)
        self.assertIn('else if (switched)', overlay)
        self.assertIn('must not replay\n      // the kickoff reveal', overlay)
        self.assertIn('pes_controller_match_hud_session()', overlay)
        self.assertIn('stamina_introduced_mask', overlay)
        self.assertNotIn('stamina_visible_mask', overlay)
        self.assertNotIn('memset(stamina_appeared_tick, 0, sizeof(stamina_appeared_tick));\n  } else', overlay)
        self.assertIn('!stamina_bar_count', overlay)

    def test_custom_hud_layout_uses_separate_badge_portrait_and_text_cells(self):
        overlay = (ROOT / "source/overlay.c").read_text()
        self.assertIn('const float horizontal_pad', overlay)
        self.assertIn('const float cell_gap', overlay)
        self.assertIn('const float bar_w = text_w', overlay)
        self.assertIn('float x = text_x', overlay)
        self.assertIn('emit_efootball_right_fit_line(', overlay)
        self.assertIn('text_right,', overlay)
        self.assertIn('const float fill_x = side ? x + bar_w - inset - fill_w',
                      overlay)
        self.assertNotIn('const float bar_w = card_w', overlay)

    def test_away_nameplate_text_anchors_to_right_edge(self):
        overlay = (ROOT / 'source/overlay.c').read_text()
        code = r'''
#include <assert.h>
#include <math.h>
#include <stdint.h>
typedef float GLfloat;
static float drawn_x, drawn_width;
static float measure_efootball_line(const char *s, int n, float gh, uint32_t w) {
  (void)s; (void)w; return (float)n * gh * 0.5f;
}
static int emit_efootball_line(const char *s, int n, float x, float y,
                               float gh, uint32_t w, GLfloat *verts) {
  (void)y; (void)verts;
  drawn_x=x; drawn_width=measure_efootball_line(s,n,gh,w); return n;
}
''' + function(overlay, 'emit_efootball_right_fit_line') + r'''
int main(void) {
  GLfloat verts[24]={0};
  assert(emit_efootball_right_fit_line("PLAYER 10",9,300,4,120,20,12,0,verts)==9);
  assert(fabsf(drawn_x + drawn_width - 300.0f)<0.001f);
  assert(emit_efootball_right_fit_line("LONG PLAYER NAME 10",19,300,4,120,20,12,0,verts)==19);
  assert(fabsf(drawn_x + drawn_width - 300.0f)<0.001f);
  assert(drawn_width <= 120.0f);
}
'''
        build_and_run(self.cc, code)


    def test_buffer_matches_engine_request_even_with_720p_config(self):
        shim = (ROOT / "source/libc_shim.c").read_text()
        block = function(shim, "ANativeWindow_setBuffersGeometry_fake")
        code = r'''
#include <assert.h>
typedef void NWindow;
static int screen_width=1280, screen_height=720, buffer_w,buffer_h;
#define debugPrintf(...) ((void)0)
static void nwindowSetDimensions(NWindow *win,int w,int h) {
  buffer_w=w; buffer_h=h;
}
''' + block + r'''
int main(void) {
  ANativeWindow_setBuffersGeometry_fake(0,1024,576,0);
  assert(buffer_w==1024 && buffer_h==576);
  ANativeWindow_setBuffersGeometry_fake(0,1280,720,0);
  assert(buffer_w==1280 && buffer_h==720);
  ANativeWindow_setBuffersGeometry_fake(0,1024,540,0);
  assert(buffer_w==1024 && buffer_h==540);
  ANativeWindow_setBuffersGeometry_fake(0,0,0,0);
  assert(buffer_w==1280 && buffer_h==720);
}
'''
        build_and_run(self.cc, code)

    def test_projected_feet_use_native_display_units_at_each_resolution(self):
        hooks = (ROOT / "source/ue4_hooks.c").read_text()
        code = r'''
#include <assert.h>
#include <math.h>
static int screen_width=1280,screen_height=720;
''' + function(hooks, "match_gauge_project_to_overlay") + r'''
int main(void) {
  float x=472,y=280;
  assert(match_gauge_project_to_overlay(&x,&y,1024,576));
  assert(x==590 && y==350);
  x=512; y=270;
  assert(match_gauge_project_to_overlay(&x,&y,1024,540));
  assert(x==640 && y==360);
  x=640; y=360;
  assert(match_gauge_project_to_overlay(&x,&y,1280,720));
  assert(x==640 && y==360);
  screen_width=1024; screen_height=540; x=640; y=360;
  assert(match_gauge_project_to_overlay(&x,&y,1280,720));
  assert(x==512 && y==270);
  assert(!match_gauge_project_to_overlay(&x,&y,0,720));
  assert(!match_gauge_project_to_overlay(&x,&y,1280,NAN));
}
'''
        build_and_run(self.cc, code)
        producer = function(hooks, 'pes_match_cursor_name_get_position')
        self.assertIn('match_gauge_project_to_overlay(&screen_x, &screen_y', producer)
        self.assertIn('match_projection_display_width()', producer)

    def test_camera_heading_and_ls_curl_are_independent(self):
        route = (ROOT / "source/native_pad_lab.inc").read_text()
        code = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
''' + f'#include "{(ROOT / "source/setplay_aim.h").as_posix()}"\n' + r'''
#define PES_SETPLAY_CORNER 2
#define PES_SETPLAY_GOAL_KICK 1
#define NATIVE_LAB_TRAJECTORY_MAX_ELEVATION_DEGREES 18.0f
static int32_t native_lab_camera_yaw_millirad[2];
static int32_t native_lab_debug_axis_x, native_lab_debug_axis_y;
static int32_t native_lab_debug_axis_x_p2, native_lab_debug_axis_y_p2;
static uint32_t native_lab_left_aim_latched_mask, native_lab_command_angle_valid_mask;
static uint32_t native_lab_command_vertical_bits[2], native_lab_command_angle_bits[2];
static uint32_t native_lab_command_curl_bits[2], native_lab_camera_heading_bits[2];
static uint32_t native_lab_camera_heading_mask;
static uint32_t native_lab_single_camera_mask;
static float (*native_lab_mobile_filter_angle_abi)(void*,const void*,float);
static float native_lab_stable_setplay_base_angle(uint32_t p,uint32_t n,float a,int *same) {
  (void)p;(void)n;(void)a;*same=1; return 90.0f;
}
''' + function(route, "native_lab_normalize_axis") + "\n" + function(route, "native_lab_apply_native_kick_angle") + r'''
static float field(unsigned char *p, unsigned off) { float v; memcpy(&v,p+off,4); return v; }
int main(void) {
  unsigned char unit[128]={0}, input[64]={0};
  float base=90; memcpy(unit+0x38,&base,4);
  for (unsigned pad=0;pad<2;pad++) {
    float heading=210; memcpy(&native_lab_camera_heading_bits[pad],&heading,4);
    native_lab_camera_heading_mask=1u<<pad;
    for(int sign=-1;sign<=1;sign++) {
      native_lab_command_curl_bits[pad]=0;
      native_lab_debug_axis_x=native_lab_debug_axis_x_p2=sign*32767;
      native_lab_debug_axis_y=native_lab_debug_axis_y_p2=0;
      native_lab_apply_native_kick_angle(unit,input,pad,PES_SETPLAY_CORNER);
      assert(fabsf(field(unit,0x38)-210)<.001f); // LS-X never rotates launch
      assert(fabsf(field(unit,0x48)-(sign?1:0))<.002f);
      assert(field(unit,0x44)==(sign<0?90:sign>0?270:0));
    }
    native_lab_debug_axis_x=native_lab_debug_axis_x_p2=32767;
    native_lab_debug_axis_y=native_lab_debug_axis_y_p2=-32767;
    native_lab_apply_native_kick_angle(unit,input,pad,PES_SETPLAY_CORNER);
    const uint32_t latched_curl=native_lab_command_curl_bits[pad];
    native_lab_debug_axis_x=native_lab_debug_axis_x_p2=0;
    native_lab_debug_axis_y=native_lab_debug_axis_y_p2=0;
    native_lab_apply_native_kick_angle(unit,input,pad,PES_SETPLAY_CORNER);
    assert(native_lab_command_curl_bits[pad]==latched_curl);
    assert(field(unit,0x44)==270 && field(unit,0x48)>.99f);
    heading=235; memcpy(&native_lab_camera_heading_bits[pad],&heading,4);
    native_lab_apply_native_kick_angle(unit,input,pad,PES_SETPLAY_CORNER);
    assert(fabsf(field(unit,0x38)-235)<.001f); // RS still moves aim after LS latch
    // Switching to single-stick camera mode preserves curl/height while the
    // routed LS is neutral, but still accepts the camera's changing heading.
    const uint32_t curl_before=native_lab_command_curl_bits[pad];
    const uint32_t height_before=native_lab_command_vertical_bits[pad];
    native_lab_single_camera_mask=1u<<pad;
    native_lab_debug_axis_x=native_lab_debug_axis_x_p2=0;
    native_lab_debug_axis_y=native_lab_debug_axis_y_p2=0;
    heading=240; memcpy(&native_lab_camera_heading_bits[pad],&heading,4);
    native_lab_apply_native_kick_angle(unit,input,pad,PES_SETPLAY_CORNER);
    assert(fabsf(field(unit,0x38)-240)<.001f);
    assert(native_lab_command_curl_bits[pad]==curl_before);
    assert(native_lab_command_vertical_bits[pad]==height_before);
    assert(field(unit,0x44)==270 && field(unit,0x48)>.99f);
    native_lab_single_camera_mask=0;
  }
  for(int s=-1;s<=1;s++) {
    const float yaw=s*.4f, old_x=-15, old_z=-20;
    const float cx=old_x*cosf(yaw)-old_z*sinf(yaw);
    const float cz=old_x*sinf(yaw)+old_z*cosf(yaw);
    const float a=pes_setplay_camera_heading(0,0,cx,cz)*.01745329252f;
    assert(fabsf(sinf(a)+cx/25)<.0001f && fabsf(cosf(a)+cz/25)<.0001f);
    float x=0,z=0; pes_setplay_bend_point(&x,&z,0,1,30,(float)s,0);
    assert(x==0 && z==0);
    x=0; z=30; pes_setplay_bend_point(&x,&z,0,1,30,(float)s,1);
    assert(fabsf(x+s*4.2f)<.001f && z==30); // lateral bend, not launch rotation
  }
}
'''
        build_and_run(self.cc, code)

class OnfieldAssetAndAbiTests(unittest.TestCase):
    def test_switch_sprites_are_bundled_byte_identical(self):
        from PIL import Image
        assets = dict(x='X_Button.png', y='Y_Button.png', l='L_Button.png',
                      zl='ZL_Button.png', zr='ZR_Button.png', sl='SL_Button.png',
                      sr='SR_Button.png', ls='LeftStick_Default_CORE.png',
                      rs='RightStick_Default_CORE.png',
                      right='Directional_Button_Right.png',
                      up='Directional_Button_Up.png',
                      down='Directional_Button_Down.png',
                      left='Directional_Button_Left.png')
        for key, source in assets.items():
            original = ROOT / 'art/SwitchButton' / source
            bundled = ROOT / 'data' / f'switch_button_{key}.bin'
            self.assertEqual(original.read_bytes(), bundled.read_bytes(), key)
            with Image.open(bundled) as png:
                self.assertEqual(png.size, (32, 32))
                self.assertIn('A', png.getbands())
        self.assertIn('!data/switch_button_*.bin', (ROOT / '.gitignore').read_text())

    def test_owned_binary_stamina_update_dispatch_is_nonvirtual(self):
        import struct
        library = ROOT / 'local-debug/apk-arm64/libUE4.so'
        if not library.exists(): self.skipTest('optional user-owned native binary unavailable')
        try:
            from elftools.elf.elffile import ELFFile
        except ImportError:
            self.skipTest('optional pyelftools unavailable')
        with library.open('rb') as stream:
            elf = ELFFile(stream)
            symbols = list(elf.get_section_by_name('.dynsym').iter_symbols())
            names = {s.name: s for s in symbols}
            name = '_ZN7match2D6Screen9ModelBase6UpdateEv'
            vt = names['_ZTVN7match2D6Screen17ModelStaminaGaugeE']
            start, end = vt['st_value'], vt['st_value'] + vt['st_size']
            slots = [symbols[r['r_info_sym']].name for r in
                     elf.get_section_by_name('.rela.dyn').iter_relocations()
                     if start <= r['r_offset'] < end]
            self.assertNotIn(name, slots)  # regression: absent vtable hook never ran
            plt = elf.get_section_by_name('.plt')
            targets = [plt['sh_addr'] + 32 + i*16 for i,r in enumerate(
                       elf.get_section_by_name('.rela.plt').iter_relocations())
                       if symbols[r['r_info_sym']].name == name]
            self.assertEqual(targets, [0x38b4b20])
            stream.seek(next(elf.address_offsets(targets[0])))
            words = struct.unpack('<4I', stream.read(16))
            self.assertEqual(words, (0x9002e330, 0xf943f611, 0x911fa210, 0xd61f0220))
        hooks = (ROOT / 'source/ue4_hooks.c').read_text()
        self.assertNotIn('stamina_draw_plt', hooks)
        self.assertNotIn('pause_stamina_update_original', hooks)

if __name__ == "__main__": unittest.main()
