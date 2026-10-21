"""Compile the real v59 immutable-selection/reload component, with native seams.

Fixtures are synthetic metadata/audio-free. The native callback seams model
request completion separately from actual MountData ownership, including
concurrent readers, timeout, rematch and exact once-only Play continuation.
"""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run_c(tmp_path, body, *, threads=False):
    compiler = shutil.which("gcc") or shutil.which("clang")
    if not compiler:
        pytest.skip("host C compiler required for actual reload component")
    code = '#include <assert.h>\n#include <stdlib.h>\n'
    if threads:
        code += '#include <pthread.h>\n'
    code += '#include "player_commentary_reload.inc"\n' + FIXTURE + body
    source, executable = tmp_path / "reload.c", tmp_path / "reload.exe"
    source.write_text(code, encoding="utf-8")
    command = [compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
               "-I", str(ROOT / "source"), str(source), "-o", str(executable)]
    if threads:
        command.append("-pthread")
    compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    ran = subprocess.run([str(executable)], capture_output=True, text=True, timeout=30)
    assert ran.returncode == 0, ran.stdout + ran.stderr


FIXTURE = r'''
static const char fingerprint[]="0123456789abcdef0123";
static const char row_hash[]="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
static PcBankOwner owners[82];
static PcBankCue cues[4];
static const uint64_t baseline_headers[2]={0x1234,0x5678};
static PcBankCatalog catalog;
static uint32_t ids[2][PC_RELOAD_SIDE_PLAYERS],counts[2],logical[2]={100,200},physical[2]={10,20};
static uint64_t carriers[2][PC_RELOAD_SIDE_PLAYERS];

typedef struct {
  PcReload state;
  PcSelection selected;
  PcReloadOps ops;
  uint64_t intent;
  int prepared,discarded,requests,busies,mount_ids,valids,dispatches,releases;
  int valid,busy,prior_busy,busy_available,id_available,request_available,prepare_available,fault,reentrant;
  int16_t id;
  int auto_mount,mode;
  uint32_t released_reason,dispatched_reason;
  int released_dispatched;
  void *allocated;
} Fixture;

static void catalog_init(void) {
  memset(owners,0,sizeof(owners));memset(cues,0,sizeof(cues));
  for (unsigned i=0;i<82;i++) owners[i]=(PcBankOwner){10000+i,1000+i,
      fingerprint,row_hash,PC_OWNER_NATIVE,0,0};
  catalog=(PcBankCatalog){"e861c583ec78e9ae",64,82,4,2,0x1111,owners,cues,baseline_headers};
  for (unsigned side=0;side<2;side++) {
    counts[side]=40;
    for (unsigned i=0;i<40;i++) {
      ids[side][i]=1000+side*40+i;
      carriers[side][i]=((uint64_t)ids[side][i]<<32)|((uint64_t)side<<24)|0x567800u|i;
    }
  }
}
static void prepare_bank(Fixture *f,const PcSelection *selection,PcBankResult *bank) {
  bank->data=calloc(1,64);assert(bank->data);f->allocated=bank->data;
  memcpy(bank->data,"@UTF",4);bank->size=64;
  bank->header_count=2;bank->headers[0]=baseline_headers[0];bank->headers[1]=baseline_headers[1];
  for (unsigned i=0;i<selection->count;i++) if (selection->owners[i])
    bank->players[bank->player_count++]=selection->owners[i];
}
static int prepare(void *context,const PcSelection *selection,PcBankResult *bank) {
  Fixture *f=context;f->prepared++;
  assert(!f->requests && selection->generation);
  assert(selection->side_count[0]>=11 && selection->side_count[1]>=11);
  prepare_bank(f,selection,bank);
  switch (f->fault) {
    case 1: bank->size=PC_BANK_MAX_BYTES+1u;break;
    case 2: bank->headers[0]^=1;break;
    case 3: bank->players[0]=owners+81;break;
    case 4: bank->cue_count=PC_BANK_MAX_CUES+1u;break;
    case 5: bank->scratch_peak=PC_BANK_MAX_SCRATCH+1u;break;
    case 6: bank->player_count--;break;
    case 7: f->valid=0;break;
    case 8: pc_reload_cancel(&f->state);break;
    case 9: bank->cue_count=1;bank->cues[0]=(const PcBankCue *)(uintptr_t)1;break;
    default: break;
  }
  return f->prepare_available;
}
static void discard(void *context,PcBankResult *bank) {
  Fixture *f=context;
  if (bank->data) {
    assert(bank->data==f->allocated);f->discarded++;
    free(bank->data);f->allocated=NULL;
  }
  memset(bank,0,sizeof(*bank));
}
static int request(void *context,uint32_t label) {
  Fixture *f=context;assert(label==4 && f->prepared==1);f->requests++;
  assert(f->requests==1);
  if (!f->request_available) return 0;
  if (f->auto_mount) {
    PcReloadBorrow lease;assert(pc_reload_borrow(&f->state,&lease));
    assert(lease.bank->data==f->allocated && lease.selection->generation==lease.generation);
    assert(pc_reload_report(&f->state,&lease,f->id,(uint32_t)f->mode));
    assert(pc_reload_release(&f->state,&lease));
  }
  return 1;
}
static int busy(void *context,uint32_t label,int *value) {
  Fixture *f=context;assert(label==4);f->busies++;
  if (!f->busy_available || (f->fault==10 && f->state.request_issued)) return 0;
  *value=f->state.request_issued?f->busy:f->prior_busy;return 1;
}
static int mount_id(void *context,uint32_t kind,int16_t *id) {
  Fixture *f=context;assert(kind==29);f->mount_ids++;*id=f->id;
  return f->id_available;
}
static int play_valid(void *context,const PcSelection *selection,uint64_t intent) {
  Fixture *f=context;f->valids++;
  return f->valid && intent==f->intent && selection->count>=11 && selection->generation;
}
static int dispatch(void *context,const PcSelection *selection,uint64_t intent,uint32_t reason) {
  Fixture *f=context;assert(intent==f->intent && selection==&f->state.selection);
  f->dispatches++;f->dispatched_reason=reason;
  if (f->reentrant) {
    pc_reload_tick(&f->state,999);
    assert(pc_reload_begin(&f->state,&f->selected,2,1000)==PC_RELOAD_BLOCKED);
  }
  return f->fault!=11;
}
static void release_loading(void *context,uint64_t intent,uint64_t generation,
                             uint32_t reason,int dispatched) {
  Fixture *f=context;assert(intent==f->intent && generation==f->state.selection.generation);
  f->releases++;f->released_reason=reason;f->released_dispatched=dispatched;
}
static void fixture(Fixture *f) {
  memset(f,0,sizeof(*f));catalog_init();
  assert(pc_selection_build(&f->selected,&catalog,catalog.runtime_pair,
      logical,physical,ids,carriers,counts));
  f->intent=1;f->valid=f->busy_available=f->id_available=f->request_available=f->prepare_available=1;
  f->id=42;f->mode=PC_RELOAD_MOUNT_SELECTED;
  f->ops=(PcReloadOps){prepare,discard,request,busy,mount_id,play_valid,
                       dispatch,release_loading,0};
  assert(pc_reload_init(&f->state,&f->ops,f,100));
}
'''


