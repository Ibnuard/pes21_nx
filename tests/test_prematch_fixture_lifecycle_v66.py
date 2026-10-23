"""Exercise new-fixture initialization on dirty reused native plan/editor owners.

The host model uses the audited Init/setup/load semantics. The optional owned
ELF test separately interprets the native leaf initializers over dirty memory;
neither test claims to execute a complete native match or native menu flow.
"""
from pathlib import Path
import hashlib
import mmap
import os
import shutil
import struct
import subprocess

import pytest

from test_gameplan_editor import function

ROOT = Path(__file__).resolve().parents[1]
HOOKS = (ROOT / "source/ue4_hooks.c").read_text()


def test_dirty_reused_native_owners_reset_once_and_full_record_swaps_still_commit(tmp_path):
    cc = shutil.which("gcc") or shutil.which("clang")
    if not cc:
        pytest.skip("host C compiler required")
    stubs = (ROOT / "tests/prematch_lineup_stubs.inc").read_text()
    cases = (ROOT / "tests/prematch_lineup_cases.inc").read_text()
    stubs = stubs.replace("#include <assert.h>", r'''
#include <assert.h>
#undef assert
#define assert(test) ((test)? (void)0 : (printf("FAIL line %d: %s\n",__LINE__,#test),fflush(stdout),exit(3)))
''')
    source = stubs + "\n" + "\n".join(function(HOOKS, name) for name in (
        "exhibition_matchplan_common_side", "exhibition_prematch_commit_refused",
        "exhibition_sync_prematch_lineup", "exhibition_save_matchplan_sides",
        "master_league_office_lineup_valid", "prematch_gameplan_replace_player",
        "exhibition_prepare_team_conditions"))
    source += "\n" + "\n".join(function(cases, name) for name in (
        "init", "assert_consistent", "do_swap"))
    source += r'''
static uint32_t native_mode=13, native_move_selected=1, fixture_inits, setups, loads;
static uint32_t common_inits, additional_inits, player_inits, cpu, actual_user=42,home_user=999;
static unsigned char parameter[32], common_user[16];
static int master_league_plan_restore_pending;
#define ML_CURRENT_PLAN_SLOT 3
static struct {uint32_t field_count,bench_count;} exhibition_gameplan_sides[2];
static void common_init(void *p) {memset(p,0xff,0x218);common_inits++;}
static void additional_init(void *p) {
 unsigned char *a=p;
 a[0]=a[1]=0xff;a[2]=0;a[3]=6;
 additional_inits++;
}
static void player_init(void *p) {memset(p,0,6);memset((unsigned char *)p+8,0,8);player_inits++;}
static void additional_construct(void *p) {
 unsigned char *a=p;
 for(unsigned i=0;i<6;i++) {
  uint32_t absent=0xff;memcpy(a+4+i*12,&absent,4);memcpy(a+8+i*12,&absent,4);
  memset(a+12+i*12,0,4);
 }
 for(unsigned i=0;i<40;i++)player_init(a+0xb8+i*16);
 additional_init(p);
}
static void begin_mode(uint32_t mode,uint32_t side) {
 assert(mode==11 && side==0);native_mode=mode;my_side=side;native_move_selected=0;
 memset(squads,0,sizeof(squads));fixture_inits++;
}
static void (*exhibition_matchplan_common_init)(void *)=common_init;
static void (*exhibition_matchplan_additional_construct)(void *)=additional_construct;
static void (*exhibition_squad_edit_begin_mode)(uint32_t,uint32_t)=begin_mode;
static void *(*exhibition_matchplan_create_instance)(void)=get_plan;
static uint32_t exhibition_cpu_level_value;
static void setup(void *p) {
 assert(p==plan && native_mode==11 && !native_move_selected);
 unsigned char kept[2][0xb8], flags[2][40][8];
 for(unsigned side=0;side<2;side++) {
  unsigned char *a=plan+0x448+side*0x340;
  memcpy(kept[side],a,0xb8);
  for(unsigned member=0;member<40;member++) {
   const unsigned char *info=a+0xb8+member*16;
   for(unsigned b=0;b<6;b++)assert(!info[b]);
   for(unsigned b=8;b<16;b++)assert(!info[b]);
   memcpy(flags[side][member],info,8);
  }
 }
 /* Populate the selected fixture. Like the native setup, preserve the prior
  * AdditionalData history and eligibility flags while replacing player refs. */
 exhibition_plan_ready=1;init();exhibition_plan_ready=0;
 for(unsigned side=0;side<2;side++) {
  unsigned char *a=plan+0x448+side*0x340;
  memcpy(a,kept[side],0xb8);
  for(unsigned member=0;member<40;member++) {
   memcpy(a+0xb8+member*16,flags[side][member],8);
   if(member<TEST_COUNT)memcpy(original_info[side][member],flags[side][member],8);
  }
 }
 setups++;home_user=999;
}
static void (*exhibition_matchplan_setup_tmpdb)(void *)=setup;
static void native_lab_assign_matchplan_pads(void *p){assert(p==plan);}
static int exhibition_refresh_selected_tmpdb(void){return 1;}
static void exhibition_apply_cpu_level(uint32_t v,void *p){(void)v;assert(!p);cpu++;}
static void exhibition_apply_match_settings(void *p){assert(!p);}
static void exhibition_apply_selected_uniforms(void *p){assert(!p);}
static void *parameter_get(void){return parameter;}
static void *(*exhibition_online_parameter_get_instance)(void)=parameter_get;
static uint32_t get_user(void *p){assert(p==common_user);return actual_user;}
static uint32_t (*exhibition_parameter_common_get_user_id)(void *)=get_user;
static void set_user(void *p,uint32_t side,uint32_t user){assert(p==match_bytes && side==0);home_user=user;}
static void (*exhibition_tmpdb_match_set_user_id)(void *,uint32_t,uint32_t)=set_user;
static uint32_t owner_get(void){return home_user==actual_user?0:2;}
static uint32_t (*exhibition_get_match_my_side)(void)=owner_get;
static int load(void) {
 assert(native_mode==11 && owner_get()==0);
 /* Native Load transfers each saved change slot into newly constructed SquadData. */
 for(unsigned side=0;side<2;side++) {
  const unsigned char *a=plan+0x448+side*0x340;
  assert(a[3]==6);
  for(unsigned i=0;i<6;i++) {
   uint32_t in,out;memcpy(&in,a+4+i*12,4);memcpy(&out,a+8+i*12,4);
   assert(in==0xff && out==0xff && !a[13+i*12]);
  }
 }
 loads++;return 1;
}
static int (*matchplan_squad_load)(void)=load;
static void exhibition_refresh_squad_player_stats(void){assert(loads && native_mode==11);}
static void prematch_gameplan_refresh_side(uint32_t side) {
 exhibition_gameplan_sides[side].field_count=11;exhibition_gameplan_sides[side].bench_count=TEST_COUNT-11;
}
static int ml_frontend_match_active(void){return 0;}
static int prematch_gameplan_load_preset(uint32_t side,uint32_t slot){(void)side;(void)slot;return 1;}
'''
    source += "\n" + "\n".join(function(HOOKS, name) for name in (
        "exhibition_gameplan_init_fixture", "exhibition_gameplan_prepare_matchplan"))
    source += r'''
int main(void) {
 void *user=common_user;memcpy(parameter+8,&user,sizeof(user));
 for(unsigned fixture=0;fixture<3;fixture++) {
  /* Fresh entry, Rematch, then Select Team all reuse these exact objects. */
  memset(plan,0xa5,sizeof(plan));memset(squads,0x5a,sizeof(squads));
  native_mode=12+(fixture&1);native_move_selected=1;exhibition_plan_ready=0;actual_user++;
  assert(exhibition_gameplan_prepare_matchplan());
  assert(fixture_inits==fixture+1 && native_mode==11 && my_side==0 && !native_move_selected);
  assert(common_inits==2*(fixture+1) && additional_inits==2*(fixture+1) && player_inits==80*(fixture+1));
  assert(loads==fixture+1 && setups==fixture+1 && cpu==fixture+1);
  do_swap(0,7,21); /* Unregistered reserve: full native record/appearance transfer. */
  do_swap(1,0,12); /* Registered bench: goalkeeper exchange is still allowed. */
  assert(exhibition_save_matchplan_sides(3));
  unsigned char saved_plan[sizeof(plan)];TestSquad saved_squads[2];
  plan[0x500+4]=1;plan[0x448+13]=1; /* Sentinel live values for the reopen guard. */
  memcpy(saved_plan,plan,sizeof(plan));memcpy(saved_squads,squads,sizeof(squads));
  assert(exhibition_gameplan_prepare_matchplan());
  assert(!memcmp(saved_plan,plan,sizeof(plan)) && !memcmp(saved_squads,squads,sizeof(squads)));
  assert(loads==fixture+1 && fixture_inits==fixture+1);
  /* A live owner must reject the reset even if wrapper readiness is stale. */
  live_gameplan_window=(void *)1;exhibition_plan_ready=0;
  assert(!exhibition_gameplan_init_fixture(plan));
  assert(!memcmp(saved_plan,plan,sizeof(plan)) && !memcmp(saved_squads,squads,sizeof(squads)));
  assert(!prematch_gameplan_replace_player(0,&squads[0],squads[0].key[7],squads[0].key[12]));
  live_gameplan_window=NULL;
 }
 assert(copies==destroys);
 /* Missing native init binding refuses before clearing either owner. */
 unsigned char before[sizeof(plan)];memcpy(before,plan,sizeof(plan));
 exhibition_matchplan_additional_construct=NULL;assert(!exhibition_gameplan_init_fixture(plan));
 assert(!memcmp(before,plan,sizeof(plan)) && fixture_inits==3);
 exhibition_prepare_team_conditions(100,200);assert(condition_calls==2);
 return 0;
}
'''
    cfile = tmp_path / "dirty_fixture.c"
    cfile.write_text(source)
    exe = tmp_path / "dirty_fixture.exe"
    subprocess.run([cc, "-std=c11", "-Wall", "-Wextra", "-Werror", str(cfile), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)


def native_leaf_initializers():
    capstone = pytest.importorskip("capstone")
    elfmod = pytest.importorskip("elftools.elf.elffile")
    path = Path(os.environ.get("PESNX_NATIVE_LIBRARY", ROOT / "dist/pes21_nx/libUE4.so"))
    if not path.is_file():
        pytest.skip("optional oracle requires ignored compatible owned libUE4.so")
    with path.open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == (
            "a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187")
        image = mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ)
        elf = elfmod.ELFFile(image)
        dyn = elf.get_section_by_name(".dynsym")
        strings = elf.get_section(dyn["sh_link"]).data()
        symbols = list(struct.iter_unpack("<IBBHQQ", dyn.data()))
        result = []
        for name, address, size in (
            ("_ZN9matchPlan18AdditionalDataInfo4InitEv", 0x7d7adb4, 116),
            ("_ZN9matchPlan14PlayerDataInfo4InitEv", 0x7d7a9d8, 16),
            ("_ZN9matchPlan16MemberChangeInfo4InitEv", 0x7d7a58c, 24),
            ("_ZN9matchPlan18AdditionalDataInfoC2Ev", 0x7bc2730, 388),
            ("_ZN4menu19MyClubFlowMatchMenu4MainEv", 0x68a5274, 572),
            ("_ZN10onlinemode22UtilityMyClubSquadEdit12SetSquadModeEN5tmpdb9SquadEdit10SQUAD_MODEE8HomeAway", 0x6acdd20, 76),
        ):
            offset = strings.find(name.encode()+b"\0")
            assert [(a, s) for n, _, _, _, a, s in symbols if n == offset] == [(address, size)]
            image.seek(next(elf.address_offsets(address)))
            raw = image.read(size)
            decoder = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
            decoder.detail = True
            result.append(list(decoder.disasm(raw, address)))
        image.close()
        return result


