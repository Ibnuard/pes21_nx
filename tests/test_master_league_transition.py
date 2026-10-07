"""The office Game Plan must remain behind the loading cover until ready."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from test_gameplan_editor import function

ROOT = Path(__file__).resolve().parents[1]


class CareerTransitionTests(unittest.TestCase):
    def test_bootstrap_and_return_cover_are_continuous(self):
        cc = shutil.which('gcc')
        if not cc:
            self.skipTest('Host C compiler unavailable')
        hooks = (ROOT / 'source/ue4_hooks.c').read_text()
        source = r'''
#include <stdint.h>
#include <assert.h>
#define PES_2P_TRANSITION_LOADING 1u
static uint32_t main_menu_2p_transition_active,main_menu_2p_transition_kind;
static int office,ready;
static int ml_frontend_plan_editor(void){return office;}
static int pes_controller_custom_prematch_gameplan_active(void){return ready;}
'''
        source += function(hooks, 'pes_controller_2p_transition_active')
        source += function(hooks, 'pes_controller_2p_transition_kind')
        source += r'''
int main(void){
 assert(!pes_controller_2p_transition_active());
 office=1; /* immediately after choosing career Game Plan */
 assert(pes_controller_2p_transition_active());
 assert(pes_controller_2p_transition_kind()==PES_2P_TRANSITION_LOADING);
 main_menu_2p_transition_active=1;
 assert(pes_controller_2p_transition_active());
 main_menu_2p_transition_active=0; /* native publishes its Hub */
 assert(pes_controller_2p_transition_active());
 ready=1; /* actual editor has prepared both squad panes */
 assert(!pes_controller_2p_transition_active());
 ready=0; /* failure or B return tears down native editor */
 assert(pes_controller_2p_transition_active());
 office=0; /* career restored */
 assert(!pes_controller_2p_transition_active());
 main_menu_2p_transition_active=1;main_menu_2p_transition_kind=2;
 assert(pes_controller_2p_transition_active() && pes_controller_2p_transition_kind()==2);
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'cover.c'
            path.write_text(source)
            exe = Path(temp) / 'cover.exe'
            subprocess.run([cc, '-std=c11', '-Wall', '-Wextra', '-Werror', str(path), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)