def test_complete_roster_carriers_identity_and_shape_are_snapshot_values(tmp_path):
    run_c(tmp_path, r'''
int main(void) {
  Fixture f;fixture(&f);PcSelection s=f.selected;
  assert(s.count==80 && !s.held_count && s.carriers[1][39]==carriers[1][39]);
  uint64_t old=s.carriers[0][39],key=s.selection_key;
  carriers[0][39]^=0xffff;ids[0][39]=900000;
  assert(s.carriers[0][39]==old && s.ids[39]==1039 && s.selection_key==key);
  catalog_init();
  for(unsigned i=0;i<10;i++) {
    ids[1][i]=ids[0][i];carriers[1][i]=((uint64_t)ids[1][i]<<32)|0xabcdu;
  }
  assert(pc_selection_build(&s,&catalog,catalog.runtime_pair,logical,physical,ids,carriers,counts));
  assert(s.count==70 && s.carriers[0][0]!=s.carriers[1][0]);
  assert(s.owners[0]==owners);
  catalog_init();ids[0][39]=999999;carriers[0][39]=((uint64_t)999999<<32)|7u;
  assert(pc_selection_build(&s,&catalog,catalog.runtime_pair,logical,physical,ids,carriers,counts));
  assert(s.count==80 && s.held_count==1 && !s.owners[39]);
  owners[0].status=PC_OWNER_HOLD;owners[0].base_id=0;owners[0].fingerprint=NULL;owners[0].row_sha256=NULL;
  assert(pc_selection_build(&s,&catalog,catalog.runtime_pair,logical,physical,ids,carriers,counts));
  assert(s.held_count==2 && s.owners[0]==owners);
  return 0;
}
''')


