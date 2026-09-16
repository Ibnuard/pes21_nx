#define _POSIX_C_SOURCE 200809L
#include "loose_cpk.h"
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#define FULL_CPK_COUNT 24

static const char *const names[FULL_CPK_COUNT] = {
    "dt120_mobile_all.cpk",
    "dt200_mobile_all.cpk",
    "dt210_mobile_android.cpk",
    "dt220_mobile_all.cpk",
    "dt230_mobile_all.cpk",
    "dt240_mobile_all.cpk",
    "dt241_mobile_all.cpk",
    "dt250_mobile_all.cpk",
    "dt260_mobile_all.cpk",
    "dt270_mobile_all.cpk",
    "dt500_mobile_all.cpk",
    "dt520_mobile_all.cpk",
    "dt530_mobile_bra_all.cpk",
    "dt530_mobile_can_all.cpk",
    "dt530_mobile_eng_all.cpk",
    "dt530_mobile_fra_all.cpk",
    "dt530_mobile_ger_all.cpk",
    "dt530_mobile_ita_all.cpk",
    "dt530_mobile_jpn_all.cpk",
    "dt530_mobile_kor_all.cpk",
    "dt530_mobile_man_all.cpk",
    "dt530_mobile_spa_all.cpk",
    "dt540_mobile_all.cpk",
    "dt700_mobile_android.cpk",
};

static const char *const native_paths[FULL_CPK_COUNT] = {
    "/Expansion/dt120_mobile_all.cpk",
    "/Expansion/dt200_mobile_all.cpk",
    "/Expansion/dt210_mobile_android.cpk",
    "/Expansion/dt220_mobile_all.cpk",
    "/Expansion/dt230_mobile_all.cpk",
    "/Expansion/dt240_mobile_all.cpk",
    "/Expansion/dt241_mobile_all.cpk",
    "/Expansion/dt250_mobile_all.cpk",
    "/Expansion/dt260_mobile_all.cpk",
    "/Expansion/dt270_mobile_all.cpk",
    "/Expansion/dt500_mobile_all.cpk",
    "/Expansion/dt520_mobile_all.cpk",
    "/Expansion/dt530_mobile_bra_all.cpk",
    "/Expansion/dt530_mobile_can_all.cpk",
    "/Expansion/dt530_mobile_eng_all.cpk",
    "/Expansion/dt530_mobile_fra_all.cpk",
    "/Expansion/dt530_mobile_ger_all.cpk",
    "/Expansion/dt530_mobile_ita_all.cpk",
    "/Expansion/dt530_mobile_jpn_all.cpk",
    "/Expansion/dt530_mobile_kor_all.cpk",
    "/Expansion/dt530_mobile_man_all.cpk",
    "/Expansion/dt530_mobile_spa_all.cpk",
    "/Expansion/dt540_mobile_all.cpk",
    "/Expansion/dt700_mobile_android.cpk",
};

static const char *const loose_paths[FULL_CPK_COUNT] = {
    "./LooseCpk/dt120_mobile_all.cpk",
    "./LooseCpk/dt200_mobile_all.cpk",
    "./LooseCpk/dt210_mobile_android.cpk",
    "./LooseCpk/dt220_mobile_all.cpk",
    "./LooseCpk/dt230_mobile_all.cpk",
    "./LooseCpk/dt240_mobile_all.cpk",
    "./LooseCpk/dt241_mobile_all.cpk",
    "./LooseCpk/dt250_mobile_all.cpk",
    "./LooseCpk/dt260_mobile_all.cpk",
    "./LooseCpk/dt270_mobile_all.cpk",
    "./LooseCpk/dt500_mobile_all.cpk",
    "./LooseCpk/dt520_mobile_all.cpk",
    "./LooseCpk/dt530_mobile_bra_all.cpk",
    "./LooseCpk/dt530_mobile_can_all.cpk",
    "./LooseCpk/dt530_mobile_eng_all.cpk",
    "./LooseCpk/dt530_mobile_fra_all.cpk",
    "./LooseCpk/dt530_mobile_ger_all.cpk",
    "./LooseCpk/dt530_mobile_ita_all.cpk",
    "./LooseCpk/dt530_mobile_jpn_all.cpk",
    "./LooseCpk/dt530_mobile_kor_all.cpk",
    "./LooseCpk/dt530_mobile_man_all.cpk",
    "./LooseCpk/dt530_mobile_spa_all.cpk",
    "./LooseCpk/dt540_mobile_all.cpk",
    "./LooseCpk/dt700_mobile_android.cpk",
};

static const unsigned canary_indices[] = {1, 6};
static int enabled_mode;

static void digest_hex(const unsigned char digest[32], char hex[65]) {
  for (unsigned i = 0; i < 32; ++i)
    snprintf(hex + i * 2, 3, "%02x", digest[i]);
}

static int verified_cache_matches(const char manifest_hex[65]) {
  FILE *cache = fopen("LooseCpk/verified-v2.txt", "rb");
  if (!cache) return 0;
  char line[128], magic[40], hex[65], extra;
  const int ok = fgets(line, sizeof(line), cache) &&
                 sscanf(line, "%39s %64s %c", magic, hex, &extra) == 2 &&
                 !strcmp(magic, "PESNX_LOOSE_CPK_VERIFIED_V2") &&
                 !strcmp(hex, manifest_hex) && fgetc(cache) == EOF;
  fclose(cache);
  return ok;
}

