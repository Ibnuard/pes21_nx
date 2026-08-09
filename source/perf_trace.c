#include "perf_trace.h"

#ifdef PERF_TRACE

#include <limits.h>
#include <stdio.h>
#include <string.h>

#include <switch.h>

#include "so_util.h"

extern so_module avs_mod;
extern so_module afp_mod;
extern so_module ue4_mod;

#define PERF_TRACE_SLOTS 128
#define PERF_TRACE_TOP 24
#define PERF_TRACE_EMPTY 0
#define PERF_TRACE_BUSY UINTPTR_MAX

typedef struct {
  volatile uintptr_t caller;
  volatile unsigned int kind;
  volatile uint64_t count;
  volatile uint64_t requested_ns;
  volatile uint64_t elapsed_ns;
  volatile uint64_t max_ns;
  volatile uint64_t errors;
} PerfTraceEntry;

typedef struct {
  uintptr_t caller;
  unsigned int kind;
  uint64_t count;
  uint64_t requested_ns;
  uint64_t elapsed_ns;
  uint64_t max_ns;
  uint64_t errors;
} PerfTraceSnapshot;

static PerfTraceEntry trace_entries[PERF_TRACE_SLOTS];
static volatile uint64_t trace_dropped;
static volatile uint64_t trace_last_report_ns;

uint64_t perf_trace_now_ns(void) {
  return armTicksToNs(armGetSystemTick());
}

static PerfTraceEntry *perf_trace_entry(enum PerfTraceKind kind,
                                        uintptr_t caller) {
  if (!caller)
    caller = 0x100u + (uintptr_t)kind;
  const uintptr_t hash = (caller >> 4) ^ (caller >> 17) ^
                         ((uintptr_t)kind * 0x9e3779b1u);
  for (unsigned int probe = 0; probe < PERF_TRACE_SLOTS; probe++) {
    PerfTraceEntry *entry =
        &trace_entries[(hash + probe) & (PERF_TRACE_SLOTS - 1)];
    uintptr_t found = __atomic_load_n(&entry->caller, __ATOMIC_ACQUIRE);
    if (found == caller &&
        __atomic_load_n(&entry->kind, __ATOMIC_RELAXED) ==
            (unsigned int)kind)
      return entry;
    if (found != PERF_TRACE_EMPTY)
      continue;
    uintptr_t expected = PERF_TRACE_EMPTY;
    if (!__atomic_compare_exchange_n(&entry->caller, &expected,
                                     PERF_TRACE_BUSY, 0, __ATOMIC_ACQ_REL,
                                     __ATOMIC_ACQUIRE))
      continue;
    __atomic_store_n(&entry->kind, (unsigned int)kind, __ATOMIC_RELAXED);
    __atomic_store_n(&entry->caller, caller, __ATOMIC_RELEASE);
    return entry;
  }
  __atomic_fetch_add(&trace_dropped, 1, __ATOMIC_RELAXED);
  return NULL;
}

void perf_trace_record(enum PerfTraceKind kind, const void *caller_ptr,
                       uint64_t requested_ns, uint64_t elapsed_ns, int result) {
  PerfTraceEntry *entry =
      perf_trace_entry(kind, (uintptr_t)caller_ptr);
  if (!entry)
    return;
  __atomic_fetch_add(&entry->count, 1, __ATOMIC_RELAXED);
  __atomic_fetch_add(&entry->requested_ns, requested_ns, __ATOMIC_RELAXED);
  __atomic_fetch_add(&entry->elapsed_ns, elapsed_ns, __ATOMIC_RELAXED);
  if (result)
    __atomic_fetch_add(&entry->errors, 1, __ATOMIC_RELAXED);
  uint64_t maximum = __atomic_load_n(&entry->max_ns, __ATOMIC_RELAXED);
  while (maximum < elapsed_ns &&
         !__atomic_compare_exchange_n(&entry->max_ns, &maximum, elapsed_ns, 0,
                                      __ATOMIC_RELAXED,
                                      __ATOMIC_RELAXED)) {
  }
}

static const char *perf_trace_kind_name(unsigned int kind) {
  static const char *const names[] = {
      "?",     "nano", "usleep", "sleep", "clockns",
      "cond",  "tcond", "looper", "frame", "swap",
  };
  return kind < sizeof(names) / sizeof(names[0]) ? names[kind] : "?";
}

