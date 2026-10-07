#ifndef PES21_MASTER_LEAGUE_H
#define PES21_MASTER_LEAGUE_H

#include <stdint.h>
#include "league_tournament.h"
#include "gameplan_preset.h"

#define ML_MAX_CLUBS 384u
#define ML_MAX_PLAYERS (ML_MAX_CLUBS * 40u)
#define ML_SQUAD_SIZE 40u
#define ML_SAVE_SLOTS 3u
#define ML_NAME_SIZE 32u
#define ML_CONTENT_ID_SIZE 65u
#define ML_INVALID_INDEX UINT32_MAX
#define ML_PLAYER_RELEASE_PAID 1u /* bit in MlPlayer.reserved; preserved in v4 saves */

/* identity is BaseId, or the existing disjoint FL26 provenance namespace.
 * Native IDs are immutable engine storage keys, not ownership or identity. */
typedef struct {
  uint32_t identity, native_id, portrait_id, club;
  uint32_t wage, contract_end;
  uint8_t overall, position, shirt, reserved;
  char name[48];
} MlPlayer;

typedef struct {
  uint32_t team, count;
  uint32_t players[ML_SQUAD_SIZE]; /* indices into the canonical player array */
  int64_t cash;
  uint32_t wage_budget;
} MlClub;

typedef struct {
  uint32_t competition_id, club, difficulty, match_minutes;
  uint32_t condition, injuries, max_substitutions;
  uint32_t cup_id;
} MlSettings;

/* Append-only save extension. Zero preserves the v1 economy and display. */
typedef struct {
  uint32_t transfer_difficulty; /* 0 normal, 1 easy, 2 hard */
  uint32_t currency;            /* 0 EUR, 1 GBP, 2 USD; fixed game units */
  uint32_t skip_first_window;
  uint32_t reserved;
} MlCareerOptions;

#define ML_MAX_OFFERS 32u
#define ML_MAX_MESSAGES 12u
enum { ML_OFFER_WAITING=1, ML_OFFER_ACCEPTED, ML_OFFER_COUNTER,
       ML_OFFER_REJECTED, ML_OFFER_COMPLETED, ML_OFFER_CANCELLED, ML_OFFER_EXPIRED };
enum { ML_NOTICE_WINDOW=1, ML_NOTICE_RESPONSE, ML_NOTICE_WARNING,
       ML_NOTICE_DISMISSED, ML_NOTICE_JOB, ML_NOTICE_TRANSFER };
typedef struct {
  uint32_t id, player, from, to, season, created, due, updated, status;
  uint32_t fee, wage, years, incoming, rounds;
} MlOffer;
typedef struct { uint32_t kind, day, season; char text[96]; } MlNotice;
/* Append-only v3 extension. Zero is the migration default for v1/v2 saves. */
typedef struct {
  uint32_t next_id, milestone_mask, offer_count, notice_count;
  uint32_t losses, negative_since, dismissed, job_team, job_expiry, job_checked;
  MlOffer offers[ML_MAX_OFFERS];
  MlNotice notices[ML_MAX_MESSAGES];
} MlOfficeState;

/* v5 extension. National assignments reference the paired native national
 * rosters; they never duplicate canonical club players or change ownership. */
#define ML_MAX_NATIONAL_OFFERS 4u
typedef struct { uint32_t team, expiry, status, seen; } MlNationalOffer;
typedef struct {
  uint32_t version, continental_id, job_checks;
  CupTournament continental;
  uint32_t national_team, national_count, national_checked;
  MlNationalOffer national_offers[ML_MAX_NATIONAL_OFFERS];
  uint32_t national_region, friendly_mask, finals_started;
  LeagueFixture friendlies[2];
  LeagueTournament qualifiers;
  CupTournament regional, world_cup;
} MlWorldState;

typedef struct {
  uint32_t seed, season, day, transaction_sequence;
  uint32_t club_count, player_count, target_rank, last_rank, seasons_completed;
  uint32_t wage_week, cup_enabled;
  int64_t wages_paid, match_income, prize_income;
  char content_id[ML_CONTENT_ID_SIZE];
  char manager_name[ML_NAME_SIZE];
  uint32_t manager_nationality;
  MlSettings settings;
  MlClub clubs[ML_MAX_CLUBS];
  MlPlayer players[ML_MAX_PLAYERS];
  LeagueTournament league;
  CupTournament cup;
  GameplanPreset current_plan;
  GameplanPreset presets[GAMEPLAN_PRESET_SLOTS];
  _Alignas(8) MlCareerOptions options;
  _Alignas(8) MlOfficeState office;
  /* v4 append-only read receipts, parallel to office.offers. Zero = unseen. */
  _Alignas(8) uint32_t offer_seen[ML_MAX_OFFERS];
  _Alignas(8) MlWorldState world;
} MasterLeague;

