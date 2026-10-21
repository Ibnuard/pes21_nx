/* Run the actual optional installers before the executable mapping exists.
 * Keep that mapping inaccessible, as it is on Switch before so_finalize(). */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <sys/mman.h>
#endif

typedef struct { void *data; int32_t num, max; } Ue4Array;
typedef struct { void *load_base, *load_virtbase; size_t load_size; } so_module;
static const char *missing_symbol;
static size_t hooks;
static uintptr_t hook_sites[32], hook_targets[32];
static so_module *active_module;
static const char root_symbol[] =
    "_ZN6AActor23execK2_GetRootComponentEP7UObjectR6FFramePv";
static const char mesh_symbol[] =
    "_ZN20UStaticMeshComponent13SetStaticMeshEP11UStaticMesh";
static const char model_symbol[] =
    "_ZN5match5Human11CreateModelERKN4draw4load11HumanLoadIdE";
static const char observer_symbol[] =
    "_ZN5match6record17ObserverOutOfPlay4ExecERNS_8registry11RecordEventERKNS0_13ObserverInputE";
static const char demo_symbol[] =
    "_ZN11FixDemoMain20GetUpdateHumanPosRotERN4math7Vector3ERNS0_10QuaternionEjhhff";
static const char flow_symbol[] = "_ZN5match4Flow9ResetFlowENS_8FlowKindE";
static const char warp_symbol[] = "_ZN5match4Flow16ExecPositionWarpEPKN5cobra4game7ContextE";
static const char render_model_symbol[] = "_ZN6render11PlayerModel6UpdateEv";
static const char ue_load_symbol[] = "_ZN13UEPlayerModel8LoadImplEv";
static const char vision_symbol[] = "_ZN18VisionModelManager11VisionModelC2Ejj";

static size_t symbol_offset(const char *symbol) {
  if (!strcmp(symbol,"_ZN5match8registry14GlobalRegistry8OpenReadEv")) return 0x1100;
  if (!strcmp(symbol, root_symbol)) return 0x100;
  if (!strcmp(symbol, mesh_symbol)) return 0x400;
  if (!strcmp(symbol, model_symbol)) return 0x700;
  if (!strcmp(symbol, observer_symbol)) return 0x900;
  if (!strcmp(symbol, demo_symbol)) return 0xa00;
  if (!strcmp(symbol, flow_symbol)) return 0xb00;
  if (!strcmp(symbol, warp_symbol)) return 0xc00;
  if (!strcmp(symbol, render_model_symbol)) return 0xd00;
  if (!strcmp(symbol, ue_load_symbol)) return 0xe00;
  if (!strcmp(symbol, vision_symbol)) return 0xf00;
  return 0x1000;
}
uintptr_t so_find_addr(so_module *module, const char *symbol) {
  assert(!missing_symbol || strcmp(symbol, missing_symbol));
  return (uintptr_t)module->load_base + symbol_offset(symbol);
}
static uintptr_t so_try_find_addr_rx(so_module *module, const char *symbol) {
  if (missing_symbol && !strcmp(symbol, missing_symbol)) return 0;
  return (uintptr_t)module->load_virtbase + symbol_offset(symbol);
}
static void hook_arm64(uintptr_t address, uintptr_t target) {
  uintptr_t backing = (uintptr_t)active_module->load_base;
  assert(address >= backing && address - backing <= active_module->load_size - 16);
  assert(hooks < 32 && target);
  hook_sites[hooks] = address - backing;
  hook_targets[hooks++] = target;
  const uint32_t words[] = {0x58000051u, 0xd61f0220u};
  memcpy((void *)address, words, sizeof(words));
  memcpy((void *)(address + 8), &target, sizeof(target));
}
uint32_t pes_controller_2p_prematch_hub_stadium_index(void) { return 0; }
uint32_t pes_controller_stadium_weather(void) { return 0; }
uint32_t pes_controller_stadium_season(void) { return 0; }
static void *exhibition_get_tmpdb_match(void) { return NULL; }
static uint64_t armGetSystemTick(void) { return 1; }
static uint64_t armTicksToNs(uint64_t n) { return n; }
static int referee_probe_scene_active(void) { return 0; }
static int referee_probe_restart_active(void) { return 0; }
#include "../source/stadium_canary.inc"
#include "../source/referee_probe.inc"
static uint32_t weather_scene_kind;
static int pes_controller_pause_skin_active(void) {return 0;}
static int pes_controller_pause_transition(void) {return 0;}
static int pes_controller_match_hud_inplay(void) {return 0;}
#include "../source/weather_scene.inc"
#include "referee_animation_fixture.h"

