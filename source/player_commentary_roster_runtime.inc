/* Selected-roster commentary glue. All construction and loader polling runs
 * on the menu/game thread. Native mount callbacks borrow immutable preparation;
 * every accepted mount still owns a separate writable ACB until native unmount.
 * No audio is compiled into this file or the generated metadata catalog. */
#include "player_commentary_bank_builder.h"
#include "player_commentary_roster_catalog.h"
#include "player_commentary_reload.inc"

#define PC_ROSTER_ARCHIVE NX_ASSET_ARCHIVE
#define PC_ROSTER_PREFIX "Commentary/players-v59/"
static PcReload player_commentary_reload;
static uint32_t player_commentary_roster_enabled;
static uint64_t player_commentary_play_intent, player_commentary_ready_key;
static uint64_t player_commentary_ready_generation;
/* These two fields and mounted policy rows share the same short metadata lock. */
static uint64_t player_commentary_active_generation;
static int16_t player_commentary_active_mount = -1;
/* Protected by the mount-policy lock: 1=baseline, 2=drain then baseline.
 * A rejected optional roster must not make a valid Exhibition unplayable.
 * Unproved/new owners remain NULL; only pinned native/canary labels survive. */
static uint32_t player_commentary_snapshot_fallback;
static uint32_t player_commentary_snapshot_identity;
static uint32_t player_commentary_snapshot_error, player_commentary_snapshot_side;
static uint32_t player_commentary_snapshot_index;
static PcReloadNativeRequest player_commentary_native_request;
static PcReloadNativeBusy player_commentary_native_busy;
static PcReloadNativeMountId player_commentary_native_mount_id;
static const char *(*player_commentary_typed_original)(
    const void *, const uint32_t *, const uint64_t *, uint32_t, uint32_t);

static int player_commentary_capture_selection(PcSelection *out) {
  player_commentary_snapshot_error=1u;
  player_commentary_snapshot_side=player_commentary_snapshot_index=UINT32_MAX;
  if (!out || !match_tmpdb_match_get_player || !exhibition_tmpdb_match_get_team)
    return 0;
  player_commentary_snapshot_error=2u;
  unsigned char *match = exhibition_get_tmpdb_match();
  if (!match) return 0;
  uint32_t ids[2][40] = {{0}}, counts[2] = {0};
  uint64_t carriers[2][40] = {{0}};
  uint32_t logical[2] = {prematch_gameplan_team_id(0), prematch_gameplan_team_id(1)};
  uint32_t physical[2] = {exhibition_native_team_id(logical[0]),
                          exhibition_native_team_id(logical[1])};
  for (uint32_t side = 0; side < 2; ++side) {
    player_commentary_snapshot_side=side;
    player_commentary_snapshot_error=3u;
    const unsigned char *team = exhibition_tmpdb_match_get_team(match, &side);
    uint32_t flags = 0;
    if (!team) return 0;
    memcpy(&flags, team + 0x3a6u, sizeof(flags));
    counts[side] = (flags >> 9) & 0x7fu;
    player_commentary_snapshot_error=4u;
    if (counts[side] < 11u || counts[side] > 40u) return 0;
    for (uint32_t i = 0; i < counts[side]; ++i) {
      player_commentary_snapshot_index=i;
      player_commentary_snapshot_error=5u;
      const unsigned char *record = match_tmpdb_match_get_player(match, &side, &i);
      uint64_t team_carrier = 0;
      if (record != match + 0x1248u + side * 0x8c00u + i * 0x380u) return 0;
      memcpy(&carriers[side][i], record + 44u, sizeof(uint64_t));
      memcpy(&team_carrier, team + 0x110u + i * 8u, sizeof(team_carrier));
      player_commentary_snapshot_error=6u;
      if (team_carrier != carriers[side][i]) return 0;
      ids[side][i] = (uint32_t)(carriers[side][i] >> 32);
    }
  }
  player_commentary_snapshot_error=7u;
  const int valid=pc_selection_build(out, &player_commentary_roster_catalog,
      prematch_gameplan_identity_scope(), logical, physical, ids, carriers, counts);
  if(valid)player_commentary_snapshot_error=0u;
  return valid;
}

