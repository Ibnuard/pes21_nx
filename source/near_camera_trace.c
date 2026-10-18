#include "near_camera_trace.h"
#ifdef NEAR_CAMERA_TRACE
#include <stdio.h>
#include "near_camera_policy.h"
#ifndef PESNX_NEAR_HOST_TEST
#include <switch.h>
#include "scene_runtime_log.h"
#endif

/* One atomic scalar snapshot; no UObject, allocation, lock or retry loop. */
static uint64_t near_camera_stamp;
static __thread struct {
  NxNearFrame frame;
  NxNearWindow zones[NX_NEAR_ZONES];
  NxNearContext context;
  uint64_t previous;
  unsigned zone, camera, width, height, discarded, gpu_supported;
} near_trace;

void nx_near_camera(const float *p,unsigned camera,uint64_t now_ns) {
  const uint64_t stamp=(uint32_t)(now_ns/1000000u);
  __atomic_store_n(&near_camera_stamp,(stamp<<32)|((camera&255u)<<8)|nx_near_zone(p),
                   __ATOMIC_RELEASE);
}
uint64_t nx_near_view_sample(void) {
  return __atomic_load_n(&near_camera_stamp,__ATOMIC_ACQUIRE);
}
void nx_near_draw(uint64_t begin,uint64_t end,uint64_t elements) {
  NxNearFrame *f=&near_trace.frame;
  if (!f->first_draw) f->first_draw=begin;
  ++f->draws; f->elements+=elements;
  if (end>=begin) f->draw_ns+=end-begin;
}
void nx_near_upload(uint64_t ns,uint64_t bytes,int mapped) {
  NxNearFrame *f=&near_trace.frame;
  f->upload_ns+=ns;
  if (mapped) { ++f->maps; f->mapped_bytes+=bytes; }
  else { ++f->uploads; f->bytes+=bytes; }
}
void nx_near_flush(void) { ++near_trace.frame.flushes; }
void nx_near_blend(int skipped) {
  ++near_trace.frame.blend_requests; near_trace.frame.blend_skipped+=!!skipped;
}
void nx_near_map_result(int success) {
  ++near_trace.frame.map_calls; near_trace.frame.map_failures+=!success;
}
void nx_near_unmap_result(int success) {
  ++near_trace.frame.unmap_calls; near_trace.frame.unmap_failures+=!success;
}
void nx_near_error_result(unsigned error) {
  ++near_trace.frame.error_checks;
  if (error) {
    ++near_trace.frame.errors;
    if (!near_trace.frame.first_error) near_trace.frame.first_error=error;
  }
}
void nx_near_gpu_support(unsigned supported) { near_trace.gpu_supported=supported; }
void nx_near_gpu(uint64_t ns,uint64_t stamp) {
  const unsigned zone=(unsigned)(stamp&255u), camera=(unsigned)(stamp>>8)&255u;
  if (!near_trace.context.live || zone>=NX_NEAR_ZONES || camera!=near_trace.camera) return;
  NxNearWindow *w=&near_trace.zones[zone];
  ++w->gpu_samples; w->gpu_ns+=ns;
  if (ns>w->gpu_worst_ns) w->gpu_worst_ns=ns;
}
static void nx_near_report(void) {
  static const char *names[NX_NEAR_ZONES]={"unknown","far_left","far_middle","far_right",
      "centre_left","centre_middle","centre_right","near_left","near_middle","near_right"};
  for (unsigned i=0;i<NX_NEAR_ZONES;++i) {
    const NxNearWindow *w=&near_trace.zones[i];
    if (!w->frames) continue;
    const NxNearContext *c=&near_trace.context;
    const uint64_t n=w->frames;
    char line[1800];
    snprintf(line,sizeof(line),
      "v32 session=%u stadium=%u day=%u weather=%u season=%u quality=%u home=%u away=%u "
      "camera=%u zone=%s frames=%llu avg_us=%llu worst_us=%llu over20=%llu over30=%llu "
      "swap_us=%llu render_span_us=%llu draws_x10=%llu submitted_elements=%llu draw_cpu_us=%llu "
      "uploads_x10=%llu upload_bytes=%llu maps_x10=%llu mapped_bytes=%llu upload_cpu_us=%llu "
      "forced_flushes=%llu discarded=%u viewport=%ux%u gpu_supported=%u gpu_samples=%llu gpu_avg_us=%llu gpu_worst_us=%llu "
      "p50_upper_us=%llu p95_upper_us=%llu p99_upper_us=%llu "
      "map_calls=%llu map_failures=%llu unmap_calls=%llu unmap_failures=%llu "
      "gl_error_checks=%llu gl_errors=%llu first_gl_error=%llu "
      "blend_requests=%llu blend_skipped=%llu "
      "(CPU calls; not GPU time; zone=camera target; quantiles=bucket upper bounds)",
      c->session,c->stadium,c->day,c->weather,c->season,c->quality,c->home,c->away,
      near_trace.camera,names[i],(unsigned long long)n,
      (unsigned long long)(w->interval_ns/n/1000),(unsigned long long)(w->worst_ns/1000),
      (unsigned long long)w->over20,(unsigned long long)w->over30,
      (unsigned long long)(w->swap_ns/n/1000),(unsigned long long)(w->span_ns/n/1000),
      (unsigned long long)(w->work.draws*10/n),(unsigned long long)(w->work.elements/n),
      (unsigned long long)(w->work.draw_ns/n/1000),(unsigned long long)(w->work.uploads*10/n),
      (unsigned long long)(w->work.bytes/n),(unsigned long long)(w->work.maps*10/n),
      (unsigned long long)(w->work.mapped_bytes/n),(unsigned long long)(w->work.upload_ns/n/1000),
      (unsigned long long)w->work.flushes,near_trace.discarded,near_trace.width,near_trace.height,
      near_trace.gpu_supported,(unsigned long long)w->gpu_samples,
      (unsigned long long)(w->gpu_samples?w->gpu_ns/w->gpu_samples/1000:0),
      (unsigned long long)(w->gpu_worst_ns/1000),
      (unsigned long long)nx_near_quantile_upper(w,50),
      (unsigned long long)nx_near_quantile_upper(w,95),
      (unsigned long long)nx_near_quantile_upper(w,99),
      (unsigned long long)w->work.map_calls,(unsigned long long)w->work.map_failures,
      (unsigned long long)w->work.unmap_calls,(unsigned long long)w->work.unmap_failures,
      (unsigned long long)w->work.error_checks,(unsigned long long)w->work.errors,
      (unsigned long long)w->work.first_error,
      (unsigned long long)w->work.blend_requests,
      (unsigned long long)w->work.blend_skipped);
    scene_runtime_note("near-camera",line);
  }
}
void nx_near_swap(uint64_t begin,uint64_t end,unsigned width,unsigned height,
                  int success,uint64_t stamp,const NxNearContext *c) {
  if (!c->live) {
    /* A pause, replay or menu is the ONLY writer. Never flush a changed
     * bucket while the match is live. No FILE call in any draw/upload hook. */
    nx_near_report(); memset(&near_trace,0,sizeof(near_trace)); return;
  }
  const uint32_t age=(uint32_t)(begin/1000000u)-(uint32_t)(stamp>>32);
  const unsigned zone=age<=250?(unsigned)(stamp&255u):0;
  const unsigned camera=(unsigned)(stamp>>8)&255u;
  const int changed=memcmp(c,&near_trace.context,sizeof(*c)) ||
      camera!=near_trace.camera || width!=near_trace.width || height!=near_trace.height;
  if (changed) {
    /* Transition evidence cannot be attributed to either state. */
    memset(near_trace.zones,0,sizeof(near_trace.zones)); near_trace.discarded=0;
    near_trace.previous=0; near_trace.context=*c; near_trace.camera=camera;
    near_trace.width=width; near_trace.height=height;
  }
  if (success && near_trace.previous && begin>near_trace.previous && end>=begin &&
      zone==near_trace.zone && zone<NX_NEAR_ZONES) {
    const uint64_t first=near_trace.frame.first_draw;
    nx_near_accumulate(&near_trace.zones[zone],&near_trace.frame,
        begin-near_trace.previous,end-begin,first && begin>=first?begin-first:0);
  } else ++near_trace.discarded;
  near_trace.previous=success?begin:0; near_trace.zone=zone;
  memset(&near_trace.frame,0,sizeof(near_trace.frame));
}
#endif
