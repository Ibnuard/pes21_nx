/* Borrowed native presentation state; admitted only after code-layout guards. */
#ifndef PESNX_REFEREE_PRESENTATION_H
#define PESNX_REFEREE_PRESENTATION_H
#include <stdint.h>
#include <string.h>

/* Visibility follows the native lifecycle, including a paused replay with no
 * input heartbeat or live draw. Only its own ModeEnd (or scene teardown) may
 * retire this owner. It is independent of the optional offside layout. */
static uintptr_t referee_recorded_replay_owner;
static inline int referee_recorded_replay_active(void) {
  return __atomic_load_n(&referee_recorded_replay_owner,__ATOMIC_ACQUIRE)!=0;
}

static inline int referee_offside_presentation(const void *registry) {
  if (!registry) return 0;
  const unsigned char *demo = NULL, *fixed = NULL;
  memcpy(&demo, (const unsigned char *)registry + 0x360u, sizeof(demo));
  memcpy(&fixed, (const unsigned char *)registry + 0x400u, sizeof(fixed));
  if (!demo || !fixed || !demo[0x7du]) return 0;
  uint32_t owner, current;
  memcpy(&owner, demo, sizeof(owner));
  memcpy(&current, fixed + 0x20u, sizeof(current));
  /* The recorded scene is cleared on cancellation even when DemoInfo's exec
   * bit awaits its next Init. Do not retain a pointer, timer or stale id. */
  return owner == 0x3017au && current == owner;
}
#endif
