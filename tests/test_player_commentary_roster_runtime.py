"""Actual v59 game-thread glue + reload/lookup/builder/archive/mount seams.

All UTF/HCA/catalog fixtures are synthetic. The public empty catalog is
overridden through its include guard in a temporary test TU; production files
and proprietary inputs are never changed. Native executable RVAs are reduced
only in this host harness so guard tests need no 110-MiB fake code allocation.
"""
from pathlib import Path
import shutil
import struct
import subprocess

import pytest

from test_gameplan_editor import function
from test_player_commentary_bank_builder import fixture as bank_fixture, archive
from build_player_commentary_roster_pack import c_header
from stage_indonesia_commentary import fnv64

ROOT = Path(__file__).resolve().parents[1]
PAIR = "e861c583ec78e9ae"


def compile_run(tmp_path, body, *, marker=True, corrupt_patch=False):
    cc = shutil.which("gcc") or shutil.which("clang")
    if not cc:
        pytest.skip("host C compiler required for actual roster runtime")
    base, catalog, assets = bank_fixture()
    catalog["runtime_pair"] = PAIR
    # Native voice in the last substitute slot; it must survive full capture.
    catalog["owners"].insert(1, dict(base_id=444, native_player_id=100039,
        fingerprint="a"*20, active_row_sha256="b"*64, status=1,
        cue_first=2, cue_count=0))
    patch = struct.pack("<8sIIQQIIII", b"NXCMT01\0", len(base), len(base),
                        fnv64(base), fnv64(base), 1, 0, 0, len(base)) + base
    patch_hash = fnv64(patch)
    if corrupt_patch:
        patch = patch[:-1] + bytes([patch[-1] ^ 1])
    folder = tmp_path / "Commentary"
    folder.mkdir()
    (tmp_path / "base.acb").write_bytes(base)
    if marker:
        assets["catalog-id.txt"] = (PAIR+"\n").encode()
    assets = {"commentary/players-v59/" + name: data for name, data in assets.items()}
    assets["commentary/players-v53.nxcp"] = patch
    archive(tmp_path / "FootballNX.assets", assets)
    (tmp_path / "fixture_catalog.h").write_text(c_header(catalog), encoding="utf-8")
    hooks = (ROOT / "source/ue4_hooks.c").read_text(encoding="utf-8")
    first = hooks.index("typedef struct {\n  const PcBankCatalog *catalog;")
    last = hooks.index("/* The native HCA codec", first)
    actual_mount_metadata = hooks[first:last]
    actual_mount = function(hooks, "pes_sound_mount_data")
    actual_unmount = function(hooks, "pes_sound_unmount_data")
    prefix = r'''
#ifndef _WIN32
#define _GNU_SOURCE
#endif
#include <assert.h>
#include <stdarg.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <sys/mman.h>
#endif
#include "player_commentary_policy.h"
#include "player_commentary_lookup.h"
#include "fixture_catalog.h"
#undef PC_LOOKUP_TYPED_RVA
#undef PC_LOOKUP_TYPED_PLT_RVA
#define PC_LOOKUP_TYPED_RVA 0x100u
#define PC_LOOKUP_TYPED_PLT_RVA 0x200u
#undef PLAYER_COMMENTARY_BASE_BYTES
#undef PLAYER_COMMENTARY_RESULT_BYTES
#undef PLAYER_COMMENTARY_PATCH_BYTES
#undef PLAYER_COMMENTARY_BASE_FNV
#undef PLAYER_COMMENTARY_RESULT_FNV
#undef PLAYER_COMMENTARY_PATCH_FNV
#define PLAYER_COMMENTARY_BASE_BYTES BASE_BYTESu
#define PLAYER_COMMENTARY_RESULT_BYTES BASE_BYTESu
#define PLAYER_COMMENTARY_PATCH_BYTES PATCH_BYTESu
#define PLAYER_COMMENTARY_BASE_FNV UINT64_C(0xVALUE_BASE_FNV)
#define PLAYER_COMMENTARY_RESULT_FNV UINT64_C(0xVALUE_BASE_FNV)
#define PLAYER_COMMENTARY_PATCH_FNV UINT64_C(0xVALUE_PATCH_FNV)
typedef struct { uintptr_t load_base,load_virtbase;size_t load_size; } so_module;
static uintptr_t so_try_find_addr_rx(so_module *,const char *);
/* The old installer must still compile when the regression is checked against
 * it; its RX opcode reads then hit the genuinely inaccessible alias page. */
#define so_find_addr_rx so_try_find_addr_rx
static void hook_arm64(uintptr_t,uintptr_t);
static void debugPrintf(const char *format,...) {(void)format;}
static unsigned notes;
static void scene_runtime_note(const char *category,const char *message) {
  assert(category && message);notes++;
}
enum { MAIN_MENU_2P_TRANSITION_NONE,MAIN_MENU_2P_TRANSITION_LOADING,MAIN_MENU_2P_TRANSITION_VS };
static uint32_t main_menu_2p_team_selector_active,main_menu_2p_prematch_hub_active=1;
static uint32_t main_menu_2p_prematch_hub_input_pending,main_menu_2p_transition_active;
static uint32_t main_menu_2p_transition_kind,main_menu_2p_prematch_hub_input_armed[2]={1,1};
static uint32_t team_commentary_indonesia_slot,player_commentary_enabled=1;
static uint32_t exhibition_session_active=1,native_gamepad_lab_active=1;
static unsigned char match_storage[0x14000],teams[2][0x500],module_code[0x400];
static uintptr_t runtime_base;
static uint32_t logical_teams[2]={108,100};
static uint32_t bad_record,bad_team,missing_match,scope_bad;
static uint64_t now_ms;
static void *exhibition_get_tmpdb_match(void) {return missing_match?NULL:match_storage;}
static uint32_t prematch_gameplan_team_id(uint32_t side) {return logical_teams[side];}
static uint32_t exhibition_native_team_id(uint32_t id) {return id+1000u;}
static const char *prematch_gameplan_identity_scope(void) {
  return scope_bad?"e861c583ec78e9af":"e861c583ec78e9ae";
}
static uint64_t exhibition_search_focus_now_ms(void) {return now_ms;}
static void *get_team(void *match,const uint32_t *side) {
  assert(match==match_storage && *side<2);return bad_team?NULL:teams[*side];
}
static const void *get_player(const void *match,const uint32_t *side,const uint32_t *index) {
  assert(match==match_storage && *side<2 && *index<40);
  return match_storage+0x1248u+*side*0x8c00u+*index*0x380u+(bad_record?1u:0u);
}
static void *(*exhibition_tmpdb_match_get_team)(void *,const uint32_t *)=get_team;
static const void *(*match_tmpdb_match_get_player)(const void *,const uint32_t *,const uint32_t *)=get_player;
static int32_t (*sound_mount_data_original)(void *,uint32_t,void *,const char *,uint16_t,uint16_t,int16_t *);
static int32_t (*sound_unmount_data_original)(int16_t);
'''
    prefix = (prefix.replace("BASE_BYTESu", f"{len(base)}u")
        .replace("PATCH_BYTESu", f"{len(patch)}u")
        .replace("VALUE_BASE_FNV", f"{fnv64(base):016x}")
        .replace("VALUE_PATCH_FNV", f"{patch_hash:016x}"))
    source = prefix + actual_mount_metadata + actual_mount + actual_unmount
    source += '\n#include "player_commentary_roster_runtime.inc"\n' + FIXTURE + body
    (tmp_path / "roster.c").write_text(source, encoding="utf-8")
    compiled = subprocess.run([cc, "-std=c11", "-O1", "-Wall", "-Wextra", "-Werror",
        "-I", str(tmp_path), "-I", str(ROOT / "source"), str(tmp_path / "roster.c"),
        "-o", str(tmp_path / "roster.exe")], capture_output=True, text=True, timeout=60)
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    ran = subprocess.run([str(tmp_path / "roster.exe")], cwd=tmp_path,
                          capture_output=True, text=True, timeout=30)
    assert ran.returncode == 0, ran.stdout + ran.stderr


