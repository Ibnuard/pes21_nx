#include "player_commentary_reload.h"

static inline int pc_reload_hex(const char *p, uint32_t length) {
  if (!p) return 0;
  for (uint32_t i=0;i<length;i++)
    if (!((p[i]>='0' && p[i]<='9') || (p[i]>='a' && p[i]<='f'))) return 0;
  return p[length]=='\0';
}

static inline uint64_t pc_reload_hash_byte(uint64_t key, uint8_t value) {
  return (key^value)*UINT64_C(0x100000001b3);
}

static inline uint64_t pc_reload_hash_u64(uint64_t key, uint64_t value) {
  for (unsigned i=0;i<8;i++) key=pc_reload_hash_byte(key,(uint8_t)(value>>(8u*i)));
  return key;
}

static inline const PcBankOwner *pc_reload_owner(const PcBankCatalog *catalog,
                                                uint32_t id) {
  uint32_t low=0,high=catalog->owner_count;
  while (low<high) {
    const uint32_t middle=low+(high-low)/2u;
    if (catalog->owners[middle].native_id<id) low=middle+1u;
    else high=middle;
  }
  return low<catalog->owner_count && catalog->owners[low].native_id==id
      ? catalog->owners+low : NULL;
}

static inline int pc_selection_build(PcSelection *out, const PcBankCatalog *catalog,
    const char *runtime_pair, const uint32_t logical[2], const uint32_t physical[2],
    const uint32_t ids[2][PC_RELOAD_SIDE_PLAYERS],
    const uint64_t carriers[2][PC_RELOAD_SIDE_PLAYERS], const uint32_t counts[2]) {
  if (!out) return 0;
  memset(out,0,sizeof(*out));
  if (!catalog || !catalog->owners || !catalog->owner_count ||
      catalog->owner_count>65535u || !pc_reload_hex(runtime_pair,16u) ||
      !pc_reload_hex(catalog->runtime_pair,16u) ||
      strcmp(runtime_pair,catalog->runtime_pair) || !logical || !physical ||
      !ids || !carriers || !counts || catalog->base_bytes<32u ||
      catalog->base_bytes>PC_BANK_MAX_BYTES ||
      catalog->baseline_header_count>PC_BANK_MAX_HEADERS ||
      (catalog->baseline_header_count && !catalog->baseline_headers) ||
      (catalog->cue_count && !catalog->cues)) return 0;
  for (uint32_t i=0;i<catalog->owner_count;i++)
    if (!catalog->owners[i].native_id || catalog->owners[i].status>PC_OWNER_NO_P0 ||
        (i && catalog->owners[i-1u].native_id>=catalog->owners[i].native_id)) return 0;
  PcSelection value={0}; value.catalog=catalog;
  memcpy(value.runtime_pair,runtime_pair,sizeof(value.runtime_pair));
  uint64_t key=UINT64_C(0xcbf29ce484222325);
  for (unsigned i=0;i<16;i++) key=pc_reload_hash_byte(key,(uint8_t)runtime_pair[i]);
  key=pc_reload_hash_u64(key,catalog->base_fnv);
  key=pc_reload_hash_u64(key,catalog->base_bytes);
  for (unsigned side=0;side<2;side++) {
    if (!logical[side] || !physical[side] || counts[side]<11u ||
        counts[side]>PC_RELOAD_SIDE_PLAYERS) return 0;
    value.logical_team[side]=logical[side];value.physical_team[side]=physical[side];
    value.side_count[side]=counts[side];
    key=pc_reload_hash_u64(key,logical[side]);key=pc_reload_hash_u64(key,physical[side]);
    key=pc_reload_hash_u64(key,counts[side]);
    for (uint32_t i=0;i<counts[side];i++) {
      const uint32_t id=ids[side][i];
      if (!id || (uint32_t)(carriers[side][i]>>32)!=id) return 0;
      for (uint32_t j=0;j<i;j++) if (ids[side][j]==id) return 0;
      value.native_ids[side][i]=id;value.carriers[side][i]=carriers[side][i];
      key=pc_reload_hash_u64(key,id);key=pc_reload_hash_u64(key,carriers[side][i]);
      uint32_t found=0;
      for (;found<value.count;found++) if (value.ids[found]==id) break;
      if (found<value.count) continue;
      if (value.count>=PC_BANK_MAX_PLAYERS) return 0;
      const PcBankOwner *owner=pc_reload_owner(catalog,id);
      if (owner && owner->status!=PC_OWNER_HOLD &&
          (!owner->base_id || !pc_reload_hex(owner->fingerprint,20u) ||
           !pc_reload_hex(owner->row_sha256,64u))) return 0;
      if (owner && (owner->cue_first>catalog->cue_count ||
          owner->cue_count>catalog->cue_count-owner->cue_first)) return 0;
      value.ids[value.count]=id;value.owners[value.count++]=owner;
      if (!owner || owner->status==PC_OWNER_HOLD ||
          owner->status==PC_OWNER_LABEL_HOLD || owner->status==PC_OWNER_NO_P0)
        value.held_count++;
      key=pc_reload_hash_u64(key,owner?owner->base_id:0u);
      key=pc_reload_hash_u64(key,owner?owner->status:PC_OWNER_HOLD);
      if (owner && owner->status!=PC_OWNER_HOLD) {
        for (unsigned j=0;j<20;j++) key=pc_reload_hash_byte(key,(uint8_t)owner->fingerprint[j]);
        for (unsigned j=0;j<64;j++) key=pc_reload_hash_byte(key,(uint8_t)owner->row_sha256[j]);
      }
    }
  }
  value.selection_key=key;*out=value;return 1;
}

