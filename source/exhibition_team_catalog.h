/* Generated data API for the custom Exhibition team selector. */

#ifndef PES21_EXHIBITION_TEAM_CATALOG_H
#define PES21_EXHIBITION_TEAM_CATALOG_H

#include <stddef.h>
#include <stdint.h>

typedef struct {
  const char *label;
  const char *icon;
  const uint32_t *teams;
  uint32_t team_count;
  uint32_t badge_slot;
} ExhibitionTeamCategory;

typedef struct {
  uint32_t team_id;
  const char *display_name;
  uint32_t badge_slot;
} ExhibitionTeamCatalogEntry;

#include "exhibition_teams_generated.inc"

#define EXHIBITION_TEAM_CATEGORY_COUNT                                    \
  ((uint32_t)(sizeof(exhibition_team_categories) /                         \
              sizeof(exhibition_team_categories[0])))
#define EXHIBITION_TEAM_CATALOG_COUNT                                     \
  ((uint32_t)(sizeof(exhibition_team_catalog) /                            \
              sizeof(exhibition_team_catalog[0])))

static inline const ExhibitionTeamCatalogEntry *
exhibition_team_catalog_find(uint32_t team_id) {
  uint32_t low = 0;
  uint32_t high = EXHIBITION_TEAM_CATALOG_COUNT;
  while (low < high) {
    const uint32_t middle = low + (high - low) / 2u;
    const uint32_t candidate = exhibition_team_catalog[middle].team_id;
    if (candidate < team_id)
      low = middle + 1u;
    else
      high = middle;
  }
  return low < EXHIBITION_TEAM_CATALOG_COUNT &&
                 exhibition_team_catalog[low].team_id == team_id
             ? &exhibition_team_catalog[low]
             : NULL;
}

static inline const char *exhibition_team_catalog_name(uint32_t team_id) {
  const ExhibitionTeamCatalogEntry *entry =
      exhibition_team_catalog_find(team_id);
  return entry ? entry->display_name : "";
}

static inline uint32_t exhibition_team_catalog_badge(uint32_t team_id) {
  const ExhibitionTeamCatalogEntry *entry =
      exhibition_team_catalog_find(team_id);
  return entry ? entry->badge_slot : 0u;
}

static inline uint32_t exhibition_team_catalog_first_id(void) {
  return EXHIBITION_TEAM_CATEGORY_COUNT &&
                 exhibition_team_categories[0].team_count
             ? exhibition_team_categories[0].teams[0]
             : 0u;
}

static inline uint32_t
exhibition_team_catalog_first_other_id(uint32_t team_id) {
  for (uint32_t category_index = 0;
       category_index < EXHIBITION_TEAM_CATEGORY_COUNT; category_index++) {
    const ExhibitionTeamCategory *category =
        &exhibition_team_categories[category_index];
    for (uint32_t team_index = 0; team_index < category->team_count;
         team_index++) {
      if (category->teams[team_index] != team_id)
        return category->teams[team_index];
    }
  }
  return team_id;
}

#endif