static void *player_commentary_read_recording(void *context, const char *asset,
                                             size_t limit, size_t *bytes) {
  (void)context;
  char path[NX_ASSET_NAME_BYTES];
  if (bytes) *bytes = 0;
  if (!asset || !bytes) return NULL;
  const int length = snprintf(path, sizeof(path), "%s%s", PC_ROSTER_PREFIX, asset);
  if (length < 0 || (size_t)length >= sizeof(path)) return NULL;
  return nx_asset_read_archive(PC_ROSTER_ARCHIVE, path, limit, bytes);
}

static int player_commentary_prepare_roster(void *context,
    const PcSelection *selection, PcBankResult *result) {
  (void)context;
  size_t size = 0;
  unsigned char *patch = nx_asset_read("Commentary/players-v53.nxcp",
                                      PLAYER_COMMENTARY_MAX_PATCH, &size);
  /* The admitted v53 delta is exactly one full-bank replacement. Reuse that
   * independently pinned bank as the seed, without capturing a mutable native
   * mount or allocating another copy of the original 6-MiB bank. */
  const int valid = patch && size == PLAYER_COMMENTARY_PATCH_BYTES && size >= 48u &&
      !memcmp(patch, "NXCMT01\0", 8) &&
      team_commentary_read_u32(patch + 8) == PLAYER_COMMENTARY_BASE_BYTES &&
      team_commentary_read_u32(patch + 12) == PLAYER_COMMENTARY_RESULT_BYTES &&
      team_commentary_read_u64(patch + 16) == PLAYER_COMMENTARY_BASE_FNV &&
      team_commentary_read_u64(patch + 24) == PLAYER_COMMENTARY_RESULT_FNV &&
      team_commentary_read_u32(patch + 32) == 1u &&
      team_commentary_read_u32(patch + 36) == 0u &&
      team_commentary_read_u32(patch + 40) == 0u &&
      team_commentary_read_u32(patch + 44) == size - 48u &&
      team_commentary_hash(patch, (uint32_t)size) == PLAYER_COMMENTARY_PATCH_FNV &&
      team_commentary_hash(patch + 48, (uint32_t)size - 48u) ==
          player_commentary_roster_catalog.base_fnv;
  const int built = valid && pc_bank_build(patch + 48, (uint32_t)size - 48u,
      selection->catalog, selection->ids, selection->count,
      player_commentary_read_recording, NULL, result);
  free(patch);
  if (built)
    debugPrintf("commentary-v59: prepared gen=%llu teams=%u/%u players=%u "
                "held=%u cues=%u bank=%u scratch=%zu\n",
        (unsigned long long)selection->generation, selection->logical_team[0],
        selection->logical_team[1], selection->count, selection->held_count,
        result->cue_count, result->size, result->scratch_peak);
  return built;
}
static void player_commentary_discard_roster(void *context, PcBankResult *bank) {
  (void)context;
  pc_bank_free(bank);
}
static int player_commentary_request_roster(void *context, uint32_t label) {
  (void)context;
  if (!player_commentary_native_request || label != 4u) return 0;
  player_commentary_native_request(label);
  return 1; /* Issued only. Completion needs busy, kind29 and own mount proof. */
}
static int player_commentary_roster_busy(void *context, uint32_t label, int *busy) {
  (void)context;
  if (!player_commentary_native_busy || label != 4u || !busy) return 0;
  *busy = player_commentary_native_busy(label) != 0;
  return 1;
}
static int player_commentary_roster_mount_id(void *context, uint32_t kind, int16_t *id) {
  (void)context;
  if (!player_commentary_native_mount_id || kind != 29u || !id) return 0;
  *id = -1;
  return player_commentary_native_mount_id(kind, id) == 0 && *id >= 0;
}
static int player_commentary_play_valid(void *context,
    const PcSelection *selection, uint64_t intent) {
  (void)context;
  PcSelection current;
  return intent == player_commentary_play_intent &&
      __atomic_load_n(&exhibition_session_active, __ATOMIC_ACQUIRE) &&
      __atomic_load_n(&native_gamepad_lab_active, __ATOMIC_ACQUIRE) &&
      !__atomic_load_n(&main_menu_2p_team_selector_active, __ATOMIC_ACQUIRE) &&
      player_commentary_capture_selection(&current) &&
      current.selection_key == selection->selection_key;
}
static int player_commentary_dispatch_ready(void *context,
    const PcSelection *selection, uint64_t intent, uint32_t reason) {
  (void)context;
  if (reason != PC_RELOAD_REASON_SELECTED ||
      !player_commentary_play_valid(NULL, selection, intent)) return 0;
  player_commentary_policy_enter();
  int owned = 0;
  for (unsigned i = 0; i < 4; ++i) {
    const TeamCommentaryMount *slot = player_commentary_mounts + i;
    if (__atomic_load_n(&slot->state, __ATOMIC_ACQUIRE) == 2u &&
        slot->id == player_commentary_reload.reported_mount_id &&
        slot->roster.generation == selection->generation &&
        slot->roster.lookup.accepted == PC_LOOKUP_ACCEPTED &&
        slot->roster.lookup.mount_id == slot->id &&
        slot->roster.catalog == selection->catalog &&
        slot->roster.bank.data == slot->data) { owned = 1; break; }
  }
  if (!owned) { player_commentary_policy_leave(); return 0; }
  player_commentary_active_generation = selection->generation;
  player_commentary_active_mount = player_commentary_reload.reported_mount_id;
  player_commentary_policy_leave();
  player_commentary_ready_key = selection->selection_key;
  player_commentary_ready_generation = selection->generation;
  char note[192];
  snprintf(note, sizeof(note), "v59 generation=%llu kind=29 mount=%d teams=%u/%u "
           "players=%u held=%u; selected bank accepted, continuing Play",
           (unsigned long long)selection->generation,
           player_commentary_reload.reported_mount_id, selection->logical_team[0],
           selection->logical_team[1], selection->count, selection->held_count);
  scene_runtime_note("player commentary", note);
  __atomic_store_n(&main_menu_2p_prematch_hub_active, 1u, __ATOMIC_RELEASE);
  __atomic_store_n(&main_menu_2p_prematch_hub_input_pending, 3u, __ATOMIC_RELEASE);
  return 1;
}
static void player_commentary_release_loading(void *context, uint64_t intent,
    uint64_t generation, uint32_t reason, int dispatched) {
  (void)context;
  if (intent != player_commentary_play_intent) return;
  debugPrintf("commentary-v59: reload gen=%llu terminal=%u dispatch=%d\n",
              (unsigned long long)generation, reason, dispatched);
  if (dispatched) return; /* Existing Strategy/VS transition owns the cover. */
  player_commentary_ready_key = player_commentary_ready_generation = 0;
  player_commentary_policy_enter();
  player_commentary_active_generation = 0;
  player_commentary_active_mount = -1;
  player_commentary_policy_leave();
  __atomic_store_n(&main_menu_2p_transition_active, 0u, __ATOMIC_RELEASE);
  __atomic_store_n(&main_menu_2p_transition_kind, MAIN_MENU_2P_TRANSITION_NONE,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&main_menu_2p_prematch_hub_active, 1u, __ATOMIC_RELEASE);
  __atomic_store_n(&main_menu_2p_prematch_hub_input_pending, 0u, __ATOMIC_RELEASE);
  main_menu_2p_prematch_hub_input_armed[0] = 0;
  char note[128];
  snprintf(note, sizeof(note), "v59 generation=%llu reason=%u; returned to setup",
           (unsigned long long)generation, reason);
  scene_runtime_note("player commentary", note);
}