static void publish_verified_cache(const char manifest_hex[65]) {
  const char *temp_path = "LooseCpk/verified-v2.part";
  FILE *cache = fopen(temp_path, "wb");
  if (!cache) return;
  const int wrote = fprintf(cache, "PESNX_LOOSE_CPK_VERIFIED_V2 %s\n",
                            manifest_hex) > 0 &&
                    !fflush(cache) && !fsync(fileno(cache));
  if (fclose(cache) || !wrote ||
      rename(temp_path, "LooseCpk/verified-v2.txt"))
    remove(temp_path);
}

int pes_loose_cpk_init(const char *build_id,
                      int require_full,
                      int (*hash_file)(const char *, unsigned char[32]),
                      char *error, size_t error_size) {
  enabled_mode = 0;
  FILE *manifest = fopen("LooseCpk/manifest.txt", "rb");
  if (!manifest) {
    if (errno == ENOENT && !require_full) return 0;
    if (errno == ENOENT)
      snprintf(error, error_size, "Full loose CPK manifest is missing");
    else
      snprintf(error, error_size, "Cannot read LooseCpk/manifest.txt");
    return -1;
  }
  char line[256], magic[32], id[17], parent_hex[65] = {0}, extra;
  unsigned long long parent_size = 0;
  struct stat st;
  const char *failure = "Invalid manifest header/build ID";
  if (!build_id || !hash_file || !fgets(line, sizeof(line), manifest))
    goto fail;
  static const char full_magic[] = "PESNX_LOOSE_CPK_V2 ";
  const int is_full = !strncmp(line, full_magic, sizeof(full_magic) - 1);
  if ((is_full && !require_full) || (!is_full && require_full)) goto fail;
  if (is_full) {
    if (sscanf(line, "%31s %16s %llu %64s %c", magic, id, &parent_size,
               parent_hex, &extra) != 4 ||
        strcmp(magic, "PESNX_LOOSE_CPK_V2") || strlen(parent_hex) != 64 ||
        strcmp(id, build_id))
      goto fail;
  } else if (sscanf(line, "%31s %16s %llu %c", magic, id, &parent_size,
                    &extra) != 3 ||
             strcmp(magic, "PESNX_LOOSE_CPK_V1") || strcmp(id, build_id)) {
    goto fail;
  }
  failure = "Wrong base OBB for loose CPK package";
  if (stat("patch.305030001.jp.nyan2021.pesam.obb", &st) ||
      !S_ISREG(st.st_mode) || (unsigned long long)st.st_size != parent_size)
    goto fail;
  if (is_full) {
    unsigned char parent_digest[32];
    char actual_parent_hex[65];
    if (!hash_file("patch.305030001.jp.nyan2021.pesam.obb", parent_digest))
      goto fail;
    digest_hex(parent_digest, actual_parent_hex);
    if (strcmp(parent_hex, actual_parent_hex)) goto fail;
  }

  unsigned char manifest_digest[32];
  char manifest_hex[65];
  int cached = 0;
  if (is_full) {
    failure = "Cannot hash full loose CPK manifest";
    if (!hash_file("LooseCpk/manifest.txt", manifest_digest)) goto fail;
    digest_hex(manifest_digest, manifest_hex);
    cached = verified_cache_matches(manifest_hex);
  }

  const unsigned entry_count = is_full ? FULL_CPK_COUNT : 2;
  for (unsigned entry = 0; entry < entry_count; ++entry) {
    const unsigned i = is_full ? entry : canary_indices[entry];
    char name[64], hex[65], actual_hex[65];
    unsigned char digest[32];
    unsigned long long size;
    failure = names[i];
    if (!fgets(line, sizeof(line), manifest) ||
        sscanf(line, "%63s %llu %64s %c", name, &size, hex, &extra) != 3 ||
        strcmp(name, names[i]) || strlen(hex) != 64 || !size ||
        stat(loose_paths[i], &st) || !S_ISREG(st.st_mode) ||
        (unsigned long long)st.st_size != size)
      goto fail;
    FILE *cpk = fopen(loose_paths[i], "rb");
    char signature[4];
    if (!cpk) goto fail;
    const int signature_ok = fread(signature, 1, 4, cpk) == 4 &&
                             !memcmp(signature, "CPK ", 4);
    fclose(cpk);
    if (!signature_ok) goto fail;
    if (!cached) {
      if (!hash_file(loose_paths[i], digest)) goto fail;
      digest_hex(digest, actual_hex);
      if (strcmp(hex, actual_hex)) goto fail;
    }
  }
  failure = "Unexpected data after manifest entries";
  for (int ch; (ch = fgetc(manifest)) != EOF; )
    if (ch != ' ' && ch != '\t' && ch != '\n' && ch != '\r') goto fail;
  if (ferror(manifest)) goto fail;
  fclose(manifest);
  if (is_full && !cached) publish_verified_cache(manifest_hex);
  enabled_mode = is_full ? 2 : 1;
  return enabled_mode;
fail:
  snprintf(error, error_size, "Loose CPK validation failed: %s", failure);
  fclose(manifest);
  return -1;
}

const char *pes_loose_cpk_path(const char *path) {
  if (!enabled_mode || !path) return NULL;
  if (enabled_mode == 1) {
    for (unsigned entry = 0; entry < 2; ++entry) {
      const unsigned i = canary_indices[entry];
      if (!strcmp(path, native_paths[i])) return loose_paths[i];
    }
    return NULL;
  }
  for (unsigned i = 0; i < FULL_CPK_COUNT; ++i)
    if (!strcmp(path, native_paths[i])) return loose_paths[i];
  return NULL;
}
