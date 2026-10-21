#ifndef PESNX_PLAYER_COMMENTARY_LOOKUP_H
#define PESNX_PLAYER_COMMENTARY_LOOKUP_H

#include <stdint.h>
#include <string.h>
#include "player_commentary_types.h"

/* This component never calls native code or publishes mount state. The caller
 * supplies a coherent snapshot while holding its mount-policy lock, then
 * releases that lock before invoking the original accessor. Cue names belong
 * to the immutable compiled catalog, not to transient ACB/UTF buffers. */
#define PC_LOOKUP_ACCEPTED UINT32_C(0x50434c31)
#define PC_LOOKUP_BANK_KIND 29u
#define PC_LOOKUP_TYPED_PLT_RVA UINT32_C(0x03849bc0)
#define PC_LOOKUP_TYPED_RVA UINT32_C(0x06cc1140)

enum { PC_LOOKUP_ORIGINAL = 0, PC_LOOKUP_NULL = 1, PC_LOOKUP_CUE = 2 };

typedef struct {
  uint64_t carrier;
  uint32_t side;
  const PcBankOwner *owner;
} PcLookupBinding;

typedef struct {
  uint64_t generation;
  int16_t mount_id;
  uint16_t binding_count;
  uint32_t accepted;
  PcLookupBinding bindings[PC_BANK_MAX_PLAYERS];
} PcLookupSnapshot;

typedef struct {
  uint32_t action;
  const char *cue;
} PcLookupDecision;

static inline int pc_lookup_owner_in_catalog(const PcBankCatalog *catalog,
                                             const PcBankOwner *owner) {
  if (!catalog || !catalog->owners || !owner ||
      catalog->owner_count > UINT32_C(65535))
    return 0;
  const uintptr_t begin = (uintptr_t)catalog->owners;
  const uintptr_t address = (uintptr_t)owner;
  if (address < begin)
    return 0;
  const uintptr_t distance = address - begin;
  return distance % sizeof(*owner) == 0 &&
         distance / sizeof(*owner) < catalog->owner_count;
}

/* A validated catalog contains the complete identity fingerprint and exact
 * active row hash. Their contents are proven by its generator/compiled pin;
 * this bounded shape check also rejects incomplete hand-written policy rows. */
static inline int pc_lookup_hex(const char *value, uint32_t length) {
  if (!value)
    return 0;
  for (uint32_t i = 0; i < length; ++i) {
    const unsigned char c = (unsigned char)value[i];
    if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f')))
      return 0;
  }
  return value[length] == '\0';
}

static inline int pc_lookup_identity_complete(const PcBankOwner *owner) {
  return owner && owner->base_id && owner->native_id &&
         owner->native_id <= 999999u &&
         pc_lookup_hex(owner->fingerprint, 20u) &&
         pc_lookup_hex(owner->row_sha256, 64u);
}

static inline int pc_lookup_owner_mounted(const PcBankResult *bank,
                                          const PcBankOwner *owner) {
  if (!bank || bank->player_count > PC_BANK_MAX_PLAYERS)
    return 0;
  for (uint32_t i = 0; i < bank->player_count; ++i)
    if (bank->players[i] == owner)
      return 1;
  return 0;
}

static inline int pc_lookup_cue_in_catalog(const PcBankCatalog *catalog,
                                           const PcBankCue *cue) {
  if (!catalog || !catalog->cues || !cue)
    return 0;
  const uintptr_t begin = (uintptr_t)catalog->cues;
  const uintptr_t address = (uintptr_t)cue;
  if (address < begin)
    return 0;
  const uintptr_t distance = address - begin;
  return distance % sizeof(*cue) == 0 &&
         distance / sizeof(*cue) < catalog->cue_count;
}

/* Snapshot the ACTUAL registry/sound carrier, not a constructed NativeID<<32
 * and not GetPurePlayerId. Low16 is the storage locator compared by native
 * lookup; it can differ between CommonWork and Match. Preserve all 64 bits.
 * A second distinct owner for the same side/carrier invalidates admission. */
static inline int pc_lookup_bind(PcLookupSnapshot *snapshot,
                                 const PcBankCatalog *catalog,
                                 const PcBankOwner *owner, uint32_t side,
                                 uint64_t carrier) {
  if (!snapshot || snapshot->accepted || side > 1u ||
      snapshot->binding_count >= PC_BANK_MAX_PLAYERS ||
      !pc_lookup_owner_in_catalog(catalog, owner) ||
      !pc_lookup_identity_complete(owner) ||
      (uint32_t)(carrier >> 32) != owner->native_id)
    return 0;
  for (uint32_t i = 0; i < snapshot->binding_count; ++i) {
    const PcLookupBinding *old = &snapshot->bindings[i];
    if (old->side == side && old->carrier == carrier)
      return old->owner == owner;
  }
  PcLookupBinding *binding = &snapshot->bindings[snapshot->binding_count++];
  binding->carrier = carrier;
  binding->side = side;
  binding->owner = owner;
  return 1;
}

/* Call only AFTER successful native mount. The caller separately owns the
 * bank buffer and any request/mount leases. No audio or generation is made
 * accepted merely by constructing a snapshot. */
