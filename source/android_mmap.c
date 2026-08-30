// Android anonymous mappings with independently reclaimable 64 KiB backing.
// UE4 reserves several MiB, then trims almost all of that reservation. A single
// malloc per mmap stranded the trimmed memory until the last page was freed.
// Keep the virtual range contiguous, but release backing in small chunks.
#include "android_mmap.h"

#include <errno.h>
#include <pthread.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#ifdef PES_MMAP_HOST_TEST
#include <sys/mman.h>
int pes_mmap_test_fail_after = -1;
#else
#include <switch.h>
#include "android_shim.h"
#include "error.h"
#include "libc_shim.h"
#endif

#define PAGE_SIZE 0x1000u
#define CHUNK_SIZE 0x10000u
#define PAGES_PER_CHUNK (CHUNK_SIZE / PAGE_SIZE)
#define ANDROID_MAP_PRIVATE 2
#define ANDROID_MAP_FIXED 0x10
#define ANDROID_MAP_ANONYMOUS 0x20

typedef struct {
  void *backing;
  size_t size;
  uint32_t live_pages;
} MapChunk;

typedef struct MapRegion {
  struct MapRegion *next;
  void *address;
  void *reservation;
  size_t size;
  size_t count;
  MapChunk chunks[];
} MapRegion;

static MapRegion *regions;
static PesMmapStats stats;
static pthread_mutex_t map_mutex = PTHREAD_MUTEX_INITIALIZER;

