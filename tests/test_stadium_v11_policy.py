"""Candidate-only checks: native ABI/policies, not hardware appearance or FPS."""
from pathlib import Path
import re
import shutil
import struct
import unittest
from test_result_flow import build_and_run, function

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'source/ue4_hooks.c').read_text(encoding='utf-8')
OVERLAY = (ROOT / 'source/overlay.c').read_text(encoding='utf-8')


class StadiumV11Tests(unittest.TestCase):
    def run_c(self, text):
        compiler = shutil.which('gcc')
        if not compiler:
            self.skipTest('gcc unavailable')
        build_and_run(compiler, '#include <stdint.h>\n#include <assert.h>\n'
                      '#include <string.h>\n#include <math.h>\n' + text)

    def test_all_gameplay_helpers_are_suppressed_by_pause_and_loading_cover(self):
        start = OVERLAY.index('  const int modal_match_frontend =')
        end = OVERLAY.index('\n  // The custom selector owns', start)
        gate = OVERLAY[start:end]
        self.run_c(r'''
#define PES_SETPLAY_NONE 0
#define PES_PENALTY_NONE 0
#define PES_VIRTUAL_CURSOR_PAUSE 1
#define PES_VIRTUAL_CURSOR_GAMEPLAN 2
static int custom_gameplan;
static int pes_controller_custom_prematch_gameplan_active(void) {return custom_gameplan;}
int main(void) {
 for(unsigned bits=0;bits<128;bits++) {
  int pause_skin=bits&1,pause_transition=bits&2,pause_camera_active=bits&4;
  int result_skin=bits&8,result_transition=bits&16;
  int virtual_cursor_context=(bits&32)?PES_VIRTUAL_CURSOR_GAMEPLAN:0;
  custom_gameplan=bits&64;
  int setplay_context=3,setplay_options=15,native_setplay_debug=1;
  int cinematic_helper_active=1,penalty_role_p1=1,penalty_role_p2=2;
''' + gate + r'''
  if(bits) {
    assert(!setplay_context && !setplay_options && !native_setplay_debug);
    assert(!cinematic_helper_active && !penalty_role_p1 && !penalty_role_p2);
  } else {assert(setplay_context==3 && cinematic_helper_active && penalty_role_p1);}
 }
}
''')
        fallback = OVERLAY.split('} else if (setplay_options && !native_lab) {', 1)[1].split(
            '\n  const int penalty_helper_active', 1)[0]
        self.assertNotIn('POSITION SHIFT', fallback)
        self.assertNotIn('SWITCH VIEW', fallback)

    def test_long_free_kick_overrides_ambiguous_goal_kick_bit(self):
        start = SOURCE.index('        const uint64_t free_kick_seen =',
                             SOURCE.index('void pes_controller_surface_snapshot'))
        end = SOURCE.index('        if (setplay_context != PES_SETPLAY_NONE)', start)
        block = SOURCE[start:end]
        self.run_c(r'''
#define PES_SETPLAY_FREE_KICK 3
#define PES_SETPLAY_BUTTON_SHORT_CORNER 2
#define PES_SETPLAY_BUTTON_SELECT_THROWER 3
#define PES_SETPLAY_BUTTON_SET_PIECE_TAKER 1
static uint64_t match_native_free_kick_seen_tick;
static uint32_t match_native_setplay_context;
static uint64_t armTicksToNs(uint64_t t) {return t;}
int main(void) {
 for(unsigned mode=0;mode<5;mode++) {
   uint64_t now=900000000;
   match_native_free_kick_seen_tick=mode==1?1:800000000;
   match_native_setplay_context=mode==2?1:PES_SETPLAY_FREE_KICK;
   uint32_t setplay_context=1,setplay_mask=(1u<<1)|(1u<<4)|(1u<<5);
   if(mode==3) setplay_mask|=1u<<2;
   if(mode==4) setplay_mask|=1u<<3;
''' + block + r'''
   if(!mode) {assert(setplay_context==3 && setplay_mask==(1u<<1));}
   else {assert(setplay_context==1 && (setplay_mask&(1u<<4)));}
 }
}
''')

    def test_player_shadow_and_camera_abi_in_optional_compatible_library(self):
        path = ROOT / 'dist/pes21_nx/libUE4.so'
        if not path.exists():
            self.skipTest('requires legally supplied compatible dist/pes21_nx/libUE4.so')
        try:
            from elftools.elf.elffile import ELFFile
        except ImportError:
            self.skipTest('requires pyelftools')
        with path.open('rb') as stream:
            elf = ELFFile(stream)
            def words(address, count=1):
                stream.seek(next(elf.address_offsets(address)))
                return struct.unpack('<'+'I'*count,stream.read(4*count))
            # Both exact selectors use w21 only for choosing/visiting shadows;
            # the quality/LOD query and native actor transforms are unchanged.
            self.assertEqual(words(0x3f0b55c,2),(0xf9400668,0x2a0003f5))
            self.assertEqual(words(0x3f0bb98,2),(0x97e4c66a,0x2a0003f5))
            self.assertEqual(words(0x3f0b610,5),
                             (0x710006bf,0x54000061,0x97e5eeba,0x14000002,0x97e584c4))
            self.assertEqual(words(0x3f0bc68,6),
                             (0x710006bf,0x540000a0,0x71000e9f,0x54000488,0x71000a9f,0x54000440))
            self.assertEqual(words(0x3f0bd20,6),
                             (0x710006bf,0x540000a0,0x71000e9f,0x54000208,0x71000a9f,0x540001c0))
            # tmpdb -> registry -> CAMERA_ID, not one interchangeable enum.
            registry=words(0x85d7958,14)
            ids=(1,)+words(0x81cef54,13)
            self.assertEqual(ids[registry[12]],6)
            self.assertEqual(ids[registry[5]],5)
            self.assertEqual(ids[registry[7]],3)
            self.assertEqual(words(0x665e888),(0xbd003661,)) # CameraParameter+0x34
            stream.seek(next(elf.address_offsets(0x7e2a448)))
            self.assertAlmostEqual(struct.unpack('<f',stream.read(4))[0],0.0174532925)
        self.assertNotIn('player_load + 0x70', SOURCE)
        self.assertNotIn('player_tick + 0x1dc', SOURCE)
        self.assertIn('player_tick + 0x1e4, 0x2a0003f4, 0x52800034', SOURCE)