@pytest.mark.parametrize("fault", range(10))
def test_invalid_snapshot_is_rejected_without_guessing_an_owner(tmp_path, fault):
    run_c(tmp_path, r'''
int main(void) {
  Fixture f;fixture(&f);PcSelection s;
  const char *pair=catalog.runtime_pair;
  switch(FAULT) {
    case 0: counts[0]=10;break;
    case 1: counts[1]=41;break;
    case 2: carriers[1][3]^=UINT64_C(1)<<32;break;
    case 3: ids[0][1]=ids[0][0];carriers[0][1]=carriers[0][0];break;
    case 4: ids[0][0]=0;carriers[0][0]=0;break;
    case 5: pair="e861c583ec78e9af";break;
    case 6: owners[1].native_id=owners[0].native_id;break;
    case 7: owners[0].fingerprint="bad";break;
    case 8: owners[0].row_sha256=NULL;break;
    case 9: owners[0].cue_first=5;break;
  }
  memset(&s,0xff,sizeof(s));
  assert(!pc_selection_build(&s,&catalog,pair,logical,physical,ids,carriers,counts));
  assert(!s.count && !s.catalog && !s.generation);
  return 0;
}
'''.replace("FAULT", str(fault)))


def test_prepare_precedes_native_request_and_dispatch_is_once_even_if_reentered(tmp_path):
    run_c(tmp_path, r'''
int main(void) {
  Fixture f;fixture(&f);PcReloadBorrow empty;
  assert(!pc_reload_borrow(&f.state,&empty));pc_reload_tick(&f.state,1);
  assert(!f.prepared && !f.requests && !f.dispatches);
  f.auto_mount=f.reentrant=1;
  assert(pc_reload_begin(&f.state,&f.selected,1,10)==PC_RELOAD_STARTED);
  assert(f.prepared==1 && f.requests==1 && !f.dispatches && !f.discarded);
  assert(f.state.selection.generation==1 && pc_reload_phase(&f.state)==PC_RELOAD_WAITING);
  f.selected.native_ids[0][0]=999999;f.selected.carriers[0][0]=0;
  assert(f.state.selection.native_ids[0][0]==1000 && f.state.selection.carriers[0][0]);
  pc_reload_tick(&f.state,11);
  assert(f.dispatches==1 && f.releases==1 && f.discarded==1);
  assert(f.released_dispatched && f.released_reason==PC_RELOAD_REASON_SELECTED);
  for(unsigned i=0;i<20;i++) pc_reload_tick(&f.state,20+i);
  pc_reload_cancel(&f.state);
  assert(pc_reload_begin(&f.state,&f.selected,1,100)==PC_RELOAD_REJECTED);
  assert(f.requests==1 && f.dispatches==1 && f.releases==1);
  return 0;
}
''')


