#ifndef PES_STADIUM_SHADOW_BUDGET_H
#define PES_STADIUM_SHADOW_BUDGET_H
#include <stdint.h>

typedef struct {
  int owned, baseline, applied;
  uint32_t priority;
} StadiumShadowBudget;

typedef struct {
  const char *name;
  int cap;
} StadiumShadowLimit;

// High Day uses the shared analytic roof receiver, eliminating CSM passes.
// Other presets/time restore the native value. Resolution remains native.
static const StadiumShadowLimit stadium_shadow_limits[] = {
  {"r.Shadow.MaxCSMResolution", -1},
  {"r.Shadow.MaxResolution", -1},
  {"r.Shadow.CSM.MaxCascades", 0},
};
#define STADIUM_SHADOW_LIMIT_COUNT \
  (sizeof(stadium_shadow_limits) / sizeof(stadium_shadow_limits[0]))

// Returns the desired value without claiming ownership until the native
// setter succeeds. Respect an external quality change and never raise a
// lower native resolution. Restoring Night cannot overwrite a newer value.
static inline int stadium_shadow_budget_target(StadiumShadowBudget *s,
    int day, int current, uint32_t priority, int cap) {
  if (s->owned && (current != s->applied || priority != s->priority))
    s->owned = 0;
  if (!day) return s->owned ? s->baseline : current;
  const int native = s->owned ? s->baseline : current;
  return cap >= 0 && native > cap ? cap : native;
}
static inline void stadium_shadow_budget_applied(StadiumShadowBudget *s,
    int day, int before, int after, uint32_t priority, int cap) {
  const int native = s->owned ? s->baseline : before;
  if (day && cap >= 0 && native > cap && after == cap) {
    if (!s->owned || before != s->applied || priority != s->priority)
      s->baseline = before;
    s->applied = after;
    s->priority = priority;
    s->owned = 1;
  } else if (!day && s->owned && after == s->baseline) s->owned = 0;
}
#endif
