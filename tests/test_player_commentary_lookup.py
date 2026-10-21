"""Exercise the production pure name filter against identity/mount changes."""
from pathlib import Path
import json
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRELUDE = r'''
#include <assert.h>
#include "player_commentary_lookup.h"
static const char fp[] = "0123456789abcdef0123";
static const char row[] = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
static PcBankOwner owners[] = {
 {101,110644,fp,row,PC_OWNER_NEW,0,2},
 {102,162114,fp,row,PC_OWNER_CANARY,2,0},
 {103,16799,fp,row,PC_OWNER_NATIVE,2,0},
 {104,541087,fp,row,PC_OWNER_LABEL_HOLD,2,0},
 {105,120000,fp,row,PC_OWNER_HOLD,2,0}
};
static PcBankCue cues[] = {
 {.owner_index=0,.type=0,.name="EN_A1_P0_R110644",.header_fnv=1,.payload_fnv=2},
 {.owner_index=0,.type=24,.name="EN_B1_P0_R110644",.header_fnv=3,.payload_fnv=4}
};
static PcBankCatalog catalog = {.owners=owners,.owner_count=5,.cues=cues,.cue_count=2};
static PcBankResult bank;
static PcLookupSnapshot snapshot;
static uint64_t carrier(uint32_t id, uint16_t locator) {
 return ((uint64_t)id << 32) | locator;
}
static void setup(void) {
 memset(&bank,0,sizeof(bank)); memset(&snapshot,0,sizeof(snapshot));
 bank.data=&bank; bank.size=100; bank.player_count=5; bank.cue_count=2;
 for(unsigned i=0;i<5;i++) {
  bank.players[i]=&owners[i];
  assert(pc_lookup_bind(&snapshot,&catalog,&owners[i],i==2?1:0,carrier(owners[i].native_id,(uint16_t)(70+i))));
 }
 bank.cues[0]=&cues[0]; bank.cues[1]=&cues[1];
 assert(pc_lookup_accept(&snapshot,&catalog,&bank,17,9,29));
}
static PcLookupDecision lookup(uint32_t side,uint64_t id,uint32_t type) {
 return pc_lookup_decide(&catalog,&bank,&snapshot,17,9,29,side,&id,type);
}
'''


def run_c(tmp_path, body):
    compiler = shutil.which("gcc") or shutil.which("clang")
    if not compiler:
        pytest.skip("host C compiler required")
    source, executable = tmp_path / "lookup.c", tmp_path / "lookup.exe"
    source.write_text(PRELUDE + "\nint main(void) {\n" + body + "\nreturn 0;}\n", encoding="utf8")
    built = subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", "-O2",
                            "-I", str(ROOT / "source"), str(source), "-o", str(executable)],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([str(executable)], capture_output=True, text=True, timeout=30)
    assert ran.returncode == 0, ran.stdout + ran.stderr


def test_own_p0_exact_static_pointer_and_native_contexts(tmp_path):
    run_c(tmp_path, r'''
 setup();
 PcLookupDecision a=lookup(0,carrier(110644,70),0);
 PcLookupDecision b=lookup(0,carrier(110644,70),24);
 assert(a.action==PC_LOOKUP_CUE && a.cue==cues[0].name);
 assert(b.action==PC_LOOKUP_CUE && b.cue==cues[1].name);
 for(unsigned type=0;type<30;type++) {
  assert(lookup(0,carrier(162114,71),type).action==PC_LOOKUP_ORIGINAL);
  assert(lookup(1,carrier(16799,72),type).action==PC_LOOKUP_ORIGINAL);
  if(type!=0 && type!=24) assert(lookup(0,carrier(110644,70),type).action==PC_LOOKUP_NULL);
 }
''')


def test_full_carrier_side_unknown_and_hold_are_not_donors(tmp_path):
    run_c(tmp_path, r'''
 setup();
 assert(lookup(1,carrier(110644,70),0).action==PC_LOOKUP_NULL);
 assert(lookup(0,carrier(110644,71),0).action==PC_LOOKUP_NULL);
 assert(lookup(0,carrier(110644,70)|UINT64_C(0x10000),0).action==PC_LOOKUP_NULL);
 assert(lookup(0,carrier(16799,73),0).action==PC_LOOKUP_NULL);
 assert(lookup(0,carrier(541087,73),0).action==PC_LOOKUP_NULL);
 assert(lookup(0,carrier(120000,74),0).action==PC_LOOKUP_NULL);
 assert(lookup(0,carrier(999999,70),0).action==PC_LOOKUP_NULL);
 assert(lookup(2,carrier(110644,70),0).action==PC_LOOKUP_NULL);
 assert(lookup(0,carrier(110644,70),30).action==PC_LOOKUP_NULL);
 assert(pc_lookup_decide(&catalog,&bank,&snapshot,17,9,29,0,NULL,0).action==PC_LOOKUP_NULL);
''')


def test_inactive_generation_mount_and_startup_keep_explicit_compatibility(tmp_path):
    run_c(tmp_path, r'''
 setup(); uint64_t id=carrier(110644,70);
 assert(pc_lookup_decide(&catalog,&bank,&snapshot,18,9,29,0,&id,0).action==PC_LOOKUP_ORIGINAL);
 assert(pc_lookup_decide(&catalog,&bank,&snapshot,17,10,29,0,&id,0).action==PC_LOOKUP_ORIGINAL);
 assert(pc_lookup_decide(&catalog,&bank,&snapshot,17,9,28,0,&id,0).action==PC_LOOKUP_ORIGINAL);
 snapshot.accepted=0;
 assert(lookup(0,id,0).action==PC_LOOKUP_ORIGINAL);
 assert(pc_lookup_decide(NULL,NULL,NULL,0,-1,0,0,&id,0).action==PC_LOOKUP_ORIGINAL);
''')


