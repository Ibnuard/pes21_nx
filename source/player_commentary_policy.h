#ifndef PESNX_PLAYER_COMMENTARY_POLICY_H
#define PESNX_PLAYER_COMMENTARY_POLICY_H

#include "team_commentary_policy.h"
#include "player_commentary_catalog.h"
#include "player_commentary_lookup.h"

/* Growing a player bank relocates its UTF tables. A separate, explicit 8-MiB
 * delta limit permits that rebuild; the team delta remains capped at 1 MiB. */
#define PLAYER_COMMENTARY_MAX_PATCH (8u * 1024u * 1024u)

static inline int player_commentary_catalog_active(const char *runtime_pair) {
  return runtime_pair && PLAYER_COMMENTARY_BASE_BYTES &&
      !strcmp(runtime_pair, PLAYER_COMMENTARY_RUNTIME_PAIR);
}

static inline int player_commentary_is_bank(const char *path) {
  if (!path) return 0;
  const char *name = strrchr(path, '/');
  return !strcmp(name ? name + 1 : path, "10_PLAYER.awb");
}

/* Only current audited plaintext header fingerprints, while a player delta
 * is actually mounted, may clear an instance's inherited HCA cipher table. */
static inline int player_commentary_plain_hca_header(
    const void *first, int64_t first_size, const void *second,
    int64_t second_size) {
  if (first_size < 0 || second_size < 0) return 0;
  const uint32_t count = first ? (first_size < 96 ? (uint32_t)first_size : 96u) : 0u;
  if (count < 96u && (!second || second_size < (int64_t)(96u - count))) return 0;
  unsigned char header[96];
  if (count) memcpy(header, first, count);
  if (count < 96u) memcpy(header + count, second, 96u - count);
  const uint64_t hash = team_commentary_hash(header, sizeof(header));
  for (size_t i = 0; i < sizeof(player_commentary_plain_headers) /
                                  sizeof(player_commentary_plain_headers[0]); ++i)
    if (hash == player_commentary_plain_headers[i]) return 1;
  return 0;
}

static inline void *player_commentary_apply_delta(
    const void *base, uint32_t base_size, const unsigned char *patch,
    uint32_t patch_size, uint32_t *result_size) {
  if (result_size) *result_size = 0;
  /* The compatibility catalog pins the audited base, result and patch, rather
   * than trusting a self-consistent but unrelated delta supplied on the SD. */
  if (!base || !patch || !result_size || patch_size < 40u ||
      patch_size > PLAYER_COMMENTARY_MAX_PATCH ||
      base_size != PLAYER_COMMENTARY_BASE_BYTES ||
      patch_size != PLAYER_COMMENTARY_PATCH_BYTES ||
      team_commentary_read_u32(patch + 12) != PLAYER_COMMENTARY_RESULT_BYTES ||
      team_commentary_read_u64(patch + 16) != PLAYER_COMMENTARY_BASE_FNV ||
      team_commentary_read_u64(patch + 24) != PLAYER_COMMENTARY_RESULT_FNV ||
      team_commentary_hash(patch, patch_size) != PLAYER_COMMENTARY_PATCH_FNV)
    return NULL;
  return commentary_apply_delta_bounded(base, base_size, patch, patch_size,
                                         PLAYER_COMMENTARY_MAX_PATCH, result_size);
}

static inline void *player_commentary_load_delta(
    const void *base, uint32_t base_size, uint32_t *result_size) {
  if (!result_size) return NULL;
  *result_size = 0;
  if (base_size != PLAYER_COMMENTARY_BASE_BYTES) return NULL;
  size_t size = 0;
  unsigned char *patch = nx_asset_read("Commentary/players-v53.nxcp",
                                      PLAYER_COMMENTARY_MAX_PATCH, &size);
  void *result = patch ? player_commentary_apply_delta(base, base_size, patch,
                                        (uint32_t)size, result_size) : NULL;
  free(patch);
  return result;
}

#endif
