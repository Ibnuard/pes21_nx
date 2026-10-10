#ifndef PESNX_SCENE_RUNTIME_LOG_H
#define PESNX_SCENE_RUNTIME_LOG_H
#include <stdio.h>
#include <stdint.h>

static inline uint64_t scene_runtime_ms(void) {
#if !defined(PESNX_STADIUM_CANARY_HOST_TEST) && !defined(PESNX_REFEREE_PROBE_HOST_TEST)
  return armTicksToNs(armGetSystemTick())/1000000u;
#else
  return 0;
#endif
}

/* Small release-build journal for device-only load failures. Never per draw,
 * no raw pointers/payloads, at most 128 events per translation unit / 64 KiB. */
static inline void scene_runtime_note(const char *area, const char *message) {
#if !defined(PESNX_STADIUM_CANARY_HOST_TEST) && !defined(PESNX_REFEREE_PROBE_HOST_TEST)
  static uint32_t events;
  if (__atomic_fetch_add(&events,1,__ATOMIC_RELAXED)>=128) return;
  FILE *file=fopen("scene-runtime.log","ab");
  if (!file) return;
  if (fseek(file,0,SEEK_END)==0 && ftell(file)<65536)
    fprintf(file,"%s: %s\n",area,message);
  fclose(file);
#else
  (void)area;(void)message;
#endif
}
static inline void scene_runtime_begin(void) {
#if !defined(PESNX_STADIUM_CANARY_HOST_TEST) && !defined(PESNX_REFEREE_PROBE_HOST_TEST)
  FILE *file=fopen("scene-runtime.log","wb");
  if (file) {fputs("FootballNX scene v14 session\n",file);fclose(file);}
#endif
}
#endif
