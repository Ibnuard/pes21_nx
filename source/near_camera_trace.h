#ifndef PES_NEAR_CAMERA_TRACE_H
#define PES_NEAR_CAMERA_TRACE_H
#include <stdint.h>

/* Separate opt-in from PERF_TRACE/DEBUG_LOG: no file I/O or GL query in play. */
#ifdef NEAR_CAMERA_TRACE
typedef struct {
  uint32_t live, session, stadium, day, weather, season, quality, home, away;
} NxNearContext;
void pes_controller_near_context(NxNearContext *out);
void nx_near_camera(const float *parameter, unsigned camera, uint64_t now_ns);
uint64_t nx_near_view_sample(void);
void nx_near_draw(uint64_t begin_ns,uint64_t end_ns,uint64_t elements);
void nx_near_upload(uint64_t ns,uint64_t bytes,int mapped);
void nx_near_map_result(int success);
void nx_near_unmap_result(int success);
void nx_near_error_result(unsigned error);
void nx_near_blend(int skipped);
int pes_gl_probe_cache_enabled(void);
void nx_near_flush(void);
void nx_near_gpu(uint64_t ns,uint64_t camera_sample);
void nx_near_gpu_support(unsigned supported);
void pes_controller_face_probe_report(void);
void nx_near_swap(uint64_t begin_ns,uint64_t end_ns,unsigned width,unsigned height,
                  int success,uint64_t camera_sample,const NxNearContext *context);
#endif
#endif
