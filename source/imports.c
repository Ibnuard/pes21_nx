/* imports.c -- .so import resolution
 *
 * Copyright (C) 2021 fgsfds, Andy Nguyen
 *
 * This software may be modified and distributed under the terms
 * of the MIT license.  See the LICENSE file for details.
 *
 * Serves both libGame.so and the C++ runtime donor (the APK's libopenal.so).
 * C++ runtime symbols (std::*, __cxa_*) resolve module-to-module from the donor,
 * not here. The table takes priority during resolution (see so_resolve_symbol).
 */

#define _GNU_SOURCE // vasprintf and friends

#include <stdlib.h>
#include <stdio.h>
#include <stdint.h>
#include <stdarg.h>
#include <string.h>
#include <unistd.h>
#include <assert.h>
#include <errno.h>
#include <wchar.h>
#include <wctype.h>
#include <ctype.h>
#include <fcntl.h>
#include <math.h>
#include <pthread.h>
#include <semaphore.h>
#include <setjmp.h>
#include <signal.h>
#include <time.h>
#include <dirent.h>
#include <locale.h>
#include <sys/time.h>
#include <sys/stat.h>
#include <sys/reent.h>
#include <sys/socket.h>
#include <sys/select.h>
#include <sys/resource.h>
#include <netdb.h>
#include <net/if.h>
#include <arpa/inet.h>
#include <EGL/egl.h>
#include <GLES2/gl2.h>
#include <AL/al.h>
#include <AL/alc.h>
#include <mpg123.h>
#include <zlib.h>
#include <switch.h>

#include "android_shim.h"
#include "config.h"
#include "so_util.h"
#include "util.h"
#include "libc_shim.h"
#include "overlay.h"

extern uintptr_t __stack_chk_fail;
extern so_module avs_mod;
extern so_module afp_mod;
extern so_module ue4_mod;

static char *__ctype_ = (char *)&_ctype_;

static uint64_t __stack_chk_guard_fake = 0x4242424242424242;
static volatile int late_sync_trace;
static inline void *mc_thread_key(void);

#define SYNC_TRACE_SLOTS 128
typedef struct {
  void *tls;
  void *object;
  void *caller;
} SyncTraceEntry;

static int sync_trace_once(SyncTraceEntry *entries, void *object,
                           void *caller) {
  void *tls = mc_thread_key();
  for (int i = 0; i < SYNC_TRACE_SLOTS; i++) {
    void *current = __atomic_load_n(&entries[i].object, __ATOMIC_ACQUIRE);
    if (current == object && entries[i].tls == tls &&
        entries[i].caller == caller)
      return 0;
  }
  for (int i = 0; i < SYNC_TRACE_SLOTS; i++) {
    void *expected = NULL;
    if (__atomic_compare_exchange_n(&entries[i].object, &expected, object, 0,
                                    __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE)) {
      entries[i].tls = tls;
      entries[i].caller = caller;
      return 1;
    }
  }
  return 0;
}

static int __cxa_atexit_fake(void (*destructor)(void *), void *object,
                             void *dso_handle) {
  (void)destructor;
  (void)object;
  (void)dso_handle;
  return 0;
}

static int clock_gettime_android(int clock_id, struct timespec *ts) {
  if (!ts) {
    errno = EFAULT;
    return -1;
  }

  // Bionic numbers REALTIME as 0 and MONOTONIC as 1, unlike newlib. Build
  // monotonic clocks from the hardware counter so RAW/BOOTTIME variants are
  // also available to CRI without depending on newlib's clock-id support.
  if (clock_id == 0 || clock_id == 5 || clock_id == 8) {
    struct timeval tv;
    if (gettimeofday(&tv, NULL) < 0)
      return -1;
    ts->tv_sec = tv.tv_sec;
    ts->tv_nsec = tv.tv_usec * 1000L;
  } else if ((clock_id >= 1 && clock_id <= 4) || clock_id == 6 ||
             clock_id == 7 || clock_id == 9) {
    const uint64_t ticks = armGetSystemTick();
    const uint64_t frequency = armGetSystemTickFreq();
    ts->tv_sec = ticks / frequency;
    ts->tv_nsec = (long)(((ticks % frequency) * 1000000000ULL) / frequency);
  } else {
    errno = EINVAL;
    return -1;
  }

  static volatile unsigned int trace_count;
  if (__sync_fetch_and_add(&trace_count, 1) < 12)
    debugPrintf("clock_gettime_android(%d) -> %lld.%09ld\n", clock_id,
                (long long)ts->tv_sec, ts->tv_nsec);
  return 0;
}

static void game_termination_trace(const char *kind, int status) {
  debugPrintf("game %s(%d): tls=%p\n", kind, status, mc_thread_key());
  const uintptr_t stack_start = (uintptr_t)__builtin_frame_address(0);
  uintptr_t frame = stack_start;
  for (int depth = 0; depth < 12; depth++) {
    if ((frame & 0xf) || frame < stack_start ||
        frame - stack_start > 0x200000)
      break;
    const uintptr_t previous = *(const uintptr_t *)frame;
    const uintptr_t address = *(const uintptr_t *)(frame + 8);
    const uintptr_t avs_base = (uintptr_t)avs_mod.load_virtbase;
    const uintptr_t afp_base = (uintptr_t)afp_mod.load_virtbase;
    const uintptr_t ue4_base = (uintptr_t)ue4_mod.load_virtbase;
    if (address >= avs_base && address < avs_base + avs_mod.load_size)
      debugPrintf("game %s frame[%d]=%p AVS+0x%lx\n", kind, depth,
                  (void *)address, address - avs_base);
    else if (address >= afp_base && address < afp_base + afp_mod.load_size)
      debugPrintf("game %s frame[%d]=%p AFP+0x%lx\n", kind, depth,
                  (void *)address, address - afp_base);
    else if (address >= ue4_base && address < ue4_base + ue4_mod.load_size)
      debugPrintf("game %s frame[%d]=%p UE4+0x%lx\n", kind, depth,
                  (void *)address, address - ue4_base);
    else
      debugPrintf("game %s frame[%d]=%p native\n", kind, depth,
                  (void *)address);
    if (previous <= frame || previous - frame > 0x100000)
      break;
    frame = previous;
  }
}

static void game_exit_fake(int status) {
  game_termination_trace("exit", status);
  pthread_exit(NULL);
  __builtin_unreachable();
}

static void game_abort_fake(void) {
  game_termination_trace("abort", 0);
  pthread_exit(NULL);
  __builtin_unreachable();
}

// Per-thread cache of the last successful eglMakeCurrent: the engine re-binds
// the same context+surface many times per frame and mesa revalidates each time,
// so skip the redundant bind (a no-op per the EGL spec). Keyed by TPIDR_EL0.
#define MC_SLOTS 32
static struct {
  void *key;
  EGLDisplay dpy; EGLSurface draw, read; EGLContext ctx;
  GLuint framebuffer;
  GLint viewport[4];
  GLuint program;
  unsigned int active_texture;
  GLuint texture2d[8];
  GLuint sampler[8];
  unsigned int trace_default_draws;
} g_mc[MC_SLOTS];

static inline void *mc_thread_key(void) {
  void *p;
  __asm__ volatile("mrs %0, tpidr_el0" : "=r"(p));
  return p;
}

static int mc_current_slot(void) {
  void *key = mc_thread_key();
  for (int i = 0; i < MC_SLOTS; i++)
    if (g_mc[i].key == key)
      return i;
  return -1;
}

// ---------------------------------------------------------------------------
// GL redundant-state cache. RenderWare / GTA SA re-set the same GL state (blend,
// depth, cull, texture bindings, active unit, program, ...) many times per frame.
// On the Switch mesa/nouveau driver every GL call is expensive and the game is
// CPU-bound on call count (GPU mostly idle), so drop calls that don't change
// state. Correct because the engine renders through one GL context at a time (EGL
// make-current transfers ownership): glc_reset() runs on every REAL eglMakeCurrent
// so the cache is never trusted across a context switch, and glDelete{Textures,
// Program} invalidate the bind caches so a reused id is never wrongly skipped.
// Set glc_enabled = 0 for a pure pass-through if a rendering glitch is suspected.
// ---------------------------------------------------------------------------
// UE4 drives several shared EGL contexts from different threads. This cache was
// designed for GTA's single-context renderer and can suppress state changes from
// the wrong context, so keep PES on the correct pass-through path.
static int glc_enabled = 0;

#define GLC_MAXCAPS 24
static struct { GLenum cap; GLboolean on; } glc_caps[GLC_MAXCAPS];
static int glc_ncaps;

static struct {
  int have_blend;  GLenum bsf, bdf;
  int have_dfunc;  GLenum dfunc;
  int have_dmask;  GLboolean dmask;
  int have_cull;   GLenum cull;
  int have_front;  GLenum front;
  int have_cmask;  GLboolean cr, cg, cb, ca;
  int have_active; GLenum active;
  int have_prog;   GLuint prog;
  GLuint tex2d[8]; int have_tex2d[8];
} glc;

// Invalidate the cache. Called on every real eglMakeCurrent (context ownership
// transfer) and once per frame from eglSwapBuffers_cache (so the wrapper's own
// direct GL -- movie player, FPS overlay -- can't leave the cache stale).
static void gl_state_cache_reset(void) {
  glc_ncaps = 0;
  memset(&glc, 0, sizeof(glc));
}

static void glEnable_c(GLenum cap) {
  if (glc_enabled) {
    for (int i = 0; i < glc_ncaps; i++)
      if (glc_caps[i].cap == cap) {
        if (glc_caps[i].on) return;
        glc_caps[i].on = GL_TRUE; glEnable(cap); return;
      }
    if (glc_ncaps < GLC_MAXCAPS) {
      glc_caps[glc_ncaps].cap = cap; glc_caps[glc_ncaps].on = GL_TRUE; glc_ncaps++;
    }
  }
  glEnable(cap);
}
static void glDisable_c(GLenum cap) {
  if (glc_enabled) {
    for (int i = 0; i < glc_ncaps; i++)
      if (glc_caps[i].cap == cap) {
        if (!glc_caps[i].on) return;
        glc_caps[i].on = GL_FALSE; glDisable(cap); return;
      }
    if (glc_ncaps < GLC_MAXCAPS) {
      glc_caps[glc_ncaps].cap = cap; glc_caps[glc_ncaps].on = GL_FALSE; glc_ncaps++;
    }
  }
  glDisable(cap);
}
static void glBlendFunc_c(GLenum s, GLenum d) {
  if (glc_enabled && glc.have_blend && glc.bsf == s && glc.bdf == d) return;
  glc.have_blend = 1; glc.bsf = s; glc.bdf = d;
  glBlendFunc(s, d);
}
static void glBlendFuncSeparate_c(GLenum sc, GLenum dc, GLenum sa, GLenum da) {
  glc.have_blend = 0; // don't reconcile with the glBlendFunc cache
  glBlendFuncSeparate(sc, dc, sa, da);
}
static void glDepthFunc_c(GLenum f) {
  if (glc_enabled && glc.have_dfunc && glc.dfunc == f) return;
  glc.have_dfunc = 1; glc.dfunc = f;
  glDepthFunc(f);
}
static void glDepthMask_c(GLboolean m) {
  if (glc_enabled && glc.have_dmask && glc.dmask == m) return;
  glc.have_dmask = 1; glc.dmask = m;
  glDepthMask(m);
}
static void glCullFace_c(GLenum m) {
  if (glc_enabled && glc.have_cull && glc.cull == m) return;
  glc.have_cull = 1; glc.cull = m;
  glCullFace(m);
}
static void glFrontFace_c(GLenum m) {
  if (glc_enabled && glc.have_front && glc.front == m) return;
  glc.have_front = 1; glc.front = m;
  glFrontFace(m);
}
static void glColorMask_c(GLboolean r, GLboolean g, GLboolean b, GLboolean a) {
  if (glc_enabled && glc.have_cmask && glc.cr == r && glc.cg == g &&
      glc.cb == b && glc.ca == a)
    return;
  glc.have_cmask = 1; glc.cr = r; glc.cg = g; glc.cb = b; glc.ca = a;
  glColorMask(r, g, b, a);
}
static void glActiveTexture_c(GLenum unit) {
  const int slot = mc_current_slot();
  if (slot >= 0 && unit >= GL_TEXTURE0 && unit < GL_TEXTURE0 + 8)
    g_mc[slot].active_texture = (unsigned int)(unit - GL_TEXTURE0);
  if (glc_enabled && glc.have_active && glc.active == unit) return;
  glc.have_active = 1; glc.active = unit;
  glActiveTexture(unit);
}
static void glBindTexture_c(GLenum target, GLuint tex) {
  const int slot = mc_current_slot();
  if (slot >= 0 && target == GL_TEXTURE_2D &&
      g_mc[slot].active_texture < 8)
    g_mc[slot].texture2d[g_mc[slot].active_texture] = tex;
  if (glc_enabled && target == GL_TEXTURE_2D && glc.have_active) {
    unsigned idx = (unsigned)(glc.active - GL_TEXTURE0);
    if (idx < 8) {
      if (glc.have_tex2d[idx] && glc.tex2d[idx] == tex) return;
      glc.have_tex2d[idx] = 1; glc.tex2d[idx] = tex;
    }
  }
  glBindTexture(target, tex);
}
static void glUseProgram_c(GLuint p) {
  const int slot = mc_current_slot();
  if (slot >= 0)
    g_mc[slot].program = p;
  if (glc_enabled && glc.have_prog && glc.prog == p) return;
  glc.have_prog = 1; glc.prog = p;
  glUseProgram(p);
}
static void glDeleteTextures_c(GLsizei n, const GLuint *t) {
  memset(glc.have_tex2d, 0, sizeof(glc.have_tex2d)); // a deleted bound tex must
  glDeleteTextures(n, t);                            // not be skipped when reused
}
static void glDeleteProgram_c(GLuint p) {
  if (glc.have_prog && glc.prog == p) glc.have_prog = 0;
  glDeleteProgram(p);
}

static volatile uint64_t gl_diag_draw_arrays;
static volatile uint64_t gl_diag_draw_elements;
static volatile uint64_t gl_diag_vertices;
static volatile uint64_t gl_diag_indices;
static volatile uint64_t gl_diag_draw_default;
static volatile uint64_t gl_diag_draw_offscreen;
static volatile uint64_t gl_diag_indices_default;
static volatile uint64_t gl_diag_indices_offscreen;
static volatile uint64_t gl_diag_bind_default;
static volatile uint64_t gl_diag_bind_offscreen;
static volatile uint64_t gl_diag_clear_default;
static volatile uint64_t gl_diag_clear_offscreen;
static volatile uint64_t gl_diag_blits;
static volatile uint32_t gl_diag_compile_ok;
static volatile uint32_t gl_diag_compile_fail;
static volatile uint32_t gl_diag_link_ok;
static volatile uint32_t gl_diag_link_fail;

static void gl_diag_trace_default_draw(const char *kind, GLsizei count,
                                       GLsizei instances) {
  const int slot = mc_current_slot();
  if (slot < 0 || g_mc[slot].framebuffer != 0 ||
      g_mc[slot].trace_default_draws == 0)
    return;
  const unsigned int order = 13 - g_mc[slot].trace_default_draws;
  debugPrintf("GL compose draw=%u kind=%s count=%d instances=%d program=%u "
              "tex=%u,%u,%u,%u sampler=%u,%u,%u,%u active=%u\n",
              order, kind, count, instances, g_mc[slot].program,
              g_mc[slot].texture2d[0], g_mc[slot].texture2d[1],
              g_mc[slot].texture2d[2], g_mc[slot].texture2d[3],
              g_mc[slot].sampler[0], g_mc[slot].sampler[1],
              g_mc[slot].sampler[2], g_mc[slot].sampler[3],
              g_mc[slot].active_texture);
  g_mc[slot].trace_default_draws--;
}

