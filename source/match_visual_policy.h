#ifndef PES_MATCH_VISUAL_POLICY_H
#define PES_MATCH_VISUAL_POLICY_H

#include <stdint.h>
#include <string.h>

// Audited PES21 Model::Manager owns exactly 17 on-pitch assist models. These
// are draw::Objects, separate from Screen/Flash cursor-name/stamina UI.
// Slots 15/16 are the native 3D shoot gauge/base and MUST also be preserved.
// Never cache these pointers across matches; the manager owns their lifetime.
static inline void pes_hide_pitch_assists(void *manager, int show,
                                          void (*set_disp)(void *, uint32_t)) {
  if (!manager || show || !set_disp)
    return;
  uint32_t state = 0;
  memcpy(&state, (const uint8_t *)manager + 0x158, sizeof(state));
  if (state != 2) // Manager::Action's initialized/MainUpdate state only.
    return;
  for (uint32_t index = 0; index < 17; index++) {
    if (index == 10 || index >= 15) // Offside line + shoot gauge/base.
      continue;
    void *model = NULL;
    memcpy(&model, (const uint8_t *)manager + 0x160 + index * 8,
           sizeof(model));
    if (model)
      set_disp(model, 0);
  }
}

// The real set-play trail is carried by the audited pass/cross trajectory
// models (11/12). Re-enable only those two after the broad cursor-hide pass;
// targets, guide rings, and area overlays stay hidden.
static inline void pes_set_pitch_trajectory(
    void *manager, int visible, void (*set_disp)(void *, uint32_t)) {
  if (!manager || !set_disp)
    return;
  uint32_t state = 0;
  memcpy(&state, (const uint8_t *)manager + 0x158, sizeof(state));
  if (state != 2)
    return;
  for (uint32_t index = 11; index <= 12; ++index) {
    void *model = NULL;
    memcpy(&model, (const uint8_t *)manager + 0x160 + index * 8,
           sizeof(model));
    if (model)
      set_disp(model, visible != 0);
  }
}

#endif
