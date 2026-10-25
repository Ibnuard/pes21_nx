#ifndef PES21_FIXDEMO_CEREMONY_POLICY_H
#define PES21_FIXDEMO_CEREMONY_POLICY_H

#include <stdint.h>
#include <string.h>

/* Planning only. These values are not permission to create or replace a scene.
 * Match phase is match::MatchPhase, not a result-page or MatchTop state. */
enum {
  FIXDEMO_CEREMONY_PHASE_END = 10u,
  FIXDEMO_CEREMONY_RESULT_SCENE = 0x80001u,
  FIXDEMO_CEREMONY_NEUTRAL_SIDE = 2u,
  FIXDEMO_CEREMONY_TROPHY_SCENE = 0x70007u
};

enum {
  FIXDEMO_CEREMONY_BOUNDARY_RESULT = 0u,
  FIXDEMO_CEREMONY_BOUNDARY_ENDING_FACTORY = 1u,
  FIXDEMO_CEREMONY_BOUNDARY_LISTENER_RESULT = 2u
};

/* All native_*_team fields below contain logical catalog IDs in native
 * HOME/AWAY order, never raw physical native IDs (physical_team_id << 14).
 * The integration must verify the observed native IDs against the established
 * logical-to-physical mapping AND native HOME/AWAY storage locators before
 * publishing a fresh logical-ID snapshot. */
typedef struct {
  uint64_t match_token;
  uint32_t native_home_team;
  uint32_t native_away_team;
  /* Exactly 1 only when competition_frontend_cup_live_final_context() succeeds
   * at this invocation.
   * A saved champion, old trophy context or previous successful query is not
   * live evidence. Leave zero if the frontend context cannot be read now. */
  uint32_t live_cup_final_fresh;
} FixdemoCeremonyContext;

typedef struct {
  uint64_t match_token;
  uint32_t native_home_team;
  uint32_t native_away_team;
  uint32_t phase;
  uint32_t original_scene;
  uint32_t original_side;
  /* Exactly 1 after reading phase, teams and match goals together at the
   * result/ending-factory boundary. Cached pause/result totals are never a source. */
  uint32_t fresh;
  /* Exactly 1 only for the exact audited caller identity. The integration
   * boundary must validate the caller; this pure policy has no native PCs. */
  uint32_t caller_verified;
  int32_t home_goals;
  int32_t away_goals;
  /* Separate, current-match shootout-only scores; never goal+PK totals. */
  uint32_t shootout_fresh;
  uint32_t shootout_only;
  int32_t home_shootout;
  int32_t away_shootout;
  /* Distinct audited factories; the original Result gate remains unchanged.
   * ENDING_FACTORY additionally requires the requested scene/side to match
   * this invocation's native MatchInfo ending request under a fresh read. */
  uint32_t boundary;
  uint32_t native_request_verified;
} FixdemoCeremonySnapshot;

typedef struct {
  uint64_t match_token;
  uint32_t consumed;
} FixdemoCeremonyLatch;

typedef struct {
  uint64_t match_token;
  uint32_t native_home_team;
  uint32_t native_away_team;
  uint32_t scene;
  uint32_t winner_side; /* Native HOME=0, AWAY=1. */
} FixdemoCeremonyPlan;

/* Caller owns one zero-initialized latch for the session. Advance it only at
 * a real new-match boundary with a strictly increasing, nonzero token. Never
 * reinitialize it on result callbacks: the same token cannot rearm a success. */
static inline int fixdemo_ceremony_begin_match(FixdemoCeremonyLatch *latch,
                                               uint64_t match_token) {
  if (!latch || !match_token || latch->consumed > 1u ||
      match_token <= latch->match_token)
    return 0;
  latch->match_token = match_token;
  latch->consumed = 0u;
  return 1;
}

static inline int fixdemo_ceremony_score_valid(int32_t score) {
  return score >= 0 && score <= 99;
}

