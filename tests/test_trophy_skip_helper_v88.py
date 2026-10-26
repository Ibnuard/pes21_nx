"""Native footer ownership and profile-correct Cup Skip helper regression."""
from pathlib import Path
import hashlib
import re
import shutil
import struct
import subprocess

import pytest
from test_fixdemo_trophy_result import ELF_SHA256
from test_gameplan_editor import function

ROOT = Path(__file__).resolve().parents[1]


def actual(source, name):
    start = re.search(r'(?m)^static (?:uint32_t|u64|int|const char \*)\s*' + name
                      + r'\([^;{]*\)\s*\{', source)
    assert start, name
    return function(source[start.start():], name)


def compile_run(tmp_path, source):
    compiler = shutil.which('gcc') or shutil.which('clang')
    if not compiler:
        pytest.skip('host C compiler required')
    path, exe = tmp_path / 'skip-helper.c', tmp_path / 'skip-helper.exe'
    path.write_text(source, encoding='utf-8')
    built = subprocess.run([compiler, '-std=c11', '-Wall', '-Wextra', '-Werror',
                            str(path), '-o', str(exe)], capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stdout + ran.stderr


def test_live_native_footer_hidden_only_during_ceremony_or_existing_pause(tmp_path):
    hooks = (ROOT / 'source/ue4_hooks.c').read_text(encoding='utf-8')
    source = r'''
#include <stdint.h>
#include <stddef.h>
#include <assert.h>
typedef struct { float alpha; } Node;
typedef struct { Node *surface, *root; unsigned gets; } Window;
static unsigned native_calls, node_writes, pause_active, ceremony;
static void *live_gameplan_window;
static unsigned (*pause_guide_update_original)(void *,unsigned);
static int pes_controller_pause_skin_active(void) { return pause_active; }
static int fixdemo_trophy_ui_active(void) { return ceremony!=0; }
static unsigned native_update(void *p,unsigned pad) {
  assert(p && pad==7); ++native_calls; return 31;
}
static void *get_surface(void *p) { assert(p); Window *w=p; ++w->gets; return w->surface; }
static void *get_root(void *p) { assert(p); Window *w=p; ++w->gets; return w->root; }
static int set_alpha(void *p,float alpha) {
  assert(p); ((Node *)p)->alpha=alpha; ++node_writes; return 0;
}
static void *(*exhibition_window_get_window)(void *)=get_surface;
static void *(*match_setplay_get_root)(void *)=get_root;
static int (*match_node_set_alpha)(void *,float)=set_alpha;
''' + actual(hooks, 'pes_pause_guide_update') + r'''
int main(void) {
  Node surface={1},root={1},other_surface={1},other_root={1};
  Window window={&surface,&root,0}, other={&other_surface,&other_root,0};
  pause_guide_update_original=native_update;
  assert(pes_pause_guide_update(&window,7)==31);
  assert(!node_writes && !window.gets); /* Ordinary cinematics unchanged. */
  for (ceremony=1;ceremony<=2;++ceremony) {
    surface.alpha=root.alpha=1;
    assert(pes_pause_guide_update(&window,7)==31);
    assert(surface.alpha==0 && root.alpha==0);
  }
  assert(!other.gets); /* Never resolve another/stored native window. */
  ceremony=0;
  assert(pes_pause_guide_update(&other,7)==31);
  assert(!other.gets && other_surface.alpha==1 && other_root.alpha==1);
  assert(pes_pause_guide_update(&window,7)==31);
  assert(surface.alpha==1 && root.alpha==1); /* Same live callback restores. */
  unsigned writes=node_writes;
  assert(pes_pause_guide_update(&window,7)==31 && writes==node_writes);
  pause_active=1;
  assert(pes_pause_guide_update(&window,7)==31);
  assert(surface.alpha==0 && root.alpha==1); /* Existing Pause policy intact. */
  pause_active=0;
  assert(pes_pause_guide_update(&window,7)==31);
  assert(surface.alpha==1 && root.alpha==1);
  ceremony=1; window.surface=window.root=NULL;
  assert(pes_pause_guide_update(&window,7)==31); /* Deferred nodes are safe. */
  ceremony=0; window.surface=&surface; window.root=&root;
  assert(pes_pause_guide_update(&window,7)==31);
  assert(surface.alpha==1 && root.alpha==1 && native_calls==10);
  return 0;
}
'''
    compile_run(tmp_path, source)


def test_helper_uses_playing_token_and_real_profile_aliases(tmp_path):
    overlay = (ROOT / 'source/overlay.c').read_text(encoding='utf-8')
    shim = (ROOT / 'source/android_shim.c').read_text(encoding='utf-8')
    source = r'''
#include <stdint.h>
#include <string.h>
#include <assert.h>
typedef uint64_t u64;
typedef enum { CONTROLLER_PROFILE_FULL, CONTROLLER_PROFILE_SINGLE_LEFT,
               CONTROLLER_PROFILE_SINGLE_RIGHT } ControllerProfile;
#define PES_CONTROLLER_PROFILE_FULL CONTROLLER_PROFILE_FULL
#define PES_CONTROLLER_PROFILE_SINGLE_LEFT CONTROLLER_PROFILE_SINGLE_LEFT
#define PES_CONTROLLER_PROFILE_SINGLE_RIGHT CONTROLLER_PROFILE_SINGLE_RIGHT
enum { PES_CEREMONY_INPUT_NONE, PES_CEREMONY_INPUT_LOADING, PES_CEREMONY_INPUT_PLAYING };
enum { HidNpadButton_A=1, HidNpadButton_B=2, HidNpadButton_X=4,
       HidNpadButton_Y=8, HidNpadButton_Left=16, HidNpadButton_Right=32,
       HidNpadButton_Up=64, HidNpadButton_Down=128 };
''' + actual(overlay, 'overlay_cinematic_helper_active') + actual(
        overlay, 'overlay_cinematic_skip_key') + actual(
        shim, 'controller_profile_map_buttons') + r'''
int main(void) {
  for (int transition=0;transition<2;++transition) {
    assert(overlay_cinematic_helper_active(PES_CEREMONY_INPUT_PLAYING,
             transition,0,0,1)==!transition);
    assert(!overlay_cinematic_helper_active(PES_CEREMONY_INPUT_LOADING,
             transition,1,1,0)); /* Even stale GoalDemo cannot leak at load. */
  }
  assert(!overlay_cinematic_helper_active(PES_CEREMONY_INPUT_NONE,0,0,1,0));
  assert(!overlay_cinematic_helper_active(PES_CEREMONY_INPUT_NONE,0,1,1,1));
  assert(overlay_cinematic_helper_active(PES_CEREMONY_INPUT_NONE,0,1,1,0));
  assert(!overlay_cinematic_helper_active(PES_CEREMONY_INPUT_NONE,0,1,0,0));
  const char *keys[]={"B","LEFT","A"};
  const u64 physical[]={HidNpadButton_B,HidNpadButton_Left,HidNpadButton_A};
  for (unsigned profile=0;profile<3;++profile) {
    assert(!strcmp(overlay_cinematic_skip_key(profile),keys[profile]));
    assert(controller_profile_map_buttons(physical[profile],(ControllerProfile)profile)
           ==HidNpadButton_B); /* Actual v85 logical face-button Skip input. */
  }
  return 0;
}
'''
    compile_run(tmp_path, source)


def test_optional_native_next_footer_is_independent_guibar_window():
    path = ROOT / 'dist/pes21_nx/libUE4.so'
    if not path.is_file():
        pytest.skip('compatible ignored libUE4.so required for footer owner proof')
    module = pytest.importorskip('elftools.elf.elffile')
    contracts = {
        '_ZN10menusystem13WindowManager12FooterUpdateEPNS_6WindowE':
            (0x6A09EBC, 0x1E4, '52ebbd62618fd7aef92baac4dbf2538931a60abe7683bdf8eaae5bf52f1f2218'),
        '_ZN10menusystem8GuideBar8SetupSwfEv':
            (0x69BFF08, 0x224, '2587aa63a40941c100b62a7f9b50eb528c7cfadcead6e072230c88dd867fdba8'),
        '_ZN10menusystem8GuideBar10UpdateDispEv':
            (0x69C02A0, 0x390, '72f91c374ade104f365e1051e3785811d605ffdaacf194591af8d9b14332eb87'),
        '_ZN10menusystem12GuiBarWindow23UpdatePostControlWindowENS_6Window10PAD_STATUSE':
            (0x69C1DB4, 8, '2b59db05426e0f313d72b30f3398c65721de2562a59dc46ceeba224f98d0b876'),
    }
    with path.open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == ELF_SHA256
        stream.seek(0)
        elf = module.ELFFile(stream)
        assert elf.elfclass == 64 and elf.little_endian and elf['e_machine'] == 'EM_AARCH64'
        symtab = elf.get_section_by_name('.dynsym')
        strings = elf.get_section(symtab['sh_link']).data()
        rows = list(struct.iter_unpack('<IBBHQQ', symtab.data()))

        def symbol_name(index):
            offset = rows[index][0]
            return strings[offset:strings.find(b'\0', offset)].decode('ascii', errors='replace')

        selected = {symbol_name(i): (row[4], row[5]) for i, row in enumerate(rows)
                    if row[3] and row[4] and symbol_name(i) in contracts}

        def read(address, size):
            offsets = list(elf.address_offsets(address, size))
            assert len(offsets) == 1
            stream.seek(offsets[0])
            return stream.read(size)

        for name, (address, size, digest) in contracts.items():
            assert selected[name] == (address, size)
            assert hashlib.sha256(read(address, size)).hexdigest() == digest
        assert read(0x81E237E, 13) == b'GuiBarWindow\0'
        assert read(0x81E23BF, 10) == b'cmnFooter\0'
        plt, relocs = elf.get_section_by_name('.plt'), elf.get_section_by_name('.rela.plt')
        calls = {plt['sh_addr'] + 32 + i * 16: symbol_name(row[1] >> 32)
                 for i, row in enumerate(struct.iter_unpack('<QQq', relocs.data()))}

        def callee(address):
            word = struct.unpack('<I', read(address, 4))[0]
            assert word & 0xFC000000 == 0x94000000
            immediate = word & 0x3FFFFFF
            if immediate & 0x2000000:
                immediate -= 0x4000000
            return calls[address + 4 * immediate]

        assert callee(0x6A09FDC) == '_ZN10menusystem8GuideBar12SetKeyStringENS_12WindowPadKey7PAD_KEYEPKc'
        assert callee(0x69C03B0) == '_ZN10menusystem12GuiBarWindow7SetTextENS_8GuideBar12BUTTON_INDEXEPKc'
        assert callee(0x69BFF84) == '_ZN10menusystem6Window11RegisterSwfEPKcb'
