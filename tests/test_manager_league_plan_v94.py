"""Execute Manager-only preset persistence and native office bridge on host.

All players, accounts and formations below are project-authored synthetic data.
Native callbacks are modeled; these checks do not claim Switch execution.
"""
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def plan_probe(tmp_path_factory):
    cc = shutil.which("gcc") or shutil.which("clang")
    if not cc:
        pytest.skip("Host C compiler required")
    folder = tmp_path_factory.mktemp("manager-plan-v94")
    cfile = folder / "probe.c"
    exe = folder / "probe.exe"
    cfile.write_text(r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "manager_league_plan.h"

static ManagerLeaguePlanScope scope;
static GameplanPreset plan;
static void initialize(void) {
 memset(&scope,0,sizeof(scope));memset(&plan,0,sizeof(plan));
 scope.account=0x1020304050607080ULL;scope.team_id=111;scope.player_count=26;
 memcpy(scope.runtime_id,"0123456789abcdef",16);
 memset(scope.content_hash,'a',64);
 plan.team_id=scope.team_id;plan.player_count=scope.player_count;
 for(uint32_t i=0;i<scope.player_count;i++){
  scope.players[i]=1000+i;scope.positions[i]=(uint8_t)(i==0 || i==18?0:1+i%12);
  memcpy(plan.players[i].player_id,&scope.players[i],4);plan.players[i].order_no=(uint8_t)i;
  plan.players[i].reserved[0]=(uint8_t)(i<18?i:0xff);
  plan.players[i].reserved[1]=0x4d;plan.players[i].reserved[2]=1;
 }
}
static void path(uint32_t slot,uint32_t copy,char out[112]) {
 snprintf(out,112,"SaveData/footballnx_manager_plan_1020304050607080_111_%u_%c.bin",slot+1,copy?'b':'a');
}
static void corrupt(uint32_t slot,uint32_t copy) {
 char file[112];path(slot,copy,file);FILE *f=fopen(file,"r+b");assert(f);
 assert(!fseek(f,-1,SEEK_END));int b=fgetc(f);assert(b!=EOF);
 assert(!fseek(f,-1,SEEK_END));assert(fputc(b^0x55,f)!=EOF);assert(!fclose(f));
}
static void persistence(void) {
 GameplanPreset out;
 assert(manager_league_plan_write(&scope,3,&plan));
 assert(manager_league_plan_read(&scope,3,&out));assert(!memcmp(&plan,&out,sizeof(plan)));
 assert(!manager_league_plan_read(&scope,0,&out));
 plan.tactics=1;assert(manager_league_plan_write(&scope,0,&plan));
 assert(manager_league_plan_read(&scope,0,&out)&&out.tactics==1);
 assert(manager_league_plan_read(&scope,3,&out)&&!out.tactics);
 assert(!manager_league_plan_write(&scope,4,&plan));
 assert(!manager_league_plan_read(&scope,4,&out));
 /* Same club's native preset remains independent, and neither overwrites it. */
 assert(gameplan_preset_write(scope.team_id,0,&plan));
 GameplanPreset native=plan;native.tactics=0;
 assert(manager_league_plan_write(&scope,0,&native));
 assert(gameplan_preset_read(scope.team_id,0,&out)&&out.tactics==1);
}
static void namespaces(void) {
 assert(manager_league_plan_write(&scope,0,&plan));
 GameplanPreset out;memset(&out,0xa5,sizeof(out));GameplanPreset untouched=out;
 ManagerLeaguePlanScope changed=scope;
 changed.account++;assert(!manager_league_plan_read(&changed,0,&out));
 changed=scope;changed.team_id++;assert(!manager_league_plan_read(&changed,0,&out));
 changed=scope;changed.runtime_id[0]='f';assert(!manager_league_plan_read(&changed,0,&out));
 changed=scope;changed.content_hash[0]='b';assert(!manager_league_plan_read(&changed,0,&out));
 changed=scope;changed.players[25]++;assert(!manager_league_plan_read(&changed,0,&out));
 changed=scope;changed.positions[25]=4;assert(!manager_league_plan_read(&changed,0,&out));
 assert(!memcmp(&out,&untouched,sizeof(out)));
 changed=scope;
 for(uint32_t i=0;i<scope.player_count;i++){
  changed.players[i]=scope.players[scope.player_count-i-1];
  changed.positions[i]=scope.positions[scope.player_count-i-1];
 }
 assert(manager_league_plan_read(&changed,0,&out));assert(!memcmp(&out,&plan,sizeof(out)));
}
static void validation(void) {
 assert(manager_league_plan_scope_valid(&scope));assert(manager_league_plan_compatible(&scope,&plan));
 ManagerLeaguePlanScope bad=scope;bad.player_count=41;assert(!manager_league_plan_scope_valid(&bad));
 bad=scope;bad.account=0;assert(!manager_league_plan_scope_valid(&bad));
 bad=scope;bad.players[2]=bad.players[1];assert(!manager_league_plan_scope_valid(&bad));
 bad=scope;bad.positions[2]=13;assert(!manager_league_plan_scope_valid(&bad));
 bad=scope;bad.positions[0]=bad.positions[18]=1;assert(!manager_league_plan_scope_valid(&bad));
 bad=scope;bad.runtime_id[4]='z';assert(!manager_league_plan_scope_valid(&bad));
 bad=scope;bad.content_hash[63]=0;assert(!manager_league_plan_scope_valid(&bad));
 bad=scope;memset(bad.content_hash,'0',64);assert(!manager_league_plan_scope_valid(&bad));
 GameplanPreset broken=plan;broken.players[0].order_no=11;broken.players[11].order_no=0;
 assert(!manager_league_plan_compatible(&scope,&broken)); /* no starter GK */
 broken=plan;broken.players[18].order_no=5;broken.players[5].order_no=18;
 assert(!manager_league_plan_compatible(&scope,&broken)); /* two starter GKs */
 broken=plan;broken.players[0].order_no=5;broken.players[5].order_no=0;
 assert(manager_league_plan_compatible(&scope,&broken)); /* keeper need not be order zero */
 broken=plan;broken.players[1].order_no=0;assert(!manager_league_plan_compatible(&scope,&broken));
 broken=plan;broken.players[1].order_no=26;assert(!manager_league_plan_compatible(&scope,&broken));
 broken=plan;broken.players[1].player_id[15]=1;assert(!manager_league_plan_compatible(&scope,&broken));
 broken=plan;uint32_t other=9999;memcpy(broken.players[1].player_id,&other,4);
 assert(!manager_league_plan_compatible(&scope,&broken));
 broken=plan;memcpy(broken.players[1].player_id,broken.players[2].player_id,16);
 assert(!manager_league_plan_write(&scope,0,&broken));
 scope.player_count=plan.player_count=40;
 for(uint32_t i=26;i<40;i++){scope.players[i]=1000+i;scope.positions[i]=4;
  memcpy(plan.players[i].player_id,&scope.players[i],4);plan.players[i].order_no=(uint8_t)i;}
 for(uint32_t i=26;i<40;i++){plan.players[i].reserved[0]=0xff;plan.players[i].reserved[1]=0x4d;plan.players[i].reserved[2]=1;}
 assert(manager_league_plan_write(&scope,3,&plan));
}
static void recovery(void) {
 GameplanPreset out;
 assert(manager_league_plan_write(&scope,1,&plan));
 plan.tactics=1;assert(manager_league_plan_write(&scope,1,&plan));
 assert(manager_league_plan_read(&scope,1,&out)&&out.tactics==1);
 corrupt(1,1);assert(manager_league_plan_read(&scope,1,&out)&&!out.tactics);
 assert(manager_league_plan_write(&scope,1,&plan));
 assert(manager_league_plan_read(&scope,1,&out)&&out.tactics==1);
 corrupt(1,1);corrupt(1,0);memset(&out,0x66,sizeof(out));GameplanPreset untouched=out;
 assert(!manager_league_plan_read(&scope,1,&out));assert(!memcmp(&out,&untouched,sizeof(out)));
}

typedef struct {uint64_t words[18];} TmpdbFormationValue;
typedef struct {uint8_t bytes[52];} TmpdbMatchPlanSettingsValue;
typedef struct {unsigned char player_id[16];uint32_t order_no,member_id;} PrematchGameplanPlayer;
typedef struct {void *squad_data;uint32_t player_count,default_formation_valid;PrematchGameplanPlayer players[40];} PrematchGameplanSide;
typedef struct {uint32_t count,key[40][4],order[40],member[40];TmpdbFormationValue formation[2];uint32_t tactics;} TestSquad;
static TestSquad squad;
static PrematchGameplanSide exhibition_gameplan_sides[2];
static int editor=1,career_editor,started=1,handoff=-1,failed_restore,restore_calls,swaps;
static uint32_t exhibition_home_team_id,exhibition_away_team_id,main_menu_2p_prematch_bootstrap_mode;
static void *live_gameplan_window;
#define MAIN_MENU_2P_PREMATCH_BOOT_HUB 1
#define EXHIBITION_PRE_STRATEGY_SQUAD_SNAPSHOT_BYTES 2048
static int ml_frontend_plan_editor(void){return career_editor;}
static int manager_dummy_plan_editor(void){return editor;}
static int manager_dummy_plan_scope(ManagerLeaguePlanScope *out){*out=scope;return editor;}
static int manager_dummy_plan_teams(uint32_t *home,uint32_t *away){*home=scope.team_id;*away=112;return editor;}
static void manager_dummy_plan_handoff_result(int value){handoff=value;}
static void competition_frontend_finish_close(void){}
static int manager_dummy_preset_read(uint32_t team,uint32_t slot,GameplanPreset *out){
 assert(team==scope.team_id);return manager_league_plan_read(&scope,slot,out);
}
static int main_menu_start_exhibition_match(void){return started;}
static uint32_t crypt(void){return 0xa59c43e7;}
static uint32_t (*exhibition_common_get_crypt_key)(void)=crypt;
static uint32_t count(void *s){return ((TestSquad*)s)->count;}
static uint32_t (*exhibition_squad_data_get_player_count)(void*)=count;
static void *key(void *s,const uint32_t *i){return ((TestSquad*)s)->key[*i];}
static void *(*exhibition_squad_data_get_player_by_index)(void*,const uint32_t*)=key;
static uint32_t find(void *s,const void *id){TestSquad *t=s;for(uint32_t i=0;i<t->count;i++)if(!memcmp(t->key[i],id,16))return i;assert(0);return 0;}
static uint32_t order(void *s,const void *id){return ((TestSquad*)s)->order[find(s,id)];}
static uint32_t member(void *s,const void *id){return ((TestSquad*)s)->member[find(s,id)];}
static uint32_t (*match_squad_data_get_order_no)(void*,const void*)=order;
static uint32_t (*match_squad_data_get_member_id)(void*,const void*)=member;
static uint32_t role(const void *f,uint32_t order,uint32_t phase){assert(order<11&&!phase);return ((const uint8_t*)f)[22+order];}
static const uint8_t *position(const void *f,uint32_t order,uint32_t phase){assert(order<11&&!phase);return (const uint8_t*)f+order*2;}
static uint32_t (*match_formation_get_role)(const void*,uint32_t,uint32_t)=role;
static const uint8_t *(*match_formation_get_position)(const void*,uint32_t,uint32_t)=position;
static void copy(void *out,const void *in){memcpy(out,in,sizeof(TestSquad));}
static void (*match_squad_data_copy_construct)(void*,const void*)=copy;
static void (*match_squad_data_copy_assign)(void*,const void*)=copy;
static void destruct(void *p){(void)p;}
static void (*match_squad_data_destruct)(void*)=destruct;
#include "manager_league_native_plan.inc"
static void prematch_gameplan_refresh_side(uint32_t side){
 assert(!side);PrematchGameplanSide *ui=&exhibition_gameplan_sides[side];ui->squad_data=&squad;ui->player_count=squad.count;
 for(uint32_t i=0;i<squad.count;i++){memcpy(ui->players[i].player_id,squad.key[i],16);ui->players[i].order_no=squad.order[i];ui->players[i].member_id=squad.member[i];}
}
static int prematch_gameplan_replace_player(uint32_t side,void *s,const void *out,const void *in){
 assert(!side);TestSquad *t=s;uint32_t a=find(s,out),b=find(s,in),swap=t->order[a];
 t->order[a]=t->order[b];t->order[b]=swap;swap=t->member[a];t->member[a]=t->member[b];t->member[b]=swap;
 swaps++;return manager_league_office_lineup_valid(side,s);
}
static int prematch_gameplan_restore(uint32_t side,const GameplanPreset *saved){
 restore_calls++;assert(manager_league_office_lineup_valid(side,&squad));
 if(failed_restore){squad.order[11]=7;return 0;}
 for(uint32_t i=0;i<saved->player_count;i++){
  uint32_t at=find(&squad,saved->players[i].player_id),order=saved->players[i].order_no;
  squad.order[at]=order<18?order:0xff;squad.member[at]=order<18?order:0xff;
 }
 prematch_gameplan_refresh_side(side);TmpdbMatchPlanSettingsValue settings={0};
 assert(manager_league_native_plan_rekey_settings(side,saved,&settings));
 return manager_league_office_lineup_valid(side,&squad);
}
typedef struct {const char *label;uint8_t role[11],x[11],y[11];} PrematchFormationPreset;
static const PrematchFormationPreset prematch_formation_presets[]={
 {"4-3-3",{0,2,1,1,3,5,4,5,9,12,10},{52,10,38,67,95,25,52,80,26,52,78},
 {2,12,12,12,12,25,25,25,42,42,42}}};
static void *prematch_gameplan_resolve_squad(uint32_t side){assert(!side);return &squad;}
static TmpdbFormationValue formation_get(const void *s,uint32_t tactic){return ((const TestSquad*)s)->formation[tactic];}
static TmpdbFormationValue (*match_squad_data_get_formation)(const void*,uint32_t)=formation_get;
static void formation_position(void *f,uint32_t order,const void *p,uint32_t phase){assert(!phase);memcpy((uint8_t*)f+order*2,p,2);}
static void (*match_formation_set_position)(void*,uint32_t,const void*,uint32_t)=formation_position;
static void formation_role(void *f,uint32_t order,uint32_t role,uint32_t phase){assert(!phase);((uint8_t*)f)[22+order]=(uint8_t)role;}
static void (*match_formation_set_role)(void*,uint32_t,uint32_t,uint32_t)=formation_role;
static void formation_set(void *s,uint32_t t,const void *f){((TestSquad*)s)->formation[t]=*(const TmpdbFormationValue*)f;}
static void (*match_squad_data_set_formation)(void*,uint32_t,const void*)=formation_set;
static void *formation_copy(void *out,const void *in){return memcpy(out,in,sizeof(TmpdbFormationValue));}
static void *(*match_formation_copy_assign)(void*,const void*)=formation_copy;
static void member_role(void *s,uint32_t role,uint32_t member,const uint32_t *t){
 TestSquad *squad=s;for(uint32_t i=0;i<squad->count;i++)if(squad->member[i]==member){
  assert(squad->order[i]<11);formation_role(&squad->formation[*t],squad->order[i],role,0);return;}assert(0);
}
static void (*match_squad_data_set_player_role_position)(void*,uint32_t,uint32_t,const uint32_t*)=member_role;
static void tactics_set(void *s,uint32_t tactic){((TestSquad*)s)->tactics=tactic;}
static void (*match_squad_data_set_tactics)(void*,uint32_t)=tactics_set;
static void prematch_gameplan_store_formation(void *s,uint32_t t,const TmpdbFormationValue *f){formation_set(s,t,f);}
#include "manager_league_native_restore.inc"
static void initialize_native(void){
 memset(&squad,0,sizeof(squad));squad.count=scope.player_count;
 for(uint32_t i=0;i<squad.count;i++){
  squad.key[i][0]=0x6789;squad.key[i][1]=scope.players[i]^crypt();
  squad.order[i]=i<18?i:0xff;squad.member[i]=i<18?i:0xff;
 }
 for(uint32_t tactic=0;tactic<2;tactic++)for(uint32_t i=0;i<11;i++){
  plan.formation[tactic][2*i]=i?24:0;plan.formation[tactic][2*i+1]=50;
  plan.formation[tactic][22+i]=i?4:0;
 }
 prematch_gameplan_refresh_side(0);
}
static void bridge(void){
 initialize_native();assert(native_office_plan_editor());
 assert(manager_league_native_plan_snapshot_members(0,&plan));
 assert(manager_league_office_lineup_valid(0,&squad));
 assert(!manager_league_office_lineup_valid(1,&squad));
 assert(manager_league_native_plan_shape_valid(&plan));
 plan.formation[1][24]=0;assert(!manager_league_native_plan_shape_valid(&plan));plan.formation[1][24]=4;
 plan.formation[0][7]=106;assert(!manager_league_native_plan_shape_valid(&plan));plan.formation[0][7]=50;
 uint32_t old=squad.member[1];squad.member[1]=0;assert(!manager_league_office_lineup_valid(0,&squad));squad.member[1]=old;
 old=squad.order[25];squad.order[25]=40;assert(!manager_league_office_lineup_valid(0,&squad));squad.order[25]=old;
 old=squad.key[25][1];squad.key[25][1]=999^crypt();assert(!manager_league_office_lineup_valid(0,&squad));squad.key[25][1]=old;
 old=squad.order[0];squad.order[0]=squad.order[11];squad.order[11]=old;
 assert(!manager_league_office_lineup_valid(0,&squad));initialize_native();
 assert(manager_league_plan_write(&scope,3,&plan));main_menu_activate_manager_plan();
 assert(handoff==1&&manager_league_plan_restore_pending&&exhibition_home_team_id==111&&exhibition_away_team_id==112);
 assert(main_menu_2p_prematch_bootstrap_mode==1);
 started=0;main_menu_activate_manager_plan();assert(!handoff&&!manager_league_plan_restore_pending);
 editor=0;assert(!native_office_plan_editor());main_menu_activate_manager_plan();assert(!handoff);
 career_editor=1;assert(native_office_plan_editor());
}
static void restore(void){
 initialize_native();
 /* Incoming bench keeper moves to order 5; outgoing keeper becomes a reserve. */
 plan.players[18].order_no=5;plan.players[5].order_no=0;plan.players[0].order_no=18;
 plan.players[18].reserved[0]=0;plan.players[0].reserved[0]=0xff;
 for(uint32_t t=0;t<2;t++){plan.formation[t][22]=4;plan.formation[t][27]=0;}
 assert(manager_league_native_plan_shape_valid(&plan));
 GameplanPreset local=plan;
 for(uint32_t i=0;i<local.player_count;i++)memcpy(local.players[i].player_id,squad.key[i],16);
 TestSquad before=squad;failed_restore=1;
 assert(!manager_league_native_plan_restore(0,&local));assert(!memcmp(&before,&squad,sizeof(squad)));
 assert(swaps==1&&restore_calls==1);
 failed_restore=0;assert(manager_league_native_plan_restore(0,&local));
 assert(squad.order[18]==5&&squad.order[0]==0xff&&squad.order[5]==0);
 before=squad;local.players[1].player_id[15]=1;
 assert(!manager_league_native_plan_restore(0,&local));assert(!memcmp(&before,&squad,sizeof(squad)));
}
static void seed(void){
 initialize_native();squad.order[0]=7;squad.order[7]=0;
 memset(squad.formation,0xff,sizeof(squad.formation));
 exhibition_gameplan_sides[0].default_formation_valid=1;
 assert(manager_league_native_plan_seed());assert(!exhibition_gameplan_sides[0].default_formation_valid);
 for(uint32_t t=0;t<2;t++)for(uint32_t order=0;order<11;order++){
  const uint32_t r=role(&squad.formation[t],order,0);assert((r==0)==(order==7));
  const uint8_t *pos=position(&squad.formation[t],order,0);assert(pos[0]<=48&&pos[1]<=105);
 }
 GameplanPreset seeded=plan;
 for(uint32_t i=0;i<seeded.player_count;i++)seeded.players[i].order_no=(uint8_t)(i==0?7:i==7?0:i);
 for(uint32_t t=0;t<2;t++)memcpy(seeded.formation[t],&squad.formation[t],144);
 assert(manager_league_native_plan_shape_valid(&seeded));
 /* Ordinary modes do not touch their squad or default shape. */
 TestSquad before=squad;editor=0;assert(manager_league_native_plan_seed());assert(!memcmp(&before,&squad,sizeof(squad)));
}
static void members(void){
 initialize_native();assert(manager_league_native_plan_snapshot_members(0,&plan));
 assert(manager_league_native_plan_members_valid(&plan));
 GameplanPreset local=plan;
 for(uint32_t i=0;i<local.player_count;i++)memcpy(local.players[i].player_id,squad.key[i],16);
 /* Reordered profile bootstrap assigns different MemberIds to these players. */
 squad.member[2]=13;squad.member[13]=2;
 TmpdbMatchPlanSettingsValue settings;memset(&settings,0xff,sizeof(settings));
 settings.bytes[49]=2;settings.bytes[40]=13;settings.bytes[48]=2;settings.bytes[45]=0x77;
 assert(manager_league_native_plan_rekey_settings(0,&local,&settings));
 assert(settings.bytes[49]==13&&settings.bytes[40]==2&&settings.bytes[48]==13&&settings.bytes[45]==0x77);
 local.players[0].reserved[2]=0;assert(!manager_league_native_plan_members_valid(&local));
 assert(!manager_league_native_plan_rekey_settings(0,&local,&settings));
 local=plan;memset(local.players[0].reserved,0,3);assert(!manager_league_native_plan_shape_valid(&local));
 local=plan;local.players[1].reserved[0]=0;assert(!manager_league_native_plan_members_valid(&local));
 editor=0;assert(manager_league_native_plan_rekey_settings(1,&local,&settings));
}
int main(int argc,char **argv){
 assert(argc==2);initialize();
 if(!strcmp(argv[1],"persistence"))persistence();
 else if(!strcmp(argv[1],"namespaces"))namespaces();
 else if(!strcmp(argv[1],"validation"))validation();
 else if(!strcmp(argv[1],"recovery"))recovery();
 else if(!strcmp(argv[1],"bridge"))bridge();
 else if(!strcmp(argv[1],"restore"))restore();
 else if(!strcmp(argv[1],"seed"))seed();
 else if(!strcmp(argv[1],"members"))members();
 else assert(0);
 return 0;
}
''', encoding="utf-8")
    result = subprocess.run(
        [cc, "-std=c11", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "source"),
         str(cfile), str(ROOT / "source/manager_league_plan.c"),
         str(ROOT / "source/gameplan_preset.c"), "-o", str(exe)],
        text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    return exe


@pytest.mark.parametrize("case", ["persistence", "namespaces", "validation", "recovery", "bridge", "restore", "seed", "members"])
def test_manager_only_presets_and_native_bridge(plan_probe, tmp_path, case):
    result = subprocess.run([str(plan_probe), case], cwd=tmp_path, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
