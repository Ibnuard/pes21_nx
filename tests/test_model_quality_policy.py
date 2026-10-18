"""High selects the Standard player class; Low and stadium remain native."""
from pathlib import Path
import re
import shutil
import struct

import pytest
from test_result_flow import build_and_run

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT/'source/model_quality_policy.inc').read_text()


@pytest.mark.parametrize('defines', ['', '#define NEAR_CAMERA_TRACE 1\n'])
def test_checked_and_idempotent_install_changes_only_high_class_call(defines):
    cc = shutil.which('gcc')
    if not cc:
        pytest.skip('host C compiler required')
    build_and_run(cc, defines + r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef struct {int unused;} so_module;
static unsigned missing, notes;
static int native_control;
int pes_gl_probe_native_player_class(void) { return native_control; }
static uint32_t code[128];
static uintptr_t so_try_find_addr_rx(so_module *m,const char *n) {
 (void)m;assert(!strcmp(n,"_ZN13UEPlayerModel8LoadImplEv"));
 return missing?0:(uintptr_t)code;
}
static uintptr_t so_find_addr(so_module *m,const char *n) {return so_try_find_addr_rx(m,n);}
static void scene_runtime_note(const char *a,const char *m) {(void)m;assert(!strcmp(a,"model quality"));notes++;}
''' + SOURCE + r'''
int main(void) {
 so_module module={0};
 const uint32_t expected[4]={0x97e7b0a3,0xaa0003f6,0x910023e0,0x97e85630};
 memcpy((char *)code+0xd4,expected,16);
 uint32_t original[128];memcpy(original,code,sizeof(code));
 missing=1;install_model_quality_policy(&module);
 assert(!model_quality_policy_installed && !memcmp(original,code,sizeof(code)));
 missing=0;
 for(unsigned i=0;i<4;i++) {
  code[0xd4/4+i]^=1;
  uint32_t damaged[128];memcpy(damaged,code,sizeof(code));
  install_model_quality_policy(&module);assert(!model_quality_policy_installed);
  assert(!memcmp(damaged,code,sizeof(code)));
  memcpy(code,original,sizeof(code));
 }
 native_control=1;
#ifdef NEAR_CAMERA_TRACE
 install_model_quality_policy(&module);
 assert(!model_quality_policy_installed && !memcmp(original,code,sizeof(code)));
 native_control=0;
#endif
 install_model_quality_policy(&module);assert(model_quality_policy_installed);
 assert(code[0xd4/4]==0x97e4ec7b);
 original[0xd4/4]=0x97e4ec7b;
 assert(!memcmp(original,code,sizeof(code))); /* Exactly one word changed. */
 const unsigned before=notes;install_model_quality_policy(&module);assert(notes==before);
}
''')


def test_native_branch_and_all_quality_paths():
    from test_referee_native_contract import RefereeNativeContractTests as Native
    Native.setUpClass()
    try:
        base = Native.symbols['_ZN13UEPlayerModel8LoadImplEv'][0]
        expected = SOURCE.split('expected[4] = {', 1)[1].split('};', 1)[0]
        words = [int(x, 16) for x in re.findall(r'0x[0-9a-f]+', expected)]
        assert Native.read(base+0xd4, 16) == struct.pack('<4I', *words)
        def branch(word, site):
            imm = word & 0x3ffffff
            if imm & 0x2000000:
                imm -= 0x4000000
            return site + 4*imm
        old = branch(words[0], base+0xd4)
        new = branch(0x97e4ec7b, base+0xd4)
        assert old == Native.plts['_ZN16APlayerActorHigh21GetPrivateStaticClassEv']
        assert new == Native.plts['_ZN15APlayerActorLow21GetPrivateStaticClassEv']
        assert branch(Native.word(base+0xb0), base+0xb0) == new
        # Execute the actual bounded AArch64 chooser with its native quality
        # calls stubbed. This verifies the selected class for every legal mode.
        unicorn = pytest.importorskip('unicorn')
        from unicorn.arm64_const import UC_ARM64_REG_W0, UC_ARM64_REG_PC, UC_ARM64_REG_LR
        for patched in (False, True):
            for quality in (0, 1, 2, 3):
                uc = unicorn.Uc(unicorn.UC_ARCH_ARM64, unicorn.UC_MODE_ARM)
                uc.mem_map(base & ~0xfff, 0x2000)
                uc.mem_write(base+0xa4, Native.read(base+0xa4, 0x28))
                uc.mem_write(base+0xd4, struct.pack('<I', 0x97e4ec7b if patched else words[0]))
                selected = []
                # Intercept external factories and quality getter before any
                # mapped execution; no game code is run on the host.
                for symbol in ('_ZN8UESystem3Env10GetQualityEv',
                               '_ZN15APlayerActorLow21GetPrivateStaticClassEv',
                               '_ZN18APlayerActorLowest21GetPrivateStaticClassEv',
                               '_ZN16APlayerActorHigh21GetPrivateStaticClassEv'):
                    page = Native.plts[symbol] & ~0xfff
                    try: uc.mem_map(page, 0x1000)
                    except unicorn.UcError: pass
                factories = {Native.plts['_ZN15APlayerActorLow21GetPrivateStaticClassEv']:'standard',
                             Native.plts['_ZN18APlayerActorLowest21GetPrivateStaticClassEv']:'low',
                             old:'high'}
                def observe(emu, address, size, user):
                    if address == Native.plts['_ZN8UESystem3Env10GetQualityEv']:
                        emu.reg_write(UC_ARM64_REG_W0, quality)
                        emu.reg_write(UC_ARM64_REG_PC, emu.reg_read(UC_ARM64_REG_LR))
                    elif address in factories:
                        selected.append(factories[address]);emu.emu_stop()
                uc.hook_add(unicorn.UC_HOOK_CODE, observe)
                # Include the complete original conditional sequence.
                uc.mem_write(base+0xa4, Native.read(base+0xa4, 0x38))
                if patched: uc.mem_write(base+0xd4, struct.pack('<I', 0x97e4ec7b))
                uc.emu_start(base+0xa4, base+0xdc, count=30)
                assert selected == [('low' if quality in (0,3) else
                                     'standard' if quality==1 or patched else 'high')]
    finally:
        Native.tearDownClass()