def test_busy_and_actual_mount_are_independent_barriers(tmp_path):
    run_c(tmp_path, r'''
int main(void) {
  Fixture f;fixture(&f);f.busy=1;
  assert(pc_reload_begin(&f.state,&f.selected,1,0)==PC_RELOAD_STARTED);
  for(unsigned i=0;i<25;i++) pc_reload_tick(&f.state,i);
  assert(f.prepared==1 && f.requests==1 && !f.releases && !f.dispatches);
  assert(pc_reload_begin(&f.state,&f.selected,2,25)==PC_RELOAD_BLOCKED);
  PcReloadBorrow lease;assert(pc_reload_borrow(&f.state,&lease));
  assert(pc_reload_report(&f.state,&lease,42,PC_RELOAD_MOUNT_SELECTED));
  f.busy=0;pc_reload_tick(&f.state,26);
  assert(!f.dispatches && !f.discarded); /* Borrow still pins metadata. */
  assert(pc_reload_release(&f.state,&lease));pc_reload_tick(&f.state,27);
  assert(f.dispatches==1 && f.discarded==1 && f.releases==1);
  return 0;
}
''')


@pytest.mark.parametrize("fault", range(1,12))
def test_preparation_and_native_failures_return_once_to_usable_frontend(tmp_path, fault):
    run_c(tmp_path, r'''
int main(void) {
  Fixture f;fixture(&f);f.fault=FAULT;
  if(FAULT==10 || FAULT==11) f.auto_mount=1;
  assert(pc_reload_begin(&f.state,&f.selected,1,0)==PC_RELOAD_STARTED);
  pc_reload_tick(&f.state,1);
  assert(f.releases==1 && !f.released_dispatched && f.discarded==1);
  assert(f.dispatches==(FAULT==11?1:0));
  if(FAULT<=9) assert(!f.requests);
  f.fault=0;pc_reload_tick(&f.state,2);pc_reload_tick(&f.state,999);
  assert(f.releases==1);
  return 0;
}
'''.replace("FAULT", str(fault)))


def test_prepare_failure_request_rejection_and_invalid_play_are_not_dispatched(tmp_path):
    run_c(tmp_path, r'''
int main(void) {
  Fixture f;
  fixture(&f);f.prepare_available=0;
  assert(pc_reload_begin(&f.state,&f.selected,1,0)==1);
  assert(f.released_reason==PC_RELOAD_REASON_PREPARE_FAILED && !f.requests && f.discarded==1);
  fixture(&f);f.request_available=0;
  assert(pc_reload_begin(&f.state,&f.selected,1,0)==1);
  assert(f.released_reason==PC_RELOAD_REASON_REQUEST_UNAVAILABLE && f.requests==1 && f.discarded==1);
  fixture(&f);f.valid=0;
  assert(pc_reload_begin(&f.state,&f.selected,1,0)==1);
  assert(f.released_reason==PC_RELOAD_REASON_STALE_PLAY && !f.prepared && !f.requests);
  fixture(&f);f.selected.selection_key^=1;
  assert(pc_reload_begin(&f.state,&f.selected,1,0)==PC_RELOAD_REJECTED);
  assert(!f.prepared && !f.requests && !f.releases);
  assert(!pc_reload_init(NULL,&f.ops,&f,100));
  assert(!pc_reload_init(&f.state,&f.ops,&f,PC_RELOAD_MAX_TIMEOUT_MS+1));
  return 0;
}
''')


