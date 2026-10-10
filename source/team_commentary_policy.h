/* Optional local audio delta; no game audio is linked into the wrapper. */
#ifndef PESNX_TEAM_COMMENTARY_POLICY_H
#define PESNX_TEAM_COMMENTARY_POLICY_H

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "runtime_assets.h"

#define TEAM_COMMENTARY_MAX_BANK (8u * 1024u * 1024u)
#define TEAM_COMMENTARY_MAX_PATCH (1024u * 1024u)

static inline int team_commentary_is_team_bank(const char *path) {
  if (!path)
    return 0;
  const char *name = strrchr(path, '/');
  return !strcmp(name ? name + 1 : path, "00_TEAM.awb");
}

static inline uint32_t team_commentary_name_id(uint32_t native_id,
                                               uint32_t indonesia_slot,
                                               uint32_t edited) {
  return indonesia_slot && !edited && native_id == 1164u ? 5750u : native_id;
}

static inline uint32_t team_commentary_read_u32(const unsigned char *p) {
  return (uint32_t)p[0] | (uint32_t)p[1] << 8 |
         (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

static inline uint64_t team_commentary_read_u64(const unsigned char *p) {
  return (uint64_t)team_commentary_read_u32(p) |
         (uint64_t)team_commentary_read_u32(p + 4) << 32;
}

static inline uint64_t team_commentary_hash(const void *data, uint32_t size) {
  const unsigned char *p = data;
  uint64_t value = UINT64_C(0xcbf29ce484222325);
  for (uint32_t i = 0; i < size; ++i)
    value = (value ^ p[i]) * UINT64_C(0x100000001b3);
  return value;
}

/* Metadata fingerprints of the two audited, unencrypted Indonesia HCA
 * headers (A1/B1). No audio payload or decryption key is embedded here.
 * CRI can present the 96-byte header across two input spans. Incomplete,
 * unrelated and encrypted headers must retain native decoder behavior. */
static inline int team_commentary_plain_hca_header(
    const void *first, int64_t first_size, const void *second,
    int64_t second_size) {
  if (first_size < 0 || second_size < 0)
    return 0;
  const uint32_t n = first ? (first_size < 96 ? (uint32_t)first_size : 96u) : 0u;
  if (n < 96u && (!second || second_size < (int64_t)(96u - n)))
    return 0;
  unsigned char header[96];
  if (n) memcpy(header, first, n);
  if (n < 96u) memcpy(header + n, second, 96u - n);
  const uint64_t hash = team_commentary_hash(header, sizeof(header));
  return hash == UINT64_C(0x1f86aac769aae1cb) ||
         hash == UINT64_C(0xcc0f25261657da3f);
}

/* Checksums bind a delta to the exact installed bank and catch damaged SD
 * copies. Every patch range is bounded before allocating/writing the bank. */
static inline void *team_commentary_apply_delta(
    const void *base, uint32_t base_size, const unsigned char *patch,
    uint32_t patch_size, uint32_t *result_size) {
  if (result_size)
    *result_size = 0;
  if (!base || !patch || !result_size || base_size < 32u ||
      base_size > TEAM_COMMENTARY_MAX_BANK || patch_size < 40u ||
      patch_size > TEAM_COMMENTARY_MAX_PATCH ||
      memcmp(patch, "NXCMT01\0", 8) || memcmp(base, "@UTF", 4) ||
      team_commentary_read_u32(patch + 8) != base_size ||
      team_commentary_read_u32(patch + 36) != 0u)
    return NULL;
  const uint32_t size = team_commentary_read_u32(patch + 12);
  const uint32_t count = team_commentary_read_u32(patch + 32);
  if (size < base_size || size > TEAM_COMMENTARY_MAX_BANK ||
      !count || count > 64u)
    return NULL;
  uint32_t cursor = 40u, previous_end = 0;
  for (uint32_t i = 0; i < count; ++i) {
    if (patch_size - cursor < 8u)
      return NULL;
    const uint32_t offset = team_commentary_read_u32(patch + cursor);
    const uint32_t length = team_commentary_read_u32(patch + cursor + 4);
    cursor += 8u;
    if (!length || offset < previous_end || offset > size ||
        length > size - offset || length > patch_size - cursor)
      return NULL;
    previous_end = offset + length;
    cursor += length;
  }
  if (cursor != patch_size || team_commentary_hash(base, base_size) !=
                              team_commentary_read_u64(patch + 16))
    return NULL;
  unsigned char *result = calloc(1, size);
  if (!result)
    return NULL;
  memcpy(result, base, base_size);
  cursor = 40u;
  for (uint32_t i = 0; i < count; ++i) {
    const uint32_t offset = team_commentary_read_u32(patch + cursor);
    const uint32_t length = team_commentary_read_u32(patch + cursor + 4);
    cursor += 8u;
    memcpy(result + offset, patch + cursor, length);
    cursor += length;
  }
  const uint32_t utf_size = (uint32_t)result[4] << 24 |
      (uint32_t)result[5] << 16 | (uint32_t)result[6] << 8 | result[7];
  if (memcmp(result, "@UTF", 4) || utf_size != size - 8u ||
      team_commentary_hash(result, size) != team_commentary_read_u64(patch + 24)) {
    free(result);
    return NULL;
  }
  *result_size = size;
  return result;
}

static inline void *team_commentary_load_delta(const void *base,
    uint32_t base_size, const char *path, uint32_t *result_size) {
  if (!result_size)
    return NULL;
  *result_size = 0;
  size_t length = 0;
  unsigned char *patch = nx_asset_read(path, TEAM_COMMENTARY_MAX_PATCH, &length);
  void *result = patch ? team_commentary_apply_delta(base, base_size, patch,
                                       (uint32_t)length, result_size) : NULL;
  free(patch);
  return result;
}

#endif
