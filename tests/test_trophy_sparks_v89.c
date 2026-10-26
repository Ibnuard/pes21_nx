#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <math.h>
static unsigned notes;
static void fixdemo_trophy_note(const char *text) { assert(text && strlen(text)<160); ++notes; }
#define PESNX_TROPHY_SPARKS_HOST_TEST
#include "../source/fixdemo_trophy_sparks.inc"
#include "../source/fixdemo_spark_owner.h"

static unsigned char world_a,world_b,podium_a,podium_b;
static unsigned char actor[0x160],component[0x700],podium_component[0x200];
static unsigned mesh_class,actor_class,component_class,mesh,material;
static unsigned loads,spawns,destroys,transforms,scalars,finished;
static unsigned alive,podium_alive=1,world_alive=1,material_alive=1,missing,failure;
static TrophySparkTransform current_pose={{0,0,.70710678f,.70710678f},{123,-456,12},{1,1,1}},spawned_pose;
static void *current_world=&world_a;

static void weak_set(TrophySparkWeak *weak,const void *value) {
  weak->serial=1;
  weak->index=value==&world_a?1:value==&world_b?2:value==&podium_a?3:
    value==&podium_b?4:value==actor?5:value==&material?6:value==podium_component?7:-1;
}
static void *weak_get(const TrophySparkWeak *weak) {
  if (weak->index==1 || weak->index==2) return world_alive?(weak->index==1?&world_a:&world_b):NULL;
  if (weak->index==3 || weak->index==4) return podium_alive?(weak->index==3?&podium_a:&podium_b):NULL;
  if (weak->index==5) return alive?actor:NULL;
  if (weak->index==6) return alive && material_alive?&material:NULL;
  if (weak->index==7) return podium_alive?podium_component:NULL;
  return NULL;
}
static void *get_mesh_class(void) { return &mesh_class; }
static void *get_actor_class(void) { return &actor_class; }
static void *get_component_class(void) { return &component_class; }
static void *load(void *kind,void *outer,const uint16_t *name,const uint16_t *file,
    uint32_t flags,void *map,int reconcile,void *context) {
  assert(kind==&mesh_class && !outer && !file && !flags && !map && reconcile==1 && !context);
  char narrow[100];unsigned i;
  for (i=0;name[i] && i<sizeof(narrow)-1;++i) narrow[i]=(char)name[i];
  narrow[i]=0;
  assert(!strcmp(narrow,"/Game/FootballNX/TrophySparks/PodiumSparks.PodiumSparks"));
  ++loads;return missing?NULL:&mesh;
}
static void *spawn(const void *world,void *kind,const TrophySparkTransform *pose,uint8_t collision,void *owner) {
  assert(world==current_world && kind==&actor_class && collision==1 && !owner);
  assert(((uintptr_t)pose&15u)==0);
  for (unsigned i=0;i<3;++i) assert(pose->scale[i]==1.f);
  spawned_pose=*pose;++spawns;
  if(failure==1) return NULL;
  alive=1;finished=0;
  void *part=component,*klass=failure==2?NULL:&component_class;
  memcpy(actor+0x158,&part,sizeof(part));memcpy(component+0x10,&klass,sizeof(klass));
  return actor;
}
static int destroy(void *value,int net,int level) {
  assert(value==actor && alive && !net && !level);alive=0;++destroys;return 1;
}
static int set_mesh(void *part,void *value) {
  assert(part==component && value==&mesh && !finished);return failure!=3;
}
static void mobility(void *part,uint32_t value) { assert(part==component && value==2 && !finished); }
static void collision(void *part,uint32_t value) { assert(part==component && value==0 && !finished); }
static void shadow(void *part,int value) { assert(part==component && value==0 && !finished); }
static void fname(uint64_t *value,const uint16_t *name,uint32_t add) {
  assert(name[0]=='S' && name[5]=='C' && add==1);*value=73;
}
static void *dynamic(void *part,int index,void *parent,uint64_t name) {
  assert(part==component && !index && !parent && !name && !finished);
  return failure==4?NULL:&material;
}
static void scalar(void *value,uint64_t name,float clock) {
  assert(value==&material && alive && name==73 && isfinite(clock) && clock>=0 && clock<4);
  ++scalars;
}
static void *finish(void *value,const TrophySparkTransform *pose) {
  assert(value==actor && !finished && !memcmp(pose,&spawned_pose,sizeof(*pose)));
  finished=1;return failure==5?NULL:value;
}
static TrophySparkTransform transform(const void *part) {
  assert(part==podium_component);++transforms;return current_pose;
}
static void observe(uint64_t epoch,uint64_t generation,uint64_t playing) {
  fixdemo_trophy_sparks_observe(epoch,generation,&podium_a,podium_component,playing);
}
static void tick(void *world,float seconds,uint64_t playing,int skip) {
  fixdemo_trophy_sparks_tick(world,seconds,trophy_sparks.epoch,playing,trophy_sparks.generation,skip);
}
int main(void) {
  trophy_spark_ops.weak_set=weak_set;trophy_spark_ops.weak_get=weak_get;
  trophy_spark_ops.world=&current_world;
  trophy_spark_ops.mesh_class=get_mesh_class;trophy_spark_ops.actor_class=get_actor_class;
  trophy_spark_ops.component_class=get_component_class;trophy_spark_ops.load=load;
  trophy_spark_ops.spawn=spawn;trophy_spark_ops.finish=finish;trophy_spark_ops.destroy=destroy;
  trophy_spark_ops.set_mesh=set_mesh;trophy_spark_ops.mobility=mobility;
  trophy_spark_ops.collision=collision;trophy_spark_ops.shadow=shadow;
  trophy_spark_ops.fname=fname;trophy_spark_ops.dynamic=dynamic;trophy_spark_ops.scalar=scalar;
  trophy_spark_ops.transform=transform;trophy_sparks.enabled=1;
  /* A loading/UI epoch is insufficient: no pointer access or allocation. */
  for(unsigned frame=0;frame<600;++frame) {
    observe(1,1,0);tick(current_world,.016f,0,0);
  }
  assert(!transforms && !loads && !spawns);
  observe(1,1,2);assert(!transforms);
  observe(1,1,1);assert(!transforms && !loads);
  /* One loading callback is enough; no callback is required after PLAYING.
   * Read the final weak component transform then, not its early loading pose. */
  for(unsigned frame=0;frame<300;++frame)tick(current_world,.016f,0,0);
  assert(!transforms && !loads && !spawns && trophy_sparks.observed);
  current_pose.location[0]=789;
  tick(current_world,.016f,1,0);
  assert(alive && spawns==1 && loads==1 && finished && spawned_pose.location[0]==789);
  const TrophySparkTransform fixed=spawned_pose;
  /* Camera/podium updates at later callbacks cannot move airborne particles.
   * No camera getter or SetWorldTransform operation exists in the binding. */
  for(unsigned frame=0;frame<600;++frame) {
    current_pose.location[0]=frame*10.f;
    observe(1,1,1);tick(current_world,.016f,1,0);
    assert(!memcmp(&spawned_pose,&fixed,sizeof(fixed)));
  }
  assert(transforms==1 && spawns==1 && trophy_sparks.clock<4 && trophy_sparks.reported);
  const unsigned calls=scalars;
  const float age=trophy_sparks.age;
  tick(current_world,NAN,1,0);
  tick(current_world,-1,1,0);
  tick(current_world,0,1,0);
  assert(calls==scalars && age==trophy_sparks.age);
  tick(current_world,.016f,1,1);
  assert(!alive && !trophy_sparks.epoch && destroys==1);
  fixdemo_trophy_sparks_reset();assert(destroys==1);
  /* Each optional failure rolls back once, never blocks readiness or retries. */
  for(failure=1;failure<=5;++failure) {
    unsigned before=spawns,removed=destroys;
    observe(2+failure,2+failure,2+failure);
    for(unsigned i=0;i<100;++i)tick(current_world,.016f,2+failure,0);
    assert(spawns==before+1 && !alive && destroys==removed+(failure!=1));
    fixdemo_trophy_sparks_reset();
  }
  failure=0;missing=1;unsigned before=loads;
  observe(10,10,10);
  for(unsigned i=0;i<300;++i) { observe(10,10,10);tick(current_world,.016f,10,0); }
  assert(loads==before+1 && !alive);fixdemo_trophy_sparks_reset();missing=0;
  /* Owner retirement, token replacement, invalid weak world and explicit
   * stadium unload all remove a live effect through its weak actor. */
  observe(11,11,11);tick(current_world,.016f,11,0);assert(alive);
  podium_alive=0;tick(current_world,.016f,11,0);assert(!alive);podium_alive=1;
  observe(12,12,12);tick(current_world,.016f,12,0);assert(alive);
  tick(current_world,.016f,13,0);assert(!alive);
  observe(13,13,13);tick(current_world,.016f,13,0);assert(alive);
  current_world=&world_b;tick(current_world,.016f,13,0);assert(!alive);
  observe(14,14,14);tick(current_world,.016f,14,0);assert(alive);
  world_alive=0;tick(current_world,.016f,14,0);assert(!alive);world_alive=1;
  observe(15,15,15);tick(current_world,.016f,15,0);assert(alive);
  before=spawns;observe(15,16,15);assert(!alive); /* Same address, new owner generation. */
  tick(current_world,.016f,15,0);assert(alive && spawns==before+1);
  fixdemo_trophy_sparks_reset();assert(!alive);
  /* Invalid actual transforms are a specific optional hold, not guessed pose. */
  before=spawns;current_pose.rotation[0]=NAN;observe(16,16,16);
  tick(current_world,.016f,16,0);assert(spawns==before && !alive);
  fixdemo_trophy_sparks_reset();current_pose.rotation[0]=0;
  /* The native prop's own scale is unchanged. Sparks retain physical cm. */
  current_pose.scale[0]=.01f;observe(17,17,17);tick(current_world,.016f,17,0);
  assert(alive && current_pose.scale[0]==.01f && spawned_pose.scale[0]==1.f);
  before=spawns;
  for(unsigned i=0;i<1200;++i)tick(current_world,.1f,17,0);
  assert(!alive && trophy_sparks.attempted);
  observe(17,17,17);tick(current_world,.016f,17,0);assert(spawns==before);
  fixdemo_trophy_sparks_reset();
  /* Cached UObjects may stay valid after native owner metadata retires. The
   * generation proof, rather than weak pointer validity, must then stop FX. */
  FixDemoPropLifecycle life={0};
  life.epoch=20;life.ready_mask=2;
  life.slots[1]=(FixDemoPropTicket){.epoch=20,.generation=99,.owner=1,.demo=2,.model=3,
      .ue=4,.key=5,.kind=2,.ready=1};
  assert(fixdemo_spark_owner_generation(&life,20)==99);
  assert(!fixdemo_spark_owner_generation(&life,19));
  life.lock=1;
  const FixDemoPropLifecycle locked=life;
  assert(!fixdemo_spark_owner_generation(&life,20));
  assert(!memcmp(&life,&locked,sizeof(life)) && !life.failed_epoch);
  life.lock=0;
  observe(20,99,20);
  fixdemo_trophy_sparks_tick(current_world,.016f,20,20,
      fixdemo_spark_owner_generation(&life,20),0);
  assert(alive && podium_alive && world_alive);
  fixdemo_prop_lifecycle_retire(&life,1,1);
  assert(!fixdemo_spark_owner_generation(&life,20));
  fixdemo_trophy_sparks_tick(current_world,.016f,20,20,
      fixdemo_spark_owner_generation(&life,20),0);
  assert(!alive && podium_alive); /* An actor cached by native code is still valid. */
  life.slots[1]=(FixDemoPropTicket){.epoch=20,.generation=100,.owner=1,.demo=2,.model=3,
      .ue=4,.key=5,.kind=2,.ready=1};life.ready_mask=2;life.failed_epoch=20;
  assert(!fixdemo_spark_owner_generation(&life,20));life.failed_epoch=0;
  observe(20,100,20);
  fixdemo_trophy_sparks_tick(current_world,.016f,0,0,100,0);
  assert(!trophy_sparks.epoch && !alive); /* Loading cancellation before any allocation. */
  puts("podium sparks: bounded native lifecycle, fixed pose and optional rollback passed");
  return 0;
}