@pytest.mark.parametrize("change", [
    'cues[0].name="EN_A1_P0_R016799";',
    'cues[0].name="EN_A1_P0A_R110644";',
    'cues[0].name="EN_A1_P0_R110644_01";',
    'cues[0].name="EN_B1_P0_R110644";',
    'cues[0].header_fnv=0;',
    'cues[0].payload_fnv=0;',
    'bank.cue_count=0;',
    'bank.player_count=0;',
    'owners[0].fingerprint="";',
    'owners[0].row_sha256=NULL;',
    'owners[0].status=PC_OWNER_NO_P0;',
    'owners[0].status=PC_OWNER_HOLD;',
])
def test_rejects_unmounted_unverified_or_wrong_context_audio(tmp_path, change):
    run_c(tmp_path, "setup();" + change + r'''
 assert(lookup(0,carrier(110644,70),0).action==PC_LOOKUP_NULL);
''')


def test_duplicate_foreign_and_capacity_admission(tmp_path):
    run_c(tmp_path, r'''
 setup();
 snapshot.accepted=0;
 assert(pc_lookup_bind(&snapshot,&catalog,&owners[0],0,carrier(110644,70)));
 assert(snapshot.binding_count==5);
 PcBankOwner foreign=owners[0];
 assert(!pc_lookup_bind(&snapshot,&catalog,&foreign,0,carrier(110644,70)));
 assert(!pc_lookup_bind(&snapshot,&catalog,&owners[0],0,carrier(16799,70)));
 snapshot.binding_count=PC_BANK_MAX_PLAYERS;
 assert(!pc_lookup_bind(&snapshot,&catalog,&owners[0],0,carrier(110644,70)));
 snapshot.binding_count=5;
 assert(!pc_lookup_accept(&snapshot,&catalog,&bank,0,9,29));
 assert(!pc_lookup_accept(&snapshot,&catalog,&bank,17,-1,29));
 assert(!pc_lookup_accept(&snapshot,&catalog,&bank,17,9,28));
 bank.size=PC_BANK_MAX_BYTES+1u;
 assert(!pc_lookup_accept(&snapshot,&catalog,&bank,17,9,29));
 bank.size=100;
 bank.header_count=PC_BANK_MAX_HEADERS+1u;
 assert(!pc_lookup_accept(&snapshot,&catalog,&bank,17,9,29));
 bank.header_count=0;
 assert(pc_lookup_accept(&snapshot,&catalog,&bank,17,9,29));
 PcBankCue foreign_cue=cues[0]; bank.cues[0]=&foreign_cue;
 assert(lookup(0,carrier(110644,70),0).action==PC_LOOKUP_NULL);
''')


def test_wide_native_owner_never_becomes_masked_donor(tmp_path):
    run_c(tmp_path, r'''
 setup();
 /* Even a wrongly admitted NEW status cannot bypass the 18-bit hold. */
 owners[3].status=PC_OWNER_NEW;
 cues[0].owner_index=3; cues[0].name="EN_A1_P0_R541087";
 assert(lookup(0,carrier(541087,73),0).action==PC_LOOKUP_NULL);
 /* The colliding native owner remains independent, with its own carrier. */
 assert(lookup(1,carrier(16799,72),0).action==PC_LOOKUP_ORIGINAL);
 assert(lookup(0,carrier(16799,73),0).action==PC_LOOKUP_NULL);
''')


def test_owned_native_carrier_snapshots_remain_explicitly_held(tmp_path):
    proof = ROOT / "local-debug/commentary-native-fallback-v58/NATIVE-CARRIER-V59.json"
    if not proof.is_file():
        pytest.skip("owned native carrier oracle snapshots unavailable")
    report = json.loads(proof.read_text(encoding="ascii"))
    assert report["binary_sha256"] == "a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187"
    assert report["owner_count"] == 68 and report["cases"] == 136
    records = report["rows"]
    assert len(records) == 136
    assert len({entry["native_id"] for entry in records}) == 68
    body = ["setup();"]
    for entry in records:
        raw = int(entry["registry_raw_carrier"], 16)
        pure = int(entry["registry_pure_carrier"], 16)
        assert raw == int(entry["resolved_common_carrier"], 16)
        assert raw == int(entry["member_and_sound_raw_carrier"], 16)
        assert raw >> 32 == entry["native_id"]
        assert raw & 65535 == entry["locator"]
        assert pure != raw
        body.append(f"owners[3].native_id={entry['native_id']}u; snapshot.bindings[3].carrier=UINT64_C({raw});")
        body.append("owners[3].status=PC_OWNER_LABEL_HOLD;")
        body.append(f"assert(lookup(0,UINT64_C({raw}),0).action==PC_LOOKUP_NULL);")
        body.append(f"assert(lookup(0,UINT64_C({pure}),0).action==PC_LOOKUP_NULL);")
        body.append("owners[3].status=PC_OWNER_NEW;")
        body.append(f"assert(lookup(0,UINT64_C({raw}),24).action==PC_LOOKUP_NULL);")
    run_c(tmp_path, "\n".join(body))
