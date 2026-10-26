/* Manager account data is separate from the immutable v1 match archive and
 * every native/career save. The full catalog digest binds BaseId, native bytes
 * and the explicit portrait policy. Credentials never enter this record. */
#define MD_PROFILE_FILE "SaveData/manager-league-profile-v2.dat"
enum { MD_COLLECTION = 128, MD_REGISTERED = 25, MD_PACKS = 3 };
typedef struct {
  uint32_t magic, version, bytes, checksum, seed, club, balance, tutorials, has_current_plan,
      roster_locked;
  GameplanPreset current_plan;
  char catalog[65], user_id[32];
  uint32_t clubs[MD_TEAMS], roster[MD_TEAMS][MD_REGISTERED], counts[MD_TEAMS];
  uint32_t match_roster[MD_TEAMS][18];
  uint32_t collection[MD_COLLECTION], collection_count, receipts;
  uint32_t receipt_players[MD_PACKS][5];
} MdProfile;
static MdProfile profile;
static const MlCatalogPlayer *squad[MD_TEAMS][MD_REGISTERED], *match_squad[MD_TEAMS][18],
    *collection[MD_COLLECTION];
static uint32_t collection_choice;
static uint32_t profile_ready, profile_blocked, profile_recovered, roster_lock_pending, editor,
    restore_pending, tutorial;
