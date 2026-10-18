#ifndef PES_STADIUM_V2_CAMERA_H
#define PES_STADIUM_V2_CAMERA_H
#include <math.h>
#include <stdint.h>
#include <string.h>

/* Native Stadium supplies the pose, bounds and optical zoom. Tracking holds a
 * composition until play approaches its screen margin, then eases to a new
 * composition. The last final view supplies the margin in screen space. */
typedef struct {
  float target[3];
  float view[6], lens, dt, pressure;
  uint64_t stamp;
  unsigned initialized, view_valid, panning;
} StadiumV2Camera;

static inline float stadium_v2_clamp(float v,float lo,float hi) {
  return fminf(hi,fmaxf(lo,v));
}
static inline int stadium_v2_valid_ball(const float *ball) {
  return ball && isfinite(ball[0]) && isfinite(ball[1]) && isfinite(ball[2]) &&
      fabsf(ball[0])<=65.f && fabsf(ball[2])<=44.f && ball[1]>=-3.f && ball[1]<=60.f;
}
static inline void stadium_v2_suspend(StadiumV2Camera *s) {
  memset(s,0,sizeof(*s));
}

/* Perspective projection in the native Y-up, 16:9 presentation. This uses
 * the final optical lens, not world-metre thresholds that change with zoom.
 * Output is normalized device space: +/-1 is an actual viewport edge. */
static inline int stadium_v2_screen(const float *view,float lens,
                                     const float *point,float *screen) {
  if (!view || !point || !screen || !isfinite(lens) || lens<.10f || lens>1.4f) return 0;
  for (unsigned i=0;i<6;++i) if (!isfinite(view[i])) return 0;
  float f[3],r[3],u[3],d[3];
  for (unsigned i=0;i<3;++i) { f[i]=view[i]-view[i+3]; d[i]=point[i]-view[i+3]; }
  const float length=sqrtf(f[0]*f[0]+f[1]*f[1]+f[2]*f[2]);
  const float flat=hypotf(f[0],f[2]);
  if (length<1.f || flat<1.f) return 0;
  for (unsigned i=0;i<3;++i) f[i]/=length;
  r[0]=-f[2]*length/flat; r[1]=0; r[2]=f[0]*length/flat;
  u[0]=r[1]*f[2]-r[2]*f[1]; u[1]=r[2]*f[0]-r[0]*f[2]; u[2]=r[0]*f[1]-r[1]*f[0];
  const float depth=d[0]*f[0]+d[1]*f[1]+d[2]*f[2];
  if (!isfinite(depth) || depth<1.f) return 0;
  const float span=depth*tanf(lens*.5f);
  screen[0]=(d[0]*r[0]+d[2]*r[2])/(span*(16.f/9.f));
  screen[1]=(d[0]*u[0]+d[1]*u[1]+d[2]*u[2])/span;
  return isfinite(screen[0]) && isfinite(screen[1]);
}

/* Hysteresis: short passes stay in a held shot; movement begins at 60%/52%
 * of the half viewport and settles at 38%/32%, never on the ball itself.
 * Approach to a screen edge increases response continuously, without a
 * predicted receiver, frame-dependent velocity, allocation or extra query. */
static inline int stadium_v2_step(StadiumV2Camera *s,float *target,
                                  float limit_x,float min_z,float max_z,
                                  uint64_t now_ns) {
  if (!s || !target) return 0;
  for (unsigned i=0;i<3;++i) if (!isfinite(target[i])) return 0;
  if (!isfinite(limit_x) || !isfinite(min_z) || !isfinite(max_z) ||
      limit_x<0.f || limit_x>80.f || min_z>max_z ||
      min_z < -60.f || max_z > 60.f) return 0;
  float desired[3]={stadium_v2_clamp(target[0],-limit_x,limit_x),target[1],
                    stadium_v2_clamp(target[2],min_z,max_z)};
  const int reset=!s->initialized || now_ns<s->stamp ||
                  now_ns-s->stamp>250000000ULL;
  s->dt=0;
  if (reset) {
    s->view_valid=s->panning=0; s->pressure=0;
    memcpy(s->target,desired,sizeof(desired)); s->initialized=1;
  } else if (now_ns>s->stamp) {
    const float dt=(float)(now_ns-s->stamp)*1.e-9f;
    float screen[2]; s->dt=dt;
    if (s->view_valid && stadium_v2_screen(s->view,s->lens,target,screen)) {
      const float outer=fmaxf(fabsf(screen[0])/.60f,fabsf(screen[1])/.52f);
      const float inner=fmaxf(fabsf(screen[0])/.38f,fabsf(screen[1])/.32f);
      s->pressure=fmaxf(fabsf(screen[0]),fabsf(screen[1]));
      if (outer>1.f) s->panning=1;
      if (inner<=1.02f) s->panning=0;
      if (s->panning) {
        const float urgency=stadium_v2_clamp((s->pressure-.60f)/.35f,0,1);
        const float response=.34f-.22f*urgency*urgency*(3.f-2.f*urgency);
        const float alpha=-expm1f(-dt/response);
        const float travel=1.f-1.f/fmaxf(inner,1.f);
        for (unsigned i=0;i<3;++i)
          s->target[i]+=(desired[i]-s->target[i])*(travel*alpha);
      }
    } else {
      /* One bootstrap frame (or an invalid native view): smooth, bounded
       * following. Do not invent a camera pose or lens to derive margins. */
      const float alpha=-expm1f(-dt/.34f);
      for (unsigned i=0;i<3;++i) s->target[i]+=(desired[i]-s->target[i])*alpha;
    }
  }
  s->target[0]=stadium_v2_clamp(s->target[0],-limit_x,limit_x);
  s->target[2]=stadium_v2_clamp(s->target[2],min_z,max_z);
  s->stamp=now_ns;
  memcpy(target,s->target,sizeof(s->target));
  return 1;
}

/* Retain native optical changes but remove single-frame lens pumping. A
 * bounded extra 18% field of view leaves room during a fast screen crossing;
 * release is slower than expansion. All pose fields stay native-derived. */
static inline void stadium_v2_finish(StadiumV2Camera *s,float *parameter,float native_lens) {
  if (!s || !parameter || !s->initialized) return;
  float screen[2];
  if (!stadium_v2_screen(parameter,native_lens,s->target,screen)) {
    s->view_valid=0; return;
  }
  float lens=native_lens;
  if (s->view_valid && s->dt>0.f) {
    const float room=stadium_v2_clamp((s->pressure-.60f)/.30f,0,1);
    const float desired=fminf(1.4f,lens*(1.f+.18f*room*room*(3.f-2.f*room)));
    const float delta=desired-s->lens;
    lens=s->lens;
    if (fabsf(delta)>.002f) {
      const float response=delta>0?.30f:.95f;
      lens+=delta*(-expm1f(-s->dt/response));
    }
  } else if (s->view_valid) lens=s->lens;
  parameter[13]=s->lens=lens;
  memcpy(s->view,parameter,sizeof(s->view)); s->view_valid=1;
}
#endif
