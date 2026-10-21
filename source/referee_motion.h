#ifndef PESNX_REFEREE_MOTION_H
#define PESNX_REFEREE_MOTION_H

/* Authored visual-only positioning, in native Fox metres (X/Z horizontal).
 * No collision objects, player registry entries or match decisions are added. */
#include <math.h>
#include <stdint.h>
#include "referee_pc_policy.h"

typedef struct { float x, z; } RefereePoint;
#define REFEREE_KICKOFF_EDGE_Z 9.15f
typedef struct {
  RefereePoint position, velocity;
  float heading, distance;
  int initialized;
  RefereePoint last_ball, ball_velocity, target;
  int has_ball, moving, restart;
  RefereePcField pc_field; // Valid only for the native-bank live-field snapshot.
} RefereeMotion;

static inline float referee_limit(float n, float lo, float hi) {
  return fminf(hi, fmaxf(lo, n));
}
static inline int referee_point_valid(RefereePoint p) {
  return isfinite(p.x) && isfinite(p.z) && fabsf(p.x)<1000.0f && fabsf(p.z)<1000.0f;
}
static inline float referee_angle_delta(float a, float b) {
  return remainderf(a-b, 6.28318530718f);
}
static inline void referee_motion_reset(RefereeMotion *m) {
  *m = (RefereeMotion){.position={0,12}, .initialized=1};
}
static inline void referee_separation(RefereePoint position, RefereePoint obstacle,
                                      float radius, float force, RefereePoint *v) {
  if (!referee_point_valid(obstacle)) return;
  float dx=position.x-obstacle.x, dz=position.z-obstacle.z;
  const float distance_squared=dx*dx+dz*dz;
  if (distance_squared>=radius*radius) return;
  const float d=sqrtf(distance_squared);
  // Exact overlap has a deterministic exit, not a divide-by-zero.
  if (d<0.01f) { dx=0; dz=1; }
  else { dx/=d; dz/=d; }
  const float gain=force*(1.0f-d/radius);
  v->x+=dx*gain; v->z+=dz*gain;
  // Near a player, destination attraction must not cancel the escape vector
  // and leave the referee standing inside that player.
  if (radius<3.0f && d<1.8f) {
    const float radial=v->x*dx+v->z*dz;
    const float escape=(1.8f-d)*3.0f;
    if (radial<escape) {v->x+=dx*(escape-radial);v->z+=dz*(escape-radial);}
  }
}
static inline void referee_motion_resume(RefereeMotion *m) {
  m->velocity=(RefereePoint){0};
  m->ball_velocity=(RefereePoint){0};
  m->has_ball=m->moving=0;
}

/* The requested near-side centre-circle/halfway intersection is a wrapper
 * presentation policy, not the different FL26 kickoff formula. */
static inline void referee_motion_kickoff(RefereeMotion *m) {
  referee_motion_reset(m);
  m->position=(RefereePoint){0,REFEREE_KICKOFF_EDGE_Z};
  m->heading=3.141592654f;
}

static inline RefereePoint referee_motion_destination(RefereePoint ball,
                                      int restart, RefereePcField field) {
  RefereePoint target={referee_limit(ball.x*0.72f,-38,38),
      referee_limit(ball.z*0.38f+10-ball.x*0.10f,-23,23)};
  const float end=ball.x<0?-1.0f:1.0f,side=ball.z<0?-1.0f:1.0f;
  if (restart==2) target=(RefereePoint){ball.x*0.85f,side*22};
  else if (restart==3) target=(RefereePoint){ball.x*0.55f,10};
  else if (restart==4) target=(RefereePoint){end*37,side*12};
  else if (restart==5) target=(RefereePoint){ball.x-end*7,ball.z-side*8};
  else if (restart==6) target=(RefereePoint){end*38,12};
  else if (restart==8) target=(RefereePoint){0,10};
  target.x=referee_limit(target.x,-42,42);
  target.z=referee_limit(target.z,-25,25);
  if (!restart) referee_pc_bound_live_target(&target.x,&target.z,field);
  return target;
}

/* A hidden replay can jump to an unrelated moment. Re-enter at the current
 * policy's destination rather than expose the stale replay-start position.
 * Bounded clearance choices run only on that transition, never each frame. */
static inline int referee_motion_restore(RefereeMotion *m, RefereePoint ball,
                         const RefereePoint *players, uint32_t count, int restart) {
  if (!m || !referee_point_valid(ball)) return 0;
  if (!m->initialized) referee_motion_reset(m);
  if (!restart && (fabsf(ball.x)>52.5f || fabsf(ball.z)>34.0f)) restart=1;
  const RefereePoint target=referee_motion_destination(ball,restart,m->pc_field);
  const RefereePoint offsets[]={{0,0},{3,0},{-3,0},{0,3},{0,-3},
    {3,3},{-3,3},{3,-3},{-3,-3},{6,0},{-6,0},{0,6},{0,-6}};
  RefereePoint best=target;
  float best_clearance=-1000;
  if (!players) count=0;
  if (count>22) count=22;
  for (unsigned i=0;i<sizeof(offsets)/sizeof(offsets[0]);++i) {
    RefereePoint candidate={referee_limit(target.x+offsets[i].x,-46,46),
                            referee_limit(target.z+offsets[i].z,-28,28)};
    float clearance=hypotf(candidate.x-ball.x,candidate.z-ball.z)-6.f;
    for (uint32_t p=0;p<count;++p)
      if (referee_point_valid(players[p]))
        clearance=fminf(clearance,hypotf(candidate.x-players[p].x,
                                       candidate.z-players[p].z)-2.4f);
    if (clearance>best_clearance) {best=candidate;best_clearance=clearance;}
    if (clearance>=0) {best=candidate;break;}
  }
  referee_motion_resume(m);
  m->position=best;m->target=target;m->last_ball=ball;m->has_ball=1;
  m->restart=restart;
  m->heading=atan2f(ball.x-best.x,ball.z-best.z);
  return 1;
}

