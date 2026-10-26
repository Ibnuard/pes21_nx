"""Replay the production snapshot/restore transaction using fresh native squads."""
from pathlib import Path
import shutil
import subprocess
import pytest
from test_gameplan_editor import function, struct

ROOT = Path(__file__).resolve().parents[1]


def test_starting_plans_survive_match_and_second_side_failure_rolls_back(tmp_path):
    compiler = shutil.which('gcc') or shutil.which('clang')
    if not compiler:
        pytest.skip('host C compiler unavailable')
    hooks = (ROOT/'source/ue4_hooks.c').read_text()
    types = '\n'.join(struct(hooks, n) for n in ('TmpdbFormationValue',
        'TmpdbMatchPlanSettingsValue', 'PrematchGameplanPlayer', 'PrematchGameplanSide'))
    source = '''#include <assert.h>
#include <string.h>
#include <stdint.h>
#include "gameplan_preset.h"
#define PREMATCH_GAMEPLAN_MAX_PLAYERS 40
#define debugPrintf(...) ((void)0)
''' + types + r'''
static int manager_dummy_plan_editor(void){return 0;}
static int manager_league_native_plan_snapshot_members(uint32_t side,GameplanPreset *p){(void)side;(void)p;return 1;}
static int manager_league_native_plan_rekey_settings(uint32_t side,const GameplanPreset *p,TmpdbMatchPlanSettingsValue *s){(void)side;(void)p;(void)s;return 1;}
typedef struct { TmpdbFormationValue formation[2]; TmpdbMatchPlanSettingsValue settings; uint32_t tactics; } Squad;
static Squad squads[2], backup_squads[2];
static PrematchGameplanSide exhibition_gameplan_sides[2], backup_sides[2];
static GameplanPreset local_rematch_plan[2];
static void *live_gameplan_window;
static int fail_side=-1, mutations, backup_ok=1, prepared=1, backup_live, rollbacks;
static uint32_t local_rematch_valid,local_rematch_session=1,local_rematch_two_player;
static uint32_t cup,league,career;
static int competition_frontend_cup_match_active(void){return cup;}
static int competition_frontend_league_match_active(void){return league;}
static int ml_frontend_match_active(void){return career;}
static int pes_controller_native_pad_lab_active(void){return 1;}
static int pes_controller_native_pad_lab_two_player(void){return 1;}
static int match_swap_member_info_construct=1,match_replace_squad_player=1;
static int match_squad_data_get_order_no=1,match_squad_data_get_member_id=1;
static int match_squad_data_set_formation=1,match_formation_copy_assign=1;
static uint32_t (*match_formation_get_role)(void *,uint32_t,int);
static void (*match_squad_data_set_player_role_position)(void *,uint32_t,uint32_t,const uint32_t *);
static uint32_t prematch_gameplan_team_id(uint32_t side){return 500+side;}
static TmpdbFormationValue formation_get(void *s,uint32_t t){return ((Squad*)s)->formation[t];}
static TmpdbMatchPlanSettingsValue settings_get(void *s){return ((Squad*)s)->settings;}
static void settings_set(void *s,const TmpdbMatchPlanSettingsValue *v){((Squad*)s)->settings=*v;mutations++;}
static void tactics_set(void *s,uint32_t t){((Squad*)s)->tactics=t;mutations++;}
static TmpdbFormationValue (*match_squad_data_get_formation)(void *,uint32_t)=formation_get;
static TmpdbMatchPlanSettingsValue (*match_squad_data_get_settings)(void *)=settings_get;
static void (*match_squad_data_set_settings)(void *,const TmpdbMatchPlanSettingsValue *)=settings_set;
static void (*match_squad_data_set_tactics)(void *,uint32_t)=tactics_set;
static void prematch_gameplan_refresh_side(uint32_t side){assert(side<2);}
static void prematch_gameplan_save_and_refresh(uint32_t side){exhibition_gameplan_sides[side].tactics=squads[side].tactics;}
static void prematch_gameplan_store_formation(void *s,uint32_t t,const TmpdbFormationValue *v){((Squad*)s)->formation[t]=*v;mutations++;}
static int prematch_gameplan_replace_player(uint32_t side,void *s,const void *a,const void *b){
  assert(s==&squads[side]);if((int)side==fail_side)return 0;
  PrematchGameplanPlayer *first=NULL,*second=NULL;
  for(unsigned i=0;i<20;i++){
    PrematchGameplanPlayer *p=&exhibition_gameplan_sides[side].players[i];
    if(!memcmp(p->player_id,a,16))first=p;
    if(!memcmp(p->player_id,b,16))second=p;
  }
  assert(first && second);uint32_t order=first->order_no;first->order_no=second->order_no;second->order_no=order;mutations++;return 1;
}
static int exhibition_gameplan_prepare_matchplan(void){return prepared;}
static int exhibition_capture_pre_strategy_squad_snapshot(void){
  if(!backup_ok)return 0;
  memcpy(backup_squads,squads,sizeof(squads));memcpy(backup_sides,exhibition_gameplan_sides,sizeof(backup_sides));backup_live=1;return 1;
}
static uint32_t exhibition_restore_pre_strategy_squad_snapshot(void){
  assert(backup_live);memcpy(squads,backup_squads,sizeof(squads));memcpy(exhibition_gameplan_sides,backup_sides,sizeof(backup_sides));rollbacks++;return 2;
}
static void exhibition_discard_pre_strategy_squad_snapshot(void){backup_live=0;}
static void exhibition_save_matchplan_sides(uint32_t mask){assert(mask==3);}
''' + '\n'.join(function(hooks, n) for n in ('prematch_gameplan_snapshot',
        'prematch_gameplan_restore','local_rematch_capture','local_rematch_apply_plans')) + r'''
static void rearrange(void){
  for(unsigned side=0;side<2;side++){
    PrematchGameplanPlayer *p=exhibition_gameplan_sides[side].players;
    uint32_t order=p[0].order_no;p[0].order_no=p[18].order_no;p[18].order_no=order;
    memset(&squads[side],77,sizeof(Squad));squads[side].tactics=1;
  }
}
int main(void){
  for(unsigned side=0;side<2;side++){
    PrematchGameplanSide *s=&exhibition_gameplan_sides[side];s->squad_data=&squads[side];s->player_count=20;
    for(unsigned i=0;i<20;i++){s->players[i].player_id[0]=(unsigned char)(i+1+side*50);s->players[i].order_no=i<18?i:255;s->players[i].member_id=i;}
    memset(&squads[side],20+side,sizeof(Squad));squads[side].tactics=side;s->tactics=side;
  }
  local_rematch_capture();assert(local_rematch_valid && local_rematch_two_player);
  const GameplanPreset initial[2]={local_rematch_plan[0],local_rematch_plan[1]};
  assert(initial[0].players[18].order_no==18 && initial[0].players[19].order_no==19);
  rearrange();assert(!memcmp(initial,local_rematch_plan,sizeof(initial))); // By value, not pointers into live squads.
  assert(local_rematch_apply_plans() && !backup_live);
  for(unsigned side=0;side<2;side++){
    GameplanPreset restored;assert(prematch_gameplan_snapshot(side,&restored));
    assert(!memcmp(&restored,&initial[side],sizeof(restored)));
  }
  rearrange();fail_side=1;
  PrematchGameplanSide before[2];Squad before_squads[2];
  memcpy(before,exhibition_gameplan_sides,sizeof(before));memcpy(before_squads,squads,sizeof(before_squads));
  assert(!local_rematch_apply_plans() && rollbacks==1 && !backup_live);
  assert(!memcmp(before,exhibition_gameplan_sides,sizeof(before)) && !memcmp(before_squads,squads,sizeof(squads)));
  int old=mutations;backup_ok=0;assert(!local_rematch_apply_plans() && mutations==old);
  backup_ok=1;GameplanPreset bad=initial[0];bad.players[0].player_id[0]=240;
  assert(!prematch_gameplan_restore(0,&bad) && mutations==old);
  assert(!prematch_gameplan_restore(2,&initial[0]) && !prematch_gameplan_snapshot(2,&bad));
  for(unsigned mode=0;mode<3;mode++){
    cup=mode==0;league=mode==1;career=mode==2;local_rematch_capture();assert(!local_rematch_valid);
  }
  return 0;
}
'''
    path = tmp_path/'rematch.c';path.write_text(source)
    exe = tmp_path/'rematch.exe'
    compiled = subprocess.run([compiler,'-std=c11','-I',str(ROOT/'source'),
        str(path),str(ROOT/'source/gameplan_preset.c'),'-o',str(exe)],capture_output=True,text=True)
    assert compiled.returncode == 0, compiled.stdout+compiled.stderr
    result = subprocess.run([str(exe)],capture_output=True,text=True)
    assert result.returncode == 0, result.stdout+result.stderr