static inline void pc_reload_lock(PcReload *state) {
  uint32_t expected=0;
  while (!__atomic_compare_exchange_n(&state->lock,&expected,1u,0,
                                      __ATOMIC_ACQUIRE,__ATOMIC_RELAXED)) expected=0;
}

static inline void pc_reload_unlock(PcReload *state) {
  __atomic_store_n(&state->lock,0u,__ATOMIC_RELEASE);
}

static inline uint32_t pc_reload_phase(const PcReload *state) {
  return state && state->initialized==PC_RELOAD_INITIALIZED
      ?__atomic_load_n(&state->phase,__ATOMIC_ACQUIRE):PC_RELOAD_IDLE;
}

static inline int pc_reload_init(PcReload *state, const PcReloadOps *ops,
                                 void *context, uint64_t timeout_ms) {
  /* Startup only: never reinitialize a live coordinator or leased preparation. */
  if (!state || !ops || !ops->prepare || !ops->discard || !ops->request ||
      !ops->busy || !ops->mount_id || !ops->play_valid || !ops->dispatch ||
      !ops->release_loading || timeout_ms>PC_RELOAD_MAX_TIMEOUT_MS) return 0;
  memset(state,0,sizeof(*state));state->ops=*ops;state->context=context;
  state->timeout_ms=timeout_ms?timeout_ms:PC_RELOAD_DEFAULT_TIMEOUT_MS;
  state->reported_mount_id=-1;state->initialized=PC_RELOAD_INITIALIZED;return 1;
}

static inline int pc_reload_result_valid(const PcSelection *selection,
                                         const PcBankResult *bank) {
  if (!bank->data || bank->size<32u || bank->size>PC_BANK_MAX_BYTES ||
      memcmp(bank->data,"@UTF",4) || bank->player_count>PC_BANK_MAX_PLAYERS ||
      bank->cue_count>PC_BANK_MAX_CUES || bank->header_count>PC_BANK_MAX_HEADERS ||
      bank->scratch_peak>PC_BANK_MAX_SCRATCH ||
      bank->header_count<selection->catalog->baseline_header_count) return 0;
  for (uint32_t i=0;i<selection->catalog->baseline_header_count;i++)
    if (bank->headers[i]!=selection->catalog->baseline_headers[i]) return 0;
  uint32_t expected=0;
  for (uint32_t i=0;i<selection->count;i++) if (selection->owners[i]) expected++;
  if (expected!=bank->player_count) return 0;
  for (uint32_t i=0;i<bank->player_count;i++) {
    int found=0;
    for (uint32_t j=0;j<selection->count;j++)
      if (bank->players[i] && bank->players[i]==selection->owners[j]) found=1;
    if (!found) return 0;
    for (uint32_t j=0;j<i;j++) if (bank->players[i]==bank->players[j]) return 0;
  }
  for (uint32_t i=0;i<bank->cue_count;i++) {
    const uintptr_t begin=(uintptr_t)selection->catalog->cues;
    const uintptr_t at=(uintptr_t)bank->cues[i];
    if (bank->cue_indices[i]==UINT16_MAX || !bank->cues[i] || at<begin || (at-begin)%sizeof(PcBankCue) ||
        (at-begin)/sizeof(PcBankCue)>=selection->catalog->cue_count) return 0;
    const PcBankCue *cue=bank->cues[i];
    if (cue->owner_index>=selection->catalog->owner_count) return 0;
    const PcBankOwner *owner=selection->catalog->owners+cue->owner_index;
    int found=0;
    for (uint32_t j=0;j<selection->count;j++) if (selection->owners[j]==owner) found=1;
    if (!found || owner->status!=PC_OWNER_NEW) return 0;
  }
  return 1;
}

