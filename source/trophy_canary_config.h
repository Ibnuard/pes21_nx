#ifndef PESNX_TROPHY_CANARY_CONFIG_H
#define PESNX_TROPHY_CANARY_CONFIG_H

#include <stddef.h>
#include <string.h>

/* One explicitly staged asset candidate. Hashes are project compatibility
 * metadata, not embedded game data. Markers cannot approve arbitrary props. */
#define PESNX_TROPHY_NATIVE_SHA256 "a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187"
#define PESNX_TROPHY_CPK_SHA256 "72db80088df2a1648b6c9be3576a35ee6a14e707cb8304c3c289592fe654fd27"
#define PESNX_TROPHY_PAK_SHA256 "17673134cdf4c1c155fc11e271d9bdb69e525b1108d6ba14f618a9c7d67e1b5a"
#define PESNX_TROPHY_MARKER_HEADER "PESNX_TROPHY_CANARY_V1\n"

typedef struct {
  char cpk_sha256[65];
  char manifest_sha256[65];
  char pak_sha256[65];
} TrophyCanaryConfig;

static inline int trophy_canary_hash_valid(const char *text) {
  int nonzero = 0;
  for (size_t i = 0; i < 64u; ++i) {
    const unsigned char ch = (unsigned char)text[i];
    if (!((ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f'))) return 0;
    nonzero |= ch != '0';
  }
  return nonzero && text[64] == '\0';
}

/* Exact ordered LF-only format, no BOM, trailing data, duplicate/unknown keys,
 * paths or permissive whitespace. A failure clears all prior evidence. */
static inline int trophy_canary_parse(const char *text, size_t length,
                                     TrophyCanaryConfig *output) {
  if (!output) return 0;
  memset(output, 0, sizeof(*output));
  static const char *const labels[] = {"cpk_sha256=", "manifest_sha256=", "pak_sha256="};
  const size_t header = sizeof(PESNX_TROPHY_MARKER_HEADER) - 1u;
  if (!text || length < header || memcmp(text, PESNX_TROPHY_MARKER_HEADER, header)) return 0;
  TrophyCanaryConfig parsed = {0};
  char *fields[] = {parsed.cpk_sha256, parsed.manifest_sha256, parsed.pak_sha256};
  size_t cursor = header;
  for (size_t i = 0; i < 3u; ++i) {
    const size_t prefix = strlen(labels[i]);
    if (length - cursor < prefix + 65u || memcmp(text + cursor, labels[i], prefix)) return 0;
    cursor += prefix;
    memcpy(fields[i], text + cursor, 64u);
    if (!trophy_canary_hash_valid(fields[i]) || text[cursor + 64u] != '\n') return 0;
    cursor += 65u;
  }
  if (cursor != length || strcmp(parsed.cpk_sha256, PESNX_TROPHY_CPK_SHA256) ||
      strcmp(parsed.pak_sha256, PESNX_TROPHY_PAK_SHA256)) return 0;
  *output = parsed;
  return 1;
}

/* These measured values come from the original installed files. A caller
 * must not substitute the marker's strings for file hash measurements. */
static inline int trophy_canary_files_match(const TrophyCanaryConfig *config,
    int full_loose_mode, const char *native_hash, const char *cpk_hash,
    const char *manifest_hash, const char *pak_hash) {
  return config && full_loose_mode == 2 && native_hash && cpk_hash &&
      manifest_hash && pak_hash &&
      trophy_canary_hash_valid(config->cpk_sha256) &&
      trophy_canary_hash_valid(config->manifest_sha256) &&
      trophy_canary_hash_valid(config->pak_sha256) &&
      !strcmp(config->cpk_sha256, PESNX_TROPHY_CPK_SHA256) &&
      !strcmp(config->pak_sha256, PESNX_TROPHY_PAK_SHA256) &&
      !strcmp(native_hash, PESNX_TROPHY_NATIVE_SHA256) &&
      !strcmp(cpk_hash, config->cpk_sha256) &&
      !strcmp(manifest_hash, config->manifest_sha256) &&
      !strcmp(pak_hash, config->pak_sha256);
}

#endif
