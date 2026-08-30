#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#include <switch.h>

#include "android_shim.h"
#include "config.h"
#include "error.h"
#include "hooks.h"
#include "imports.h"
#include "jni_fake.h"
#include "so_util.h"
#include "ue4_hooks.h"
#include "util.h"

static void *heap_so_base;
static size_t heap_so_limit;
static uint8_t main_fake_tls[0x100] __attribute__((aligned(16)));
static Thread constructor_watchdog_thread;
static Thread *main_thread;
static volatile int constructor_watchdog_cancel;

so_module avs_mod;
so_module afp_mod;
so_module ue4_mod;

size_t g_mem_total_mb;
size_t g_mem_newlib_mb;
size_t g_mem_so_mb;

// UE4 needs more CPU-side memory than GTA, so start with a smaller NV pool.
u32 __nx_nv_transfermem_size = 0x40000000;

volatile int g_hide_saves = 0;

void __libnx_initheap(void) {
  void *addr;
  size_t size = 0;
  size_t mem_available = 0;
  size_t mem_used = 0;

  if (envHasHeapOverride()) {
    addr = envGetHeapOverrideAddr();
    size = envGetHeapOverrideSize();
  } else {
    svcGetInfo(&mem_available, InfoType_TotalMemorySize, CUR_PROCESS_HANDLE, 0);
    svcGetInfo(&mem_used, InfoType_UsedMemorySize, CUR_PROCESS_HANDLE, 0);
    if (mem_available > mem_used + 0x200000)
      size = (mem_available - mem_used - 0x200000) & ~0x1fffff;
    if (!size)
      size = 0x20000000;
    Result rc = svcSetHeapSize(&addr, size);
    if (R_FAILED(rc))
      diagAbortWithResult(MAKERESULT(Module_Libnx, LibnxError_HeapAllocFailed));
  }

  size_t so_region = (size_t)MEMORY_SO_MB * 1024 * 1024;
  if (so_region > size / 3)
    so_region = size / 3;
  const size_t newlib_size = size - so_region;

  extern char *fake_heap_start;
  extern char *fake_heap_end;
  fake_heap_start = addr;
  fake_heap_end = (char *)addr + newlib_size;

  heap_so_base = (void *)ALIGN_MEM((uintptr_t)addr + newlib_size, 0x1000);
  heap_so_limit = (char *)addr + size - (char *)heap_so_base;
  g_mem_total_mb = size >> 20;
  g_mem_newlib_mb = newlib_size >> 20;
  g_mem_so_mb = so_region >> 20;
}

static void check_syscalls(void) {
  if (!envIsSyscallHinted(0x77) || !envIsSyscallHinted(0x78) ||
      !envIsSyscallHinted(0x73))
    debugPrintf("warning: code-memory syscalls are not hinted; trying them directly\n");
}

typedef struct {
  const char *path;
  size_t expected_size;
} RuntimeFile;

