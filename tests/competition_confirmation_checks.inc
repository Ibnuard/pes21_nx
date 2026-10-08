/* Shared checks run only in the frontend tests' isolated temporary SaveData. */
#include <stdio.h>
#include "cup_save.h"
#include "league_save.h"

static uint32_t confirmation_file_hash(const char *path) {
  FILE *f=fopen(path,"rb");if(!f)return 0u;
  uint32_t hash=2166136261u;int c;
  while((c=fgetc(f))!=EOF)hash=(hash^(uint8_t)c)*16777619u;
  assert(fclose(f)==0);return hash;
}

static void check_save_confirmations(int cup) {
  const CompetitionFrontendState hub=cup ? COMPETITION_FRONTEND_CUP_BRACKET : COMPETITION_FRONTEND_LEAGUE_HUB;
  const CompetitionFrontendState slots=cup ? COMPETITION_FRONTEND_CUP_SLOTS : COMPETITION_FRONTEND_LEAGUE_SLOTS;
  char path_a[80],path_b[80],corrupt[80];
  snprintf(path_a,sizeof(path_a),"SaveData/footballnx_%s_1_a.bin",cup ? "cup" : "league");
  snprintf(path_b,sizeof(path_b),"SaveData/footballnx_%s_1_b.bin",cup ? "cup" : "league");
  snprintf(corrupt,sizeof(corrupt),"SaveData/footballnx_%s_2_b.bin",cup ? "cup" : "league");
  const uint32_t old_a=confirmation_file_hash(path_a),old_b=confirmation_file_hash(path_b);
  assert(old_a && !old_b);
  assert(competition_frontend_state()==hub && competition_frontend_focus()==3u);
  press(BUTTON_A);assert(competition_frontend_state()==slots);
  competition_frontend_pad_event(BUTTON_A,0u);
  for(int i=0;i<20;i++)competition_frontend_pad_event(BUTTON_A,0u);
  assert(competition_frontend_confirmation_active() && competition_frontend_confirmation_focus()==1u);
  assert(strstr(competition_frontend_confirmation_title(),"SLOT 1"));
  competition_frontend_pad_event(0u,0u);
  press(BUTTON_X|BUTTON_Y|BUTTON_UP|BUTTON_DOWN|BUTTON_L|BUTTON_R);
  assert(competition_frontend_focus()==0u && competition_frontend_confirmation_focus()==1u);
  press(BUTTON_A); /* Default Cancel. */
  assert(!competition_frontend_confirmation_active() && competition_frontend_state()==slots);
  press(BUTTON_A);press(BUTTON_LEFT|BUTTON_A);
  assert(competition_frontend_confirmation_active() && !competition_frontend_confirmation_focus());
  assert(confirmation_file_hash(path_a)==old_a && confirmation_file_hash(path_b)==old_b);
  press(BUTTON_B|BUTTON_A); /* B wins over accepting the selected Overwrite. */
  assert(!competition_frontend_confirmation_active());
  assert(confirmation_file_hash(path_a)==old_a && confirmation_file_hash(path_b)==old_b);
  press(BUTTON_A);press(BUTTON_LEFT);press(BUTTON_A);
  assert(competition_frontend_state()==hub && !competition_frontend_confirmation_active());
  assert(confirmation_file_hash(path_a)==old_a && confirmation_file_hash(path_b)!=old_b);

  /* A corrupt B-only copy is occupied, not an empty slot. Cancel preserves bytes. */
  FILE *f=fopen(corrupt,"wb");assert(f);assert(fputs("unreadable user save",f)>=0);assert(!fclose(f));
  assert(cup ? cup_save_slot_exists(1u) : league_save_slot_exists(1u));
  const uint32_t bad_hash=confirmation_file_hash(corrupt);
  press(BUTTON_A);press(BUTTON_DOWN);
  assert(!strcmp(competition_frontend_item_value(1u),"UNREADABLE DATA"));
  press(BUTTON_A);assert(competition_frontend_confirmation_active());
  assert(strstr(competition_frontend_confirmation_title(),"SLOT 2"));
  press(BUTTON_B);assert(confirmation_file_hash(corrupt)==bad_hash);
  press(BUTTON_B);assert(competition_frontend_state()==hub);
  assert(remove(corrupt)==0); /* Only our synthetic test fixture. */

  press(BUTTON_B);assert(competition_frontend_confirmation_active());
  assert(competition_frontend_confirmation_focus()==1u && !competition_frontend_closing());
  assert(!strcmp(competition_frontend_confirmation_accept(),"LEAVE"));
  const uint32_t news=cup ? competition_frontend_cup_news_index() : competition_frontend_league_news_index();
  for(uint64_t ms=100u;ms<13000u;ms+=100u)competition_frontend_tick(ms);
  assert(news==(cup ? competition_frontend_cup_news_index() : competition_frontend_league_news_index()));
  press(BUTTON_A);assert(competition_frontend_state()==hub && !competition_frontend_closing());
  press(BUTTON_B);press(BUTTON_LEFT);press(BUTTON_B);
  assert(competition_frontend_state()==hub && !competition_frontend_closing());
}
