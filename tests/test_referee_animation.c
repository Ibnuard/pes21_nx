#include <assert.h>
#include "referee_animation_fixture.h"
static void check_pose(const RefereeBonePose pose[19]) {
  for(unsigned b=0;b<19;++b) {
    float norm=0;
    for(unsigned k=0;k<4;++k) {assert(isfinite(pose[b].rotation[k]));norm+=pose[b].rotation[k]*pose[b].rotation[k];}
    assert(fabsf(norm-1)<0.00001f && pose[b].position[3]==1);
  }
}
int main(void) {
  size_t size;unsigned char *data=referee_animation_fixture(&size);
  RefereeAnimationBank bank;assert(referee_animation_bind(&bank,data,size));
  fixture_word(data+8,1);assert(!referee_animation_bind(&bank,data,size));
  fixture_word(data+8,2);assert(referee_animation_bind(&bank,data,size));
  RefereeAnimationClock a={0},b={0};RefereeBonePose pose[19],other[19];
  for(unsigned i=0;i<300;++i)assert(referee_animation_step(&bank,&a,3.2f,1.0f/30,pose));
  for(unsigned i=0;i<600;++i)assert(referee_animation_step(&bank,&b,3.2f,1.0f/60,other));
  assert(fabs(a.gait_phase-b.gait_phase)<0.0001);check_pose(pose);check_pose(other);
  // Stops preserve cycle phase and blend into idle; resuming never restarts it.
  const double phase=a.gait_phase;
  for(unsigned i=0;i<90;++i)referee_animation_step(&bank,&a,0,1.0f/30,pose);
  assert(a.speed<0.001f && a.gait_phase==phase);
  referee_animation_step(&bank,&a,3.2f,0,pose);assert(a.gait_phase==phase);
  const RefereeAnimationClock held=a;
  assert(!referee_animation_step(&bank,&a,NAN,1.0f/30,pose));
  assert(!referee_animation_step(&bank,&a,1e30f,1.0f/30,pose));
  assert(!memcmp(&held,&a,sizeof(a)));
  // Large wall-clock gaps are capped; changing speeds does not reset phase.
  referee_animation_step(&bank,&a,1.4f,30,pose);check_pose(pose);
  RefereeBonePose p={.rotation={0,0,0,1},.position={0,1,0,1}},q=p,r;
  q.rotation[3]=-1;referee_pose_blend(&r,&p,&q,0.5f);assert(r.rotation[3]==1);
  // Loop-seam interpolation is continuous on either side of zero.
  referee_clip_sample(&bank.clips[2],0.999999,pose);
  referee_clip_sample(&bank.clips[2],0.000001,other);
  assert(fabsf(pose[0].rotation[0]-other[0].rotation[0])<0.0001f);
  for(size_t n=0;n<160;++n)assert(!referee_animation_bind(&bank,data,n));
  const unsigned offsets[]={0,8,12,16,20,24,32,36,40,44,48,160};
  for(unsigned i=0;i<sizeof(offsets)/sizeof(*offsets);++i) {
    data[offsets[i]]^=128;assert(!referee_animation_bind(&bank,data,size));data[offsets[i]]^=128;
  }
  // A valid checksum cannot authorize overlapping frames or near-zero speed
  // knots that would overflow playback frequency.
  unsigned char saved[160];memcpy(saved,data,160);
  const unsigned fields[]={32,36,48,64+12};
  const uint32_t invalid[]={601,0,1,0x00000001};
  for(unsigned i=0;i<4;++i) {
    memcpy(data+fields[i],&invalid[i],4);
    uint64_t digest=nx_asset_hash(data+32,size-32);memcpy(data+24,&digest,8);
    assert(!referee_animation_bind(&bank,data,size));memcpy(data,saved,160);
  }
  // Valid checksum cannot hide a NaN or invalid quaternion in a loose file.
  float nan=NAN;memcpy(data+160,&nan,4);
  uint64_t sum=nx_asset_hash(data+32,size-32);memcpy(data+24,&sum,8);
  assert(!referee_animation_bind(&bank,data,size));free(data);
  data=referee_animation_fixture_count(&size,8);
  assert(referee_animation_bind(&bank,data,size)&&bank.count==8);
  fixture_word(data+8,2);assert(!referee_animation_bind(&bank,data,size));
  fixture_word(data+8,3);assert(referee_animation_bind(&bank,data,size));
  float moving=1;memcpy(data+32+4*32+12,&moving,4);
  sum=nx_asset_hash(data+32,size-32);memcpy(data+24,&sum,8);
  assert(!referee_animation_bind(&bank,data,size)); // Gestures cannot enter the speed blend knots.
  moving=0;memcpy(data+32+4*32+12,&moving,4);
  sum=nx_asset_hash(data+32,size-32);memcpy(data+24,&sum,8);
  assert(referee_animation_bind(&bank,data,size));
  RefereeGesture gesture={0};
  referee_gesture_start(&gesture,1,5,5);assert(gesture.clip==4&&gesture.next==5);
  const unsigned expected[]={4,5,7};
  for(unsigned n=0;n<3;++n) {
    assert(gesture.clip==expected[n]);
    for(unsigned i=0;i<4;++i) {
      referee_animation_step(&bank,&a,0,0.025f,pose);
      referee_gesture_apply(&bank,&gesture,0.025f,pose);check_pose(pose);
    }
  }
  assert(!gesture.clip);
  referee_gesture_start(&gesture,1,5,5);assert(!gesture.clip); // Held event cannot loop.
  referee_gesture_start(&gesture,2,2,4);assert(gesture.clip==4&&gesture.next==6);
  RefereeGesture snapshot=gesture;
  assert(!referee_gesture_apply(&bank,&gesture,NAN,pose));
  assert(!memcmp(&gesture,&snapshot,sizeof(gesture)));
  referee_gesture_start(&gesture,3,1,0);assert(gesture.serial==3&&!gesture.clip); // Kickoff cancels old gestures.
  // Pointing clips may contain walking feet. A signal must never substitute
  // those legs for the actor's actual gait, including at rest.
  referee_animation_step(&bank,&a,3.2f,.03f,pose);memcpy(other,pose,sizeof(pose));
  referee_gesture_start(&gesture,4,4,4);assert(gesture.next==5);
  referee_gesture_apply(&bank,&gesture,.03f,pose);
  assert(!memcmp(pose,other,7*sizeof(*pose)));check_pose(pose);
  referee_gesture_whistle(&gesture,5);assert(gesture.clip==4 && gesture.elapsed>=.70f);
  gesture.elapsed=1.9f;referee_gesture_whistle(&gesture,4);
  assert(gesture.elapsed==.70f && gesture.next==5); // Cue during the lowering tail.
  // Pelvis alignment translates upper-body bones with the moving character.
  RefereeBonePose translated[19];memcpy(translated,other,sizeof(translated));
  for(unsigned i=0;i<19;++i)translated[i].position[0]+=1;
  referee_upper_body(translated,other,1);
  for(unsigned i=0;i<19;++i)assert(fabsf(translated[i].position[0]-other[i].position[0]-1)<.0001f);
  free(data);
  puts("independent referee animation and one-shot events: pass");return 0;
}
