/* Theme keys are presentation identifiers, never engine competition IDs. */
#ifndef PESNX_SCOREBOARD_THEME_H
#define PESNX_SCOREBOARD_THEME_H
#include <stdint.h>
enum { NX_SCORE_DEFAULT=0, NX_SCORE_CUP=1000, NX_SCORE_LEAGUE=1001,
       NX_SCORE_CONTINENTAL=1002 };
static inline uint32_t nx_score_key(int cup, uint32_t id) {
  return id ? id : (cup ? NX_SCORE_CUP : NX_SCORE_LEAGUE);
}
#endif
