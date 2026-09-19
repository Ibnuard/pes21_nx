#ifndef PES_PITCH_SHADOW_POLICY_H
#define PES_PITCH_SHADOW_POLICY_H
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

// Fingerprints of the owned v5.3.0 day pitch main bodies (both CSM and non-CSM
// variants). Audited night/Low bodies do not share these hashes. No generated
// shader payload is embedded.
static int pitch_day_shadow_body(const char *body) {
  static const uint32_t allowed[] = {
    0x038325c5u, 0x284db1fau, 0x2ba923ebu, 0x2d9e5957u,
    0x37966a69u, 0x3e3879b5u, 0x523e5f8cu, 0x536331a8u,
    0x713d2026u, 0x7e2c0da5u, 0x97e96ba6u, 0x9e0b3576u,
    0xa251829cu, 0xb51dd7c1u, 0xbd0af1c0u, 0xbe93c4b6u,
    0xefff8d62u, 0xf0d87d2du
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

  // Day-only additive grazing highlight, not the base texture or scene tint.
  const char *old_tint = "vec3(8.755540e-01,1.000000e+00,0.000000e+00)";
  // The roof-disabled mask makes this view-dependent term full-strength in
  // places that used to be shadowed. Remove only this additive term: the
  // authored diffuse, mowing stripes and grain still feed native lighting.
  const char *new_tint = "vec3(0.000000e+00,0.000000e+00,0.000000e+00)";
  const char *tint = strstr(body, old_tint);
  if (!tint || strstr(tint+strlen(old_tint), old_tint)) return NULL;

  // Detect output variable: CSM variants write v1, non-CSM variants write v0.
  const char *out_v1 = "out_Target0.xyzw = v1;";
  const char *out_v0 = "out_Target0.xyzw = v0;";
  const char *out_target = strstr(body, out_v1);
  int is_v1 = 1;
  if (!out_target) {
    out_target = strstr(body, out_v0);
    is_v1 = 0;
  }
  if (!out_target) return NULL;
  if (is_v1 && strstr(out_target+strlen(out_v1), out_v1)) return NULL;
  if (!is_v1 && strstr(out_target+strlen(out_v0), out_v0)) return NULL;
  // Optional CSM depth comparison slope adjustment.
  const char *key = "MobileDirectionalLight_DirectionalLightDirectionAndShadowTransition.w";
  const char *at = strstr(body, key);
  if (at && (at[strlen(key)] != ';' || strstr(at+strlen(key), key))) return NULL;
  const char *extra = at ? " * 0.85" : "";
  const size_t extra_len = strlen(extra);
  const size_t n = strlen(source);
  const size_t prefix = at ? (size_t)(at-source)+strlen(key) : 0;

  char *result = (char *)malloc(n+extra_len+1);
  if (!result) return NULL;
  if (at) {
    memcpy(result, source, prefix);
    memcpy(result+prefix, extra, extra_len);
    memcpy(result+prefix+extra_len, source+prefix, n-prefix+1);
  } else {
    memcpy(result, source, n+1);
  }

  size_t tint_offset = (size_t)(tint-source);
  if (at && tint_offset >= prefix) tint_offset += extra_len;
  // Equal-length tokens preserve every other byte in the shader.
  memcpy(result+tint_offset, new_tint, strlen(new_tint));

  // The previous post-light green/blue grass grade is intentionally removed:
  // native pitch UV colour now passes through unchanged. Keep the independent
  // roof-mask and additive-highlight fixes above.
  return result;
}

// Called only after the day allowlist accepted the original shader.
static char *pitch_roof_source(const char *source) {
  const char *main = strstr(source, "void main()");
  const char *sample = "texture(ps1,in_TEXCOORD0.zw)";
  const char *at = main ? strstr(main, sample) : NULL;
  if (!at || strstr(at+strlen(sample), sample)) return NULL;
  const char *declaration = "uniform highp float nxRoofDisabled;\n";
  // Uniform branch also avoids the unused roof-mask fetch in OFF, instead
  // of sampling it and merely mixing away the result afterwards.
  const char *replacement = "(nxRoofDisabled > 0.5 ? vec4(1.0) : texture(ps1,in_TEXCOORD0.zw))";
  size_t a = (size_t)(main-source), b = (size_t)(at-main);
  size_t length = strlen(source)+strlen(declaration)+strlen(replacement)-strlen(sample);
  char *result = (char *)malloc(length+1);
  if (!result) return NULL;
  memcpy(result, source, a);
  memcpy(result+a, declaration, strlen(declaration));
  size_t pos = a+strlen(declaration);
  memcpy(result+pos, main, b); pos += b;
  memcpy(result+pos, replacement, strlen(replacement)); pos += strlen(replacement);
  strcpy(result+pos, at+strlen(sample));
  return result;
}
#endif
