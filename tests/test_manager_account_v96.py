"""Local account gate, password primitives and controller-only product paths."""
from pathlib import Path
import hashlib
import shutil
import subprocess

import pytest

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def account_probe(tmp_path_factory):
    cc=shutil.which('gcc')
    if not cc:pytest.skip('Host C compiler unavailable')
    work=tmp_path_factory.mktemp('manager-account-v96');c=work/'probe.c';exe=work/'probe.exe'
    c.write_text(r'''
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "manager_league_catalog_fixture.inc"
#include "manager_league_dummy.c"
#undef assert
#define assert(c) do{if(!(c)){fprintf(stderr,"line %d: %s\n",__LINE__,#c);exit(97);}}while(0)
static MdView view(void){MdView v;manager_dummy_view(&v);return v;}
static void setup(void){
 epoch_now=1793015700000ULL;memset(&md,0,sizeof(md));md.balance=5000;md.seed=1707;md.club=100;
 md.week_id=1;md.day_ms=MD_DEMO_DAY_MS;strcpy(md.name,"Account United");
 assert(profile_create());strcpy(profile.user_id,"manager_96");assert(profile_save());
 md.created=md.joined=1;make_fixtures();assert(persist());loaded=1;strcpy(password,"Test-Password-96");
 assert(auth_store());auth_clear_inputs();authenticated=0;auth_load();assert(credential_state==1);
 page=MD_REGISTER;focus=0;
}
static void login(const char *secret){
 manager_dummy_pad(A);assert(page==MD_LOGIN);manager_dummy_name_result("MANAGER_96");
 manager_dummy_pad(DOWN);manager_dummy_name_result(secret);manager_dummy_pad(DOWN);manager_dummy_pad(A);
}
int main(int argc,char **argv){
 assert(argc>=2);
 if(!strcmp(argv[1],"sha")){
  MdSha c=md_sha_init();uint8_t out[32];md_sha_update(&c,argv[2],strlen(argv[2]));md_sha_final(&c,out);
  for(unsigned i=0;i<32;i++)printf("%02x",out[i]);return 0;
 }
 if(!strcmp(argv[1],"kdf")){
  uint8_t salt[16],out[32];for(unsigned i=0;i<16;i++)salt[i]=(uint8_t)i;
  md_auth_kdf(argv[2],salt,(uint32_t)atoi(argv[3]),out);for(unsigned i=0;i<32;i++)printf("%02x",out[i]);return 0;
 }
 if(!strcmp(argv[1],"signupfail")) {
  manager_dummy_open();manager_dummy_tick_at(1793015700000ULL);assert(page==MD_REGISTER);
  manager_dummy_pad(A);manager_dummy_pad(A);manager_dummy_pad(A);assert(page==MD_NAME);
  manager_dummy_name_result("Registration United");manager_dummy_pad(DOWN);manager_dummy_name_result("manager_fail");
  manager_dummy_pad(DOWN);manager_dummy_name_result("Secret-Fail-96");assert(!mkdir(MD_FILE ".tmp",0700));
  manager_dummy_pad(X);assert(page==MD_NAME && !authenticated && !md.joined && !md.created);
  FILE *f=fopen(MD_AUTH_FILE,"rb");assert(!f);manager_dummy_pad(B);manager_dummy_pad(B);manager_dummy_pad(B);
  assert(page==MD_REGISTER);focus=0;manager_dummy_pad(A);assert(page==MD_REGISTER&&!authenticated);return 0;
 }
 setup();
 if(!strcmp(argv[1],"gate")){
  MdSave before=md;MdProfile players=profile;
  login("Wrong-Password");assert(page==MD_LOGIN && !authenticated && !password[0]);
  manager_dummy_pad(B);assert(page==MD_REGISTER);login("Test-Password-96");
  assert(authenticated && page==MD_DASHBOARD);for(int i=0;i<3;i++)manager_dummy_pad(A);
  manager_dummy_pad(X);assert(page==MD_LOGOUT);manager_dummy_pad(B);assert(page==MD_DASHBOARD);
  manager_dummy_pad(X);manager_dummy_pad(LEFT);manager_dummy_pad(A);assert(page==MD_REGISTER && !authenticated);
  assert(!password[0]&&!password_confirmation[0]&&!editor&&!restore_pending&&!replay&&!paused);
  assert(!memcmp(&before,&md,sizeof(md)));players.tutorials=profile.tutorials;players.checksum=profile.checksum;
  assert(!memcmp(&players,&profile,sizeof(profile)));assert(!manager_dummy_next_week());
  login("Test-Password-96");assert(authenticated);
 }else if(!strcmp(argv[1],"legacy")){
  assert(!remove(MD_AUTH_FILE));auth_load();assert(!credential_state);manager_dummy_pad(A);
  assert(page==MD_SECURE);manager_dummy_name_result("New-Password-96");manager_dummy_pad(DOWN);
  manager_dummy_name_result("Wrong-Confirm-96");manager_dummy_pad(DOWN);manager_dummy_pad(A);
  assert(page==MD_SECURE&&!authenticated);manager_dummy_pad(UP);manager_dummy_name_result("New-Password-96");
  manager_dummy_pad(DOWN);manager_dummy_pad(A);assert(authenticated&&page==MD_DASHBOARD);
  assert(md_auth_verify(&credential,md.seed,"manager_96","New-Password-96"));
 }else if(!strcmp(argv[1],"corrupt")){
  FILE *f=fopen(MD_AUTH_FILE,"wb");assert(f);fputs("corrupt credentials",f);fclose(f);auth_load();assert(credential_state<0);
  manager_dummy_pad(A);assert(page==MD_REGISTER && !authenticated);
 }else if(!strcmp(argv[1],"directory")){
  assert(!remove(MD_AUTH_FILE));assert(!mkdir(MD_AUTH_FILE,0700));auth_load();assert(credential_state<0);
  manager_dummy_pad(A);assert(page==MD_REGISTER && !authenticated);
 }else if(!strcmp(argv[1],"navigation")){
  auth_enter_hub();tutorial=0;hub_section=2;
  const MdPage expected[5]={MD_TABLE,MD_OVERALL,MD_SCHEDULE,MD_OVERALL,MD_RULES};
  for(unsigned i=0;i<5;i++){page=MD_DASHBOARD;focus=i;MdView v=view();assert(v.count==5);
   manager_dummy_pad(A);assert(page==expected[i]);manager_dummy_pad(B);assert(page==MD_DASHBOARD&&focus==i);}
  packs_build();page=MD_SHOP;focus=0;manager_dummy_pad(A);manager_dummy_pad(A);epoch_now+=MD_PACK_OPEN_MS+1;manager_dummy_tick_at(epoch_now);
  assert(page==MD_PACK_SELECT);focus=4;manager_dummy_pad(DOWN);assert(focus==4);
  focus=0;manager_dummy_pad(A);manager_dummy_pad(RIGHT);manager_dummy_pad(A);assert(selected_count()==2);
  manager_dummy_pad(DOWN);manager_dummy_pad(DOWN);assert(focus==pack_pools[0]);
  MdView v=view();for(unsigned i=0;i<v.pack_count;i++)assert(v.pack_players[i].role==pack_pool[0][i]->position);
 }else assert(0);
 return 0;
}
''')
    ran=subprocess.run([cc,'-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
        '-I',str(ROOT/'source'),'-I',str(ROOT/'tests'),str(c),str(ROOT/'source/manager_league_motion.c'),
        str(ROOT/'source/manager_league_plan.c'),str(ROOT/'source/gameplan_preset.c'),'-lm','-pthread','-o',str(exe)],capture_output=True)
    assert ran.returncode==0,ran.stderr.decode(errors='replace')
    return exe

