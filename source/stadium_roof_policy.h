#ifndef PES_STADIUM_ROOF_POLICY_H
#define PES_STADIUM_ROOF_POLICY_H

#include <stdint.h>
#include <stddef.h>
#include <string.h>

// Exact native asset identities, not a substring such as "roof" or "frame".
// The audited bounds put these meshes above the playing field. Backface,
// stands, goal frames, players and unknown stadiums remain native.
static inline uint32_t stadium_roof_mesh_id(const uint16_t *path, int32_t count) {
  static const char *const paths[] = {
    "/Game/Assets/bg_lighting_AM1/Meshes/st029_c.st029_c",
    "/Game/Assets/bg_lighting_AM1/Meshes/st029_c_glass.st029_c_glass",
  };
  if (!path || count <= 1 || count > 256) return 0;
  for (unsigned n = 0; n < sizeof(paths) / sizeof(paths[0]); ++n) {
    const size_t len = strlen(paths[n]);
    if ((size_t)count != len + 1 || path[len] != 0) continue;
    size_t i = 0;
    for (; i < len && path[i] == (unsigned char)paths[n][i]; ++i) {}
    if (i == len) return n + 1;
  }
  return 0;
}

// Creation happens on the game thread; shadow queries/destruction may happen
// on a render worker. Never retain or dereference a UObject on that worker.
// Exhaustion fails open. Destruction and non-roof address reuse clear entries.
#define STADIUM_ROOF_PROXY_SLOTS 32
typedef struct { uintptr_t slots[STADIUM_ROOF_PROXY_SLOTS]; } StadiumRoofProxies;

static inline void stadium_roof_forget(StadiumRoofProxies *p, uintptr_t proxy) {
  if (!proxy) return;
  for (unsigned i = 0; i < STADIUM_ROOF_PROXY_SLOTS; ++i) {
    uintptr_t expected = proxy;
    __atomic_compare_exchange_n(&p->slots[i], &expected, 0, 0,
                                __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE);
  }
}

static inline int stadium_roof_contains(const StadiumRoofProxies *p,
                                        uintptr_t proxy) {
  if (!proxy) return 0;
  for (unsigned i = 0; i < STADIUM_ROOF_PROXY_SLOTS; ++i)
    if (__atomic_load_n(&p->slots[i], __ATOMIC_ACQUIRE) == proxy) return 1;
  return 0;
}

static inline int stadium_roof_remember(StadiumRoofProxies *p, uintptr_t proxy) {
  if (!proxy) return 0;
  if (stadium_roof_contains(p, proxy)) return 1;
  for (unsigned i = 0; i < STADIUM_ROOF_PROXY_SLOTS; ++i) {
    uintptr_t expected = 0;
    if (__atomic_compare_exchange_n(&p->slots[i], &expected, proxy, 0,
                                    __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE)) return 1;
  }
  return 0;
}

#endif