static void perf_trace_address(char *out, size_t size, uintptr_t address) {
  const uintptr_t ue4 = (uintptr_t)ue4_mod.load_virtbase;
  const uintptr_t avs = (uintptr_t)avs_mod.load_virtbase;
  const uintptr_t afp = (uintptr_t)afp_mod.load_virtbase;
  if (ue4 && address >= ue4 && address < ue4 + ue4_mod.load_size)
    snprintf(out, size, "UE4+%lx", (unsigned long)(address - ue4));
  else if (avs && address >= avs && address < avs + avs_mod.load_size)
    snprintf(out, size, "AVS+%lx", (unsigned long)(address - avs));
  else if (afp && address >= afp && address < afp + afp_mod.load_size)
    snprintf(out, size, "AFP+%lx", (unsigned long)(address - afp));
  else if (address < 0x200)
    snprintf(out, size, "internal");
  else
    snprintf(out, size, "%lx", (unsigned long)address);
}

static uint64_t perf_trace_score(const PerfTraceSnapshot *snapshot) {
  return snapshot->elapsed_ns + snapshot->max_ns * 4;
}

static void perf_trace_insert_top(PerfTraceSnapshot *top, unsigned int *count,
                                  const PerfTraceSnapshot *candidate) {
  unsigned int at = *count;
  if (at < PERF_TRACE_TOP)
    (*count)++;
  else if (perf_trace_score(candidate) <= perf_trace_score(&top[at - 1]))
    return;
  else
    at--;

  while (at > 0 &&
         perf_trace_score(candidate) > perf_trace_score(&top[at - 1])) {
    if (at < PERF_TRACE_TOP)
      top[at] = top[at - 1];
    at--;
  }
  top[at] = *candidate;
}

static void perf_trace_output(const char *line) {
  svcOutputDebugString(line, strlen(line));
}

void perf_trace_report(void) {
  const uint64_t now = perf_trace_now_ns();
  uint64_t previous =
      __atomic_load_n(&trace_last_report_ns, __ATOMIC_RELAXED);
  if (previous && now - previous < 5000000000ULL)
    return;
  if (!__atomic_compare_exchange_n(&trace_last_report_ns, &previous, now, 0,
                                   __ATOMIC_ACQ_REL, __ATOMIC_RELAXED))
    return;

  PerfTraceSnapshot top[PERF_TRACE_TOP] = {0};
  unsigned int top_count = 0;
  for (unsigned int i = 0; i < PERF_TRACE_SLOTS; i++) {
    PerfTraceEntry *entry = &trace_entries[i];
    const uintptr_t caller =
        __atomic_load_n(&entry->caller, __ATOMIC_ACQUIRE);
    if (!caller || caller == PERF_TRACE_BUSY)
      continue;
    PerfTraceSnapshot snapshot = {
        .caller = caller,
        .kind = __atomic_load_n(&entry->kind, __ATOMIC_RELAXED),
        .count = __atomic_exchange_n(&entry->count, 0, __ATOMIC_RELAXED),
        .requested_ns =
            __atomic_exchange_n(&entry->requested_ns, 0, __ATOMIC_RELAXED),
        .elapsed_ns =
            __atomic_exchange_n(&entry->elapsed_ns, 0, __ATOMIC_RELAXED),
        .max_ns = __atomic_exchange_n(&entry->max_ns, 0, __ATOMIC_RELAXED),
        .errors = __atomic_exchange_n(&entry->errors, 0, __ATOMIC_RELAXED),
    };
    if (snapshot.count)
      perf_trace_insert_top(top, &top_count, &snapshot);
  }

  char line[256];
  snprintf(line, sizeof(line),
           "[PESPERF] window=%llums entries=%u dropped=%llu\n",
           (unsigned long long)(previous ? (now - previous) / 1000000ULL : 0),
           top_count,
           (unsigned long long)__atomic_exchange_n(&trace_dropped, 0,
                                                   __ATOMIC_RELAXED));
  perf_trace_output(line);
  for (unsigned int i = 0; i < top_count; i++) {
    char address[48];
    perf_trace_address(address, sizeof(address), top[i].caller);
    snprintf(line, sizeof(line),
             "[PESPERF] %-7s %-18s n=%llu req=%llums wait=%llums avg=%lluus "
             "max=%lluus err=%llu\n",
             perf_trace_kind_name(top[i].kind), address,
             (unsigned long long)top[i].count,
             (unsigned long long)(top[i].requested_ns / 1000000ULL),
             (unsigned long long)(top[i].elapsed_ns / 1000000ULL),
             (unsigned long long)(top[i].elapsed_ns /
                                  (top[i].count ? top[i].count : 1) / 1000ULL),
             (unsigned long long)(top[i].max_ns / 1000ULL),
             (unsigned long long)top[i].errors);
    perf_trace_output(line);
  }
}

#endif
