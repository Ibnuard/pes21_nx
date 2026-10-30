#ifndef FNX_MANAGER_CLUB_PICKER_H
#define FNX_MANAGER_CLUB_PICKER_H
#include <string.h>
#include "exhibition_team_catalog.h"

/* The paired selector groups national teams under NATIONAL <region>.
 * Filter that catalog's membership; native team numbers are not a type. */
static inline int manager_club_category(uint32_t index) {
  return index < EXHIBITION_TEAM_CATEGORY_COUNT &&
      exhibition_team_categories[index].team_count &&
      strncmp(exhibition_team_categories[index].label, "NATIONAL ", 9);
}
static inline uint32_t manager_club_category_count(void) {
  uint32_t n=0;
  for(uint32_t i=0;i<EXHIBITION_TEAM_CATEGORY_COUNT;i++)n+=!!manager_club_category(i);
  return n;
}
static inline uint32_t manager_club_category_at(uint32_t ordinal) {
  for(uint32_t i=0;i<EXHIBITION_TEAM_CATEGORY_COUNT;i++)
    if(manager_club_category(i) && !ordinal--)return i;
  return EXHIBITION_TEAM_CATEGORY_COUNT;
}
static inline uint32_t manager_club_category_ordinal(uint32_t index) {
  uint32_t n=0;
  for(uint32_t i=0;i<index && i<EXHIBITION_TEAM_CATEGORY_COUNT;i++)n+=!!manager_club_category(i);
  return n;
}
static inline int manager_club_team_allowed(uint32_t team) {
  for(uint32_t i=0;i<EXHIBITION_TEAM_CATEGORY_COUNT;i++)if(manager_club_category(i)) {
    const ExhibitionTeamCategory *c=&exhibition_team_categories[i];
    for(uint32_t j=0;j<c->team_count;j++)if(c->teams[j]==team)return 1;
  }
  return 0;
}
#endif