/* Wrapper visual movement with native match restart inputs. The verified PC
 * target bounds are applied when a valid live FieldInfo snapshot is supplied.
 * Target selection, avoidance and integration remain wrapper policies. */
static inline int referee_motion_step_mode(RefereeMotion *m, RefereePoint ball,
                                      const RefereePoint *players, uint32_t count,
                                      float dt, int restart) {
  if (!m || !referee_point_valid(ball) || !isfinite(dt) || dt<=0) return 0;
  if (!m->initialized) referee_motion_reset(m);
  if (dt>0.10f) dt=0.10f; // Never catch up across a pause/loading stall.
  if (count>22) count=22;
  if (!players) count=0;
  if (!restart && (fabsf(ball.x)>52.5f || fabsf(ball.z)>34.0f)) restart=1;
  RefereePoint observed={0};
  if (m->has_ball) {
    const float dx=ball.x-m->last_ball.x,dz=ball.z-m->last_ball.z;
    // A reset/replay teleport is not a 100 m/s counterattack.
    if (hypotf(dx,dz)<12.0f) {
      observed=(RefereePoint){dx/dt,dz/dt};
      const float speed=hypotf(observed.x,observed.z);
      if (speed>25) {observed.x*=25/speed;observed.z*=25/speed;}
    }
  }
  const int first=!m->has_ball;
  m->last_ball=ball;m->has_ball=1;
  const unsigned steps=(unsigned)ceilf(dt*120.0f);
  const float h=dt/(float)steps;
  const float tracking=1.0f-expf(-h*3.0f);
  for (unsigned i=0; i<steps; ++i) {
    m->ball_velocity.x+=(observed.x-m->ball_velocity.x)*tracking;
    m->ball_velocity.z+=(observed.z-m->ball_velocity.z)*tracking;
    const RefereePoint predicted={ball.x+(restart?0:m->ball_velocity.x*0.3f),
                                 ball.z+(restart?0:m->ball_velocity.z*0.3f)};
    // Keep a consistent diagonal viewing lane, inside the field and away
    // from goal mouths. Smooth the destination instead of chasing every touch.
    // Restart identifiers are translated from PES21, never EF object offsets.
    // Use distinct viewing positions for a throw, goal kick, corner and kick.
    const RefereePoint desired_target=referee_motion_destination(predicted,restart,m->pc_field);
    if ((first && !i) || m->restart!=restart) m->target=desired_target;
    else if (!restart || hypotf(m->target.x-desired_target.x,m->target.z-desired_target.z)>3) {
      m->target.x+=(desired_target.x-m->target.x)*tracking;
      m->target.z+=(desired_target.z-m->target.z)*tracking;
    }
    m->restart=restart;
    float dx=m->target.x-m->position.x, dz=m->target.z-m->position.z;
    const float d=hypotf(dx,dz);
    if (d>2.2f) m->moving=1;
    else if (d<0.8f) m->moving=0;
    float speed=m->moving?referee_limit((d-0.5f)*1.2f,0,restart?3.0f:5.8f):0;
    RefereePoint desired={0};
    if (d>0.001f) { desired.x=dx/d*speed; desired.z=dz/d*speed; }
    referee_separation(m->position,ball,6.0f,7.0f,&desired);
    for (uint32_t p=0;p<count;++p)
      referee_separation(m->position,players[p],2.4f,5.0f,&desired);
    speed=hypotf(desired.x,desired.z);
    if (speed>5.8f) { desired.x*=5.8f/speed; desired.z*=5.8f/speed; }
    const float heading=speed>0.35f?atan2f(desired.x,desired.z):
        atan2f(ball.x-m->position.x,ball.z-m->position.z);
    m->heading=referee_angle_delta(m->heading+
        referee_limit(referee_angle_delta(heading,m->heading),-3*h,3*h),0);
    if (speed>0.35f) {
      const float forward=fmaxf(0.0f,cosf(referee_angle_delta(heading,m->heading)));
      desired.x*=forward;desired.z*=forward;
    }
    dx=desired.x-m->velocity.x; dz=desired.z-m->velocity.z;
    const float change=hypotf(dx,dz);
    const float limit=(speed<hypotf(m->velocity.x,m->velocity.z)?8.0f:4.0f)*h;
    if (change>limit) { dx*=limit/change; dz*=limit/change; }
    m->velocity.x+=dx; m->velocity.z+=dz;
    const RefereePoint before=m->position;
    m->position.x=referee_limit(before.x+m->velocity.x*h,-46,46);
    m->position.z=referee_limit(before.z+m->velocity.z*h,-28,28);
    m->distance+=hypotf(m->position.x-before.x,m->position.z-before.z);
    if (fabsf(m->position.x)>=46) m->velocity.x=0;
    if (fabsf(m->position.z)>=28) m->velocity.z=0;
  }
  return 1;
}

static inline int referee_motion_step(RefereeMotion *m, RefereePoint ball,
                                      const RefereePoint *players, uint32_t count,
                                      float dt) {
  return referee_motion_step_mode(m,ball,players,count,dt,0);
}

#endif
