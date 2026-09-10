"""Execute pending-substitution transactions and transition lifetime guards."""
from pathlib import Path
import unittest
from test_gameplan_editor import function
import test_pause_v19

ROOT = Path(__file__).resolve().parents[1]


class PauseV20Tests(unittest.TestCase):
    run_c = test_pause_v19.PauseV19Tests.run_c

    def test_pending_cancel_replace_limit_reject_commit_and_applied(self):
        hooks = (ROOT / 'source/ue4_hooks.c').read_text(encoding='utf-8')
        code = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#define PREMATCH_GAMEPLAN_MAX_PLAYERS 40u
#define debugPrintf(...) ((void)0)
typedef struct {uint8_t slots[6][4];} Squad;
static Squad squads[2];
static struct {void *squad_data;} exhibition_gameplan_sides[2];
static uint64_t live_substitution_locked[2];
static unsigned limit=2, rejected=39;
static const uint8_t *live_squad_reservation_info(const void *s, uint32_t i) {
 assert(i<6); return ((const Squad*)s)->slots[i];
}
static void live_squad_cancel_reservation(void *s, uint32_t i) {
 uint8_t *p=((Squad*)s)->slots[i]; assert(!p[3]);
 p[0]=p[1]=255; p[2]=p[3]=0;
}
static int live_squad_can_reserve(void *s,uint32_t out,uint32_t in) {
 // Native CanReserved checks the authoritative starting/bench membership.
 return out<11 && in>=11 && in<40;
}
static int live_squad_reserve(void *s,uint32_t out,uint32_t in) {
 Squad *q=s; unsigned used=0;
 if(in==rejected) return 0;
 for(unsigned i=0;i<6;i++) {
  if(q->slots[i][0]<40) {
   used++;
   if(q->slots[i][0]==in || q->slots[i][1]==out) return 0;
  }
 }
 if(used>=limit) return 0;
 for(unsigned i=0;i<6;i++) if(q->slots[i][0]==255) {
  q->slots[i][0]=in; q->slots[i][1]=out; q->slots[i][2]=1; return 1;
 }
 return 0;
}
static int pair(unsigned side,unsigned out,unsigned in) {
 for(unsigned i=0;i<6;i++) if(squads[side].slots[i][0]==in &&
    squads[side].slots[i][1]==out) return 1;
 return 0;
}
'''
        code += function(hooks, 'live_gameplan_lock_substitutions')
        code += function(hooks, 'live_gameplan_change_substitution')
        code += r'''
int main(void) {
 for(unsigned s=0;s<2;s++) {
  exhibition_gameplan_sides[s].squad_data=&squads[s];
  for(unsigned i=0;i<6;i++) live_squad_cancel_reservation(&squads[s],i);
 }
 assert(live_gameplan_change_substitution(0,8,14)); assert(pair(0,8,14));
 live_gameplan_lock_substitutions(0,0); assert(!live_substitution_locked[0]);
 assert(live_gameplan_change_substitution(0,14,8)); assert(!pair(0,8,14));
 assert(live_gameplan_change_substitution(0,8,14));
 assert(live_gameplan_change_substitution(0,9,15));
 // At the limit: replace an incoming player, and undo, without spending a sub.
 assert(live_gameplan_change_substitution(0,14,16));
 assert(pair(0,8,16) && pair(0,9,15) && !pair(0,8,14));
 assert(!live_gameplan_change_substitution(0,16,39)); assert(pair(0,8,16));
 assert(!live_gameplan_change_substitution(0,10,17)); assert(pair(0,8,16));
 assert(live_gameplan_change_substitution(0,16,8)); assert(!pair(0,8,16));
 assert(live_gameplan_change_substitution(0,8,17));
 // Back locks outgoing members, across reopening, independently by team.
 live_gameplan_lock_substitutions(0,1);
 assert((live_substitution_locked[0] & ((1ULL<<8)|(1ULL<<9))) == ((1ULL<<8)|(1ULL<<9)));
 assert(!live_gameplan_change_substitution(0,17,8));
 assert(!live_gameplan_change_substitution(0,17,18));
 assert(!live_gameplan_change_substitution(0,10,9));
 assert(live_gameplan_change_substitution(1,8,14)); assert(!live_substitution_locked[1]);
 squads[1].slots[0][3]=1;
 live_gameplan_lock_substitutions(1,0); assert(live_substitution_locked[1] == (1ULL<<8));
 assert(!live_gameplan_change_substitution(1,10,8));
 assert(!live_gameplan_change_substitution(2,8,14));
 return 0;
}
'''
        self.run_c(code)

    def test_transition_handoff_and_resume_need_fresh_gameplay(self):
        hooks = (ROOT / 'source/ue4_hooks.c').read_text(encoding='utf-8')
        code = r'''
#include <assert.h>
#include <stdint.h>
static uint64_t now, pause_resume_transition_tick, pause_editor_transition_tick, match_pause_seen_tick;
static uint32_t exhibition_gameplan_custom_active, live_gameplan_returning_to_pause, match_pause_skin_ready;
static uint64_t armGetSystemTick(void) {return now;}
static uint64_t armTicksToNs(uint64_t t) {return t;}
'''
        code += function(hooks, 'pes_controller_pause_transition')
        code += function(hooks, 'pause_resume_reveal')
        code += r'''
int main(void) {
 now=100; pause_editor_transition_tick=now;
 assert(pes_controller_pause_transition()==1);
 now+=6000000000ULL; assert(pes_controller_pause_transition()==1);
 exhibition_gameplan_custom_active=1; assert(!pes_controller_pause_transition());
 exhibition_gameplan_custom_active=0; live_gameplan_returning_to_pause=1;
 assert(pes_controller_pause_transition()==2);
 pause_editor_transition_tick=0; assert(!pes_controller_pause_transition());
 pause_resume_transition_tick=now; match_pause_skin_ready=1;
 now+=400000000ULL; pause_resume_reveal(); assert(pes_controller_pause_transition()==3);
 match_pause_skin_ready=0; match_pause_seen_tick=now;
 pause_resume_reveal(); assert(pes_controller_pause_transition()==3);
 now+=250000000ULL; pause_resume_reveal(); assert(!pes_controller_pause_transition());
 pause_resume_transition_tick=now; now+=6000000000ULL;
 assert(!pes_controller_pause_transition());
 return 0;
}
'''
        self.run_c(code)


if __name__ == '__main__':
    unittest.main()