FIXTURE = r'''
#define request_code ((uint32_t *)(void *)(module_code+0x300u))
#define busy_code ((uint32_t *)(void *)(module_code+0x320u))
#define mount_code ((uint32_t *)(void *)(module_code+0x340u))
static int missing_request,symbol_range_fault,hooked,native_requests,native_busy_value,native_mount_calls;
static int typed_calls,native_patch_calls,native_original_calls,fail_patch_mount,fail_unmount;
static int16_t native_id=-1,next_id=40;
static unsigned char *native_base;
static uintptr_t so_try_find_addr_rx(so_module *module,const char *name) {
  assert(module && name);
  if(!strcmp(name,"_ZN5sound3sys4Load7RequestE13SD_LOAD_LABEL")) {
    if(missing_request)return 0;
    if(symbol_range_fault==1)return module->load_virtbase-1u;
    if(symbol_range_fault==2)return module->load_virtbase+module->load_size-8u;
    if(symbol_range_fault==3)return module->load_virtbase+module->load_size;
    return module->load_virtbase+0x300u;
  }
  if(!strcmp(name,"_ZN5sound3sys4Load6IsBusyE13SD_LOAD_LABEL"))return module->load_virtbase+0x320u;
  if(!strcmp(name,"_ZN5sound3sys4load7Manager10GetMountIDEjPs"))return module->load_virtbase+0x340u;
  assert(0);return 0;
}
static void hook_arm64(uintptr_t where,uintptr_t target) {
  assert(where==(uintptr_t)module_code+PC_LOOKUP_TYPED_PLT_RVA);
  assert(target==(uintptr_t)&pes_sound_player_name_label);hooked++;
}
static inline uint64_t carrier_at(unsigned side,unsigned index) {
  uint64_t carrier;memcpy(&carrier,match_storage+0x1248u+side*0x8c00u+index*0x380u+44u,8);
  return carrier;
}
static void set_carrier(unsigned side,unsigned index,uint64_t carrier) {
  memcpy(match_storage+0x1248u+side*0x8c00u+index*0x380u+44u,&carrier,8);
  memcpy(teams[side]+0x110u+index*8u,&carrier,8);
}
static void environment(void) {
#ifdef _WIN32
  runtime_base=(uintptr_t)VirtualAlloc(NULL,4096,MEM_RESERVE|MEM_COMMIT,PAGE_NOACCESS);
  assert(runtime_base);
#else
  void *reserved=mmap(NULL,4096,PROT_NONE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
  assert(reserved!=MAP_FAILED);runtime_base=(uintptr_t)reserved;
#endif
  const uint32_t rg[4]=PC_RELOAD_REQUEST_GUARD,bg[4]=PC_RELOAD_BUSY_GUARD,mg[4]=PC_RELOAD_MOUNT_ID_GUARD;
  const uint32_t tg[4]={0xf81c0ff8,0xa9015bf7,0xa90253f5,0xa9037bf3};
  const uint32_t pg[4]={0xd002e4d0,0xf9401e11,0x9100e210,0xd61f0220};
  memcpy(request_code,rg,16);memcpy(busy_code,bg,16);memcpy(mount_code,mg,16);
  memcpy(module_code+PC_LOOKUP_TYPED_RVA,tg,16);memcpy(module_code+PC_LOOKUP_TYPED_PLT_RVA,pg,16);
  for(unsigned side=0;side<2;side++) {
    uint32_t flags=40u<<9;memcpy(teams[side]+0x3a6u,&flags,4);
    for(unsigned i=0;i<40;i++) {
      uint32_t id=side?200000u+i:100000u+i;
      if(side && i==0)id=300000;
      if(side && i==1)id=200000;
      set_carrier(side,i,((uint64_t)id<<32)|((uint64_t)side<<24)|0xab0000u|i);
    }
  }
  FILE *f=fopen("base.acb","rb");assert(f);native_base=malloc(PLAYER_COMMENTARY_BASE_BYTES);assert(native_base);
  assert(fread(native_base,1,PLAYER_COMMENTARY_BASE_BYTES,f)==PLAYER_COMMENTARY_BASE_BYTES);fclose(f);
  (void)player_commentary_roster_tick;(void)player_commentary_roster_invalidate;
  (void)player_commentary_roster_resume_pending;(void)player_commentary_roster_header_mounted;
  (void)pes_sound_mount_data;(void)pes_sound_unmount_data;
}
static int32_t native_mount(void *data,uint32_t bytes,void *binder,const char *path,
    uint16_t flags,uint16_t search,int16_t *id) {
  assert(binder==(void *)9 && flags==3 && search==4 && path && id);native_mount_calls++;
  if(data==native_base) {assert(bytes==PLAYER_COMMENTARY_BASE_BYTES);native_original_calls++;}
  else {
    assert(data!=player_commentary_reload.prepared.data && bytes<=PC_BANK_MAX_BYTES);
    native_patch_calls++;if(fail_patch_mount)return -2;
  }
  *id=native_id=next_id++;return 0;
}
static int32_t native_unmount(int16_t id) {
  if(fail_unmount)return -3;
  if(native_id==id)native_id=-1;
  return 0;
}
static int32_t native_request(uint32_t label) {
  assert(label==4);native_requests++;native_busy_value=1;
  for(unsigned i=0;i<4;i++) if(player_commentary_mounts[i].state==2)
    assert(!pes_sound_unmount_data(player_commentary_mounts[i].id));
  return -99; /* Request return value is deliberately not a mount-success flag. */
}
static uint32_t native_busy(uint32_t label) {assert(label==4);return (uint32_t)native_busy_value;}
static int32_t native_mount_id(uint32_t kind,int16_t *id) {assert(kind==29 && id);*id=native_id;return 0;}
static const char *native_typed(const void *accessor,const uint32_t *side,
    const uint64_t *carrier,uint32_t type,uint32_t access) {
  (void)accessor;(void)side;(void)carrier;(void)type;(void)access;typed_calls++;return "native-label";
}
static inline void install(void) {
  so_module module={(uintptr_t)module_code,runtime_base,sizeof(module_code)};
  player_commentary_roster_install(&module);
  assert(player_commentary_roster_enabled && hooked==1);
  assert((uintptr_t)player_commentary_native_request==runtime_base+0x300u);
  assert((uintptr_t)player_commentary_native_busy==runtime_base+0x320u);
  assert((uintptr_t)player_commentary_native_mount_id==runtime_base+0x340u);
  assert((uintptr_t)player_commentary_typed_original==runtime_base+PC_LOOKUP_TYPED_RVA);
  player_commentary_native_request=native_request;player_commentary_native_busy=native_busy;
  player_commentary_native_mount_id=native_mount_id;player_commentary_typed_original=native_typed;
  sound_mount_data_original=native_mount;sound_unmount_data_original=native_unmount;
}
static int16_t mount_players(void) {
  int16_t id=-1;
  assert(!pes_sound_mount_data(native_base,PLAYER_COMMENTARY_BASE_BYTES,(void *)9,
      "eng/sound/awb/10_PLAYER.awb",3,4,&id));
  return id;
}
static inline void ready(void) {
  assert(!player_commentary_roster_play_gate());
  assert(native_requests==1 && native_busy_value==1 && !main_menu_2p_prematch_hub_active);
  assert(main_menu_2p_transition_active && main_menu_2p_transition_kind==MAIN_MENU_2P_TRANSITION_LOADING);
  mount_players();native_busy_value=0;now_ms++;
  player_commentary_roster_tick();
  assert(player_commentary_roster_resume_pending() && main_menu_2p_prematch_hub_input_pending==3);
  assert(main_menu_2p_prematch_hub_active && !player_commentary_reload.prepared_live);
}
static inline void cleanup(void) {
  fail_unmount=0;
  for(unsigned i=0;i<4;i++) if(player_commentary_mounts[i].state==2)
    assert(!pes_sound_unmount_data(player_commentary_mounts[i].id));
  free(native_base);
}
'''


