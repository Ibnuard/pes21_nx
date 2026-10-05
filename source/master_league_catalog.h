#ifndef PES21_MASTER_LEAGUE_CATALOG_H
#define PES21_MASTER_LEAGUE_CATALOG_H
#include "master_league.h"
const char *ml_catalog_content_id(void);
const char *ml_catalog_pair_id(void);
int ml_catalog_import(MasterLeague *career);
int ml_catalog_has_team(uint32_t team);
#endif
