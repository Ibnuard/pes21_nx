"""Cloud-only lifecycle installation must not depend on optional field PAKs."""
from pathlib import Path
import shutil

import pytest
from test_result_flow import build_and_run

ROOT=Path(__file__).resolve().parents[1]


def test_install_without_precipitation_package_retains_native_guards():
    compiler=shutil.which('gcc')
    if not compiler:
        pytest.skip('Host C compiler unavailable')
    scene=(ROOT/'source/weather_scene.inc').read_text()
    build_and_run(compiler,r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
static unsigned weather_scene_kind;
static int pes_controller_pause_skin_active(void){return 0;}
static int pes_controller_pause_transition(void){return 0;}
static int pes_controller_match_hud_inplay(void){return 0;}
static void scene_runtime_note(const char *a,const char *b){(void)a;(void)b;}
#define PESNX_WEATHER_SCENE_HOST_TEST
'''+'#include "'+(ROOT/'source/weather_scene.inc').as_posix()+'"\n'+r'''
typedef struct {unsigned char *load_base;} so_module;
static unsigned root_words[20],mesh_words[20],hooks;
static int stadium_canary_installed,referee_probe_enabled;
static uintptr_t so_try_find_addr_rx(so_module*m,const char*s){(void)m;(void)s;return 1;}
static uintptr_t so_find_addr(so_module*m,const char*s){
 (void)m;return (uintptr_t)(strstr(s,"GetRootComponent")?root_words:mesh_words);
}
static void stadium_loaded_canary(void*p){(void)p;}
static void referee_probe_loaded_scene(void*p){(void)p;}
static void referee_probe_unload(void*p){(void)p;}
static void referee_probe_destroy_loader(void*p){(void)p;}
static void hook_arm64(uintptr_t a,uintptr_t b){assert(a&&b);++hooks;}
'''+scene[scene.index('static void install_weather_scene'):scene.rindex('\n#endif')]+r'''
int main(void){
 const uint32_t load[]={0xb002e2f0,0xf9409e11,0x9104e210,0xd61f0220};
 const uint32_t unload[]={0xf002e270,0xf945c211,0x912e0210,0xd61f0220};
 const uint32_t destroy[]={0xd002e2b0,0xf9465611,0x9132a210,0xd61f0220};
 const uint32_t tick[]={0x9002e170,0xf9425211,0x91128210,0xd61f0220};
 so_module module={calloc(0x3924490+16,1)};assert(module.load_base);
 memcpy(module.load_base+0x38c3dc0,load,16);memcpy(module.load_base+0x38dd250,unload,16);
 memcpy(module.load_base+0x38cf4a0,destroy,16);memcpy(module.load_base+0x3924490,tick,16);
 root_words[4]=0xf940ac08;mesh_words[10]=0xf942d808;
 // Runs in the fixture's empty directory: no weather PAK is present.
 install_weather_scene(&module);assert(hooks==4);
 hooks=0;module.load_base[0x3924490]^=1;
 install_weather_scene(&module);assert(hooks==0); // Unknown runtime still refuses hooks.
 free(module.load_base);
}
''')
