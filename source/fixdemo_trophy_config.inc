/* Boot-only opt-in and bounded lifecycle journal. No gameplay polling here. */
#include "trophy_canary_config.h"
#include "runtime_assets.h"
#include <errno.h>
#include <switch/crypto/sha256.h>

#ifndef PESNX_BUILD_ID
#define PESNX_BUILD_ID "unavailable"
#endif

const char pesnx_trophy_canary_capability[] = "PESNX trophy production runtime v1";
static char fixdemo_trophy_verified_elf_sha256[65];
static int fixdemo_trophy_canary_validated;
static uint32_t fixdemo_trophy_note_count;
static uint32_t fixdemo_trophy_journal_errors;
static unsigned char fixdemo_trophy_journal_lock;
static int fixdemo_trophy_journal_ready;
static uint64_t fixdemo_trophy_boot_ms;

/* Values come from the executing build, never an installed NRO filename. The
 * tick identifies this process session; it is not a wall-clock timestamp. */
static void fixdemo_trophy_scene_status(const char *event) {
  char line[768];
  snprintf(line, sizeof(line), "revision=v60 app=%s build=%s boot_ms=%llu %s",
           PES_NX_VERSION, PESNX_BUILD_ID,
           (unsigned long long)fixdemo_trophy_boot_ms, event ? event : "");
  for (char *p = line; *p; ++p)
    if ((unsigned char)*p < 32u || (unsigned char)*p == 127u) *p = ' ';
  scene_runtime_note("ceremony status", line);
}

static void fixdemo_trophy_journal_problem(const char *stage, const char *path,
                                         int error) {
  if (__atomic_fetch_add(&fixdemo_trophy_journal_errors, 1u, __ATOMIC_RELAXED) >= 8u) return;
  char line[256];
  snprintf(line, sizeof(line), "journal %s failed path=%s errno=%d; consult this scene session",
           stage, path, error);
  fixdemo_trophy_scene_status(line);
}

static void fixdemo_trophy_note(const char *event) {
  if (__atomic_fetch_add(&fixdemo_trophy_note_count, 1u, __ATOMIC_RELAXED) >= 192u ||
      !__atomic_load_n(&fixdemo_trophy_journal_ready, __ATOMIC_ACQUIRE)) return;
  /* Lifecycle callbacks may arrive on different native queues. A competing
   * writer drops its diagnostic instead of blocking or exceeding the cap. */
  if (__atomic_test_and_set(&fixdemo_trophy_journal_lock, __ATOMIC_ACQUIRE)) return;
  char line[512];
  int length = snprintf(line, sizeof(line), "%llu %s",
                        (unsigned long long)scene_runtime_ms(), event ? event : "");
  if (length < 0) goto done;
  if ((size_t)length > sizeof(line) - 2u) length = (int)sizeof(line) - 2;
  for (int i = 0; i < length; ++i)
    if ((unsigned char)line[i] < 32u || (unsigned char)line[i] == 127u) line[i] = ' ';
  line[length++] = '\n';
  errno = 0;
  FILE *file = fopen("trophy-runtime.log", "r+b");
  const char *failure = NULL;
  int error = errno;
  if (!file) failure = "append-open";
  else {
    errno = 0;
    const int sought = fseek(file, 0, SEEK_END);
    const long bytes = sought == 0 ? ftell(file) : -1;
    error = errno;
    if (bytes < 0) failure = "append-seek";
    else if (bytes > 32768L - length) failure = "size-limit";
    else {
      errno = 0;
      if (fwrite(line, 1, (size_t)length, file) != (size_t)length) {
        failure = "append-write";
        error = errno;
      }
    }
    errno = 0;
    if (fclose(file) != 0 && !failure) { failure = "append-close"; error = errno; }
  }
  if (failure) {
    __atomic_store_n(&fixdemo_trophy_journal_ready, 0, __ATOMIC_RELEASE);
    fixdemo_trophy_journal_problem(failure, "trophy-runtime.log", error);
  }
done:
  __atomic_clear(&fixdemo_trophy_journal_lock, __ATOMIC_RELEASE);
}

/* Common install code uses this for the final enabled/ABI-rejected outcome.
 * The scene journal must already have begun, with no later truncation. */