static void glDrawArrays_diag(GLenum mode, GLint first, GLsizei count) {
  __atomic_fetch_add(&gl_diag_draw_arrays, 1, __ATOMIC_RELAXED);
  const int slot = mc_current_slot();
  const int offscreen = slot >= 0 && g_mc[slot].framebuffer != 0;
  __atomic_fetch_add(offscreen ? &gl_diag_draw_offscreen
                               : &gl_diag_draw_default,
                     1, __ATOMIC_RELAXED);
  if (count > 0)
    __atomic_fetch_add(&gl_diag_vertices, (uint64_t)count, __ATOMIC_RELAXED);
  gl_diag_trace_default_draw("arrays", count, 1);
  glDrawArrays(mode, first, count);
}

static void glDrawElements_diag(GLenum mode, GLsizei count, GLenum type,
                                const void *indices) {
  __atomic_fetch_add(&gl_diag_draw_elements, 1, __ATOMIC_RELAXED);
  const int slot = mc_current_slot();
  const int offscreen = slot >= 0 && g_mc[slot].framebuffer != 0;
  __atomic_fetch_add(offscreen ? &gl_diag_draw_offscreen
                               : &gl_diag_draw_default,
                     1, __ATOMIC_RELAXED);
  if (count > 0) {
    __atomic_fetch_add(&gl_diag_indices, (uint64_t)count, __ATOMIC_RELAXED);
    __atomic_fetch_add(offscreen ? &gl_diag_indices_offscreen
                                 : &gl_diag_indices_default,
                       (uint64_t)count, __ATOMIC_RELAXED);
  }
  gl_diag_trace_default_draw("elements", count, 1);
  glDrawElements(mode, count, type, indices);
}

#ifndef GL_DRAW_FRAMEBUFFER
#define GL_DRAW_FRAMEBUFFER 0x8CA9
#endif

static void gl_diag_sample_rgb(const GLint viewport[4], GLint read_format,
                               GLint read_type, unsigned int *nonzero,
                               unsigned int *max_value,
                               unsigned long long *sum) {
  *nonzero = 0;
  *max_value = 0;
  *sum = 0;
  if (viewport[2] < 16 || viewport[3] < 16 ||
      (read_format != GL_RGBA && read_format != 0x80E1))
    return;

  const GLint x = viewport[0] + viewport[2] / 2 - 8;
  const GLint y = viewport[1] + viewport[3] / 2 - 8;
  if (read_type == GL_UNSIGNED_BYTE) {
    unsigned char pixels[16 * 16 * 4] = {0};
    glReadPixels(x, y, 16, 16, (GLenum)read_format, (GLenum)read_type, pixels);
    for (unsigned int pixel = 0; pixel < 16 * 16; pixel++)
      for (unsigned int channel = 0; channel < 3; channel++) {
        const unsigned int value = pixels[pixel * 4 + channel];
        *sum += value;
        if (value)
          (*nonzero)++;
        if (value > *max_value)
          *max_value = value;
      }
  } else if (read_type == 0x140B) { // GL_HALF_FLOAT
    uint16_t pixels[16 * 16 * 4] = {0};
    glReadPixels(x, y, 16, 16, (GLenum)read_format, (GLenum)read_type, pixels);
    for (unsigned int pixel = 0; pixel < 16 * 16; pixel++)
      for (unsigned int channel = 0; channel < 3; channel++) {
        const unsigned int value = pixels[pixel * 4 + channel];
        *sum += value;
        if (value)
          (*nonzero)++;
        if (value > *max_value)
          *max_value = value;
      }
  }
}

static unsigned int gl_diag_sample_offscreen(GLuint framebuffer) {
  static volatile uint32_t transition_count;
  const uint32_t transition =
      __atomic_add_fetch(&transition_count, 1, __ATOMIC_RELAXED);
  if (transition > 3 && (transition % 120) != 0)
    return 0;

  GLint viewport[4] = {0};
  GLint color_type = GL_NONE;
  GLint color_name = 0;
  GLint depth_type = GL_NONE;
  GLint depth_name = 0;
  GLint read_format = 0;
  GLint read_type = 0;
  glGetIntegerv(GL_VIEWPORT, viewport);
  glGetIntegerv(GL_IMPLEMENTATION_COLOR_READ_FORMAT, &read_format);
  glGetIntegerv(GL_IMPLEMENTATION_COLOR_READ_TYPE, &read_type);
  glGetFramebufferAttachmentParameteriv(
      GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
      GL_FRAMEBUFFER_ATTACHMENT_OBJECT_TYPE, &color_type);
  glGetFramebufferAttachmentParameteriv(
      GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
      GL_FRAMEBUFFER_ATTACHMENT_OBJECT_NAME, &color_name);
  glGetFramebufferAttachmentParameteriv(
      GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT,
      GL_FRAMEBUFFER_ATTACHMENT_OBJECT_TYPE, &depth_type);
  glGetFramebufferAttachmentParameteriv(
      GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT,
      GL_FRAMEBUFFER_ATTACHMENT_OBJECT_NAME, &depth_name);
  const GLenum status = glCheckFramebufferStatus(GL_FRAMEBUFFER);

  unsigned int nonzero = 0;
  unsigned int max_value = 0;
  unsigned long long sum = 0;
  if (status == GL_FRAMEBUFFER_COMPLETE && color_type != GL_NONE)
    gl_diag_sample_rgb(viewport, read_format, read_type, &nonzero, &max_value,
                       &sum);

  debugPrintf("GL offscreen transition=%u fbo=%u status=0x%x "
              "vp=%d,%d,%d,%d color=0x%x/%d depth=0x%x/%d "
              "read=0x%x/0x%x sample=%u/%u/%llu\n",
              transition, framebuffer, status, viewport[0], viewport[1],
              viewport[2], viewport[3], color_type, color_name, depth_type,
              depth_name, read_format, read_type, nonzero, max_value, sum);
  return nonzero;
}

static void glBindFramebuffer_diag(GLenum target, GLuint framebuffer) {
  const int slot = mc_current_slot();
  if ((target == GL_FRAMEBUFFER || target == GL_DRAW_FRAMEBUFFER) &&
      slot >= 0 && g_mc[slot].framebuffer != 0 && framebuffer == 0) {
    const unsigned int sample =
        gl_diag_sample_offscreen(g_mc[slot].framebuffer);
    if (sample)
      g_mc[slot].trace_default_draws = 12;
  }
  glBindFramebuffer(target, framebuffer);
  if (target == GL_FRAMEBUFFER || target == GL_DRAW_FRAMEBUFFER) {
    if (slot >= 0)
      g_mc[slot].framebuffer = framebuffer;
    __atomic_fetch_add(framebuffer ? &gl_diag_bind_offscreen
                                   : &gl_diag_bind_default,
                       1, __ATOMIC_RELAXED);
  }
}

static void glViewport_diag(GLint x, GLint y, GLsizei width, GLsizei height) {
  const int slot = mc_current_slot();
  if (slot >= 0) {
    g_mc[slot].viewport[0] = x;
    g_mc[slot].viewport[1] = y;
    g_mc[slot].viewport[2] = width;
    g_mc[slot].viewport[3] = height;
  }
  glViewport(x, y, width, height);
}

static void glClear_diag(GLbitfield mask) {
  const int slot = mc_current_slot();
  const int offscreen = slot >= 0 && g_mc[slot].framebuffer != 0;
  __atomic_fetch_add(offscreen ? &gl_diag_clear_offscreen
                               : &gl_diag_clear_default,
                     1, __ATOMIC_RELAXED);
  glClear(mask);
}

static GLenum glCheckFramebufferStatus_diag(GLenum target) {
  const GLenum status = glCheckFramebufferStatus(target);
  if (status != GL_FRAMEBUFFER_COMPLETE) {
    static volatile uint32_t failure_count;
    const uint32_t failure =
        __atomic_add_fetch(&failure_count, 1, __ATOMIC_RELAXED);
    if (failure <= 20)
      debugPrintf("GL framebuffer INCOMPLETE target=0x%x status=0x%x tls=%p\n",
                  target, status, mc_thread_key());
  }
  return status;
}

typedef void (*GLBlitFramebufferProc)(GLint, GLint, GLint, GLint, GLint, GLint,
                                      GLint, GLint, GLbitfield, GLenum);
static GLBlitFramebufferProc gl_blit_framebuffer_real;
typedef void (*GLDrawElementsInstancedProc)(GLenum, GLsizei, GLenum,
                                            const void *, GLsizei);
typedef void (*GLDrawArraysInstancedProc)(GLenum, GLint, GLsizei, GLsizei);
typedef void (*GLClearBufferfvProc)(GLenum, GLint, const GLfloat *);
typedef void (*GLClearBufferivProc)(GLenum, GLint, const GLint *);
typedef void (*GLClearBufferuivProc)(GLenum, GLint, const GLuint *);
typedef void (*GLClearBufferfiProc)(GLenum, GLint, GLfloat, GLint);
typedef void (*GLDiscardFramebufferEXTProc)(GLenum, GLsizei, const GLenum *);
typedef void (*GLTexStorage2DProc)(GLenum, GLsizei, GLenum, GLsizei, GLsizei);
typedef void (*GLBindSamplerProc)(GLuint, GLuint);
typedef void (*GLSamplerParameteriProc)(GLuint, GLenum, GLint);
static GLDrawElementsInstancedProc gl_draw_elements_instanced_real;
static GLDrawArraysInstancedProc gl_draw_arrays_instanced_real;
static GLClearBufferfvProc gl_clear_buffer_fv_real;
static GLClearBufferivProc gl_clear_buffer_iv_real;
static GLClearBufferuivProc gl_clear_buffer_uiv_real;
static GLClearBufferfiProc gl_clear_buffer_fi_real;
static GLDiscardFramebufferEXTProc gl_discard_framebuffer_real;
static GLTexStorage2DProc gl_tex_storage_2d_real;
static GLBindSamplerProc gl_bind_sampler_real;
static GLSamplerParameteriProc gl_sampler_parameteri_real;

static void glBlitFramebuffer_diag(GLint src_x0, GLint src_y0, GLint src_x1,
                                   GLint src_y1, GLint dst_x0, GLint dst_y0,
                                   GLint dst_x1, GLint dst_y1,
                                   GLbitfield mask, GLenum filter) {
  __atomic_fetch_add(&gl_diag_blits, 1, __ATOMIC_RELAXED);
  gl_blit_framebuffer_real(src_x0, src_y0, src_x1, src_y1, dst_x0, dst_y0,
                           dst_x1, dst_y1, mask, filter);
}

static void glDrawElementsInstanced_diag(GLenum mode, GLsizei count,
                                         GLenum type, const void *indices,
                                         GLsizei instances) {
  const uint64_t total =
      count > 0 && instances > 0 ? (uint64_t)count * instances : 0;
  __atomic_fetch_add(&gl_diag_draw_elements, 1, __ATOMIC_RELAXED);
  __atomic_fetch_add(&gl_diag_indices, total, __ATOMIC_RELAXED);
  const int slot = mc_current_slot();
  const int offscreen = slot >= 0 && g_mc[slot].framebuffer != 0;
  __atomic_fetch_add(offscreen ? &gl_diag_draw_offscreen
                               : &gl_diag_draw_default,
                     1, __ATOMIC_RELAXED);
  __atomic_fetch_add(offscreen ? &gl_diag_indices_offscreen
                               : &gl_diag_indices_default,
                     total, __ATOMIC_RELAXED);
  gl_diag_trace_default_draw("elements-instanced", count, instances);
  gl_draw_elements_instanced_real(mode, count, type, indices, instances);
}

static void glDrawArraysInstanced_diag(GLenum mode, GLint first, GLsizei count,
                                       GLsizei instances) {
  const uint64_t total =
      count > 0 && instances > 0 ? (uint64_t)count * instances : 0;
  __atomic_fetch_add(&gl_diag_draw_arrays, 1, __ATOMIC_RELAXED);
  __atomic_fetch_add(&gl_diag_vertices, total, __ATOMIC_RELAXED);
  const int slot = mc_current_slot();
  const int offscreen = slot >= 0 && g_mc[slot].framebuffer != 0;
  __atomic_fetch_add(offscreen ? &gl_diag_draw_offscreen
                               : &gl_diag_draw_default,
                     1, __ATOMIC_RELAXED);
  gl_diag_trace_default_draw("arrays-instanced", count, instances);
  gl_draw_arrays_instanced_real(mode, first, count, instances);
}

static void gl_diag_dynamic_clear(void) {
  const int slot = mc_current_slot();
  const int offscreen = slot >= 0 && g_mc[slot].framebuffer != 0;
  __atomic_fetch_add(offscreen ? &gl_diag_clear_offscreen
                               : &gl_diag_clear_default,
                     1, __ATOMIC_RELAXED);
}

static void glClearBufferfv_diag(GLenum buffer, GLint drawbuffer,
                                 const GLfloat *value) {
  gl_diag_dynamic_clear();
  gl_clear_buffer_fv_real(buffer, drawbuffer, value);
}

static void glClearBufferiv_diag(GLenum buffer, GLint drawbuffer,
                                 const GLint *value) {
  gl_diag_dynamic_clear();
  gl_clear_buffer_iv_real(buffer, drawbuffer, value);
}

static void glClearBufferuiv_diag(GLenum buffer, GLint drawbuffer,
                                  const GLuint *value) {
  gl_diag_dynamic_clear();
  gl_clear_buffer_uiv_real(buffer, drawbuffer, value);
}

static void glClearBufferfi_diag(GLenum buffer, GLint drawbuffer, GLfloat depth,
                                 GLint stencil) {
  gl_diag_dynamic_clear();
  gl_clear_buffer_fi_real(buffer, drawbuffer, depth, stencil);
}

static void glDiscardFramebufferEXT_diag(GLenum target, GLsizei count,
                                         const GLenum *attachments) {
  static volatile uint32_t discard_count;
  const uint32_t discard =
      __atomic_add_fetch(&discard_count, 1, __ATOMIC_RELAXED);
  if (discard <= 12 || (discard % 120) == 0) {
    const int slot = mc_current_slot();
    const GLuint framebuffer = slot >= 0 ? g_mc[slot].framebuffer : 0;
    const GLenum a0 = count > 0 && attachments ? attachments[0] : 0;
    const GLenum a1 = count > 1 && attachments ? attachments[1] : 0;
    const GLenum a2 = count > 2 && attachments ? attachments[2] : 0;
    const GLenum a3 = count > 3 && attachments ? attachments[3] : 0;
    debugPrintf("GL discard=%u fbo=%u target=0x%x count=%d "
                "attachments=0x%x,0x%x,0x%x,0x%x\n",
                discard, framebuffer, target, count, a0, a1, a2, a3);
  }
  gl_discard_framebuffer_real(target, count, attachments);
}

static void glTexStorage2D_compat(GLenum target, GLsizei levels,
                                  GLenum internal_format, GLsizei width,
                                  GLsizei height) {
  GLenum actual_format = internal_format;
  if (internal_format == 0x881A) { // GL_RGBA16F
    static volatile uint32_t conversion_count;
    const uint32_t conversion =
        __atomic_add_fetch(&conversion_count, 1, __ATOMIC_RELAXED);
    if (conversion <= 64) {
      GLint texture = 0;
      if (target == GL_TEXTURE_2D)
        glGetIntegerv(GL_TEXTURE_BINDING_2D, &texture);
      debugPrintf("GL TexStorage2D RGBA16F[%u] tex=%d target=0x%x "
                  "levels=%d size=%dx%d format=0x%x->0x%x\n",
                  conversion, texture, target, levels, width, height,
                  internal_format, actual_format);
    }
  }
  gl_tex_storage_2d_real(target, levels, actual_format, width, height);
}

static void glBindSampler_diag(GLuint unit, GLuint sampler) {
  const int slot = mc_current_slot();
  if (slot >= 0 && unit < 8)
    g_mc[slot].sampler[unit] = sampler;
  gl_bind_sampler_real(unit, sampler);
}

static void glSamplerParameteri_diag(GLuint sampler, GLenum pname, GLint param) {
  static volatile uint32_t parameter_count;
  const uint32_t setting =
      __atomic_add_fetch(&parameter_count, 1, __ATOMIC_RELAXED);
  if (setting <= 80)
    debugPrintf("GL sampler parameter[%u] sampler=%u pname=0x%x value=0x%x\n",
                setting, sampler, pname, param);
  gl_sampler_parameteri_real(sampler, pname, param);
}

