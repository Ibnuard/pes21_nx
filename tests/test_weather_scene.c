#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <math.h>
#include <stddef.h>
static uint32_t weather_scene_kind;
static int pause_mode,camera_obj,asset_obj,material_obj,finished,scalar_calls,location_calls;
static int failure;
static unsigned char actor_obj[0x160];
static unsigned char component_obj[0x780];
static unsigned char world_obj[0x440];
static int alive,spawn_count,destroy_count,load_count,tick_count,native_exits,missing;
static int live_ready=1,first_begin,first_return;
static int pes_controller_pause_skin_active(void){return pause_mode;}
static int pes_controller_pause_transition(void){return 0;}
static int pes_controller_match_hud_inplay(void){return live_ready;}
static void scene_runtime_note(const char *a,const char *b){
 (void)a;
 if(!strcmp(b,"first native world tick after spawn begin"))++first_begin;
 if(!strcmp(b,"first native world tick after spawn returned"))++first_return;
}
#define PESNX_WEATHER_SCENE_HOST_TEST
#include "../source/weather_scene.inc"
static void weak_set(NxWeatherWeak *w,const void *p){w->index=p==&world_obj?1:p==&component_obj?2:p==&actor_obj?3:p==&material_obj?4:-1;w->serial=1;}
static void *weak_get(const NxWeatherWeak *w){return w->index==1?(void*)world_obj:alive?(w->index==2?(void*)component_obj:w->index==3?(void*)actor_obj:w->index==4?&material_obj:NULL):NULL;}
static void native_loaded(void *p){(void)p;}
static void native_exit(void *p){(void)p;assert(!alive);++native_exits;}
static void native_tick(void *p,int t,float dt){(void)p;(void)t;(void)dt;++tick_count;}
static void *get_class(void){return &asset_obj;}
static void *load_asset(void *c,void *o,const uint16_t *n,const uint16_t *f,uint32_t flags,void *m,int r,void *ctx){
 (void)c;(void)o;(void)f;(void)flags;(void)m;(void)r;(void)ctx;assert(n[0]=='/');++load_count;return missing?NULL:&asset_obj;
}
static void *spawn_asset(const void *w,void *a,const NxWeatherTransform *tr,uint8_t collision,void *owner){
 assert(w==&world_obj&&a==&asset_obj&&collision==1&&!owner&&tr->rotation[3]==1&&tr->scale[0]==1);
 assert(((uintptr_t)tr&15)==0);++spawn_count;
 if(failure==1)return NULL;
 alive=1;finished=0;
 void *c=&component_obj,*k=failure==2?NULL:&asset_obj;
 memcpy(actor_obj+0x158,&c,8);memcpy(component_obj+0x10,&k,8);
 return actor_obj;
}
static int mesh(void *c,void *a){assert(c==component_obj&&a==&asset_obj&&!finished);return failure!=3;}
static void mobility(void *c,uint32_t mode){assert(c==component_obj&&mode==2&&!finished);}
static void collision(void *c,uint32_t mode){assert(c==component_obj&&!mode&&!finished);}
static void shadow(void *c,int cast){assert(c==component_obj&&!cast&&!finished);}
static void fname(uint64_t *n,const uint16_t *name,uint32_t mode){assert(name[0]=='W'&&mode==1);*n=42;}
static void *dynamic(void *c,int slot,void *parent,uint64_t name){
 assert(c==component_obj&&!slot&&!parent&&!name&&!finished);return failure==4?NULL:&material_obj;
}
static void scalar(void *m,uint64_t name,float value){
 assert(alive&&m==&material_obj&&name==42&&isfinite(value)&&value>=0&&value<24);++scalar_calls;
}
static void *finish(void *a,const NxWeatherTransform *t){
 assert(a==actor_obj&&t->scale[1]==1&&!finished);finished=1;return failure==5?NULL:a;
}
static void *camera(const void *w,int id){assert(w==&world_obj&&!id);return &camera_obj;}
static NxWeatherVec eye(const void *c){assert(c==&camera_obj);return (NxWeatherVec){0,-9000,8000};}
static NxWeatherVec angle(const void *c){assert(c==&camera_obj);return (NxWeatherVec){-45,90,0};}
static void location(void *c,const NxWeatherVec *p,const NxWeatherVec *r){assert(c==&component_obj&&fabsf(p->x)<=4000&&fabsf(p->y)<=2500&&!r->z);++location_calls;}
static int destroy(void *a,int net,int level){assert(a==actor_obj&&!net&&!level&&alive);alive=0;++destroy_count;return 1;}
int main(void){
 weather_actor_class=weather_mesh_class=weather_component_class=get_class;
 weather_finish=finish;weather_destroy_actor=destroy;weather_set_mesh=mesh;
 weather_mobility=mobility;weather_collision=collision;weather_shadow=shadow;
 weather_fname=fname;weather_dynamic_material=dynamic;weather_scalar=scalar;
 weather_weak_set=weak_set;weather_weak_get=weak_get;
 weather_loaded_original=native_loaded;weather_unload_original=weather_destroy_original=native_exit;
 weather_tick_original=native_tick;void *world=&world_obj;weather_world=&world;
 weather_load=load_asset;weather_spawn=spawn_asset;
 weather_camera=camera;weather_camera_position=eye;weather_camera_angles=angle;
 weather_location=location;
 /* Model the actual Android callee's offsets, not the C declaration. */
 NxWeatherTransform tr={{0,0,0,1},{12,34,56},{1,1,1}};
 float scale[3];memcpy(scale,(const char *)&tr+0x1c,12);
 assert(sizeof(tr)==40&&scale[0]==1&&scale[1]==1&&scale[2]==1);
 for(int match=0;match<60;++match){
   weather_scene_kind=match%3;weather_scene_loaded(NULL);
   const int before=spawn_count;
   for(int frame=0;frame<30;++frame){pause_mode=frame>=10&&frame<20;weather_scene_tick(world,0,1.f/60);}
   assert(spawn_count==before+(weather_scene_kind!=0));
   if(match%2)weather_scene_unload(NULL);else weather_scene_destroy(NULL);
   assert(!weather_scene_first_tick);
   weather_scene_tick(world,0,1.f/60);assert(!alive);
 }
 assert(spawn_count==destroy_count&&native_exits==60&&tick_count==1860);
 assert(first_begin==40&&first_return==40);
 assert(location_calls==0); // Stable camera does not enqueue transform updates.
 /* LoadedCall can precede player/uniform readiness by an arbitrary duration.
  * No weather asset allocation is allowed during that interval, even on a
  * later match with an FX system left alive by UE. */
 weather_scene_kind=1;live_ready=0;pause_mode=0;weather_scene_loaded(NULL);
 const int load_before=load_count,spawn_before=spawn_count;
 for(int i=0;i<1800;++i)weather_scene_tick(world,0,1.f/60);
 assert(load_count==load_before&&spawn_count==spawn_before);
 assert(!weather_scene_attempted&&!alive&&weather_scene_age==0);
 live_ready=1;pause_mode=1;weather_scene_tick(world,0,1.f/60);
 assert(!weather_scene_attempted&&!alive);
 pause_mode=0;weather_scene_tick(world,0,1.f/60);
 assert(alive&&spawn_count==spawn_before+1&&!weather_scene_first_tick);
 /* Readiness is an initial-spawn gate, not a visibility toggle for replay. */
 live_ready=0;
 for(int i=0;i<40;++i)weather_scene_tick(world,0,1.f/60);
 assert(alive&&spawn_count==spawn_before+1&&weather_scene_first_tick);
 assert(first_begin==41&&first_return==41);
 weather_scene_destroy(NULL);
 weather_scene_loaded(NULL);weather_scene_tick(world,0,1.f/60);
 assert(!alive&&!weather_scene_attempted); // Fresh match must wait again.
 weather_scene_destroy(NULL);live_ready=1;
 missing=1;weather_scene_kind=1;weather_scene_loaded(NULL);const int before=load_count;
 for(int i=0;i<50;i++)weather_scene_tick(world,0,.016f);
 assert(load_count==before+1&&!alive);weather_scene_destroy(NULL);
 missing=0;weather_scene_loaded(NULL);weather_scene_tick(world,0,.016f);
 alive=0; /* GC invalidates a weak component; no stale destroy/deref. */
 weather_scene_destroy(NULL);assert(!weather_scene_active);
 pause_mode=0;weather_scene_loaded(NULL);
 for(int i=0;i<600;i++)weather_scene_tick(world,0,1.f/60);
 assert(weather_scene_reports==2);
 pause_mode=1;const float age=weather_scene_age,clock=weather_clock;const int scalars=scalar_calls;
 for(int i=0;i<300;i++)weather_scene_tick(world,0,1.f/60);
 assert(weather_scene_age==age&&weather_clock==clock&&scalar_calls==scalars);
 weather_scene_destroy(NULL);assert(!weather_scene_reports&&weather_scene_age==0);
 /* Roll back each partial actor setup, once per match. Never retry per tick. */
 pause_mode=0;
 for(failure=1;failure<=5;++failure){
   weather_scene_loaded(NULL);const int attempts=spawn_count,removed=destroy_count;
   for(int i=0;i<100;++i)weather_scene_tick(world,0,1.f/60);
   assert(spawn_count==attempts+1&&!alive);
   assert(destroy_count==removed+(failure!=1));
   weather_scene_destroy(NULL);
 }
 failure=0;weather_scene_loaded(NULL);
 for(int i=0;i<24000;++i)weather_scene_tick(world,0,1.f/60);
 assert(weather_clock<24&&weather_scene_reports==2);
 const float valid_clock=weather_clock;
 weather_scene_tick(world,0,NAN);weather_scene_tick(world,0,-1);
 assert(weather_clock==valid_clock);
 weather_scene_destroy(NULL);
 puts("weather lifecycle: deferred allocation, repeated matches, replay/pause and weak retirement passed");
}