/* Only game-thread control paths collect. Audio borrowers merely release their
 * exact ticket; no allocation or native callback runs on that release path. */
static inline void pc_reload_collect(PcReload *state) {
  PcBankResult retired={0};
  pc_reload_lock(state);
  if (state->prepared_live && !state->borrowers &&
      (state->phase==PC_RELOAD_TERMINAL || state->phase==PC_RELOAD_DRAINING)) {
    retired=state->prepared;memset(&state->prepared,0,sizeof(state->prepared));
    state->prepared_live=0;
  }
  pc_reload_unlock(state);
  if (retired.data) state->ops.discard(state->context,&retired);
}

static inline void pc_reload_finish(PcReload *state, uint32_t reason,
                                    int dispatch, int draining) {
  pc_reload_lock(state);
  if (state->notified) {pc_reload_unlock(state);return;}
  state->notified=1;state->finishing=1;state->terminal_reason=reason;
  __atomic_store_n(&state->phase,draining?PC_RELOAD_DRAINING:PC_RELOAD_TERMINAL,
                   __ATOMIC_RELEASE);
  pc_reload_unlock(state);
  int dispatched=0;
  if (dispatch) {
    dispatched=state->ops.dispatch(state->context,&state->selection,state->intent,reason)!=0;
    if (!dispatched) state->terminal_reason=reason=PC_RELOAD_REASON_DISPATCH_FAILED;
  }
  state->ops.release_loading(state->context,state->intent,state->selection.generation,
                              reason,dispatched);
  state->finishing=0;
  pc_reload_collect(state);
}