def test_capture_preserves_all_substitutes_and_full_native_carriers(tmp_path):
    compile_run(tmp_path, r'''
int main(void) {
  environment();PcSelection selected;assert(player_commentary_capture_selection(&selected));
  assert(selected.side_count[0]==40 && selected.side_count[1]==40 && selected.count==80);
  assert(selected.carriers[0][39]==carrier_at(0,39) && selected.native_ids[0][39]==100039);
  assert(selected.logical_team[0]==108 && selected.physical_team[0]==1108);
  assert(selected.owners[39] && selected.owners[39]->status==PC_OWNER_NATIVE);
  uint64_t copied=selected.carriers[0][39];set_carrier(0,39,copied^0xffffu);
  assert(selected.carriers[0][39]==copied);
  free(native_base);return 0;
}
''')


def test_install_before_code_mapping_reads_backing_and_binds_only_future_rx(tmp_path):
    # environment reserves a PAGE_NOACCESS/PROT_NONE RX alias. An installer
    # reading opcodes through that alias faults; all installed calls must still
    # point there for use AFTER the real loader maps it executable.
    compile_run(tmp_path, r'''
int main(void) {
  environment();install();
  assert(player_commentary_roster_enabled && hooked==1 && !native_requests);
  assert(!player_commentary_reload.prepared_live);
  cleanup();return 0;
}
''')


