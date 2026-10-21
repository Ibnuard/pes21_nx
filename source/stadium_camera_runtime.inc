/* Included after pause_settings_tmpdb_camera. No registry or ball pointer is
 * retained: the target callback runs inside native Update's registry locks. */
#include "stadium_camera_policy.h"

static __thread PesStadiumTargetScope stadium_camera_scope;

static void stadium_camera_begin(void *camera, void *parameter) {
  pes_stadium_target_scope_end(&stadium_camera_scope);
  if (!camera || !parameter) return;
  uint32_t id = UINT32_MAX, follow_player = 0;
  memcpy(&id, (const char *)camera + 8, sizeof(id));
  memcpy(&follow_player, (const char *)parameter + 0x48, sizeof(follow_player));
  const uint32_t v2 = __atomic_load_n(&pause_camera_stadium_v2, __ATOMIC_ACQUIRE);
  if (id != 6u || follow_player || v2 || !pes_controller_match_hud_inplay()) return;
  uint8_t type = 0;
  if (!pause_settings_tmpdb_camera(&type)) return;
  pes_stadium_target_scope_begin(&stadium_camera_scope, (uintptr_t)camera,
      id, type, v2, follow_player, 1u);
}

static int stadium_camera_target(void *camera, float *target,
                                  const float *sampled_ball) {
  if (!stadium_camera_scope.active ||
      stadium_camera_scope.owner != (uintptr_t)camera) return 0;
  /* Native Update has now acquired its current MatchInfo copy, and keeps it
   * alive through ShotBroadcastBallActive. Do not read it in begin(). */
  const void *match_info = NULL;
  uint32_t phase = UINT32_MAX;
  memcpy(&match_info, (const char *)camera + 0x238, sizeof(match_info));
  if (match_info)
    memcpy(&phase, (const char *)match_info + 0x116c, sizeof(phase));
  return pes_stadium_target_correct(&stadium_camera_scope, (uintptr_t)camera,
      phase, target, sampled_ball);
}

static void stadium_camera_end(void) {
  pes_stadium_target_scope_end(&stadium_camera_scope);
}