static __eglMustCastToProperFunctionPointerType
eglGetProcAddress_diag(const char *name) {
  __eglMustCastToProperFunctionPointerType proc = eglGetProcAddress(name);
  static volatile uint32_t getproc_count;
  const uint32_t request =
      __atomic_add_fetch(&getproc_count, 1, __ATOMIC_RELAXED);
  if (request <= 160)
    debugPrintf("eglGetProcAddress[%u](%s) -> %p\n", request,
                name ? name : "(null)", (void *)proc);
  if (name && !strcmp(name, "glBlitFramebuffer") && proc) {
    gl_blit_framebuffer_real = (GLBlitFramebufferProc)proc;
    return (__eglMustCastToProperFunctionPointerType)&glBlitFramebuffer_diag;
  }
  if (name && !strcmp(name, "glDrawElementsInstanced") && proc) {
    gl_draw_elements_instanced_real = (GLDrawElementsInstancedProc)proc;
    return (__eglMustCastToProperFunctionPointerType)
        &glDrawElementsInstanced_diag;
  }
  if (name && !strcmp(name, "glDrawArraysInstanced") && proc) {
    gl_draw_arrays_instanced_real = (GLDrawArraysInstancedProc)proc;
    return (__eglMustCastToProperFunctionPointerType)&glDrawArraysInstanced_diag;
  }
  if (name && !strcmp(name, "glClearBufferfv") && proc) {
    gl_clear_buffer_fv_real = (GLClearBufferfvProc)proc;
    return (__eglMustCastToProperFunctionPointerType)&glClearBufferfv_diag;
  }
  if (name && !strcmp(name, "glClearBufferiv") && proc) {
    gl_clear_buffer_iv_real = (GLClearBufferivProc)proc;
    return (__eglMustCastToProperFunctionPointerType)&glClearBufferiv_diag;
  }
  if (name && !strcmp(name, "glClearBufferuiv") && proc) {
    gl_clear_buffer_uiv_real = (GLClearBufferuivProc)proc;
    return (__eglMustCastToProperFunctionPointerType)&glClearBufferuiv_diag;
  }
  if (name && !strcmp(name, "glClearBufferfi") && proc) {
    gl_clear_buffer_fi_real = (GLClearBufferfiProc)proc;
    return (__eglMustCastToProperFunctionPointerType)&glClearBufferfi_diag;
  }
  if (name && !strcmp(name, "glDiscardFramebufferEXT") && proc) {
    gl_discard_framebuffer_real = (GLDiscardFramebufferEXTProc)proc;
    return (__eglMustCastToProperFunctionPointerType)
        &glDiscardFramebufferEXT_diag;
  }
  if (name && !strcmp(name, "glTexStorage2D") && proc) {
    gl_tex_storage_2d_real = (GLTexStorage2DProc)proc;
    return (__eglMustCastToProperFunctionPointerType)&glTexStorage2D_compat;
  }
  if (name && !strcmp(name, "glBindSampler") && proc) {
    gl_bind_sampler_real = (GLBindSamplerProc)proc;
    return (__eglMustCastToProperFunctionPointerType)&glBindSampler_diag;
  }
  if (name && !strcmp(name, "glSamplerParameteri") && proc) {
    gl_sampler_parameteri_real = (GLSamplerParameteriProc)proc;
    return (__eglMustCastToProperFunctionPointerType)&glSamplerParameteri_diag;
  }
  return proc;
}

static void glCompileShader_diag(GLuint shader) {
  glCompileShader(shader);
  GLint status = GL_FALSE;
  glGetShaderiv(shader, GL_COMPILE_STATUS, &status);
  if (status == GL_TRUE) {
    __atomic_fetch_add(&gl_diag_compile_ok, 1, __ATOMIC_RELAXED);
    return;
  }

  __atomic_fetch_add(&gl_diag_compile_fail, 1, __ATOMIC_RELAXED);
  GLint type = 0;
  GLsizei length = 0;
  char log[8192] = {0};
  glGetShaderiv(shader, GL_SHADER_TYPE, &type);
  glGetShaderInfoLog(shader, sizeof(log) - 1, &length, log);
  debugPrintf("GL shader compile FAILED id=%u type=0x%x len=%d: %s\n",
              shader, type, length, log[0] ? log : "(empty log)");
}

static void glLinkProgram_diag(GLuint program) {
  glLinkProgram(program);
  GLint status = GL_FALSE;
  glGetProgramiv(program, GL_LINK_STATUS, &status);
  if (status == GL_TRUE) {
    __atomic_fetch_add(&gl_diag_link_ok, 1, __ATOMIC_RELAXED);
    return;
  }

  __atomic_fetch_add(&gl_diag_link_fail, 1, __ATOMIC_RELAXED);
  GLsizei length = 0;
  char log[8192] = {0};
  glGetProgramInfoLog(program, sizeof(log) - 1, &length, log);
  debugPrintf("GL program link FAILED id=%u len=%d: %s\n", program, length,
              log[0] ? log : "(empty log)");
}

// Frame boundary: invalidate the state cache once per frame, then run the real
// swap hook. The wrapper's own direct GL there (movie player / FPS overlay) goes
// around the cache, so this keeps the game's next frame from trusting a stale
// entry. Kept in this TU so no cross-file symbol is needed. eglSwapBuffersHook is
// defined in movie_player.c (already referenced by the import table below).
extern unsigned int eglSwapBuffersHook(void *display, void *surface);
static unsigned int eglSwapBuffers_cache(void *display, void *surface) {
  static volatile unsigned int swap_count;
  const unsigned int frame = __sync_add_and_fetch(&swap_count, 1);
  const uint64_t arrays =
      __atomic_exchange_n(&gl_diag_draw_arrays, 0, __ATOMIC_RELAXED);
  const uint64_t elements =
      __atomic_exchange_n(&gl_diag_draw_elements, 0, __ATOMIC_RELAXED);
  const uint64_t vertices =
      __atomic_exchange_n(&gl_diag_vertices, 0, __ATOMIC_RELAXED);
  const uint64_t indices =
      __atomic_exchange_n(&gl_diag_indices, 0, __ATOMIC_RELAXED);
  const uint64_t draw_default =
      __atomic_exchange_n(&gl_diag_draw_default, 0, __ATOMIC_RELAXED);
  const uint64_t draw_offscreen =
      __atomic_exchange_n(&gl_diag_draw_offscreen, 0, __ATOMIC_RELAXED);
  const uint64_t indices_default =
      __atomic_exchange_n(&gl_diag_indices_default, 0, __ATOMIC_RELAXED);
  const uint64_t indices_offscreen =
      __atomic_exchange_n(&gl_diag_indices_offscreen, 0, __ATOMIC_RELAXED);
  const uint64_t bind_default =
      __atomic_exchange_n(&gl_diag_bind_default, 0, __ATOMIC_RELAXED);
  const uint64_t bind_offscreen =
      __atomic_exchange_n(&gl_diag_bind_offscreen, 0, __ATOMIC_RELAXED);
  const uint64_t clear_default =
      __atomic_exchange_n(&gl_diag_clear_default, 0, __ATOMIC_RELAXED);
  const uint64_t clear_offscreen =
      __atomic_exchange_n(&gl_diag_clear_offscreen, 0, __ATOMIC_RELAXED);
  const uint64_t blits =
      __atomic_exchange_n(&gl_diag_blits, 0, __ATOMIC_RELAXED);
  if (frame <= 10 || (frame % 120) == 0) {
    GLint framebuffer = 0;
    GLint viewport[4] = {0};
    GLint program = 0;
    GLboolean color_mask[4] = {0};
    GLboolean depth_mask = GL_FALSE;
    glGetIntegerv(GL_FRAMEBUFFER_BINDING, &framebuffer);
    glGetIntegerv(GL_VIEWPORT, viewport);
    glGetIntegerv(GL_CURRENT_PROGRAM, &program);
    glGetBooleanv(GL_COLOR_WRITEMASK, color_mask);
    glGetBooleanv(GL_DEPTH_WRITEMASK, &depth_mask);
    const GLenum framebuffer_status = glCheckFramebufferStatus(GL_FRAMEBUFFER);
    GLint read_format = 0;
    GLint read_type = 0;
    unsigned int back_nonzero = 0;
    unsigned int back_max = 0;
    unsigned long long back_sum = 0;
    glGetIntegerv(GL_IMPLEMENTATION_COLOR_READ_FORMAT, &read_format);
    glGetIntegerv(GL_IMPLEMENTATION_COLOR_READ_TYPE, &read_type);
    gl_diag_sample_rgb(viewport, read_format, read_type, &back_nonzero,
                       &back_max, &back_sum);
    debugPrintf("GL frame=%u draw_arrays=%llu/%llu draw_elements=%llu/%llu "
                "target=%llu/%llu idx=%llu/%llu bind=%llu/%llu "
                "clear=%llu/%llu blit=%llu fbo=%d/0x%x vp=%d,%d,%d,%d "
                "program=%d mask=%d%d%d%d depth=%d back=0x%x/0x%x/%u/%u/%llu "
                "shader=%u/%u link=%u/%u tls=%p surface=%p\n",
                frame, (unsigned long long)arrays,
                (unsigned long long)vertices, (unsigned long long)elements,
                (unsigned long long)indices, (unsigned long long)draw_default,
                (unsigned long long)draw_offscreen,
                (unsigned long long)indices_default,
                (unsigned long long)indices_offscreen,
                (unsigned long long)bind_default,
                (unsigned long long)bind_offscreen,
                (unsigned long long)clear_default,
                (unsigned long long)clear_offscreen,
                (unsigned long long)blits, framebuffer, framebuffer_status,
                viewport[0], viewport[1], viewport[2], viewport[3], program,
                color_mask[0], color_mask[1], color_mask[2], color_mask[3],
                depth_mask, read_format, read_type, back_nonzero, back_max,
                back_sum,
                __atomic_load_n(&gl_diag_compile_ok, __ATOMIC_RELAXED),
                __atomic_load_n(&gl_diag_compile_fail, __ATOMIC_RELAXED),
                __atomic_load_n(&gl_diag_link_ok, __ATOMIC_RELAXED),
                __atomic_load_n(&gl_diag_link_fail, __ATOMIC_RELAXED),
                mc_thread_key(), surface);
  }
  gl_state_cache_reset();
  return eglSwapBuffersHook(display, surface);
}

#ifndef EGL_OPENGL_ES3_BIT
#define EGL_OPENGL_ES3_BIT 0x00000040
#endif

#define FAKE_PBUFFER_MAGIC 0x50425546u

typedef struct {
  uint32_t magic;
  EGLint width;
  EGLint height;
} FakePbuffer;

static EGLSurface main_window_surface = EGL_NO_SURFACE;

#define GL_DIAG_CONTEXTS 16
static EGLContext gl_diag_contexts[GL_DIAG_CONTEXTS];

static void gl_log_context_once(EGLContext context) {
  for (int i = 0; i < GL_DIAG_CONTEXTS; i++) {
    if (gl_diag_contexts[i] == context)
      return;
    if (gl_diag_contexts[i] == EGL_NO_CONTEXT) {
      gl_diag_contexts[i] = context;
      debugPrintf("GL context=%p version=%s glsl=%s vendor=%s renderer=%s\n",
                  context, glGetString(GL_VERSION),
                  glGetString(GL_SHADING_LANGUAGE_VERSION),
                  glGetString(GL_VENDOR), glGetString(GL_RENDERER));
      return;
    }
  }
}

static EGLint egl_attrib_value(const EGLint *attribs, EGLint key,
                               EGLint fallback) {
  if (!attribs)
    return fallback;
  for (int i = 0; i < 62 && attribs[i] != EGL_NONE; i += 2)
    if (attribs[i] == key)
      return attribs[i + 1];
  return fallback;
}

static FakePbuffer *fake_pbuffer(EGLSurface surface) {
  if (surface == EGL_NO_SURFACE)
    return NULL;
  FakePbuffer *pbuffer = (FakePbuffer *)surface;
  return pbuffer->magic == FAKE_PBUFFER_MAGIC ? pbuffer : NULL;
}

static EGLBoolean eglChooseConfig_compat(EGLDisplay dpy,
                                         const EGLint *attrib_list,
                                         EGLConfig *configs,
                                         EGLint config_size,
                                         EGLint *num_config) {
  EGLint attribs[64];
  int n = 0;
  int saw_renderable = 0;
  if (attrib_list) {
    while (n < 60 && attrib_list[n] != EGL_NONE) {
      attribs[n] = attrib_list[n];
      attribs[n + 1] = attrib_list[n + 1];
      if (attribs[n] == EGL_SURFACE_TYPE)
        attribs[n + 1] &= ~EGL_PBUFFER_BIT;
      if (attribs[n] == EGL_RENDERABLE_TYPE) {
        attribs[n + 1] |= EGL_OPENGL_ES3_BIT;
        saw_renderable = 1;
      }
      n += 2;
    }
  }
  if (!saw_renderable && n < 60) {
    attribs[n++] = EGL_RENDERABLE_TYPE;
    attribs[n++] = EGL_OPENGL_ES3_BIT;
  }
  attribs[n] = EGL_NONE;

  EGLBoolean result =
      eglChooseConfig(dpy, attribs, configs, config_size, num_config);
  if (result == EGL_TRUE && num_config && *num_config > 0) {
    debugPrintf("eglChooseConfig compat -> %d configs\n", *num_config);
    return result;
  }

  static const EGLint relaxed[] = {
      EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8,
      EGL_ALPHA_SIZE, 8, EGL_DEPTH_SIZE, 24, EGL_STENCIL_SIZE, 8,
      EGL_RENDERABLE_TYPE, EGL_OPENGL_ES3_BIT,
      EGL_SURFACE_TYPE, EGL_WINDOW_BIT, EGL_NONE};
  static const EGLint minimal[] = {
      EGL_RENDERABLE_TYPE, EGL_OPENGL_ES3_BIT, EGL_NONE};
  const EGLint *fallbacks[] = {relaxed, minimal};
  for (unsigned int i = 0; i < 2; i++) {
    result = eglChooseConfig(dpy, fallbacks[i], configs, config_size,
                             num_config);
    if (result == EGL_TRUE && num_config && *num_config > 0) {
      debugPrintf("eglChooseConfig fallback[%u] -> %d configs\n", i,
                  *num_config);
      return result;
    }
  }
  debugPrintf("eglChooseConfig failed err=%x\n", eglGetError());
  return result;
}

static EGLContext eglCreateContext_compat(EGLDisplay dpy, EGLConfig config,
                                          EGLContext share,
                                          const EGLint *attribs) {
  EGLContext context = eglCreateContext(dpy, config, share, attribs);
  debugPrintf("eglCreateContext(dpy=%p config=%p share=%p version=%d) -> %p "
              "err=%x\n",
              dpy, config, share,
              egl_attrib_value(attribs, EGL_CONTEXT_CLIENT_VERSION, 0), context,
              context != EGL_NO_CONTEXT ? EGL_SUCCESS : eglGetError());
  return context;
}

static EGLSurface eglCreateWindowSurface_cache(EGLDisplay dpy,
                                                EGLConfig config,
                                                EGLNativeWindowType window,
                                                const EGLint *attribs) {
  EGLSurface surface = eglCreateWindowSurface(dpy, config, window, attribs);
  if (surface != EGL_NO_SURFACE) {
    main_window_surface = surface;
  }
  debugPrintf("eglCreateWindowSurface(dpy=%p config=%p window=%p) -> %p "
              "err=%x\n",
              dpy, config, window, surface,
              surface != EGL_NO_SURFACE ? EGL_SUCCESS : eglGetError());
  return surface;
}

static EGLSurface eglCreatePbufferSurface_compat(EGLDisplay dpy,
                                                 EGLConfig config,
                                                 const EGLint *attribs) {
  EGLSurface surface = eglCreatePbufferSurface(dpy, config, attribs);
  if (surface != EGL_NO_SURFACE)
    return surface;
  (void)eglGetError();

  FakePbuffer *pbuffer = calloc(1, sizeof(*pbuffer));
  if (!pbuffer)
    return EGL_NO_SURFACE;
  pbuffer->magic = FAKE_PBUFFER_MAGIC;
  pbuffer->width = egl_attrib_value(attribs, EGL_WIDTH, 1);
  pbuffer->height = egl_attrib_value(attribs, EGL_HEIGHT, 1);
  if (pbuffer->width <= 0)
    pbuffer->width = 1;
  if (pbuffer->height <= 0)
    pbuffer->height = 1;
  debugPrintf("eglCreatePbufferSurface -> fake %p (%dx%d)\n", pbuffer,
              pbuffer->width, pbuffer->height);
  return (EGLSurface)pbuffer;
}