static inline int pc_reload_begin(PcReload *state, const PcSelection *selection,
                                  uint64_t intent, uint64_t now_ms) {
  if (!state || state->initialized!=PC_RELOAD_INITIALIZED || !selection || !intent)
    return PC_RELOAD_REJECTED;
  pc_reload_collect(state);
  pc_reload_lock(state);
  const int blocked=state->phase==PC_RELOAD_PREPARING || state->phase==PC_RELOAD_WAITING ||
      state->phase==PC_RELOAD_DRAINING || state->borrowers || state->prepared_live || state->finishing;
  pc_reload_unlock(state);
  if (blocked) return PC_RELOAD_BLOCKED;
  /* Each admitted Play intent has a fresh token. Repeated menu callbacks must
   * not replay an already completed intent after its generation is terminal. */
  if (state->notified && state->intent==intent) return PC_RELOAD_REJECTED;
  PcSelection canonical;
  if (!pc_selection_build(&canonical,selection->catalog,selection->runtime_pair,
          selection->logical_team,selection->physical_team,selection->native_ids,
          selection->carriers,selection->side_count) ||
      canonical.selection_key!=selection->selection_key ||
      state->next_generation==UINT64_MAX) return PC_RELOAD_REJECTED;
  pc_reload_lock(state);
  state->selection=canonical;state->selection.generation=++state->next_generation;
  state->intent=intent;state->started_ms=now_ms;state->request_issued=0;
  state->notified=state->mount_reported=state->mount_outcome=0;
  state->terminal_reason=PC_RELOAD_REASON_NONE;state->reported_mount_id=-1;
  __atomic_store_n(&state->phase,PC_RELOAD_PREPARING,__ATOMIC_RELEASE);
  pc_reload_unlock(state);
  if (!state->ops.play_valid(state->context,&state->selection,intent)) {
    pc_reload_finish(state,PC_RELOAD_REASON_STALE_PLAY,0,0);return PC_RELOAD_STARTED;
  }
  if (pc_reload_phase(state)!=PC_RELOAD_PREPARING) return PC_RELOAD_STARTED;
  /* A language-change/startup request outside this coordinator must complete
   * before publishing our preparation. It must not consume the next roster. */
  int prior_busy=1;
  if (!state->ops.busy(state->context,PC_RELOAD_LOAD_LABEL,&prior_busy)) {
    pc_reload_finish(state,PC_RELOAD_REASON_LOADER_UNAVAILABLE,0,0);return PC_RELOAD_STARTED;
  }
  if (prior_busy) {
    pc_reload_finish(state,PC_RELOAD_REASON_PRIOR_LOAD_BUSY,0,0);return PC_RELOAD_STARTED;
  }
  PcBankResult prepared={0};
  const int made=state->ops.prepare(state->context,&state->selection,&prepared);
  if (pc_reload_phase(state)!=PC_RELOAD_PREPARING) {
    state->ops.discard(state->context,&prepared);return PC_RELOAD_STARTED;
  }
  if (!made || !pc_reload_result_valid(&state->selection,&prepared)) {
    state->ops.discard(state->context,&prepared);
    pc_reload_finish(state,PC_RELOAD_REASON_PREPARE_FAILED,0,0);return PC_RELOAD_STARTED;
  }
  if (!state->ops.play_valid(state->context,&state->selection,intent)) {
    state->ops.discard(state->context,&prepared);
    pc_reload_finish(state,PC_RELOAD_REASON_STALE_PLAY,0,0);return PC_RELOAD_STARTED;
  }
  if (pc_reload_phase(state)!=PC_RELOAD_PREPARING) {
    state->ops.discard(state->context,&prepared);return PC_RELOAD_STARTED;
  }
  pc_reload_lock(state);
  state->prepared=prepared;state->prepared_live=1;state->request_issued=1;
  __atomic_store_n(&state->phase,PC_RELOAD_WAITING,__ATOMIC_RELEASE);
  pc_reload_unlock(state);
  /* Request may synchronously reach a test/native mount callback. Publish the
   * immutable preparation first, with no policy lock held across native code. */
  if (!state->ops.request(state->context,PC_RELOAD_LOAD_LABEL)) {
    state->request_issued=0;
    pc_reload_finish(state,PC_RELOAD_REASON_REQUEST_UNAVAILABLE,0,0);
  }
  return PC_RELOAD_STARTED;
}

static inline int pc_reload_ticket_valid(const PcReload *state,
                                         const PcReloadBorrow *borrow) {
  return borrow && borrow->slot<PC_RELOAD_MAX_BORROWS && borrow->ticket &&
      borrow->generation==state->selection.generation &&
      state->tickets[borrow->slot]==borrow->ticket &&
      borrow->bank==&state->prepared && borrow->selection==&state->selection;
}

static inline int pc_reload_borrow(PcReload *state, PcReloadBorrow *borrow) {
  if (!state || state->initialized!=PC_RELOAD_INITIALIZED || !borrow) return 0;
  memset(borrow,0,sizeof(*borrow));pc_reload_lock(state);
  if (state->phase!=PC_RELOAD_WAITING || !state->prepared_live ||
      !state->request_issued || state->borrowers>=PC_RELOAD_MAX_BORROWS ||
      state->next_ticket==UINT64_MAX) {pc_reload_unlock(state);return 0;}
  for (uint32_t i=0;i<PC_RELOAD_MAX_BORROWS;i++) if (!state->tickets[i]) {
    state->tickets[i]=++state->next_ticket;state->borrowers++;
    borrow->bank=&state->prepared;borrow->selection=&state->selection;
    borrow->generation=state->selection.generation;borrow->ticket=state->tickets[i];
    borrow->slot=i;pc_reload_unlock(state);return 1;
  }
  pc_reload_unlock(state);return 0;
}

static inline int pc_reload_report(PcReload *state, const PcReloadBorrow *borrow,
                                   int16_t mount_id, uint32_t outcome) {
  if (!state || state->initialized!=PC_RELOAD_INITIALIZED ||
      outcome<PC_RELOAD_MOUNT_SELECTED || outcome>PC_RELOAD_MOUNT_FAILED ||
      (outcome!=PC_RELOAD_MOUNT_FAILED && mount_id<0)) return 0;
  pc_reload_lock(state);
  if (state->phase!=PC_RELOAD_WAITING || !pc_reload_ticket_valid(state,borrow)) {
    pc_reload_unlock(state);return 0;
  }
  state->reported_mount_id=mount_id;state->mount_outcome=outcome;state->mount_reported=1;
  pc_reload_unlock(state);return 1;
}

