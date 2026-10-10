#ifndef PESNX_REFEREE_ANIMATION_H
#define PESNX_REFEREE_ANIMATION_H
/* Bounded, read-only EF motion bake. Each pose is already retargeted to the
 * native renderer's 19 slots; no EF pointers, rig or code run on Switch. */
#include <math.h>
#include "runtime_assets.h"

#define REFEREE_ANIMATION_BONES 19u
#define REFEREE_ANIMATION_CLIPS 8u
#define REFEREE_ANIMATION_LIMIT (512u*1024u)
typedef struct { float rotation[4], position[4]; } RefereeBonePose;
typedef struct {
  uint32_t frames;
  float rate, speed;
  const RefereeBonePose *poses;
} RefereeClip;
typedef struct { RefereeClip clips[REFEREE_ANIMATION_CLIPS]; unsigned count; int valid; } RefereeAnimationBank;
typedef struct { double gait_phase, idle_phase; float speed; int initialized; } RefereeAnimationClock;

static inline float referee_animation_float(const unsigned char *p) {
  float value;memcpy(&value,p,4);return value;
}
static inline int referee_animation_bind(RefereeAnimationBank *bank,const void *bytes,size_t size) {
  *bank=(RefereeAnimationBank){0};
  if (!bytes || size<160 || size>REFEREE_ANIMATION_LIMIT) return 0;
  const unsigned char *p=bytes;
  // v1 stored animation-space rotations and deformed the skinned model.
  // v3 adds four ordered, non-looping gestures; v2 remains locomotion-only.
  const unsigned version=nx_asset_u32(p+8),count=nx_asset_u32(p+12);
  if (memcmp(p,"NXREF01\0",8) || !((version==2 && count==4)||(version==3 && count==8)) ||
      nx_asset_u32(p+16)!=19 || nx_asset_u32(p+20)!=32 ||
      nx_asset_hash(p+32,size-32)!=nx_asset_u64(p+24)) return 0;
  size_t cursor=32+count*32;
  if (size<cursor) return 0;
  RefereeAnimationBank candidate={0};
  for (unsigned i=0;i<count;++i) {
    const unsigned char *row=p+32+i*32;
    RefereeClip *c=&candidate.clips[i];
    c->frames=nx_asset_u32(row);c->rate=referee_animation_float(row+8);
    c->speed=referee_animation_float(row+12);
    if (c->frames<2 || c->frames>600 || nx_asset_u32(row+4)!=cursor ||
        !isfinite(c->rate) || c->rate<10 || c->rate>60 ||
        !isfinite(c->speed) || c->speed<0 || c->speed>12 ||
        (i==0 || i>=4 ? c->speed!=0 : c->speed-candidate.clips[i-1].speed<0.1f) ||
        nx_asset_u64(row+16) || nx_asset_u64(row+24)) return 0;
    const size_t count=(size_t)c->frames*REFEREE_ANIMATION_BONES;
    const size_t length=count*sizeof(RefereeBonePose);
    if (length>size-cursor || ((uintptr_t)(p+cursor)&15u)) return 0;
    c->poses=(const RefereeBonePose *)(p+cursor);
    for (size_t j=0;j<count;++j) {
      const RefereeBonePose *bone=&c->poses[j];float norm=0;
      for (unsigned k=0;k<4;++k) {
        if (!isfinite(bone->rotation[k]) || !isfinite(bone->position[k]) ||
            fabsf(bone->position[k])>4) return 0;
        norm+=bone->rotation[k]*bone->rotation[k];
      }
      if (norm<0.98f || norm>1.02f || bone->position[3]!=1.0f) return 0;
    }
    cursor+=length;
  }
  if (cursor!=size) return 0;
  candidate.count=count;candidate.valid=1;*bank=candidate;return 1;
}
static inline void referee_pose_blend(RefereeBonePose *out,const RefereeBonePose *a,
                                      const RefereeBonePose *b,float weight) {
  float dot=0,norm=0;
  for (unsigned i=0;i<4;++i) dot+=a->rotation[i]*b->rotation[i];
  const float sign=dot<0?-1.0f:1.0f;
  for (unsigned i=0;i<4;++i) {
    out->rotation[i]=a->rotation[i]*(1-weight)+b->rotation[i]*sign*weight;
    norm+=out->rotation[i]*out->rotation[i];
    out->position[i]=a->position[i]*(1-weight)+b->position[i]*weight;
  }
  const float inverse=1.0f/sqrtf(norm);
  for (unsigned i=0;i<4;++i) out->rotation[i]*=inverse;
  out->position[3]=1;
}
static inline void referee_clip_sample(const RefereeClip *clip,double phase,
                                       RefereeBonePose out[REFEREE_ANIMATION_BONES]) {
  const double frame=phase*clip->frames;
  const uint32_t first=(uint32_t)frame%clip->frames,second=(first+1)%clip->frames;
  const float weight=(float)(frame-floor(frame));
  for (unsigned i=0;i<REFEREE_ANIMATION_BONES;++i)
    referee_pose_blend(&out[i],&clip->poses[first*REFEREE_ANIMATION_BONES+i],
                      &clip->poses[second*REFEREE_ANIMATION_BONES+i],weight);
}
static inline int referee_animation_step(const RefereeAnimationBank *bank,
                                         RefereeAnimationClock *clock,float speed,float dt,
                                         RefereeBonePose out[REFEREE_ANIMATION_BONES]) {
  if (!bank->valid || !isfinite(speed) || !isfinite(dt) || speed<0 || speed>12 || dt<0) return 0;
  if (dt>0.1f) dt=0.1f;
  if (!clock->initialized) { *clock=(RefereeAnimationClock){.initialized=1,.speed=speed}; }
  clock->speed+=(speed-clock->speed)*(1.0f-expf(-dt/0.12f));
  unsigned upper=1;
  while (upper<3 && clock->speed>bank->clips[upper].speed) ++upper;
  const RefereeClip *a=&bank->clips[upper-1],*b=&bank->clips[upper];
  float weight=(clock->speed-a->speed)/(b->speed-a->speed);
  weight=fmaxf(0,fminf(1,weight));
  float frequency;
  if (upper==1) frequency=(b->rate/b->frames)*speed/b->speed;
  else frequency=(1-weight)*(a->rate/a->frames)*speed/a->speed+
                 weight*(b->rate/b->frames)*speed/b->speed;
  clock->gait_phase+=frequency*dt;clock->gait_phase-=floor(clock->gait_phase);
  clock->idle_phase+=(bank->clips[0].rate/bank->clips[0].frames)*dt;
  clock->idle_phase-=floor(clock->idle_phase);
  RefereeBonePose pa[REFEREE_ANIMATION_BONES],pb[REFEREE_ANIMATION_BONES];
  referee_clip_sample(a,upper==1?clock->idle_phase:clock->gait_phase,pa);
  referee_clip_sample(b,clock->gait_phase,pb);
  for (unsigned i=0;i<REFEREE_ANIMATION_BONES;++i) referee_pose_blend(&out[i],&pa[i],&pb[i],weight);
  return 1;
}