def run_leaf(instructions, dirty):
    """Interpret complete store-only native initializers; reject unknown opcodes."""
    from capstone import arm64_const as arm
    registers = {"x0": 0}
    result = bytearray(dirty)
    for ins in instructions:
        ops = ins.operands
        if ins.mnemonic in ("mov", "movi"):
            assert ops[1].type == arm.ARM64_OP_IMM
            registers[ins.reg_name(ops[0].reg)] = ops[1].imm
        elif ins.mnemonic in ("str", "strb", "strh", "stur"):
            name = ins.reg_name(ops[0].reg)
            value = 0 if name in ("xzr", "wzr") else registers[name]
            width = {"strb": 1, "strh": 2}.get(ins.mnemonic, 4 if name.startswith("w") else 8)
            target = ops[1]
            assert target.type == arm.ARM64_OP_MEM and not target.mem.index
            at = registers[ins.reg_name(target.mem.base)] + target.mem.disp
            assert 0 <= at <= len(result)-width
            result[at:at+width] = (value & ((1 << (8*width))-1)).to_bytes(width, "little")
        elif ins.mnemonic == "ret":
            break
        else:
            raise AssertionError("unmodelled native opcode: " + ins.mnemonic)
    return result


def test_owned_native_constructor_initializes_every_eligibility_and_history_slot():
    additional, player, change, constructor, _, _ = native_leaf_initializers()
    raw = bytes([0xa5])*0x340
    reset = run_leaf(additional, raw)
    assert reset[3] == 6
    # Init alone leaves BOTH arrays dirty. The complete constructor is needed.
    assert reset[4:0x4c] == raw[4:0x4c]
    assert reset[0xb8:0x338] == raw[0xb8:0x338]
    # Decode the real constructor's complete argument/call sequence and invoke
    # the real leaf initializer instructions at each observed relative offset.
    from capstone import arm64_const as arm
    registers = {"x0": 0}
    calls = []
    for ins in constructor:
        ops = ins.operands
        if ins.mnemonic == "mov":
            registers[ins.reg_name(ops[0].reg)] = registers[ins.reg_name(ops[1].reg)]
        elif ins.mnemonic == "add":
            assert ops[2].type == arm.ARM64_OP_IMM
            registers[ins.reg_name(ops[0].reg)] = registers[ins.reg_name(ops[1].reg)]+ops[2].imm
        elif ins.mnemonic in ("bl", "b"):
            target = ops[0].imm
            at = registers["x0"]
            if target == 0x38d1b90:
                reset[at:at+12] = run_leaf(change, reset[at:at+12])
            elif target == 0x3863500:
                reset[at:at+16] = run_leaf(player, reset[at:at+16])
            elif target == 0x37e72d0:
                assert ins.mnemonic == "b" and at == 0
                reset = run_leaf(additional, reset)
            else:
                raise AssertionError("unmodelled native constructor call")
            calls.append((target, at))
        else:
            assert ins.mnemonic in ("stp", "ldp")  # Callee-save stack traffic only.
    assert calls == ([(0x38d1b90, 4+i*12) for i in range(6)] +
                     [(0x3863500, 0xb8+i*16) for i in range(40)] + [(0x37e72d0, 0)])
    for slot in range(6):
        assert struct.unpack_from("<III", reset, 4+slot*12) == (0xff, 0xff, 0)
    for member in range(40):
        at = 0xb8+member*16
        assert reset[at:at+6] == bytes(6)
        assert reset[at+8:at+16] == bytes(8)
        assert reset[at+6:at+8] == bytes([0xa5])*2  # Native reserved padding stays untouched.


def test_owned_native_prematch_mode_route_initializes_editor_before_loading():
    _, _, _, _, flow, utility = native_leaf_initializers()
    # Actual native pre-match state-0 sequence: resolve owner, mode11, utility,
    # then load. The custom hub now uses the same utility and ordering.
    block = [ins for ins in flow if 0x68a5408 <= ins.address <= 0x68a5418]
    assert [(ins.mnemonic, ins.op_str) for ins in block] == [
        ("bl", "#0x390d280"), ("mov", "w1, w0"), ("mov", "w0, #0xb"),
        ("bl", "#0x38bfe20"), ("bl", "#0x380f2f0")]
    # UtilityMyClubSquadEdit::SetSquadMode calls manager, SquadEdit::Init,
    # SquadEdit::SetSquadMode and SquadEdit::SetMySide in that order.
    assert [ins.operands[0].imm for ins in utility if ins.mnemonic == "bl"] == [
        0x39092e0, 0x386fc30, 0x38c6320, 0x37f73c0]
