#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "match_visual_policy.h"
#include "config.h"

static unsigned int calls;
static void hide(void *model, uint32_t visible) {
  assert(visible == 0);
  *(uint32_t *)model = visible;
  calls++;
}

int main(void) {
  _Alignas(8) uint8_t manager[0x220] = {0};
  uint32_t draws[17];
  for (unsigned int i = 0; i < 17; i++) {
    draws[i] = 1;
    void *p = &draws[i];
    memcpy(manager + 0x160 + i*8, &p, sizeof(p));
  }
  uint32_t ready = 2;
  memcpy(manager + 0x158, &ready, sizeof(ready));
  pes_hide_pitch_assists(NULL, 0, hide);
  pes_hide_pitch_assists(manager, 0, NULL);
  pes_hide_pitch_assists(manager, 1, hide);
  assert(calls == 0);
  pes_hide_pitch_assists(manager, 0, hide);
  assert(calls == 14);
  for (unsigned int i = 0; i < 17; i++)
    assert(draws[i] == (i == 10 || i >= 15));
  for (uint32_t state = 0; state <= 4; state++) {
    if (state == 2) continue;
    memcpy(manager + 0x158, &state, sizeof(state));
    pes_hide_pitch_assists(manager, 0, hide);
  }
  assert(calls == 14);
  // A fresh match may allocate completely different models, with null slots.
  memset(manager, 0, sizeof(manager));
  memcpy(manager + 0x158, &ready, sizeof(ready));
  uint32_t fresh = 1;
  void *fresh_ptr = &fresh;
  memcpy(manager + 0x160, &fresh_ptr, sizeof(fresh_ptr));
  pes_hide_pitch_assists(manager, 0, hide);
  assert(calls == 15 && fresh == 0);

  // Tests run from a new temporary working directory; never user config.
  assert(read_config("missing.cfg") == -1);
  assert(config.player_cursor_show == 1);
  config.show_fps = 1;
  config.player_cursor_show = 0;
  assert(write_config("cursor-test.cfg") == 0);
  assert(read_config("cursor-test.cfg") == 0);
  assert(config.player_cursor_show == 0 && config.show_fps == 1);
  config.player_cursor_show = 1;
  assert(write_config("cursor-test.cfg") == 0);
  assert(read_config("cursor-test.cfg") == 0 && config.player_cursor_show == 1);
  puts("PASS visual policy: show/hide, lifecycle, null slots, second match, shoot gauge/offside preserved, config roundtrip");
  return 0;
}
