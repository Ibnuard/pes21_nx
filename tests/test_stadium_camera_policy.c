#include "../source/stadium_camera_policy.h"
#include <assert.h>

static void start(PesStadiumTargetScope *s) {
  pes_stadium_target_scope_begin(s, 0x1000, 6, 12, 0, 0, 1);
}

int main(void) {
  PesStadiumTargetScope s = {0};
  const float situations[][3] = {
      {-51.f, 1.5f, 2.f}, /* own keeper holding a catch */
      {51.f, 1.8f, -2.f}, /* opposite end, independent of team/pad */
      {-49.f, .2f, 3.f}, /* backpass towards own keeper */
      {4.f, .5f, -16.f}, /* turnover with a stale goalward target */
      {-4.f, .5f, 16.f}, {0.f, 24.f, 32.f}};
  for (unsigned k = 0; k < sizeof(situations)/sizeof(situations[0]); ++k) {
    float p[16];
    for (unsigned n = 0; n < 16; ++n) p[n] = (float)(100+n);
    float untouched[16]; memcpy(untouched, p, sizeof(p));
    start(&s);
    assert(pes_stadium_target_correct(&s, 0x1000, 1, p, situations[k]));
    assert(!memcmp(p, situations[k], 3*sizeof(float)));
    /* Includes native eye, projection, FOV and unrelated parameter values. */
    assert(!memcmp(p+3, untouched+3, sizeof(p)-3*sizeof(float)));
    pes_stadium_target_scope_end(&s);
    assert(!s.active && !s.owner);
    assert(!pes_stadium_target_correct(&s, 0x1000, 1, p, situations[k]));
  }

  /* Every other choice, player-follow, V2, replay/stale HUD and match phase
   * remains native. These are gates, not a new camera or game-mode switch. */
  for (unsigned id = 0; id < 14; ++id) {
    pes_stadium_target_scope_begin(&s, 0x1000, id, 12, 0, 0, 1);
    assert(s.active == (id == 6));
  }
  for (unsigned type = 0; type < 14; ++type) {
    pes_stadium_target_scope_begin(&s, 0x1000, 6, type, 0, 0, 1);
    assert(s.active == (type == 12));
  }
  pes_stadium_target_scope_begin(&s, 0x1000, 6, 12, 1, 0, 1); assert(!s.active);
  pes_stadium_target_scope_begin(&s, 0x1000, 6, 12, 0, 1, 1); assert(!s.active);
  pes_stadium_target_scope_begin(&s, 0x1000, 6, 12, 0, 0, 0); assert(!s.active);
  pes_stadium_target_scope_begin(&s, 0, 6, 12, 0, 0, 1); assert(!s.active);

  float out[3] = {33,22,11}, previous[3]; memcpy(previous,out,sizeof(out));
  const float valid[3] = {1,.5f,2};
  start(&s);
  assert(!pes_stadium_target_correct(&s, 0x2000, 1, out, valid));
  assert(s.active && !memcmp(out,previous,sizeof(out)));
  for (unsigned phase = 0; phase < 8; ++phase) {
    start(&s);
    assert(pes_stadium_target_correct(&s,0x1000,phase,out,valid) == (phase == 1));
    if (phase != 1) assert(!s.active);
    memcpy(out, previous, sizeof(out));
  }
  const float bad[][3] = {{NAN,0,0},{0,INFINITY,0},{66,0,0},{0,-4,0},
                         {0,61,0},{0,0,45}};
  for(unsigned i=0;i<sizeof(bad)/sizeof(bad[0]);++i) {
    start(&s); assert(!pes_stadium_target_correct(&s,0x1000,1,out,bad[i]));
    assert(!s.active && !memcmp(out,previous,sizeof(out)));
  }
  start(&s); assert(!pes_stadium_target_correct(&s,0x1000,1,out,0));
  start(&s); assert(!pes_stadium_target_correct(&s,0x1000,1,0,valid));
  start(&s); memcpy(out,valid,sizeof(out));
  assert(pes_stadium_target_correct(&s,0x1000,1,out,out));
  assert(!memcmp(out,valid,sizeof(out)));
  return 0;
}
