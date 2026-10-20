#include <assert.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>

#include "fixdemo_ceremony_policy.h"

static const FixdemoCeremonyContext live_final = {
  .match_token = 41u,
  .native_home_team = 101u,
  .native_away_team = 107u,
  .live_cup_final_fresh = 1u
};

static const FixdemoCeremonySnapshot full_time = {
  .match_token = 41u,
  .native_home_team = 101u,
  .native_away_team = 107u,
  .phase = FIXDEMO_CEREMONY_PHASE_END,
  .original_scene = FIXDEMO_CEREMONY_RESULT_SCENE,
  .original_side = FIXDEMO_CEREMONY_NEUTRAL_SIDE,
  .fresh = 1u,
  .caller_verified = 1u,
  .home_goals = 2,
  .away_goals = 1
};

static const FixdemoCeremonyLatch ready = { .match_token = 41u };

static void rejected(const FixdemoCeremonyContext *context,
                     const FixdemoCeremonySnapshot *snapshot,
                     const FixdemoCeremonyLatch *latch) {
  FixdemoCeremonyPlan plan;
  const FixdemoCeremonyPlan empty = {0};
  memset(&plan, 0xa5, sizeof(plan));
  assert(!fixdemo_ceremony_plan(context, snapshot, latch, &plan));
  assert(!memcmp(&plan, &empty, sizeof(plan)));
}

static FixdemoCeremonyPlan accepted(const FixdemoCeremonyContext *context,
                                    const FixdemoCeremonySnapshot *snapshot,
                                    const FixdemoCeremonyLatch *latch,
                                    uint32_t winner_side) {
  const FixdemoCeremonyContext before_context = *context;
  const FixdemoCeremonySnapshot before_snapshot = *snapshot;
  const FixdemoCeremonyLatch before_latch = *latch;
  FixdemoCeremonyPlan plan;
  assert(fixdemo_ceremony_plan(context, snapshot, latch, &plan));
  assert(plan.match_token == context->match_token);
  assert(plan.native_home_team == context->native_home_team);
  assert(plan.native_away_team == context->native_away_team);
  assert(plan.scene == 0x70007u && plan.winner_side == winner_side);
  assert(!memcmp(&before_context, context, sizeof(*context)));
  assert(!memcmp(&before_snapshot, snapshot, sizeof(*snapshot)));
  assert(!memcmp(&before_latch, latch, sizeof(*latch)));
  return plan;
}

static void check_result_boundary(void) {
  accepted(&live_final, &full_time, &ready, 0u);
  /* Actual MatchPhase values: halftime=2, ET=4/6, pre-PK=8, PK=9.
   * The same scene/neutral side at any of these is not a final result. */
  for (uint32_t phase = 0u; phase <= 11u; phase++) {
    if (phase == 10u) continue;
    FixdemoCeremonySnapshot snapshot = full_time;
    snapshot.phase = phase;
    rejected(&live_final, &snapshot, &ready);
  }
  FixdemoCeremonySnapshot snapshot = full_time;
  snapshot.phase = UINT32_MAX;
  rejected(&live_final, &snapshot, &ready);
  const uint32_t scenes[] = {0u, 0x10001u, 0x70001u, 0x70002u, 0x70007u, 0x80002u};
  for (uint32_t i = 0u; i < sizeof(scenes) / sizeof(scenes[0]); i++) {
    snapshot = full_time;
    snapshot.original_scene = scenes[i];
    rejected(&live_final, &snapshot, &ready);
  }
  const uint32_t sides[] = {0u, 1u, 3u, UINT32_MAX};
  for (uint32_t i = 0u; i < sizeof(sides) / sizeof(sides[0]); i++) {
    snapshot = full_time;
    snapshot.original_side = sides[i];
    rejected(&live_final, &snapshot, &ready);
  }
  const uint32_t unknown[] = {0u, 2u, UINT32_MAX};
  for (uint32_t i = 0u; i < sizeof(unknown) / sizeof(unknown[0]); i++) {
    snapshot = full_time;
    snapshot.fresh = unknown[i];
    rejected(&live_final, &snapshot, &ready);
    snapshot = full_time;
    snapshot.caller_verified = unknown[i];
    rejected(&live_final, &snapshot, &ready);
    FixdemoCeremonyContext context = live_final;
    context.live_cup_final_fresh = unknown[i];
    rejected(&context, &full_time, &ready);
  }
  rejected(NULL, &full_time, &ready);
  rejected(&live_final, NULL, &ready);
  rejected(&live_final, &full_time, NULL);
  assert(!fixdemo_ceremony_plan(&live_final, &full_time, &ready, NULL));
}