typedef enum { ML_EVENT_LEAGUE = 1, ML_EVENT_CUP, ML_EVENT_SEASON_END,
  ML_EVENT_WINDOW, ML_EVENT_RESPONSE, ML_EVENT_BOARD,
  ML_EVENT_CONTINENTAL, ML_EVENT_FRIENDLY, ML_EVENT_QUALIFIER,
  ML_EVENT_REGIONAL, ML_EVENT_WORLD_CUP } MlEventKind;
typedef struct {
  uint32_t kind, day, index, round, home, away;
} MlEvent;

int ml_manager_name_valid(const char *name);
int ml_init(MasterLeague *career, const char *content_id, const MlSettings *settings,
            const char *manager, uint32_t nationality, uint32_t seed);
int ml_add_player(MasterLeague *career, uint32_t club, const MlPlayer *player);
int ml_start_season(MasterLeague *career, const uint32_t *teams, uint32_t count,
                    const uint32_t *cup_teams, uint32_t cup_count);
int ml_valid(const MasterLeague *career);
MlClub *ml_club(MasterLeague *career, uint32_t team);
const MlClub *ml_find_club(const MasterLeague *career, uint32_t team);
const MlPlayer *ml_find_native(const MasterLeague *career, uint32_t native_id);
uint32_t ml_weekly_wage(const MasterLeague *career, uint32_t club);
uint32_t ml_transfer_value(const MlPlayer *player);
uint32_t ml_transfer_fee(const MasterLeague *career, const MlPlayer *player);
uint32_t ml_league_day(const MasterLeague *career, uint32_t matchday);
uint32_t ml_cup_day(const MasterLeague *career, uint32_t round);
int ml_window_open(const MasterLeague *career);
const char *ml_offer_submit(MasterLeague *c, uint32_t player, uint32_t fee,
                           uint32_t wage, uint32_t years, uint32_t offer_id);
const char *ml_offer_accept(MasterLeague *c, uint32_t offer_id);
const char *ml_offer_reject(MasterLeague *c, uint32_t offer_id);
int ml_offer_unread(const MasterLeague *c, uint32_t offer_index);
void ml_offer_mark_read(MasterLeague *c, uint32_t offer_index);
const char *ml_accept_job(MasterLeague *c);
int ml_process_office_event(MasterLeague *c, const MlEvent *event);
const char *ml_event_label(const MasterLeague *c, const MlEvent *event);
uint32_t ml_calendar_transfer(const MasterLeague *c, uint32_t day);
uint32_t ml_weak_position(const MasterLeague *c);
int ml_event_is_match(uint32_t kind);
int ml_event_is_knockout(uint32_t kind);
int ml_event_is_national(uint32_t kind);
uint32_t ml_event_manager_team(const MasterLeague *c, uint32_t kind);
void ml_world_enable(MasterLeague *c);
uint32_t ml_national_offer_status(const MasterLeague *c, uint32_t index);
int ml_national_offer_unread(const MasterLeague *c, uint32_t index);
void ml_national_offer_mark_read(MasterLeague *c, uint32_t index);
const char *ml_accept_national_job(MasterLeague *c, uint32_t index);
const char *ml_reject_national_job(MasterLeague *c, uint32_t index);
const char *ml_world_name(const MasterLeague *c, uint32_t kind);
uint32_t ml_world_day(const MasterLeague *c, uint32_t kind, uint32_t index);
const CupTournament *ml_event_cup(const MasterLeague *c, uint32_t kind);
/* Returns an explanatory message; empty means success. No partial writes. */
const char *ml_transfer(MasterLeague *career, uint32_t player_index,
                        uint32_t destination, uint32_t years);
const char *ml_renew(MasterLeague *career, uint32_t player_index, uint32_t years);
int64_t ml_renew_fee(const MasterLeague *career, uint32_t player_index, uint32_t years);
uint32_t ml_release_value(const MasterLeague *career, uint32_t player_index);
const char *ml_release(MasterLeague *career, uint32_t player_index);
int ml_swap(MasterLeague *career, uint32_t team, uint32_t first, uint32_t second);
int ml_next_event(const MasterLeague *career, MlEvent *event);
int ml_advance_date(MasterLeague *career, const MlEvent *event);
int ml_record_event(MasterLeague *career, const MlEvent *event,
                     uint32_t home_goals, uint32_t away_goals,
                     const LeagueScorer *scorers, uint32_t scorer_count,
                     int simulated);
/* A played cup draw requires the actual shootout winner, never a random pick. */
int ml_record_event_decided(MasterLeague *career, const MlEvent *event,
                     uint32_t home_goals, uint32_t away_goals,
                     const LeagueScorer *scorers, uint32_t scorer_count,
                     int simulated, uint32_t shootout_winner);
int ml_simulate_event(MasterLeague *career, const MlEvent *event);
int ml_next_season(MasterLeague *career);
uint32_t ml_rank(const MasterLeague *career);
int ml_plan_compatible(const MasterLeague *career, const GameplanPreset *plan);
int ml_store_plan(MasterLeague *career, const GameplanPreset *plan);
int ml_save_read(uint32_t slot, const char *content_id, MasterLeague *out);
int ml_save_write(uint32_t slot, const MasterLeague *career);

#endif
