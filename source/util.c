/* util.c -- misc utility functions
 *
 * Copyright (C) 2021 fgsfds, Andy Nguyen
 *
 * This software may be modified and distributed under the terms
 * of the MIT license.  See the LICENSE file for details.
 */

#include <switch.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include <unistd.h>

#include "util.h"
#include "config.h"
#include "so_util.h"

#ifdef DEBUG_LOG

static int s_nxlinkSock = -1;

static void initNxLink(void) {
  if (R_FAILED(socketInitializeDefault()))
    return;
  s_nxlinkSock = nxlinkStdio();
  if (s_nxlinkSock < 0)
    socketExit();
}

static void deinitNxLink(void) {
  if (s_nxlinkSock >= 0) {
    close(s_nxlinkSock);
    socketExit();
    s_nxlinkSock = -1;
  }
}

void userAppInit(void) {
  initNxLink();
}

void userAppExit(void) {
  deinitNxLink();
}

#endif

// the game's `printf` import points here; a no-op with DEBUG_LOG off. The log
// file is kept open for the run (reopening per line on FAT is slow) and flushed
// each line to survive an abrupt exit.
int debugPrintf(char *text, ...) {
#ifdef DEBUG_LOG
  va_list list;
  static FILE *f = NULL;
  if (!f)
    f = fopen(LOG_NAME, "w"); // fresh log each boot
  if (f) {
    va_start(list, text);
    vfprintf(f, text, list);
    va_end(list);
    fflush(f);
  }
  va_start(list, text);
  vprintf(text, list); // also to nxlink stdout, if a host is connected
  va_end(list);
#endif
  return 0;
}

// boost the CPU to 1785MHz while loading
void cpu_boost(int on) {
  appletSetCpuBoostMode(on ? ApmCpuBoostMode_FastLoad : ApmCpuBoostMode_Normal);
}

// pin the calling thread to a single core. Only pins to cores actually granted
// to this process (cores 0..2 for an application; core 3 is the system core),
// so an out-of-range request just leaves the thread on its default core.
void set_thread_core(int core) {
  static u64 mask = 0;
  if (mask == 0)
    svcGetInfo(&mask, InfoType_CoreMask, CUR_PROCESS_HANDLE, 0);
  if (core < 0 || !(mask & (1ull << core)))
    return;
  Result rc = svcSetThreadCoreMask(CUR_THREAD_HANDLE, core, 1ull << core);
  if (R_FAILED(rc))
    debugPrintf("affinity: pin to core %d failed: %08x\n", core, rc);
}

// --- thread registry (see util.h) -----------------------------------------
#define MAX_TRACKED_THREADS 64
static Handle g_thread_handles[MAX_TRACKED_THREADS];
static char g_thread_names[MAX_TRACKED_THREADS][32];
static int g_thread_count; // grow-only; index reserved with an atomic add
static Thread g_dump_watchdog_thread;
static volatile int g_dump_watchdog_started;

extern so_module ue4_mod;

void thread_registry_add(void) {
  int i = __atomic_fetch_add(&g_thread_count, 1, __ATOMIC_RELAXED);
  if (i < MAX_TRACKED_THREADS)
    g_thread_handles[i] = threadGetCurHandle();
}

void thread_registry_set_name(const char *name) {
  const Handle self = threadGetCurHandle();
  int n = g_thread_count;
  if (n > MAX_TRACKED_THREADS)
    n = MAX_TRACKED_THREADS;
  for (int i = 0; i < n; i++) {
    if (g_thread_handles[i] == self) {
      strlcpy(g_thread_names[i], name ? name : "(unnamed)",
              sizeof(g_thread_names[i]));
      return;
    }
  }
}

