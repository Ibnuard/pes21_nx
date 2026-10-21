/* Borrowed native presentation state; admitted only after code-layout guards. */
#ifndef PESNX_REFEREE_PRESENTATION_H
#define PESNX_REFEREE_PRESENTATION_H
#include <stdint.h>
#include <string.h>

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
