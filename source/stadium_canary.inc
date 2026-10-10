/* Optional local Anfield shell. Uses native pitch, goals, lights and cameras.
 * Runs on LoadedCall's game thread. No UObject pointer survives the callback. */
#include "stadium_catalog.h"
#include "scene_runtime_log.h"
static void (*stadium_loaded_original)(void *);
static void *(*stadium_actor_class)(void);
static void *(*stadium_mesh_class)(void);
static void *(*stadium_component_class)(void);
static void (*stadium_get_actors)(const void *, void *, Ue4Array *);
static void *(*stadium_load_object)(void *, void *, const uint16_t *,
                                  const uint16_t *, uint32_t, void *, int, void *);
static void (*stadium_fname_string)(const void *, Ue4Array *);
static void (*stadium_engine_free)(void *);
static int (*stadium_set_mesh)(void *, void *);
static void (*stadium_empty_materials)(void *);
static void (*stadium_hide_actor)(void *, int);
static void (*stadium_set_mobility)(void *, uint32_t);
static void (*stadium_set_collision)(void *, uint32_t);
static void (*stadium_set_cast_shadow)(void *, int);
static void (*stadium_reregister_begin)(void *, void *);
static void (*stadium_reregister_end)(void *);
static void (*stadium_release_resources)(void *);
static void (*stadium_flush_rendering)(int);
static int (*stadium_set_lod_count)(void *, uint32_t, uint32_t);
static void (*stadium_set_forced_lod)(void *, int);
static void **stadium_world;
static uint32_t stadium_canary_installed, stadium_canary_active;

static void stadium_canary_note(const char *text) {
  scene_runtime_note("stadium",text);
#ifndef PESNX_STADIUM_CANARY_HOST_TEST
  FILE *file = fopen("stadium-canary.status", "w");
  if (file) { fputs(text, file); fputc('\n', file); fclose(file); }
#else
  (void)text;
#endif
}

