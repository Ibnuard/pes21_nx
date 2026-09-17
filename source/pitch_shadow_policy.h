#ifndef PES_PITCH_SHADOW_POLICY_H
#define PES_PITCH_SHADOW_POLICY_H
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

// Fingerprints of the owned v5.3.0 day pitch main bodies. Audited night/Low
// bodies do not share these hashes. No generated shader payload is embedded.
static int pitch_day_shadow_body(const char *body) {
  static const uint32_t allowed[] = {
    0x2ba923ebu, 0x3e3879b5u, 0x7e2c0da5u, 0x9e0b3576u,
    0xa251829cu, 0xb51dd7c1u, 0xbd0af1c0u, 0xf0d87d2du
  };
  uint32_t hash = 2166136261u;
  for (const unsigned char *p=(const unsigned char *)body; *p; ++p) {
    if (*p==' ' || *p=='\r' || *p=='\n' || *p=='\t') continue;
    hash = (hash ^ *p) * 16777619u;
  }
  for (unsigned i=0; i<sizeof(allowed)/sizeof(allowed[0]); ++i)
    if (hash == allowed[i]) return 1;
  return 0;
}

static char *pitch_shadow_source(const char *source) {
  const char *body = strstr(source, "void main()");
  if (!body || !pitch_day_shadow_body(body)) return NULL;
  const char *key = "MobileDirectionalLight_DirectionalLightDirectionAndShadowTransition.w";
  const char *at = strstr(body, key);
  if (!at || at[strlen(key)] != ';' || strstr(at+strlen(key), key)) return NULL;
  // Reduce the native depth comparison slope slightly; preserve all nine
  // PCF taps, geometry, lighting color and cascade logic. This is a depth
  // transition experiment, not a change to the spatial PCF kernel.
  const char *extra = " * 0.85";
  const size_t n = strlen(source), prefix = (size_t)(at-source)+strlen(key);
  char *result = (char *)malloc(n+strlen(extra)+1);
  if (!result) return NULL;
  memcpy(result, source, prefix);
  memcpy(result+prefix, extra, strlen(extra));
  memcpy(result+prefix+strlen(extra), source+prefix, n-prefix+1);
  return result;
}
#endif
