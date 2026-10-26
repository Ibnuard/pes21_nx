/* World-space mesh precipitation, owned by UE's current match world.
 * All callbacks run on the game thread. No render-thread registry writes. */
typedef struct { int32_t index, serial; } NxWeatherWeak;
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
static NxWeatherWeak weather_match_world={-1,0}, weather_component={-1,0};
static NxWeatherWeak weather_actor={-1,0}, weather_material={-1,0};
static int weather_scene_active, weather_scene_attempted;
#ifndef PESNX_WEATHER_SCENE_HOST_TEST
static int weather_scene_installed;
#endif
static int weather_scene_first_tick;
static float weather_scene_age,weather_clock;
static float weather_cloud_clock;
static int weather_cloud_live;
static unsigned weather_cloud_reports;
static _Alignas(4) uint32_t weather_cloud_step;
uint32_t pes_controller_cloud_shadow_step(void) {
  return __atomic_load_n(&weather_cloud_step,__ATOMIC_RELAXED);
}
static unsigned weather_scene_reports;
static uint64_t weather_clock_name;

static void weather_scene_retire(void) {
#ifdef PESNX_TROPHY_SPARKS_RUNTIME
  fixdemo_trophy_sparks_reset();
#endif
  void *actor=weather_weak_get(&weather_actor);
  if (actor) weather_destroy_actor(actor,0,0);
  weather_weak_set(&weather_actor,NULL);
  weather_weak_set(&weather_material,NULL);
  weather_weak_set(&weather_component,NULL);
  weather_weak_set(&weather_match_world,NULL);
  weather_scene_active=weather_scene_attempted=0;
  weather_scene_first_tick=0;
  weather_scene_age=weather_clock=0;weather_scene_reports=0;
  weather_cloud_clock=0;weather_cloud_live=0;weather_cloud_reports=0;
  __atomic_store_n(&weather_cloud_step,0,__ATOMIC_RELAXED);
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
static void weather_scene_spawn(void *world,uint32_t kind) {
  if(kind!=1 && kind!=2)return;
  weather_scene_attempted=1;
  const char *name=kind==2 ? "/Game/FootballNX/WeatherWorld/SnowField.SnowField" :
      "/Game/FootballNX/WeatherWorld/RainField.RainField";
  uint16_t wide[96];
  for (size_t i=0;i<=strlen(name);++i) wide[i]=(uint8_t)name[i];
  void *asset=weather_load(weather_mesh_class(),NULL,wide,NULL,0,NULL,1,NULL);
  if (!asset) { scene_runtime_note("weather field","asset missing; physics retained");return; }
  /* Full-pitch authored coordinates. Only the shader's fall/wind clock moves
   * airborne particles; the camera never rebases their world positions. */
  _Alignas(16) NxWeatherTransform transform={{0,0,0,1},{0,0,0},{1,1,1}};
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
  scene_runtime_note("weather field",kind==2 ?
      "light snow mesh spawned (256 small flakes, 1024 triangles)" :
      "light rain mesh spawned (256 thin drops, 1024 triangles)");
}
static void weather_scene_tick(void *world,int level_tick,float seconds) {
  const int first=weather_scene_active && !weather_scene_first_tick &&
      weather_weak_get(&weather_match_world)==world && weather_weak_get(&weather_actor)!=NULL;
  if (first) {
    weather_scene_first_tick=1;
    scene_runtime_note("weather field","first native world tick after spawn begin");
  }
  weather_tick_original(world,level_tick,seconds);
#ifdef PESNX_TROPHY_SPARKS_RUNTIME
  fixdemo_trophy_sparks_update_world(world,seconds);
#endif
  if (first) scene_runtime_note("weather field","first native world tick after spawn returned");
  if (!weather_scene_active) return;
  void *owner=weather_weak_get(&weather_match_world);
  if (!owner) { weather_scene_retire();return; }
  if (owner!=world) return;
  const int paused=pes_controller_pause_skin_active() || pes_controller_pause_transition();
  if (!weather_cloud_live && !paused && pes_controller_match_hud_inplay()) weather_cloud_live=1;
  if (weather_cloud_live && !paused && isfinite(seconds) && seconds>0) {
    weather_cloud_clock=fmodf(weather_cloud_clock+fminf(seconds,0.1f),240.0f);
    __atomic_store_n(&weather_cloud_step,(uint32_t)(weather_cloud_clock*4.0f),__ATOMIC_RELAXED);
    if (weather_cloud_reports<2 && weather_cloud_clock>=(weather_cloud_reports?8.0f:0.25f)) {
      char message[128];
      snprintf(message,sizeof(message),"v77 match clock=%.2fs phase=%.4f; Cloudy motion independent of rain/snow assets",
          weather_cloud_clock,weather_cloud_clock/120.0f);
      scene_runtime_note("weather motion",message);++weather_cloud_reports;
    }
  }
  const uint32_t kind=__atomic_load_n(&weather_scene_kind,__ATOMIC_ACQUIRE);
  if (kind!=1 && kind!=2) return;
  if (!weather_scene_attempted && !paused && pes_controller_match_hud_inplay())
    weather_scene_spawn(world,kind);
  void *component=weather_weak_get(&weather_component),*material=weather_weak_get(&weather_material);
  if (!component || !material || paused) return;
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
    snprintf(message,sizeof(message),"%s mesh registered=%u proxy=%d clock=%.2f fixed world origin=(0,0,0)",
        kind==2 ? "Light Snow" : "Light Rain",registered&1u,proxy!=NULL,weather_clock);
    scene_runtime_note("weather field",message);++weather_scene_reports;
  }
}
#ifndef PESNX_WEATHER_SCENE_HOST_TEST
static void install_weather_scene(so_module *module) {
  /* Cloud motion needs only the match lifecycle. Optional precipitation assets
   * are resolved once at spawn, and their absence must not disable this clock. */
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
  weather_scene_installed=1;
  scene_runtime_note("weather field","v77 independent Cloudy clock; v75 fixed full-pitch precipitation retained");
}
#endif
