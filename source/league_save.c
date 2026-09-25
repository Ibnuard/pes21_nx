#include "league_save.h"

#include <errno.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#ifdef _WIN32
#include <direct.h>
#endif

#define LEAGUE_SAVE_MAGIC 0x314c5846u /* FXL1 */
#define LEAGUE_SAVE_VERSION 2u

typedef struct {
  uint32_t magic, version, payload_size, sequence, checksum;
} LeagueSaveHeader;

typedef struct {
  uint32_t sequence;
  LeagueSaveState state;
} LeagueSaveCopy;

static void league_save_path(uint32_t slot, uint32_t copy, char path[64]) {
  snprintf(path, 64, "SaveData/footballnx_league_%u_%c.bin",
           slot + 1u, copy ? 'b' : 'a');
}

static uint32_t league_save_checksum(const void *payload, size_t size) {
  const uint8_t *bytes = (const uint8_t *)payload;
  uint32_t hash = 2166136261u;
  for (size_t i = 0; i < size; i++) {
    hash ^= bytes[i];
    hash *= 16777619u;
  }
  return hash;
}

static int league_save_read_copy(uint32_t slot, uint32_t copy,
                                  LeagueSaveCopy *out) {
  char path[64];
  league_save_path(slot, copy, path);
  FILE *stream = fopen(path, "rb");
  if (!stream) return 0;
  LeagueSaveHeader header;
  const size_t old_size = offsetof(LeagueSaveState, tournament) +
      offsetof(LeagueTournament, scorer_count);
  const int read_header = fread(&header, 1, sizeof(header), stream) ==
      sizeof(header);
  const size_t payload_size = read_header && header.version == 1u
      ? old_size : sizeof(LeagueSaveState);
  const int valid_header = read_header &&
      header.magic == LEAGUE_SAVE_MAGIC &&
      (header.version == 1u || header.version == LEAGUE_SAVE_VERSION) &&
      header.payload_size == payload_size;
  if (!valid_header) {
    fclose(stream);
    return 0;
  }
  memset(&out->state, 0, sizeof(out->state));
  const int read = fread(&out->state, 1, payload_size, stream) == payload_size;
  const int end = fgetc(stream) == EOF;
  const int closed = fclose(stream) == 0;
  if (!read || !end || !closed || header.checksum !=
      league_save_checksum(&out->state, payload_size)) return 0;
  out->sequence = header.sequence;
  return 1;
}

int league_save_read(uint32_t slot, LeagueSaveState *state) {
  if (slot >= LEAGUE_SAVE_SLOTS || !state) return 0;
  static LeagueSaveCopy first, second;
  const int a = league_save_read_copy(slot, 0u, &first);
  const int b = league_save_read_copy(slot, 1u, &second);
  if (!a && !b) return 0;
  *state = !a ? second.state : !b || first.sequence >= second.sequence
               ? first.state : second.state;
  return 1;
}

int league_save_write(uint32_t slot, const LeagueSaveState *state) {
  if (slot >= LEAGUE_SAVE_SLOTS || !state) return 0;
#ifdef _WIN32
  if (_mkdir("SaveData") != 0 && errno != EEXIST) return 0;
#else
  if (mkdir("SaveData", 0777) != 0 && errno != EEXIST) return 0;
#endif
  static LeagueSaveCopy first, second;
  const int a = league_save_read_copy(slot, 0u, &first);
  const int b = league_save_read_copy(slot, 1u, &second);
  const uint32_t latest = a && (!b || first.sequence >= second.sequence)
                              ? first.sequence : b ? second.sequence : 0u;
  const uint32_t target = !a ? 0u : !b ? 1u
                          : first.sequence <= second.sequence ? 0u : 1u;
  LeagueSaveHeader header = {LEAGUE_SAVE_MAGIC, LEAGUE_SAVE_VERSION,
                             sizeof(*state), latest + 1u,
                             league_save_checksum(state, sizeof(*state))};
  char path[64];
  league_save_path(slot, target, path);
  FILE *stream = fopen(path, "wb");
  if (!stream) return 0;
  const int written = fwrite(&header, 1, sizeof(header), stream) ==
                          sizeof(header) &&
                      fwrite(state, 1, sizeof(*state), stream) ==
                          sizeof(*state);
  const int flushed = fflush(stream) == 0;
  const int closed = fclose(stream) == 0;
  static LeagueSaveCopy verify;
  return written && flushed && closed &&
         league_save_read_copy(slot, target, &verify) &&
         verify.sequence == header.sequence;
}