static void check_match_identity(void) {
  const uint64_t tokens[] = {0u, 40u, 42u, UINT64_MAX};
  for (uint32_t i = 0u; i < sizeof(tokens) / sizeof(tokens[0]); i++) {
    FixdemoCeremonyContext context = live_final;
    context.match_token = tokens[i];
    rejected(&context, &full_time, &ready);
    FixdemoCeremonySnapshot snapshot = full_time;
    snapshot.match_token = tokens[i];
    rejected(&live_final, &snapshot, &ready);
    FixdemoCeremonyLatch latch = ready;
    latch.match_token = tokens[i];
    rejected(&live_final, &full_time, &latch);
  }
  FixdemoCeremonySnapshot snapshot = full_time;
  snapshot.native_home_team = full_time.native_away_team;
  snapshot.native_away_team = full_time.native_home_team;
  rejected(&live_final, &snapshot, &ready);
  snapshot = full_time;
  snapshot.native_home_team = 0u;
  rejected(&live_final, &snapshot, &ready);
  snapshot = full_time;
  snapshot.native_away_team = 108u;
  rejected(&live_final, &snapshot, &ready);
  FixdemoCeremonyContext context = live_final;
  context.native_away_team = 0u;
  rejected(&context, &full_time, &ready);
  context = live_final;
  context.native_home_team = context.native_away_team;
  snapshot = full_time;
  snapshot.native_home_team = context.native_home_team;
  rejected(&context, &snapshot, &ready);
  /* Native HOME can be the bracket's AWAY after the human-slot swap. The
   * policy preserves native order; it never guesses from IDs or ownership. */
  context = live_final;
  context.native_home_team = 107u;
  context.native_away_team = 101u;
  snapshot = full_time;
  snapshot.native_home_team = 107u;
  snapshot.native_away_team = 101u;
  accepted(&context, &snapshot, &ready, 0u);
}

static void check_ending_factory_boundary(void) {
  FixdemoCeremonySnapshot snapshot = full_time;
  snapshot.boundary = FIXDEMO_CEREMONY_BOUNDARY_ENDING_FACTORY;
  snapshot.original_scene = 0x70004;
  snapshot.original_side = 0;
  rejected(&live_final, &snapshot, &ready); /* exact native request still required */
  snapshot.native_request_verified = 1;
  for (uint32_t side = 0; side != 3; ++side) {
    snapshot.original_side = side;
    accepted(&live_final, &snapshot, &ready, 0);
  }
  snapshot.original_scene = 0x6000f;
  accepted(&live_final, &snapshot, &ready, 0);
  snapshot.home_goals = 0;
  accepted(&live_final, &snapshot, &ready, 1); /* chosen ending side is not winner evidence */
  snapshot.phase = 2;
  rejected(&live_final, &snapshot, &ready);
  snapshot.phase = 10; snapshot.caller_verified = 0;
  rejected(&live_final, &snapshot, &ready);
  snapshot.caller_verified = 1; snapshot.original_side = 3;
  rejected(&live_final, &snapshot, &ready);
  snapshot.original_side = 2;
  const uint32_t invalid[] = {0, 0x60000, 0x70000, 0x80001, UINT32_MAX};
  for (unsigned i = 0; i != sizeof(invalid) / sizeof(invalid[0]); ++i) {
    snapshot.original_scene = invalid[i];
    rejected(&live_final, &snapshot, &ready);
  }
  snapshot = full_time; snapshot.boundary = 3;
  rejected(&live_final, &snapshot, &ready);
  snapshot = full_time; snapshot.native_request_verified = 1;
  snapshot.original_scene = 0x70004;
  rejected(&live_final, &snapshot, &ready); /* original RESULT gate was not widened */
}

static void check_listener_result_boundary(void) {
  FixdemoCeremonySnapshot snapshot = full_time;
  snapshot.boundary = FIXDEMO_CEREMONY_BOUNDARY_LISTENER_RESULT;
  rejected(&live_final, &snapshot, &ready);
  snapshot.native_request_verified = 1u;
  for (uint32_t side = 0; side != 3; ++side) {
    snapshot.original_side = side;
    accepted(&live_final, &snapshot, &ready, 0);
  }
  snapshot.home_goals = 0;
  accepted(&live_final, &snapshot, &ready, 1);
  for (uint32_t phase = 0; phase != 12; ++phase) {
    if (phase == 10) continue;
    snapshot.phase = phase;
    rejected(&live_final, &snapshot, &ready);
  }
  snapshot.phase = 10;
  snapshot.original_side = 3;
  rejected(&live_final, &snapshot, &ready);
  snapshot.original_side = 2;
  snapshot.original_scene = 0x70004;
  rejected(&live_final, &snapshot, &ready);
  snapshot.original_scene = 0x80001;
  snapshot.caller_verified = 0;
  rejected(&live_final, &snapshot, &ready);
  snapshot = full_time;
  snapshot.native_request_verified = 1;
  snapshot.original_side = 0;
  rejected(&live_final, &snapshot, &ready); /* old RESULT boundary stays neutral-only */
}

