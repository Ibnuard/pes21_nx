#ifndef PES_STADIUM_CAMERA_POLICY_H
#define PES_STADIUM_CAMERA_POLICY_H

#include <math.h>
#include <stdint.h>
#include <string.h>

/* Acquisition only. The native Stadium pipeline still computes its screen
 * margins, pan/trace state, bounds, height, zoom and final camera transform.
 * This scope never stores a ball/registry pointer or motion history. */
typedef struct {
  uintptr_t owner;
  unsigned active;
} PesStadiumTargetScope;

static inline void pes_stadium_target_scope_begin(PesStadiumTargetScope *scope,
    uintptr_t owner, unsigned camera_id, unsigned tmpdb_type, unsigned v2,
    unsigned follow_player, unsigned live_surface) {
  if (!scope) return;
  scope->owner = owner;
  scope->active = owner && camera_id == 6u && tmpdb_type == 12u && !v2 &&
      !follow_player && live_surface;
}

static inline void pes_stadium_target_scope_end(PesStadiumTargetScope *scope) {
  if (scope) {
    scope->active = 0;
    scope->owner = 0;
  }
}

/* Called after the engine has acquired its contextual target and sampled
 * BallInfo::GetTrans, before target height/projection/optics are calculated.
 * Replace only that target's three floats with the actual sampled ball.
 * Invalid samples fall back to the untouched native result for this update. */
static inline int pes_stadium_target_correct(PesStadiumTargetScope *scope,
    uintptr_t owner, unsigned current_match_phase, float *target,
    const float *sampled_ball) {
  if (!scope || !scope->active || scope->owner != owner) return 0;
  /* MatchInfo is refreshed/locked by native Update after scope entry.
   * Read its current phase at this boundary, never borrow yesterday's copy
   * before native Update has acquired the registry. */
  if (current_match_phase != 1u || !target || !sampled_ball ||
      !isfinite(sampled_ball[0]) || !isfinite(sampled_ball[1]) ||
      !isfinite(sampled_ball[2]) || fabsf(sampled_ball[0]) > 65.f ||
      fabsf(sampled_ball[2]) > 44.f || sampled_ball[1] < -3.f ||
      sampled_ball[1] > 60.f) {
    pes_stadium_target_scope_end(scope);
    return 0;
  }
  memmove(target, sampled_ball, 3u * sizeof(float));
  return 1;
}

#endif
