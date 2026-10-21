#ifndef PESNX_SCENE_RUNTIME_LOG_H
#define PESNX_SCENE_RUNTIME_LOG_H
#include <stdio.h>
#include <stdint.h>
#include "experimental_features.h"
#ifdef NEAR_CAMERA_TRACE
extern int pes_gl_probe_cache_enabled(void);
#endif

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
  // Keep exactly one bounded prior session: a second launch must not erase
  // the cold-start evidence needed to compare missing/blinking geometry.
  FILE *prior=fopen("scene-runtime.log","rb");
  if (prior) {
    const int seek_ok=fseek(prior,0,SEEK_END)==0;
    const long bytes=seek_ok ? ftell(prior) : -1;
    fclose(prior);
    if (bytes>0 && bytes<=65536) {
      remove("scene-runtime.previous.log");
      (void)rename("scene-runtime.log","scene-runtime.previous.log");
    }
  }
  FILE *file=fopen("scene-runtime.log","wb");
  if (file) {
    fputs("FootballNX scene v65 session\n",file);
    fputs("match v65: native match-local HOME/AWAY team keys; checked squad publication with refusal stages\n",file);
    fputs("match v62: native host admission and checked squad load; result exit confirmation; kickoff snapshot hold; stadium mowing\n",file);
    fputs("compat hotpaths v44: release clock/TLS trace atomics removed\n",file);
    fputs("compat hotpaths v45: cached native thread IDs; single-pass buffer free lists; native prematch reveal\n",file);
    fputs("compat hotpaths v46: context-local separate blend suppression; diagnostic savings counts\n",file);
    fputs("render stability v47: private overlay vertex state; High uses Standard players\n",file);
    fputs("render audit v48: no compositor pixel probes/error drains in ordinary or pacing builds; native stadium inventory\n",file);
    fputs("render cache v51: core/OES program-binary loads invalidate wrapper uniform locations and values\n",file);
#if PESNX_STADIUM_V2_ENABLED
    fputs("camera policy: STADIUM-V2 screen margin hold v1; smooth native zoom; no ball-centre lock\n",file);
#else
    fputs("camera policy: STADIUM-V2 suspended; native STADIUM retained\n",file);
#endif
#if !PESNX_ENTRANCE_CANARY_ENABLED
    fputs("entrance trace: disabled; native lifecycle retained; installed CPK selects the intro\n",file);
#endif
#ifdef NEAR_CAMERA_TRACE
    fputs("near-camera trace v43: CPU/GPU spans; corrected mesh snapshots; core/EXT/OES buffer outcomes; deferred until non-play\n",file);
    fprintf(file,"render control: state_cache=%s (diagnostic boot setting; face PAK unchanged)\n",
            pes_gl_probe_cache_enabled()?"enabled":"bypassed");
#endif
    fclose(file);
  }
#endif
}
#endif
