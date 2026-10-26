/* Authored, optional podium spark fountains. This is a lightweight visual
 * approximation: the supported Mobile binary's PC FixDemo FX methods are stubs.
 * Only the UE game thread calls these functions. The native callback supplies
 * its already-validated, live podium actor/component; no saved PES/UEObject
 * identity is ever dereferenced here. All retained UObjects are weak handles.
 */
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <math.h>

typedef struct { int32_t index, serial; } TrophySparkWeak;
typedef struct { float rotation[4], location[3], scale[3]; } TrophySparkTransform;
_Static_assert(sizeof(TrophySparkTransform) == 40, "Android non-SIMD FTransform");
_Static_assert(offsetof(TrophySparkTransform, scale) == 28, "Android scale offset");

static struct {
  void (*weak_set)(TrophySparkWeak *, const void *);
  void *(*weak_get)(const TrophySparkWeak *);
  void **world;
  void *(*mesh_class)(void);
  void *(*actor_class)(void);
  void *(*component_class)(void);
  void *(*load)(void *,void *,const uint16_t *,const uint16_t *,uint32_t,void *,int,void *);
  void *(*spawn)(const void *,void *,const TrophySparkTransform *,uint8_t,void *);
  void *(*finish)(void *,const TrophySparkTransform *);
  int (*destroy)(void *,int,int);
  int (*set_mesh)(void *,void *);
  void (*mobility)(void *,uint32_t);
  void (*collision)(void *,uint32_t);
  void (*shadow)(void *,int);
  void (*fname)(uint64_t *,const uint16_t *,uint32_t);
  void *(*dynamic)(void *,int,void *,uint64_t);
  void (*scalar)(void *,uint64_t,float);
  TrophySparkTransform (*transform)(const void *);
} trophy_spark_ops;

static struct {
  TrophySparkWeak world, podium, component, actor, material;
  TrophySparkTransform pose;
  uint64_t epoch, generation, clock_name;
  float clock, age;
  unsigned enabled, observed, attempted, reported;
} trophy_sparks = {.world={-1,0}, .podium={-1,0}, .component={-1,0}, .actor={-1,0}, .material={-1,0}};

static void fixdemo_trophy_sparks_reset(void) {
  if (!trophy_sparks.enabled) return;
  void *actor = trophy_spark_ops.weak_get(&trophy_sparks.actor);
  if (actor) trophy_spark_ops.destroy(actor, 0, 0);
  trophy_spark_ops.weak_set(&trophy_sparks.actor, NULL);
  trophy_spark_ops.weak_set(&trophy_sparks.material, NULL);
  trophy_spark_ops.weak_set(&trophy_sparks.podium, NULL);
  trophy_spark_ops.weak_set(&trophy_sparks.component, NULL);
  trophy_spark_ops.weak_set(&trophy_sparks.world, NULL);
  trophy_sparks.epoch = trophy_sparks.generation = 0;
  trophy_sparks.clock = trophy_sparks.age = 0;
  trophy_sparks.observed = trophy_sparks.attempted = trophy_sparks.reported = 0;
}

static int trophy_spark_valid_pose(const TrophySparkTransform *pose) {
  float norm = 0;
  for (unsigned i=0; i<4; ++i) {
    if (!isfinite(pose->rotation[i])) return 0;
    norm += pose->rotation[i] * pose->rotation[i];
  }
  if (norm < .98f || norm > 1.02f) return 0;
  for (unsigned i=0; i<3; ++i)
    if (!isfinite(pose->location[i]) || fabsf(pose->location[i]) > 20000.f ||
        !isfinite(pose->scale[i]) || pose->scale[i] < .001f || pose->scale[i] > 100.f) return 0;
  return 1;
}

static int fixdemo_trophy_sparks_matches_owner(uint64_t epoch, uint64_t generation) {
  return epoch && generation && trophy_sparks.observed &&
      trophy_sparks.epoch == epoch && trophy_sparks.generation == generation;
}

/* Called after original UE OnHandleCallback and an exact kind=podium mesh
 * binding check. Loading may publish only weak UObject references: no actor or
 * material allocation occurs here. A one-shot loading callback is sufficient;
 * the pose is obtained from the valid weak component only when PLAYING starts.
 * No saved native PES/UEObject identity is ever dereferenced on this thread. */
static void fixdemo_trophy_sparks_observe(uint64_t epoch, uint64_t generation,
    void *podium_actor, void *podium_component, uint64_t active_ui_epoch) {
  if (!trophy_sparks.enabled || !epoch || epoch != active_ui_epoch || !generation ||
      !podium_actor || !podium_component || !trophy_spark_ops.world || !*trophy_spark_ops.world) return;
  if (trophy_sparks.epoch == epoch && trophy_sparks.generation == generation &&
      trophy_sparks.observed) return;
  fixdemo_trophy_sparks_reset();
  trophy_sparks.epoch = epoch;
  trophy_sparks.generation = generation;
  trophy_spark_ops.weak_set(&trophy_sparks.world, *trophy_spark_ops.world);
  trophy_spark_ops.weak_set(&trophy_sparks.podium, podium_actor);
  trophy_spark_ops.weak_set(&trophy_sparks.component, podium_component);
  trophy_sparks.observed = 1;
}