static void *player_commentary_clone_roster(const void *base, uint32_t base_bytes,
    PlayerCommentaryMountedPolicy *policy, uint32_t *bytes, void **lease_out) {
  *lease_out = NULL;
  PcReloadBorrow *lease = malloc(sizeof(*lease));
  if (!lease) return NULL;
  if (!pc_reload_borrow(&player_commentary_reload, lease)) { free(lease); return NULL; }
  void *copy = NULL;
  if (!base || base_bytes != PLAYER_COMMENTARY_BASE_BYTES ||
      team_commentary_hash(base, base_bytes) != PLAYER_COMMENTARY_BASE_FNV ||
      !lease->bank->data || lease->bank->size > PC_BANK_MAX_BYTES) goto failed;
  copy = malloc(lease->bank->size);
  if (!copy) goto failed;
  memcpy(copy, lease->bank->data, lease->bank->size);
  memset(policy, 0, sizeof(*policy));
  policy->catalog = lease->selection->catalog;
  policy->generation = lease->generation;
  policy->bank = *lease->bank;
  policy->bank.data = copy;
  for (uint32_t side = 0; side < 2; ++side)
    for (uint32_t i = 0; i < lease->selection->side_count[side]; ++i) {
      const PcBankOwner *owner = pc_reload_owner(policy->catalog,
          lease->selection->native_ids[side][i]);
      if (pc_lookup_identity_complete(owner) &&
          !pc_lookup_bind(&policy->lookup, policy->catalog, owner, side,
                         lease->selection->carriers[side][i])) goto failed;
    }
  /* Shape/identity validation before native mount, without claiming acceptance.
   * The real mount ID is attached only after MountData succeeds. */
  if (!pc_lookup_accept(&policy->lookup, policy->catalog, &policy->bank,
                        policy->generation, 0, PC_LOOKUP_BANK_KIND)) goto failed;
  policy->lookup.accepted = 0;
  policy->lookup.mount_id = -1;
  *bytes = policy->bank.size;
  *lease_out = lease;
  return copy;
failed:
  free(copy);
  memset(policy, 0, sizeof(*policy));
  pc_reload_release(&player_commentary_reload, lease);
  free(lease);
  return NULL;
}
static void player_commentary_observe_roster(void *opaque, int16_t id,
                                            unsigned variant) {
  PcReloadBorrow local, *lease = opaque;
  if (!lease && pc_reload_borrow(&player_commentary_reload, &local)) lease = &local;
  if (lease) {
    pc_reload_report(&player_commentary_reload, lease, id, variant + 1u);
    pc_reload_release(&player_commentary_reload, lease);
  }
  free(opaque);
}
static const char *pes_sound_player_name_label(const void *accessor,
    const uint32_t *side, const uint64_t *carrier, uint32_t type, uint32_t access) {
  PcLookupDecision decision = {PC_LOOKUP_ORIGINAL, NULL};
  player_commentary_policy_enter();
  if (player_commentary_snapshot_fallback) {
    decision.action=PC_LOOKUP_NULL;
    uint64_t raw=0;
    if(carrier)memcpy(&raw,carrier,sizeof(raw));
    const PcBankOwner *owner=pc_reload_owner(&player_commentary_roster_catalog,(uint32_t)(raw>>32));
    if(player_commentary_snapshot_identity && side && *side<2u && carrier &&
        pc_lookup_identity_complete(owner) &&
        (owner->status==PC_OWNER_NATIVE || owner->status==PC_OWNER_CANARY))
      decision.action=PC_LOOKUP_ORIGINAL;
  } else if (player_commentary_active_generation) {
    decision.action = PC_LOOKUP_NULL;
    for (unsigned i = 0; i < 4; ++i) {
      const TeamCommentaryMount *slot = player_commentary_mounts + i;
      if (__atomic_load_n(&slot->state, __ATOMIC_ACQUIRE) != 2u ||
          slot->id != player_commentary_active_mount ||
          slot->roster.lookup.accepted != PC_LOOKUP_ACCEPTED ||
          slot->roster.generation != player_commentary_active_generation) continue;
      decision = pc_lookup_decide(slot->roster.catalog, &slot->roster.bank,
          &slot->roster.lookup, player_commentary_active_generation,
          player_commentary_active_mount, PC_LOOKUP_BANK_KIND,
          side ? *side : 2u, carrier, type);
      break;
    }
  }
  player_commentary_policy_leave();
  if (decision.action == PC_LOOKUP_CUE) return decision.cue;
  if (decision.action == PC_LOOKUP_NULL) return NULL;
  return player_commentary_typed_original(accessor, side, carrier, type, access);
}

