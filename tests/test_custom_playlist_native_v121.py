"""Execute native ownership with the audited CRI mute/volume semantics."""
from pathlib import Path

from test_custom_playlist_native_v120 import run_c

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include <assert.h>
#include <stdint.h>
#include <math.h>
#include <string.h>
#include "custom_playlist.h"
static int ready,menu,audible,muted,fail_mute,registered=1,enabled=1;
static uint32_t revision=1;
static unsigned mute_calls,read_calls,volume_calls,acf_calls,notes;
static uint32_t input_warnings;
static float level=.5f,gain;
void custom_playlist_publish(int active,uint64_t now){(void)now;menu=active;}
int custom_playlist_ready(void){return ready;}
int custom_playlist_enabled(void){return enabled;}
uint32_t custom_playlist_revision(void){return revision;}
uint32_t custom_playlist_input_warnings(void){return input_warnings;}
void custom_playlist_set_audible(int active,float value){
 if(active)assert(muted && menu && ready && enabled && registered);
 audible=active;gain=value;
}
static int acf_registered(int notify){assert(!notify);++acf_calls;return registered;}
static void mute(const char *name,int value){
 assert(registered && !strcmp(name,"OptVol_Menu_Music"));
 ++mute_calls;if(!fail_mute)muted=value;
}
static int is_muted(const char *name){
 assert(registered && !strcmp(name,"OptVol_Menu_Music"));++read_calls;return muted;
}
static float volume(const char *name){
 assert(registered);++volume_calls;
 if(!strcmp(name,"OptVol_Menu_Music"))return muted ? .00001525f : level;
 assert(!strcmp(name,"DefVol_Menu_Music"));return .8f;
}
static void scene_runtime_note(const char *tag,const char *reason){
 assert((!strcmp(tag,"custom playlist fallback") || !strcmp(tag,"custom playlist input")) && reason && *reason);++notes;
}
'''


def run_adapter(tmp_path, body):
    adapter = (ROOT / 'source/custom_playlist_native.inc').read_text().split(
        'static void custom_playlist_native_install')[0]
    run_c(tmp_path, HARNESS + adapter + r'''
