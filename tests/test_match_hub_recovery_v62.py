"""Execute current native-host admission, ownership and lineup publication."""
from pathlib import Path
import re
import shutil
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=(ROOT/'source/ue4_hooks.c').read_text()

def production(name):
    signature=r'(?m)^(?:(?:static|inline|const|unsigned|long)\s+)*[A-Za-z_]\w*[\s*]+\b'+re.escape(name)+r'\([^;{}]*\)\s*\{'
    match=re.search(signature,SOURCE)
    assert match,name
    return SOURCE[match.start():SOURCE.index('\n}',match.end())+2]

def run(tmp_path,text):
    cc=shutil.which('gcc') or shutil.which('clang')
    if not cc:pytest.skip('host C compiler required')
    src=tmp_path/'hub.c';src.write_text(text)
    exe=tmp_path/'hub.exe'
    subprocess.run([cc,'-std=c11','-Wall','-Wextra','-Werror','-I',str(ROOT/'source'),str(src),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

def test_actual_host_post_update_loads_new_squads_before_ready_and_each_rematch(tmp_path):
    run(tmp_path,r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define debugPrintf(...) ((void)0)
#define EXHIBITION_INITIAL_REFRESH_TICKS 8u
enum {MAIN_MENU_2P_TRANSITION_NONE=0};
static uint32_t exhibition_plan_ready,exhibition_cpu_level_value;
static unsigned char plan[64],parameter[32],common[16],match[64];
static uint32_t actual_user=42,home_user=999;
static uint32_t loads,setup_calls,refreshed,notes,loaded_generation,fail_load;
static int master_league_plan_restore_pending;
#define ML_CURRENT_PLAN_SLOT 3
static struct {uint32_t field_count,bench_count;} exhibition_gameplan_sides[2];
static void *plan_get(void){return plan;}
static void *parameter_get(void){return parameter;}
static void *(*exhibition_matchplan_get_instance)(void)=plan_get;
static void *(*exhibition_matchplan_create_instance)(void)=plan_get;
static void *(*exhibition_online_parameter_get_instance)(void)=parameter_get;
static uint32_t user_get(void *p){assert(p==common);return actual_user;}
static uint32_t (*exhibition_parameter_common_get_user_id)(void *)=user_get;
static void *exhibition_get_tmpdb_match(void){return match;}
static void set_user(void *p,uint32_t side,uint32_t user){assert(p==match && side==0);home_user=user;}
static void (*exhibition_tmpdb_match_set_user_id)(void *,uint32_t,uint32_t)=set_user;
static uint32_t owner_get(void){return home_user==actual_user?0:2;}
static uint32_t (*exhibition_get_match_my_side)(void)=owner_get;
static void setup(void *p){assert(p==plan);setup_calls++;home_user=999;}
static void (*exhibition_matchplan_setup_tmpdb)(void *)=setup;
static int native_load(void){loads++;assert(owner_get()==0);if(fail_load)return 0;loaded_generation=actual_user;return 1;}
static int (*matchplan_squad_load)(void)=native_load;
static int exhibition_refresh_selected_tmpdb(void){refreshed++;return 1;}
static int exhibition_gameplan_init_fixture(void *p){assert(p==plan);return 1;}
static void native_lab_assign_matchplan_pads(void *p){assert(p==plan);}
static void exhibition_apply_cpu_level(uint32_t v,void *p){(void)v;assert(!p);}
static void exhibition_apply_match_settings(void *p){assert(!p);}
static void exhibition_apply_selected_uniforms(void *p){assert(!p);}
static void exhibition_refresh_squad_player_stats(void){assert(loaded_generation==actual_user);}
static void prematch_gameplan_refresh_side(uint32_t side){assert(side<2);exhibition_gameplan_sides[side].field_count=11;exhibition_gameplan_sides[side].bench_count=12;}
static int ml_frontend_match_active(void){return 0;}
static int prematch_gameplan_load_preset(uint32_t a,uint32_t b){(void)a;(void)b;return 1;}
static void scene_runtime_note(const char *a,const char *b){assert(a && b);notes++;}
''' + production('exhibition_gameplan_prepare_matchplan') + r'''
static uint32_t main_menu_2p_prematch_hub_active=1,exhibition_hub_squad_state;
static uint32_t local_rematch_handoff_cover=1,main_menu_2p_transition_active=1;
static uint32_t main_menu_2p_transition_kind=1,main_menu_controller_active=1;
static uint32_t main_menu_2p_prematch_hub_input_pending,main_menu_2p_prematch_lineup_count[2];
static uint32_t local_rematch_booting=1,restores,caches;
static int local_rematch_apply_plans(void){assert(exhibition_plan_ready);restores++;return 1;}
static void main_menu_2p_prematch_hub_cache_lineups(void){assert(exhibition_plan_ready && loaded_generation==actual_user);caches++;main_menu_2p_prematch_lineup_count[0]=main_menu_2p_prematch_lineup_count[1]=11;}
''' + production('exhibition_prematch_hub_admit') + r'''
static uint32_t exhibition_searching_active=1,exhibition_search_focus_index;
static uint32_t exhibition_home_team_id=108,exhibition_away_team_id=100;
static uint32_t exhibition_search_touch_pending,exhibition_search_refresh_pending=1;
static uint32_t exhibition_search_initial_refresh_ticks;
static void *exhibition_search_window;
static uintptr_t exhibition_search_post_resume=0x1234;
static int matching_ready;
static int exhibition_update_matching_record(void *w,uint32_t side,uint32_t team){assert(w && side<2 && team);return matching_ready;}
static void (*exhibition_search_update_disp)(void *);
static uint32_t exhibition_matchup_ready(void){return matching_ready;}
static void exhibition_open_team_picker(void *w,uint32_t side){(void)w;(void)side;}
static void (*exhibition_search_update_team_info)(void *,const uint32_t *);
static void (*exhibition_set_pad_key_kind)(void *,uint32_t,uint32_t);
static void (*exhibition_set_pad_key_active)(void *,uint32_t,uint32_t);
static void (*exhibition_set_pad_key_string)(void *,uint32_t,uint32_t);
static void exhibition_update_matchmaking_card(void *w,uint32_t side,uint32_t team){(void)w;(void)side;(void)team;}
static void exhibition_search_focus_apply(void *w){(void)w;}
''' + production('pes_exhibition_search_post_entry') + r'''
int main(void){
 void *p=common;memcpy(parameter+8,&p,sizeof(p));
 for(unsigned session=0;session<3;session++){
  actual_user=42+session;home_user=999;exhibition_plan_ready=0;exhibition_hub_squad_state=0;
  matching_ready=0;local_rematch_booting=1;local_rematch_handoff_cover=1;main_menu_controller_active=1;
  main_menu_2p_prematch_hub_input_pending=0;exhibition_search_refresh_pending=1;
  const unsigned before=loads;
  assert(pes_exhibition_search_post_entry((void *)123)==0x1234);
  assert(loads==before && !exhibition_hub_squad_state && local_rematch_handoff_cover);
  matching_ready=1;pes_exhibition_search_post_entry((void *)123);
  assert(loads==before+1 && loaded_generation==actual_user && exhibition_hub_squad_state==1);
  assert(!local_rematch_handoff_cover && !main_menu_controller_active && !local_rematch_booting);
  assert(main_menu_2p_prematch_hub_input_pending==3 && main_menu_2p_prematch_lineup_count[0]==11);
  assert(exhibition_gameplan_sides[0].bench_count==12);
  pes_exhibition_search_post_entry((void *)123);
  assert(loads==before+1);assert(exhibition_gameplan_prepare_matchplan());assert(loads==before+1);
 }
 assert(loads==3 && setup_calls==3 && caches==3 && restores==3);
 /* A refused conversion never admits the previous session's cached squad. */
 fail_load=1;exhibition_plan_ready=0;exhibition_hub_squad_state=0;local_rematch_booting=1;
 local_rematch_handoff_cover=1;main_menu_2p_transition_active=1;
 pes_exhibition_search_post_entry((void *)123);
 assert(exhibition_hub_squad_state==2 && !exhibition_plan_ready && !local_rematch_handoff_cover);
 assert(!local_rematch_booting && caches==3 && restores==3);
}
''')

def test_selection_projection_preserves_canonical_teams(tmp_path):
    run(tmp_path,r'''
#include <assert.h>
#include "exhibition_selection_groups.h"
int main(void){
 const uint32_t raw_count=EXHIBITION_TEAM_CATEGORY_COUNT;
 assert(exhibition_selection_group_count()==raw_count);
 exhibition_selection_groups_init();
 assert(exhibition_selection_group_count()==raw_count-1);
 unsigned merged=0;
 for(uint32_t i=0;i<exhibition_selection_group_count();i++){
  const ExhibitionTeamCategory *g=exhibition_selection_group_at(i);assert(g);
  if(!strcmp(g->label,"Other Asia & American Clubs")){
   merged++;assert(g->team_count);
   for(uint32_t a=0;a<g->team_count;a++)for(uint32_t b=a+1;b<g->team_count;b++)assert(g->teams[a]!=g->teams[b]);
  }
 }
 assert(merged==1 && !exhibition_selection_group_at(exhibition_selection_group_count()));
 for(uint32_t i=0;i<raw_count;i++)for(uint32_t t=0;t<exhibition_team_categories[i].team_count;t++){
  uint32_t found=0,id=exhibition_team_categories[i].teams[t];
  for(uint32_t j=0;j<exhibition_selection_group_count();j++){
   const ExhibitionTeamCategory *g=exhibition_selection_group_at(j);
   for(uint32_t k=0;k<g->team_count;k++)found+=g->teams[k]==id;
  }
  assert(found);
 }
 exhibition_selection_groups_init();assert(exhibition_selection_group_count()==raw_count-1);
}
''')

def test_hub_starting_xi_uses_current_prepared_order_not_old_registry(tmp_path):
    run(tmp_path,r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define debugPrintf(...) ((void)0)
#define MAIN_MENU_2P_PREMATCH_LINEUP_COUNT 11u
typedef struct {uint32_t starting,order_no;char name[64];} PrematchGameplanPlayer;
typedef struct {uint32_t player_count;PrematchGameplanPlayer players[40];} PrematchGameplanSide;
static PrematchGameplanSide exhibition_gameplan_sides[2];
static uint32_t exhibition_plan_ready=1,main_menu_2p_prematch_lineup_count[2];
static char main_menu_2p_prematch_lineup[2][11][64];
static void *exhibition_get_tmpdb_match(void){assert(0);return NULL;}
static const void *(*match_tmpdb_match_get_player)(const void *,const uint32_t *,const uint32_t *);
static const char *(*match_tmpdb_player_get_name)(const void *);
static const void *exhibition_matchplan_common_side(uint32_t side){(void)side;assert(0);return NULL;}
static const void *(*match_global_registry_get_instance)(void);
static const void *(*match_global_registry_get_order_info)(const void *,uint32_t);
static uint32_t (*matchplan_common_get_member_id)(const void *,uint32_t);
static uint32_t (*match_order_info_get_member_id)(const void *,uint32_t);
''' + production('main_menu_2p_prematch_hub_cache_lineups') + r'''
int main(void){
 for(uint32_t side=0;side<2;side++) {
  PrematchGameplanSide *s=&exhibition_gameplan_sides[side];s->player_count=23;
  for(uint32_t i=0;i<23;i++) {
   s->players[i].starting=i<11;s->players[i].order_no=i<11?10-i:i;
   snprintf(s->players[i].name,64,"NEW%u-ORDER%u",side,s->players[i].order_no);
  }
 }
 main_menu_2p_prematch_hub_cache_lineups();
 for(uint32_t side=0;side<2;side++)for(uint32_t i=0;i<11;i++){
  char expected[64];snprintf(expected,64,"NEW%u-ORDER%u",side,i);
  assert(main_menu_2p_prematch_lineup_count[side]==11);
  assert(!strcmp(main_menu_2p_prematch_lineup[side][i],expected));
 }
 /* A committed substitution must replace that actual order in the hub. */
 exhibition_gameplan_sides[0].players[10].starting=0;
 exhibition_gameplan_sides[0].players[20].starting=1;
 exhibition_gameplan_sides[0].players[20].order_no=0;
 strcpy(exhibition_gameplan_sides[0].players[20].name,"NEW RESERVE");
 main_menu_2p_prematch_hub_cache_lineups();
 assert(!strcmp(main_menu_2p_prematch_lineup[0][0],"NEW RESERVE"));
 assert(main_menu_2p_prematch_lineup_count[0]==11);
}
''')
