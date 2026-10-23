"""A confirmed bench edit must repair late native Match writes before validation.

The scenario reuses the real selected-match rebuild and full-record commit.
Native imports/menu callbacks are modeled; this is not a Switch execution test.
"""
from pathlib import Path
import shutil
import subprocess
import pytest
from test_gameplan_editor import function

ROOT=Path(__file__).resolve().parents[1]

MODES=['home-overwrite','away-overwrite','import-refused','career-office','live','fresh-repeat','unregistered-reserve']

@pytest.mark.parametrize('mode', MODES)
def test_actual_A_confirm_uses_correct_publication_owner(tmp_path,mode):
    cc=shutil.which('gcc') or shutil.which('clang')
    if not cc:pytest.skip('host C compiler required')
    hooks=(ROOT/'source/ue4_hooks.c').read_text()
    cases=(ROOT/'tests/prematch_lineup_cases.inc').read_text()
    code=(ROOT/'tests/prematch_lineup_stubs.inc').read_text()
    code+='\n'+ '\n'.join(function(hooks,n) for n in (
        'exhibition_matchplan_common_side','exhibition_prematch_commit_refused',
        'exhibition_sync_prematch_lineup','exhibition_save_matchplan_sides',
        'master_league_office_lineup_valid','prematch_gameplan_replace_player'))
    code+='\n#include "exhibition_match_identity.h"\n'
    code+='\n'+function(cases,'init')+'\n'+function(cases,'assert_consistent')
    code+=r'''
static unsigned char source_teams[2][0x590];
static unsigned seeds,setups,seed_failed,refreshes,reservations;
static uint32_t exhibition_home_team_id=108,exhibition_away_team_id=100;
static uint32_t exhibition_native_team_id(uint32_t id){return id<<14;}
static int exhibition_seed_selected_tmpdb(void){
 seeds++;if(seed_failed)return 0;
 for(uint32_t side=0;side<2;side++){
  memcpy(teams[side],source_teams[side],sizeof(teams[side]));
  for(uint32_t i=0;i<TEST_COUNT;i++)memcpy((void*)get_player(match_bytes,&side,&i),original[side][i],0x380);
 }
 return 1;
}
static void setup(void *p){
 assert(p==plan);setups++;
 for(uint32_t side=0;side<2;side++){
  *(unsigned char*)exhibition_matchplan_common_side(side)=TEST_COUNT;
  for(uint32_t i=0;i<TEST_COUNT;i++){
   const void *p=get_player(match_bytes,&side,&i);unsigned char *info=plan+0x500+side*0x340+i*16;
   memcpy(info,original_info[side][i],8);memcpy(info+8,&p,sizeof(p));
  }
 }
}
static void (*exhibition_matchplan_setup_tmpdb)(void*)=setup;
static void native_lab_assign_matchplan_pads(void *p){assert(p==plan);}
'''
    code+='\n'+function(hooks,'exhibition_rebase_prepared_matchplan')
    code+=r'''
enum {PES_PREMATCH_GAMEPLAN_AREA_FIELD=0,PES_PREMATCH_GAMEPLAN_AREA_BENCH=1,
 PREMATCH_GAMEPLAN_NO_SELECTION=0xffffffffu,PES_PREMATCH_GAMEPLAN_PAGE_ROOT=0,
 PES_PAUSE_INPUT_UP=1,PES_PAUSE_INPUT_DOWN=2,PES_PAUSE_INPUT_LEFT=3,
 PES_PAUSE_INPUT_RIGHT=4,PES_PAUSE_INPUT_BACK=5,PES_PAUSE_INPUT_ROLE=6,PES_PAUSE_INPUT_DECIDE=7};
typedef struct {unsigned char player_id[16];char name[32];} PrematchGameplanPlayer;
typedef struct {void *squad_data;uint32_t field_focus,bench_focus,selected_area,selected_index,
 substitute_area,position_dragging,page,field_count,bench_count;PrematchGameplanPlayer player[2];} PrematchGameplanSide;
static PrematchGameplanSide exhibition_gameplan_sides[2];
static PrematchGameplanPlayer *prematch_gameplan_nth_player(PrematchGameplanSide *s,uint32_t field,uint32_t index){
 if(index)return NULL;return &s->player[field?0:1];
}
static int live_gameplan_change_substitution(uint32_t side,uint32_t out,uint32_t in){
 assert(live_gameplan_window && side==0 && out==7 && in==12);reservations++;return 0;
}
static void prematch_gameplan_save_and_refresh(uint32_t side){
 refreshes++;if(!office_editor && !live_gameplan_window)assert(exhibition_save_matchplan_sides(1u<<side));
}
static int pes_controller_gameplan_bench_locked(uint32_t side,uint32_t current){(void)side;(void)current;return 0;}
static void prematch_gameplan_finish_drag(uint32_t side){(void)side;assert(0);}
static void prematch_gameplan_cycle_role(uint32_t side){(void)side;assert(0);}
static void prematch_gameplan_move_field(PrematchGameplanSide *s,uint32_t action){(void)s;(void)action;assert(0);}
static void prematch_gameplan_swap_field(uint32_t side,uint32_t a,uint32_t b){(void)side;(void)a;(void)b;assert(0);}
'''
    code+='\n'+function(hooks,'prematch_gameplan_swap')+'\n'+function(hooks,'prematch_gameplan_process_substitute')
    code+=r'''
int main(void){
 init();
 for(uint32_t side=0;side<2;side++){
  uint32_t team=exhibition_native_team_id(side?exhibition_away_team_id:exhibition_home_team_id)|(0x3ffdu+side);
  memcpy(teams[side],&team,4);
 }
 memcpy(source_teams,teams,sizeof(teams));
 PrematchGameplanSide *ui=&exhibition_gameplan_sides[0];ui->squad_data=&squads[0];
 ui->field_count=11;ui->bench_count=TEST_COUNT-11;ui->selected_area=PES_PREMATCH_GAMEPLAN_AREA_FIELD;
 ui->selected_index=0;ui->substitute_area=PES_PREMATCH_GAMEPLAN_AREA_BENCH;
 const unsigned replacement=MODE==6?21:12;
 memcpy(ui->player[0].player_id,squads[0].key[7],16);memcpy(ui->player[1].player_id,squads[0].key[replacement],16);
 TestSquad before[2];memcpy(before,squads,sizeof(before));
 if(MODE==0 || MODE==1 || MODE==2){
  const uint32_t damaged=MODE==1?1:0;
  memset(teams[damaged],0,sizeof(teams[damaged]));uint32_t flags=2u<<9;memcpy(teams[damaged]+0x3a6,&flags,4);
  memset(match_bytes+0x1248+damaged*0x8c00,0,0x8c00);
 }
 if(MODE==2)seed_failed=1;
 if(MODE==3){office_editor=1;exhibition_plan_ready=0;memset(match_bytes,0,sizeof(match_bytes));}
 if(MODE==4)live_gameplan_window=(void*)1;
 /* Actual A on a highlighted bench player with an on-field selection. */
 prematch_gameplan_process_substitute(0,PES_PAUSE_INPUT_DECIDE);
 if(MODE==2 || MODE==4){
  assert(!memcmp(before,squads,sizeof(before)));assert(!refreshes);
  assert(ui->selected_area==PES_PREMATCH_GAMEPLAN_AREA_FIELD);
  if(MODE==2)assert(seeds==1 && !setups && !reservations);
  else assert(!seeds && !setups && reservations==1);
  return 0;
 }
 assert(get_order(&squads[0],squads[0].key[replacement])==7);
 assert(get_order(&squads[0],squads[0].key[7])==(MODE==6?0xffu:12u));
 assert(!memcmp(&before[1],&squads[1],sizeof(TestSquad)) && refreshes==1);
 assert(ui->selected_area==PREMATCH_GAMEPLAN_NO_SELECTION && ui->selected_index==PREMATCH_GAMEPLAN_NO_SELECTION);
 if(MODE==3){assert(!seeds && !setups && !publishes);return 0;}
 assert(seeds==1 && setups==1);assert_consistent(0);assert_consistent(1);
 if(MODE==5){
  /* Refresh projects the new native starting/bench order. Confirm its inverse
   * without losing the earlier edit when native source data is imported again. */
  memcpy(ui->player[0].player_id,squads[0].key[12],16);memcpy(ui->player[1].player_id,squads[0].key[7],16);
  ui->selected_area=PES_PREMATCH_GAMEPLAN_AREA_FIELD;ui->selected_index=0;
  prematch_gameplan_process_substitute(0,PES_PAUSE_INPUT_DECIDE);
  assert(get_order(&squads[0],squads[0].key[7])==7 && get_order(&squads[0],squads[0].key[12])==12);
  assert(seeds==2 && setups==2 && refreshes==2);assert_consistent(0);assert_consistent(1);
 }
 return 0;
}
'''
    code=code.replace('MODE',str(MODES.index(mode)))
    source=tmp_path/'bench.c';source.write_text(code);exe=tmp_path/'bench.exe'
    build=subprocess.run([cc,'-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
        '-Wno-unused-function','-Wno-unused-variable',
        '-I',str(ROOT/'source'),str(source),'-o',str(exe)],capture_output=True,text=True)
    assert build.returncode==0,build.stdout+build.stderr
    result=subprocess.run([str(exe)],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