def test_uninitialized_or_prior_native_load_cannot_consume_a_selected_bank(tmp_path):
    run_c(tmp_path, r'''
int main(void) {
  Fixture f;fixture(&f);PcReload zero={0};PcReloadBorrow lease;
  assert(pc_reload_phase(&zero)==PC_RELOAD_IDLE);
  assert(pc_reload_begin(&zero,&f.selected,1,0)==PC_RELOAD_REJECTED);
  assert(!pc_reload_borrow(&zero,&lease));
  assert(!pc_reload_release(&zero,&lease));
  assert(!pc_reload_report(&zero,&lease,42,PC_RELOAD_MOUNT_SELECTED));
  pc_reload_cancel(&zero);pc_reload_tick(&zero,100);
  f.prior_busy=1;
  assert(pc_reload_begin(&f.state,&f.selected,1,0)==PC_RELOAD_STARTED);
  assert(!f.prepared && !f.requests && !f.dispatches && f.releases==1);
  assert(f.released_reason==PC_RELOAD_REASON_PRIOR_LOAD_BUSY);
  f.prior_busy=0;f.busy_available=0;
  f.intent=2;
  assert(pc_reload_begin(&f.state,&f.selected,2,1)==PC_RELOAD_STARTED);
  assert(!f.prepared && !f.requests && f.releases==2);
  assert(f.released_reason==PC_RELOAD_REASON_LOADER_UNAVAILABLE);
  return 0;
}
''')


@pytest.mark.parametrize("mode,allow", [(2,0),(2,1),(3,0),(3,1)])
def test_fallback_requires_explicit_policy_and_generation_mount_proof(tmp_path, mode, allow):
    run_c(tmp_path, r'''
int main(void) {
  Fixture f;fixture(&f);f.auto_mount=1;f.mode=MODE;
  f.state.ops.allow_native_fallback=ALLOW;
  assert(pc_reload_begin(&f.state,&f.selected,1,0)==1);
  pc_reload_tick(&f.state,1);
  assert(f.dispatches==ALLOW && f.releases==1 && f.discarded==1);
  assert(f.released_reason==(ALLOW?PC_RELOAD_REASON_FALLBACK:PC_RELOAD_REASON_MOUNT_FAILED));
  return 0;
}
'''.replace("MODE",str(mode)).replace("ALLOW",str(allow)))


def test_completion_without_matching_native_mount_id_never_advances_play(tmp_path):
    run_c(tmp_path, r'''
int main(void) {
  Fixture f;
  fixture(&f);assert(pc_reload_begin(&f.state,&f.selected,1,0)==1);
  pc_reload_tick(&f.state,1);
  assert(f.released_reason==PC_RELOAD_REASON_MOUNT_MISSING && !f.dispatches && !f.mount_ids);
  fixture(&f);f.auto_mount=1;assert(pc_reload_begin(&f.state,&f.selected,1,0)==1);
  f.id=43;pc_reload_tick(&f.state,1);
  assert(f.released_reason==PC_RELOAD_REASON_MOUNT_ID && !f.dispatches);
  fixture(&f);f.auto_mount=1;f.id_available=0;
  assert(pc_reload_begin(&f.state,&f.selected,1,0)==1);pc_reload_tick(&f.state,1);
  assert(f.released_reason==PC_RELOAD_REASON_MOUNT_ID && !f.dispatches);
  fixture(&f);f.auto_mount=1;f.mode=PC_RELOAD_MOUNT_FAILED;
  assert(pc_reload_begin(&f.state,&f.selected,1,0)==1);pc_reload_tick(&f.state,1);
  assert(f.released_reason==PC_RELOAD_REASON_MOUNT_FAILED && !f.dispatches);
  return 0;
}
''')