static const RuntimeFile required_runtime_files[] = {
  { AVS_SO_NAME, 491032 },
  { AFP_SO_NAME, 1401216 },
  { UE4_SO_NAME, 157571792 },
  { "PesMobile/Content/Paks/PesMobile-Android_ETC1.pak", 459211124 },
  { "patch.305030001.jp.nyan2021.pesam.obb", 1391120384 },
  { "Download/dt530_mobile_bra_all.cpk", 173204 },
  { "Download/dt530_mobile_can_all.cpk", 165480 },
  { "Download/dt530_mobile_eng_all.cpk", 198701 },
  { "Download/dt530_mobile_fra_all.cpk", 193581 },
  { "Download/dt530_mobile_ger_all.cpk", 188884 },
  { "Download/dt530_mobile_ita_all.cpk", 189454 },
  { "Download/dt530_mobile_jpn_all.cpk", 235766 },
  { "Download/dt530_mobile_kor_all.cpk", 129215 },
  { "Download/dt530_mobile_man_all.cpk", 165584 },
  { "Download/dt530_mobile_spa_all.cpk", 194310 },
  { "assets/responses/CMD_GET_SERVER_ENV.bin", 1608 },
  { "assets/responses/CmdCheckString.bin", 80 },
  { "assets/responses/CmdCreateUser.bin", 208 },
  { "assets/responses/CmdExtendMyclubCoach.bin", 120 },
  { "assets/responses/CmdExtendMyclubGameplayer.bin", 120 },
  { "assets/responses/CmdGetCountryList.bin", 2384 },
  { "assets/responses/CmdGetMaintenanceInfo.bin", 128 },
  { "assets/responses/CmdGetMyclubAchievementlist.bin", 176 },
  { "assets/responses/CmdGetMyclubAgentBoxInfo.bin", 144 },
  { "assets/responses/CmdGetMyclubAgentlist.bin", 376 },
  { "assets/responses/CmdGetMyclubCoachContractNorma.bin", 200 },
  { "assets/responses/CmdGetMyclubCommentaryInfo.bin", 440 },
  { "assets/responses/CmdGetMyclubEntryInfo.bin", 2520 },
  { "assets/responses/CmdGetMyclubMainmenuInfo.bin", 1272 },
  { "assets/responses/CmdGetMyclubMarketAgentlist.bin", 176 },
  { "assets/responses/CmdGetMyclubMatchStats.bin", 120 },
  { "assets/responses/CmdGetMyclubPresentlist.bin", 112 },
  { "assets/responses/CmdGetMyclubProcurableGameplayerlist.bin", 272 },
  { "assets/responses/CmdGetMyclubVscomOpponent.bin", 248 },
  { "assets/responses/CmdGetProductList.bin", 448 },
  { "assets/responses/CmdGetServerEnv.bin", 1608 },
  { "assets/responses/CmdLogin.bin", 2544 },
  { "assets/responses/CmdRecoverEnergy.bin", 112 },
  { "assets/responses/CmdSendDownloadStatsData.bin", 88 },
  { "assets/responses/CmdSendHeartbeat.bin", 96 },
  { "assets/responses/CmdSendMatchTeamInfo.bin", 112 },
  { "assets/responses/CmdSendPlaylog.bin", 72 },
  { "assets/responses/CmdSetDevicetoken.bin", 80 },
  { "assets/responses/CmdSetMatchResult.bin", 312 },
  { "assets/responses/CmdSetMyclubEntryInfo.bin", 2520 },
  { "assets/responses/CmdSetMyclubLanguage.bin", 80 },
  { "assets/responses/CmdSetMyclubLockGameplayer.bin", 104 },
  { "assets/responses/CmdSetMyclubMainSquad.bin", 96 },
  { "assets/responses/CmdSetMyclubSeasonUpdateInfo.bin", 104 },
  { "assets/responses/CmdSetMyclubSquadInfo.bin", 96 },
  { "assets/responses/CmdSetMyclubSquadName.bin", 96 },
  { "assets/responses/CmdSetMyclubTutorialAchievementInfo.bin", 104 },
  { "assets/responses/CmdSetMyclubUserInfo.bin", 88 },
  { "assets/responses/CmdSetUserUpdateInfo.bin", 80 },
  { "assets/responses/CmdStartMatch.bin", 216 },
  { "assets/responses/CmdUseMyclubAgent.bin", 632 },
  { "assets/responses/generic.bin", 56 },
  { "assets/responses/get_myclub_coaches_norma.bin", 200 },
  { "assets/responses/get_myclub_commentary_info.bin", 440 },
  { "assets/responses/get_myclub_mainmenu_info.bin", 1272 },
  { "assets/responses/get_product_list.bin", 448 },
  { "assets/responses/GetCountryList.bin", 2384 },
  { "assets/responses/set_myclub_entry_info.bin", 2520 },
};

static void check_data(void) {
  const char *first_bad = NULL;
  size_t bad_count = 0;

  for (size_t i = 0;
       i < sizeof(required_runtime_files) / sizeof(required_runtime_files[0]);
       i++) {
    const RuntimeFile *required = &required_runtime_files[i];
    struct stat st;
    const int stat_rc = stat(required->path, &st);
    if (stat_rc == 0 && S_ISREG(st.st_mode) &&
        (size_t)st.st_size == required->expected_size)
      continue;

    if (!first_bad)
      first_bad = required->path;
    bad_count++;
    debugPrintf("runtime validation failed: %s expected=%zu actual=%lld\n",
                required->path, required->expected_size,
                stat_rc == 0 ? (long long)st.st_size : -1LL);
  }

  if (bad_count)
    fatal_error("Loose runtime data is incomplete.\nFirst bad file:\n%s\n"
                "Missing/corrupt files: %zu",
                first_bad, bad_count);

  debugPrintf("runtime validation: %zu loose files OK\n",
              sizeof(required_runtime_files) / sizeof(required_runtime_files[0]));
}

static void set_screen_size(void) {
  if (config.screen_width > 0 && config.screen_height > 0 &&
      config.screen_width <= 1920 && config.screen_height <= 1080) {
    screen_width = config.screen_width;
    screen_height = config.screen_height;
  } else {
    // The game renders its 3D scene near 576p. Matching that surface avoids a
    // costly full-screen upscale/composite on Switch while keeping a 16:9 UI.
    screen_width = 1024;
    screen_height = 576;
  }
}