static EGLBoolean eglMakeCurrent_dedup(EGLDisplay dpy, EGLSurface draw,
                                       EGLSurface read, EGLContext ctx) {
  EGLSurface real_draw = draw;
  EGLSurface real_read = read;
  const int mapped_pbuffer = fake_pbuffer(draw) || fake_pbuffer(read);
  if (mapped_pbuffer)
    real_draw = real_read = EGL_NO_SURFACE;
  void *key = mc_thread_key();
  int slot = -1, freeslot = -1;
  for (int i = 0; i < MC_SLOTS; i++) {
    if (g_mc[i].key == key) { slot = i; break; }
    if (!g_mc[i].key && freeslot < 0) freeslot = i;
  }
  if (slot >= 0 && g_mc[slot].dpy == dpy && g_mc[slot].draw == real_draw &&
      g_mc[slot].read == real_read && g_mc[slot].ctx == ctx &&
      eglGetCurrentContext() == ctx)
    return EGL_TRUE;

  EGLBoolean r = eglMakeCurrent(dpy, real_draw, real_read, ctx);
  EGLint error = r ? EGL_SUCCESS : eglGetError();
  // Mesa normally supports surfaceless contexts. Keep the window fallback for
  // hardware/driver combinations that reject EGL_NO_SURFACE.
  if (!r && mapped_pbuffer && main_window_surface != EGL_NO_SURFACE) {
    real_draw = real_read = main_window_surface;
    r = eglMakeCurrent(dpy, real_draw, real_read, ctx);
    error = r ? EGL_SUCCESS : eglGetError();
  }
  debugPrintf("eglMakeCurrent(dpy=%p draw=%p read=%p ctx=%p%s) -> %d err=%x\n",
              dpy, real_draw, real_read, ctx,
              mapped_pbuffer ? " fake-pbuffer" : "", r, error);
  if (r) {
    if (ctx != EGL_NO_CONTEXT)
      gl_log_context_once(ctx);
    gl_state_cache_reset(); // context/surface changed -> GL state cache is stale
    if (slot < 0) slot = (freeslot >= 0) ? freeslot : 0;
    g_mc[slot].key = key; g_mc[slot].dpy = dpy;
    g_mc[slot].draw = real_draw; g_mc[slot].read = real_read;
    g_mc[slot].ctx = ctx;
  }
  return r;
}

static EGLBoolean eglDestroyContext_cache(EGLDisplay dpy, EGLContext ctx) {
  for (int i = 0; i < MC_SLOTS; i++) {
    if (g_mc[i].ctx == ctx)
      memset(&g_mc[i], 0, sizeof(g_mc[i]));
  }
  const EGLBoolean result = eglDestroyContext(dpy, ctx);
  debugPrintf("eglDestroyContext(dpy=%p ctx=%p) -> %d\n", dpy, ctx, result);
  return result;
}

static EGLBoolean eglDestroySurface_cache(EGLDisplay dpy, EGLSurface surface) {
  FakePbuffer *pbuffer = fake_pbuffer(surface);
  if (pbuffer) {
    free(pbuffer);
    return EGL_TRUE;
  }
  for (int i = 0; i < MC_SLOTS; i++) {
    if (g_mc[i].draw == surface || g_mc[i].read == surface)
      memset(&g_mc[i], 0, sizeof(g_mc[i]));
  }
  if (surface == main_window_surface)
    main_window_surface = EGL_NO_SURFACE;
  const EGLBoolean result = eglDestroySurface(dpy, surface);
  debugPrintf("eglDestroySurface(dpy=%p surface=%p) -> %d\n",
              dpy, surface, result);
  return result;
}

static EGLBoolean eglQuerySurface_compat(EGLDisplay dpy, EGLSurface surface,
                                         EGLint attribute, EGLint *value) {
  FakePbuffer *pbuffer = fake_pbuffer(surface);
  if (pbuffer) {
    if (value) {
      if (attribute == EGL_WIDTH)
        *value = pbuffer->width;
      else if (attribute == EGL_HEIGHT)
        *value = pbuffer->height;
      else
        *value = 0;
    }
    return EGL_TRUE;
  }
  EGLBoolean result = eglQuerySurface(dpy, surface, attribute, value);
  if (result == EGL_TRUE && value && *value == 0) {
    if (attribute == EGL_WIDTH)
      *value = screen_width;
    else if (attribute == EGL_HEIGHT)
      *value = screen_height;
  }
  return result;
}

// mesa nouveau_mm slab-allocator replacement (-Wl,--wrap): mesa's small-buffer
// sub-allocator corrupts its slab pool under the world load, so replace it with
// a bump-slab pool of large bos, sub-allocated linearly and never freed.
// nouveau_mman layout { dev@0; bucket[15]; uint32_t domain@848; config@852 };
// handle is malloc(24) { next@0; priv@8; uint32_t offset@16 }.
extern int nouveau_bo_new(void *dev, uint32_t flags, uint32_t align,
                          uint64_t size, const void *config, void **bo);
extern int nouveau_bo_ref(void *bo, void **pref);

#define NMM_DEV(c)    (*(void **)((char *)(c) + 0))
#define NMM_DOMAIN(c) (*(uint32_t *)((char *)(c) + 848))
#define NMM_CONFIG(c) ((const void *)((char *)(c) + 852))

#define NMM_ALIGN      256u
#define NMM_SLAB_BYTES (2u * 1024 * 1024)   // 2 MB per slab
#define NMM_BIG_THRESH (512u * 1024)        // > this -> its own dedicated bo
#define NMM_MAX_SLABS  1024

struct nmm_slab { void *cache; void *bo; uint64_t size; uint64_t cur; };
static struct nmm_slab g_nmm_slabs[NMM_MAX_SLABS];
static int g_nmm_nslabs = 0;
static pthread_mutex_t g_nmm_mtx = PTHREAD_MUTEX_INITIALIZER;

// dedicated, right-sized bo (mirrors mesa's >2MB path: NULL handle, *bo set)
static void *nmm_dedicated(void *cache, uint32_t sz, void **bo, uint32_t *offset) {
  void *nb = NULL;
  if (nouveau_bo_new(NMM_DEV(cache), NMM_DOMAIN(cache), 0, sz, NMM_CONFIG(cache), &nb) || !nb)
    nb = NULL;
  if (bo) *bo = nb;
  if (offset) *offset = 0;
  return NULL;
}

void *__wrap_nouveau_mm_allocate(void *cache, uint32_t size, void **bo, uint32_t *offset) {
  uint32_t asz = (size + (NMM_ALIGN - 1)) & ~(NMM_ALIGN - 1);
  if (asz == 0) asz = NMM_ALIGN;
  if (asz > NMM_BIG_THRESH)
    return nmm_dedicated(cache, asz, bo, offset);

  pthread_mutex_lock(&g_nmm_mtx);
  struct nmm_slab *s = NULL;
  for (int i = g_nmm_nslabs - 1; i >= 0; i--) {       // newest first (bump locality)
    if (g_nmm_slabs[i].cache == cache &&
        (g_nmm_slabs[i].size - g_nmm_slabs[i].cur) >= asz) { s = &g_nmm_slabs[i]; break; }
  }
  if (!s) {
    if (g_nmm_nslabs >= NMM_MAX_SLABS) {              // table full -> dedicated bo
      pthread_mutex_unlock(&g_nmm_mtx);
      return nmm_dedicated(cache, asz, bo, offset);
    }
    void *nb = NULL;
    if (nouveau_bo_new(NMM_DEV(cache), NMM_DOMAIN(cache), 0, NMM_SLAB_BYTES,
                       NMM_CONFIG(cache), &nb) || !nb) {
      pthread_mutex_unlock(&g_nmm_mtx);
      return nmm_dedicated(cache, asz, bo, offset);  // slab alloc failed -> dedicated
    }
    s = &g_nmm_slabs[g_nmm_nslabs++];
    s->cache = cache; s->bo = nb; s->size = NMM_SLAB_BYTES; s->cur = 0;
  }
  uint64_t off = s->cur;
  s->cur += asz;
  void *slab_bo = s->bo;
  pthread_mutex_unlock(&g_nmm_mtx);

  if (bo) nouveau_bo_ref(slab_bo, bo);   // *bo = slab_bo (refcount++), as stock does
  if (offset) *offset = (uint32_t)off;

  void **h = (void **)malloc(24);        // layout = struct nouveau_mm_allocation
  if (h) { h[0] = NULL; h[1] = s; *(uint32_t *)((char *)h + 16) = (uint32_t)off; }
  return h;
}

void __wrap_nouveau_mm_free(void *handle) {
  // slabs are never freed; just release the handle
  if (handle) free(handle);
}

// nouveau_mm_free_work is an intra-object alias that bypasses --wrap, so wrap it
// too to keep deferred frees of our handles away from mesa's stock free.
void __wrap_nouveau_mm_free_work(void *handle) {
  if (handle) free(handle);
}

// The world load creates thousands of buffers/textures without presenting, so
// mesa never flushes; force a periodic submit to bound the nouveau bo-list.
static void gl_load_drain(void) {
  static unsigned n = 0;
  if ((++n & 0x1ff) == 0) glFlush();
}

static void glTexImage2D_w(GLenum t, GLint l, GLint i, GLsizei w, GLsizei h,
                           GLint b, GLenum f, GLenum y, const void *p) {
  gl_load_drain();
  glTexImage2D(t, l, i, w, h, b, f, y, p);
}
static void glCompressedTexImage2D_w(GLenum t, GLint l, GLenum i, GLsizei w,
                                     GLsizei h, GLint b, GLsizei s, const void *d) {
  gl_load_drain();
  glCompressedTexImage2D(t, l, i, w, h, b, s, d);
}
static void glBufferData_w(GLenum target, GLsizeiptr size, const void *data,
                           GLenum usage) {
  gl_load_drain();
  glBufferData(target, size, data, usage);
}

FILE *stderr_fake = (FILE *)&fake_sF[2];

// OpenAL hooks living in hooks/openal.c (frequency override + device capture)
extern ALCcontext *alcCreateContextHook(ALCdevice *dev, const ALCint *unused);
extern ALCdevice *alcOpenDeviceHook(const char *name);

void __assert2(const char *file, int line, const char *func, const char *expr) {
  debugPrintf("assertion failed:\n%s:%d (%s): %s\n", file, line, func, expr);
  assert(0);
}

// bionic's fatal logger: __android_log_assert(cond, tag, fmt, ...) -> log+abort
void __android_log_assert(const char *cond, const char *tag, const char *fmt, ...) {
  char string[0x400];
  if (fmt) {
    va_list va;
    va_start(va, fmt);
    vsnprintf(string, sizeof(string), fmt, va);
    va_end(va);
  } else {
    snprintf(string, sizeof(string), "assertion \"%s\" failed", cond ? cond : "");
  }
  debugPrintf("FATAL %s: %s\n", tag ? tag : "", string);
  abort();
}

int __android_log_print(int prio, const char *tag, const char *fmt, ...) {
#ifdef DEBUG_LOG
  va_list list;
  static char string[0x1000];

  va_start(list, fmt);
  vsnprintf(string, sizeof(string), fmt, list);
  va_end(list);

  debugPrintf("%s: %s\n", tag, string);
#endif
  return 0;
}

int __android_log_write(int prio, const char *tag, const char *text) {
  debugPrintf("%s: %s\n", tag, text);
  return 0;
}

int __android_log_vprint(int prio, const char *tag, const char *fmt, va_list va) {
#ifdef DEBUG_LOG
  static char string[0x1000];
  vsnprintf(string, sizeof(string), fmt, va);
  debugPrintf("%s: %s\n", tag, string);
#endif
  return 0;
}

// pthread stuff
// have to wrap it since struct sizes are different

int pthread_mutex_init_fake(pthread_mutex_t **uid, const int *mutexattr) {
  pthread_mutex_t *m = calloc(1, sizeof(pthread_mutex_t));
  if (!m) return -1;

  // Force RECURSIVE on every engine mutex: mutexattr_settype is stubbed out, and
  // the engine relies on recursive re-locking (else the world load self-deadlocks).
  (void)mutexattr;
  *m = PTHREAD_RECURSIVE_MUTEX_INITIALIZER;
  *uid = m;
  return 0;
}

int pthread_mutex_destroy_fake(pthread_mutex_t **uid) {
  if (uid && *uid && (uintptr_t)*uid > 0x8000) {
    pthread_mutex_destroy(*uid);
    free(*uid);
    *uid = NULL;
  }
  return 0;
}

int pthread_mutex_lock_fake(pthread_mutex_t **uid) {
  static SyncTraceEntry traces[SYNC_TRACE_SLOTS];
  int ret = 0;
  if (!*uid) {
    ret = pthread_mutex_init_fake(uid, NULL);
  } else if ((uintptr_t)*uid == 0x4000) {
    int attr = 1; // recursive
    ret = pthread_mutex_init_fake(uid, &attr);
  }
  if (ret < 0) return ret;
  if (!late_sync_trace)
    return pthread_mutex_lock(*uid);

  ret = pthread_mutex_trylock(*uid);
  if (ret == 0)
    return 0;
  void *caller = __builtin_return_address(0);
  const int trace = sync_trace_once(traces, uid, caller);
  if (trace)
    debugPrintf("late mutex WAIT tls=%p uid=%p native=%p ra=%p try=%d\n",
                mc_thread_key(), uid, *uid, caller, ret);
  ret = pthread_mutex_lock(*uid);
  if (trace)
    debugPrintf("late mutex ACQUIRED tls=%p uid=%p ra=%p -> %d\n",
                mc_thread_key(), uid, caller, ret);
  return ret;
}

int pthread_mutex_trylock_fake(pthread_mutex_t **uid) {
  int ret = 0;
  if (!*uid) {
    ret = pthread_mutex_init_fake(uid, NULL);
  } else if ((uintptr_t)*uid == 0x4000) {
    int attr = 1; // recursive
    ret = pthread_mutex_init_fake(uid, &attr);
  }
  if (ret < 0) return ret;
  return pthread_mutex_trylock(*uid);
}

int pthread_mutex_unlock_fake(pthread_mutex_t **uid) {
  int ret = 0;
  if (!*uid) {
    ret = pthread_mutex_init_fake(uid, NULL);
  } else if ((uintptr_t)*uid == 0x4000) {
    int attr = 1; // recursive
    ret = pthread_mutex_init_fake(uid, &attr);
  }
  if (ret < 0) return ret;
  return pthread_mutex_unlock(*uid);
}

int pthread_cond_init_fake(pthread_cond_t **cnd, const int *condattr) {
  pthread_cond_t *c = calloc(1, sizeof(pthread_cond_t));
  if (!c) return -1;

  *c = PTHREAD_COND_INITIALIZER;

  int ret = pthread_cond_init(c, NULL);
  if (ret < 0) {
    free(c);
    return -1;
  }

  *cnd = c;

  return 0;
}

int pthread_cond_broadcast_fake(pthread_cond_t **cnd) {
  if (!*cnd) {
    if (pthread_cond_init_fake(cnd, NULL) < 0)
      return -1;
  }
  return pthread_cond_broadcast(*cnd);
}

int pthread_cond_signal_fake(pthread_cond_t **cnd) {
  if (!*cnd) {
    if (pthread_cond_init_fake(cnd, NULL) < 0)
      return -1;
  };
  return pthread_cond_signal(*cnd);
}

int pthread_cond_destroy_fake(pthread_cond_t **cnd) {
  if (cnd && *cnd) {
    pthread_cond_destroy(*cnd);
    free(*cnd);
    *cnd = NULL;
  }
  return 0;
}

