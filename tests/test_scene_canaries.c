/* Execute optional runtime paths against bounded, lifetime-aware host objects. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct { void *data; int32_t num,max; } Ue4Array;
static uint32_t selected;
uint32_t pes_controller_2p_prematch_hub_stadium_index(void) { return selected; }
#define PESNX_STADIUM_CANARY_HOST_TEST
#include "../source/stadium_canary.inc"
static unsigned char actor[4][0x180], component[4][0x600], mesh[5][128];
static int hidden[4], forwarded, have_asset=1, class_token, reject_mesh;
static int transaction, release_stage, transactions, stale_indices=1;
static unsigned mobility;
static void *world=(void*)1;
static void *klass(void) { return &class_token; }
static void original(void *p) { (void)p; forwarded++; }
static void actors(const void *w,void *c,Ue4Array *a) {
  assert(w==world && c==&class_token);
  a->data=malloc(4*sizeof(void*)); a->num=a->max=4;
  for(int i=0;i<4;i++) ((void**)a->data)[i]=actor[i];
}
static void name(const void *n,Ue4Array *s) {
  const char *text=n; s->num=s->max=(int32_t)strlen(text)+1;
  s->data=calloc((size_t)s->num,2);
  for(int i=0;i<s->num;i++) ((uint16_t*)s->data)[i]=(uint8_t)text[i];
}
static void *load(void *c,void *o,const uint16_t *p,const uint16_t *f,
                   uint32_t flags,void *map,int reconcile,void *context) {
  assert(c==&class_token && !o && !f && !flags && !map && reconcile && !context);
  if(!have_asset)return NULL;
  return p[6]=='F' ? mesh[4] : mesh[0];
}
static int set_mesh(void *c,void *m) {
  assert(transaction && release_stage==0);
  if(reject_mesh)return 0;
  *(void**)((char*)c+0x5b0)=m;return 1;
}
static void hide(void *a,int value) {
  for(int i=0;i<4;i++) if(a==actor[i])hidden[i]=value;
}
static void component_call(void *c) { assert(c==component[0]); }
static void component_mode(void *c,uint32_t mode) {(void)mode;component_call(c);}
static void set_mobility(void *c,uint32_t mode) {component_call(c);mobility=mode;}
static void cast(void *c,int value) { assert(!value);component_call(c); }
static void unregister_context(void *context,void *c) {
  component_call(c);assert(!transaction && !((uintptr_t)context%16));
  transaction=1;release_stage=0;*(void**)context=c;
}
static void release_resources(void *c) {
  component_call(c);assert(transaction && release_stage==0);release_stage=1;
}
static void flush_resources(int log) {
  assert(!log && transaction && release_stage==1);release_stage=2;
}
static int clear_lods(void *c,uint32_t low,uint32_t high) {
  component_call(c);assert(transaction && release_stage==2 && !low && !high);
  stale_indices=0;release_stage=3;return 1;
}
static void reset_lod(void *c,int lod) {component_call(c);assert(!lod && release_stage==3);}
static void register_context(void *context) {
  assert(transaction && *(void**)context==component[0]);
  assert(reject_mesh ? release_stage==0 : release_stage==3 && !stale_indices);
  transaction=0;transactions++;
}
static void stadium_test(void) {
  const char *names[] = {"st029_b","st029_pitch_2","st029_audi_b","mobile_goal_L","AnfieldShell"};
  for(int i=0;i<5;i++)strcpy((char*)mesh[i]+0x18,names[i]);
  for(int i=0;i<4;i++) {
    *(void**)(actor[i]+0x158)=component[i];
    *(void**)(component[i]+0x10)=&class_token;
    *(void**)(component[i]+0x5b0)=mesh[i];
  }
  stadium_loaded_original=original;stadium_world=&world;
  stadium_actor_class=stadium_mesh_class=stadium_component_class=klass;
  stadium_get_actors=actors;stadium_fname_string=name;stadium_engine_free=free;
  stadium_load_object=load;stadium_set_mesh=set_mesh;stadium_hide_actor=hide;
  stadium_empty_materials=component_call;stadium_set_mobility=set_mobility;
  stadium_set_collision=component_mode;stadium_set_cast_shadow=cast;
  stadium_reregister_begin=unregister_context;stadium_reregister_end=register_context;
  stadium_release_resources=release_resources;stadium_flush_rendering=flush_resources;
  stadium_set_lod_count=clear_lods;stadium_set_forced_lod=reset_lod;
  assert(pes_controller_stadium_catalog_count()==1);
  stadium_canary_installed=1; assert(pes_controller_stadium_catalog_count()==2);
  selected=1; have_asset=0; stadium_loaded_canary(NULL);
  assert(!hidden[2] && !pes_controller_stadium_canary_active());
  assert(!transactions && stale_indices);
  have_asset=1;reject_mesh=1;stadium_loaded_canary(NULL);
  assert(!transaction && transactions==1 && stale_indices && !hidden[2]);
  assert(*(void**)(component[0]+0x5b0)==mesh[0]);
  reject_mesh=0;
  have_asset=1;stadium_loaded_canary(NULL);
  assert(pes_controller_stadium_canary_active()==1 && hidden[2]);
  assert(!hidden[0] && !hidden[1] && !hidden[3]);
  assert(*(void**)(component[0]+0x5b0)==mesh[4]);
  assert(mobility==0);
  const int installed_transactions=transactions;
  stadium_loaded_canary(NULL);
  assert(transactions==installed_transactions && pes_controller_stadium_canary_active());
  selected=0;stadium_loaded_canary(NULL);
  assert(!hidden[2] && !pes_controller_stadium_canary_active());
  assert(*(void**)(component[0]+0x5b0)==mesh[0]);
  selected=1;*(void**)(component[0]+0x10)=(void*)2;
  stadium_loaded_canary(NULL);assert(!pes_controller_stadium_canary_active());
  assert(forwarded==6 && transactions==3 && !transaction);
  assert(!stadium_shell_member("st029_pitch_2") && !stadium_shell_member("flag"));
  assert(stadium_shell_member("st029_c") && stadium_shell_member("pitch_side_nf2"));
}

static void *exhibition_get_tmpdb_match(void) { return (void*)1; }
uint32_t pes_controller_stadium_weather(void) { return 1; }
uint32_t pes_controller_stadium_season(void) { return 0; }
static uint64_t ticks=1000000000, stamp=1;
static int inplay=2;
static uint64_t armGetSystemTick(void) { return ticks; }
static uint64_t armTicksToNs(uint64_t n) { return n; }
static int referee_probe_scene_active(void) { return inplay; }
static int referee_probe_restart_active(void) { return 0; }
#define PESNX_REFEREE_PROBE_HOST_TEST
#include "../source/referee_probe.inc"
#include "referee_animation_fixture.h"
static unsigned char human[22][0x820], animation[22][0x940];
static unsigned char registry_data[0xa0], move_data[22][0x580];
static float ball_data[3]={35,0,5};
static _Alignas(16) RefereeBonePose bone_storage[20];
static int registry_available=1;
static RefereeProbeVector last_position;
static int creations,deleted,drawn,updates,displayed,ready=1,released,display_calls;
static int published, load_groups_alive=1;
static int in_draw, native_loaded=1, player_creates, original_result=1,uniform_busy;
static unsigned sound_calls;
static void sound_original(const void *self,uint64_t handle,const uint8_t *command,
                           uint32_t arg,const void *registry,uint32_t player) {
  assert(self==(void*)3 && command && registry==(void*)4 && player==22);
  (void)handle;(void)arg;++sound_calls;
}
static RefereeProbeLoadId load_id(uint32_t k,uint32_t id,uint32_t w,uint32_t s) {
  assert(k==0 && id==1 && w==0 && s==0);return (RefereeProbeLoadId){{0}};
}
static uint32_t get_id(void *m,uint32_t i) {assert(m==(void*)1 && i==0);return 0;}
static void *allocate(size_t n) {assert(n==0x448);creations++;return calloc(1,n);}
static void constructor(void *p,uint32_t k,const RefereeProbeLoadId *id) {assert(p && k==2 && id && !in_draw);}
static void destroy(void *p) {assert(!referee_probe_model && load_groups_alive);deleted++;free(p);}
static int init(void *p) {
  assert(!in_draw);
  if(ready) {*(void**)((char*)p+0x440)=(void*)1;*(void**)((char*)p+0x418)=bone_storage;*(void**)((char*)p+0x420)=bone_storage+20;}
  return ready;
}
static float root_scale(const void *p) {assert(p==(char*)referee_probe_model+0x10);return 1.0f;}
static void update(void *p,const RefereeProbeVector *v,float a,const RefereeProbeVector *o) {
  assert(p && v->y==0 && isfinite(a) && !o->x);
  assert(fabsf(v->x)<=46 && fabsf(v->z)<=28);last_position=*v;updates++;
}
static void display(void *p,int visible) {assert(p);displayed=visible;display_calls++;}
static void draw(void *p) {assert(p);drawn+=22;}
static int create_player(void *p,const RefereeProbeLoadId *id) {
  assert(p && id);player_creates++;return original_result;
}
static int all_loaded(void *m) {assert(m==(void*)1 && !in_draw);return native_loaded;}
static int uniforms_busy(void) {return uniform_busy;}
static void loaded_scene(void *p) {
  (void)p;assert(!referee_probe_scene_ready && referee_probe_scene_loading);
  const int previous=creations;
  // Emulate the Fox loading barrier while UE is still applying the shell.
  assert(!referee_probe_all_loaded((void*)1) && creations==previous);
}
static void out_record(void *r,const void *g,const void *j) {(void)r;(void)g;assert(j);}
static void lod(void *p,uint32_t level,float near,float far) {assert(p && level==2 && near==0 && far==0 && !in_draw);}
static void release(void *p) {assert(!referee_probe_model);(void)p;released++;}
static void release_animation(void) {assert(!referee_probe_model);load_groups_alive=0;}
static int create_manager(void) {load_groups_alive=1;return 1;}
static void publish(void *v,const void *b) {
  assert(v==(void*)1 && b==(char*)referee_probe_model+0x410);published++;
  assert(bone_storage[19].rotation[3]==1 && bone_storage[19].position[3]==1);
}
static void *get_registry(void) {return registry_available?registry_data:NULL;}
static const void *player_move(const void *r,uint32_t p) {
  assert(r==registry_data && p<22);return move_data[p];
}
static const float *ball_trans(const void *b) {assert(b==ball_data);return ball_data;}
static uint64_t frame_stamp(void) {return stamp;}
static void frame(void) {
  ++stamp;ticks+=33333333;
  const int before=published, before_display=display_calls;
  in_draw=1;
  referee_probe_draw(human);
  referee_probe_draw(human); // Duplicate listener in one upload frame.
  in_draw=0;
  assert(published-before<=1);
  assert(display_calls-before_display<=2); // At most one early hide + first pose.
}
static void preload(void) {
  RefereeProbeLoadId id={{0}};
  for (int i=0;i<22;i++) assert(referee_probe_create_model(human[i],&id)==original_result);
  assert(referee_probe_all_loaded((void*)1)==(native_loaded&&!uniform_busy));
}
static void referee_test(void) {
  referee_create_id=load_id;referee_get_id=get_id;referee_new=allocate;
  referee_ctor=constructor;referee_delete=destroy;referee_init=init;
  referee_root_scale=root_scale;referee_update=update;referee_display=display;
  referee_create_model_original=create_player;referee_all_loaded_original=all_loaded;
  referee_uniform_busy=uniforms_busy;
  referee_loaded_original=loaded_scene;referee_out_original=out_record;
  referee_sound_original=sound_original;
  referee_set_lod=lod;
  referee_draw_original=draw;referee_release_original=referee_unload_original=release;
  referee_registry=get_registry;referee_player_move=player_move;
  referee_ball_trans=ball_trans;referee_frame_stamp=frame_stamp;
  referee_publish_bones=publish;
  referee_animation_release_original=release_animation;
  referee_manager_create_original=create_manager;
  referee_destroy_loader_original=release;
  size_t animation_size;unsigned char *animation_data=referee_animation_fixture_count(&animation_size,8);
  assert(referee_animation_bind(&referee_animation_bank,animation_data,animation_size));
  *(void**)(registry_data+0x90)=ball_data;
  for(int i=0;i<22;i++) {
    *(uint32_t*)(human[i]+0x18)=(uint32_t)i;
    *(void**)(human[i]+0x7e0)=animation[i];
    animation[i][0x918]=animation[i][0x919]=1;
    RefereeNativeVector p={-45+(float)i*4,0,-30};
    memcpy(move_data[i]+0x55c,&p,sizeof(p));
  }
  // All donor visibility bytes are zero: off-screen players still have a pose,
  // and must not hide the independent referee model.
  referee_probe_draw(human);assert(drawn==22 && !creations);
  referee_probe_enabled=1;
  frame();assert(!creations); // A draw can never enqueue a new model.
  preload();assert(!creations); // Native preview barrier before stadium is unaffected.
  referee_probe_loaded_scene(NULL);player_creates=0;
  native_loaded=0;
  preload();assert(!creations && !displayed && !published && player_creates==22);
  frame();assert(!published && !updates && referee_probe_pending);
  assert(!referee_probe_all_loaded((void*)1));native_loaded=1;
  assert(referee_probe_all_loaded((void*)1) && !referee_probe_pending);
  unsigned char players_before[sizeof(human)];memcpy(players_before,human,sizeof(human));
  for(int i=0;i<300;i++)frame();
  assert(!memcmp(players_before,human,sizeof(human))); // Referee cannot mutate players.
  assert(creations==1 && published==300 && updates==300 && displayed);
  assert(display_calls==2); // One hide at load, one show: no per-frame queue churn.
  assert(last_position.x>18 && referee_motion.distance>15 && referee_probe_moved);
  const RefereeProbeVector before=last_position;
  int old_published=published,old_updates=updates;
  const int visible_commands=display_calls;
  inplay=0;for(int i=0;i<100;i++)frame();
  assert(display_calls==visible_commands+1);
  assert(!displayed && old_published==published && old_updates==updates);
  inplay=2;frame();assert(fabsf(last_position.x-before.x)<0.0001f);
  inplay=1;frame();assert(displayed); // A visible pause/replay holds the pose.
  inplay=2;frame();assert(fabsf(last_position.x-before.x)<0.0001f);
  // A temporary registry handover holds the last pose and position.
  registry_available=0;frame();assert(displayed); // Brief registry gap cannot blink.
  registry_available=1;frame();assert(displayed);
  // Pose playback keeps running even when every player anime pointer vanishes.
  for(int i=0;i<22;i++)*(void**)(human[i]+0x7e0)=NULL;
  old_published=published;for(int i=0;i<12;i++)frame();
  assert(published==old_published+12 && displayed);
  referee_probe_unload(NULL);assert(deleted==1 && released==1);
  for(int i=0;i<22;i++)frame();
  assert(creations==1); // Late draw callbacks during teardown cannot respawn.
  referee_probe_manager_create();
  referee_probe_loaded_scene(NULL);
  ready=0;
  RefereeProbeLoadId id={{0}};
  referee_probe_create_model(human[0],&id);
  assert(!referee_probe_all_loaded((void*)1));
  for(int i=0;i<650;i++) {
    ticks+=33333333;
    referee_probe_all_loaded((void*)1);
    frame();
  }
  assert(referee_probe_all_loaded((void*)1)); // Optional timeout never blocks play.
  assert(creations==2 && deleted==2 && referee_probe_failed && !referee_probe_model);
  referee_probe_release(NULL);ready=1;referee_probe_manager_create();referee_probe_loaded_scene(NULL);
  preload();frame();assert(creations==3 && referee_probe_ready);
  referee_probe_animation_release(); // Must precede native load-group death.
  frame();assert(creations==3 && deleted==3 && !load_groups_alive);
  referee_probe_release(NULL);assert(deleted==3 && released==3);
  referee_probe_manager_create();referee_probe_loaded_scene(NULL);preload();frame();
  assert(creations==4 && displayed);
  // Idempotent manager creation and new native players during events cannot
  // destroy/reload the follower or reset its world position.
  const void *same_model=referee_probe_model;
  const RefereePoint same_position=referee_motion.position;
  referee_probe_manager_create();preload();
  assert(referee_probe_model==same_model && creations==4 && deleted==3);
  assert(referee_motion.position.x==same_position.x && referee_motion.position.z==same_position.z);
  // A stadium load is the fallback boundary even if no exit callback arrived.
  referee_probe_loaded_scene(NULL);assert(deleted==4 && load_groups_alive);
  preload();frame();assert(creations==5 && displayed);
  referee_probe_destroy_loader(NULL);assert(deleted==5);
  frame();assert(creations==5);
  referee_probe_manager_create();referee_probe_loaded_scene(NULL);
  uniform_busy=1;preload();frame();assert(creations==5 && !displayed);
  uniform_busy=0;assert(referee_probe_all_loaded((void*)1));frame();assert(displayed);
  unsigned char judge[0x30]={0};uint32_t kind=5,reason=5;
  uint32_t event_record[16]={0x24,100,100,0,2};
  memcpy(judge,&kind,4);memcpy(judge+0x20,&reason,4);
  referee_probe_out_of_play(event_record+5,NULL,judge);
  assert((referee_probe_event>>32)==1 && (referee_probe_event&0xffff)==0x505);
  const RefereePoint event_position=referee_motion.position;
  frame();assert(displayed && referee_gesture.clip==4 && referee_gesture.next==5);
  frame();
  const float event_step=hypotf(referee_motion.position.x-event_position.x,referee_motion.position.z-event_position.z);
  assert(event_step>0 && event_step<5.8f/30+.001f); // Gesture cannot stop moving feet.
  inplay=1;const float elapsed=referee_gesture.elapsed;
  for(int i=0;i<60;i++)frame();
  assert(displayed && referee_gesture.elapsed==elapsed); // Pause doesn't consume a gesture.
  inplay=2;frame();assert(referee_gesture.elapsed==elapsed);
  for(int i=0;i<20;i++)frame();
  assert(displayed && !referee_gesture.clip && creations==6 && deleted==5);
  referee_probe_out_of_play(event_record+5,NULL,judge);assert((referee_probe_event>>32)==1);
  event_record[1]++;
  referee_probe_out_of_play(event_record+5,NULL,judge);assert((referee_probe_event>>32)==2);
  // Native referee-position audio triggers one mouth gesture, while every
  // command is forwarded exactly once. Ball/player audio cannot trigger it.
  uint8_t command=0x4e;
  referee_probe_sound((void*)3,20,&command,0x1d,(void*)4,22);
  command=0x4f;
  referee_probe_sound((void*)3,20,&command,0x18,(void*)4,22);
  referee_probe_sound((void*)3,0,&command,0x1d,(void*)4,22);
  assert(!referee_probe_whistle_serial && sound_calls==3);
  referee_probe_sound((void*)3,20,&command,0x1d,(void*)4,22);
  referee_probe_sound((void*)3,20,&command,0x1d,(void*)4,22);
  frame();assert(referee_probe_whistle_serial==1 && referee_probe_whistle_seen==1);
  assert(referee_gesture.clip==6); // Synthetic whistle is only 0.1 s long.
  referee_probe_sound((void*)3,21,&command,0x1d,(void*)4,22);
  assert(sound_calls==6 && referee_probe_whistle_serial==2);
  inplay=1;frame();assert(referee_probe_whistle_seen==2);
  // The model stays loaded and its animation clock advances during a goal.
  inplay=2;for(int i=0;i<240;i++)frame();
  inplay=3;frame();const float goal_distance=referee_motion.distance;
  const int goal_frames=published;
  for(int i=0;i<90;i++)frame();
  assert(displayed && published==goal_frames+90 && referee_motion.distance>goal_distance+.1f);
  assert(creations==6 && deleted==5 && referee_motion.restart==8);
  inplay=2;
  referee_probe_animation_release();referee_probe_release(NULL);
  assert(deleted==6);
  // A stuck optional uniform preflight must not strand a native-ready match.
  referee_probe_manager_create();referee_probe_loaded_scene(NULL);
  uniform_busy=1;preload();assert(creations==6);
  ticks+=21000000000ull;
  assert(referee_probe_all_loaded((void*)1) && referee_probe_failed && !referee_probe_pending);
  assert(creations==6 && !referee_probe_model);
  uniform_busy=0;referee_probe_release(NULL);
  free(animation_data);referee_animation_bank=(RefereeAnimationBank){0};
}
static void motion_test(void) {
  RefereeMotion slow={0},fast={0};
  const RefereePoint target={40,20};
  for(int i=0;i<300;i++) {
    RefereePoint previous=slow.position;
    referee_motion_step(&slow,target,NULL,0,1.0f/30);
    if(i)assert(hypotf(slow.position.x-previous.x,slow.position.z-previous.z)<=5.8f/30+0.001f);
  }
  for(int i=0;i<600;i++)referee_motion_step(&fast,target,NULL,0,1.0f/60);
  assert(hypotf(slow.position.x-fast.position.x,slow.position.z-fast.position.z)<0.01f);
  RefereeMotion invalid=slow;
  assert(!referee_motion_step(&slow,(RefereePoint){NAN,0},NULL,0,1.0f/30));
  assert(!memcmp(&slow,&invalid,sizeof(slow)));
  RefereePoint previous=slow.position;
  referee_motion_step(&slow,(RefereePoint){-100,100},NULL,0,90);
  assert(hypotf(slow.position.x-previous.x,slow.position.z-previous.z)<=0.581f);
  RefereeMotion avoid={0};referee_motion_reset(&avoid);
  const RefereePoint obstacle=avoid.position;
  for(int i=0;i<90;i++)referee_motion_step(&avoid,(RefereePoint){0,0},&obstacle,1,1.0f/30);
  assert(hypotf(avoid.position.x-obstacle.x,avoid.position.z-obstacle.z)>1);
  for(int i=0;i<1800;i++) {
    referee_motion_step(&slow,(RefereePoint){i%2?800:-800,800},NULL,0,1.0f/30);
    assert(fabsf(slow.position.x)<=46 && fabsf(slow.position.z)<=28);
    assert(hypotf(slow.velocity.x,slow.velocity.z)<=5.801f && isfinite(slow.heading));
  }

}
int main(void) { stadium_test();motion_test();referee_test();puts("scene canaries: pass");return 0; }
