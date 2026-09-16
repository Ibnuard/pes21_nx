#include "loose_cpk.h"
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>

static const char *const names[] = {
    "dt200_mobile_all.cpk", "dt241_mobile_all.cpk"};
static const char *const native_paths[] = {
    "/Expansion/dt200_mobile_all.cpk", "/Expansion/dt241_mobile_all.cpk"};
static const char *const loose_paths[] = {
    "./LooseCpk/dt200_mobile_all.cpk", "./LooseCpk/dt241_mobile_all.cpk"};
static int enabled;

int pes_loose_cpk_init(const char *build_id,
                      int (*hash_file)(const char *, unsigned char[32]),
                      char *error, size_t error_size) {
  enabled = 0;
  FILE *manifest = fopen("LooseCpk/manifest.txt", "rb");
  if (!manifest) {
    if (errno == ENOENT) return 0;
    snprintf(error, error_size, "Cannot read LooseCpk/manifest.txt");
    return -1;
  }
  char line[256], magic[32], id[17], extra;
  unsigned long long parent_size = 0;
  struct stat st;
  const char *failure = "Invalid manifest header/build ID";
  if (!build_id || !hash_file || !fgets(line, sizeof(line), manifest) ||
      sscanf(line, "%31s %16s %llu %c", magic, id, &parent_size, &extra) != 3 ||
      strcmp(magic, "PESNX_LOOSE_CPK_V1") || strcmp(id, build_id))
    goto fail;
  failure = "Wrong base OBB for loose CPK package";
  if (stat("patch.305030001.jp.nyan2021.pesam.obb", &st) ||
      !S_ISREG(st.st_mode) || (unsigned long long)st.st_size != parent_size)
    goto fail;
  for (unsigned i = 0; i < 2; ++i) {
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
    if (!signature_ok || !hash_file(loose_paths[i], digest)) goto fail;
    for (unsigned j = 0; j < 32; ++j)
      snprintf(actual_hex + j * 2, 3, "%02x", digest[j]);
    if (strcmp(hex, actual_hex)) goto fail;
  }
  failure = "Unexpected data after manifest entries";
  for (int ch; (ch = fgetc(manifest)) != EOF; )
    if (ch != ' ' && ch != '\t' && ch != '\n' && ch != '\r') goto fail;
  if (ferror(manifest)) goto fail;
  fclose(manifest);
  enabled = 1;
  return 1;
fail:
  snprintf(error, error_size, "Loose CPK validation failed: %s", failure);
  fclose(manifest);
  return -1;
}

const char *pes_loose_cpk_path(const char *path) {
  if (enabled && path)
    for (unsigned i = 0; i < 2; ++i)
      if (!strcmp(path, native_paths[i])) return loose_paths[i];
  return NULL;
}