static void fixdemo_trophy_status(const char *event) {
  fixdemo_trophy_note(event);
  fixdemo_trophy_scene_status(event);
}

static void fixdemo_trophy_journal_begin(void) {
  fixdemo_trophy_note_count = 0;
  fixdemo_trophy_journal_errors = 0;
  fixdemo_trophy_journal_ready = 0;
  fixdemo_trophy_journal_lock = 0;
  fixdemo_trophy_boot_ms = scene_runtime_ms();
  fixdemo_trophy_scene_status("boot: canary inactive; package checks pending");

  /* Keep one bounded prior boot, including an old startup-only v49 journal.
   * Failure to rotate is reported; creation of the fresh journal is still
   * attempted. Failed creation never enables appending to the stale file. */
  errno = 0;
  FILE *prior = fopen("trophy-runtime.log", "rb");
  if (prior) {
    errno = 0;
    const int sought = fseek(prior, 0, SEEK_END);
    const long bytes = sought == 0 ? ftell(prior) : -1;
    int error = errno;
    errno = 0;
    const int closed = fclose(prior);
    if (closed != 0) error = errno;
    if (bytes < 0 || closed != 0)
      fixdemo_trophy_journal_problem(bytes < 0 ? "prior-seek" : "prior-close", "trophy-runtime.log", error);
    else if (bytes > 0 && bytes <= 32768) {
      errno = 0;
      if (remove("trophy-runtime.previous.log") != 0 && errno != ENOENT)
        fixdemo_trophy_journal_problem("previous-remove", "trophy-runtime.previous.log", errno);
      else {
        errno = 0;
        if (rename("trophy-runtime.log", "trophy-runtime.previous.log") != 0)
          fixdemo_trophy_journal_problem("prior-rename", "trophy-runtime.log", errno);
      }
    } else if (bytes > 32768)
      fixdemo_trophy_scene_status("journal prior oversized; not preserved; creating fresh session");
  } else if (errno != ENOENT)
    fixdemo_trophy_journal_problem("prior-open", "trophy-runtime.log", errno);

  errno = 0;
  FILE *journal = fopen("trophy-runtime.log", "wb");
  if (!journal) {
    fixdemo_trophy_journal_problem("create; prior file may be stale", "trophy-runtime.log", errno);
    return;
  }
  char header[512];
  const int length = snprintf(header, sizeof(header), "%s\nrevision=v60 app=%s build=%s boot_ms=%llu\n",
                              pesnx_trophy_canary_capability, PES_NX_VERSION, PESNX_BUILD_ID,
                              (unsigned long long)fixdemo_trophy_boot_ms);
  errno = 0;
  const int written = length > 0 && (size_t)length < sizeof(header) &&
      fwrite(header, 1, (size_t)length, journal) == (size_t)length;
  int error = errno;
  errno = 0;
  const int closed = fclose(journal);
  if (!written || closed != 0) {
    if (written) error = errno;
    fixdemo_trophy_journal_problem(!written ? "header-write" : "header-close", "trophy-runtime.log", error);
    return;
  }
  __atomic_store_n(&fixdemo_trophy_journal_ready, 1, __ATOMIC_RELEASE);
}

static void fixdemo_trophy_io_reject(const char *stage, const char *path, int error) {
  char line[256];
  snprintf(line, sizeof(line), "disabled: %s path=%s errno=%d", stage, path, error);
  fixdemo_trophy_status(line);
}

static int fixdemo_trophy_file_hash(const char *path, size_t limit, char hash[65]) {
  hash[0] = '\0';
  errno = 0;
  FILE *file = fopen(path, "rb");
  if (!file) { fixdemo_trophy_io_reject("asset open failed", path, errno); return 0; }
  Sha256Context context;
  sha256ContextCreate(&context);
  unsigned char buffer[16384], digest[32];
  size_t bytes = 0;
  const char *failure = NULL;
  int error = 0;
  for (;;) {
    errno = 0;
    const size_t count = fread(buffer, 1, sizeof(buffer), file);
    if (ferror(file)) { failure = "asset read failed"; error = errno; break; }
    if (count > limit - bytes) { failure = "asset size limit exceeded"; break; }
    if (!count) break;
    sha256ContextUpdate(&context, buffer, count);
    bytes += count;
  }
  if (!failure && !bytes) failure = "asset empty";
  errno = 0;
  if (fclose(file) != 0 && !failure) { failure = "asset close failed"; error = errno; }
  if (failure) { fixdemo_trophy_io_reject(failure, path, error); return 0; }
  sha256ContextGetHash(&context, digest);
  static const char digits[] = "0123456789abcdef";
  for (size_t i = 0; i < sizeof(digest); ++i) {
    hash[i * 2u] = digits[digest[i] >> 4];
    hash[i * 2u + 1u] = digits[digest[i] & 15u];
  }
  hash[64] = '\0';
  return 1;
}