static void player_commentary_roster_invalidate(void) {
  if (!player_commentary_roster_enabled) return;
  /* Invalidate intent BEFORE cancel, so a stale completion cannot reopen hub. */
  ++player_commentary_play_intent;
  player_commentary_ready_key = player_commentary_ready_generation = 0;
  player_commentary_policy_enter();
  player_commentary_active_generation = 0;
  player_commentary_active_mount = -1;
  player_commentary_snapshot_fallback=player_commentary_snapshot_identity=0u;
  player_commentary_policy_leave();
  pc_reload_cancel(&player_commentary_reload);
}
static void player_commentary_roster_tick(void) {
  if (!player_commentary_roster_enabled) return;
  const uint32_t phase = pc_reload_phase(&player_commentary_reload);
  if (phase == PC_RELOAD_WAITING || phase == PC_RELOAD_DRAINING ||
      player_commentary_reload.prepared_live)
    pc_reload_tick(&player_commentary_reload, exhibition_search_focus_now_ms());
  /* A prior native request must drain before baseline Play can resume. Never
   * reopen a cancelled selector/session or spin a second reload request. */
  const uint32_t after=pc_reload_phase(&player_commentary_reload);
  int resume=0;
  player_commentary_policy_enter();
  if(player_commentary_snapshot_fallback==2u && after!=PC_RELOAD_WAITING &&
      after!=PC_RELOAD_DRAINING) {
    player_commentary_snapshot_fallback=1u;
    resume=1;
  }
  player_commentary_policy_leave();
  if(resume && __atomic_load_n(&main_menu_2p_prematch_hub_active,__ATOMIC_ACQUIRE) &&
      !__atomic_load_n(&main_menu_2p_team_selector_active,__ATOMIC_ACQUIRE))
    __atomic_store_n(&main_menu_2p_prematch_hub_input_pending,3u,__ATOMIC_RELEASE);
}
static int player_commentary_roster_resume_pending(void) {
  return player_commentary_roster_enabled && player_commentary_ready_key &&
         player_commentary_ready_generation;
}
static int player_commentary_roster_play_gate(void) {
  if (!player_commentary_roster_enabled) return 1;
  player_commentary_policy_enter();
  const uint32_t fallback=player_commentary_snapshot_fallback;
  player_commentary_policy_leave();
  PcSelection selection;
  const int captured = player_commentary_capture_selection(&selection);
  /* Stages 1..6 describe real Match structure, not optional audio metadata.
   * Never repeat v63's bypass of an invalid HOME into entrance/gameplay. */
  if (!captured && player_commentary_snapshot_error < 7u) {
    char note[144];
    snprintf(note,sizeof(note),"v64 invalid Match blocked stage=%u side=%u index=%u; setup retained",
        player_commentary_snapshot_error,player_commentary_snapshot_side,
        player_commentary_snapshot_index);
    scene_runtime_note("player commentary",note);
    player_commentary_roster_invalidate();
    return 0;
  }
  if(fallback)return fallback==1u;
  if (!captured) {
    char note[160];
    snprintf(note,sizeof(note),"v64 optional snapshot rejected stage=%u side=%u index=%u; native/canary fallback, new names suppressed",
        player_commentary_snapshot_error,player_commentary_snapshot_side,
        player_commentary_snapshot_index);
    scene_runtime_note("player commentary",note);
    /* Keep every identity gate unchanged. Cancel only our optional intent;
     * mounted buffers/leases still follow native unmount ownership. */
    player_commentary_roster_invalidate();
    const uint32_t phase=pc_reload_phase(&player_commentary_reload);
    const uint32_t waiting=phase==PC_RELOAD_WAITING || phase==PC_RELOAD_DRAINING;
    const int identity=!strcmp(prematch_gameplan_identity_scope(),player_commentary_roster_catalog.runtime_pair);
    player_commentary_policy_enter();
    player_commentary_snapshot_identity=identity;
    player_commentary_snapshot_fallback=waiting?2u:1u;
    player_commentary_policy_leave();
    return !waiting;
  }
  if (player_commentary_ready_key == selection.selection_key &&
      player_commentary_ready_generation == player_commentary_reload.selection.generation) {
    player_commentary_ready_key = player_commentary_ready_generation = 0;
    return 1; /* Resume the existing Strategy transition exactly once. */
  }
  player_commentary_ready_key = player_commentary_ready_generation = 0;
  ++player_commentary_play_intent;
  __atomic_store_n(&main_menu_2p_prematch_hub_active, 0u, __ATOMIC_RELEASE);
  __atomic_store_n(&main_menu_2p_transition_active, 1u, __ATOMIC_RELEASE);
  __atomic_store_n(&main_menu_2p_transition_kind, MAIN_MENU_2P_TRANSITION_LOADING,
                   __ATOMIC_RELEASE);
  const int result = pc_reload_begin(&player_commentary_reload, &selection,
      player_commentary_play_intent, exhibition_search_focus_now_ms());
  if (result != PC_RELOAD_STARTED)
    player_commentary_release_loading(NULL, player_commentary_play_intent, 0,
                                     PC_RELOAD_REASON_PRIOR_LOAD_BUSY, 0);
  return 0;
}

