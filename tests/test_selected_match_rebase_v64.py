"""Replay the late native HOME overwrite against the real publication code.

The native Training data-sync path imports offline MyClub team data into Match
after the custom hub can already have valid SquadData. These synthetic native
values model that ordering; this is not a Switch execution test.
"""
from pathlib import Path
import shutil
import subprocess

import pytest

from test_gameplan_editor import function

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("fault", range(7))
def test_complete_selected_payload_replaces_late_home_and_keeps_edited_squads(tmp_path, fault):
    cc = shutil.which("gcc") or shutil.which("clang")
    if not cc:
        pytest.skip("host C compiler required")
    hooks = (ROOT / "source/ue4_hooks.c").read_text()
    cases = (ROOT / "tests/prematch_lineup_cases.inc").read_text()
    source = (ROOT / "tests/prematch_lineup_stubs.inc").read_text()
    source += "\n" + "\n".join(function(hooks, name) for name in (
        "exhibition_matchplan_common_side", "exhibition_prematch_commit_refused", "exhibition_sync_prematch_lineup",
        "exhibition_save_matchplan_sides"))
    source += '\n#include "exhibition_match_identity.h"\n'
    source += "\n" + function(cases, "init")
    source += "\n" + function(cases, "assert_consistent")
    source += r'''
static unsigned char source_teams[2][0x590];
static unsigned seeds,setups,seed_failed;
static uint32_t exhibition_home_team_id=108,exhibition_away_team_id=100;
static uint32_t exhibition_native_team_id(uint32_t id){return id<<14;}
static int exhibition_seed_selected_tmpdb(void){
 seeds++;if(seed_failed)return 0;
 for(uint32_t side=0;side<2;side++){
  memcpy(teams[side],source_teams[side],sizeof(teams[side]));
  for(uint32_t i=0;i<TEST_COUNT;i++)
   memcpy((void *)get_player(match_bytes,&side,&i),original[side][i],0x380);
 }
 return 1;
}
static void setup(void *p){
 assert(p==plan);setups++;
 for(uint32_t side=0;side<2;side++){
  *(unsigned char *)exhibition_matchplan_common_side(side)=TEST_COUNT;
  for(uint32_t i=0;i<TEST_COUNT;i++){
   const void *record=get_player(match_bytes,&side,&i);
   unsigned char *info=plan+0x500+side*0x340+i*16;
   memcpy(info,original_info[side][i],8);memcpy(info+8,&record,sizeof(record));
  }
 }
}
static void (*exhibition_matchplan_setup_tmpdb)(void *)=setup;
static void native_lab_assign_matchplan_pads(void *p){assert(p==plan);}
static int fail_save(void){assert(my_side<2);saves[my_side]++;return my_side==0;}
'''
    source += function(hooks, "exhibition_rebase_prepared_matchplan")
    source += r'''
int main(void){
 init();
 for(uint32_t side=0;side<2;side++){
  uint32_t team=exhibition_native_team_id(side?exhibition_away_team_id:exhibition_home_team_id)|(0x3ffdu+side);
  memcpy(teams[side],&team,4);
 }
 memcpy(source_teams,teams,sizeof(teams));
 /* An unregistered reserve becomes a starter; AWAY also has a bench edit.
  * Those keys and orders live in SquadData, not in the corrupted Match. */
 squads[0].member_uid[7]=ids[21];
 squads[1].order[4]=12;squads[1].order[12]=4;
 TestSquad chosen[2];memcpy(chosen,squads,sizeof(squads));
 /* Native Training ActDatasync later copies the offline MyClub HOME into
  * Match: only two placeholder members, unusable body/appearance payloads.
  * The hub's XI/bench projection still appears complete. */
 memset(teams[0],0,sizeof(teams[0]));
 uint32_t flags=2u<<9;memcpy(teams[0]+0x3a6,&flags,4);
 memset(match_bytes+0x1248,0,0x8c00);
 assert(!exhibition_save_matchplan_sides(3u));
 assert(!saves[0] && !saves[1] && !publishes);
 assert(!memcmp(chosen,squads,sizeof(squads)));
 if(FAULT==1)seed_failed=1;
 if(FAULT==2)source_teams[0][2]^=1; /* importer returned wrong physical identity */
 if(FAULT==3)source_teams[1][0x110+4]^=1; /* invalid source identity */
 if(FAULT==4)matchplan_squad_save=fail_save; /* native refused AWAY save */
 if(FAULT==5)live_gameplan_window=(void *)1; /* never reimport a live match */
 if(FAULT==6)exhibition_squad_edit_get_squad_data=NULL; /* missing binding refuses with stage */
 notes=0;my_side=1;
 const int ok=exhibition_rebase_prepared_matchplan();
 assert(my_side==1 && !memcmp(chosen,squads,sizeof(squads)));
 if(FAULT){assert(!ok && !publishes && notes==1);return 0;}
 assert(ok && seeds==1 && setups==1 && notes==1 && publishes==1);
 assert_consistent(0);assert_consistent(1);
 /* Stock Strategy can overwrite HOME again. Final MatchSetup publication
  * produces exactly the same full records/carriers as the frozen audio
  * selection, including the reserve's appearance and parameter payloads. */
 unsigned char expected[sizeof(match_bytes)],expected_plan[sizeof(plan)];
 memcpy(expected,match_bytes,sizeof(expected));memcpy(expected_plan,plan,sizeof(plan));
 memset(teams[0],0,sizeof(teams[0]));memset(match_bytes+0x1248,0,0x8c00);
 assert(exhibition_rebase_prepared_matchplan());
 assert(!memcmp(expected,match_bytes,sizeof(expected)));
 assert(!memcmp(expected_plan,plan,sizeof(plan)));
 assert_consistent(0);assert_consistent(1);
 assert(!memcmp(chosen,squads,sizeof(squads)));
 return 0;
}
'''
    source = source.replace("FAULT", str(fault))
    path = tmp_path / "rebase.c"
    path.write_text(source)
    exe = tmp_path / "rebase.exe"
    compiled = subprocess.run([cc, "-std=c11", "-Wall", "-Wextra", "-Werror",
        "-Wno-unused-function", "-Wno-unused-variable", "-I", str(ROOT / "source"), str(path), "-o", str(exe)],
        capture_output=True, text=True)
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    result = subprocess.run([str(exe)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_final_native_boundary_rebases_before_import_and_audio_resume_does_not_reimport():
    hooks = (ROOT / "source/ue4_hooks.c").read_text()
    final = function(hooks, "pes_exhibition_match_setup_data_entry")
    assert final.index("exhibition_rebase_prepared_matchplan()") < final.index("live_gameplan_capture_identity()")
    assert "fatal_error(\"Exhibition squad publication refused before MatchSetup\")" in final
    rebase = function(hooks, "exhibition_rebase_prepared_matchplan")
    assert "matchplan_squad_load" not in rebase
    assert rebase.index("exhibition_seed_selected_tmpdb()") < rebase.index("exhibition_matchplan_setup_tmpdb(plan)")
