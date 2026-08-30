#include "android_mmap.h"
#include <assert.h>
#include <errno.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

extern int pes_mmap_test_fail_after;

static unsigned char *allocate(size_t n) {
  unsigned char *p = mmap_fake(NULL, n, 3, 0x22, -1, 0);
  assert(p != (void *)-1);
  for (size_t i = 0; i < n; ++i)
    assert(p[i] == 0);
  return p;
}

static void empty(void) {
  PesMmapStats s;
  pes_mmap_get_stats(&s);
  assert(s.regions == 0 && s.backing_bytes == 0 && s.mapped_bytes == 0);
}

static void *worker(void *arg) {
  (void)arg;
  for (int i = 0; i < 100; ++i) {
    unsigned char *p = allocate(0x41000);
    memset(p, 0xa5, 0x41000);
    assert(munmap_fake(p + 0x1000, 0x3f000) == 0);
    assert(p[0] == 0xa5 && p[0x40000] == 0xa5);
    assert(munmap_fake(p, 0x41000) == 0);
  }
  return NULL;
}

int main(void) {
  assert(mmap_fake(NULL, 0, 3, 0x22, -1, 0) == (void *)-1);
  assert(mmap_fake(NULL, SIZE_MAX, 3, 0x22, -1, 0) == (void *)-1);
  assert(mmap_fake(NULL, 4096, 3, 0x32, -1, 0) == (void *)-1);
  assert(munmap_fake((void *)1, 4096) == -1 && errno == EINVAL);
  assert(munmap_fake(NULL, 0) == -1);
  assert(munmap_fake((void *)(UINTPTR_MAX & ~(uintptr_t)4095), 8192) == -1);
  // UE4-style trim: 4 MiB -> 4 KiB. Only one 64 KiB backing remains.
  unsigned char *p = allocate(0x400000);
  p[0x200000] = 0x5a;
  assert(munmap_fake(p, 0x200000) == 0);
  assert(munmap_fake(p + 0x201000, 0x1ff000) == 0);
  PesMmapStats s;
  pes_mmap_get_stats(&s);
  assert(s.backing_bytes == 0x10000 && s.mapped_bytes == 0x1000);
  assert(p[0x200000] == 0x5a);
  // Repeated overlapping unmap must not underflow accounting.
  assert(munmap_fake(p, 0x200000) == 0);
  assert(munmap_fake(p + 0x200000, 1) == 0);
  empty();
  for (int fail = 0; fail < 4; ++fail) {
    pes_mmap_test_fail_after = fail;
    assert(mmap_fake(NULL, 0x40000, 3, 0x22, -1, 0) == (void *)-1);
    empty();
  }
  pes_mmap_test_fail_after = -1;
  FILE *file = tmpfile();
  assert(file);
  assert(fwrite("PES21", 1, 5, file) == 5);
  fflush(file);
  p = mmap_fake(NULL, 4096, 1, 2, fileno(file), 0);
  assert(p != (void *)-1 && memcmp(p, "PES21", 5) == 0 && p[5] == 0);
  fclose(file);
  assert(munmap_fake(p, 4096) == 0);
  assert(mmap_fake(NULL, 4096, 1, 2, 999999, 0) == (void *)-1);
  empty();
  pthread_t threads[4];
  for (int i = 0; i < 4; ++i)
    assert(pthread_create(&threads[i], NULL, worker, NULL) == 0);
  for (int i = 0; i < 4; ++i)
    assert(pthread_join(threads[i], NULL) == 0);
  empty();
  puts("PASS mmap: partial trim, overlap, zero-fill, rollback, overflow, 400 threaded lifecycles");
}
