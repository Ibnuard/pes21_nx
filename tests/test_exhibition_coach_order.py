"""Host-execute the production roster writer against separate Team/Coach storage."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import pytest
from test_gameplan_editor import function

ROOT = Path(__file__).resolve().parents[1]


def test_appointment_order_belongs_to_coach_and_preserves_all_40_members():
    cc = shutil.which('gcc') or shutil.which('clang')
    if not cc:
        pytest.skip('Host C compiler required')
    source = r'''
#include <stdint.h>
#include <string.h>
#include <assert.h>
#define debugPrintf(...) ((void)0)
typedef struct {uint32_t player_count; uint32_t player_unique_ids[40]; uint8_t shirt_numbers[40];} ExhibitionMasterRoster;
static unsigned char team[0x590], coach[0x254];
static int missing_coach;
static void *get_team(void *w,const uint32_t *id){return team;}
static void *get_coach(void *w,const uint64_t *id){assert(*id==0x123400000007ULL);return missing_coach?0:coach;}
static void *get_player(void *w,uint64_t id){return team;}
static uint64_t get_id(const uint32_t *id){return ((uint64_t)*id<<32)|(*id&65535);}
static void *(*exhibition_commonwork_update_team)(void*,const uint32_t*)=get_team;
static void *(*exhibition_commonwork_update_coach)(void*,const uint64_t*)=get_coach;
static void *(*exhibition_commonwork_update_player)(void*,uint64_t)=get_player;
static uint64_t (*exhibition_get_player_id_by_unique_id)(const uint32_t*)=get_id;
static int exhibition_roster_player_allowed(const ExhibitionMasterRoster *r,uint32_t id){return 1;}
'''
    source += function((ROOT/'source/ue4_hooks.c').read_text(), 'exhibition_install_master_roster')
    source += r'''
int main(void){
 uint32_t id=108; uint64_t cid=0x1234abcd0007ULL;
 ExhibitionMasterRoster r={0}; r.player_count=40;
 memset(team,0xa5,sizeof team);memset(coach,0x5a,sizeof coach);
 memcpy(team,&id,4);memcpy(team+0x250,&cid,8);
 for(unsigned i=0;i<40;i++){r.player_unique_ids[i]=1000+i;r.shirt_numbers[i]=i+1;}
 assert(exhibition_install_master_roster(team,&id,&r)==40);
 for(unsigned i=0;i<40;i++){
  uint64_t member;memcpy(&member,team+272+i*8,8);
  assert(member==get_id(&r.player_unique_ids[i]));
  assert(coach[0x218+i]==i);
 }
 for(unsigned i=0;i<sizeof coach;i++)if(i<0x218||i>=0x240)assert(coach[i]==0x5a);
 uint64_t after;memcpy(&after,team+0x250,8);assert(after==cid);
 unsigned char before[sizeof team];memcpy(before,team,sizeof team);
 missing_coach=1;assert(exhibition_install_master_roster(team,&id,&r)==0);
 assert(!memcmp(before,team,sizeof team));
 return 0;
}
'''
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp)/'test.c'
        path.write_text(source)
        exe = Path(tmp)/'test.exe'
        subprocess.run([cc, '-std=c11', str(path), '-o', str(exe)], check=True, capture_output=True)
        subprocess.run([str(exe)], check=True, capture_output=True)