static int fixdemo_trophy_config_bootstrap(int full_loose_mode, const char *baseline_error) {
  fixdemo_trophy_canary_validated = 0;
  fixdemo_trophy_verified_elf_sha256[0] = '\0';
  fixdemo_trophy_journal_begin();
  if (full_loose_mode != 2) {
    char detail[384];
    snprintf(detail, sizeof(detail), "disabled: full-loose baseline mode=%d reason=%.240s",
             full_loose_mode, baseline_error && *baseline_error ? baseline_error : "full loose mode required");
    fixdemo_trophy_status(detail);
    return 0;
  }
  size_t production_length=0;
  char *production=nx_asset_read_archive(NX_ASSET_ARCHIVE,"Runtime/trophy.cfg",512u,&production_length);
  errno = 0;
  FILE *marker = production ? NULL : fopen("trophy-canary.txt", "rb");
  if (!marker && !production) {
    const int error = errno;
    fixdemo_trophy_io_reject(error == ENOENT ? "marker absent" : "marker open failed",
                            "trophy-canary.txt", error);
    return 0; /* Ordinary installation keeps all trophy hooks absent. */
  }
  char text[512];
  errno = 0;
  const size_t length = production ? production_length : fread(text, 1, sizeof(text), marker);
  if(production){memcpy(text,production,length);free(production);}
  const int read_ok = !marker || !ferror(marker);
  int error = errno;
  errno = 0;
  const int close_ok = !marker || fclose(marker) == 0;
  if (read_ok && !close_ok) error = errno;
  if (!read_ok || !close_ok) {
    fixdemo_trophy_io_reject(!read_ok ? "marker read failed" : "marker close failed",
                            "trophy-canary.txt", error);
    return 0;
  }
  TrophyCanaryConfig config;
  if (!trophy_canary_parse(text, length, &config)) {
    char detail[160];
    snprintf(detail, sizeof(detail), "disabled: marker format or pinned identity invalid path=trophy-canary.txt bytes=%zu", length);
    fixdemo_trophy_status(detail);
    return 0;
  }

  /* so_load rebases program headers inside module->so_base. Hash original
   * files once, never the changed in-memory ELF or asserted marker strings. */
  static const char *const paths[] = {"libUE4.so", "LooseCpk/dt220_mobile_all.cpk",
      "LooseCpk/manifest.txt", "PesMobile/Content/Paks/PesMobile-CinematicProps-Android_ETC1_P.pak"};
  static const size_t limits[] = {256u * 1024u * 1024u, 64u * 1024u * 1024u, 16384u, 8u * 1024u * 1024u};
  const char *expected[] = {PESNX_TROPHY_NATIVE_SHA256, config.cpk_sha256, config.manifest_sha256, config.pak_sha256};
  char measured[4][65];
  for (size_t i = 0; i < 4u; ++i) {
    if (!fixdemo_trophy_file_hash(paths[i], limits[i], measured[i])) return 0;
    if (strcmp(measured[i], expected[i])) {
      char detail[320];
      snprintf(detail, sizeof(detail), "disabled: asset hash mismatch path=%s expected=%s measured=%s",
               paths[i], expected[i], measured[i]);
      fixdemo_trophy_status(detail);
      return 0;
    }
  }
  if (!trophy_canary_files_match(&config, full_loose_mode, measured[0], measured[1], measured[2], measured[3])) {
    fixdemo_trophy_status("disabled: package identity invariant failed");
    return 0;
  }
  memcpy(fixdemo_trophy_verified_elf_sha256, measured[0], sizeof(measured[0]));
  fixdemo_trophy_canary_validated = 1;
  fixdemo_trophy_status("validated: combined FL26 walkout and trophy files; runtime ABI preflight pending");
  return 1;
}
