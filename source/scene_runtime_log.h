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
    fputs("FootballNX scene v87 session\n",file);
    fputs("review v87: exact native prop paths; contiguous Cup/podium file list; native result footer held with ceremony\n",file);
    fputs("review v86: custom overview and menu input wait for Cup ceremony; cut/prop loading stages journaled\n",file);
    fputs("review v85: trophy Skip waits for native Start, button release and fresh face/Plus press\n",file);
    fputs("review v84: bounded native trophy loading and terminal diagnostics; v83 added-time plate retained\n",file);
    fputs("review v83: native HOME/AWAY trophy result identities; larger centered FootballNX27 added-time plate\n",file);
    fputs("review v82: FootballNX27 white-blue-red League/Cup scoreboard; adaptive charcoal/white branding\n",file);
    fputs("review v81: both corner helper entries share native-sized bold white HUD rows and sprite spacing\n",file);
    fputs("review v80: deeper Cloudy shade; source-backed Old Trafford; held horizontal Joy-Con corner tactics; v78 skin retained\n",file);
    fputs("review v77: calibrated Serie A cells; independent visible Cloudy drift; Camp Nou upper-stand repair pairing\n",file);
    fputs("weather v75: fixed world-space full-pitch rain/snow; no camera-follow transform updates\n",file);
    fputs("weather v74: small slow Winter snow; thin cold distance haze; slow Cloudy pitch shadows\n",file);
    fputs("review v73: stadium-wide distance mist; bounded thin 3D rain; bottom-corner per-pad tactics panels\n",file);
    fputs("review v72: corner-only restart and native-list guards; owned goal-kick helper; stronger Rainy Day High material mist\n",file);
    fputs("review v71: one right corner column; conditional league added time; Rainy material mist; low shell apron preserved; scoped body palette package\n",file);
    fputs("startup v70: corner opcode guards use bounded RW backing before native RX mapping\n",file);
    fputs("corner v69: native corner presets; per-pad LEFT selector and RIGHT taker; restart-owned command lifetime\n",file);
    fputs("match v67: checked selected-Match rebuild before bench confirmation; career office and live reservations separate\n",file);
    fputs("match v66: fresh prematch edit lifecycle; replay visibility bridge; compact league scoreboards\n",file);
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