@pytest.mark.parametrize("fault", range(8))
def test_install_rejects_unmapped_or_out_of_image_symbol_contracts(tmp_path, fault):
    compile_run(tmp_path, r'''
int main(void) {
  environment();so_module module={(uintptr_t)module_code,runtime_base,sizeof(module_code)};
  switch(FAULT) {
    case 0: module.load_base=0;break;
    case 1: module.load_virtbase=0;break;
    case 2: module.load_size=0;break;
    case 3: module.load_size=PC_LOOKUP_TYPED_PLT_RVA+8u;break;
    case 4: symbol_range_fault=1;break;
    case 5: symbol_range_fault=2;break;
    case 6: symbol_range_fault=3;break;
    case 7: player_commentary_roster_install(NULL);free(native_base);return 0;
  }
  player_commentary_roster_install(&module);
  assert(!player_commentary_roster_enabled && !hooked && !native_requests);
  assert(player_commentary_roster_play_gate());
  free(native_base);return 0;
}
'''.replace("FAULT", str(fault)))


@pytest.mark.parametrize("fault", range(8))
def test_capture_rejects_partial_or_incoherent_tmpdb_records(tmp_path, fault):
    compile_run(tmp_path, r'''
int main(void) {
  environment();PcSelection selected;uint32_t flags;
  switch(FAULT) {
    case 0: flags=10u<<9;memcpy(teams[0]+0x3a6u,&flags,4);break;
    case 1: flags=41u<<9;memcpy(teams[1]+0x3a6u,&flags,4);break;
    case 2: bad_record=1;break;
    case 3: bad_team=1;break;
    case 4: missing_match=1;break;
    case 5: teams[1][0x110u]^=1;break;
    case 6: match_tmpdb_match_get_player=NULL;break;
    case 7: scope_bad=1;break;
  }
  assert(!player_commentary_capture_selection(&selected));
  free(native_base);return 0;
}
'''.replace("FAULT", str(fault)))