int pthread_cond_wait_fake(pthread_cond_t **cnd, pthread_mutex_t **mtx) {
  static SyncTraceEntry traces[SYNC_TRACE_SLOTS];
  if (!*cnd) {
    if (pthread_cond_init_fake(cnd, NULL) < 0)
      return -1;
  }
  void *caller = __builtin_return_address(0);
  const int trace = late_sync_trace && sync_trace_once(traces, cnd, caller);
  if (trace)
    debugPrintf("late cond WAIT tls=%p cnd=%p/%p mtx=%p/%p ra=%p\n",
                mc_thread_key(), cnd, *cnd, mtx, *mtx, caller);
  const int result = pthread_cond_wait(*cnd, *mtx);
  if (trace)
    debugPrintf("late cond WAKE tls=%p cnd=%p ra=%p -> %d\n",
                mc_thread_key(), cnd, caller, result);
  return result;
}

int pthread_cond_timedwait_fake(pthread_cond_t **cnd, pthread_mutex_t **mtx, const struct timespec *t) {
  static SyncTraceEntry traces[SYNC_TRACE_SLOTS];
  if (!*cnd) {
    if (pthread_cond_init_fake(cnd, NULL) < 0)
      return -1;
  }
  void *caller = __builtin_return_address(0);
  const int trace = late_sync_trace && sync_trace_once(traces, cnd, caller);
  if (trace)
    debugPrintf("late timedcond WAIT tls=%p cnd=%p/%p mtx=%p/%p ra=%p\n",
                mc_thread_key(), cnd, *cnd, mtx, *mtx, caller);
  const int result = pthread_cond_timedwait(*cnd, *mtx, t);
  if (trace)
    debugPrintf("late timedcond WAKE tls=%p cnd=%p ra=%p -> %d\n",
                mc_thread_key(), cnd, caller, result);
  return result;
}

int pthread_once_fake(volatile int *once_control, void (*init_routine) (void)) {
  if (!once_control || !init_routine)
    return EINVAL;

  // Bionic uses 0/1/2 for uninitialized/running/complete. A competing thread
  // must wait for the initializer instead of observing partially-built state.
  int state = __atomic_load_n(once_control, __ATOMIC_ACQUIRE);
  if (state == 2)
    return 0;
  if (state == 0 && __sync_bool_compare_and_swap(once_control, 0, 1)) {
    (*init_routine)();
    __atomic_store_n(once_control, 2, __ATOMIC_RELEASE);
    return 0;
  }

  while (__atomic_load_n(once_control, __ATOMIC_ACQUIRE) != 2)
    svcSleepThread(100000);
  return 0;
}

// newlib only exposes a very small pthread-key pool on Horizon (11 usable keys
// in practice), while UE4 creates hundreds of FThreadSingleton keys. Keep the
// Android-side keys and per-thread values separate from newlib's TSD storage.
#define FAKE_TLS_MAX_KEYS 4096
#define FAKE_TLS_MAX_THREADS 64

static volatile unsigned int fake_tls_next_key = 1;
static volatile unsigned int pthread_tls_get_trace_count;
static volatile unsigned int pthread_tls_set_trace_count;
static unsigned char fake_tls_key_active[FAKE_TLS_MAX_KEYS];
static void (*fake_tls_destructors[FAKE_TLS_MAX_KEYS])(void *);
static void *fake_tls_thread_ids[FAKE_TLS_MAX_THREADS];
static void *fake_tls_values[FAKE_TLS_MAX_THREADS][FAKE_TLS_MAX_KEYS];

static int fake_tls_thread_slot(int create) {
  void *thread_id = mc_thread_key();
  if (!thread_id)
    thread_id = (void *)(uintptr_t)pthread_self();

  for (int i = 0; i < FAKE_TLS_MAX_THREADS; i++) {
    void *current = __atomic_load_n(&fake_tls_thread_ids[i], __ATOMIC_ACQUIRE);
    if (current == thread_id)
      return i;
  }
  if (!create)
    return -1;

  for (int i = 0; i < FAKE_TLS_MAX_THREADS; i++) {
    void *expected = NULL;
    if (__atomic_compare_exchange_n(&fake_tls_thread_ids[i], &expected,
                                    thread_id, 0, __ATOMIC_ACQ_REL,
                                    __ATOMIC_ACQUIRE))
      return i;
    if (expected == thread_id)
      return i;
  }
  return -1;
}

static int pthread_key_create_fake(pthread_key_t *key,
                                   void (*destructor)(void *)) {
  if (!key)
    return EINVAL;

  const unsigned int new_key = __sync_fetch_and_add(&fake_tls_next_key, 1);
  if (new_key >= FAKE_TLS_MAX_KEYS) {
    debugPrintf("pthread_key_create_fake: exhausted at %u keys\n", new_key);
    return EAGAIN;
  }

  fake_tls_destructors[new_key] = destructor;
  __atomic_store_n(&fake_tls_key_active[new_key], 1, __ATOMIC_RELEASE);
  *key = (pthread_key_t)new_key;
  if (new_key <= 32 || (new_key % 128) == 0)
    debugPrintf("pthread_key_create_fake(storage=%p) -> key=%u\n", key,
                new_key);
  return 0;
}

static int pthread_key_delete_fake(pthread_key_t key) {
  const unsigned int key_index = (unsigned int)key;
  if (key_index == 0 || key_index >= FAKE_TLS_MAX_KEYS ||
      !__atomic_load_n(&fake_tls_key_active[key_index], __ATOMIC_ACQUIRE))
    return EINVAL;

  __atomic_store_n(&fake_tls_key_active[key_index], 0, __ATOMIC_RELEASE);
  fake_tls_destructors[key_index] = NULL;
  for (int i = 0; i < FAKE_TLS_MAX_THREADS; i++)
    fake_tls_values[i][key_index] = NULL;
  return 0;
}

static void *pthread_getspecific_fake(pthread_key_t key) {
  const unsigned int key_index = (unsigned int)key;
  if (key_index == 0 || key_index >= FAKE_TLS_MAX_KEYS ||
      !__atomic_load_n(&fake_tls_key_active[key_index], __ATOMIC_ACQUIRE))
    return NULL;

  const int slot = fake_tls_thread_slot(0);
  if (slot < 0)
    return NULL;
  void *value = fake_tls_values[slot][key_index];
  if (value && __sync_fetch_and_add(&pthread_tls_get_trace_count, 1) < 64)
    debugPrintf("pthread_getspecific_fake(tls=%p slot=%d key=%u) -> %p\n",
                mc_thread_key(), slot, key_index, value);
  return value;
}

static int pthread_setspecific_fake(pthread_key_t key, const void *value) {
  const unsigned int key_index = (unsigned int)key;
  if (key_index == 0 || key_index >= FAKE_TLS_MAX_KEYS ||
      !__atomic_load_n(&fake_tls_key_active[key_index], __ATOMIC_ACQUIRE))
    return EINVAL;

  const int slot = fake_tls_thread_slot(1);
  if (slot < 0)
    return EAGAIN;
  fake_tls_values[slot][key_index] = (void *)value;
  if (__sync_fetch_and_add(&pthread_tls_set_trace_count, 1) < 128)
    debugPrintf("pthread_setspecific_fake(tls=%p slot=%d key=%u value=%p)\n",
                mc_thread_key(), slot, key_index, value);
  return 0;
}

// Each pthread_create'd thread needs a fake stack-guard TLS block in TPIDR_EL0
// (see hooks/game.c): libnx leaves TPIDR_EL0 zero on new threads, so a guarded
// function would fault reading its cookie at [TPIDR_EL0, #0x28].
typedef struct {
  void *(*func)(void *);
  void *arg;
  uint8_t tls[0x100];
} PthreadStart;

static void *pthread_trampoline(void *p) {
  PthreadStart *s = p;
  void *(*func)(void *) = s->func;
  void *arg = s->arg;
  // Let Horizon schedule UE4's render, RHI, task-graph, audio, and streaming
  // workers across every core granted to the application.
  thread_registry_add();            // track for freeze-on-exit
  memset(s->tls, 0, sizeof(s->tls));
  armSetTlsRw(s->tls);
  // tls stays in TPIDR_EL0 for the thread's lifetime, so PthreadStart is leaked
  return func(arg);
}

int pthread_create_fake(pthread_t *thread, const void *unused, void *entry, void *arg) {
  (void)unused;
  PthreadStart *s = calloc(1, sizeof(*s));
  if (!s)
    return -1;
  s->func = (void *(*)(void *))entry;
  s->arg = arg;
  pthread_attr_t native_attr;
  int rc = pthread_attr_init(&native_attr);
  const int attr_initialized = rc == 0;
  if (rc == 0)
    rc = pthread_attr_setstacksize(&native_attr, 2 * 1024 * 1024);
  if (rc == 0)
    rc = pthread_create(thread, &native_attr, pthread_trampoline, s);
  if (rc != 0)
    free(s);
  if (attr_initialized)
    pthread_attr_destroy(&native_attr);
  debugPrintf("pthread_create_fake: entry=%p arg=%p stack=2MiB -> rc=%d\n",
              entry, arg, rc);
  return rc;
}

static int pthread_setname_np_fake(pthread_t thread, const char *name) {
  (void)thread;
  thread_registry_set_name(name);
  debugPrintf("pthread_setname_np_fake(tls=%p, name=%s)\n", mc_thread_key(),
              name ? name : "(null)");
  return 0;
}

// GL stuff

void glGetShaderInfoLogHook(GLuint shader, GLsizei maxLength, GLsizei *length, GLchar *infoLog) {
  glGetShaderInfoLog(shader, maxLength, length, infoLog);
  debugPrintf("shader info log:\n%s\n", infoLog);
}

void glTexParameteriHook(GLenum target, GLenum param, GLint val) {
  // force trilinear filtering instead of bilinear+nearest mipmap
  if (val == GL_LINEAR_MIPMAP_NEAREST)
    val = GL_LINEAR_MIPMAP_LINEAR;
  glTexParameteri(target, param, val);
}

// CTW extras

// fortify wrappers bionic emits for read()/write()
ssize_t __read_chk(int fd, void *buf, size_t count, size_t buf_size) {
  (void)buf_size;
  return read_dispatch_fake(fd, buf, count);
}

ssize_t __write_chk(int fd, const void *buf, size_t count, size_t buf_size) {
  (void)buf_size;
  return write_dispatch_fake(fd, buf, count);
}

static int getpid_fake(void) {
  return 1;
}

static int sched_yield_fake(void) {
  svcSleepThread(0);
  return 0;
}

static void sincos_fake(double x, double *s, double *c) {
  *s = sin(x);
  *c = cos(x);
}

// the donor's OpenSLES backend is dead here, but its imports must still resolve
static void *SL_IID_fake = NULL;

static unsigned int slCreateEngine_fake(void) {
  return 0x0000000C; // SL_RESULT_FEATURE_UNSUPPORTED
}

// FuzzySeek (port of TheOfficialFloW's GTA_FuzzySeek / fastman92 JPatch): add
// MPG123_FUZZY|SEEKBUFFER|GAPLESS when the game configures its mp3 decoder flags,
// so mpg123 skips loading useless data on seeks -> less SD I/O and snappier radio
// station switching. The game imports mpg123_param, so we just wrap it here (no
// hook needed). Gated on the flags keys so non-flag param calls pass through
// untouched.
static int mpg123_param_fuzzy(mpg123_handle *mh, enum mpg123_parms type,
                              long value, double fvalue) {
  if (config.fuzzy_seek && (type == MPG123_FLAGS || type == MPG123_ADD_FLAGS))
    value |= MPG123_FUZZY | MPG123_SEEKBUFFER | MPG123_GAPLESS;
  return mpg123_param(mh, type, value, fvalue);
}

// import table

