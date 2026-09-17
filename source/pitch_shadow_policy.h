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
  // Day-only additive grazing highlight, not the base texture or scene tint.
  // Retain peak green and use the accepted grass's approximate R:G:B ratio.
  const char *old_tint = "vec3(8.755540e-01,1.000000e+00,0.000000e+00)";
  const char *new_tint = "vec3(6.000000e-01,1.000000e+00,2.900000e-01)";
  const char *tint = strstr(body, old_tint);
  if (!tint || strstr(tint+strlen(old_tint), old_tint)) return NULL;
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
  size_t tint_offset = (size_t)(tint-source);
  if (tint_offset >= prefix) tint_offset += strlen(extra);
  // Equal-length tokens preserve every other byte in the shader.
  memcpy(result+tint_offset, new_tint, strlen(new_tint));
  // A pitch-local artistic grade after lighting. Preserve luminance and alpha;
  // fade out on neutral paint instead of grading the entire composed scene.
  const char *output = "out_Target0.xyzw = v1;";
  char *end = strstr(result, output);
  if (!end || strstr(end+strlen(output), output)) { free(result); return NULL; }
  const char *grade =
    "\n// NX pitch hue begin\n"
    "highp vec3 nxGrass = max(v1.xyz, vec3(0.0));\n"
    "highp float nxMask = smoothstep(0.05, 0.18, (nxGrass.g-max(nxGrass.r,nxGrass.b))/max(nxGrass.g,0.0001));\n"
    "highp vec3 nxTint = nxGrass*vec3(0.82,1.0,1.12);\n"
    "nxTint *= dot(nxGrass,vec3(0.2126,0.7152,0.0722))/max(dot(nxTint,vec3(0.2126,0.7152,0.0722)),0.0001);\n"
    "out_Target0.xyz = mix(v1.xyz,nxTint,nxMask);\n"
    "// NX pitch hue end\n";
  size_t offset = (size_t)(end-result)+strlen(output), total = strlen(result);
  char *graded = (char *)malloc(total+strlen(grade)+1);
  if (!graded) { free(result); return NULL; }
  memcpy(graded, result, offset);
  memcpy(graded+offset, grade, strlen(grade));
  memcpy(graded+offset+strlen(grade), result+offset, total-offset+1);
  free(result);
  return graded;
}
// Called only after the day allowlist accepted the original shader.
static char *pitch_roof_source(const char *source) {
  const char *main = strstr(source, "void main()");
  const char *sample = "texture(ps1,in_TEXCOORD0.zw)";
  const char *at = main ? strstr(main, sample) : NULL;
  if (!at || strstr(at+strlen(sample), sample)) return NULL;
  const char *declaration = "uniform highp float nxRoofDisabled;\n";
  const char *replacement = "mix(texture(ps1,in_TEXCOORD0.zw),vec4(1.0),nxRoofDisabled)";
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
