#ifndef PES_STADIUM_DIAGNOSTIC_POLICY_H
#define PES_STADIUM_DIAGNOSTIC_POLICY_H
#include <stdint.h>
#include <string.h>

// Read-only probe policy. Included only in diagnostic builds at runtime.
typedef struct {
  uint64_t last_ns;
  uintptr_t owner;
  uint32_t state;
  int seen;
} StadiumDiagnosticGate;

static inline int stadium_diagnostic_due(StadiumDiagnosticGate *gate, uint64_t now,
                                   uintptr_t owner, uint32_t state,
                                   uint64_t interval) {
  if (gate->seen && gate->owner == owner && gate->state == state &&
      now >= gate->last_ns && now - gate->last_ns < interval)
    return 0;
  gate->last_ns = now;
  gate->owner = owner;
  gate->state = state;
  gate->seen = 1;
  return 1;
}

static inline uint32_t stadium_diagnostic_hash(const char *source) {
  uint32_t hash = 2166136261u;
  for (const unsigned char *p = (const unsigned char *)source; *p; ++p) {
    if (*p == ' ' || *p == '\r' || *p == '\n' || *p == '\t') continue;
    hash = (hash ^ *p) * 16777619u;
  }
  return hash;
}

// These are source features, not a claim that a sampler contains roof shadows.
static inline unsigned stadium_diagnostic_features(const char *source) {
  return (strstr(source, "nxRoofDisabled") ? 1u : 0u) |
         (strstr(source, "MobileDirectionalLight") ? 2u : 0u) |
         (strstr(source, "texture(ps1,in_TEXCOORD0.zw)") ? 4u : 0u);
}
#endif
