#ifndef PESNX_EXHIBITION_MATCH_IDENTITY_H
#define PESNX_EXHIBITION_MATCH_IDENTITY_H
#include <stdint.h>

/* SetExhibitionTeamId preserves the physical identity in bits 14..31 and
 * replaces the storage locator with 0x3ffd (HOME) or 0x3ffe (AWAY).
 * A match-local key must not be compared directly with a master key whose
 * locator is zero. Require both the identity AND the correct native side. */
static inline int exhibition_match_team_identity(uint32_t match_key,
    uint32_t master_key, uint32_t side) {
  return side < 2u && master_key && !(master_key & 0x3fffu) &&
      match_key == (master_key | (0x3ffdu + side));
}
#endif
