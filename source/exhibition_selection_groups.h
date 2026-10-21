/* Menu-only grouping. Canonical competition rosters and identities stay intact. */
#ifndef PESNX_EXHIBITION_SELECTION_GROUPS_H
#define PESNX_EXHIBITION_SELECTION_GROUPS_H
#include <string.h>
#include "exhibition_team_catalog.h"

static uint32_t exhibition_selection_merged_teams[EXHIBITION_TEAM_CATALOG_COUNT];
static ExhibitionTeamCategory exhibition_selection_merged;
static uint32_t exhibition_selection_asia = UINT32_MAX;
static uint32_t exhibition_selection_america = UINT32_MAX;
static uint32_t exhibition_selection_grouping_ready;

/* Called during hook installation, before any menu renderer or input owner. */
static void exhibition_selection_groups_init(void) {
  if (exhibition_selection_grouping_ready) return;
  for (uint32_t i = 0; i < EXHIBITION_TEAM_CATEGORY_COUNT; ++i) {
    const char *name = exhibition_team_categories[i].label;
    if (!strcmp(name,"OTHER ASIA CLUBS") || !strcmp(name,"OTHER ASIAN CLUBS"))
      exhibition_selection_asia = i;
    if (!strcmp(name,"N AMERICA CLUBS") || !strcmp(name,"MLS") ||
        !strcmp(name,"MAJOR LEAGUE SOCCER")) exhibition_selection_america = i;
  }
  if (exhibition_selection_asia == UINT32_MAX ||
      exhibition_selection_america == UINT32_MAX) return;
  exhibition_selection_merged = exhibition_team_categories[exhibition_selection_asia];
  exhibition_selection_merged.label = "Other Asia & American Clubs";
  exhibition_selection_merged.teams = exhibition_selection_merged_teams;
  exhibition_selection_merged.team_count = 0;
  const uint32_t groups[2] = {exhibition_selection_asia,exhibition_selection_america};
  for (uint32_t g = 0; g < 2; ++g) {
    const ExhibitionTeamCategory *category = &exhibition_team_categories[groups[g]];
    for (uint32_t n = 0; n < category->team_count; ++n) {
      const uint32_t id = category->teams[n];
      uint32_t j = 0;
      while (j < exhibition_selection_merged.team_count && exhibition_selection_merged_teams[j] != id) ++j;
      if (j == exhibition_selection_merged.team_count && j < EXHIBITION_TEAM_CATALOG_COUNT)
        exhibition_selection_merged_teams[exhibition_selection_merged.team_count++] = id;
    }
  }
  exhibition_selection_grouping_ready = 1;
}
static uint32_t exhibition_selection_group_count(void) {
  return EXHIBITION_TEAM_CATEGORY_COUNT - (exhibition_selection_grouping_ready ? 1u : 0u);
}
static const ExhibitionTeamCategory *exhibition_selection_group_at(uint32_t index) {
  if (!exhibition_selection_grouping_ready)
    return index < EXHIBITION_TEAM_CATEGORY_COUNT ? &exhibition_team_categories[index] : NULL;
  for (uint32_t i = 0, visible = 0; i < EXHIBITION_TEAM_CATEGORY_COUNT; ++i) {
    if (i == exhibition_selection_america) continue;
    if (visible++ == index) return i == exhibition_selection_asia
        ? &exhibition_selection_merged : &exhibition_team_categories[i];
  }
  return NULL;
}
#endif
