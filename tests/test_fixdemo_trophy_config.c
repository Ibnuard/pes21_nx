/* Execute the production bootstrap include with synthetic files and injected
 * filesystem faults. The SHA shim identifies test bytes only; these fixtures
 * are not game payloads and this is not a test of libnx's cryptography. */
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <switch/crypto/sha256.h>
#include "trophy_canary_config.h"

#define PES_NX_VERSION "test-app"
static const char manifest_hash[] =
    "123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef0";
static const char *const asset_paths[] = {
    "libUE4.so", "LooseCpk/dt220_mobile_all.cpk", "LooseCpk/manifest.txt",
    "PesMobile/Content/Paks/PesMobile-CinematicProps-Android_ETC1_P.pak"
};
static unsigned sha_creates, sha_updates, sha_finishes;
void sha256ContextCreate(Sha256Context *ctx) {
  memset(ctx, 0, sizeof(*ctx));
  ++sha_creates;
}
void sha256ContextUpdate(Sha256Context *ctx, const void *data, size_t length) {
  const unsigned char *bytes = data;
  for (size_t i = 0; i < length; ++i) {
    if (!ctx->bytes) ctx->tag = bytes[i];
    if (bytes[i] != ctx->tag) ctx->mixed = 1;
    ++ctx->bytes;
  }
  ++sha_updates;
}
void sha256ContextGetHash(Sha256Context *ctx, void *out) {
  static const char *const hashes[] = {
      PESNX_TROPHY_NATIVE_SHA256, PESNX_TROPHY_CPK_SHA256,
      manifest_hash, PESNX_TROPHY_PAK_SHA256
  };
  unsigned char *digest = out;
  memset(digest, 0, 32);
  if (!ctx->mixed && ctx->tag >= 1 && ctx->tag <= 4) {
    const char *hash = hashes[ctx->tag - 1];
    for (unsigned i = 0; i < 32; ++i) {
      unsigned value;
      assert(sscanf(hash + i * 2, "%2x", &value) == 1);
      digest[i] = (unsigned char)value;
    }
  }
  ++sha_finishes;
}

typedef struct { FILE *file; char path[128], mode[8]; int read_error; } OpenFile;
typedef struct { const char *op, *path, *mode; unsigned remaining; } Fault;
static OpenFile opened[16];
static Fault faults[3];
static OpenFile *lookup(FILE *file) {
  for (unsigned i = 0; i < 16; ++i) if (opened[i].file == file) return &opened[i];
  assert(!"untracked file");
  return NULL;
}
static int fault(const char *op, const char *path, const char *mode) {
  for (unsigned i = 0; i < 3; ++i) {
    Fault *f = &faults[i];
    if (f->remaining && !strcmp(f->op, op) && !strcmp(f->path, path) &&
        (!f->mode || !strcmp(f->mode, mode))) {
      --f->remaining;
      errno = !strcmp(op, "open") ? EACCES : EIO;
      return 1;
    }
  }
  return 0;
}
static void inject(unsigned slot, const char *op, const char *path, const char *mode) {
  faults[slot] = (Fault){op, path, mode, 1};
}
static FILE *test_fopen(const char *path, const char *mode) {
  if (fault("open", path, mode)) return NULL;
  FILE *file = fopen(path, mode);
  if (!file) return NULL;
  for (unsigned i = 0; i < 16; ++i) if (!opened[i].file) {
    opened[i].file = file;
    snprintf(opened[i].path, sizeof(opened[i].path), "%s", path);
    snprintf(opened[i].mode, sizeof(opened[i].mode), "%s", mode);
    opened[i].read_error = 0;
    return file;
  }
  assert(!"too many streams");
  return file;
}
static size_t test_fread(void *out, size_t size, size_t count, FILE *file) {
  OpenFile *entry = lookup(file);
  if (fault("read", entry->path, entry->mode)) { entry->read_error = 1; return 0; }
  return fread(out, size, count, file);
}
static int test_ferror(FILE *file) { return lookup(file)->read_error || ferror(file); }
static int test_fclose(FILE *file) {
  OpenFile *entry = lookup(file);
  const int fail = fault("close", entry->path, entry->mode);
  entry->file = NULL;
  const int result = fclose(file);
  if (fail) { errno = EIO; return EOF; }
  return result;
}
static int test_fseek(FILE *file, long offset, int whence) {
  OpenFile *entry = lookup(file);
  if (fault("seek", entry->path, entry->mode)) return -1;
  return fseek(file, offset, whence);
}
static long test_ftell(FILE *file) {
  OpenFile *entry = lookup(file);
  if (fault("tell", entry->path, entry->mode)) return -1;
  return ftell(file);
}
static size_t test_fwrite(const void *data, size_t size, size_t count, FILE *file) {
  OpenFile *entry = lookup(file);
  if (fault("write", entry->path, entry->mode)) {
    const size_t result = count ? fwrite(data, size, count - 1, file) : 0;
    errno = EIO;
    return result;
  }
  return fwrite(data, size, count, file);
}
static int test_remove(const char *path) {
  if (fault("remove", path, "")) return -1;
  return remove(path);
}
static int test_rename(const char *old_path, const char *new_path) {
  if (fault("rename", old_path, "")) return -1;
  return rename(old_path, new_path);
}

