/* World-space mesh precipitation, owned by UE's current match world.
 * All callbacks run on the game thread. No render-thread registry writes. */
typedef struct { int32_t index, serial; } NxWeatherWeak;
typedef struct { float x,y,z; } NxWeatherVec;
/* This Android binary uses the non-vectorized, 40-byte FTransform. Its
 * translation is 12 bytes: scale starts at 0x1c, NOT the desktop SIMD 0x20.
 * A padded translation silently turns unit scale into (0,1,1). */
typedef struct { float rotation[4], location[3], scale[3]; } NxWeatherTransform;
_Static_assert(sizeof(NxWeatherTransform)==40, "Android FTransform size");
_Static_assert(offsetof(NxWeatherTransform,scale)==28, "Android FTransform scale");
static void (*weather_weak_set)(NxWeatherWeak *, const void *);
static void *(*weather_weak_get)(const NxWeatherWeak *);
static void (*weather_loaded_original)(void *);
static void (*weather_unload_original)(void *);
static void (*weather_destroy_original)(void *);
static void (*weather_tick_original)(void *, int, float);
static void **weather_world;
static void *(*weather_mesh_class)(void);
static void *(*weather_actor_class)(void);
static void *(*weather_component_class)(void);
static void *(*weather_load)(void *,void *,const uint16_t *,const uint16_t *,uint32_t,void *,int,void *);
static void *(*weather_spawn)(const void *,void *,const NxWeatherTransform *,uint8_t,void *);
static void *(*weather_finish)(void *,const NxWeatherTransform *);
static int (*weather_destroy_actor)(void *,int,int);
static int (*weather_set_mesh)(void *,void *);
static void (*weather_mobility)(void *,uint32_t);
static void (*weather_collision)(void *,uint32_t);
static void (*weather_shadow)(void *,int);
/* Shipping Android FName is two 32-bit fields, passed in one x-register. */
static void (*weather_fname)(uint64_t *,const uint16_t *,uint32_t);
static void *(*weather_dynamic_material)(void *,int,void *,uint64_t);
static void (*weather_scalar)(void *,uint64_t,float);
static void *(*weather_camera)(const void *,int);
static NxWeatherVec (*weather_camera_position)(const void *);
static NxWeatherVec (*weather_camera_angles)(const void *);
static void (*weather_location)(void *,const NxWeatherVec *,const NxWeatherVec *);
static NxWeatherWeak weather_match_world={-1,0}, weather_component={-1,0};
static NxWeatherWeak weather_actor={-1,0}, weather_material={-1,0};
static int weather_scene_active, weather_scene_attempted;
static int weather_scene_first_tick;
static float weather_scene_age,weather_clock;
static unsigned weather_scene_reports;
static uint64_t weather_clock_name;
static NxWeatherVec weather_last_focus;