static inline int fixdemo_ceremony_boundary_valid(
    const FixdemoCeremonySnapshot *snapshot) {
  if (snapshot->boundary == FIXDEMO_CEREMONY_BOUNDARY_RESULT)
    return snapshot->original_scene == FIXDEMO_CEREMONY_RESULT_SCENE &&
           snapshot->original_side == FIXDEMO_CEREMONY_NEUTRAL_SIDE;
  /* MatchHalfTimeDemo also owns the full-time result background. Its audited
   * factory passes MatchInfo.result-side, which must be freshly verified.
   * END phase and live Cup-final evidence below still exclude halftime. */
  if (snapshot->boundary == FIXDEMO_CEREMONY_BOUNDARY_LISTENER_RESULT)
    return snapshot->native_request_verified == 1u &&
           snapshot->original_scene == FIXDEMO_CEREMONY_RESULT_SCENE &&
           snapshot->original_side <= FIXDEMO_CEREMONY_NEUTRAL_SIDE;
  if (snapshot->boundary != FIXDEMO_CEREMONY_BOUNDARY_ENDING_FACTORY ||
      snapshot->native_request_verified != 1u ||
      snapshot->original_side > FIXDEMO_CEREMONY_NEUTRAL_SIDE)
    return 0;
  /* Native GetFullTimeDemo/GetPkEndDemo select ending scenes in these two
   * groups. Group membership alone never establishes the ending boundary:
   * exact caller, current request, END phase and live final are also required. */
  const uint32_t group = snapshot->original_scene >> 16;
  return (group == 6u || group == 7u) &&
         (snapshot->original_scene & 0xffffu) != 0u;
}

/* Pure gate: reads caller-owned evidence and produces a plan, with no native
 * calls, scene creation, latch consumption or competition/save writes. The
 * caller must serialize planning, backend execution and success acknowledgement.
 * A rejected request clears the output so it cannot reuse an earlier plan. */
static inline int fixdemo_ceremony_plan(
    const FixdemoCeremonyContext *context,
    const FixdemoCeremonySnapshot *snapshot,
    const FixdemoCeremonyLatch *latch, FixdemoCeremonyPlan *plan) {
  if (!plan) return 0;
  memset(plan, 0, sizeof(*plan));
  if (!context || !snapshot || !latch || !context->match_token ||
      context->live_cup_final_fresh != 1u || !context->native_home_team ||
      !context->native_away_team ||
      context->native_home_team == context->native_away_team ||
      snapshot->fresh != 1u || snapshot->caller_verified != 1u ||
      snapshot->phase != FIXDEMO_CEREMONY_PHASE_END ||
      !fixdemo_ceremony_boundary_valid(snapshot) ||
      snapshot->match_token != context->match_token ||
      snapshot->native_home_team != context->native_home_team ||
      snapshot->native_away_team != context->native_away_team ||
      latch->match_token != context->match_token || latch->consumed != 0u ||
      !fixdemo_ceremony_score_valid(snapshot->home_goals) ||
      !fixdemo_ceremony_score_valid(snapshot->away_goals) ||
      snapshot->shootout_fresh > 1u || snapshot->shootout_only > 1u ||
      (snapshot->shootout_fresh == 1u &&
       (snapshot->shootout_only != 1u ||
        !fixdemo_ceremony_score_valid(snapshot->home_shootout) ||
        !fixdemo_ceremony_score_valid(snapshot->away_shootout))))
    return 0;

  uint32_t winner = snapshot->home_goals > snapshot->away_goals ? 0u : 1u;
  if (snapshot->home_goals == snapshot->away_goals) {
    if (snapshot->shootout_fresh != 1u ||
        snapshot->home_shootout == snapshot->away_shootout)
      return 0;
    winner = snapshot->home_shootout > snapshot->away_shootout ? 0u : 1u;
  }
  plan->match_token = context->match_token;
  plan->native_home_team = context->native_home_team;
  plan->native_away_team = context->native_away_team;
  plan->scene = FIXDEMO_CEREMONY_TROPHY_SCENE;
  plan->winner_side = winner;
  return 1;
}

/* Call only with the plan that the backend just executed. A backend failure
 * (including unknown status) leaves the latch retryable. Allocating an object
 * is not proof of successful scene execution or a working renderer. */
static inline int fixdemo_ceremony_backend_result(
    FixdemoCeremonyLatch *latch, const FixdemoCeremonyPlan *plan,
    int backend_succeeded) {
  if (!latch || !plan || backend_succeeded != 1 || !plan->match_token ||
      plan->match_token != latch->match_token || latch->consumed != 0u ||
      plan->scene != FIXDEMO_CEREMONY_TROPHY_SCENE || plan->winner_side > 1u ||
      !plan->native_home_team || !plan->native_away_team ||
      plan->native_home_team == plan->native_away_team)
    return 0;
  latch->consumed = 1u;
  return 1;
}

#endif