def test_cancel_timeout_and_old_tickets_cannot_free_or_replace_a_new_generation(tmp_path):
    run_c(tmp_path, r'''
int main(void) {
  Fixture f;fixture(&f);f.busy=1;
  assert(pc_reload_begin(&f.state,&f.selected,1,0)==1);
  PcReloadBorrow leases[4],fifth;
  for(unsigned i=0;i<4;i++) assert(pc_reload_borrow(&f.state,leases+i));
  assert(!pc_reload_borrow(&f.state,&fifth));
  PcReloadBorrow bad=leases[0];bad.ticket++;
  assert(!pc_reload_release(&f.state,&bad));
  pc_reload_cancel(&f.state);pc_reload_cancel(&f.state);
  assert(f.releases==1 && !f.discarded && !f.dispatches);
  assert(pc_reload_phase(&f.state)==PC_RELOAD_DRAINING);
  for(unsigned i=0;i<4;i++) {
    assert(!memcmp(leases[i].bank->data,"@UTF",4));
    assert(!pc_reload_report(&f.state,leases+i,42,PC_RELOAD_MOUNT_SELECTED));
    assert(pc_reload_release(&f.state,leases+i));
    assert(!pc_reload_release(&f.state,leases+i));
  }
  pc_reload_tick(&f.state,1);assert(f.discarded==1);
  assert(pc_reload_begin(&f.state,&f.selected,2,2)==PC_RELOAD_BLOCKED);
  f.busy=0;pc_reload_tick(&f.state,3);
  assert(pc_reload_phase(&f.state)==PC_RELOAD_TERMINAL);
  f.intent=2;f.prepared=f.requests=0;f.auto_mount=1;
  assert(pc_reload_begin(&f.state,&f.selected,2,4)==1);
  assert(f.state.selection.generation==2 && !pc_reload_release(&f.state,leases));
  assert(!pc_reload_report(&f.state,leases,42,PC_RELOAD_MOUNT_SELECTED));
  pc_reload_tick(&f.state,5);assert(f.dispatches==1 && f.releases==2 && f.discarded==2);
  return 0;
}
''')


def test_timeout_releases_loading_once_and_drains_without_restarting_old_request(tmp_path):
    run_c(tmp_path, r'''
int main(void) {
  Fixture f;fixture(&f);f.busy=1;f.state.timeout_ms=20;
  assert(pc_reload_begin(&f.state,&f.selected,1,UINT64_MAX-10)==1);
  pc_reload_tick(&f.state,8);assert(!f.releases);
  pc_reload_tick(&f.state,9);
  assert(f.releases==1 && f.discarded==1 && f.released_reason==PC_RELOAD_REASON_TIMEOUT);
  assert(pc_reload_phase(&f.state)==PC_RELOAD_DRAINING);
  PcReloadBorrow lease;assert(!pc_reload_borrow(&f.state,&lease));
  for(unsigned i=10;i<200;i++)pc_reload_tick(&f.state,i);
  assert(f.requests==1 && f.releases==1 && !f.dispatches);
  f.busy=0;pc_reload_tick(&f.state,201);
  assert(pc_reload_phase(&f.state)==PC_RELOAD_TERMINAL);
  return 0;
}
''')


def test_actual_concurrent_mount_borrowers_keep_data_alive_after_cancel(tmp_path):
    run_c(tmp_path, r'''
static uint32_t ready,go;
static void *reader(void *context) {
  Fixture *f=context;PcReloadBorrow lease;
  assert(pc_reload_borrow(&f->state,&lease));
  __atomic_add_fetch(&ready,1u,__ATOMIC_RELEASE);
  while(!__atomic_load_n(&go,__ATOMIC_ACQUIRE)) {}
  assert(lease.bank->size==64 && !memcmp(lease.bank->data,"@UTF",4));
  assert(!pc_reload_report(&f->state,&lease,42,PC_RELOAD_MOUNT_SELECTED));
  assert(pc_reload_release(&f->state,&lease));
  return NULL;
}
int main(void) {
  Fixture f;fixture(&f);f.busy=1;assert(pc_reload_begin(&f.state,&f.selected,1,0)==1);
  pthread_t threads[4];
  for(unsigned i=0;i<4;i++)assert(!pthread_create(threads+i,NULL,reader,&f));
  while(__atomic_load_n(&ready,__ATOMIC_ACQUIRE)!=4) {}
  pc_reload_cancel(&f.state);assert(f.releases==1 && !f.discarded);
  PcReloadBorrow fifth;assert(!pc_reload_borrow(&f.state,&fifth));
  __atomic_store_n(&go,1u,__ATOMIC_RELEASE);
  for(unsigned i=0;i<4;i++)assert(!pthread_join(threads[i],NULL));
  f.busy=0;pc_reload_tick(&f.state,1);
  assert(f.discarded==1 && !f.dispatches && pc_reload_phase(&f.state)==PC_RELOAD_TERMINAL);
  return 0;
}
''', threads=True)
