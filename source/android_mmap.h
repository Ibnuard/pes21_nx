#ifndef PES_ANDROID_MMAP_H
#define PES_ANDROID_MMAP_H

#include <stddef.h>
#include <stdint.h>

typedef struct {
  size_t mapped_bytes;
  size_t backing_bytes;
  size_t peak_backing_bytes;
  size_t regions;
} PesMmapStats;

void *mmap_fake(void *addr, size_t length, int prot, int flags, int fd,
                int64_t offset);
int munmap_fake(void *addr, size_t length);
// On-demand diagnostics only: no frame hook or periodic scan.
void pes_mmap_get_stats(PesMmapStats *out);

#endif
