#ifndef PES21_GAMEPLAN_PRESET_H
#define PES21_GAMEPLAN_PRESET_H

#include <stdint.h>

#define GAMEPLAN_PRESET_SLOTS 3u
#define GAMEPLAN_PRESET_MAX_PLAYERS 40u

typedef struct {
  uint8_t player_id[16];
  uint8_t order_no;
  uint8_t reserved[3];
} GameplanPresetPlayer;

typedef struct {
  uint32_t team_id;
  uint32_t player_count;
  uint32_t tactics;
  GameplanPresetPlayer players[GAMEPLAN_PRESET_MAX_PLAYERS];
  uint8_t formation[2][144];
  uint8_t settings[52];
} GameplanPreset;

int gameplan_preset_read(uint32_t team_id, uint32_t slot,
                         GameplanPreset *out);
int gameplan_preset_write(uint32_t team_id, uint32_t slot,
                          const GameplanPreset *preset);
int gameplan_preset_valid(const GameplanPreset *preset);

#endif