static int reserve_region(MapRegion *region) {
#ifdef PES_MMAP_HOST_TEST
  region->address = mmap(NULL, region->size, PROT_NONE,
                         MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
  return region->address != MAP_FAILED;
#else
  virtmemLock();
  region->address = virtmemFindStack(region->size, PAGE_SIZE);
  if (region->address)
    region->reservation = virtmemAddReservation(region->address, region->size);
  virtmemUnlock();
  return region->address && region->reservation;
#endif
}

static void release_region(MapRegion *region) {
#ifdef PES_MMAP_HOST_TEST
  munmap(region->address, region->size);
#else
  virtmemLock();
  virtmemRemoveReservation(region->reservation);
  virtmemUnlock();
#endif
}

static int commit_chunk(void *destination, MapChunk *chunk) {
#ifdef PES_MMAP_HOST_TEST
  if (pes_mmap_test_fail_after == 0)
    return 0;
  if (pes_mmap_test_fail_after > 0)
    pes_mmap_test_fail_after--;
  if (mmap(destination, chunk->size, PROT_READ | PROT_WRITE,
           MAP_FIXED | MAP_PRIVATE | MAP_ANONYMOUS, -1, 0) == MAP_FAILED)
    return 0;
  chunk->backing = destination;
#else
  if (posix_memalign_fake(&chunk->backing, PAGE_SIZE, chunk->size) != 0)
    return 0;
  memset(chunk->backing, 0, chunk->size);
  const Result rc = svcMapMemory(destination, chunk->backing, chunk->size);
  if (R_FAILED(rc)) {
    free(chunk->backing);
    chunk->backing = NULL;
    return 0;
  }
#endif
  chunk->live_pages = (1u << (chunk->size / PAGE_SIZE)) - 1u;
  return 1;
}

static void release_chunk(void *destination, MapChunk *chunk) {
#ifdef PES_MMAP_HOST_TEST
  // Keep the virtual reservation until all chunks are gone.
  if (mmap(destination, chunk->size, PROT_NONE,
           MAP_FIXED | MAP_PRIVATE | MAP_ANONYMOUS, -1, 0) == MAP_FAILED)
    abort();
#else
  const Result rc = svcUnmapMemory(destination, chunk->backing, chunk->size);
  // Never free still-mapped heap memory: newlib would touch protected pages.
  if (R_FAILED(rc))
    fatal_error("mmap backing unmap failed: %08x", rc);
  free(chunk->backing);
#endif
  chunk->backing = NULL;
  chunk->live_pages = 0;
}

static int align_length(size_t length, size_t *aligned) {
  if (!length || length > SIZE_MAX - (PAGE_SIZE - 1)) {
    errno = EINVAL;
    return 0;
  }
  *aligned = (length + PAGE_SIZE - 1) & ~(size_t)(PAGE_SIZE - 1);
  return 1;
}

void *mmap_fake(void *addr, size_t length, int prot, int flags, int fd,
                int64_t offset) {
  (void)addr; // A non-fixed address is only a hint.
  size_t aligned;
  if (!align_length(length, &aligned))
    return (void *)-1;
  // Do not silently return a different address for MAP_FIXED or pretend a
  // private heap copy is writable shared/file-backed memory.
  if ((flags & ANDROID_MAP_FIXED) || !(flags & ANDROID_MAP_PRIVATE) ||
      (prot & ~3) || offset < 0 || ((uint64_t)offset & (PAGE_SIZE - 1)) ||
      (!(flags & ANDROID_MAP_ANONYMOUS) && fd < 0)) {
    errno = EINVAL;
    return (void *)-1;
  }
  const size_t count = aligned / CHUNK_SIZE + (aligned % CHUNK_SIZE != 0);
  if (count > (SIZE_MAX - sizeof(MapRegion)) / sizeof(MapChunk)) {
    errno = ENOMEM;
    return (void *)-1;
  }
  MapRegion *region = calloc(1, sizeof(*region) + count * sizeof(MapChunk));
  if (!region) {
    errno = ENOMEM;
    return (void *)-1;
  }
  region->size = aligned;
  region->count = count;
  if (!reserve_region(region)) {
    free(region);
    errno = ENOMEM;
    return (void *)-1;
  }
  size_t committed = 0;
  for (; committed < count; committed++) {
    MapChunk *chunk = &region->chunks[committed];
    const size_t remaining = aligned - committed * CHUNK_SIZE;
    chunk->size = remaining < CHUNK_SIZE ? remaining : CHUNK_SIZE;
    if (!commit_chunk((char *)region->address + committed * CHUNK_SIZE, chunk))
      break;
  }
  int saved_errno = ENOMEM;
  if (committed == count && !(flags & ANDROID_MAP_ANONYMOUS)) {
    size_t read_bytes = 0;
    while (read_bytes < length) {
#ifdef PES_MMAP_HOST_TEST
      ssize_t got = pread(fd, (char *)region->address + read_bytes,
                          length - read_bytes, offset + read_bytes);
#else
      ssize_t got = pread64_fake(fd, (char *)region->address + read_bytes,
                                 length - read_bytes, offset + read_bytes);
#endif
      if (got < 0 && errno == EINTR)
        continue;
      if (got < 0) {
        saved_errno = errno;
        goto fail;
      }
      if (!got)
        break;
      read_bytes += (size_t)got;
    }
  }
  if (committed != count)
    goto fail;

  pthread_mutex_lock(&map_mutex);
  region->next = regions;
  regions = region;
  stats.regions++;
  stats.mapped_bytes += aligned;
  stats.backing_bytes += aligned;
  if (stats.backing_bytes > stats.peak_backing_bytes)
    stats.peak_backing_bytes = stats.backing_bytes;
  pthread_mutex_unlock(&map_mutex);
  return region->address;

fail:
  while (committed) {
    --committed;
    release_chunk((char *)region->address + committed * CHUNK_SIZE,
                   &region->chunks[committed]);
  }
  release_region(region);
  free(region);
  errno = saved_errno;
  return (void *)-1;
}

int munmap_fake(void *addr, size_t length) {
  size_t aligned;
  const uintptr_t start = (uintptr_t)addr;
  if (!align_length(length, &aligned))
    return -1;
  if ((start & (PAGE_SIZE - 1)) || start > UINTPTR_MAX - aligned) {
    errno = EINVAL;
    return -1;
  }
  const uintptr_t end = start + aligned;
  pthread_mutex_lock(&map_mutex);
  MapRegion **link = &regions;
  while (*link) {
    MapRegion *region = *link;
    const uintptr_t base = (uintptr_t)region->address;
    if (end <= base || start >= base + region->size) {
      link = &region->next;
      continue;
    }
    int live = 0;
    for (size_t i = 0; i < region->count; i++) {
      MapChunk *chunk = &region->chunks[i];
      if (!chunk->backing)
        continue;
      const uintptr_t chunk_start = base + i * CHUNK_SIZE;
      const uintptr_t chunk_end = chunk_start + chunk->size;
      const uintptr_t lo = start > chunk_start ? start : chunk_start;
      const uintptr_t hi = end < chunk_end ? end : chunk_end;
      if (lo < hi) {
        const unsigned first = (lo - chunk_start) / PAGE_SIZE;
        const unsigned pages = (hi - lo) / PAGE_SIZE;
        const uint32_t mask = ((1u << pages) - 1u) << first;
        stats.mapped_bytes -=
            (size_t)__builtin_popcount(chunk->live_pages & mask) * PAGE_SIZE;
        chunk->live_pages &= ~mask;
        if (!chunk->live_pages) {
          release_chunk((void *)chunk_start, chunk);
          stats.backing_bytes -= chunk->size;
        }
      }
      live |= chunk->backing != NULL;
    }
    if (live) {
      link = &region->next;
    } else {
      *link = region->next;
      release_region(region);
      free(region);
      stats.regions--;
    }
  }
  pthread_mutex_unlock(&map_mutex);
  return 0;
}

void pes_mmap_get_stats(PesMmapStats *out) {
  pthread_mutex_lock(&map_mutex);
  *out = stats;
  pthread_mutex_unlock(&map_mutex);
}
