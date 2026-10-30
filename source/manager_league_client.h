#ifndef PESNX_MANAGER_LEAGUE_CLIENT_H
#define PESNX_MANAGER_LEAGUE_CLIENT_H
#include "manager_league_dummy.h"
void manager_client_open(int offline_dev);
void manager_client_close(void);
int manager_client_online(void);
void manager_client_tick(uint64_t ms);
void manager_client_pad(uint32_t pressed);
void manager_client_sample(uint32_t buttons,uint32_t pressed,int32_t ax,int32_t ay);
void manager_client_view(MdView *out);
uint32_t manager_client_take_action(void);
const char *manager_client_name(void);
const char *manager_client_input_label(void);
int manager_client_input_password(void);
int manager_client_input_promotion(void);
void manager_client_name_result(const char *text);
void manager_client_audio_frame(ManagerLeagueAudioFrame *out,uint64_t ms);
#endif