DynLibFunction dynlib_functions[] = {
  { "__sF", (uintptr_t)&fake_sF },
  { "__cxa_atexit", (uintptr_t)&__cxa_atexit_fake },
  { "__cxa_finalize", (uintptr_t)&ret0 },
  { "__cxa_thread_atexit_impl", (uintptr_t)&__cxa_thread_atexit_impl_fake },

  { "stderr", (uintptr_t)&stderr_fake },

  // AAssets are emulated over regular files relative to the game dir
  { "AAssetManager_open", (uintptr_t)&AAssetManager_open_fake },
  { "AAssetManager_fromJava", (uintptr_t)&AAssetManager_fromJava_fake },
  { "AAsset_close", (uintptr_t)&AAsset_close_fake },
  { "AAsset_getLength", (uintptr_t)&AAsset_getLength_fake },
  { "AAsset_getLength64", (uintptr_t)&AAsset_getLength64_fake },
  { "AAsset_getRemainingLength", (uintptr_t)&AAsset_getRemainingLength_fake },
  { "AAsset_getRemainingLength64", (uintptr_t)&AAsset_getRemainingLength64_fake },
  { "AAsset_read", (uintptr_t)&AAsset_read_fake },
  { "AAsset_seek", (uintptr_t)&AAsset_seek_fake },
  { "AAsset_seek64", (uintptr_t)&AAsset_seek64_fake },

  // ANativeWindow maps onto the default NWindow
  { "ANativeWindow_fromSurface", (uintptr_t)&ANativeWindow_fromSurface_fake },
  { "ANativeWindow_getWidth", (uintptr_t)&ANativeWindow_getWidth_fake },
  { "ANativeWindow_getHeight", (uintptr_t)&ANativeWindow_getHeight_fake },
  { "ANativeWindow_release", (uintptr_t)&ANativeWindow_release_fake },
  { "ANativeWindow_setBuffersGeometry", (uintptr_t)&ANativeWindow_setBuffersGeometry_fake },

  { "pthread_key_create", (uintptr_t)&pthread_key_create_fake },
  { "pthread_key_delete", (uintptr_t)&pthread_key_delete_fake },
  { "pthread_getspecific", (uintptr_t)&pthread_getspecific_fake },
  { "pthread_setspecific", (uintptr_t)&pthread_setspecific_fake },

  { "pthread_cond_broadcast", (uintptr_t)&pthread_cond_broadcast_fake },
  { "pthread_cond_destroy", (uintptr_t)&pthread_cond_destroy_fake },
  { "pthread_cond_init", (uintptr_t)&pthread_cond_init_fake },
  { "pthread_cond_signal", (uintptr_t)&pthread_cond_signal_fake },
  { "pthread_cond_timedwait", (uintptr_t)&pthread_cond_timedwait_fake },
  { "pthread_cond_wait", (uintptr_t)&pthread_cond_wait_fake },

  { "pthread_create", (uintptr_t)&pthread_create_fake },
  { "pthread_join", (uintptr_t)&pthread_join },
  { "pthread_detach", (uintptr_t)&pthread_detach },
  { "pthread_self", (uintptr_t)&pthread_self },

  { "pthread_setschedparam", (uintptr_t)&ret0 },
  { "pthread_setname_np", (uintptr_t)&pthread_setname_np_fake },

  { "pthread_attr_init", (uintptr_t)&ret0 },
  { "pthread_attr_destroy", (uintptr_t)&ret0 },
  { "pthread_attr_setschedparam", (uintptr_t)&ret0 },
  { "pthread_attr_getschedparam", (uintptr_t)&pthread_attr_getschedparam_fake },
  { "pthread_attr_getstacksize", (uintptr_t)&pthread_attr_getstacksize_fake },

  { "pthread_mutexattr_init", (uintptr_t)&ret0 },
  { "pthread_mutexattr_settype", (uintptr_t)&ret0 },
  { "pthread_mutexattr_destroy", (uintptr_t)&ret0 },
  { "pthread_mutex_destroy", (uintptr_t)&pthread_mutex_destroy_fake },
  { "pthread_mutex_init", (uintptr_t)&pthread_mutex_init_fake },
  { "pthread_mutex_lock", (uintptr_t)&pthread_mutex_lock_fake },
  { "pthread_mutex_trylock", (uintptr_t)&pthread_mutex_trylock_fake },
  { "pthread_mutex_unlock", (uintptr_t)&pthread_mutex_unlock_fake },

  { "pthread_once", (uintptr_t)&pthread_once_fake },

  { "pthread_rwlock_rdlock", (uintptr_t)&pthread_rwlock_rdlock_fake },
  { "pthread_rwlock_wrlock", (uintptr_t)&pthread_rwlock_wrlock_fake },
  { "pthread_rwlock_unlock", (uintptr_t)&pthread_rwlock_unlock_fake },

  { "sem_init", (uintptr_t)&sem_init_fake },
  { "sem_destroy", (uintptr_t)&sem_destroy_fake },
  { "sem_post", (uintptr_t)&sem_post_fake },
  { "sem_wait", (uintptr_t)&sem_wait_fake },
  { "sem_trywait", (uintptr_t)&sem_trywait_fake },
  { "sem_getvalue", (uintptr_t)&sem_getvalue_fake },

  { "sched_get_priority_min", (uintptr_t)&retm1 },
  { "sched_get_priority_max", (uintptr_t)&sched_get_priority_max_fake },

  { "__android_log_print", (uintptr_t)__android_log_print },
  { "__android_log_write", (uintptr_t)__android_log_write },
  { "__android_log_vprint", (uintptr_t)__android_log_vprint },
  { "android_set_abort_message", (uintptr_t)&android_set_abort_message_fake },

  { "__errno", (uintptr_t)&__errno },

  { "__stack_chk_fail", (uintptr_t)&__stack_chk_fail },
  // freezes with real __stack_chk_guard
  { "__stack_chk_guard", (uintptr_t)&__stack_chk_guard_fake },

  { "_ctype_", (uintptr_t)&__ctype_ },
  { "__ctype_get_mb_cur_max", (uintptr_t)&__ctype_get_mb_cur_max_fake },

  { "__register_atfork", (uintptr_t)&__register_atfork_fake },
  { "__system_property_get", (uintptr_t)&__system_property_get_fake },
  { "getauxval", (uintptr_t)&getauxval_fake },
  { "gettid", (uintptr_t)&gettid_fake },
  { "syscall", (uintptr_t)&syscall_fake },
  { "dl_iterate_phdr", (uintptr_t)&so_dl_iterate_phdr },

  // fortify wrappers
  { "__memcpy_chk", (uintptr_t)&__memcpy_chk_fake },
  { "__memmove_chk", (uintptr_t)&__memmove_chk_fake },
  { "__strcat_chk", (uintptr_t)&__strcat_chk_fake },
  { "__strchr_chk", (uintptr_t)&__strchr_chk_fake },
  { "__strcpy_chk", (uintptr_t)&__strcpy_chk_fake },
  { "__strlen_chk", (uintptr_t)&__strlen_chk_fake },
  { "__strncat_chk", (uintptr_t)&__strncat_chk_fake },
  { "__strncpy_chk", (uintptr_t)&__strncpy_chk_fake },
  { "__strncpy_chk2", (uintptr_t)&__strncpy_chk2_fake },
  { "__vsnprintf_chk", (uintptr_t)&__vsnprintf_chk_fake },
  { "__vsprintf_chk", (uintptr_t)&__vsprintf_chk_fake },

  { "acos", (uintptr_t)&acos },
  { "acosf", (uintptr_t)&acosf },
  { "asinf", (uintptr_t)&asinf },
  { "atan2f", (uintptr_t)&atan2f },
  { "atanf", (uintptr_t)&atanf },
  { "cos", (uintptr_t)&cos },
  { "cosf", (uintptr_t)&cosf },
  { "exp", (uintptr_t)&exp },
  { "floor", (uintptr_t)&floor },
  { "floorf", (uintptr_t)&floorf },
  { "fmod", (uintptr_t)&fmod },
  { "fmodf", (uintptr_t)&fmodf },
  { "log", (uintptr_t)&log },
  { "log10f", (uintptr_t)&log10f },
  { "pow", (uintptr_t)&pow },
  { "powf", (uintptr_t)&powf },
  { "sin", (uintptr_t)&sin },
  { "sinf", (uintptr_t)&sinf },
  { "sincosf", (uintptr_t)&sincosf_fake },
  { "tan", (uintptr_t)&tan },
  { "tanf", (uintptr_t)&tanf },
  { "sqrt", (uintptr_t)&sqrt },
  { "sqrtf", (uintptr_t)&sqrtf },

  { "atoi", (uintptr_t)&atoi },
  { "atof", (uintptr_t)&atof },
  { "isspace", (uintptr_t)&isspace },
  { "tolower", (uintptr_t)&tolower },
  { "towlower", (uintptr_t)&towlower },
  { "toupper", (uintptr_t)&toupper },
  { "towupper", (uintptr_t)&towupper },

  { "calloc", (uintptr_t)&calloc },
  { "free", (uintptr_t)&free },
  { "malloc", (uintptr_t)&malloc },
  { "realloc", (uintptr_t)&realloc },
  { "posix_memalign", (uintptr_t)&posix_memalign_fake },

  { "clock_gettime", (uintptr_t)&clock_gettime_android },
  { "gettimeofday", (uintptr_t)&gettimeofday },
  { "time", (uintptr_t)&time },
  { "asctime", (uintptr_t)&asctime },
  { "localtime", (uintptr_t)&localtime },
  { "localtime_r", (uintptr_t)&localtime_r },
  { "strftime", (uintptr_t)&strftime },
  { "strftime_l", (uintptr_t)&strftime_l_fake },
  { "nanosleep", (uintptr_t)&nanosleep },
  { "usleep", (uintptr_t)&usleep },

  // EGL: the game creates and manages its own context now
  { "eglGetProcAddress", (uintptr_t)&eglGetProcAddress_diag },
  { "eglGetDisplay", (uintptr_t)&eglGetDisplay },
  { "eglQueryString", (uintptr_t)&eglQueryString },
  { "eglInitialize", (uintptr_t)&eglInitialize },
  { "eglChooseConfig", (uintptr_t)&eglChooseConfig_compat },
  { "eglGetConfigAttrib", (uintptr_t)&eglGetConfigAttrib },
  { "eglCreateContext", (uintptr_t)&eglCreateContext_compat },
  { "eglCreateWindowSurface", (uintptr_t)&eglCreateWindowSurface_cache },
  { "eglDestroySurface", (uintptr_t)&eglDestroySurface_cache },
  { "eglDestroyContext", (uintptr_t)&eglDestroyContext_cache },
  { "eglMakeCurrent", (uintptr_t)&eglMakeCurrent_dedup },
  // reset the GL cache after the overlay's direct GL, then run the (FPS) swap hook
  { "eglSwapBuffers", (uintptr_t)&eglSwapBuffers_cache },
  { "eglSwapInterval", (uintptr_t)&eglSwapInterval },
  { "eglGetError", (uintptr_t)&eglGetError },
  { "eglTerminate", (uintptr_t)&eglTerminate },
  { "eglBindAPI", (uintptr_t)&eglBindAPI },

  // OpenAL: imported by libGame.so since 2.x; alcOpenDevice/alcCreateContext
  // go through hooks for the 44100hz override
  { "alBufferData", (uintptr_t)&alBufferData },
  { "alDeleteBuffers", (uintptr_t)&alDeleteBuffers },
  { "alDeleteSources", (uintptr_t)&alDeleteSources },
  { "alDistanceModel", (uintptr_t)&alDistanceModel },
  { "alGenBuffers", (uintptr_t)&alGenBuffers },
  { "alGenSources", (uintptr_t)&alGenSources },
  { "alGetEnumValue", (uintptr_t)&alGetEnumValue },
  { "alGetError", (uintptr_t)&alGetError },
  { "alGetSourcef", (uintptr_t)&alGetSourcef },
  { "alGetSourcei", (uintptr_t)&alGetSourcei },
  { "alGetString", (uintptr_t)&alGetString },
  { "alIsExtensionPresent", (uintptr_t)&alIsExtensionPresent },
  { "alListener3f", (uintptr_t)&alListener3f },
  { "alListenerf", (uintptr_t)&alListenerf },
  { "alListenerfv", (uintptr_t)&alListenerfv },
  { "alSource3f", (uintptr_t)&alSource3f },
  { "alSourcePause", (uintptr_t)&alSourcePause },
  { "alSourcePlay", (uintptr_t)&alSourcePlay },
  { "alSourceQueueBuffers", (uintptr_t)&alSourceQueueBuffers },
  { "alSourceStop", (uintptr_t)&alSourceStop },
  { "alSourceUnqueueBuffers", (uintptr_t)&alSourceUnqueueBuffers },
  { "alSourcef", (uintptr_t)&alSourcef },
  { "alSourcei", (uintptr_t)&alSourcei },
  { "alcCloseDevice", (uintptr_t)&alcCloseDevice },
  { "alcCreateContext", (uintptr_t)&alcCreateContextHook },
  { "alcDestroyContext", (uintptr_t)&alcDestroyContext },
  { "alcGetError", (uintptr_t)&alcGetError },
  { "alcGetString", (uintptr_t)&alcGetString },
  { "alcMakeContextCurrent", (uintptr_t)&alcMakeContextCurrent },
  { "alcOpenDevice", (uintptr_t)&alcOpenDeviceHook },

  // mpg123 (music streaming); was libVendor_mpg123.so on Android,
  // provided natively by the switch-mpg123 portlib here
  { "mpg123_delete", (uintptr_t)&mpg123_delete },
  { "mpg123_exit", (uintptr_t)&mpg123_exit },
  { "mpg123_feed", (uintptr_t)&mpg123_feed },
  { "mpg123_feedseek", (uintptr_t)&mpg123_feedseek },
  { "mpg123_format_all", (uintptr_t)&mpg123_format_all },
  { "mpg123_getformat", (uintptr_t)&mpg123_getformat },
  { "mpg123_info", (uintptr_t)&mpg123_info },
  { "mpg123_init", (uintptr_t)&mpg123_init },
  { "mpg123_new", (uintptr_t)&mpg123_new },
  { "mpg123_open_feed", (uintptr_t)&mpg123_open_feed },
  { "mpg123_outblock", (uintptr_t)&mpg123_outblock },
  { "mpg123_read", (uintptr_t)&mpg123_read },

  { "abort", (uintptr_t)&game_abort_fake },
  { "exit", (uintptr_t)&game_exit_fake },

  { "fopen", (uintptr_t)&fopen_fake },
  { "fclose", (uintptr_t)&fclose_fake },
  { "fdopen", (uintptr_t)&fdopen },
  { "fflush", (uintptr_t)&fflush_fake },
  { "fgetc", (uintptr_t)&fgetc },
  { "fgets", (uintptr_t)&fgets },
  { "fputs", (uintptr_t)&fputs_fake },
  { "fputc", (uintptr_t)&fputc_fake },
  { "fprintf", (uintptr_t)&fprintf_fake },
  { "vfprintf", (uintptr_t)&vfprintf_fake },
  { "fread", (uintptr_t)&fread_fake },
  { "fseek", (uintptr_t)&fseek_fake },
  { "fseeko", (uintptr_t)&fseeko },
  { "ftell", (uintptr_t)&ftell },
  { "ftello", (uintptr_t)&ftello },
  { "fwrite", (uintptr_t)&fwrite_fake },
  { "fstat", (uintptr_t)&fstat_fake },
  { "ferror", (uintptr_t)&ferror_fake },
  { "feof", (uintptr_t)&feof },
  { "fileno", (uintptr_t)&fileno_fake },
  { "ftruncate", (uintptr_t)&ftruncate },
  { "setvbuf", (uintptr_t)&setvbuf },
  { "setbuf", (uintptr_t)&setbuf_fake },
  { "getc", (uintptr_t)&getc_fake },
  { "ungetc", (uintptr_t)&ungetc_fake },
  { "getwc", (uintptr_t)&getwc },
  { "ungetwc", (uintptr_t)&ungetwc },
  { "fputwc", (uintptr_t)&fputwc },

  { "getenv", (uintptr_t)&getenv },

  { "glActiveTexture", (uintptr_t)&glActiveTexture_c },
  { "glAttachShader", (uintptr_t)&glAttachShader },
  { "glBindAttribLocation", (uintptr_t)&glBindAttribLocation },
  { "glBindBuffer", (uintptr_t)&glBindBuffer },
  { "glBindFramebuffer", (uintptr_t)&glBindFramebuffer_diag },
  { "glBindRenderbuffer", (uintptr_t)&glBindRenderbuffer },
  { "glBindTexture", (uintptr_t)&glBindTexture_c },
  { "glBlendFunc", (uintptr_t)&glBlendFunc_c },
  { "glBlendFuncSeparate", (uintptr_t)&glBlendFuncSeparate_c },
  { "glBufferData", (uintptr_t)&glBufferData_w },
  { "glCheckFramebufferStatus", (uintptr_t)&glCheckFramebufferStatus_diag },
  { "glClear", (uintptr_t)&glClear_diag },
  { "glClearColor", (uintptr_t)&glClearColor },
  { "glClearDepthf", (uintptr_t)&glClearDepthf },
  { "glClearStencil", (uintptr_t)&glClearStencil },
  { "glColorMask", (uintptr_t)&glColorMask_c },
  { "glCompileShader", (uintptr_t)&glCompileShader_diag },
  { "glCompressedTexImage2D", (uintptr_t)&glCompressedTexImage2D_w },
  { "glCreateProgram", (uintptr_t)&glCreateProgram },
  { "glCreateShader", (uintptr_t)&glCreateShader },
  { "glCullFace", (uintptr_t)&glCullFace_c },
  { "glDeleteBuffers", (uintptr_t)&glDeleteBuffers },
  { "glDeleteFramebuffers", (uintptr_t)&glDeleteFramebuffers },
  { "glDeleteProgram", (uintptr_t)&glDeleteProgram_c },
  { "glDeleteRenderbuffers", (uintptr_t)&glDeleteRenderbuffers },
  { "glDeleteShader", (uintptr_t)&glDeleteShader },
  { "glDeleteTextures", (uintptr_t)&glDeleteTextures_c },
  { "glDepthFunc", (uintptr_t)&glDepthFunc_c },
  { "glDepthMask", (uintptr_t)&glDepthMask_c },
  { "glDepthRangef", (uintptr_t)&glDepthRangef },
  { "glDisable", (uintptr_t)&glDisable_c },
  { "glDisableVertexAttribArray", (uintptr_t)&glDisableVertexAttribArray },
  { "glDrawArrays", (uintptr_t)&glDrawArrays_diag },
  { "glDrawElements", (uintptr_t)&glDrawElements_diag },
  { "glEnable", (uintptr_t)&glEnable_c },
  { "glEnableVertexAttribArray", (uintptr_t)&glEnableVertexAttribArray },
  { "glFinish", (uintptr_t)&glFinish },
  { "glFramebufferRenderbuffer", (uintptr_t)&glFramebufferRenderbuffer },
  { "glFramebufferTexture2D", (uintptr_t)&glFramebufferTexture2D },
  { "glFrontFace", (uintptr_t)&glFrontFace_c },
  { "glGenBuffers", (uintptr_t)&glGenBuffers },
  { "glGenFramebuffers", (uintptr_t)&glGenFramebuffers },
  { "glGenRenderbuffers", (uintptr_t)&glGenRenderbuffers },
  { "glGenTextures", (uintptr_t)&glGenTextures },
  { "glGetAttribLocation", (uintptr_t)&glGetAttribLocation },
  { "glGetError", (uintptr_t)&glGetError },
  { "glGetBooleanv", (uintptr_t)&glGetBooleanv },
  { "glGetIntegerv", (uintptr_t)&glGetIntegerv },
  { "glGetProgramInfoLog", (uintptr_t)&glGetProgramInfoLog },
  { "glGetProgramiv", (uintptr_t)&glGetProgramiv },
  { "glGetShaderInfoLog", (uintptr_t)&glGetShaderInfoLogHook },
  { "glGetShaderiv", (uintptr_t)&glGetShaderiv },
  { "glGetString", (uintptr_t)&glGetString },
  { "glGetUniformLocation", (uintptr_t)&glGetUniformLocation },
  { "glHint", (uintptr_t)&glHint },
  { "glIsEnabled", (uintptr_t)&glIsEnabled },
  { "glIsTexture", (uintptr_t)&glIsTexture },
  { "glLinkProgram", (uintptr_t)&glLinkProgram_diag },
  { "glPolygonOffset", (uintptr_t)&glPolygonOffset },
  { "glReadPixels", (uintptr_t)&glReadPixels },
  { "glRenderbufferStorage", (uintptr_t)&glRenderbufferStorage },
  { "glScissor", (uintptr_t)&glScissor },
  { "glShaderSource", (uintptr_t)&glShaderSource },
  { "glTexImage2D", (uintptr_t)&glTexImage2D_w },
  { "glTexParameterf", (uintptr_t)&glTexParameterf },
  { "glTexParameteri", (uintptr_t)&glTexParameteri },
  { "glUniform1f", (uintptr_t)&glUniform1f },
  { "glUniform1fv", (uintptr_t)&glUniform1fv },
  { "glUniform1i", (uintptr_t)&glUniform1i },
  { "glUniform2fv", (uintptr_t)&glUniform2fv },
  { "glUniform3f", (uintptr_t)&glUniform3f },
  { "glUniform3fv", (uintptr_t)&glUniform3fv },
  { "glUniform4fv", (uintptr_t)&glUniform4fv },
  { "glUniformMatrix3fv", (uintptr_t)&glUniformMatrix3fv },
  { "glUniformMatrix4fv", (uintptr_t)&glUniformMatrix4fv },
  { "glUseProgram", (uintptr_t)&glUseProgram_c },
  { "glVertexAttrib4fv", (uintptr_t)&glVertexAttrib4fv },
  { "glVertexAttribPointer", (uintptr_t)&glVertexAttribPointer },
  { "glViewport", (uintptr_t)&glViewport_diag },

  { "setjmp", (uintptr_t)&setjmp },
  { "longjmp", (uintptr_t)&longjmp },

  { "memcmp", (uintptr_t)&memcmp },
  { "wmemcmp", (uintptr_t)&wmemcmp },
  { "wmemchr", (uintptr_t)&wmemchr },
  { "memcpy", (uintptr_t)&memcpy },
  { "memmove", (uintptr_t)&memmove },
  { "memset", (uintptr_t)&memset },
  { "memchr", (uintptr_t)&memchr },

  { "printf", (uintptr_t)&debugPrintf },

  { "bsearch", (uintptr_t)&bsearch },
  { "qsort", (uintptr_t)&qsort },

  { "snprintf", (uintptr_t)&snprintf },
  { "sprintf", (uintptr_t)&sprintf },
  { "vsnprintf", (uintptr_t)&vsnprintf },
  { "vsprintf", (uintptr_t)&vsprintf },
  { "vasprintf", (uintptr_t)&vasprintf },

  { "sscanf", (uintptr_t)&sscanf },
  { "vsscanf", (uintptr_t)&vsscanf },
  { "swprintf", (uintptr_t)&swprintf },

  { "close", (uintptr_t)&close_dispatch_fake },
  { "lseek", (uintptr_t)&lseek },
  { "mkdir", (uintptr_t)&mkdir },
  { "open", (uintptr_t)&open_fake },
  { "openat", (uintptr_t)&openat_fake },
  { "read", (uintptr_t)&read_dispatch_fake },
  { "write", (uintptr_t)&write_dispatch_fake },
  { "stat", (uintptr_t)&stat_fake },
  { "lstat", (uintptr_t)&lstat_fake },
  { "remove", (uintptr_t)&remove },
  { "rename", (uintptr_t)&rename },
  { "unlink", (uintptr_t)&unlink },
  { "unlinkat", (uintptr_t)&unlinkat_fake },
  { "truncate", (uintptr_t)&retm1 },
  { "link", (uintptr_t)&retm1 },
  { "symlink", (uintptr_t)&retm1 },
  { "readlink", (uintptr_t)&retm1 },
  { "chdir", (uintptr_t)&chdir },
  { "getcwd", (uintptr_t)&getcwd },
  { "realpath", (uintptr_t)&realpath_fake },
  { "isatty", (uintptr_t)&isatty },
  { "ioctl", (uintptr_t)&retm1 },
  { "fchmod", (uintptr_t)&ret0 },
  { "fchmodat", (uintptr_t)&ret0 },
  { "utimensat", (uintptr_t)&ret0 },
  { "sendfile", (uintptr_t)&retm1 },
  { "statvfs", (uintptr_t)&statvfs_fake },
  { "pathconf", (uintptr_t)&pathconf_fake },
  { "sysconf", (uintptr_t)&sysconf_fake },

  { "opendir", (uintptr_t)&opendir_fake },
  { "fdopendir", (uintptr_t)&ret0 },
  { "closedir", (uintptr_t)&closedir },
  { "readdir", (uintptr_t)&readdir_fake },
  { "readdir64", (uintptr_t)&readdir_fake },

  { "openlog", (uintptr_t)&ret0 },
  { "closelog", (uintptr_t)&ret0 },
  { "syslog", (uintptr_t)&ret0 },

  { "strcasecmp", (uintptr_t)&strcasecmp },
  { "strcat", (uintptr_t)&strcat },
  { "strchr", (uintptr_t)&strchr },
  { "strcmp", (uintptr_t)&strcmp },
  { "strcoll", (uintptr_t)&strcoll },
  { "strcoll_l", (uintptr_t)&strcoll_l_fake },
  { "strcpy", (uintptr_t)&strcpy },
  { "stpcpy", (uintptr_t)&stpcpy },
  { "strdup", (uintptr_t)&strdup },
  { "strerror", (uintptr_t)&strerror },
  { "strerror_r", (uintptr_t)&strerror_r_fake },
  { "strlen", (uintptr_t)&strlen },
  { "strncasecmp", (uintptr_t)&strncasecmp },
  { "strncat", (uintptr_t)&strncat },
  { "strncmp", (uintptr_t)&strncmp },
  { "strncpy", (uintptr_t)&strncpy },
  { "strpbrk", (uintptr_t)&strpbrk },
  { "strrchr", (uintptr_t)&strrchr },
  { "strstr", (uintptr_t)&strstr },
  { "strtod", (uintptr_t)&strtod },
  { "strtok", (uintptr_t)&strtok },
  { "strtol", (uintptr_t)&strtol },
  { "strtoul", (uintptr_t)&strtoul },
  { "strtof", (uintptr_t)&strtof },
  { "strtold", (uintptr_t)&strtold },
  { "strtold_l", (uintptr_t)&strtold_l_fake },
  { "strtoll", (uintptr_t)&strtoll },
  { "strtoll_l", (uintptr_t)&strtoll_l_fake },
  { "strtoull", (uintptr_t)&strtoull },
  { "strtoull_l", (uintptr_t)&strtoull_l_fake },
  { "strxfrm", (uintptr_t)&strxfrm },
  { "strxfrm_l", (uintptr_t)&strxfrm_l_fake },

  { "srand", (uintptr_t)&srand },
  { "rand", (uintptr_t)&rand },

  // locale: the _l variants ignore the locale and use the C locale
  { "setlocale", (uintptr_t)&setlocale },
  { "localeconv", (uintptr_t)&localeconv },
  { "newlocale", (uintptr_t)&newlocale_fake },
  { "freelocale", (uintptr_t)&freelocale_fake },
  { "uselocale", (uintptr_t)&uselocale_fake },
  { "iswalpha_l", (uintptr_t)&iswalpha_l_fake },
  { "iswblank_l", (uintptr_t)&iswblank_l_fake },
  { "iswcntrl_l", (uintptr_t)&iswcntrl_l_fake },
  { "iswdigit_l", (uintptr_t)&iswdigit_l_fake },
  { "iswlower_l", (uintptr_t)&iswlower_l_fake },
  { "iswprint_l", (uintptr_t)&iswprint_l_fake },
  { "iswpunct_l", (uintptr_t)&iswpunct_l_fake },
  { "iswspace_l", (uintptr_t)&iswspace_l_fake },
  { "iswupper_l", (uintptr_t)&iswupper_l_fake },
  { "iswxdigit_l", (uintptr_t)&iswxdigit_l_fake },
  { "towlower_l", (uintptr_t)&towlower_l_fake },
  { "towupper_l", (uintptr_t)&towupper_l_fake },
  { "wcscoll_l", (uintptr_t)&wcscoll_l_fake },
  { "wcsxfrm_l", (uintptr_t)&wcsxfrm_l_fake },

  { "wctob", (uintptr_t)&wctob },
  { "wctype", (uintptr_t)&wctype },
  { "wcsxfrm", (uintptr_t)&wcsxfrm },
  { "iswctype", (uintptr_t)&iswctype },
  { "wcscoll", (uintptr_t)&wcscoll },
  { "wcsftime", (uintptr_t)&wcsftime },
  { "mbrtowc", (uintptr_t)&mbrtowc },
  { "mbrlen", (uintptr_t)&mbrlen },
  { "mbtowc", (uintptr_t)&mbtowc },
  { "mbsrtowcs", (uintptr_t)&mbsrtowcs },
  { "mbsnrtowcs", (uintptr_t)&mbsnrtowcs_fake },
  { "wcsnrtombs", (uintptr_t)&wcsnrtombs_fake },
  { "wcrtomb", (uintptr_t)&wcrtomb },
  { "wcslen", (uintptr_t)&wcslen },
  { "btowc", (uintptr_t)&btowc },
  { "wcstod", (uintptr_t)&wcstod },
  { "wcstof", (uintptr_t)&wcstof },
  { "wcstol", (uintptr_t)&wcstol },
  { "wcstold", (uintptr_t)&wcstold },
  { "wcstoll", (uintptr_t)&wcstoll },
  { "wcstoul", (uintptr_t)&wcstoul },
  { "wcstoull", (uintptr_t)&wcstoull },

  // --- CTW 4.4.243 additions ---

  // libGame.so extras over the Max Payne 2.1.131 import set
  { "__read_chk", (uintptr_t)&__read_chk },
  { "__write_chk", (uintptr_t)&__write_chk },
  { "atan", (uintptr_t)&atan },
  { "expf", (uintptr_t)&expf },
  { "frexp", (uintptr_t)&frexp },
  { "logf", (uintptr_t)&logf },
  { "modf", (uintptr_t)&modf },
  { "gmtime", (uintptr_t)&gmtime },
  { "getpid", (uintptr_t)&getpid_fake },
  { "putchar", (uintptr_t)&putchar },
  { "puts", (uintptr_t)&puts },
  { "glBlendEquation", (uintptr_t)&glBlendEquation },
  { "glLineWidth", (uintptr_t)&glLineWidth },
  { "glUniform4f", (uintptr_t)&glUniform4f },
  { "glVertexAttrib2f", (uintptr_t)&glVertexAttrib2f },
  { "glVertexAttrib3f", (uintptr_t)&glVertexAttrib3f },
  { "glVertexAttrib4f", (uintptr_t)&glVertexAttrib4f },
  { "alBufferi", (uintptr_t)&alBufferi },
  { "alcGetProcAddress", (uintptr_t)&alcGetProcAddress },
  { "alcProcessContext", (uintptr_t)&alcProcessContext },
  { "alcSuspendContext", (uintptr_t)&alcSuspendContext },
  { "mpg123_param", (uintptr_t)&mpg123_param_fuzzy }, // FuzzySeek (see wrapper)

  // imports of the C++ runtime donor (the APK's libopenal.so)
  { "__assert2", (uintptr_t)&__assert2 },
  { "__readlink_chk", (uintptr_t)&retm1 },
  { "atan2", (uintptr_t)&atan2 },
  { "cbrtf", (uintptr_t)&cbrtf },
  { "exp2f", (uintptr_t)&exp2f },
  { "hypot", (uintptr_t)&hypot },
  { "ldexpf", (uintptr_t)&ldexpf },
  { "log2f", (uintptr_t)&log2f },
  { "sinhf", (uintptr_t)&sinhf },
  { "sincos", (uintptr_t)&sincos_fake },
  { "clearerr", (uintptr_t)&clearerr },
  { "rewind", (uintptr_t)&rewind },
  { "raise", (uintptr_t)&raise },
  { "sched_yield", (uintptr_t)&sched_yield_fake },
  { "slCreateEngine", (uintptr_t)&slCreateEngine_fake },
  { "SL_IID_ANDROIDCONFIGURATION", (uintptr_t)&SL_IID_fake },
  { "SL_IID_ANDROIDSIMPLEBUFFERQUEUE", (uintptr_t)&SL_IID_fake },
  { "SL_IID_ENGINE", (uintptr_t)&SL_IID_fake },
  { "SL_IID_PLAY", (uintptr_t)&SL_IID_fake },
  { "SL_IID_RECORD", (uintptr_t)&SL_IID_fake },
  // thread_local init wrapper; safe to no-op (TLS pointer is zero-initialized)
  { "_ZTHN10ALCcontext13sLocalContextE", (uintptr_t)&ret0 },

  // ======================================================================
  // LCS 2.4.379 additions over the CTW import set
  // (the older GTAJNIlib engine + its renderer/netcode pull in more symbols)
  // ======================================================================

  // -- GLESv2 functions the LCS renderer uses (native, -lGLESv2) --
  { "glBlendColor", (uintptr_t)&glBlendColor },
  { "glBlendEquationSeparate", (uintptr_t)&glBlendEquationSeparate },
  { "glBufferSubData", (uintptr_t)&glBufferSubData },
  { "glCompressedTexSubImage2D", (uintptr_t)&glCompressedTexSubImage2D },
  { "glCopyTexImage2D", (uintptr_t)&glCopyTexImage2D },
  { "glCopyTexSubImage2D", (uintptr_t)&glCopyTexSubImage2D },
  { "glDetachShader", (uintptr_t)&glDetachShader },
  { "glFlush", (uintptr_t)&glFlush },
  { "glGenerateMipmap", (uintptr_t)&glGenerateMipmap },
  { "glGetActiveAttrib", (uintptr_t)&glGetActiveAttrib },
  { "glGetActiveUniform", (uintptr_t)&glGetActiveUniform },
  { "glGetAttachedShaders", (uintptr_t)&glGetAttachedShaders },
  { "glGetBufferParameteriv", (uintptr_t)&glGetBufferParameteriv },
  { "glGetFloatv", (uintptr_t)&glGetFloatv },
  { "glGetFramebufferAttachmentParameteriv", (uintptr_t)&glGetFramebufferAttachmentParameteriv },
  { "glGetRenderbufferParameteriv", (uintptr_t)&glGetRenderbufferParameteriv },
  { "glGetShaderPrecisionFormat", (uintptr_t)&glGetShaderPrecisionFormat },
  { "glGetShaderSource", (uintptr_t)&glGetShaderSource },
  { "glGetTexParameterfv", (uintptr_t)&glGetTexParameterfv },
  { "glGetTexParameteriv", (uintptr_t)&glGetTexParameteriv },
  { "glGetUniformfv", (uintptr_t)&glGetUniformfv },
  { "glGetUniformiv", (uintptr_t)&glGetUniformiv },
  { "glGetVertexAttribfv", (uintptr_t)&glGetVertexAttribfv },
  { "glGetVertexAttribiv", (uintptr_t)&glGetVertexAttribiv },
  { "glGetVertexAttribPointerv", (uintptr_t)&glGetVertexAttribPointerv },
  { "glIsBuffer", (uintptr_t)&glIsBuffer },
  { "glIsFramebuffer", (uintptr_t)&glIsFramebuffer },
  { "glIsRenderbuffer", (uintptr_t)&glIsRenderbuffer },
  { "glIsShader", (uintptr_t)&glIsShader },
  { "glPixelStorei", (uintptr_t)&glPixelStorei },
  { "glReleaseShaderCompiler", (uintptr_t)&glReleaseShaderCompiler },
  { "glSampleCoverage", (uintptr_t)&glSampleCoverage },
  { "glShaderBinary", (uintptr_t)&glShaderBinary },
  { "glStencilFunc", (uintptr_t)&glStencilFunc },
  { "glStencilFuncSeparate", (uintptr_t)&glStencilFuncSeparate },
  { "glStencilMask", (uintptr_t)&glStencilMask },
  { "glStencilMaskSeparate", (uintptr_t)&glStencilMaskSeparate },
  { "glStencilOp", (uintptr_t)&glStencilOp },
  { "glStencilOpSeparate", (uintptr_t)&glStencilOpSeparate },
  { "glTexParameterfv", (uintptr_t)&glTexParameterfv },
  { "glTexParameteriv", (uintptr_t)&glTexParameteriv },
  { "glTexSubImage2D", (uintptr_t)&glTexSubImage2D },
  { "glUniform1iv", (uintptr_t)&glUniform1iv },
  { "glUniform2f", (uintptr_t)&glUniform2f },
  { "glUniform2i", (uintptr_t)&glUniform2i },
  { "glUniform2iv", (uintptr_t)&glUniform2iv },
  { "glUniform3i", (uintptr_t)&glUniform3i },
  { "glUniform3iv", (uintptr_t)&glUniform3iv },
  { "glUniform4i", (uintptr_t)&glUniform4i },
  { "glUniform4iv", (uintptr_t)&glUniform4iv },
  { "glUniformMatrix2fv", (uintptr_t)&glUniformMatrix2fv },
  { "glValidateProgram", (uintptr_t)&glValidateProgram },
  { "glVertexAttrib1f", (uintptr_t)&glVertexAttrib1f },
  { "glVertexAttrib1fv", (uintptr_t)&glVertexAttrib1fv },
  { "glVertexAttrib2fv", (uintptr_t)&glVertexAttrib2fv },
  { "glVertexAttrib3fv", (uintptr_t)&glVertexAttrib3fv },

  // -- BSD sockets / net (Social Club + cloud). native via libnx -lnx;
  //    socketInitializeDefault() is called once at boot in main.c --
  { "socket", (uintptr_t)&socket },
  { "bind", (uintptr_t)&bind },
  { "connect", (uintptr_t)&connect },
  { "accept", (uintptr_t)&accept },
  { "listen", (uintptr_t)&listen },
  { "recvfrom", (uintptr_t)&recvfrom },
  { "sendto", (uintptr_t)&sendto },
  { "setsockopt", (uintptr_t)&setsockopt_fake },
  { "shutdown", (uintptr_t)&shutdown },
  { "getaddrinfo", (uintptr_t)&getaddrinfo },
  { "inet_pton", (uintptr_t)&inet_pton },
  { "inet_ntop", (uintptr_t)&inet_ntop },
  { "select", (uintptr_t)&select },
  { "fcntl", (uintptr_t)&fcntl_dispatch_fake },

  // -- named POSIX semaphores (mapped to the same FakeSem as the unnamed ones) --
  { "sem_open", (uintptr_t)&sem_open_fake },
  { "sem_close", (uintptr_t)&sem_close_fake },
  { "sem_unlink", (uintptr_t)&sem_unlink_fake },

  // -- extra bionic _FORTIFY_SOURCE wrappers --
  { "__memset_chk", (uintptr_t)&__memset_chk_fake },
  { "__strrchr_chk", (uintptr_t)&__strrchr_chk_fake },
  { "__fread_chk", (uintptr_t)&__fread_chk_fake },
  { "__FD_SET_chk", (uintptr_t)&__FD_SET_chk_fake },
  { "__FD_ISSET_chk", (uintptr_t)&__FD_ISSET_chk_fake },

  // -- misc --
  { "__android_log_assert", (uintptr_t)&__android_log_assert },
  { "stdout", (uintptr_t)&fake_stdout },
  { "mktime", (uintptr_t)&mktime },
  { "pthread_attr_setdetachstate", (uintptr_t)&ret0 },
  { "pthread_attr_setstacksize", (uintptr_t)&ret0 },

  // -- C++ runtime donor imports not provided by libGame.so --
  { "wmemcpy", (uintptr_t)&wmemcpy },
  { "wmemset", (uintptr_t)&wmemset },
  { "wmemmove", (uintptr_t)&wmemmove },
  { "pthread_equal", (uintptr_t)&pthread_equal },
  { "isdigit_l", (uintptr_t)&isdigit_l_fake },
  { "isxdigit_l", (uintptr_t)&isxdigit_l_fake },
  { "islower_l", (uintptr_t)&islower_l_fake },
  { "isupper_l", (uintptr_t)&isupper_l_fake },
  { "toupper_l", (uintptr_t)&toupper_l_fake },
  { "tolower_l", (uintptr_t)&tolower_l_fake },

  // ======================================================================
  // GTA: San Andreas 2.11.311 additions over the CTW/LCS import set.
  // Everything else SA imports is either above or resolves from the C++ runtime
  // donor (libc++_shared.so), so only these four are new here.
  // ======================================================================
  { "ctime", (uintptr_t)&ctime },
  { "modff", (uintptr_t)&modff },
  { "mpg123_length", (uintptr_t)&mpg123_length },
  { "mpg123_set_filesize", (uintptr_t)&mpg123_set_filesize },

  // ======================================================================
  // PES 2021 / UE4 4.22 Android platform imports.
  // ======================================================================

  // NativeActivity, input, looper, configuration and asset-manager APIs.
  { "AAsset_getBuffer", (uintptr_t)&AAsset_getBuffer_fake },
  { "AAsset_openFileDescriptor", (uintptr_t)&AAsset_openFileDescriptor_fake },
  { "AAsset_openFileDescriptor64", (uintptr_t)&AAsset_openFileDescriptor64_fake },
  { "AAssetManager_openDir", (uintptr_t)&AAssetManager_openDir_fake },
  { "AAssetDir_getNextFileName", (uintptr_t)&AAssetDir_getNextFileName_fake },
  { "AAssetDir_close", (uintptr_t)&AAssetDir_close_fake },
  { "AConfiguration_new", (uintptr_t)&AConfiguration_new_fake },
  { "AConfiguration_delete", (uintptr_t)&AConfiguration_delete_fake },
  { "AConfiguration_fromAssetManager", (uintptr_t)&AConfiguration_fromAssetManager_fake },
  { "AConfiguration_getLanguage", (uintptr_t)&AConfiguration_getLanguage_fake },
  { "AConfiguration_getCountry", (uintptr_t)&AConfiguration_getCountry_fake },
  { "ALooper_prepare", (uintptr_t)&ALooper_prepare_fake },
  { "ALooper_addFd", (uintptr_t)&ALooper_addFd_fake },
  { "ALooper_pollAll", (uintptr_t)&ALooper_pollAll_fake },
  { "AInputQueue_attachLooper", (uintptr_t)&AInputQueue_attachLooper_fake },
  { "AInputQueue_detachLooper", (uintptr_t)&AInputQueue_detachLooper_fake },
  { "AInputQueue_getEvent", (uintptr_t)&AInputQueue_getEvent_fake },
  { "AInputQueue_preDispatchEvent", (uintptr_t)&AInputQueue_preDispatchEvent_fake },
  { "AInputQueue_finishEvent", (uintptr_t)&AInputQueue_finishEvent_fake },
  { "AInputEvent_getType", (uintptr_t)&AInputEvent_getType_fake },
  { "AInputEvent_getDeviceId", (uintptr_t)&AInputEvent_getDeviceId_fake },
  { "AInputEvent_getSource", (uintptr_t)&AInputEvent_getSource_fake },
  { "AKeyEvent_getAction", (uintptr_t)&AKeyEvent_getAction_fake },
  { "AKeyEvent_getFlags", (uintptr_t)&AKeyEvent_getFlags_fake },
  { "AKeyEvent_getKeyCode", (uintptr_t)&AKeyEvent_getKeyCode_fake },
  { "AKeyEvent_getMetaState", (uintptr_t)&AKeyEvent_getMetaState_fake },
  { "AMotionEvent_getAction", (uintptr_t)&AMotionEvent_getAction_fake },
  { "AMotionEvent_getButtonState", (uintptr_t)&AMotionEvent_getButtonState_fake },
  { "AMotionEvent_getPointerCount", (uintptr_t)&AMotionEvent_getPointerCount_fake },
  { "AMotionEvent_getPointerId", (uintptr_t)&AMotionEvent_getPointerId_fake },
  { "AMotionEvent_getX", (uintptr_t)&AMotionEvent_getX_fake },
  { "AMotionEvent_getY", (uintptr_t)&AMotionEvent_getY_fake },
  { "ANativeActivity_setWindowFormat", (uintptr_t)&ANativeActivity_setWindowFormat_fake },
  { "ANativeWindow_acquire", (uintptr_t)&ANativeWindow_acquire_fake },

  // bionic memory, descriptor and dynamic-loader compatibility.
  { "mmap", (uintptr_t)&mmap_fake },
  { "munmap", (uintptr_t)&munmap_fake },
  { "mprotect", (uintptr_t)&mprotect_fake },
  { "madvise", (uintptr_t)&madvise_fake },
  { "mlock", (uintptr_t)&mlock_fake },
  { "pipe", (uintptr_t)&pipe_fake },
  { "poll", (uintptr_t)&poll_dispatch_fake },
  { "clock_nanosleep", (uintptr_t)&clock_nanosleep_fake },
  { "fdatasync", (uintptr_t)&fdatasync_fake },
  { "lseek64", (uintptr_t)&lseek64_fake },
  { "pread64", (uintptr_t)&pread64_fake },
  { "pwrite64", (uintptr_t)&pwrite64_fake },
  { "dlopen", (uintptr_t)&dlopen_fake },
  { "dlsym", (uintptr_t)&dlsym_fake },
  { "dlclose", (uintptr_t)&dlclose_fake },
  { "dlerror", (uintptr_t)&dlerror_fake },
  { "dladdr", (uintptr_t)&dladdr_fake },
  { "epoll_create", (uintptr_t)&epoll_create_fake },
  { "epoll_ctl", (uintptr_t)&epoll_ctl_fake },
  { "epoll_wait", (uintptr_t)&epoll_wait_fake },
  { "statfs", (uintptr_t)&statfs_fake },
  { "sysinfo", (uintptr_t)&sysinfo_fake },

  // UE4 uses the full zlib streaming API for pak and network payloads.
  { "compress2", (uintptr_t)&compress2 },
  { "compressBound", (uintptr_t)&compressBound },
  { "crc32", (uintptr_t)&crc32 },
  { "deflate", (uintptr_t)&deflate },
  { "deflateEnd", (uintptr_t)&deflateEnd },
  { "deflateInit2_", (uintptr_t)&deflateInit2_ },
  { "deflateReset", (uintptr_t)&deflateReset },
  { "inflate", (uintptr_t)&inflate },
  { "inflateEnd", (uintptr_t)&inflateEnd },
  { "inflateInit_", (uintptr_t)&inflateInit_ },
  { "inflateInit2_", (uintptr_t)&inflateInit2_ },
  { "inflateReset", (uintptr_t)&inflateReset },
  { "uncompress", (uintptr_t)&uncompress },

  // EGL entry points present in UE4 but absent from the original GTA table.
  { "eglCreatePbufferSurface", (uintptr_t)&eglCreatePbufferSurface_compat },
  { "eglGetCurrentContext", (uintptr_t)&eglGetCurrentContext },
  { "eglQuerySurface", (uintptr_t)&eglQuerySurface_compat },
  { "eglSurfaceAttrib", (uintptr_t)&eglSurfaceAttrib },

  // Remaining libc, networking and threading imports used by UE4 and AVS.
  { "__isfinitef", (uintptr_t)&isfinitef_fake },
  { "abs", (uintptr_t)&abs },
  { "access", (uintptr_t)&access_fake },
  { "atol", (uintptr_t)&atol },
  { "chmod", (uintptr_t)&chmod },
  { "clock", (uintptr_t)&clock },
  { "div", (uintptr_t)&div },
  { "freeaddrinfo", (uintptr_t)&freeaddrinfo },
  { "fscanf", (uintptr_t)&fscanf },
  { "fsync", (uintptr_t)&fsync },
  { "gai_strerror", (uintptr_t)&gai_strerror },
  { "getegid", (uintptr_t)&getgid_fake },
  { "geteuid", (uintptr_t)&geteuid },
  { "getgid", (uintptr_t)&getgid_fake },
  { "gethostbyaddr", (uintptr_t)&gethostbyaddr },
  { "gethostbyname", (uintptr_t)&gethostbyname },
  { "gethostname", (uintptr_t)&gethostname },
  { "getnameinfo", (uintptr_t)&getnameinfo },
  { "getpeername", (uintptr_t)&getpeername },
  { "getpriority", (uintptr_t)&getpriority_fake },
  { "getrlimit", (uintptr_t)&getrlimit_fake },
  { "getsockname", (uintptr_t)&getsockname },
  { "getsockopt", (uintptr_t)&getsockopt },
  { "getuid", (uintptr_t)&getuid_fake },
  { "gmtime_r", (uintptr_t)&gmtime_r },
  { "if_indextoname", (uintptr_t)&if_indextoname_fake },
  { "inet_addr", (uintptr_t)&inet_addr },
  { "isalnum", (uintptr_t)&isalnum },
  { "isalpha", (uintptr_t)&isalpha },
  { "iscntrl", (uintptr_t)&iscntrl },
  { "isdigit", (uintptr_t)&isdigit },
  { "islower", (uintptr_t)&islower },
  { "isnanf", (uintptr_t)&isnanf },
  { "isprint", (uintptr_t)&isprint },
  { "isupper", (uintptr_t)&isupper },
  { "iswalnum", (uintptr_t)&iswalnum },
  { "iswalpha", (uintptr_t)&iswalpha },
  { "iswblank", (uintptr_t)&iswblank },
  { "iswcntrl", (uintptr_t)&iswcntrl },
  { "iswdigit", (uintptr_t)&iswdigit },
  { "iswlower", (uintptr_t)&iswlower },
  { "iswprint", (uintptr_t)&iswprint },
  { "iswpunct", (uintptr_t)&iswpunct },
  { "iswupper", (uintptr_t)&iswupper },
  { "iswxdigit", (uintptr_t)&iswxdigit },
  { "isxdigit", (uintptr_t)&isxdigit },
  { "pause", (uintptr_t)&pause_fake },
  { "pthread_attr_setschedpolicy", (uintptr_t)&ret0 },
  { "pthread_exit", (uintptr_t)&pthread_exit },
  { "pthread_getschedparam", (uintptr_t)&pthread_getschedparam_fake },
  { "pthread_rwlock_init", (uintptr_t)&pthread_rwlock_init_fake },
  { "pthread_rwlock_destroy", (uintptr_t)&pthread_rwlock_destroy_fake },
  { "pthread_rwlock_tryrdlock", (uintptr_t)&pthread_rwlock_tryrdlock_fake },
  { "pthread_rwlock_trywrlock", (uintptr_t)&pthread_rwlock_trywrlock_fake },
  { "pthread_rwlockattr_init", (uintptr_t)&ret0 },
  { "pthread_rwlockattr_destroy", (uintptr_t)&ret0 },
  { "readv", (uintptr_t)&readv_fake },
  { "recv", (uintptr_t)&recv },
  { "recvmsg", (uintptr_t)&recvmsg },
  { "rmdir", (uintptr_t)&rmdir },
  { "send", (uintptr_t)&send },
  { "sendmsg", (uintptr_t)&sendmsg },
  { "setpriority", (uintptr_t)&setpriority_fake },
  { "setrlimit", (uintptr_t)&setrlimit_fake },
  { "sigaction", (uintptr_t)&sigaction_fake },
  { "sigemptyset", (uintptr_t)&sigemptyset_fake },
  { "sleep", (uintptr_t)&sleep },
  { "strcasestr", (uintptr_t)&strcasestr },
  { "strcspn", (uintptr_t)&strcspn },
  { "strnlen", (uintptr_t)&strnlen },
  { "strspn", (uintptr_t)&strspn },
  { "strtok_r", (uintptr_t)&strtok_r },
  { "timezone", (uintptr_t)&timezone_fake },
  { "tzname", (uintptr_t)&tzname_fake },
  { "tzset", (uintptr_t)&tzset },
  { "wcschr", (uintptr_t)&wcschr },
  { "writev", (uintptr_t)&writev_fake },

  { "SL_IID_BUFFERQUEUE", (uintptr_t)&SL_IID_fake },
  { "SL_IID_VOLUME", (uintptr_t)&SL_IID_fake },
};

size_t dynlib_numfunctions = sizeof(dynlib_functions) / sizeof(*dynlib_functions);

void update_imports(void) {
  // only install the hook when the config option is enabled
  if (config.trilinear_filter)
    so_find_import(dynlib_functions, dynlib_numfunctions, "glTexParameteri")->func = (uintptr_t)glTexParameteriHook;
}