static inline int pc_lookup_accept(PcLookupSnapshot *snapshot,
                                   const PcBankCatalog *catalog,
                                   const PcBankResult *bank,
                                   uint64_t generation, int16_t mount_id,
                                   uint32_t bank_kind) {
  if (!snapshot || snapshot->accepted || !generation || mount_id < 0 ||
      bank_kind != PC_LOOKUP_BANK_KIND || !bank || !bank->data || !bank->size ||
      bank->size > PC_BANK_MAX_BYTES ||
      bank->player_count > PC_BANK_MAX_PLAYERS ||
      bank->cue_count > PC_BANK_MAX_CUES ||
      bank->header_count > PC_BANK_MAX_HEADERS ||
      snapshot->binding_count > PC_BANK_MAX_PLAYERS)
    return 0;
  for (uint32_t i = 0; i < snapshot->binding_count; ++i) {
    const PcLookupBinding *binding = &snapshot->bindings[i];
    if (binding->side > 1u ||
        !pc_lookup_owner_in_catalog(catalog, binding->owner) ||
        !pc_lookup_identity_complete(binding->owner) ||
        (uint32_t)(binding->carrier >> 32) != binding->owner->native_id ||
        !pc_lookup_owner_mounted(bank, binding->owner))
      return 0;
  }
  snapshot->generation = generation;
  snapshot->mount_id = mount_id;
  snapshot->accepted = PC_LOOKUP_ACCEPTED;
  return 1;
}

static inline int pc_lookup_own_p0_name(const char *name, uint32_t type,
                                        uint32_t native_id) {
  if (!name || (type != 0u && type != 24u) || !native_id || native_id > 999999u)
    return 0;
  const char *prefix = type == 0u ? "EN_A1_P0_R" : "EN_B1_P0_R";
  for (uint32_t i = 0; i < 10u; ++i)
    if (!name[i] || name[i] != prefix[i])
      return 0;
  uint32_t actual = 0;
  for (uint32_t i = 10u; i < 16u; ++i) {
    const unsigned char c = (unsigned char)name[i];
    if (c < '0' || c > '9')
      return 0;
    actual = actual * 10u + (uint32_t)(c - '0');
  }
  return name[16] == '\0' && actual == native_id;
}

static inline PcLookupDecision pc_lookup_decide(
    const PcBankCatalog *catalog, const PcBankResult *bank,
    const PcLookupSnapshot *snapshot, uint64_t current_generation,
    int16_t current_mount_id, uint32_t current_bank_kind, uint32_t side,
    const uint64_t *carrier_ptr, uint32_t type) {
  const PcLookupDecision original = {PC_LOOKUP_ORIGINAL, NULL};
  const PcLookupDecision missing = {PC_LOOKUP_NULL, NULL};
  /* Compatibility fallback is intentional: an unavailable optional bank or
   * inactive generation preserves the unmodified native lookup. It cannot be
   * reported as correcting inherited wrong names for that failed mount. */
  if (!snapshot || snapshot->accepted != PC_LOOKUP_ACCEPTED ||
      !current_generation || snapshot->generation != current_generation ||
      snapshot->mount_id != current_mount_id ||
      current_bank_kind != PC_LOOKUP_BANK_KIND)
    return original;
  if (side > 1u || !carrier_ptr || type > 29u || !catalog || !bank ||
      snapshot->binding_count > PC_BANK_MAX_PLAYERS ||
      bank->player_count > PC_BANK_MAX_PLAYERS ||
      bank->cue_count > PC_BANK_MAX_CUES ||
      bank->header_count > PC_BANK_MAX_HEADERS)
    return missing;
  uint64_t carrier;
  memcpy(&carrier, carrier_ptr, sizeof(carrier));
  const PcBankOwner *owner = NULL;
  for (uint32_t i = 0; i < snapshot->binding_count; ++i) {
    const PcLookupBinding *binding = &snapshot->bindings[i];
    if (binding->side != side || binding->carrier != carrier)
      continue;
    if (owner && owner != binding->owner)
      return missing;
    owner = binding->owner;
  }
  if (!pc_lookup_owner_in_catalog(catalog, owner) ||
      !pc_lookup_identity_complete(owner) ||
      (uint32_t)(carrier >> 32) != owner->native_id ||
      !pc_lookup_owner_mounted(bank, owner))
    return missing;
  if (owner->status == PC_OWNER_NATIVE || owner->status == PC_OWNER_CANARY)
    return original;
  if (owner->status != PC_OWNER_NEW || (type != 0u && type != 24u))
    return missing;
  /* Six-digit staging is not proof for >18-bit native IDs. Keep every such
   * new owner held until a separately accepted registry/translation contract
   * explicitly supersedes this policy. Never use its masked-ID donor cue. */
  if (owner->native_id > UINT32_C(0x3ffff))
    return missing;
  const PcBankCue *selected = NULL;
  for (uint32_t i = 0; i < bank->cue_count; ++i) {
    const PcBankCue *cue = bank->cues[i];
    if (!pc_lookup_cue_in_catalog(catalog, cue))
      return missing;
    if (cue->owner_index >= catalog->owner_count ||
        &catalog->owners[cue->owner_index] != owner || cue->type != type)
      continue;
    if (!pc_lookup_own_p0_name(cue->name, type, owner->native_id) ||
        !cue->header_fnv || !cue->payload_fnv)
      return missing;
    if (selected && selected != cue)
      return missing;
    selected = cue;
  }
  if (!selected)
    return missing;
  const PcLookupDecision named = {PC_LOOKUP_CUE, selected->name};
  return named;
}

#endif