def test_actual_gate_mount_and_resume_once_keep_fresh_copies_after_prepare_freed(tmp_path):
    compile_run(tmp_path, r'''
int main(void) {
  environment();install();ready();
  assert(player_commentary_active_generation==1 && player_commentary_active_mount==native_id);
  TeamCommentaryMount *slot=player_commentary_mounts;
  assert(slot->data && slot->roster.bank.data==slot->data && slot->roster.lookup.binding_count==4);
  assert(slot->roster.lookup.accepted==PC_LOOKUP_ACCEPTED && slot->roster.lookup.generation==1);
  assert(!memcmp(slot->data,"@UTF",4) && !player_commentary_reload.prepared.data);
  assert(player_commentary_roster_play_gate());
  assert(!player_commentary_roster_resume_pending());
  main_menu_2p_prematch_hub_input_pending=0;main_menu_2p_prematch_hub_active=0;
  for(unsigned i=0;i<20;i++) {now_ms++;player_commentary_roster_tick();}
  assert(native_requests==1 && !main_menu_2p_prematch_hub_input_pending);
  cleanup();return 0;
}
''')


def test_actual_typed_lookup_uses_own_p0_preserves_native_and_never_inherits_unknown(tmp_path):
    compile_run(tmp_path, r'''
int main(void) {
  environment();install();ready();uint32_t side=0;uint64_t carrier=carrier_at(0,0);
  assert(!strcmp(pes_sound_player_name_label(NULL,&side,&carrier,0,0),"EN_A1_P0_R100000"));
  assert(!strcmp(pes_sound_player_name_label(NULL,&side,&carrier,24,0),"EN_B1_P0_R100000"));
  assert(!pes_sound_player_name_label(NULL,&side,&carrier,1,0));
  carrier^=1;assert(!pes_sound_player_name_label(NULL,&side,&carrier,0,0));
  carrier=carrier_at(0,1);assert(!pes_sound_player_name_label(NULL,&side,&carrier,0,0));
  carrier=carrier_at(0,39);assert(!strcmp(pes_sound_player_name_label(NULL,&side,&carrier,0,0),"native-label"));
  side=1;carrier=carrier_at(1,0);assert(!strcmp(pes_sound_player_name_label(NULL,&side,&carrier,0,0),"native-label"));
  carrier=carrier_at(1,1);assert(!pes_sound_player_name_label(NULL,&side,&carrier,0,0));
  assert(typed_calls==2);
  player_commentary_roster_invalidate();
  carrier=carrier_at(1,2);assert(!strcmp(pes_sound_player_name_label(NULL,&side,&carrier,0,0),"native-label"));
  assert(typed_calls==3 && !player_commentary_active_generation);
  cleanup();return 0;
}
''')


