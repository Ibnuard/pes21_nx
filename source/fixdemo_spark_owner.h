/* Metadata-only optional FX admission. Never dereference cached owner IDs. */
#ifndef PESNX_FIXDEMO_SPARK_OWNER_H
#define PESNX_FIXDEMO_SPARK_OWNER_H
#include "fixdemo_prop_lifecycle.h"

static inline uint64_t fixdemo_spark_owner_generation(FixDemoPropLifecycle *state,
    uint64_t epoch) {
  if (!state || !epoch) return 0;
  /* Optional FX must not fail the native ceremony on lock contention. A single
   * try-lock leaves its failed_epoch and every ownership record untouched. */
  if (__atomic_test_and_set(&state->lock,__ATOMIC_ACQUIRE)) return 0;
  const FixDemoPropTicket *podium=&state->slots[1];
  const uint64_t generation = fixdemo_prop_lifecycle_epoch(state)==epoch &&
      __atomic_load_n(&state->failed_epoch,__ATOMIC_ACQUIRE)!=epoch &&
      (state->ready_mask & 2u) && podium->epoch==epoch && podium->kind==2u &&
      podium->ready && podium->owner && podium->demo && podium->model &&
      podium->ue && podium->key<192u ? podium->generation : 0;
  fixdemo_prop_lifecycle_unlock(state);
  return generation;
}
#endif
