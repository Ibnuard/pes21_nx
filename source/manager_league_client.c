#include "manager_league_client.h"
#include "manager_league_online.h"
#include <stdio.h>
static int online;
void manager_client_open(int dev){
  manager_online_close();online=!dev;
  if(online)manager_online_open();else manager_dummy_open();
}
void manager_client_close(void){if(online)manager_online_close();}
int manager_client_online(void){return online;}
void manager_client_tick(uint64_t ms){if(online)manager_online_tick(ms);else manager_dummy_tick(ms);}
void manager_client_pad(uint32_t key){if(online)manager_online_pad(key);else manager_dummy_pad(key);}
void manager_client_sample(uint32_t buttons,uint32_t pressed,int32_t ax,int32_t ay){if(online)manager_online_sample(buttons,pressed,ax,ay);else manager_dummy_pad(pressed);}
void manager_client_view(MdView *out){
  if(online)manager_online_view(out);
  else {
    manager_dummy_view(out);
    char caption[sizeof(out->caption)];snprintf(caption,sizeof(caption),"DEV OFFLINE - %.77s",out->caption[0]?out->caption:out->subtitle);
    snprintf(out->caption,sizeof(out->caption),"%s",caption);
  }
}
uint32_t manager_client_take_action(void){return online?manager_online_take_action():manager_dummy_take_action();}
const char *manager_client_name(void){return online?manager_online_name():manager_dummy_name();}
const char *manager_client_input_label(void){return online?manager_online_input_label():manager_dummy_input_label();}
int manager_client_input_password(void){return online?0:manager_dummy_input_password();}
int manager_client_input_promotion(void){return online&&manager_online_input_promotion();}
void manager_client_name_result(const char *text){if(online)manager_online_name_result(text);else manager_dummy_name_result(text);}
void manager_client_audio_frame(ManagerLeagueAudioFrame *out,uint64_t ms){if(online)manager_online_audio_frame(out,ms);else manager_dummy_audio_frame(out,ms);}