def test_header_and_lookup_policy_survive_failed_unmount_then_retire_together(tmp_path):
    compile_run(tmp_path, r'''
int main(void) {
  environment();install();ready();size_t size=0;
  unsigned char *audio=nx_asset_read_archive(PC_ROSTER_ARCHIVE,PC_ROSTER_PREFIX "audio/1.hca",PC_BANK_MAX_AUDIO,&size);
  assert(audio && size>=96);
  for(unsigned split=0;split<=96;split++)assert(player_commentary_roster_header_mounted(audio,split,audio+split,96-split));
  fail_unmount=1;int16_t id=player_commentary_mounts[0].id;
  assert(pes_sound_unmount_data(id)==-3 && player_commentary_mounts[0].state==2);
  assert(player_commentary_roster_header_mounted(audio,96,NULL,0));
  fail_unmount=0;assert(!pes_sound_unmount_data(id));
  assert(!player_commentary_mounts[0].state && !player_commentary_mounts[0].data);
  assert(!player_commentary_mounts[0].roster.lookup.accepted);
  assert(!player_commentary_roster_header_mounted(audio,96,NULL,0));
  uint32_t side=0;uint64_t carrier=carrier_at(0,0);
  assert(!pes_sound_player_name_label(NULL,&side,&carrier,0,0));
  free(audio);cleanup();return 0;
}
''')


@pytest.mark.parametrize("fault", range(6))
def test_dispatch_requires_actual_owned_matching_mount_not_only_native_id(tmp_path, fault):
    compile_run(tmp_path, r'''
int main(void) {
  environment();install();assert(!player_commentary_roster_play_gate());
  mount_players();native_busy_value=0;
  TeamCommentaryMount *slot=player_commentary_mounts;PcBankResult saved_bank=slot->roster.bank;
  switch(FAULT) {
    case 0: slot->state=1;break;
    case 1: slot->roster.generation++;break;
    case 2: slot->roster.lookup.accepted=0;break;
    case 3: slot->roster.lookup.mount_id++;break;
    case 4: slot->roster.bank.data=NULL;break;
    case 5: slot->roster.catalog=NULL;break;
  }
  player_commentary_roster_tick();
  assert(player_commentary_reload.terminal_reason==PC_RELOAD_REASON_DISPATCH_FAILED);
  assert(!player_commentary_active_generation && !player_commentary_roster_resume_pending());
  assert(main_menu_2p_prematch_hub_active && !main_menu_2p_transition_active && !main_menu_2p_prematch_hub_input_pending);
  slot->state=2;slot->roster.bank=saved_bank;cleanup();return 0;
}
'''.replace("FAULT", str(fault)))