static void check_winner_evidence(void) {
  FixdemoCeremonySnapshot snapshot = full_time;
  snapshot.home_goals = 0;
  snapshot.away_goals = 99;
  accepted(&live_final, &snapshot, &ready, 1u);
  snapshot.home_goals = 99;
  snapshot.away_goals = 0;
  accepted(&live_final, &snapshot, &ready, 0u);
  const int32_t invalid[] = {-1, 100, INT32_MIN, INT32_MAX};
  for (uint32_t i = 0u; i < sizeof(invalid) / sizeof(invalid[0]); i++) {
    snapshot = full_time;
    snapshot.home_goals = invalid[i];
    rejected(&live_final, &snapshot, &ready);
    snapshot = full_time;
    snapshot.away_goals = invalid[i];
    rejected(&live_final, &snapshot, &ready);
  }
  snapshot = full_time;
  snapshot.home_goals = snapshot.away_goals = 1;
  snapshot.home_shootout = 5;
  snapshot.away_shootout = 4;
  rejected(&live_final, &snapshot, &ready); /* Cached PK winner is insufficient. */
  snapshot.shootout_fresh = 1u;
  rejected(&live_final, &snapshot, &ready); /* Totals are not shootout-only. */
  snapshot.shootout_only = 1u;
  accepted(&live_final, &snapshot, &ready, 0u);
  snapshot.home_shootout = 3;
  accepted(&live_final, &snapshot, &ready, 1u);
  snapshot.home_shootout = 4;
  rejected(&live_final, &snapshot, &ready);
  snapshot.home_shootout = 5;
  for (uint32_t i = 0u; i < sizeof(invalid) / sizeof(invalid[0]); i++) {
    FixdemoCeremonySnapshot bad = snapshot;
    bad.home_shootout = invalid[i];
    rejected(&live_final, &bad, &ready);
    bad = snapshot;
    bad.away_shootout = invalid[i];
    rejected(&live_final, &bad, &ready);
  }
  snapshot.shootout_fresh = 0u;
  rejected(&live_final, &snapshot, &ready);
  snapshot.shootout_fresh = 2u;
  rejected(&live_final, &snapshot, &ready);
  snapshot.shootout_fresh = 1u;
  snapshot.shootout_only = UINT32_MAX;
  rejected(&live_final, &snapshot, &ready);
  /* An irrelevant old shootout must never replace the goals winner. */
  snapshot = full_time;
  snapshot.home_shootout = 0;
  snapshot.away_shootout = 99;
  accepted(&live_final, &snapshot, &ready, 0u);
  snapshot.shootout_fresh = 1u;
  rejected(&live_final, &snapshot, &ready); /* Claimed fresh but not PK-only. */
  snapshot.shootout_only = 1u;
  snapshot.away_shootout = 100;
  rejected(&live_final, &snapshot, &ready);
}

static void check_one_shot(void) {
  FixdemoCeremonyLatch latch = {0};
  rejected(&live_final, &full_time, &latch);
  assert(!fixdemo_ceremony_begin_match(NULL, 41u));
  assert(!fixdemo_ceremony_begin_match(&latch, 0u));
  assert(fixdemo_ceremony_begin_match(&latch, 41u));
  assert(!fixdemo_ceremony_begin_match(&latch, 41u));
  FixdemoCeremonyPlan plan = accepted(&live_final, &full_time, &latch, 0u);
  const int failed[] = {0, -1, 2};
  for (uint32_t i = 0u; i < sizeof(failed) / sizeof(failed[0]); i++) {
    assert(!fixdemo_ceremony_backend_result(&latch, &plan, failed[i]));
    assert(!latch.consumed);
    accepted(&live_final, &full_time, &latch, 0u);
  }
  assert(!fixdemo_ceremony_backend_result(NULL, &plan, 1));
  assert(!fixdemo_ceremony_backend_result(&latch, NULL, 1));
  FixdemoCeremonyPlan invalid = plan;
  invalid.winner_side = 2u;
  assert(!fixdemo_ceremony_backend_result(&latch, &invalid, 1));
  invalid = plan;
  invalid.scene = 0x80001u;
  assert(!fixdemo_ceremony_backend_result(&latch, &invalid, 1));
  assert(fixdemo_ceremony_backend_result(&latch, &plan, 1));
  assert(latch.consumed == 1u);
  rejected(&live_final, &full_time, &latch);
  assert(!fixdemo_ceremony_backend_result(&latch, &plan, 1));
  assert(!fixdemo_ceremony_begin_match(&latch, 41u));
  assert(!fixdemo_ceremony_begin_match(&latch, 40u));
  assert(latch.consumed == 1u);
  assert(fixdemo_ceremony_begin_match(&latch, 42u));
  assert(!latch.consumed);
  rejected(&live_final, &full_time, &latch);
  assert(!fixdemo_ceremony_backend_result(&latch, &plan, 1));
  FixdemoCeremonyContext context = live_final;
  FixdemoCeremonySnapshot snapshot = full_time;
  context.match_token = snapshot.match_token = 42u;
  plan = accepted(&context, &snapshot, &latch, 0u);
  assert(fixdemo_ceremony_backend_result(&latch, &plan, 1));
  latch.consumed = 2u;
  rejected(&context, &snapshot, &latch);
  assert(!fixdemo_ceremony_begin_match(&latch, 43u));
}

int main(void) {
  check_result_boundary();
  check_match_identity();
  check_ending_factory_boundary();
  check_listener_result_boundary();
  check_winner_evidence();
  check_one_shot();
  puts("Fixdemo ceremony policy tests passed");
  return 0;
}
