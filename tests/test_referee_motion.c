#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "../source/referee_motion.h"

static void step(RefereeMotion *m, RefereePoint ball, float dt, int restart) {
  const RefereePoint before=m->position;
  const float heading=m->heading;
  assert(referee_motion_step_mode(m,ball,NULL,0,dt,restart));
  assert(isfinite(m->heading) && isfinite(m->distance));
  assert(hypotf(m->velocity.x,m->velocity.z)<=5.801f);
  assert(hypotf(m->position.x-before.x,m->position.z-before.z)<=5.8f*dt+0.001f);
  assert(fabsf(referee_angle_delta(m->heading,heading))<=3*dt+0.001f);
  assert(fabsf(m->position.x)<=46 && fabsf(m->position.z)<=28);
}

int main(void) {
  RefereeMotion m;referee_motion_reset(&m);
  const RefereePoint initial=m.position;
  for(int i=0;i<600;i++)step(&m,(RefereePoint){0.15f*sinf(i*0.3f),0},1.0f/30,0);
  assert(hypotf(m.position.x-initial.x,m.position.z-initial.z)<0.01f);
  assert(!m.moving && hypotf(m.velocity.x,m.velocity.z)<0.001f);

  // Settle after a change of play; destination noise cannot restart locomotion.
  for(int i=0;i<1200;i++)step(&m,(RefereePoint){35,5},1.0f/30,0);
  float travelled=m.distance;
  for(int i=0;i<600;i++)step(&m,(RefereePoint){35+0.1f*sinf(i),5},1.0f/30,0);
  assert(m.distance-travelled<0.02f && !m.moving);

  // A restart keeps a viewing position, not pursuit of a stationary kicker.
  for(int i=0;i<1200;i++)step(&m,(RefereePoint){50,-30},1.0f/30,1);
  const RefereePoint restart_target=m.target;
  travelled=m.distance;
  for(int i=0;i<300;i++)step(&m,(RefereePoint){50+0.15f*sinf(i),-30},1.0f/30,1);
  assert(m.target.x==restart_target.x && m.target.z==restart_target.z);
  assert(m.distance-travelled<0.02f);
  assert(hypotf(m.position.x-50,m.position.z+30)>6);

  // Each restart reaches a stable viewing position without a jump. Signals
  // can finish independently; restarts do not pursue the stationary ball.
  const RefereePoint balls[]={{15,34},{-48,5},{52.5f,-34},{24,4},{41,0},{51,0}};
  const int restarts[]={2,3,4,5,6,8};
  for(unsigned k=0;k<6;++k) {
    for(int i=0;i<1200;++i)step(&m,balls[k],1.0f/30,restarts[k]);
    travelled=m.distance;
    for(int i=0;i<120;++i)step(&m,balls[k],1.0f/30,restarts[k]);
    assert(m.distance-travelled<.02f);
    assert(hypotf(m.position.x-balls[k].x,m.position.z-balls[k].z)>6);
    if(restarts[k]==8)assert(hypotf(m.position.x,m.position.z-10)<1);
  }

  // Resume/counterattack: turn and accelerate with bounded speed, no teleport.
  referee_motion_resume(&m);assert(!m.has_ball && !m.moving);
  for(int i=0;i<600;i++)step(&m,(RefereePoint){40-i*0.12f,8*sinf(i*.01f)},1.0f/60,0);
  assert(!m.restart && m.position.x<25);
  step(&m,(RefereePoint){0,0},1.0f/60,0); // Discontinuous ball reset.
  referee_motion_resume(&m);
  assert(m.ball_velocity.x==0 && m.ball_velocity.z==0);

  // Identical smooth plays remain close across frame rates.
  RefereeMotion a,b;referee_motion_reset(&a);referee_motion_reset(&b);
  for(int i=0;i<900;i++)step(&a,(RefereePoint){25*sinf(i/30.0f*.2f),10},1.0f/30,0);
  for(int i=0;i<1800;i++)step(&b,(RefereePoint){25*sinf(i/60.0f*.2f),10},1.0f/60,0);
  assert(hypotf(a.position.x-b.position.x,a.position.z-b.position.z)<0.25f);
  const RefereeMotion saved=m;
  assert(!referee_motion_step_mode(&m,(RefereePoint){NAN,0},NULL,0,.03f,0));
  assert(!memcmp(&m,&saved,sizeof(m)));
  puts("referee behavior scenarios: pass");
}
