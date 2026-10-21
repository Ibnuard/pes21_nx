#include <assert.h>
#include <math.h>
#include <stddef.h>
#include <stdio.h>
#include "../source/referee_pc_policy.h"

static void close_to(float actual, float expected) {
  assert(fabsf(actual - expected) < 0.0001f);
}

int main(void) {
  /* The Mobile constructor's audited geometry is an input fixture. It is
   * deliberately not described as an observed FL26 live/default field. */
  const RefereePcField field = {34.06f, 36.14f, 20.12f};
  float x = 0.0f, z = 12.0f;
  assert(referee_pc_bound_live_target(&x, &z, field));
  close_to(x, 0.0f); close_to(z, 12.0f);

  /* A target beside the far goal is brought away from the goal mouth and
   * toward the permitted diagonal; midfield is not pulled to its center. */
  x = 50.0f; z = 34.0f;
  assert(referee_pc_bound_live_target(&x, &z, field));
  close_to(x, 33.14f); close_to(z, 15.61019f);
  x = -50.0f; z = -34.0f;
  assert(referee_pc_bound_live_target(&x, &z, field));
  close_to(x, -33.14f); close_to(z, -15.61019f);
  x = 0.0f; z = 32.0f;
  assert(referee_pc_bound_live_target(&x, &z, field));
  close_to(x, 0.0f); close_to(z, 32.0f);

  /* Different field geometry is respected, with no assumptions about PC
   * constructor literals. Once bounded, another application is stable. */
  const RefereePcField smaller = {25.0f, 30.0f, 15.0f};
  x = 40.0f; z = 30.0f;
  assert(referee_pc_bound_live_target(&x, &z, smaller));
  close_to(x, 27.0f); close_to(z, 11.5f);
  assert(referee_pc_bound_live_target(&x, &z, smaller));
  close_to(x, 27.0f); close_to(z, 11.5f);

  /* An invalid or absent live snapshot cannot mutate an existing target. */
  const RefereePcField invalid[] = {{NAN,36,20}, {34,3,20}, {34,36,35},
                                  {0,36,20}, {34,INFINITY,20}};
  for (unsigned i = 0; i < sizeof(invalid)/sizeof(*invalid); ++i) {
    x = 10.0f; z = 15.0f;
    assert(!referee_pc_bound_live_target(&x, &z, invalid[i]));
    assert(x == 10.0f && z == 15.0f);
  }
  assert(!referee_pc_bound_live_target(NULL, &z, field));
  x = NAN;
  assert(!referee_pc_bound_live_target(&x, &z, field));
  puts("PC referee target constraints: pass");
}