static inline int pc_reload_release(PcReload *state, const PcReloadBorrow *borrow) {
  if (!state || state->initialized!=PC_RELOAD_INITIALIZED) return 0;
  pc_reload_lock(state);
  if (!pc_reload_ticket_valid(state,borrow)) {pc_reload_unlock(state);return 0;}
  state->tickets[borrow->slot]=0;state->borrowers--;
  pc_reload_unlock(state);return 1;
}

static inline void pc_reload_cancel(PcReload *state) {
  if (!state || state->initialized!=PC_RELOAD_INITIALIZED || state->finishing) return;
  const uint32_t phase=pc_reload_phase(state);
  if (phase==PC_RELOAD_PREPARING || phase==PC_RELOAD_WAITING)
    pc_reload_finish(state,PC_RELOAD_REASON_CANCELLED,0,state->request_issued!=0);
}

static inline void pc_reload_tick(PcReload *state, uint64_t now_ms) {
  if (!state || state->initialized!=PC_RELOAD_INITIALIZED || state->finishing) return;
  pc_reload_collect(state);
  const uint32_t phase=pc_reload_phase(state);
  if (phase==PC_RELOAD_DRAINING) {
    int busy=1;
    if (state->ops.busy(state->context,PC_RELOAD_LOAD_LABEL,&busy) && !busy) {
      pc_reload_lock(state);
      if (!state->borrowers) __atomic_store_n(&state->phase,PC_RELOAD_TERMINAL,__ATOMIC_RELEASE);
      pc_reload_unlock(state);
    }
    return;
  }
  if (phase!=PC_RELOAD_WAITING) return;
  if (!state->ops.play_valid(state->context,&state->selection,state->intent)) {
    pc_reload_finish(state,PC_RELOAD_REASON_STALE_PLAY,0,1);return;
  }
  int busy=1;
  if (!state->ops.busy(state->context,PC_RELOAD_LOAD_LABEL,&busy)) {
    pc_reload_finish(state,PC_RELOAD_REASON_LOADER_UNAVAILABLE,0,1);return;
  }
  if (busy) {
    if (now_ms-state->started_ms>=state->timeout_ms)
      pc_reload_finish(state,PC_RELOAD_REASON_TIMEOUT,0,1);
    return;
  }
  pc_reload_lock(state);
  const uint32_t reported=state->mount_reported,outcome=state->mount_outcome;
  const uint32_t borrowers=state->borrowers;
  const int16_t reported_id=state->reported_mount_id;
  pc_reload_unlock(state);
  /* A completing mount callback may still be copying its private per-slot
   * metadata. Never dispatch or retire preparation until its ticket is released. */
  if (borrowers) {
    if (now_ms-state->started_ms>=state->timeout_ms)
      pc_reload_finish(state,PC_RELOAD_REASON_TIMEOUT,0,1);
    return;
  }
  if (!reported) {pc_reload_finish(state,PC_RELOAD_REASON_MOUNT_MISSING,0,0);return;}
  if (outcome==PC_RELOAD_MOUNT_FAILED) {
    pc_reload_finish(state,PC_RELOAD_REASON_MOUNT_FAILED,0,0);return;
  }
  int16_t actual_id=-1;
  if (!state->ops.mount_id(state->context,PC_RELOAD_BANK_KIND,&actual_id) ||
      actual_id<0 || actual_id!=reported_id) {
    pc_reload_finish(state,PC_RELOAD_REASON_MOUNT_ID,0,0);return;
  }
  if (outcome==PC_RELOAD_MOUNT_SELECTED)
    pc_reload_finish(state,PC_RELOAD_REASON_SELECTED,1,0);
  else if (state->ops.allow_native_fallback)
    pc_reload_finish(state,PC_RELOAD_REASON_FALLBACK,1,0);
  else pc_reload_finish(state,PC_RELOAD_REASON_MOUNT_FAILED,0,0);
}
