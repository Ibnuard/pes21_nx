#include "cup_save.h"

#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#ifdef _WIN32
#include <direct.h>
#endif

#define CUP_SAVE_MAGIC 0x32584346u /* FCX2 */
#define CUP_SAVE_VERSION 1u

typedef struct {
  uint32_t magic;
  uint32_t version;
  uint32_t payload_size;
  uint32_t sequence;
  uint32_t checksum;
  CupSaveState state;
} CupSaveFile;

static void cup_save_path(uint32_t slot, uint32_t copy, char path[64]) {
  snprintf(path, 64, "SaveData/footballnx_cup_%u_%c.bin",
           slot + 1u, copy ? 'b' : 'a');
}

static uint32_t cup_save_checksum(const CupSaveState *state) {
  const uint8_t *bytes = (const uint8_t *)state;
  uint32_t hash = 2166136261u;
  for (uint32_t i = 0; i < sizeof(*state); i++) {
    hash ^= bytes[i];
    hash *= 16777619u;
  }
  return hash;
}

static int cup_save_read_copy(uint32_t slot, uint32_t copy,
                              CupSaveFile *file) {
  char path[64];
  cup_save_path(slot, copy, path);
  FILE *stream = fopen(path, "rb");
  if (!stream) return 0;
  const int read = fread(file, 1, sizeof(*file), stream) == sizeof(*file);
  const int end = fgetc(stream) == EOF;
  const int closed = fclose(stream) == 0;
  return read && end && closed && file->magic == CUP_SAVE_MAGIC &&
         file->version == CUP_SAVE_VERSION &&
         file->payload_size == sizeof(file->state) &&
         file->checksum == cup_save_checksum(&file->state);
}

int cup_save_read(uint32_t slot, CupSaveState *state) {
  if (slot >= CUP_SAVE_SLOTS || !state) return 0;
  CupSaveFile first, second;
  const int a = cup_save_read_copy(slot, 0u, &first);
  const int b = cup_save_read_copy(slot, 1u, &second);
  if (!a && !b) return 0;
  *state = !a ? second.state : !b || first.sequence >= second.sequence
               ? first.state : second.state;
  return 1;
}

int cup_save_write(uint32_t slot, const CupSaveState *state) {
  if (slot >= CUP_SAVE_SLOTS || !state) return 0;
#ifdef _WIN32
  if (_mkdir("SaveData") != 0 && errno != EEXIST) return 0;
#else
  if (mkdir("SaveData", 0777) != 0 && errno != EEXIST) return 0;
#endif
  CupSaveFile first, second;
  const int a = cup_save_read_copy(slot, 0u, &first);
  const int b = cup_save_read_copy(slot, 1u, &second);
  const uint32_t latest = a && (!b || first.sequence >= second.sequence)
                              ? first.sequence : b ? second.sequence : 0u;
  const uint32_t target = !a ? 0u : !b ? 1u
                          : first.sequence <= second.sequence ? 0u : 1u;
  CupSaveFile file;
  memset(&file, 0, sizeof(file));
  file.magic = CUP_SAVE_MAGIC;
  file.version = CUP_SAVE_VERSION;
  file.payload_size = sizeof(file.state);
  file.sequence = latest + 1u;
  file.state = *state;
  file.checksum = cup_save_checksum(&file.state);
  char path[64];
  cup_save_path(slot, target, path);
  FILE *stream = fopen(path, "wb");
  if (!stream) return 0;
  const int written = fwrite(&file, 1, sizeof(file), stream) == sizeof(file);
  const int flushed = fflush(stream) == 0;
  const int closed = fclose(stream) == 0;
  CupSaveFile verify;
  return written && flushed && closed &&
         cup_save_read_copy(slot, target, &verify) &&
         verify.sequence == file.sequence;
}