static void load_module(so_module *mod, const char *name, void **cursor) {
  const size_t used = (uintptr_t)*cursor - (uintptr_t)heap_so_base;
  if (used >= heap_so_limit ||
      so_load(mod, name, *cursor, heap_so_limit - used) < 0)
    fatal_error("Could not load %s.\nSO region: %zu MiB", name, g_mem_so_mb);
  *cursor = (void *)ALIGN_MEM((uintptr_t)*cursor + mod->load_size, 0x1000);
}

static void init_android_tls(void) {
  memset(main_fake_tls, 0, sizeof(main_fake_tls));
  armSetTlsRw(main_fake_tls);
  debugPrintf("stage: Android-compatible main TLS installed at %p\n",
              main_fake_tls);
}

static void constructor_watchdog(void *arg) {
  (void)arg;
  svcSleepThread(30000000000LL);
  if (constructor_watchdog_cancel || !main_thread)
    return;

  Result rc = threadPause(main_thread);
  if (R_FAILED(rc)) {
    debugPrintf("watchdog: threadPause failed: %08x\n", rc);
    return;
  }

  ThreadContext context;
  memset(&context, 0, sizeof(context));
  rc = threadDumpContext(&context, main_thread);
  if (R_SUCCEEDED(rc)) {
    const uintptr_t base = (uintptr_t)ue4_mod.load_virtbase;
    const uintptr_t pc = (uintptr_t)context.pc.x;
    const uintptr_t lr = (uintptr_t)context.lr;
    const uintptr_t end = base + ue4_mod.load_size;
    debugPrintf("watchdog: PC=%p %s LR=%p %s SP=%p FP=%p\n",
                (void *)pc,
                pc >= base && pc < end ? "in UE4" : "native",
                (void *)lr,
                lr >= base && lr < end ? "in UE4" : "native",
                (void *)context.sp, (void *)context.fp);
    debugPrintf("watchdog: X0=%p X1=%p X2=%p X3=%p X4=%p X5=%p\n",
                (void *)context.cpu_gprs[0].x,
                (void *)context.cpu_gprs[1].x,
                (void *)context.cpu_gprs[2].x,
                (void *)context.cpu_gprs[3].x,
                (void *)context.cpu_gprs[4].x,
                (void *)context.cpu_gprs[5].x);

    uintptr_t frame = (uintptr_t)context.fp;
    const uintptr_t stack_start = (uintptr_t)context.sp;
    for (int depth = 0; depth < 16; depth++) {
      if ((frame & 0xf) || frame < stack_start ||
          frame - stack_start > 0x200000)
        break;

      const uintptr_t previous = *(const uintptr_t *)frame;
      const uintptr_t return_address = *(const uintptr_t *)(frame + 8);
      debugPrintf("watchdog: frame[%d] fp=%p prev=%p return=%p",
                  depth, (void *)frame, (void *)previous,
                  (void *)return_address);
      if (return_address >= base && return_address < end)
        debugPrintf(" UE4+0x%lx\n", return_address - base);
      else
        debugPrintf(" native\n");

      if (previous <= frame || previous - frame > 0x100000)
        break;
      frame = previous;
    }
  } else {
    debugPrintf("watchdog: threadDumpContext failed: %08x\n", rc);
  }
  threadResume(main_thread);
}

static void start_constructor_watchdog(void) {
  main_thread = threadGetSelf();
  Result rc = threadCreate(&constructor_watchdog_thread, constructor_watchdog,
                           NULL, NULL, 0x8000, 0x2c, 2);
  if (R_SUCCEEDED(rc))
    rc = threadStart(&constructor_watchdog_thread);
  if (R_FAILED(rc))
    debugPrintf("watchdog: could not start: %08x\n", rc);
}

void hard_exit(void) {
  thread_registry_pause_others();
  extern void NX_NORETURN __libnx_exit(int rc);
  __libnx_exit(0);
}

