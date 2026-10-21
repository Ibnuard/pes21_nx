#ifndef PESNX_RESULT_EXIT_CONFIRM_H
#define PESNX_RESULT_EXIT_CONFIRM_H
#include <stdint.h>
typedef struct { uint32_t active, focus; } ResultExitConfirm;
static inline void result_exit_confirm_clear(ResultExitConfirm *state) {
  __atomic_store_n(&state->active,0u,__ATOMIC_RELEASE);
  __atomic_store_n(&state->focus,1u,__ATOMIC_RELEASE);
}
static inline void result_exit_confirm_open(ResultExitConfirm *state) {
  __atomic_store_n(&state->focus,1u,__ATOMIC_RELEASE);
  __atomic_store_n(&state->active,1u,__ATOMIC_RELEASE);
}
/* 2 = normal page input; 0 = modal consumed; 1 = explicitly confirmed. */
static inline int result_exit_confirm_input(ResultExitConfirm *state,
    int navigate,int back,int decide) {
  if (!__atomic_load_n(&state->active,__ATOMIC_ACQUIRE)) return 2;
  if (back) { result_exit_confirm_clear(state); return 0; }
  if (navigate) { __atomic_fetch_xor(&state->focus,1u,__ATOMIC_ACQ_REL); return 0; }
  if (decide) {
    const int accepted=__atomic_load_n(&state->focus,__ATOMIC_ACQUIRE)==0u;
    result_exit_confirm_clear(state);
    return accepted;
  }
  return 0;
}
#endif
