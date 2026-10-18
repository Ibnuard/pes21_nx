#ifndef PESNX_GL_RENDER_PROBE_POLICY_H
#define PESNX_GL_RENDER_PROBE_POLICY_H
#include <stddef.h>
#include <string.h>

/* Diagnostic boot control only. A malformed or unrelated file keeps the
 * production state cache enabled. No live file polling or game asset change. */
static inline int nx_gl_cache_bypass_line(const char *data,size_t size) {
  static const char token[]="PESNX_GL_CACHE_BYPASS_V1";
  if (size && data[size-1]=='\n') --size;
  if (size && data[size-1]=='\r') --size;
  return size==sizeof(token)-1 && !memcmp(data,token,size);
}
/* Separate A/B: retain the cache and native saved quality, but don't install
 * the mixed High->Standard player-class branch in the diagnostic build. */
static inline int nx_gl_native_player_class_line(const char *data,size_t size) {
  static const char token[]="PESNX_NATIVE_PLAYER_CLASS_V1";
  if (size && data[size-1]=='\n') --size;
  if (size && data[size-1]=='\r') --size;
  return size==sizeof(token)-1 && !memcmp(data,token,size);
}
#endif
