/* util.h -- misc utility functions
 *
 * Copyright (C) 2021 fgsfds, Andy Nguyen
 *
 * This software may be modified and distributed under the terms
 * of the MIT license.  See the LICENSE file for details.
 */

#ifndef __UTIL_H__
#define __UTIL_H__

#include <stdint.h>

// the game's `printf` import target; compiles to a no-op with DEBUG_LOG off
int debugPrintf(char *text, ...);

void cpu_boost(int on);

// pin the calling thread to a single CPU core (no-op if that core isn't in this
// process's allowed mask)
void set_thread_core(int core);

// Thread registry for a clean shutdown. Each engine worker thread records its own
// kernel handle from its trampoline via thread_registry_add(); on exit the main
// thread calls thread_registry_pause_others() to freeze them all so none is
// executing engine/audio code while the process tears down (the mobile engine
// never stops its own threads, so any exit otherwise faults a live worker).
void thread_registry_add(void);
void thread_registry_set_name(const char *name);
void thread_registry_start_dump_watchdog(void);
void thread_registry_pause_others(void);

int ret0(void);
int retm1(void);

static inline void armSetTlsRw(void *addr) {
  __asm__  ("msr s3_3_c13_c0_2, %0" : : "r"(addr));
}

static inline uint64_t umin(uint64_t a, uint64_t b) {
  return (a < b) ? a : b;
}

#endif