int main(void) {
  // Direct homebrew launchers may start in sdmc:/ instead of the NRO folder.
  (void)chdir("sdmc:/switch/pes21_nx");
  cpu_boost(1);
  setenv("MESA_GLTHREAD", "false", 1);
  setenv("GALLIUM_THREAD", "0", 1);
  setenv("MESA_GLSL_CACHE_DIR", "shadercache", 1);
  setenv("MESA_GLSL_CACHE_DISABLE", "false", 1);

  if (read_config(CONFIG_NAME) < 0)
    write_config(CONFIG_NAME);
  set_screen_size();
  check_syscalls();
  check_data();

  Result socket_rc = socketInitializeDefault();
  if (R_FAILED(socket_rc))
    debugPrintf("socketInitializeDefault failed: %08x\n", socket_rc);

  debugPrintf("PES21 NX boot: heap=%zu MiB, game=%zu MiB, so=%zu MiB\n",
              g_mem_total_mb, g_mem_newlib_mb, g_mem_so_mb);

  void *cursor = heap_so_base;
  load_module(&avs_mod, AVS_SO_NAME, &cursor);
  load_module(&afp_mod, AFP_SO_NAME, &cursor);
  load_module(&ue4_mod, UE4_SO_NAME, &cursor);

  update_imports();
  so_relocate(&avs_mod);
  so_relocate(&afp_mod);
  so_relocate(&ue4_mod);
  const int missing =
      so_resolve(&avs_mod, dynlib_functions, dynlib_numfunctions, 1) +
      so_resolve(&afp_mod, dynlib_functions, dynlib_numfunctions, 1) +
      so_resolve(&ue4_mod, dynlib_functions, dynlib_numfunctions, 1);
  if (missing)
    fatal_error("Native libraries still have %d unresolved imports.\nSee debug.log.", missing);

  install_ue4_hooks(&ue4_mod);

  debugPrintf("stage: finalize AVS begin\n");
  so_finalize(&avs_mod);
  debugPrintf("stage: finalize AVS done\n");
  debugPrintf("stage: finalize AFP begin\n");
  so_finalize(&afp_mod);
  debugPrintf("stage: finalize AFP done\n");
  debugPrintf("stage: finalize UE4 begin\n");
  so_finalize(&ue4_mod);
  debugPrintf("stage: finalize UE4 done\n");

  debugPrintf("stage: flush caches begin\n");
  so_flush_caches(&avs_mod);
  so_flush_caches(&afp_mod);
  so_flush_caches(&ue4_mod);
  debugPrintf("stage: flush caches done\n");

  debugPrintf("stage: post-finalize hooks begin\n");
  ue4_hooks_post_finalize(&ue4_mod);
  debugPrintf("stage: post-finalize hooks done\n");

  start_constructor_watchdog();

  // Android arm64 code reads stack guards and thread state through TPIDR_EL0.
  // libnx's main-thread TLS layout is different, so install the same small
  // compatibility block used by the reference ports before any game code runs.
  init_android_tls();

  debugPrintf("stage: init AVS begin\n");
  so_execute_init_array(&avs_mod);
  debugPrintf("stage: init AVS done\n");
  debugPrintf("stage: init AFP begin\n");
  so_execute_init_array(&afp_mod);
  debugPrintf("stage: init AFP done\n");
  debugPrintf("stage: init UE4 begin\n");
  so_execute_init_array(&ue4_mod);
  debugPrintf("stage: init UE4 done\n");
  constructor_watchdog_cancel = 1;
  so_free_temp(&avs_mod);
  so_free_temp(&afp_mod);

  debugPrintf("stage: JNI environment init begin\n");
  jni_init();
  debugPrintf("stage: JNI environment init done\n");
  int (*jni_on_load)(void *, void *) =
      (void *)so_find_addr_rx(&ue4_mod, "JNI_OnLoad");
  debugPrintf("stage: JNI_OnLoad begin at %p\n", jni_on_load);
  const int jni_version = jni_on_load(fake_vm, NULL);
  debugPrintf("JNI_OnLoad returned %08x\n", jni_version);
  jni_set_webview_finish_navigation(
      (void *)so_find_addr_rx(
          &ue4_mod,
          "Java_jp_konami_android_common_KWebDialog_callbackOnFinishNavigation"));

  debugPrintf("stage: NativeActivity bootstrap begin\n");
  android_runtime_bootstrap(&ue4_mod);
  debugPrintf("stage: NativeActivity bootstrap done\n");
  // UE4 export lookup uses dynstrtab/syms from the temporary file image.
  so_free_temp(&ue4_mod);
  cpu_boost(0);

  while (appletMainLoop()) {
    android_input_poll();
    jni_poll_platform_callbacks();
    // Android touch/gamepad delivery is frame-oriented.  Polling at 250 Hz
    // created far more synthetic MotionEvents than the 30 FPS game thread
    // could consume during a live match.  60 Hz preserves responsive controls
    // while preventing input work from starving gameplay simulation.
    svcSleepThread(16000000);
  }

  hard_exit();
}
