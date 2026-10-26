/* Native first-leg storage is previous-leg HOME/AWAY. The frontend provides
 * scores ordered as the current match's teams. The original native HUD and
 * match logic reverse the stored pair once when adding current-leg goals. */
#ifndef PESNX_SCOREBOARD_AGGREGATE_POLICY_H
#define PESNX_SCOREBOARD_AGGREGATE_POLICY_H
#include <stdint.h>
typedef struct { uint8_t previous_home, previous_away; } NxNativeFirstLegScore;
static inline NxNativeFirstLegScore nx_native_first_leg_score(uint32_t leg,
    uint8_t current_home_first, uint8_t current_away_first) {
  return leg==2u ? (NxNativeFirstLegScore){current_away_first,current_home_first} :
      (NxNativeFirstLegScore){0,0};
}
#endif