/* install_ue4_hooks runs BEFORE so_finalize maps load_virtbase. Symbol lookup
 * may calculate the future RX address, but every opcode read/patch must use
 * the readable RW backing image. Never dereference an RX alias here. */
static uintptr_t player_commentary_roster_backing_symbol(so_module *module,
    const char *name, uintptr_t *runtime) {
  if (!module || !module->load_base || !module->load_virtbase ||
      module->load_size < 16u || !runtime) return 0;
  const uintptr_t rx = so_try_find_addr_rx(module, name);
  const uintptr_t alias = (uintptr_t)module->load_virtbase;
  if (!rx || rx < alias || rx - alias > module->load_size - 16u) return 0;
  *runtime = rx;
  return (uintptr_t)module->load_base + (rx - alias);
}
static void player_commentary_roster_install(so_module *module) {
  if (!module || !module->load_base || !module->load_virtbase ||
      module->load_size < 16u ||
      PC_LOOKUP_TYPED_RVA > module->load_size - 16u ||
      PC_LOOKUP_TYPED_PLT_RVA > module->load_size - 16u ||
      !player_commentary_enabled || !player_commentary_roster_catalog.owner_count ||
      !player_commentary_roster_catalog.runtime_pair ||
      strcmp(player_commentary_roster_catalog.runtime_pair,
             prematch_gameplan_identity_scope())) return;
  size_t marker_bytes = 0;
  char *marker = nx_asset_read_archive(PC_ROSTER_ARCHIVE, PC_ROSTER_PREFIX "catalog-id.txt", 64,
                                      &marker_bytes);
  const int available = marker && marker_bytes == 17u && marker[16] == '\n' &&
      !memcmp(marker, player_commentary_roster_catalog.runtime_pair, 16u);
  free(marker);
  if (!available) {
    scene_runtime_note("player commentary", "optional roster pack absent; v53 retained");
    return;
  }
  scene_runtime_note("player commentary", "v61 install: unified assets; checking RW backing before native code mapping");
  uintptr_t request_rx = 0, busy_rx = 0, mount_rx = 0;
  const uintptr_t request = player_commentary_roster_backing_symbol(module,
      "_ZN5sound3sys4Load7RequestE13SD_LOAD_LABEL", &request_rx);
  const uintptr_t busy = player_commentary_roster_backing_symbol(module,
      "_ZN5sound3sys4Load6IsBusyE13SD_LOAD_LABEL", &busy_rx);
  const uintptr_t mount = player_commentary_roster_backing_symbol(module,
      "_ZN5sound3sys4load7Manager10GetMountIDEjPs", &mount_rx);
  uintptr_t typed = (uintptr_t)module->load_base + PC_LOOKUP_TYPED_RVA;
  uintptr_t plt = (uintptr_t)module->load_base + PC_LOOKUP_TYPED_PLT_RVA;
  const uint32_t request_guard[4] = PC_RELOAD_REQUEST_GUARD;
  const uint32_t busy_guard[4] = PC_RELOAD_BUSY_GUARD;
  const uint32_t mount_guard[4] = PC_RELOAD_MOUNT_ID_GUARD;
  const uint32_t typed_guard[4] = {0xf81c0ff8, 0xa9015bf7, 0xa90253f5, 0xa9037bf3};
  const uint32_t plt_guard[4] = {0xd002e4d0, 0xf9401e11, 0x9100e210, 0xd61f0220};
  if (!request || !busy || !mount || memcmp((void *)request, request_guard, 16) ||
      memcmp((void *)busy, busy_guard, 16) || memcmp((void *)mount, mount_guard, 16) ||
      memcmp((void *)typed, typed_guard, 16) || memcmp((void *)plt, plt_guard, 16)) {
    scene_runtime_note("player commentary", "roster ABI guard rejected; v53 retained");
    return;
  }
  const PcReloadOps ops = {player_commentary_prepare_roster,
      player_commentary_discard_roster, player_commentary_request_roster,
      player_commentary_roster_busy, player_commentary_roster_mount_id,
      player_commentary_play_valid, player_commentary_dispatch_ready,
      player_commentary_release_loading, 0u};
  if (!pc_reload_init(&player_commentary_reload, &ops, NULL, 30000u)) return;
  player_commentary_native_request = (void *)request_rx;
  player_commentary_native_busy = (void *)busy_rx;
  player_commentary_native_mount_id = (void *)mount_rx;
  player_commentary_typed_original =
      (void *)((uintptr_t)module->load_virtbase + PC_LOOKUP_TYPED_RVA);
  player_commentary_roster_clone_for_mount = player_commentary_clone_roster;
  player_commentary_roster_mount_observe = player_commentary_observe_roster;
  hook_arm64(plt, (uintptr_t)&pes_sound_player_name_label);
  player_commentary_roster_enabled = 1u;
  scene_runtime_note("player commentary", "v61 selected-roster hooks armed; unified assets; RW guards and RX call targets separated");
}