static void trophy_spark_spawn(void *world) {
  trophy_sparks.attempted = 1; /* Optional failure is tried once per owner generation. */
  void *podium_component = trophy_spark_ops.weak_get(&trophy_sparks.component);
  if (!podium_component) return;
  trophy_sparks.pose = trophy_spark_ops.transform(podium_component);
  if (!trophy_spark_valid_pose(&trophy_sparks.pose)) {
    fixdemo_trophy_note("sparks-disabled invalid-podium-transform");
    return;
  }
  /* Physical centimetres, not the source prop's conversion scale. The original
   * component remains untouched. This snapshot never follows a moving camera. */
  for (unsigned i=0; i<3; ++i) trophy_sparks.pose.scale[i] = 1.f;
  static const uint16_t name[] = {'/','G','a','m','e','/','F','o','o','t','b','a','l','l','N','X','/',
    'T','r','o','p','h','y','S','p','a','r','k','s','/','P','o','d','i','u','m','S','p','a','r','k','s','.',
    'P','o','d','i','u','m','S','p','a','r','k','s',0};
  void *mesh = trophy_spark_ops.load(trophy_spark_ops.mesh_class(), NULL, name, NULL, 0, NULL, 1, NULL);
  if (!mesh) { fixdemo_trophy_note("sparks-unavailable optional-mesh-missing"); return; }
  _Alignas(16) TrophySparkTransform pose = trophy_sparks.pose;
  void *actor = trophy_spark_ops.spawn(world, trophy_spark_ops.actor_class(), &pose, 1, NULL);
  if (!actor) { fixdemo_trophy_note("sparks-unavailable actor-spawn-failed"); return; }
  void *component = NULL, *klass = NULL;
  memcpy(&component, (const char *)actor + 0x158u, sizeof(component));
  if (component) memcpy(&klass, (const char *)component + 0x10u, sizeof(klass));
  if (!component || klass != trophy_spark_ops.component_class()) goto failed;
  trophy_spark_ops.mobility(component, 2);
  trophy_spark_ops.collision(component, 0);
  trophy_spark_ops.shadow(component, 0);
  if (!trophy_spark_ops.set_mesh(component, mesh)) goto failed;
  void *material = trophy_spark_ops.dynamic(component, 0, NULL, 0);
  if (!material) goto failed;
  const uint16_t clock[] = {'S','p','a','r','k','C','l','o','c','k',0};
  trophy_spark_ops.fname(&trophy_sparks.clock_name, clock, 1);
  trophy_spark_ops.scalar(material, trophy_sparks.clock_name, 0);
  if (!trophy_spark_ops.finish(actor, &pose)) goto failed;
  trophy_spark_ops.weak_set(&trophy_sparks.actor, actor);
  trophy_spark_ops.weak_set(&trophy_sparks.material, material);
  fixdemo_trophy_note("sparks-start authored-gold 128-sparks 512-triangles one-primitive fixed-podium-pose");
  return;
failed:
  trophy_spark_ops.destroy(actor, 0, 0);
  fixdemo_trophy_note("sparks-unavailable actor-setup-failed");
}

/* Called on UE's world thread after its native tick. A cancelled/Skipped token,
 * replacement, GC retirement, different world or a 60 s safety bound retires
 * the effect without changing native ceremony readiness/playback/result flow. */
static void fixdemo_trophy_sparks_tick(void *world, float seconds,
    uint64_t active_ui_epoch, uint64_t playing_epoch,
    uint64_t current_podium_generation, int skip_requested) {
  if (!trophy_sparks.enabled || !trophy_sparks.epoch) return;
  void *owner_world = trophy_spark_ops.weak_get(&trophy_sparks.world);
  if (!active_ui_epoch || trophy_sparks.epoch != active_ui_epoch || skip_requested ||
      (playing_epoch && playing_epoch != active_ui_epoch) ||
      !fixdemo_trophy_sparks_matches_owner(active_ui_epoch,current_podium_generation) ||
      !owner_world || !trophy_spark_ops.world || owner_world != *trophy_spark_ops.world ||
      !trophy_spark_ops.weak_get(&trophy_sparks.podium) ||
      !trophy_spark_ops.weak_get(&trophy_sparks.component)) {
    fixdemo_trophy_sparks_reset();
    return;
  }
  if (world != owner_world) return;
  if (playing_epoch != active_ui_epoch) return; /* Loading never allocates or advances FX. */
  if (!trophy_sparks.attempted) trophy_spark_spawn(world);
  if (!trophy_spark_ops.weak_get(&trophy_sparks.actor)) return;
  void *material = trophy_spark_ops.weak_get(&trophy_sparks.material);
  if (!material) {
    void *actor = trophy_spark_ops.weak_get(&trophy_sparks.actor);
    if (actor) trophy_spark_ops.destroy(actor, 0, 0);
    trophy_spark_ops.weak_set(&trophy_sparks.actor, NULL);
    return;
  }
  if (isfinite(seconds) && seconds > 0) {
    const float dt = fminf(seconds, .1f);
    trophy_sparks.age += dt;
    trophy_sparks.clock = fmodf(trophy_sparks.clock + dt, 4.f);
    trophy_spark_ops.scalar(material, trophy_sparks.clock_name, trophy_sparks.clock);
  }
  if (!trophy_sparks.reported && trophy_sparks.age >= 2.f) {
    trophy_sparks.reported = 1;
    fixdemo_trophy_note("sparks-live world-anchored depth-tested no-lights no-shadow-map no-fragment-textures");
  }
  if (trophy_sparks.age >= 60.f) {
    /* Keep the generation attempted: do not restart every frame while the
     * ceremony is held open beyond the optional effect's safety duration. */
    void *actor = trophy_spark_ops.weak_get(&trophy_sparks.actor);
    if (actor) trophy_spark_ops.destroy(actor, 0, 0);
    trophy_spark_ops.weak_set(&trophy_sparks.actor, NULL);
    trophy_spark_ops.weak_set(&trophy_sparks.material, NULL);
  }
}

