/* Apply native surface/weather after Mobile's initializer resets rain. This
 * callback receives the writable MatchEnv inside the game's own setup lock;
 * no registry pointer is retained or written from the render thread. */
#include "match_environment.h"
#include "scene_runtime_log.h"
static void (*weather_env_copy_original)(void *, const void *);
static void (*weather_env_common)(void *, uint8_t, uint8_t, uint8_t);
static void (*weather_env_turf)(void *, uint32_t);
static void (*weather_env_pitch)(void *, uint32_t);
static void (*weather_env_change)(void *, uint32_t);
static void (*weather_env_rain)(void *, int);
static void (*weather_env_wet)(void *, int);
static uint32_t (*weather_get_turf)(const void *);
static uint32_t (*weather_get_pitch)(const void *);
static uint32_t (*weather_get_rain)(const void *);
static void (*weather_ball_state_original)(void *);
static _Alignas(4) uint32_t weather_scene_kind;
static uint32_t weather_ball_logged;

static void weather_apply_native(void *env, const void *match) {
  weather_env_copy_original(env, match);
  if (!env) return;
  const uint32_t choice = pes_controller_stadium_weather();
  const NxMatchEnvironment e = nx_match_environment(choice,
      pes_controller_stadium_season(), pes_controller_stadium_turf_length(),
      pes_controller_stadium_pitch_condition());
  weather_env_common(env, e.weather, !pes_controller_stadium_is_day(), e.season);
  weather_env_turf(env, e.turf);
  weather_env_pitch(env, e.condition);
  weather_env_change(env, e.change);
  weather_env_wet(env, e.wet);
  weather_env_rain(env, e.raining);
  __atomic_store_n(&weather_scene_kind, e.raining ? e.weather : 0u, __ATOMIC_RELEASE);
  weather_ball_logged = 0;
  char detail[160];
  snprintf(detail, sizeof(detail), "%s season=%u turf=%u pitch=%u rain=%u change=%u",
      nx_weather_label(choice), e.season, weather_get_turf(env),
      weather_get_pitch(env), weather_get_rain(env), e.change);
  scene_runtime_note("native weather", detail);
}
static void weather_ball_surface(void *ball) {
  weather_ball_state_original(ball);
  if (ball && !weather_ball_logged) {
    /* Read only: UpdateBallPitchState owns registry locking and both the
     * live/future movement fields. Preserve its normal prediction updates. */
    uint32_t live, future;
    memcpy(&live, (const char *)ball + 0xdc, 4);
    memcpy(&future, (const char *)ball + 0x1e8, 4);
    char detail[96];
    snprintf(detail, sizeof(detail), "native ball surface live=%u future=%u", live, future);
    scene_runtime_note("native weather", detail);
    weather_ball_logged = 1;
  }
}
#ifndef PESNX_WEATHER_HOST_TEST
static void install_native_weather(so_module *module) {
  const uintptr_t env_plt = (uintptr_t)module->load_base + 0x387b510;
  const uintptr_t ball_plt = (uintptr_t)module->load_base + 0x38e8680;
  const uint32_t env_words[] = {0x9002e410,0xf9467211,0x91338210,0xd61f0220};
  const uint32_t ball_words[] = {0xd002e250,0xf942ce11,0x91166210,0xd61f0220};
  if (memcmp((void *)env_plt, env_words, 16) ||
      memcmp((void *)ball_plt, ball_words, 16)) {
    scene_runtime_note("native weather", "ABI mismatch; native weather hooks not installed");
    return;
  }
#define WEATHER_BIND(target, symbol) do { \
  target = (void *)so_try_find_addr_rx(module, symbol); \
  if (!target) return; \
} while (0)
  WEATHER_BIND(weather_env_copy_original, "_ZN9game_mode31SetTmpdbMatchToRegistryMatchEnvEPN5match8registry8MatchEnvERKN5tmpdb5MatchE");
  WEATHER_BIND(weather_env_common, "_ZN9game_mode21SetMatchEnvFromCommonEPN5match8registry8MatchEnvEhhh");
  WEATHER_BIND(weather_env_turf, "_ZN5match8registry8MatchEnv20SetStadiumTurfLengthEN6common11TURF_LENGTHE");
  WEATHER_BIND(weather_env_pitch, "_ZN5match8registry8MatchEnv24SetStadiumPitchConditionEN6common15PITCH_CONDITIONE");
  WEATHER_BIND(weather_env_change, "_ZN5match8registry8MatchEnv20SetChangeWeatherTypeEN6common17ChangeWeatherTypeE");
  WEATHER_BIND(weather_env_rain, "_ZN5match8registry8MatchEnv13SetIsNowRainyEb");
  WEATHER_BIND(weather_env_wet, "_ZN5match8registry8MatchEnv13SetIsWetRainyEb");
  WEATHER_BIND(weather_get_turf, "_ZNK5match8registry8MatchEnv20GetStadiumTurfLengthEv");
  WEATHER_BIND(weather_get_pitch, "_ZNK5match8registry8MatchEnv24GetStadiumPitchConditionEv");
  WEATHER_BIND(weather_get_rain, "_ZNK5match8registry8MatchEnv10IsNowRainyEv");
  WEATHER_BIND(weather_ball_state_original, "_ZN5match4Ball20UpdateBallPitchStateEv");
#undef WEATHER_BIND
  hook_arm64(env_plt, (uintptr_t)weather_apply_native);
  hook_arm64(ball_plt, (uintptr_t)weather_ball_surface);
  scene_runtime_note("native weather", "native surface/rain setup installed");
}
#endif
