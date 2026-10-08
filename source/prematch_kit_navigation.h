#ifndef PES_PREMATCH_KIT_NAVIGATION_H
#define PES_PREMATCH_KIT_NAVIGATION_H

#include <stdint.h>

typedef struct { uint32_t side, editing; } PesKitNavigation;
enum { PES_KIT_STAY, PES_KIT_PREVIOUS, PES_KIT_NEXT, PES_KIT_BACK };

/* Controller edge input only. Container selection and kit adjustment are
 * separate levels; up/down must never silently select the other player. */
static inline uint32_t pes_kit_navigate(PesKitNavigation *nav, uint32_t pressed) {
  nav->side &= 1u;
  if (pressed & (1u << 0)) {
    if (nav->editing) nav->editing = 0u;
    else return PES_KIT_BACK;
  } else if (pressed & (1u << 1)) {
    nav->editing = 1u;
  } else if (pressed & ((1u << 12) | (1u << 13))) {
    if (nav->editing)
      return (pressed & (1u << 12)) ? PES_KIT_PREVIOUS : PES_KIT_NEXT;
    nav->side = (pressed & (1u << 12)) ? 0u : 1u;
  }
  return PES_KIT_STAY;
}

#endif
