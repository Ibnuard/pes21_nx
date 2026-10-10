/* Optional local assets in a project-defined archive; no executable data. */
#ifndef PESNX_RUNTIME_ASSETS_H
#define PESNX_RUNTIME_ASSETS_H

#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define NX_ASSET_ARCHIVE "FootballNX.assets"
#define NX_ASSET_NAME_BYTES 128u
#define NX_ASSET_ENTRY_BYTES 160u
#define NX_ASSET_MAX_ENTRIES 4096u

static inline uint64_t nx_asset_u64(const unsigned char *p) {
  uint64_t v = 0;
  for (unsigned i = 0; i < 8; ++i) v |= (uint64_t)p[i] << (i * 8u);
  return v;
}
static inline uint32_t nx_asset_u32(const unsigned char *p) {
  return (uint32_t)p[0] | (uint32_t)p[1] << 8 |
         (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}
static inline uint64_t nx_asset_hash(const void *data, size_t size) {
  const unsigned char *p = data;
  uint64_t h = UINT64_C(0xcbf29ce484222325);
  for (size_t i = 0; i < size; ++i)
    h = (h ^ p[i]) * UINT64_C(0x100000001b3);
  return h;
}

/* Match SD's case-insensitive names, but accept only relative portable paths.
 * Reject traversal before attempting either the loose file or archive. */
static inline int nx_asset_name(const char *path, char out[NX_ASSET_NAME_BYTES]) {
  if (!path || !*path) return 0;
  size_t n = 0, segment = 0;
  for (; path[n]; ++n) {
    unsigned char c = (unsigned char)path[n];
    if (n >= NX_ASSET_NAME_BYTES - 1u || c < 32u || c >= 127u ||
        c == ':' || c == '\\') return 0;
    if (c == '/') {
      const size_t len = n - segment;
      if (!len || (len == 1 && path[segment] == '.') ||
          (len == 2 && path[segment] == '.' && path[segment+1] == '.'))
        return 0;
      segment = n + 1;
    }
    out[n] = (char)(c >= 'A' && c <= 'Z' ? c + ('a' - 'A') : c);
  }
  const size_t len = n - segment;
  if (!len || (len == 1 && path[segment] == '.') ||
      (len == 2 && path[segment] == '.' && path[segment+1] == '.')) return 0;
  out[n] = 0;
  return 1;
}

/* Binary-search the fixed-width index directly. No global mutable file cursor,
 * index allocation, extraction, or whole-archive decompression is needed. */
static inline void *nx_asset_read_archive(const char *archive, const char *path,
                                         size_t max_bytes, size_t *size) {
  char key[NX_ASSET_NAME_BYTES];
  if (size) *size = 0;
  if (!size || !max_bytes || !nx_asset_name(path, key)) return NULL;
  FILE *f = fopen(archive, "rb");
  if (!f) return NULL;
  unsigned char header[32], entry[NX_ASSET_ENTRY_BYTES];
  unsigned char *bytes = NULL;
  if (fseek(f, 0, SEEK_END)) goto done;
  const long length = ftell(f);
  if (length < 32 || fseek(f, 0, SEEK_SET) ||
      fread(header, 1, sizeof(header), f) != sizeof(header) ||
      memcmp(header, "FNXAS01\0", 8)) goto done;
  const uint32_t count = nx_asset_u32(header + 8);
  const uint64_t payload = 32u + (uint64_t)count * NX_ASSET_ENTRY_BYTES;
  if (!count || count > NX_ASSET_MAX_ENTRIES ||
      nx_asset_u32(header + 12) != NX_ASSET_ENTRY_BYTES ||
      nx_asset_u64(header + 16) != (uint64_t)length ||
      nx_asset_u64(header + 24) != payload || payload > (uint64_t)length)
    goto done;
  uint32_t low = 0, high = count;
  while (low < high) {
    const uint32_t mid = low + (high - low) / 2u;
    if (fseek(f, (long)(32u + mid * NX_ASSET_ENTRY_BYTES), SEEK_SET) ||
        fread(entry, 1, sizeof(entry), f) != sizeof(entry) ||
        !memchr(entry, 0, NX_ASSET_NAME_BYTES)) goto done;
    const int order = strcmp(key, (const char *)entry);
    if (order < 0) high = mid;
    else if (order > 0) low = mid + 1;
    else {
      const uint64_t offset = nx_asset_u64(entry + 128);
      const uint64_t bytes_count = nx_asset_u64(entry + 136);
      if (nx_asset_u32(entry + 152) || nx_asset_u32(entry + 156) ||
          offset < payload || offset > (uint64_t)length ||
          !bytes_count || bytes_count > max_bytes ||
          bytes_count > (uint64_t)length - offset || offset > LONG_MAX)
        goto done;
      bytes = malloc((size_t)bytes_count);
      if (!bytes || fseek(f, (long)offset, SEEK_SET) ||
          fread(bytes, 1, (size_t)bytes_count, f) != bytes_count ||
          nx_asset_hash(bytes, (size_t)bytes_count) != nx_asset_u64(entry + 144)) {
        free(bytes);
        bytes = NULL;
      } else *size = (size_t)bytes_count;
      break;
    }
  }
done:
  fclose(f);
  return bytes;
}

/* Loose files remain an explicit mod override. An invalid override is an
 * error, rather than silently loading an unrelated archived replacement. */
static inline void *nx_asset_read(const char *path, size_t max_bytes, size_t *size) {
  char key[NX_ASSET_NAME_BYTES];
  if (size) *size = 0;
  if (!size || !max_bytes || !nx_asset_name(path, key)) return NULL;
  FILE *f = fopen(path, "rb");
  if (!f) return nx_asset_read_archive(NX_ASSET_ARCHIVE, key, max_bytes, size);
  unsigned char *bytes = NULL;
  if (fseek(f, 0, SEEK_END)) goto done;
  const long length = ftell(f);
  if (length <= 0 || (uint64_t)length > max_bytes || fseek(f, 0, SEEK_SET)) goto done;
  bytes = malloc((size_t)length);
  if (!bytes || fread(bytes, 1, (size_t)length, f) != (size_t)length) {
    free(bytes);
    bytes = NULL;
  } else *size = (size_t)length;
done:
  fclose(f);
  return bytes;
}
#endif