static char scene[65536];
static uint64_t clock_ms = 9876000;
static uint64_t armGetSystemTick(void) { return clock_ms * 1000000u; }
static uint64_t armTicksToNs(uint64_t ticks) { return ticks; }
/* Exercise the actual scene journal as well as the actual bootstrap. Its
 * filesystem operations remain real, independently of trophy fault injection. */
#include "scene_runtime_log.h"
#define fopen test_fopen
#define fread test_fread
#undef ferror
#define ferror test_ferror
#define fclose test_fclose
#define fseek test_fseek
#define ftell test_ftell
#define fwrite test_fwrite
#define remove test_remove
#define rename test_rename
#include "../source/fixdemo_trophy_config.inc"
#undef fopen
#undef fread
#undef ferror
#undef fclose
#undef fseek
#undef ftell
#undef fwrite
#undef remove
#undef rename

static void put(const char *path, const void *bytes, size_t length) {
  FILE *file = fopen(path, "wb");
  assert(file);
  assert(fwrite(bytes, 1, length, file) == length);
  assert(!fclose(file));
}
static void fill(const char *path, unsigned char byte, size_t count) {
  unsigned char bytes[1024];
  memset(bytes, byte, sizeof(bytes));
  FILE *file = fopen(path, "wb");
  assert(file);
  while (count) {
    const size_t chunk = count < sizeof(bytes) ? count : sizeof(bytes);
    assert(fwrite(bytes, 1, chunk, file) == chunk);
    count -= chunk;
  }
  assert(!fclose(file));
}
static size_t read_text(const char *path, char *buffer, size_t capacity) {
  FILE *file = fopen(path, "rb");
  assert(file);
  const size_t count = fread(buffer, 1, capacity - 1, file);
  assert(!ferror(file) && feof(file));
  buffer[count] = '\0';
  assert(!fclose(file));
  return count;
}
static int present(const char *path) {
  FILE *file = fopen(path, "rb");
  if (!file) return 0;
  assert(!fclose(file));
  return 1;
}
static void marker(void) {
  char text[512];
  const int count = snprintf(text, sizeof(text), PESNX_TROPHY_MARKER_HEADER
      "cpk_sha256=%s\nmanifest_sha256=%s\npak_sha256=%s\n",
      PESNX_TROPHY_CPK_SHA256, manifest_hash, PESNX_TROPHY_PAK_SHA256);
  assert(count > 0 && (size_t)count < sizeof(text));
  put("trophy-canary.txt", text, (size_t)count);
}
static void package(void) {
  marker();
  for (unsigned i = 0; i < 4; ++i)
    fill(asset_paths[i], (unsigned char)(i + 1), i ? 64 : 20000);
}
static void check_scene(const char *needle) {
  read_text("scene-runtime.log", scene, sizeof(scene));
  assert(strstr(scene, "FootballNX scene v52 session\n"));
  assert(strstr(scene, "ceremony status: revision=v52 app=test-app build=" PESNX_BUILD_ID));
  assert(strstr(scene, "boot_ms=9876000"));
  if (!strstr(scene, needle)) {
    fprintf(stderr, "Expected [%s], got:\n%s\n", needle, scene);
    assert(!"missing scene event");
  }
}
static void rejected(const char *needle) {
  assert(!fixdemo_trophy_canary_validated);
  assert(!*fixdemo_trophy_verified_elf_sha256);
  check_scene(needle);
}
static void not_leaking(void) {
  for (unsigned i = 0; i < 16; ++i) assert(!opened[i].file);
}
static void accepted(void) {
  assert(fixdemo_trophy_canary_validated);
  assert(!strcmp(fixdemo_trophy_verified_elf_sha256, PESNX_TROPHY_NATIVE_SHA256));
  assert(sha_creates == 4 && sha_finishes == 4 && sha_updates == 5);
  check_scene("runtime ABI preflight pending");
  assert(!strstr(scene, "enabled:"));
}

