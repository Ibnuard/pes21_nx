#ifndef PESNX_MATCH_PREFERENCES_H
#define PESNX_MATCH_PREFERENCES_H
#include <stdint.h>
/* Each UI enum appends RANDOM after its concrete native choices. Native
 * snapshots always receive a resolved concrete value, never this sentinel. */
enum {NX_TIME_RANDOM=2,NX_SEASON_RANDOM=2,NX_WEATHER_RANDOM=3};
static inline uint32_t nx_preference_next(uint32_t choice,uint32_t count,int direction) {
  if(choice>count)choice=count;
  return direction<0 ? (choice ? choice-1u : count) : (choice+1u)%(count+1u);
}
static inline uint32_t nx_preference_resolve(uint32_t choice,uint32_t count,uint32_t *seed) {
  if(choice<count)return choice;
  /* Rejection avoids modulo bias for the three weather variants. */
  uint32_t value,limit=(uint32_t)(-count)%count;
  do {*seed=*seed*1664525u+1013904223u;value=*seed;}while(value<limit);
  return value%count;
}
static inline const char *nx_time_preference_label(uint32_t choice) {
  return choice==0 ? "DAY" : choice==1 ? "NIGHT" : "RANDOM";
}
static inline const char *nx_season_preference_label(uint32_t choice) {
  return choice==0 ? "SUMMER" : choice==1 ? "WINTER" : "RANDOM";
}
#endif