def test_failed_native_selected_mount_returns_frontend_without_wrong_name_acceptance(tmp_path):
    compile_run(tmp_path, r'''
int main(void) {
  environment();install();assert(!player_commentary_roster_play_gate());
  fail_patch_mount=1;mount_players();native_busy_value=0;
  assert(native_patch_calls==1 && native_original_calls==1 && !player_commentary_reload.borrowers);
  player_commentary_roster_tick();
  assert(player_commentary_reload.terminal_reason==PC_RELOAD_REASON_MOUNT_FAILED);
  assert(main_menu_2p_prematch_hub_active && !main_menu_2p_transition_active && !player_commentary_active_generation);
  assert(!player_commentary_roster_resume_pending() && !player_commentary_reload.prepared_live);
  cleanup();return 0;
}
''')


def test_corrupt_pinned_seed_releases_loading_without_native_request(tmp_path):
    compile_run(tmp_path, r'''
int main(void) {
  environment();install();assert(!player_commentary_roster_play_gate());
  assert(!native_requests && player_commentary_reload.terminal_reason==PC_RELOAD_REASON_PREPARE_FAILED);
  assert(main_menu_2p_prematch_hub_active && !main_menu_2p_transition_active);
  assert(!main_menu_2p_prematch_hub_input_pending && !player_commentary_reload.prepared_live);
  cleanup();return 0;
}
''', corrupt_patch=True)


def test_timeout_and_invalidation_do_not_leave_loading_or_reopen_old_intent(tmp_path):
    compile_run(tmp_path, r'''
int main(void) {
  environment();install();assert(!player_commentary_roster_play_gate());
  now_ms=30000;player_commentary_roster_tick();
  assert(player_commentary_reload.terminal_reason==PC_RELOAD_REASON_TIMEOUT);
  assert(main_menu_2p_prematch_hub_active && !main_menu_2p_transition_active && !player_commentary_reload.prepared_live);
  native_busy_value=0;now_ms++;player_commentary_roster_tick();
  assert(pc_reload_phase(&player_commentary_reload)==PC_RELOAD_TERMINAL);
  assert(!main_menu_2p_prematch_hub_input_pending && native_requests==1);
  assert(!player_commentary_roster_play_gate());
  main_menu_2p_team_selector_active=1;main_menu_2p_prematch_hub_active=0;
  player_commentary_roster_invalidate();native_busy_value=0;now_ms++;
  player_commentary_roster_tick();
  assert(!main_menu_2p_prematch_hub_active && !main_menu_2p_prematch_hub_input_pending);
  assert(!player_commentary_active_generation && native_requests==2);
  cleanup();return 0;
}
''')


@pytest.mark.parametrize("fault", range(8))
def test_install_opcode_and_identity_guards_leave_v53_available(tmp_path, fault):
    compile_run(tmp_path, r'''
int main(void) {
  environment();so_module module={(uintptr_t)module_code,runtime_base,sizeof(module_code)};
  switch(FAULT) {
    case 0: request_code[2]^=1;break;
    case 1: busy_code[1]^=1;break;
    case 2: mount_code[0]^=1;break;
    case 3: module_code[PC_LOOKUP_TYPED_RVA]^=1;break;
    case 4: module_code[PC_LOOKUP_TYPED_PLT_RVA+8]^=1;break;
    case 5: missing_request=1;break;
    case 6: player_commentary_enabled=0;break;
    case 7: scope_bad=1;break;
  }
  player_commentary_roster_install(&module);
  assert(!player_commentary_roster_enabled && !hooked);
  assert(player_commentary_roster_play_gate()); /* Inactive extension retains original Play. */
  free(native_base);return 0;
}
'''.replace("FAULT", str(fault)))


def test_absent_optional_marker_does_not_install_or_block_existing_play(tmp_path):
    compile_run(tmp_path, r'''
int main(void) {
  environment();so_module module={(uintptr_t)module_code,runtime_base,sizeof(module_code)};
  player_commentary_roster_install(&module);
  assert(!player_commentary_roster_enabled && !hooked && player_commentary_roster_play_gate());
  free(native_base);return 0;
}
''', marker=False)