static char password[64];
static const uint32_t pack_draws[3] = {2, 4, 5}, pack_pools[3] = {5, 6, 8};
/* Local offer fixtures. Production prices and availability come from the API. */
static const uint32_t pack_prices[3] = {1000, 2200, 3000};
static const uint32_t pack_clubs[3] = {108, 109, 100};
static uint32_t pack_choice, pack_selected;
static uint64_t pack_opened_at;
static uint32_t profile_hash(const MdProfile *p) {
  MdProfile c = *p;
  c.checksum = 0;
  const unsigned char *b = (const unsigned char *)&c;
  uint32_t h = 2166136261u;
  for (size_t i = 0; i < sizeof(c); i++)
    h = (h ^ b[i]) * 16777619u;
  return h;
}
static int profile_scope(const MdProfile *p, ManagerLeaguePlanScope *out) {
  if (!p || !out || p->counts[0] < 18 || p->counts[0] > MD_REGISTERED ||
      strlen(ml_catalog_pair_id()) != 16 || strlen(ml_catalog_manager_binding_id()) != 64)
    return 0;
  memset(out, 0, sizeof(*out));
  out->account = ((uint64_t)p->seed << 32) | 0x4d4c0001u;
  out->team_id = p->clubs[0];
  out->player_count = p->counts[0];
  memcpy(out->runtime_id, ml_catalog_pair_id(), 16);
  memcpy(out->content_hash, ml_catalog_manager_binding_id(), 64);
  for (uint32_t n = 0; n < out->player_count; n++) {
    const MlCatalogPlayer *player = ml_catalog_find_identity(p->roster[0][n]);
    if (!player)
      return 0;
    out->players[n] = player->native_id;
    out->positions[n] = player->position;
  }
  return manager_league_plan_scope_valid(out);
}
static int profile_valid(const MdProfile *p) {
  if (p->magic != 0x4d4c5032u || p->version != 2 || p->bytes != sizeof(*p) ||
      p->checksum != profile_hash(p) || p->seed != md.seed || p->club != md.club ||
      p->catalog[64] || strcmp(p->catalog, ml_catalog_manager_binding_id()) ||
      !memchr(p->user_id, 0, sizeof(p->user_id)) || p->collection_count > MD_COLLECTION ||
      p->tutorials > 7 || p->receipts > 7 || p->has_current_plan > 1 || p->roster_locked > 1)
    return 0;
  ManagerLeaguePlanScope scope;
  if (p->has_current_plan &&
      (!profile_scope(p, &scope) || !manager_league_plan_compatible(&scope, &p->current_plan)))
    return 0;
  uint32_t cost = 0;
  for (uint32_t t = 0; t < MD_TEAMS; t++)
    for (uint32_t n = 0; n < 18; n++)
      if (!ml_catalog_find_identity(p->match_roster[t][n]))
        return 0;
  for (uint32_t i = 0; i < 3; i++)
    if (p->receipts & (1u << i))
      cost += pack_prices[i];
  if (cost > md.balance || p->balance != md.balance - cost)
    return 0;
  for (uint32_t i = 0; i < p->collection_count; i++) {
    if (!ml_catalog_find_identity(p->collection[i]))
      return 0;
    for (uint32_t j = 0; j < i; j++)
      if (p->collection[j] == p->collection[i])
        return 0;
  }
  for (uint32_t t = 0; t < MD_TEAMS; t++) {
    if (!exhibition_team_catalog_find(p->clubs[t]) || !ml_catalog_has_team(p->clubs[t]) ||
        p->counts[t] < 18 || p->counts[t] > MD_REGISTERED)
      return 0;
    uint32_t gk = 0;
    for (uint32_t n = 0; n < p->counts[t]; n++) {
      const MlCatalogPlayer *cp = ml_catalog_find_identity(p->roster[t][n]);
      if (!cp)
        return 0;
      if (n < 11 && !cp->position)
        gk++;
      for (uint32_t j = 0; j < n; j++)
        if (p->roster[t][n] == p->roster[t][j])
          return 0;
      if (!t) {
        uint32_t i = 0;
        while (i < p->collection_count && p->collection[i] != cp->identity)
          i++;
        if (i == p->collection_count)
          return 0;
      }
    }
    if (gk != 1)
      return 0;
  }
  for (uint32_t i = 0; i < 3; i++)
    if (p->receipts & (1u << i))
      for (uint32_t n = 0; n < pack_draws[i]; n++) {
        if (!ml_catalog_find_identity(p->receipt_players[i][n]))
          return 0;
        for (uint32_t j = 0; j < n; j++)
          if (p->receipt_players[i][n] == p->receipt_players[i][j])
            return 0;
        uint32_t j = 0;
        while (j < p->collection_count && p->collection[j] != p->receipt_players[i][n])
          j++;
        if (j == p->collection_count)
          return 0;
      }
  return 1;
}
static void profile_cache(void) {
  memset(squad, 0, sizeof(squad));
  for (uint32_t t = 0; t < MD_TEAMS; t++)
    for (uint32_t n = 0; n < profile.counts[t]; n++)
      squad[t][n] = ml_catalog_find_identity(profile.roster[t][n]);
  for (uint32_t t = 0; t < MD_TEAMS; t++)
    for (uint32_t n = 0; n < 18; n++)
      match_squad[t][n] = ml_catalog_find_identity(profile.match_roster[t][n]);
  for (uint32_t n = 0; n < profile.collection_count; n++)
    collection[n] = ml_catalog_find_identity(profile.collection[n]);
}
static int profile_read(const char *path) {
  MdProfile p;
  FILE *f = fopen(path, "rb");
  if (!f)
    return 0;
  int ok = fread(&p, 1, sizeof(p), f) == sizeof(p) && fgetc(f) == EOF;
  fclose(f);
  if (!ok || !profile_valid(&p))
    return 0;
  profile = p;
  profile_ready = 1;
  profile_cache();
  return 1;
}
static int profile_save(void) {
  if (profile_blocked || blocked)
    return 0;
  if (md.joined && now() >= manager_dummy_week(&md, now()).first_kickoff_ms)
    profile.roster_locked = 1;
  if (!profile.roster_locked &&
      (!md.joined || manager_dummy_week(&md, now()).state == MD_PRE_LEAGUE))
    for (uint32_t t = 0; t < MD_TEAMS; t++)
      memcpy(profile.match_roster[t], profile.roster[t], 18 * sizeof(uint32_t));
  profile.magic = 0x4d4c5032u;
  profile.version = 2;
  profile.bytes = sizeof(profile);
  profile.checksum = profile_hash(&profile);
  if (!profile_valid(&profile))
    return 0;
  mkdir("SaveData", 0700);
  FILE *f = fopen(MD_PROFILE_FILE ".tmp", "wb");
  int ok = 0;
  if (f) {
    ok = fwrite(&profile, 1, sizeof(profile), f) == sizeof(profile) && fflush(f) == 0;
    if (fclose(f))
      ok = 0;
  }
  if (!ok)
    return 0;
  if (profile_recovered) {
    FILE *prior = fopen(MD_PROFILE_FILE ".invalid", "rb");
    if (prior) {
      fclose(prior);
      return 0;
    }
    FILE *bad = fopen(MD_PROFILE_FILE, "rb");
    if (bad) {
      fclose(bad);
      if (rename(MD_PROFILE_FILE, MD_PROFILE_FILE ".invalid"))
        return 0;
    }
    if (rename(MD_PROFILE_FILE ".tmp", MD_PROFILE_FILE))
      return 0;
    profile_recovered = 0;
    return 1;
  }
  remove(MD_PROFILE_FILE ".bak");
  if (rename(MD_PROFILE_FILE, MD_PROFILE_FILE ".bak")) {
    f = fopen(MD_PROFILE_FILE, "rb");
    if (f) {
      fclose(f);
      return 0;
    }
  }
  if (rename(MD_PROFILE_FILE ".tmp", MD_PROFILE_FILE)) {
    rename(MD_PROFILE_FILE ".bak", MD_PROFILE_FILE);
    return 0;
  }
  return 1;
}
static uint32_t role_group(uint32_t r) { return !r ? 0 : r <= 3 ? 1 : r <= 8 ? 2 : 3; }
static int profile_create(void) {
  if (strlen(ml_catalog_manager_binding_id()) != 64 || !ml_catalog_has_team(md.club))
    return 0;
  memset(&profile, 0, sizeof(profile));
  profile.seed = md.seed;
  profile.club = md.club;
  profile.balance = md.balance;
  snprintf(profile.catalog, sizeof(profile.catalog), "%s", ml_catalog_manager_binding_id());
  profile.clubs[0] = md.club;
  static const uint32_t rivals[] = {100, 101, 102, 103, 108, 109, 119, 121, 211};
  uint32_t r = 1;
  for (uint32_t i = 0; i < sizeof(rivals) / sizeof(*rivals) && r < 7; i++)
    if (rivals[i] != md.club && ml_catalog_has_team(rivals[i]))
      profile.clubs[r++] = rivals[i];
  for (uint32_t i = 0; i < EXHIBITION_TEAM_CATALOG_COUNT && r < 7; i++) {
    uint32_t c = exhibition_team_catalog[i].team_id, j = 0;
    if (!ml_catalog_has_team(c))
      continue;
    while (j < r && profile.clubs[j] != c)
      j++;
    if (j == r)
      profile.clubs[r++] = c;
  }
  if (r != 7)
    return 0;
  /* Slot order is the native editor's default 4-3-3: one GK in the XI;
   * bench adds the second GK. Counts are 2 GK, 6 DEF, 6 MID, 4 FWD. */
  static const uint8_t groups[18] = {0, 1, 1, 1, 1, 2, 2, 2, 3, 3, 3, 1, 1, 2, 2, 2, 3, 0};
  for (uint32_t t = 0; t < 7; t++) {
    uint32_t s = md.seed ^ (0x9e3779b9u * (t + 1));
    for (uint32_t n = 0; n < 18; n++) {
      const MlCatalogPlayer *chosen = NULL;
      uint32_t eligible = 0;
      for (uint32_t i = 0; i < ml_catalog_player_count(); i++) {
        const MlCatalogPlayer *p = ml_catalog_player_at(i);
        if (!p || !p->identity || p->identity & 0x80000000u || p->overall < 60 || p->overall > 69 ||
            !ml_catalog_has_real_portrait(p->identity) || role_group(p->position) != groups[n])
          continue;
        uint32_t j = 0;
        while (j < n && profile.roster[t][j] != p->identity)
          j++;
        if (j < n)
          continue;
        if ((rng(&s) % (++eligible)) == 0)
          chosen = p;
      }
      if (!chosen)
        return 0;
      profile.roster[t][n] = chosen->identity;
    }
    profile.counts[t] = 18;
  }
  for (uint32_t t = 0; t < MD_TEAMS; t++)
    memcpy(profile.match_roster[t], profile.roster[t], 18 * sizeof(uint32_t));
  profile.collection_count = 18;
  memcpy(profile.collection, profile.roster[0], 18 * sizeof(uint32_t));
  profile_ready = 1;
  profile_cache();
  return 1;
}
static void profile_load(void) {
  if (profile_ready || profile_blocked || !md.club)
    return;
  if (profile_read(MD_PROFILE_FILE))
    return;
  if (profile_read(MD_PROFILE_FILE ".bak")) {
    profile_recovered = 1;
    return;
  }
  FILE *a = fopen(MD_PROFILE_FILE, "rb"), *b = fopen(MD_PROFILE_FILE ".bak", "rb");
  if (a || b) {
    if (a)
      fclose(a);
    if (b)
      fclose(b);
    profile_blocked = 1;
    snprintf(notice, sizeof(notice), "PLAYER PROFILE INCOMPATIBLE - EXISTING FILES PRESERVED");
    return;
  }
  if (!profile_create())
    snprintf(notice, sizeof(notice), "PAIRED PLAYER CATALOG REQUIRED - PROFILE NOT CREATED");
}
static const MlCatalogPlayer *pack_pool[3][8];
static void packs_build(void) {
  memset(pack_pool, 0, sizeof(pack_pool));
  for (uint32_t k = 0; k < 3; k++) {
    uint32_t n = 0;
    for (uint32_t i = 0; i < ml_catalog_player_count() && n < pack_pools[k]; i++) {
      const MlCatalogPlayer *p = ml_catalog_player_at(i);
      if (!p || p->club != pack_clubs[k])
        continue;
      uint32_t j = 0;
      while (j < 18 && profile.collection[j] != p->identity)
        j++;
      if (j < 18)
        continue;
      pack_pool[k][n++] = p;
    }
  }
}
static uint32_t selected_count(void) {
  uint32_t n = 0;
  for (uint32_t i = 0; i < 8; i++)
    n += (pack_selected >> i) & 1u;
  return n;
}
static void pack_open(void) {
  uint32_t k = pack_choice;
  if (profile.receipts & (1u << k)) {
    page = MD_PACK_RESULT;
    focus = 0;
    return;
  }
  if (shop_locked()) {
    snprintf(notice, sizeof(notice), "SHOP CLOSED DURING MATCH DAY");
    return;
  }
  if (!profile_ready || !pack_pool[k][pack_pools[k] - 1]) {
    snprintf(notice, sizeof(notice), "PACK CATALOG UNAVAILABLE");
    return;
  }
  if (profile.balance < pack_prices[k]) {
    snprintf(notice, sizeof(notice), "NOT ENOUGH POINTS");
    return;
  }
  pack_selected = 0;
  pack_opened_at = epoch_now;
  page = MD_PACK_OPENING;
  focus = 0;
  notice[0] = 0;
}
static void pack_confirm(void) {
  const uint32_t k = pack_choice;
  if (shop_locked()) {
    snprintf(notice, sizeof(notice), "SHOP CLOSED DURING MATCH DAY");
    return;
  }
  if (profile.receipts & (1u << k)) {
    page = MD_PACK_RESULT;
    focus = 0;
    return;
  }
  if (!profile_ready || !pack_pool[k][pack_pools[k] - 1] || selected_count() != pack_draws[k] ||
      pack_selected >= (1u << pack_pools[k])) {
    snprintf(notice, sizeof(notice), "COMPLETE YOUR PLAYER SELECTION");
    return;
  }
  if (profile.balance < pack_prices[k]) {
    snprintf(notice, sizeof(notice), "NOT ENOUGH POINTS");
    return;
  }
  if (profile.collection_count + pack_draws[k] > MD_COLLECTION) {
    snprintf(notice, sizeof(notice), "COLLECTION FULL");
    return;
  }
  MdProfile before = profile;
  uint32_t n = 0;
  for (uint32_t i = 0; i < pack_pools[k]; i++)
    if (pack_selected & (1u << i)) {
      uint32_t id = pack_pool[k][i]->identity;
      profile.receipt_players[k][n++] = id;
      profile.collection[profile.collection_count++] = id;
      if (profile.counts[0] < MD_REGISTERED)
        profile.roster[0][profile.counts[0]++] = id;
    }
  profile.has_current_plan = 0;
  memset(&profile.current_plan, 0, sizeof(profile.current_plan));
  profile.balance -= pack_prices[k];
  profile.receipts |= 1u << k;
  if (!profile_save()) {
    profile = before;
    snprintf(notice, sizeof(notice), "PURCHASE NOT SAVED - NO POINTS CHARGED");
    return;
  }
  profile_cache();
  page = MD_PACK_RESULT;
  focus = 0;
  notice[0] = 0;
}