#ifndef PESNX_TROPHY_SPARKS_HOST_TEST
static int fixdemo_trophy_sparks_prepare(so_module *module) {
  if (!module || !fixdemo_trophy_canary_validated) return 0;
  /* The original native exec wrapper calls this getter with x8 pointing to a
   * 40-byte result. Full-ELF identity is already pinned by trophy admission. */
  static const uint32_t getter[] = {0x3dc06400,0x9106b00b,0x3d800100,0xb941a809,
    0xf940d00a,0xb9001909,0xf900090a,0xb941b409,0xf940016a,0xb9002509,0xf801c10a,0xd65f03c0};
  const char *getter_name = "_ZNK15USceneComponent22K2_GetComponentToWorldEv";
  uintptr_t address = so_try_find_addr_rx(module, getter_name);
  if (address != (uintptr_t)module->load_virtbase + 0x545fcf8u ||
      memcmp((const void *)so_find_addr(module, getter_name), getter, sizeof(getter))) return 0;
#define TROPHY_SPARK_BIND(target, symbol) do { \
  trophy_spark_ops.target = (void *)so_try_find_addr_rx(module, symbol); \
  if (!trophy_spark_ops.target) return 0; \
} while (0)
  TROPHY_SPARK_BIND(weak_set,"_ZN14FWeakObjectPtraSEPK7UObject");
  TROPHY_SPARK_BIND(weak_get,"_ZNK14FWeakObjectPtr3GetEv");
  TROPHY_SPARK_BIND(world,"GWorld");
  TROPHY_SPARK_BIND(mesh_class,"_ZN11UStaticMesh21GetPrivateStaticClassEv");
  TROPHY_SPARK_BIND(actor_class,"_ZN16AStaticMeshActor21GetPrivateStaticClassEv");
  TROPHY_SPARK_BIND(component_class,"_ZN20UStaticMeshComponent21GetPrivateStaticClassEv");
  TROPHY_SPARK_BIND(load,"_Z16StaticLoadObjectP6UClassP7UObjectPKDsS4_jP11UPackageMapbP24FUObjectSerializeContext");
  TROPHY_SPARK_BIND(spawn,"_ZN16UGameplayStatics32BeginDeferredActorSpawnFromClassEPK7UObject11TSubclassOfI6AActorERK10FTransform34ESpawnActorCollisionHandlingMethodPS4_");
  TROPHY_SPARK_BIND(finish,"_ZN16UGameplayStatics19FinishSpawningActorEP6AActorRK10FTransform");
  TROPHY_SPARK_BIND(destroy,"_ZN6AActor7DestroyEbb");
  TROPHY_SPARK_BIND(set_mesh,"_ZN20UStaticMeshComponent13SetStaticMeshEP11UStaticMesh");
  TROPHY_SPARK_BIND(mobility,"_ZN15USceneComponent11SetMobilityEN18EComponentMobility4TypeE");
  TROPHY_SPARK_BIND(collision,"_ZN19UPrimitiveComponent19SetCollisionEnabledEN17ECollisionEnabled4TypeE");
  TROPHY_SPARK_BIND(shadow,"_ZN19UPrimitiveComponent13SetCastShadowEb");
  TROPHY_SPARK_BIND(fname,"_ZN5FNameC1EPKDs9EFindName");
  TROPHY_SPARK_BIND(dynamic,"_ZN19UPrimitiveComponent29CreateDynamicMaterialInstanceEiP18UMaterialInterface5FName");
  TROPHY_SPARK_BIND(scalar,"_ZN24UMaterialInstanceDynamic23SetScalarParameterValueE5FNamef");
  TROPHY_SPARK_BIND(transform,getter_name);
#undef TROPHY_SPARK_BIND
  trophy_sparks.enabled = 1;
  return 1;
}
#endif