def test_sha256_known_answers(account_probe,tmp_path):
    for text in ('','abc','a'*55,'b'*56,'c'*63,'d'*64,'e'*65,'f'*1000):
        out=subprocess.check_output([str(account_probe),'sha',text],cwd=tmp_path,text=True)
        assert out==hashlib.sha256(text.encode()).hexdigest()

def test_pbkdf2_sha256_against_independent_implementation(account_probe,tmp_path):
    for secret,rounds in (('',1),('password',2),('a'*63,1000),('b'*80,120000)):
        out=subprocess.check_output([str(account_probe),'kdf',secret,str(rounds)],cwd=tmp_path,text=True)
        assert out==hashlib.pbkdf2_hmac('sha256',secret.encode(),bytes(range(16)),rounds).hex()

@pytest.mark.parametrize('mode',['gate','legacy','corrupt','directory','navigation','signupfail'])
def test_account_and_product_paths(account_probe,tmp_path,mode):
    ran=subprocess.run([str(account_probe),mode],cwd=tmp_path,capture_output=True,timeout=25)
    assert ran.returncode==0,(ran.stdout+ran.stderr).decode(errors='replace')
    for path in (tmp_path/'SaveData').rglob('*'):
        if path.is_file():assert b'Test-Password-96' not in path.read_bytes()
