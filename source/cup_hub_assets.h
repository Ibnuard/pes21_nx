#ifndef PES21_CUP_HUB_ASSETS_H
#define PES21_CUP_HUB_ASSETS_H

#include <stdint.h>

/* Project-authored PNGs linked by bin2o. Text and bracket state remain live. */
extern const uint8_t cup_hub_stadium_bin[];
extern const uint8_t cup_hub_stadium_bin_end[];
extern const uint8_t cup_hub_trophy_bin[];
extern const uint8_t cup_hub_trophy_bin_end[];
extern const uint8_t cup_hub_header_ornament_bin[];
extern const uint8_t cup_hub_header_ornament_bin_end[];

extern const uint8_t cup_news_v1_bin[], cup_news_v1_bin_end[];
extern const uint8_t cup_pearl_v1_bin[], cup_pearl_v1_bin_end[];
/* Shared flat action ornaments for Cup and League, rendered at 20% opacity. */
extern const uint8_t competition_actions_v1_bin[], competition_actions_v1_bin_end[];

#endif