static void weather_scene_retire(void) {
  void *actor=weather_weak_get(&weather_actor);
  if (actor) weather_destroy_actor(actor,0,0);
  weather_weak_set(&weather_actor,NULL);
  weather_weak_set(&weather_material,NULL);
  weather_weak_set(&weather_component,NULL);
  weather_weak_set(&weather_match_world,NULL);
  weather_scene_active=weather_scene_attempted=0;
  weather_scene_first_tick=0;
  weather_scene_age=weather_clock=0;weather_scene_reports=0;
}
static void weather_scene_loaded(void *loader) {
  weather_scene_retire();
  weather_loaded_original(loader);
  if (weather_world && *weather_world) {
    weather_weak_set(&weather_match_world,*weather_world);
    weather_scene_active=1;
    const uint32_t kind=__atomic_load_n(&weather_scene_kind,__ATOMIC_ACQUIRE);
    if (kind==1 || kind==2)
      scene_runtime_note("weather field","waiting for first live match frame; no allocation during prematch loading");
  }
}
static void weather_scene_unload(void *loader) {
  weather_scene_retire();
  weather_unload_original(loader);
}
static void weather_scene_destroy(void *loader) {
  weather_scene_retire();
  weather_destroy_original(loader);
}
static float weather_limit(float value,float bound) {
  return value < -bound ? -bound : value > bound ? bound : value;
}
static NxWeatherVec weather_focus(void *world) {
  NxWeatherVec position={0,0,0};
  void *camera=weather_camera(world,0);
  if (!camera) return position;
  const NxWeatherVec eye=weather_camera_position(camera);
  const NxWeatherVec angles=weather_camera_angles(camera);
  if (!isfinite(eye.x) || !isfinite(eye.y) || !isfinite(eye.z) ||
      !isfinite(angles.x) || !isfinite(angles.y)) return position;
  const float pitch=angles.x*0.01745329252f, yaw=angles.y*0.01745329252f;
  const float down=sinf(pitch);
  if (down < -0.05f && eye.z > 0) {
    const float distance=fminf(15000.0f, -eye.z/down);
    position.x=weather_limit(eye.x+distance*cosf(pitch)*cosf(yaw),4000);
    position.y=weather_limit(eye.y+distance*cosf(pitch)*sinf(yaw),2500);
  }
  return position;
}
static void weather_scene_spawn(void *world,uint32_t kind) {
  weather_scene_attempted=1;
  const char *name=kind==2 ? "/Game/FootballNX/Weather/SnowField.SnowField" :
                           "/Game/FootballNX/Weather/RainField.RainField";
  uint16_t wide[96];
  for (size_t i=0;i<=strlen(name);++i) wide[i]=(uint8_t)name[i];
  void *asset=weather_load(weather_mesh_class(),NULL,wide,NULL,0,NULL,1,NULL);
  if (!asset) { scene_runtime_note("weather field","asset missing; physics retained");return; }
  const NxWeatherVec p=weather_focus(world);
  _Alignas(16) NxWeatherTransform transform={{0,0,0,1},{p.x,p.y,p.z},{1,1,1}};
  void *actor=weather_spawn(world,weather_actor_class(),&transform,1,NULL);
  if (!actor) { scene_runtime_note("weather field","actor spawn failed");return; }
  void *component=NULL,*klass=NULL;
  memcpy(&component,(const char *)actor+0x158,sizeof(component));
  if (component) memcpy(&klass,(const char *)component+0x10,sizeof(klass));
  if (klass!=weather_component_class()) {
    weather_destroy_actor(actor,0,0);
    scene_runtime_note("weather field","unexpected root class; field disabled");return;
  }
  weather_mobility(component,2);
  weather_collision(component,0);
  weather_shadow(component,0);
  if (!weather_set_mesh(component,asset)) {
    weather_destroy_actor(actor,0,0);
    scene_runtime_note("weather field","mesh rejected; field disabled");return;
  }
  void *material=weather_dynamic_material(component,0,NULL,0);
  if (!material) {
    weather_destroy_actor(actor,0,0);
    scene_runtime_note("weather field","material unavailable; field disabled");return;
  }
  const uint16_t clock_name[]={'W','e','a','t','h','e','r','C','l','o','c','k',0};
  weather_fname(&weather_clock_name,clock_name,1); // FNAME_Add, not Find-only.
  weather_scalar(material,weather_clock_name,0);
  if (!weather_finish(actor,&transform)) {
    weather_destroy_actor(actor,0,0);
    scene_runtime_note("weather field","actor finish failed");return;
  }
  weather_weak_set(&weather_actor,actor);
  weather_weak_set(&weather_component,component);
  weather_weak_set(&weather_material,material);
  weather_last_focus=p;
  scene_runtime_note("weather field",kind==2?"Snow mesh spawned (640 flakes)":"Rain mesh spawned (768 drops)");
}
static void weather_scene_tick(void *world,int level_tick,float seconds) {
  const int first=weather_scene_active && !weather_scene_first_tick &&
      weather_weak_get(&weather_match_world)==world && weather_weak_get(&weather_actor)!=NULL;
  if (first) {
    weather_scene_first_tick=1;
    scene_runtime_note("weather field","first native world tick after spawn begin");
  }
  weather_tick_original(world,level_tick,seconds);
  if (first) scene_runtime_note("weather field","first native world tick after spawn returned");
  if (!weather_scene_active) return;
  void *owner=weather_weak_get(&weather_match_world);
  if (!owner) { weather_scene_retire();return; }
  if (owner!=world) return;
  const uint32_t kind=__atomic_load_n(&weather_scene_kind,__ATOMIC_ACQUIRE);
  if (kind!=1 && kind!=2) return;
  const int paused=pes_controller_pause_skin_active() || pes_controller_pause_transition();
  if (!weather_scene_attempted && !paused && pes_controller_match_hud_inplay())
    weather_scene_spawn(world,kind);
  void *component=weather_weak_get(&weather_component),*material=weather_weak_get(&weather_material);
  if (!component || !material || paused) return;
  const NxWeatherVec p=weather_focus(world),angle={0,0,0};
  const float dx=p.x-weather_last_focus.x,dy=p.y-weather_last_focus.y;
  if (dx*dx+dy*dy>2500.0f) {
    weather_location(component,&p,&angle);weather_last_focus=p;
  }
  if (isfinite(seconds) && seconds>0) {
    const float dt=fminf(seconds,0.1f);
    weather_scene_age+=dt;weather_clock=fmodf(weather_clock+dt,24.0f);
    weather_scalar(material,weather_clock_name,weather_clock);
  }
  if (weather_scene_reports<2 && weather_scene_age>=(weather_scene_reports?8.0f:2.0f)) {
    // Ordinary primitive registration/proxy, not an emitter simulation count.
    void *proxy=NULL;uint8_t registered=0;
    memcpy(&proxy,(const char *)component+0x500,sizeof(proxy));
    memcpy(&registered,(const char *)component+0xac,1);
    char message[192];
    snprintf(message,sizeof(message),"%s mesh registered=%u proxy=%d clock=%.2f focus=(%.0f,%.0f,0)",
        kind==2?"Snow":"Rain",registered&1u,proxy!=NULL,weather_clock,p.x,p.y);
    scene_runtime_note("weather field",message);++weather_scene_reports;
  }
}
#ifndef PESNX_WEATHER_SCENE_HOST_TEST
static void install_weather_scene(so_module *module) {
  FILE *f=fopen("PesMobile/Content/Paks/PesMobile-Weather-Android_ETC1_P.pak","rb");
  if (!f) return;
  fclose(f);
  const uintptr_t base=(uintptr_t)module->load_base;
  const char *root_symbol="_ZN6AActor23execK2_GetRootComponentEP7UObjectR6FFramePv";
  const char *mesh_symbol="_ZN20UStaticMeshComponent13SetStaticMeshEP11UStaticMesh";
  if (!so_try_find_addr_rx(module,root_symbol) || !so_try_find_addr_rx(module,mesh_symbol)) return;
  if (*(const uint32_t *)(so_find_addr(module,root_symbol)+16)!=0xf940ac08 ||
      *(const uint32_t *)(so_find_addr(module,mesh_symbol)+40)!=0xf942d808) return;
  const uint32_t loaded[]={0xb002e2f0,0xf9409e11,0x9104e210,0xd61f0220};
  const uint32_t unload[]={0xf002e270,0xf945c211,0x912e0210,0xd61f0220};
  const uint32_t destroy[]={0xd002e2b0,0xf9465611,0x9132a210,0xd61f0220};
  const uint32_t tick[]={0x9002e170,0xf9425211,0x91128210,0xd61f0220};
  if ((!stadium_canary_installed && !referee_probe_enabled && memcmp((void *)(base+0x38c3dc0),loaded,16)) ||
      (!referee_probe_enabled && (memcmp((void *)(base+0x38dd250),unload,16) ||
                                 memcmp((void *)(base+0x38cf4a0),destroy,16))) ||
      memcmp((void *)(base+0x3924490),tick,16)) return;
#define WEATHER_SCENE_BIND(target,symbol) do { \
  target=(void *)so_try_find_addr_rx(module,symbol); if (!target) return; \
} while (0)
  WEATHER_SCENE_BIND(weather_loaded_original,"_ZN14AStadiumLoader10LoadedCallEv");
  WEATHER_SCENE_BIND(weather_unload_original,"_ZN14AStadiumLoader6UnLoadEv");
  WEATHER_SCENE_BIND(weather_destroy_original,"_ZN14AStadiumLoader13DestroyLoaderEv");
  WEATHER_SCENE_BIND(weather_tick_original,"_ZN6UWorld4TickE10ELevelTickf");
  WEATHER_SCENE_BIND(weather_world,"GWorld");
  WEATHER_SCENE_BIND(weather_weak_set,"_ZN14FWeakObjectPtraSEPK7UObject");
  WEATHER_SCENE_BIND(weather_weak_get,"_ZNK14FWeakObjectPtr3GetEv");
  WEATHER_SCENE_BIND(weather_mesh_class,"_ZN11UStaticMesh21GetPrivateStaticClassEv");
  WEATHER_SCENE_BIND(weather_actor_class,"_ZN16AStaticMeshActor21GetPrivateStaticClassEv");
  WEATHER_SCENE_BIND(weather_component_class,"_ZN20UStaticMeshComponent21GetPrivateStaticClassEv");
  WEATHER_SCENE_BIND(weather_load,"_Z16StaticLoadObjectP6UClassP7UObjectPKDsS4_jP11UPackageMapbP24FUObjectSerializeContext");
  WEATHER_SCENE_BIND(weather_spawn,"_ZN16UGameplayStatics32BeginDeferredActorSpawnFromClassEPK7UObject11TSubclassOfI6AActorERK10FTransform34ESpawnActorCollisionHandlingMethodPS4_");
  WEATHER_SCENE_BIND(weather_finish,"_ZN16UGameplayStatics19FinishSpawningActorEP6AActorRK10FTransform");
  WEATHER_SCENE_BIND(weather_destroy_actor,"_ZN6AActor7DestroyEbb");
  WEATHER_SCENE_BIND(weather_set_mesh,"_ZN20UStaticMeshComponent13SetStaticMeshEP11UStaticMesh");
  WEATHER_SCENE_BIND(weather_mobility,"_ZN15USceneComponent11SetMobilityEN18EComponentMobility4TypeE");
  WEATHER_SCENE_BIND(weather_collision,"_ZN19UPrimitiveComponent19SetCollisionEnabledEN17ECollisionEnabled4TypeE");
  WEATHER_SCENE_BIND(weather_shadow,"_ZN19UPrimitiveComponent13SetCastShadowEb");
  WEATHER_SCENE_BIND(weather_fname,"_ZN5FNameC1EPKDs9EFindName");
  WEATHER_SCENE_BIND(weather_dynamic_material,"_ZN19UPrimitiveComponent29CreateDynamicMaterialInstanceEiP18UMaterialInterface5FName");
  WEATHER_SCENE_BIND(weather_scalar,"_ZN24UMaterialInstanceDynamic23SetScalarParameterValueE5FNamef");
  WEATHER_SCENE_BIND(weather_camera,"_ZN16UGameplayStatics22GetPlayerCameraManagerEPK7UObjecti");
  WEATHER_SCENE_BIND(weather_camera_position,"_ZNK20APlayerCameraManager17GetCameraLocationEv");
  WEATHER_SCENE_BIND(weather_camera_angles,"_ZNK20APlayerCameraManager17GetCameraRotationEv");
  WEATHER_SCENE_BIND(weather_location,"_ZN15USceneComponent36SetWorldLocationAndRotationNoPhysicsERK7FVectorRK8FRotator");
#undef WEATHER_SCENE_BIND
  if (stadium_canary_installed) weather_loaded_original=stadium_loaded_canary;
  if (referee_probe_enabled) {
    weather_loaded_original=referee_probe_loaded_scene;
    weather_unload_original=referee_probe_unload;
    weather_destroy_original=referee_probe_destroy_loader;
  }
  hook_arm64(base+0x38c3dc0,(uintptr_t)weather_scene_loaded);
  hook_arm64(base+0x38dd250,(uintptr_t)weather_scene_unload);
  hook_arm64(base+0x38cf4a0,(uintptr_t)weather_scene_destroy);
  hook_arm64(base+0x3924490,(uintptr_t)weather_scene_tick);
  scene_runtime_note("weather field","v11 native mesh precipitation installed; deferred until live match");
}
#endif