static void word(so_module *module, size_t offset, uint32_t value) {
  memcpy((char *)module->load_base + offset, &value, sizeof(value));
}
static void plt(so_module *module, size_t offset, const uint32_t words[4]) {
  memcpy((char *)module->load_base + offset, words, 16);
}

int main(int argc, char **argv) {
  assert(argc == 3);
  const int stadium = !strcmp(argv[1], "stadium");
  const int weather = !strcmp(argv[1], "weather");
  const char *scenario = argv[2];
  so_module module = {.load_size = 0x4000000};
  module.load_base = calloc(1, module.load_size);
  assert(module.load_base);
#ifdef _WIN32
  SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX);
  module.load_virtbase = VirtualAlloc(NULL, module.load_size, MEM_RESERVE, PAGE_NOACCESS);
  assert(module.load_virtbase);
#else
  module.load_virtbase = mmap(NULL, module.load_size, PROT_NONE,
                             MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
  assert(module.load_virtbase != MAP_FAILED);
#endif
  active_module = &module;
  word(&module, 0x100 + 16, 0xf940ac08);
  word(&module, 0x400 + 40, 0xf942d808);
  word(&module, 0x700 + 164, 0x52808900);
  word(&module, 0x900 + 0x64, 0x52800481);
  word(&module, 0x900 + 0x80, 0x91005280);
  word(&module, 0xa00 + 0x7c, 0xf94676ea);
  word(&module, 0xa00 + 0x80, 0xf94672e8);
  word(&module, 0xb00 + 0xc, 0xb90cd401);
  word(&module, 0xc00 + 0xc, 0x39754808);
  word(&module, 0xd00 + 0x44, 0xf9005a60);
  word(&module, 0xe00, 0xd102c3ff);
  word(&module, 0xf00 + 0x18, 0xb9003001);
  word(&module, 0x1100 + 0x2a4, 0xf9650a68);
  word(&module, 0x1100 + 0x2b8, 0x52894208);
  word(&module, 0x1100 + 0x2c0, 0x8b080261);
  const uint32_t stadium_words[] = {0xb002e2f0,0xf9409e11,0x9104e210,0xd61f0220};
  const uint32_t draw_words[] = {0xd002e370,0xf9440211,0x91200210,0xd61f0220};
  const uint32_t create_words[] = {0x9002e3b0,0xf9436611,0x911b2210,0xd61f0220};
  const uint32_t loaded_words[] = {0x9002e5f0,0xf9438a11,0x911c4210,0xd61f0220};
  const uint32_t release_words[] = {0xb002e5b0,0xf942ba11,0x9115c210,0xd61f0220};
  const uint32_t unload_words[] = {0xf002e270,0xf945c211,0x912e0210,0xd61f0220};
  plt(&module, 0x38c3dc0, stadium_words);
  plt(&module, 0x38a0b50, draw_words);
  plt(&module, 0x38948e0, create_words);
  plt(&module, 0x3804970, loaded_words);
  plt(&module, 0x3812630, release_words);
  plt(&module, 0x38dd250, unload_words);
  const uint32_t animation_words[] = {0xb002e5b0,0xf9453e11,0x9129e210,0xd61f0220};
  const uint32_t manager_words[] = {0x9002e3b0,0xf943f211,0x911f8210,0xd61f0220};
  plt(&module, 0x3811040, animation_words);
  plt(&module, 0x3894b10, manager_words);
  const uint32_t destroy_loader_words[] = {0xd002e2b0,0xf9465611,0x9132a210,0xd61f0220};
  const uint32_t out_words[] = {0xf002e630,0xf9453a11,0x9129c210,0xd61f0220};
  plt(&module, 0x38cf4a0, destroy_loader_words);
  plt(&module, 0x37ed030, out_words);
  const uint32_t sound_words[] = {0x9002e590,0xf941ba11,0x910dc210,0xd61f0220};
  plt(&module, 0x381c230, sound_words);
  const uint32_t warp_words[] = {0xf002e2f0,0xf946de11,0x9136e210,0xd61f0220};
  const uint32_t demo_words[] = {0x9002e4f0,0xf940a211,0x91050210,0xd61f0220};
  plt(&module, 0x38bd6c0, warp_words);
  plt(&module, 0x3845dd0, demo_words);
  const uint32_t model_update_words[] = {0xf002e170,0xf9436e11,0x911b6210,0xd61f0220};
  const uint32_t queue_player_words[] = {0xf002e4b0,0xf9441e11,0x9120e210,0xd61f0220};
  const uint32_t load_player_words[] = {0x9002e3f0,0xf944fe11,0x9127e210,0xd61f0220};
  const uint32_t quality_words[] = {0xd002e470,0xf9449a11,0x9124c210,0xd61f0220};
  plt(&module,0x391e900,model_update_words);
  plt(&module,0x384ebc0,queue_player_words);
  plt(&module,0x3884f40,load_player_words);
  plt(&module,0x3860db0,quality_words);
  const uint32_t tick_words[] = {0x9002e170,0xf9425211,0x91128210,0xd61f0220};
  plt(&module, 0x3924490, tick_words);
  const uint32_t render_words[] = {0xf002e3f0,0xf9407611,0x9103a210,0xd61f0220};
  plt(&module, 0x387fd20, render_words);
  if (!strcmp(scenario, "missing-gate"))
    missing_symbol = stadium ? root_symbol : model_symbol;
  if (!strcmp(scenario, "missing-binding"))
    missing_symbol = stadium ? "GWorld" : "_ZN4draw5Human7SetDispEb";
  if (!strcmp(scenario, "bad-opcode"))
    word(&module, stadium ? 0x100 + 16 : 0x700 + 164, 0);
  if (!strcmp(scenario, "bad-plt"))
    word(&module, stadium ? 0x38c3dc0 : 0x38dd250, 0);
  if (!strcmp(scenario, "bad-retire-plt"))
    word(&module, 0x38c3dc0, 0);
  if (!strcmp(scenario, "bad-event-plt"))
    word(&module, 0x37ed030, 0);
  if (!strcmp(scenario, "bad-sound-plt"))
    word(&module, 0x381c230, 0);
  if (!strcmp(scenario, "bad-warp-plt"))word(&module, 0x38bd6c0, 0);
  if (!strcmp(scenario, "bad-demo-plt"))word(&module, 0x3845dd0, 0);
  if (!strcmp(scenario, "bad-demo-layout"))word(&module, 0xa00 + 0x80, 0);
  if (!strcmp(scenario, "bad-flow-layout"))word(&module, 0xb00 + 0xc, 0);
  if (!strcmp(scenario, "bad-warp-layout"))word(&module, 0xc00 + 0xc, 0);
  if (!strcmp(scenario, "bad-render-layout"))word(&module, 0xd00 + 0x44, 0);
  if (!strcmp(scenario, "bad-load-layout"))word(&module, 0xe00, 0);
  if (!strcmp(scenario, "bad-vision-layout"))word(&module, 0xf00 + 0x18, 0);
  if (!strcmp(scenario, "bad-field-layout"))word(&module, 0x1100 + 0x2a4, 0);
  if (!strcmp(scenario, "bad-field-destination"))word(&module, 0x1100 + 0x2b8, 0);
  if (!strcmp(scenario, "bad-field-lock"))word(&module, 0x1100 + 0x2c0, 0);
  if (!strcmp(scenario, "bad-render-plt"))word(&module, 0x391e900, 0);
  if (!strcmp(scenario, "bad-queue-plt"))word(&module, 0x384ebc0, 0);
  if (!strcmp(scenario, "bad-load-plt"))word(&module, 0x3884f40, 0);
  if (!strcmp(scenario, "bad-quality-plt"))word(&module, 0x3860db0, 0);
  if (!strcmp(scenario, "bad-event-layout"))
    word(&module, 0x900 + 0x80, 0);
  if (!strcmp(scenario, "bad-preload-plt"))
    word(&module, 0x3804970, 0);
  if (!strcmp(scenario, "bad-frame-plt"))
    word(&module, 0x38a0b50, 0);
  if (!stadium && strcmp(scenario,"missing-animation")) {
    size_t n;unsigned char *data=referee_animation_fixture(&n);
    FILE *f=fopen("Animations/referee.nxra","wb");assert(f);
    assert(fwrite(data,1,n,f)==n);fclose(f);free(data);
  }

  if (weather) {
    install_stadium_canary(&module);install_referee_probe(&module);install_weather_scene(&module);
    const unsigned has_stadium=!strcmp(scenario,"stadium")||!strcmp(scenario,"both");
    const unsigned has_referee=!strcmp(scenario,"referee")||!strcmp(scenario,"both");
    assert(stadium_canary_installed==has_stadium&&referee_probe_enabled==has_referee);
    assert(hooks==has_stadium+17*has_referee+4);
    assert(hook_targets[hooks-4]==(uintptr_t)weather_scene_loaded);
    /* Renderer setup must stay native in the crash-recovery build. */
    assert(!memcmp((char *)module.load_base+0x387fd20,render_words,16));
    assert(weather_loaded_original==(has_referee?referee_probe_loaded_scene:
        has_stadium?stadium_loaded_canary:(void*)((uintptr_t)module.load_virtbase+0x1000)));
    if(has_referee) {
      assert(referee_loaded_original==(has_stadium?stadium_loaded_canary:
          (void*)((uintptr_t)module.load_virtbase+0x1000)));
      assert(weather_unload_original==referee_probe_unload);
      assert(weather_destroy_original==referee_probe_destroy_loader);
    }
  } else {
  if (stadium) install_stadium_canary(&module);
  else install_referee_probe(&module);
  const int expected = !strcmp(scenario, "enabled") || !strcmp(scenario, "selected-packages") || !strcmp(scenario, "campnou-only");
  assert(hooks == (expected ? (stadium ? 1u : 17u) : 0u));
  assert((stadium ? stadium_canary_installed : referee_probe_enabled) == (unsigned)expected);
  if (expected) {
    /* Bind eventual native calls to RX, but only inspect/patch backing now. */
    uintptr_t runtime = (uintptr_t)module.load_virtbase;
    if (stadium) {
      if (!strcmp(scenario,"selected-packages")) {
        const unsigned wanted[]={0,1,2,8,9,12,13};
        assert(stadium_available_count==sizeof(wanted)/sizeof(wanted[0]));
        for(unsigned i=0;i<stadium_available_count;i++)assert(stadium_available[i]==wanted[i]);
        assert(!strcmp(pes_controller_stadium_catalog_label(5),"OLD TRAFFORD"));
        assert(!strcmp(pes_controller_stadium_catalog_label(6),"CAMP NOU"));
      } else if (!strcmp(scenario,"campnou-only")) {
        assert(stadium_available_count==2 && stadium_available[1]==13);
        assert(!strcmp(pes_controller_stadium_catalog_label(1),"CAMP NOU"));
      }
      assert((uintptr_t)stadium_set_mesh == runtime + 0x400);
      assert((uintptr_t)stadium_loaded_original == runtime + 0x1000);
      assert(hook_sites[0] == 0x38c3dc0);
      assert(hook_targets[0] == (uintptr_t)stadium_loaded_canary);
    } else {
      assert((uintptr_t)referee_ctor == runtime + 0x1000);
      assert((uintptr_t)referee_draw_original == runtime + 0x1000);
      assert(hook_sites[0] == 0x38a0b50 && hook_sites[1] == 0x38948e0 &&
             hook_sites[2] == 0x3804970);
      assert(hook_targets[0] == (uintptr_t)referee_probe_draw);
      /* The broad ResetFlow PLT remains native. Fade polling is gone. */
      assert(hook_sites[11]==0x38bd6c0 && hook_targets[11]==(uintptr_t)referee_probe_position_warp);
      assert(hook_sites[13]==0x391e900 && hook_targets[13]==(uintptr_t)referee_probe_render_update);
    }
  }
  }
#ifdef _WIN32
  VirtualFree(module.load_virtbase, 0, MEM_RELEASE);
#else
  munmap(module.load_virtbase, module.load_size);
#endif
  free(module.load_base);
  free(referee_animation_data);
  puts("optional bootstrap: pass");
  return 0;
}