static void thread_registry_dump_watchdog(void *arg) {
  (void)arg;
  // Startup reaches its first swap after roughly a minute in the emulator.
  // Capture the engine after that point, when the current black-screen stall
  // is active rather than while worker threads are still being created.
  svcSleepThread(75000000000LL);
  const uintptr_t ue4_base = (uintptr_t)ue4_mod.load_virtbase;
  const uintptr_t ue4_end = ue4_base + ue4_mod.load_size;
  int n = g_thread_count;
  if (n > MAX_TRACKED_THREADS)
    n = MAX_TRACKED_THREADS;
  debugPrintf("thread dump: begin tracked=%d ue4=%p..%p\n", n,
              (void *)ue4_base, (void *)ue4_end);

  for (int i = 0; i < n; i++) {
    const Handle handle = g_thread_handles[i];
    if (!handle)
      continue;
    Result rc = svcSetThreadActivity(handle, ThreadActivity_Paused);
    if (R_FAILED(rc)) {
      debugPrintf("thread dump[%d] %s: pause failed %08x\n", i,
                  g_thread_names[i][0] ? g_thread_names[i] : "(unnamed)", rc);
      continue;
    }

    ThreadContext context;
    memset(&context, 0, sizeof(context));
    rc = svcGetThreadContext3(&context, handle);
    if (R_SUCCEEDED(rc)) {
      const uintptr_t pc = (uintptr_t)context.pc.x;
      const uintptr_t lr = (uintptr_t)context.lr;
      debugPrintf("thread dump[%d] %s: PC=%p", i,
                  g_thread_names[i][0] ? g_thread_names[i] : "(unnamed)",
                  (void *)pc);
      if (pc >= ue4_base && pc < ue4_end)
        debugPrintf(" UE4+0x%lx", pc - ue4_base);
      debugPrintf(" LR=%p", (void *)lr);
      if (lr >= ue4_base && lr < ue4_end)
        debugPrintf(" UE4+0x%lx", lr - ue4_base);
      debugPrintf(" SP=%p FP=%p\n", (void *)context.sp, (void *)context.fp);

      uintptr_t frame = (uintptr_t)context.fp;
      const uintptr_t stack_start = (uintptr_t)context.sp;
      for (int depth = 0; depth < 8; depth++) {
        if ((frame & 0xf) || frame < stack_start ||
            frame - stack_start > 0x200000)
          break;
        const uintptr_t previous = *(const uintptr_t *)frame;
        const uintptr_t return_address = *(const uintptr_t *)(frame + 8);
        debugPrintf("thread dump[%d] frame[%d]=%p", i, depth,
                    (void *)return_address);
        if (return_address >= ue4_base && return_address < ue4_end)
          debugPrintf(" UE4+0x%lx", return_address - ue4_base);
        debugPrintf("\n");
        if (previous <= frame || previous - frame > 0x100000)
          break;
        frame = previous;
      }
    } else {
      debugPrintf("thread dump[%d] %s: context failed %08x\n", i,
                  g_thread_names[i][0] ? g_thread_names[i] : "(unnamed)", rc);
    }
    svcSetThreadActivity(handle, ThreadActivity_Runnable);
  }
  debugPrintf("thread dump: end\n");
}

void thread_registry_start_dump_watchdog(void) {
  if (__sync_lock_test_and_set(&g_dump_watchdog_started, 1))
    return;
  Result rc = threadCreate(&g_dump_watchdog_thread,
                           thread_registry_dump_watchdog, NULL, NULL, 0x8000,
                           0x2d, 2);
  if (R_SUCCEEDED(rc))
    rc = threadStart(&g_dump_watchdog_thread);
  if (R_FAILED(rc))
    debugPrintf("thread dump: watchdog start failed %08x\n", rc);
}

void thread_registry_pause_others(void) {
  Handle self = threadGetCurHandle();
  int n = g_thread_count;
  if (n > MAX_TRACKED_THREADS)
    n = MAX_TRACKED_THREADS;
  int paused = 0;
  for (int i = 0; i < n; i++) {
    Handle h = g_thread_handles[i];
    if (h && h != self && R_SUCCEEDED(svcSetThreadActivity(h, ThreadActivity_Paused)))
      paused++;
  }
  debugPrintf("EXIT: paused %d/%d engine threads\n", paused, n);
}

int ret0(void) { return 0; }

int retm1(void) { return -1; }
