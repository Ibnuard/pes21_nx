#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "league_save.h"

typedef struct {
  uint32_t magic, version, payload_size, sequence, checksum;
} TestHeader;

static uint32_t checksum(const void *payload, size_t size) {
  const uint8_t *bytes = payload;
  uint32_t hash = 2166136261u;
  for (size_t i = 0; i < size; i++) {
    hash ^= bytes[i];
    hash *= 16777619u;
  }
  return hash;
}

int main(void) {
  static LeagueSaveState legacy, loaded;
  legacy.player_count = 1u;
  legacy.team_count = 3u;
  legacy.tournament.team_count = 3u;
  legacy.tournament.standings[0].team = 100u;
  const size_t old_size = offsetof(LeagueSaveState, tournament) +
      offsetof(LeagueTournament, scorer_count);
  const TestHeader header = {0x314c5846u, 1u, (uint32_t)old_size, 4u,
                             checksum(&legacy, old_size)};
  FILE *stream = fopen("SaveData/footballnx_league_1_a.bin", "wb");
  assert(stream);
  assert(fwrite(&header, 1, sizeof(header), stream) == sizeof(header));
  assert(fwrite(&legacy, 1, old_size, stream) == old_size);
  assert(fclose(stream) == 0);
  assert(league_save_read(0u, &loaded));
  assert(loaded.team_count == 3u);
  assert(loaded.tournament.standings[0].team == 100u);
  assert(loaded.tournament.scorer_count == 0u);
  loaded.tournament.scorer_count = 1u;
  loaded.tournament.scorers[0].base_id = 42u;
  loaded.tournament.scorers[0].goals = 3u;
  assert(league_save_write(0u, &loaded));
  memset(&loaded, 0, sizeof(loaded));
  assert(league_save_read(0u, &loaded));
  assert(loaded.tournament.scorer_count == 1u);
  assert(loaded.tournament.scorers[0].base_id == 42u);
  assert(loaded.tournament.scorers[0].goals == 3u);
  puts("league save migration tests passed");
  return 0;
}