int main(int argc, char **argv) {
  assert(argc == 2);
  const char *test = argv[1];
  char current[65536], previous[65536];
  static const char stale[] = "PESNX trophy runtime canary v1\nv49 old validated enabled journal\n";
  scene_runtime_begin();
  if (!strcmp(test, "missing-marker")) {
    put("trophy-runtime.log", stale, sizeof(stale) - 1);
    put("trophy-runtime.previous.log", "older", 5);
    fixdemo_trophy_canary_validated = 1;
    memset(fixdemo_trophy_verified_elf_sha256, 'x', 64);
    assert(!fixdemo_trophy_config_bootstrap(2, NULL));
    rejected("disabled: marker absent path=trophy-canary.txt errno=");
    assert(!sha_creates);
    read_text("trophy-runtime.log", current, sizeof(current));
    read_text("trophy-runtime.previous.log", previous, sizeof(previous));
    assert(!strcmp(previous, stale));
    assert(strstr(current, "revision=v52 app=test-app build=" PESNX_BUILD_ID));
    assert(strstr(current, "marker absent") && !strstr(current, "v49"));
  } else if (!strcmp(test, "valid-and-abi")) {
    package();
    assert(fixdemo_trophy_config_bootstrap(2, NULL));
    accepted();
    fixdemo_trophy_status("disabled: runtime ABI preflight stage=props; no trophy patches installed");
    check_scene("stage=props");
    fixdemo_trophy_status("disabled: runtime ABI preflight stage=ending; no trophy patches installed");
    check_scene("stage=ending");
    fixdemo_trophy_status("enabled: final-only trophy canary");
    check_scene("enabled: final-only trophy canary");
    read_text("trophy-runtime.log", current, sizeof(current));
    assert(strstr(current, "stage=props") && strstr(current, "stage=ending"));
    assert(strstr(current, "enabled: final-only trophy canary"));
    scene_runtime_note("stadium", "native inventory retained");
    scene_runtime_note("native prematch reveal", "lifecycle ready");
    check_scene("runtime ABI preflight pending");
    check_scene("enabled: final-only trophy canary");
    check_scene("stadium: native inventory retained");
    check_scene("native prematch reveal: lifecycle ready");
  } else if (!strcmp(test, "baseline")) {
    package();
    assert(!fixdemo_trophy_config_bootstrap(-1, "manifest mismatch\npath=LooseCpk/manifest.txt"));
    rejected("full-loose baseline mode=-1 reason=manifest mismatch path=LooseCpk/manifest.txt");
    assert(!sha_creates);
    assert(!fixdemo_trophy_config_bootstrap(0, NULL));
    rejected("full-loose baseline mode=0 reason=full loose mode required");
  } else if (!strcmp(test, "marker-invalid")) {
    put("trophy-canary.txt", "not a marker", 12);
    assert(!fixdemo_trophy_config_bootstrap(2, NULL));
    rejected("marker format or pinned identity invalid");
    assert(!sha_creates);
  } else if (!strncmp(test, "marker-", 7)) {
    package();
    const char *op = test + 7;
    inject(0, op, "trophy-canary.txt", "rb");
    assert(!fixdemo_trophy_config_bootstrap(2, NULL));
    char reason[64];
    snprintf(reason, sizeof(reason), "marker %s failed", op);
    rejected(reason);
    assert(!sha_creates);
  } else if (!strncmp(test, "hash-mismatch-", 14)) {
    const unsigned index = (unsigned)strtoul(test + 14, NULL, 10);
    assert(index < 4);
    package();
    fill(asset_paths[index], 9, 64);
    assert(!fixdemo_trophy_config_bootstrap(2, NULL));
    rejected("asset hash mismatch");
    check_scene(asset_paths[index]);
    check_scene("expected=");
    check_scene("measured=0000000000000000000000000000000000000000000000000000000000000000");
    assert(sha_finishes == index + 1);
  } else if (!strncmp(test, "asset-", 6)) {
    package();
    const char *op = test + 6;
    if (!strcmp(op, "empty")) fill(asset_paths[2], 3, 0);
    else if (!strcmp(op, "size")) fill(asset_paths[2], 3, 16385);
    else inject(0, op, asset_paths[2], "rb");
    assert(!fixdemo_trophy_config_bootstrap(2, NULL));
    char reason[64];
    snprintf(reason, sizeof(reason), "asset %s%s", op,
             !strcmp(op, "empty") ? "" : !strcmp(op, "size") ? " limit exceeded" : " failed");
    rejected(reason);
    check_scene(asset_paths[2]);
    assert(sha_finishes == 2);
  } else if (!strcmp(test, "journal-create")) {
    package();
    put("trophy-runtime.log", stale, sizeof(stale) - 1);
    inject(0, "rename", "trophy-runtime.log", "");
    inject(1, "open", "trophy-runtime.log", "wb");
    assert(fixdemo_trophy_config_bootstrap(2, NULL));
    accepted();
    check_scene("journal create; prior file may be stale failed");
    assert(!fixdemo_trophy_journal_ready);
    fixdemo_trophy_status("enabled: final-only trophy canary");
    read_text("trophy-runtime.log", current, sizeof(current));
    assert(!strcmp(current, stale)); /* Never append fresh success to old boot. */
    check_scene("enabled: final-only trophy canary");
  } else if (!strncmp(test, "prior-", 6)) {
    package();
    put("trophy-runtime.log", stale, sizeof(stale) - 1);
    put("trophy-runtime.previous.log", "older", 5);
    const char *op = test + 6;
    if (!strcmp(op, "remove")) inject(0, op, "trophy-runtime.previous.log", "");
    else inject(0, op, "trophy-runtime.log", !strcmp(op, "rename") ? "" : "rb");
    assert(fixdemo_trophy_config_bootstrap(2, NULL));
    accepted();
    check_scene("journal ");
    check_scene("failed path=trophy-runtime.");
    assert(fixdemo_trophy_journal_ready);
    read_text("trophy-runtime.log", current, sizeof(current));
    assert(strstr(current, "revision=v52") && !strstr(current, "v49"));
  } else if (!strncmp(test, "header-", 7)) {
    package();
    const char *op = test + 7;
    inject(0, op, "trophy-runtime.log", "wb");
    assert(fixdemo_trophy_config_bootstrap(2, NULL));
    accepted();
    char reason[64];
    snprintf(reason, sizeof(reason), "journal header-%s failed", op);
    check_scene(reason);
    assert(!fixdemo_trophy_journal_ready);
    read_text("trophy-runtime.log", current, sizeof(current));
    assert(!strstr(current, "validated:")); /* No append after uncertain write. */
  } else if (!strncmp(test, "append-", 7)) {
    package();
    assert(fixdemo_trophy_config_bootstrap(2, NULL));
    accepted();
    const char *op = test + 7;
    inject(0, op, "trophy-runtime.log", "r+b");
    fixdemo_trophy_note("bounded lifecycle event");
    char reason[64];
    snprintf(reason, sizeof(reason), "journal append-%s failed", !strcmp(op, "tell") ? "seek" : op);
    check_scene(reason);
    assert(!fixdemo_trophy_journal_ready);
    const size_t before = read_text("trophy-runtime.log", current, sizeof(current));
    fixdemo_trophy_note("later event must not reopen journal");
    const size_t after = read_text("trophy-runtime.log", previous, sizeof(previous));
    assert(before == after && !strcmp(current, previous));
  } else if (!strcmp(test, "two-boots")) {
    package();
    put("trophy-runtime.log", stale, sizeof(stale) - 1);
    assert(fixdemo_trophy_config_bootstrap(2, NULL));
    read_text("trophy-runtime.log", current, sizeof(current));
    clock_ms += 1000;
    assert(!remove("trophy-canary.txt"));
    scene_runtime_begin();
    assert(!fixdemo_trophy_config_bootstrap(2, NULL));
    read_text("trophy-runtime.previous.log", previous, sizeof(previous));
    assert(!strcmp(current, previous));
    read_text("trophy-runtime.log", current, sizeof(current));
    assert(strstr(current, "boot_ms=9877000"));
    assert(strstr(current, "marker absent") && !strstr(current, "validated:"));
    read_text("scene-runtime.previous.log", previous, sizeof(previous));
    assert(strstr(previous, "boot_ms=9876000") && strstr(previous, "validated:"));
    read_text("scene-runtime.log", scene, sizeof(scene));
    assert(strstr(scene, "boot_ms=9877000") && strstr(scene, "marker absent"));
    assert(!strstr(scene, "boot_ms=9876000") && !strstr(scene, "validated:"));
  } else if (!strcmp(test, "journal-oversized")) {
    package();
    fill("trophy-runtime.log", 'x', 40000);
    assert(fixdemo_trophy_config_bootstrap(2, NULL));
    accepted();
    check_scene("journal prior oversized; not preserved");
    assert(!present("trophy-runtime.previous.log"));
    assert(read_text("trophy-runtime.log", current, sizeof(current)) < 32768);
  } else if (!strcmp(test, "journal-bounds")) {
    package();
    assert(fixdemo_trophy_config_bootstrap(2, NULL));
    fill("trophy-runtime.log", 'x', 32500);
    char event[2048];
    memset(event, 'y', sizeof(event) - 1);
    event[sizeof(event) - 1] = '\0';
    fixdemo_trophy_note(event);
    check_scene("journal size-limit failed");
    assert(read_text("trophy-runtime.log", current, sizeof(current)) == 32500);
    assert(!fixdemo_trophy_journal_ready);
  } else if (!strcmp(test, "event-bounds")) {
    package();
    assert(fixdemo_trophy_config_bootstrap(2, NULL));
    for (unsigned i = 0; i < 1000; ++i) fixdemo_trophy_note("one event");
    const size_t length = read_text("trophy-runtime.log", current, sizeof(current));
    unsigned lines = 0;
    for (size_t i = 0; i < length; ++i) lines += current[i] == '\n';
    assert(lines == 194); /* Two header lines, at most 192 lifecycle notes. */
    assert(length <= 32768);
  } else if (!strcmp(test, "no-wait-writer")) {
    package();
    assert(fixdemo_trophy_config_bootstrap(2, NULL));
    const size_t before = read_text("trophy-runtime.log", current, sizeof(current));
    fixdemo_trophy_journal_lock = 1;
    fixdemo_trophy_note("contended event is dropped");
    assert(read_text("trophy-runtime.log", previous, sizeof(previous)) == before);
    fixdemo_trophy_journal_lock = 0;
    fixdemo_trophy_note("next event");
    assert(read_text("trophy-runtime.log", previous, sizeof(previous)) > before);
  } else if (!strcmp(test, "hash-limit-clears")) {
    package();
    char hash[65];
    memset(hash, 'x', sizeof(hash));
    assert(!fixdemo_trophy_file_hash(asset_paths[0], 19999, hash));
    assert(!*hash && !sha_finishes);
    assert(fixdemo_trophy_file_hash(asset_paths[0], 20000, hash));
    assert(!strcmp(hash, PESNX_TROPHY_NATIVE_SHA256));
  } else assert(!"unknown scenario");
  not_leaking();
  printf("trophy bootstrap actual include: %s pass\n", test);
  return 0;
}
