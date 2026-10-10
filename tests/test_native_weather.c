#include <assert.h>
#include <stdint.h>
#include <string.h>
static uint32_t choice, season, turf=1, condition=1;
uint32_t pes_controller_stadium_weather(void) { return choice; }
uint32_t pes_controller_stadium_season(void) { return season; }
uint32_t pes_controller_stadium_turf_length(void) { return turf; }
uint32_t pes_controller_stadium_pitch_condition(void) { return condition; }
uint32_t pes_controller_stadium_is_day(void) { return 1; }
#define PESNX_WEATHER_HOST_TEST
#define PESNX_SCENE_RUNTIME_LOG_H
static void scene_runtime_note(const char *a,const char *b) {(void)a;(void)b;}
#include <stdio.h>
#include "../source/native_weather.inc"
static unsigned resets;
static void reset(void *p,const void *match) {
  assert(match==(const void*)1); ++resets;
  if(p) memset(p,0,sizeof(NxMatchEnvironment));
}
static void common(void *p,uint8_t w,uint8_t t,uint8_t s) {
  assert(!t); NxMatchEnvironment *e=p;e->weather=w;e->season=s;
}
#define SETTER(name,field) static void name(void *p,uint32_t v){((NxMatchEnvironment*)p)->field=v;}
SETTER(set_turf,turf) SETTER(set_pitch,condition) SETTER(set_change,change)
static void rain(void *p,int v){((NxMatchEnvironment*)p)->raining=v;}
static void wet(void *p,int v){((NxMatchEnvironment*)p)->wet=v;}
static uint32_t gt(const void *p){return ((const NxMatchEnvironment*)p)->turf;}
static uint32_t gp(const void *p){return ((const NxMatchEnvironment*)p)->condition;}
static uint32_t gr(const void *p){return ((const NxMatchEnvironment*)p)->raining;}
static void ball_native(void *p){(void)p;}
int main(void) {
  weather_env_copy_original=reset;weather_env_common=common;
  weather_env_turf=set_turf;weather_env_pitch=set_pitch;weather_env_change=set_change;
  weather_env_rain=rain;weather_env_wet=wet;
  weather_get_turf=gt;weather_get_pitch=gp;weather_get_rain=gr;
  weather_ball_state_original=ball_native;
  for(choice=0;choice<NX_WEATHER_COUNT;++choice)
  for(season=0;season<2;++season)for(turf=0;turf<3;++turf)for(condition=0;condition<3;++condition) {
    unsigned char snapshot[0xa8];memset(snapshot,0x5a,sizeof(snapshot));
    NxMatchEnvironment e=nx_match_environment(choice,season,turf,condition),actual;
    assert(nx_environment_write_snapshot(snapshot,sizeof(snapshot),e));
    uint32_t w,s,t,c;memcpy(&w,snapshot+8,4);memcpy(&s,snapshot+12,4);
    memcpy(&t,snapshot+0x78,4);memcpy(&c,snapshot+0x7c,4);
    assert(w==e.weather && s==e.season && t==turf && c==e.condition);
    for(unsigned i=0;i<sizeof(snapshot);++i)
      if(!(i>=8&&i<16)&&!(i>=0x78&&i<0x80)) assert(snapshot[i]==0x5a);
    weather_apply_native(&actual,(void*)1);assert(!memcmp(&actual,&e,sizeof(e)));
    assert(weather_scene_kind==(choice>=NX_WEATHER_RAIN?e.weather:0));
    if(choice>=NX_WEATHER_RAIN) assert(actual.raining && actual.wet && actual.condition==2);
    else assert(!actual.raining && actual.condition==condition);
    assert(actual.season==season);
  }
  assert(resets==54);
  /* Repeated matches: rain and winter never stick after selecting fine/summer. */
  NxMatchEnvironment e; choice=NX_WEATHER_RAIN;season=1;weather_apply_native(&e,(void*)1);
  choice=NX_WEATHER_FINE;season=0;turf=1;condition=0;weather_apply_native(&e,(void*)1);
  assert(!e.raining&&!e.wet&&!e.season&&!e.weather&&!e.change&&!weather_scene_kind);
  e=nx_match_environment(99,99,99,99);assert(e.turf==1&&e.condition==1&&!e.weather);
  unsigned char guard[0xa8];memset(guard,0x7a,sizeof(guard));
  assert(!nx_environment_write_snapshot(guard,sizeof(guard)-1,e));
  for(unsigned i=0;i<sizeof(guard);++i)assert(guard[i]==0x7a);
  unsigned char ball[0x200]={0};weather_ball_surface(ball);assert(weather_ball_logged);
  weather_apply_native(NULL,(void*)1);
  return 0;
}
