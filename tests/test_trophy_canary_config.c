#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "trophy_canary_config.h"

static const char manifest_hash[] = "123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef0";
static void empty(const TrophyCanaryConfig *config) {
  const TrophyCanaryConfig zero = {0};
  assert(!memcmp(config, &zero, sizeof(zero)));
}

int main(void) {
  char marker[512];
  const int length = snprintf(marker, sizeof(marker), PESNX_TROPHY_MARKER_HEADER
      "cpk_sha256=%s\nmanifest_sha256=%s\npak_sha256=%s\n",
      PESNX_TROPHY_CPK_SHA256, manifest_hash, PESNX_TROPHY_PAK_SHA256);
  assert(length > 0 && (size_t)length < sizeof(marker));
  TrophyCanaryConfig config;
  assert(trophy_canary_parse(marker, (size_t)length, &config));
  assert(trophy_canary_files_match(&config, 2, PESNX_TROPHY_NATIVE_SHA256,
      PESNX_TROPHY_CPK_SHA256, manifest_hash, PESNX_TROPHY_PAK_SHA256));
  assert(!trophy_canary_files_match(&config, 1, PESNX_TROPHY_NATIVE_SHA256,
      PESNX_TROPHY_CPK_SHA256, manifest_hash, PESNX_TROPHY_PAK_SHA256));
  const char *actual[] = {PESNX_TROPHY_NATIVE_SHA256, PESNX_TROPHY_CPK_SHA256,
                          manifest_hash, PESNX_TROPHY_PAK_SHA256};
  for (int i = 0; i < 4; ++i) {
    const char *values[4];
    memcpy(values, actual, sizeof(values));
    values[i] = "different-file";
    assert(!trophy_canary_files_match(&config, 2, values[0], values[1], values[2], values[3]));
    values[i] = NULL;
    assert(!trophy_canary_files_match(&config, 2, values[0], values[1], values[2], values[3]));
  }
  for (int i = 0; i < length; ++i) {
    memset(&config, 0xff, sizeof(config));
    assert(!trophy_canary_parse(marker, (size_t)i, &config));
    empty(&config);
  }
  char altered[512];
  memcpy(altered, marker, (size_t)length);
  altered[length] = '\n';
  assert(!trophy_canary_parse(altered, (size_t)length + 1u, &config));
  empty(&config);
  const char replacements[] = {'\r', 'X', '\0'};
  const size_t key = sizeof(PESNX_TROPHY_MARKER_HEADER) - 1u;
  for (size_t i = 0; i < sizeof(replacements); ++i) {
    memcpy(altered, marker, (size_t)length);
    altered[key] = replacements[i];
    assert(!trophy_canary_parse(altered, (size_t)length, &config));
    empty(&config);
  }
  memcpy(altered, marker, (size_t)length);
  const size_t first_hash_digit = key + strlen("cpk_sha256=");
  altered[first_hash_digit] = marker[first_hash_digit] == '0' ? '1' : '0';
  assert(!trophy_canary_parse(altered, (size_t)length, &config)); /* unknown CPK */
  empty(&config);
  /* A v50 NRO must not enable against the native-intro-only v49 package. */
  memcpy(altered, marker, (size_t)length);
  memcpy(altered + first_hash_digit,
      "3fe2308ad07e4d776fcd1bb816cecbd2b859072b908b467b2bc56ce1b7e28cbb", 64u);
  assert(!trophy_canary_parse(altered, (size_t)length, &config));
  empty(&config);
  assert(!trophy_canary_parse(NULL, 0, &config));
  assert(!trophy_canary_parse(marker, (size_t)length, NULL));
  puts("trophy marker identity: pass");
  return 0;
}
