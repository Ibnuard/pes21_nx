"""A legacy League final gains a return leg without reopening awarded titles."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_v5_final_migration_and_return_leg_across_processes(tmp_path):
    cc = shutil.which('gcc')
    if not cc:
        pytest.skip('host C compiler required')
    source = tmp_path / 'league-final.c'
    source.write_text(r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include "league_save.h"
typedef struct {uint32_t magic,version,bytes,sequence,checksum;} Header;
static uint32_t hash(const void *p,size_t n) {
  const unsigned char *b=p;uint32_t h=2166136261u;
  for(size_t i=0;i<n;i++)h=(h^b[i])*16777619u;
  return h;
}
static void legacy(const char *path,int completed) {
  const uint32_t teams[]={101u,104u};static LeagueSaveState s;
  memset(&s,0,sizeof(s));s.home_away=1u;s.team_count=2u;s.tournament_valid=1u;
  assert(league_tournament_init(&s.tournament,teams,2u,teams,1u,1,72u));
  while(s.tournament.phase==LEAGUE_PHASE_TABLE) {
    uint32_t i=0;assert(league_tournament_next_human(&s.tournament,&i,NULL,NULL));
    const LeagueFixture *f=&s.tournament.fixtures[i];
    assert(league_tournament_record(&s.tournament,i,0,0,f->home==101u ? 2u : 0u,
                                    f->away==101u ? 2u : 0u));
  }
  assert(s.tournament.phase==LEAGUE_PHASE_KNOCKOUT);
  cup_tournament_set_final_two_legs(&s.tournament.knockout,0); /* sealed v5 semantics */
  if(completed) {
    const CupFixture *f=&s.tournament.knockout.fixtures[0][0];
    assert(league_tournament_record(&s.tournament,0,0,0,f->home==101u ? 2u : 0u,
                                    f->away==101u ? 2u : 0u));
    assert(s.tournament.phase==LEAGUE_PHASE_COMPLETE);
  }
  Header h={0x314c5846u,5u,sizeof(s),1u,hash(&s,sizeof(s))};
  FILE *f=fopen(path,"wb");assert(f);
  assert(fwrite(&h,1,sizeof(h),f)==sizeof(h));
  assert(fwrite(&s,1,sizeof(s),f)==sizeof(s));assert(!fclose(f));
}
int main(int argc,char **argv) {
  assert(argc==2);static LeagueSaveState s;
  if(!strcmp(argv[1],"prepare")) {
    assert(!mkdir("SaveData",0700));
    legacy("SaveData/footballnx_league_1_a.bin",0);
    legacy("SaveData/footballnx_league_2_a.bin",1);
    assert(league_save_read(0,&s));
    assert(cup_tournament_has_second_leg(&s.tournament.knockout,0,0));
    const CupFixture *f=&s.tournament.knockout.fixtures[0][0];
    assert(league_tournament_record(&s.tournament,0,0,0,f->home==101u ? 2u : 0u,
                                    f->away==101u ? 2u : 0u));
    assert(s.tournament.phase==LEAGUE_PHASE_KNOCKOUT && !s.tournament.knockout.champion);
    assert(league_save_write(0,&s));return 0;
  }
  assert(league_save_read(0,&s) && s.tournament.phase==LEAGUE_PHASE_KNOCKOUT);
  const CupFixture *f=&s.tournament.knockout.fixtures[0][0];
  assert(f->first_leg_complete && !f->complete);
  assert(league_tournament_record(&s.tournament,0,0,0,f->home==104u ? 1u : 0u,
                                  f->away==104u ? 1u : 0u));
  assert(s.tournament.phase==LEAGUE_PHASE_COMPLETE && s.tournament.knockout.champion==101u);
  assert(league_save_write(0,&s) && league_save_read(0,&s));
  assert(s.tournament.knockout.champion==101u);
  assert(league_save_read(1,&s) && s.tournament.knockout.champion==101u);
  assert(!cup_tournament_has_second_leg(&s.tournament.knockout,0,0));
  return 0;
}
''', encoding='utf8')
    exe = tmp_path / 'league-final.exe'
    built = subprocess.run([
        cc, '-std=c11', '-Wall', '-Wextra', '-Werror', '-I', str(ROOT / 'source'),
        str(source), *[str(ROOT / 'source' / name) for name in
                       ('league_save.c', 'league_tournament.c', 'cup_tournament.c')],
        '-o', str(exe)], capture_output=True, text=True, timeout=45)
    assert built.returncode == 0, built.stdout + built.stderr
    subprocess.run([str(exe), 'prepare'], cwd=tmp_path, check=True, timeout=15)
    awarded = (tmp_path / 'SaveData/footballnx_league_2_a.bin').read_bytes()
    subprocess.run([str(exe), 'resume'], cwd=tmp_path, check=True, timeout=15)
    assert (tmp_path / 'SaveData/footballnx_league_2_a.bin').read_bytes() == awarded
