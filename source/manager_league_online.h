#ifndef PESNX_MANAGER_LEAGUE_ONLINE_H
#define PESNX_MANAGER_LEAGUE_ONLINE_H
#include "manager_league_dummy.h"
void manager_online_open(void);
void manager_online_close(void);
void manager_online_tick(uint64_t monotonic_ms);
void manager_online_pad(uint32_t pressed);
void manager_online_sample(uint32_t buttons,uint32_t pressed,int32_t ax,int32_t ay);
void manager_online_view(MdView *out);
uint32_t manager_online_take_action(void);
const char *manager_online_name(void);
const char *manager_online_input_label(void);
int manager_online_input_promotion(void);
void manager_online_name_result(const char *text);
void manager_online_audio_frame(ManagerLeagueAudioFrame *out,uint64_t monotonic_ms);
#endif
