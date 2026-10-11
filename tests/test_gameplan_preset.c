#include "gameplan_preset.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

int main(void) {
  GameplanPreset preset = {0}, loaded = {0};
  preset.team_id = 108u;
  preset.player_count = 11u;
  preset.tactics = 1u;
  for (uint32_t i = 0; i < 11u; ++i) {
    preset.players[i].player_id[0] = (uint8_t)(i + 1u);
    preset.players[i].order_no = (uint8_t)i;
  }
  preset.formation[0][0] = 12u;
  preset.settings[50] = 1u;
  assert(gameplan_preset_valid(&preset));
  assert(!gameplan_preset_read(108u, 0u, &loaded));
  assert(gameplan_preset_write(108u, 0u, &preset));
  assert(gameplan_preset_read(108u, 0u, &loaded));
  assert(memcmp(&preset, &loaded, sizeof(preset)) == 0);
  assert(!gameplan_preset_read(108u, 1u, &loaded));
  assert(!gameplan_preset_read(100u, 0u, &loaded));

  preset.formation[0][0] = 24u;
  assert(gameplan_preset_write(108u, 0u, &preset));
  assert(gameplan_preset_read(108u, 0u, &loaded));
  assert(loaded.formation[0][0] == 24u);
  /* A corrupt newest copy must fall back to the previous complete copy. */
  FILE *stream = fopen("SaveData/footballnx_plan_108_1_b.bin", "r+b");
  assert(stream);
  assert(fputc(0, stream) != EOF);
  assert(fclose(stream) == 0);
  assert(gameplan_preset_read(108u, 0u, &loaded));
  assert(loaded.formation[0][0] == 12u);

  assert(gameplan_preset_write(108u, 2u, &preset));
  assert(gameplan_preset_read(108u, 2u, &loaded));
  assert(loaded.formation[0][0] == 24u);
  assert(!gameplan_preset_write(108u, 3u, &preset));
  uint32_t canonical=99;
  assert(gameplan_preset_slot_present(108u,0u));
  assert(gameplan_preset_read_scoped(108u,0u,&loaded,"0123456789abcdef",&canonical) && !canonical);
  assert(!gameplan_preset_slot_present(108u,1u));
  assert(gameplan_preset_write_scoped(108u,1u,&preset,"0123456789abcdef"));
  assert(gameplan_preset_read_scoped(108u,1u,&loaded,"0123456789abcdef",&canonical) && canonical);
  assert(!memcmp(&preset,&loaded,sizeof(preset)));
  assert(!gameplan_preset_read_scoped(108u,1u,&loaded,"fedcba9876543210",&canonical));
  assert(gameplan_preset_slot_present(108u,1u)); // foreign/corrupt slots still require overwrite confirmation
  assert(!gameplan_preset_read(108u,1u,&loaded));
  preset.formation[0][0]=31u;
  assert(gameplan_preset_write_scoped(108u,1u,&preset,"0123456789abcdef"));
  stream=fopen("SaveData/footballnx_plan_108_2_b.bin","r+b");assert(stream);
  assert(fputc(0,stream)!=EOF && !fclose(stream));
  assert(gameplan_preset_read_scoped(108u,1u,&loaded,"0123456789abcdef",&canonical) && canonical);
  assert(loaded.formation[0][0]==24u);
  preset.players[1].order_no = 0u;
  assert(!gameplan_preset_valid(&preset));
  assert(!gameplan_preset_write(108u, 1u, &preset));
  return 0;
}