int main(void){
 playlist_native_acf_registered=acf_registered;
 playlist_native_mute=mute;
 playlist_native_is_muted=is_muted;
 playlist_native_volume=volume;
''' + body + '\nreturn 0;\n}\n')


def test_steady_playback_is_bounded_even_with_many_pad_callbacks(tmp_path):
    run_adapter(tmp_path, r'''
 ready=1;custom_playlist_native_tick(1,1000);
 assert(audible && muted && fabsf(gain-.4f)<.0001f);
 unsigned initial_reads=read_calls,initial_acf=acf_calls;
 for(uint64_t stamp=1000;stamp<2000;++stamp)
  for(unsigned pad=0;pad<8;++pad)custom_playlist_native_tick(1,stamp);
 assert(mute_calls==1 && volume_calls==2 && read_calls==initial_reads+1);
 assert(acf_calls==initial_acf+1 && fabsf(gain-.4f)<.0001f && !notes);
''')


def test_missing_acf_never_enters_native_category_api(tmp_path):
    run_adapter(tmp_path, r'''
 ready=1;registered=0;
 for(uint64_t stamp=1000;stamp<2000;++stamp)custom_playlist_native_tick(1,stamp);
 assert(!audible && !muted && !mute_calls && !read_calls && !volume_calls);
 assert(acf_calls==2 && !notes);
 registered=1;custom_playlist_native_tick(1,2000);
 assert(audible && muted && fabsf(gain-.4f)<.0001f);
 /* ACF teardown invalidates the lease, without touching retired categories. */
 registered=0;muted=0;custom_playlist_native_tick(1,2500);
 assert(!audible && !playlist_native_owned && mute_calls==1);
 registered=1;custom_playlist_native_tick(1,3000);assert(audible && muted);
''')


def test_short_underflow_holds_mute_long_underflow_restores_once(tmp_path):
    run_adapter(tmp_path, r'''
 ready=1;custom_playlist_native_tick(1,1000);assert(mute_calls==1);
 ready=0;custom_playlist_native_tick(1,1100);
 custom_playlist_native_tick(1,1800);assert(muted && !audible && mute_calls==1);
 ready=1;custom_playlist_native_tick(1,1801);assert(audible && muted && mute_calls==1);
 ready=0;custom_playlist_native_tick(1,1900);
 custom_playlist_native_tick(1,2649);assert(muted && !notes);
 custom_playlist_native_tick(1,2650);assert(!muted && !audible && notes==1);
 assert(mute_calls==2 && playlist_native_failed);
 ready=1;for(uint64_t stamp=2651;stamp<8000;++stamp)custom_playlist_native_tick(1,stamp);
 assert(!muted && !audible && mute_calls==2 && notes==1);
 enabled=0;++revision;custom_playlist_native_tick(1,8000);
 enabled=1;++revision;custom_playlist_native_tick(1,8001);
 assert(muted && audible && !playlist_native_failed);
''')


def test_rejected_mute_does_not_retry_on_every_frame_or_menu_entry(tmp_path):
    run_adapter(tmp_path, r'''
 ready=1;fail_mute=1;custom_playlist_native_tick(1,1000);
 assert(!audible && !muted && mute_calls==1 && notes==1);
 for(uint64_t stamp=1001;stamp<20000;++stamp)custom_playlist_native_tick(1,stamp);
 custom_playlist_native_tick(0,20000);custom_playlist_native_tick(1,20001);
 assert(mute_calls==1 && notes==1);
 fail_mute=0;enabled=0;++revision;custom_playlist_native_tick(1,20002);
 enabled=1;++revision;custom_playlist_native_tick(1,20003);
 assert(audible && muted && mute_calls==2);
''')


def test_native_override_cannot_create_an_unbounded_mute_fight(tmp_path):
    run_adapter(tmp_path, r'''
 ready=1;custom_playlist_native_tick(1,1000);
 muted=0;custom_playlist_native_tick(1,1500);assert(muted && mute_calls==2);
 muted=0;custom_playlist_native_tick(1,2000);assert(muted && mute_calls==3);
 muted=0;custom_playlist_native_tick(1,2500);
 assert(!audible && !muted && playlist_native_failed && mute_calls==3 && notes==1);
 for(uint64_t stamp=2501;stamp<10000;++stamp)custom_playlist_native_tick(1,stamp);
 assert(mute_calls==3 && notes==1);
''')


def test_normal_menu_match_cycles_are_not_counted_as_native_overrides(tmp_path):
    run_adapter(tmp_path, r'''
 ready=1;
 for(uint64_t cycle=0;cycle<20;++cycle){
  custom_playlist_native_tick(1,1000+cycle*2000);assert(muted && audible);
  custom_playlist_native_tick(0,1001+cycle*2000);assert(!muted && !audible);
 }
 assert(mute_calls==40 && !notes && !playlist_native_failed);
 /* OFF releases immediately, even inside the 750 ms starvation grace. */
 custom_playlist_native_tick(1,50000);ready=0;custom_playlist_native_tick(1,50001);
 enabled=0;++revision;custom_playlist_native_tick(1,50002);
 assert(!muted && !audible && !playlist_native_owned);
''')


def test_install_rejects_missing_or_changed_native_abi_without_fatal_lookup(tmp_path):
    adapter = (ROOT / 'source/custom_playlist_native.inc').read_text()
    run_c(tmp_path, HARNESS + r'''
typedef struct {void *load_base;} so_module;
static unsigned symbol_index,backing_lookups;
static int missing_at=-1,corrupt_at=-1;
static const uint32_t rvas[]={0x750f854,0x750cbfc,0x750cc4c,0x750c4a4};
static const uint64_t hashes[]={UINT64_C(0x077e2ca84ca368ef),UINT64_C(0x08af5c32184f8165),
 UINT64_C(0xc3163b9e72ec8220),UINT64_C(0xc7c7a9da2ced689d)};
static uintptr_t so_try_find_addr_rx(so_module *module,const char *name){
 (void)module;assert(name && *name);
 void *methods[]={(void*)acf_registered,(void*)mute,(void*)is_muted,(void*)volume};
 unsigned i=symbol_index++;assert(i<4);return (int)i==missing_at?0:(uintptr_t)methods[i];
}
static uintptr_t so_find_addr(so_module *module,const char *name){
 (void)name;unsigned i=symbol_index-1;assert((int)i!=missing_at);++backing_lookups;
 return (uintptr_t)module->load_base+rvas[i];
}
static uint64_t trophy_audio_hash(const void *data,uint32_t bytes){
 (void)data;assert(bytes>0);unsigned i=symbol_index-1;
 return (int)i==corrupt_at?0:hashes[i];
}
''' + adapter + r'''
int main(void){
 so_module module={(void*)(uintptr_t)0x10000000};
 for(int i=0;i<4;++i){
  missing_at=i;symbol_index=backing_lookups=0;custom_playlist_native_install(&module);
  assert(!playlist_native_mute && backing_lookups==(unsigned)i);
 }
 missing_at=-1;
 for(int i=0;i<4;++i){
  corrupt_at=i;symbol_index=0;custom_playlist_native_install(&module);
  assert(!playlist_native_mute);
 }
 corrupt_at=-1;symbol_index=0;custom_playlist_native_install(&module);
 assert(playlist_native_acf_registered==acf_registered && playlist_native_mute==mute);
 ready=1;custom_playlist_native_tick(1,1000);assert(muted && audible);
 return 0;
}
''')