uint32_t pes_controller_stadium_catalog_count(void) {
  return stadium_canary_installed ? 2u : 1u;
}
uint32_t pes_controller_stadium_canary_active(void) {
  return __atomic_load_n(&stadium_canary_active, __ATOMIC_ACQUIRE);
}
static int stadium_object_name(const void *object, char out[96]) {
  Ue4Array string = {0};
  stadium_fname_string((const char *)object + 0x18, &string);
  int valid = string.data && string.num > 0 && string.num <= 96 &&
              string.max >= string.num;
  if (valid) {
    const uint16_t *text = string.data;
    for (int32_t i = 0; i < string.num; ++i) {
      if (text[i] > 127) { valid = 0; break; }
      out[i] = (char)text[i];
    }
    out[string.num - 1] = 0;
  }
  if (string.data) stadium_engine_free(string.data);
  return valid;
}
static void *stadium_load_mesh(const char *path) {
  uint16_t wide[192];
  size_t length = strlen(path);
  if (length >= sizeof(wide) / sizeof(wide[0])) return NULL;
  for (size_t i = 0; i <= length; ++i) wide[i] = (uint8_t)path[i];
  return stadium_load_object(stadium_mesh_class(), NULL, wide, NULL,
                             0, NULL, 1, NULL);
}
static void *stadium_actor_component(void *actor) {
  void *component = *(void **)((char *)actor + 0x158);
  // Exact class check before reading the StaticMesh-only portion of the object.
  if (!component || *(void **)((char *)component + 0x10) != stadium_component_class())
    return NULL;
  return component;
}
static void stadium_loaded_canary(void *loader) {
  const uint64_t started=scene_runtime_ms();
  scene_runtime_note("stadium","LoadedCall begin");
  stadium_loaded_original(loader);
  const uint64_t native_done=scene_runtime_ms();
  scene_runtime_note("stadium","native LoadedCall returned");
  __atomic_store_n(&stadium_canary_active, 0, __ATOMIC_RELEASE);
  if (!stadium_world || !*stadium_world) return;
  Ue4Array actors = {0};
  stadium_get_actors(*stadium_world, stadium_actor_class(), &actors);
  if (!actors.data || actors.num <= 0 || actors.num > 4096 ||
      actors.max < actors.num) {
    if (actors.data) stadium_engine_free(actors.data);
    return;
  }
  const int requested = pes_controller_2p_prematch_hub_stadium_index() == 1;
  void *carrier = NULL, *carrier_actor = NULL;
  int previous_canary = 0;
  for (int32_t i = 0; i < actors.num; ++i) {
    void *actor = ((void **)actors.data)[i];
    if (!actor) continue;
    // Offsets are gated against instructions in the owned runtime at install.
    void *component = stadium_actor_component(actor);
    if (!component) continue;
    void *mesh = *(void **)((char *)component + 0x5b0);
    char name[96];
    if (!mesh || !stadium_object_name(mesh, name)) continue;
    if (!strcmp(name, "AnfieldShell")) previous_canary = 1;
    if (!strcmp(name, "st029_b") || !strcmp(name, "AnfieldShell")) {
      carrier = component; carrier_actor = actor;
    }
  }
  if (!carrier || (!requested && !previous_canary)) {
    stadium_canary_note(requested
        ? "Anfield not applied: native shell carrier unavailable. Test with High quality."
        : "Konami stadium selected.");
    stadium_engine_free(actors.data); return;
  }
  const uint64_t asset_begin=scene_runtime_ms();
  void *replacement = stadium_load_mesh(requested
      ? "/Game/FootballNX/Stadiums/Anfield/AnfieldShell.AnfieldShell"
      : "/Game/Assets/bg_lighting_AM1/Meshes/st029_b.st029_b");
  if (!replacement) {
    stadium_canary_note("Stadium replacement asset unavailable; native shell retained.");
    stadium_engine_free(actors.data); return;
  }
  const uint64_t asset_done=scene_runtime_ms();
  int cleared_lods=0;
  const int mesh_changed=*(void **)((char *)carrier+0x5b0)!=replacement;
  if (mesh_changed) {
  // SetStaticMesh alone retains the old component's per-instance LOD data.
  // Its pre-culled index buffer belongs to st029_b, NOT the replacement mesh:
  // reusing those triangle ranges can punch holes through unrelated sections.
  // The native context preserves whether this component was registered. Its
  // audited layout is two 8-byte weak object pointers (component and world).
  _Alignas(16) uint64_t registration[2] = {0};
  stadium_reregister_begin(registration, carrier);
  stadium_set_mobility(carrier, 2);
  if (!stadium_set_mesh(carrier, replacement) &&
      *(void **)((char *)carrier + 0x5b0) != replacement) {
    stadium_reregister_end(registration);
    stadium_canary_note("Stadium replacement rejected by native component.");
    stadium_engine_free(actors.data); return;
  }
  // Release queues GPU work. Finish it before native LOD destructors free the
  // old pre-culled index buffers, override colours and baked-light references.
  stadium_release_resources(carrier);
  stadium_flush_rendering(0);
  cleared_lods=stadium_set_lod_count(carrier, 0, 0);
  stadium_set_forced_lod(carrier, 0);
  stadium_empty_materials(carrier);
  stadium_set_collision(carrier, 0);
  stadium_set_cast_shadow(carrier, 0);
  // Mobility is needed only during replacement. The shell never moves:
  // restore Static before registration so UE can retain its static draw data.
  // Crowd motion is UV-only and does not change bounds or vertex positions.
  stadium_set_mobility(carrier, 0);
  stadium_reregister_end(registration);
  } // Repeated LoadedCall for the same mesh needs no GPU drain/re-registration.
  stadium_hide_actor(carrier_actor, 0);
  for (int32_t i = 0; i < actors.num; ++i) {
    void *actor = ((void **)actors.data)[i];
    if (!actor || actor == carrier_actor) continue;
    void *component = stadium_actor_component(actor);
    if (!component) continue;
    void *mesh = *(void **)((char *)component + 0x5b0);
    char name[96];
    if (mesh && stadium_object_name(mesh, name) && stadium_shell_member(name))
      stadium_hide_actor(actor, requested);
  }
  stadium_engine_free(actors.data);
  __atomic_store_n(&stadium_canary_active, requested, __ATOMIC_RELEASE);
  char timing[160];
  snprintf(timing,sizeof(timing),"load ms: native=%llu actors=%llu asset=%llu apply=%llu replaced=%d",
      (unsigned long long)(native_done-started),
      (unsigned long long)(asset_begin-native_done),
      (unsigned long long)(asset_done-asset_begin),
      (unsigned long long)(scene_runtime_ms()-asset_done),mesh_changed);
  scene_runtime_note("stadium",timing);
  stadium_canary_note(!requested ? "Konami stadium restored." : cleared_lods
      ? "Anfield v5 applied; old instance LOD/pre-cull/lightmap caches released."
      : "Anfield v5 applied; existing component resources retained.");
}
#ifndef PESNX_STADIUM_CANARY_HOST_TEST
static void install_stadium_canary(so_module *module) {
  FILE *package = fopen("PesMobile/Content/Paks/PesMobile-Anfield-Android_ETC1_P.pak", "rb");
  if (!package) return;
  fclose(package);
  scene_runtime_begin();
  const char *root_symbol =
      "_ZN6AActor23execK2_GetRootComponentEP7UObjectR6FFramePv";
  const char *mesh_symbol =
      "_ZN20UStaticMeshComponent13SetStaticMeshEP11UStaticMesh";
  if (!so_try_find_addr_rx(module, root_symbol) ||
      !so_try_find_addr_rx(module, mesh_symbol)) return;
  // Installation precedes so_finalize: RX is only reserved at this point.
  // Inspect/patch the readable backing; retain RX only for later native calls.
  const uintptr_t root_fn = so_find_addr(module, root_symbol);
  const uintptr_t mesh_fn = so_find_addr(module, mesh_symbol);
  if (*(const uint32_t *)(root_fn + 16) != 0xf940ac08 ||
      *(const uint32_t *)(mesh_fn + 40) != 0xf942d808) return;
  const uintptr_t loaded_plt = (uintptr_t)module->load_base + 0x38c3dc0;
  const uint32_t words[] = {0xb002e2f0,0xf9409e11,0x9104e210,0xd61f0220};
  if (memcmp((void *)loaded_plt, words, sizeof(words))) return;
#define STADIUM_BIND(target, symbol) do { \
  target = (void *)so_try_find_addr_rx(module, symbol); \
  if (!target) return; \
} while (0)
  STADIUM_BIND(stadium_loaded_original, "_ZN14AStadiumLoader10LoadedCallEv");
  STADIUM_BIND(stadium_actor_class, "_ZN16AStaticMeshActor21GetPrivateStaticClassEv");
  STADIUM_BIND(stadium_mesh_class, "_ZN11UStaticMesh21GetPrivateStaticClassEv");
  STADIUM_BIND(stadium_component_class, "_ZN20UStaticMeshComponent21GetPrivateStaticClassEv");
  STADIUM_BIND(stadium_get_actors, "_ZN16UGameplayStatics19GetAllActorsOfClassEPK7UObject11TSubclassOfI6AActorER6TArrayIPS4_17FDefaultAllocatorE");
  STADIUM_BIND(stadium_load_object, "_Z16StaticLoadObjectP6UClassP7UObjectPKDsS4_jP11UPackageMapbP24FUObjectSerializeContext");
  STADIUM_BIND(stadium_fname_string, "_ZNK5FName8ToStringER7FString");
  STADIUM_BIND(stadium_engine_free, "_ZN7FMemory4FreeEPv");
  STADIUM_BIND(stadium_set_mesh, "_ZN20UStaticMeshComponent13SetStaticMeshEP11UStaticMesh");
  STADIUM_BIND(stadium_empty_materials, "_ZN14UMeshComponent22EmptyOverrideMaterialsEv");
  STADIUM_BIND(stadium_hide_actor, "_ZN6AActor20SetActorHiddenInGameEb");
  STADIUM_BIND(stadium_set_mobility, "_ZN15USceneComponent11SetMobilityEN18EComponentMobility4TypeE");
  STADIUM_BIND(stadium_set_collision, "_ZN19UPrimitiveComponent19SetCollisionEnabledEN17ECollisionEnabled4TypeE");
  STADIUM_BIND(stadium_set_cast_shadow, "_ZN19UPrimitiveComponent13SetCastShadowEb");
  STADIUM_BIND(stadium_reregister_begin, "_ZN27FComponentReregisterContextC2EP15UActorComponent");
  STADIUM_BIND(stadium_reregister_end, "_ZN27FComponentReregisterContextD2Ev");
  STADIUM_BIND(stadium_release_resources, "_ZN20UStaticMeshComponent16ReleaseResourcesEv");
  STADIUM_BIND(stadium_flush_rendering, "_Z22FlushRenderingCommandsb");
  STADIUM_BIND(stadium_set_lod_count, "_ZN20UStaticMeshComponent15SetLODDataCountEjj");
  STADIUM_BIND(stadium_set_forced_lod, "_ZN20UStaticMeshComponent17SetForcedLodModelEi");
  STADIUM_BIND(stadium_world, "GWorld");
#undef STADIUM_BIND
  hook_arm64(loaded_plt, (uintptr_t)stadium_loaded_canary);
  stadium_canary_installed = 1;
  stadium_canary_note("Anfield package detected; select ANFIELD (TEST) in Stadium settings.");
}
#endif
