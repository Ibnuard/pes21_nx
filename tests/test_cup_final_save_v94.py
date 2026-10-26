"""Legacy pending/champion saves and a return leg saved across processes."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT=Path(__file__).resolve().parents[1]


def test_v4_pending_final_migrates_but_awarded_cup_is_preserved(tmp_path):
    cc=shutil.which('gcc')
    if not cc:
        pytest.skip('host C compiler required')
    source=tmp_path/'final.c'
    source.write_text(r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include "cup_save.h"
typedef struct {uint32_t magic,version,bytes,sequence,checksum;} Header;
static uint32_t hash(const void *p,size_t n){
 const unsigned char *b=p;uint32_t h=2166136261u;
 for(size_t i=0;i<n;i++)h=(h^b[i])*16777619u;
 return h;}
static void legacy(const char *path,int completed){
 const uint32_t teams[]={101,104};CupSaveState s={0};
 s.home_away=1;s.team_count=2;s.tournament_valid=1;
 assert(cup_tournament_init(&s.tournament,teams,2,teams,1,72));
 cup_tournament_set_rules(&s.tournament,1,0);
 if(completed)assert(cup_tournament_record(&s.tournament,0,0,2,0));
 Header h={0x32584346u,4u,sizeof(s),1u,hash(&s,sizeof(s))};
 FILE *f=fopen(path,"wb");assert(f);
 assert(fwrite(&h,1,sizeof(h),f)==sizeof(h));
 assert(fwrite(&s,1,sizeof(s),f)==sizeof(s));assert(!fclose(f));}
int main(int argc,char **argv){
 assert(argc==2);CupSaveState s;
 if(!strcmp(argv[1],"prepare")){
  assert(!mkdir("SaveData",0700));
  legacy("SaveData/footballnx_cup_1_a.bin",0);
  legacy("SaveData/footballnx_cup_2_a.bin",1);
  assert(cup_save_read(0,&s)&&cup_tournament_has_second_leg(&s.tournament,0,0));
  assert(cup_tournament_record(&s.tournament,0,0,2,0));
  assert(!s.tournament.champion&&!s.tournament.fixtures[0][0].complete);
  assert(cup_save_write(0,&s));return 0;
 }
 assert(cup_save_read(0,&s)&&!s.tournament.champion);
 assert(s.tournament.fixtures[0][0].first_leg_home_goals==2);
 assert(cup_tournament_record(&s.tournament,0,0,0,1));
 assert(s.tournament.champion==101&&s.tournament.fixtures[0][0].home_goals==2);
 assert(cup_save_write(0,&s)&&cup_save_read(0,&s)&&s.tournament.champion==101);
 assert(cup_save_read(1,&s)&&s.tournament.champion==101);
 assert(s.tournament.fixtures[0][0].complete&&!s.tournament.fixtures[0][0].first_leg_complete);
 assert(!cup_tournament_has_second_leg(&s.tournament,0,0));
 return 0;}
''',encoding='utf8')
    exe=tmp_path/'final.exe'
    built=subprocess.run([cc,'-std=c11','-Wall','-Wextra','-Werror','-I',str(ROOT/'source'),
                    str(source),str(ROOT/'source/cup_save.c'),str(ROOT/'source/cup_tournament.c'),
                    '-o',str(exe)],capture_output=True,text=True)
    assert built.returncode==0,built.stdout+built.stderr
    subprocess.run([str(exe),'prepare'],cwd=tmp_path,check=True,capture_output=True)
    legacy=(tmp_path/'SaveData/footballnx_cup_2_a.bin').read_bytes()
    subprocess.run([str(exe),'resume'],cwd=tmp_path,check=True,capture_output=True)
    assert (tmp_path/'SaveData/footballnx_cup_2_a.bin').read_bytes()==legacy