/* Imported EF10 gesture slots: whistle, arm up, direction, arm down. These
 * clips use their original time order and clamp at the last frame. */
typedef struct { uint32_t serial; unsigned clip, next; float elapsed; } RefereeGesture;
static inline void referee_gesture_start(RefereeGesture *g,uint32_t serial,
                                         unsigned restart,unsigned reason) {
  if (!serial || serial==g->serial) return;
  *g=(RefereeGesture){.serial=serial};
  if ((reason!=4 && reason!=5 && reason!=3) || restart<1 || restart>6) return;
  g->clip=4;g->next=(restart==4 || restart==5 || restart==6)?5:6;g->elapsed=0;
}
/* Renderer slots 0..6 are pelvis and legs. Gestures from EF sometimes contain
 * a walk-to-stop cycle: retain locomotion below the waist so that signalling
 * never stops movement or plays walking feet on a stationary actor. Align the
 * upper body about the current pelvis to retain the native bone lengths. */
static inline void referee_quat_product(float out[4],const float a[4],const float b[4]) {
  const float q[4]={a[3]*b[0]+a[0]*b[3]+a[1]*b[2]-a[2]*b[1],
    a[3]*b[1]-a[0]*b[2]+a[1]*b[3]+a[2]*b[0],
    a[3]*b[2]+a[0]*b[1]-a[1]*b[0]+a[2]*b[3],
    a[3]*b[3]-a[0]*b[0]-a[1]*b[1]-a[2]*b[2]};
  memcpy(out,q,sizeof(q));
}
static inline void referee_upper_body(RefereeBonePose pose[REFEREE_ANIMATION_BONES],
    const RefereeBonePose gesture[REFEREE_ANIMATION_BONES],float weight) {
  const float inverse[4]={-gesture[0].rotation[0],-gesture[0].rotation[1],
                         -gesture[0].rotation[2],gesture[0].rotation[3]};
  float delta[4];referee_quat_product(delta,pose[0].rotation,inverse);
  const float inv_delta[4]={-delta[0],-delta[1],-delta[2],delta[3]};
  for (unsigned i=7;i<REFEREE_ANIMATION_BONES;++i) {
    RefereeBonePose aligned=gesture[i];
    float offset[4]={0},tmp[4];
    for (unsigned k=0;k<3;++k) offset[k]=gesture[i].position[k]-gesture[0].position[k];
    referee_quat_product(tmp,delta,offset);referee_quat_product(offset,tmp,inv_delta);
    for (unsigned k=0;k<3;++k) aligned.position[k]=pose[0].position[k]+offset[k];
    referee_quat_product(aligned.rotation,delta,gesture[i].rotation);
    referee_pose_blend(&pose[i],&pose[i],&aligned,weight);
  }
}
static inline void referee_gesture_whistle(RefereeGesture *g,unsigned restart) {
  // A native sound request is the timing authority, including restart whistles
  // with no new OutOfPlay record. Do not replay an already-raised hand from zero.
  // The baked stand-whistle raises its left hand during 0.2..0.7 s, holds it
  // by the face until ~1.2 s, then lowers it. A sound arriving late must not
  // leave the arm in the lowering tail. Timing is specific to this EF clip.
  if (g->clip!=4 || g->elapsed<0.70f || g->elapsed>1.15f) g->elapsed=0.70f;
  g->clip=4;
  g->next=(restart==4 || restart==5 || restart==6)?5:6;
}
static inline int referee_gesture_apply(const RefereeAnimationBank *bank,
                                        RefereeGesture *g,float dt,
                                        RefereeBonePose pose[REFEREE_ANIMATION_BONES]) {
  if (!bank->valid || bank->count<8 || g->clip<4 || g->clip>=8 ||
      !isfinite(dt) || dt<0) return 0;
  const RefereeClip *c=&bank->clips[g->clip];
  const float duration=(c->frames-1)/c->rate;
  g->elapsed+=fminf(dt,0.1f);
  const float frame=fminf(g->elapsed*c->rate,(float)c->frames-1);
  const unsigned first=(unsigned)frame,second=first+1<c->frames?first+1:first;
  // Adjacent EF signal clips are a sequence (whistle -> raise -> lower).
  // Fading back to locomotion between each stage made the arm dip/pop twice.
  // Blend in only at sequence entry, and out only after its final stage.
  const float fade_in=g->clip==4?g->elapsed/0.18f:1;
  const float fade_out=g->next?1:(duration-g->elapsed)/0.22f;
  const float fade=fmaxf(0,fminf(1,fminf(fade_in,fade_out)));
  RefereeBonePose gesture[REFEREE_ANIMATION_BONES];
  for (unsigned i=0;i<REFEREE_ANIMATION_BONES;++i) {
    referee_pose_blend(&gesture[i],&c->poses[first*REFEREE_ANIMATION_BONES+i],
                       &c->poses[second*REFEREE_ANIMATION_BONES+i],frame-first);
  }
  referee_upper_body(pose,gesture,fade);
  if (g->elapsed>=duration) {
    const unsigned finished=g->clip;
    g->clip=g->next;g->next=finished==4 && g->clip==5?7:0;g->elapsed=0;
  }
  return 1;
}
#endif
