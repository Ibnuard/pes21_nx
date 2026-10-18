#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "../source/fixdemo_prop_bridge.inc"

#define COUNT(a) (sizeof(a) / sizeof((a)[0]))
#define WINDOW_COUNT COUNT(fixdemo_prop_abi_windows)

static const char approved_package[] =
    "123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef01234";
static const char marker_prefix[] = "PESNX_FIXDEMO_PROPS_V1\npak_sha256=";
enum { MARKER_SIZE = sizeof(marker_prefix) - 1 + 64 + 1 };

static void make_marker(char marker[MARKER_SIZE]) {
  memcpy(marker, marker_prefix, sizeof(marker_prefix) - 1);
  memcpy(marker + sizeof(marker_prefix) - 1, approved_package, 64);
  marker[MARKER_SIZE - 1] = '\n';
}

static void test_paths(void) {
  const struct {
    enum FixDemoPropKind kind;
    const char *descriptor, *runtime, *mesh;
  } expected[] = {
    {FIXDEMO_PROP_CUP,
     "common/demo/prop/cup_int_hi/cup_int_hi.fpk",
     "common/demo/prop/cup_int_hi/cup_int_hi.xml",
     "FootballNX/FixDemo/cup_int_hi/cup_int_hi.cup_int_hi"},
    {FIXDEMO_PROP_PODIUM,
     "common/demo/fixdemoobj/winners_platform_common/winners_platform_common.fpk",
     "common/demo/fixdemoobj/winners_platform_common/winners_platform_common.xml",
     "FootballNX/FixDemo/platform_cmn/platform_cmn.platform_cmn"},
  };
  for (size_t i = 0; i < COUNT(expected); ++i) {
    for (int descriptor = 0; descriptor <= 1; ++descriptor) {
      const char *path = descriptor ? expected[i].descriptor : expected[i].runtime;
      const size_t length = strlen(path);
      const FixDemoPropMapping *mapping = fixdemo_prop_lookup(path, length, descriptor);
      assert(mapping && mapping->kind == expected[i].kind);
      assert(!strcmp(mapping->descriptor_path, expected[i].descriptor));
      assert(!strcmp(mapping->runtime_path, expected[i].runtime));
      assert(!strcmp(mapping->ue_name, expected[i].mesh));
      assert(!fixdemo_prop_lookup(path, length, !descriptor));
      assert(!fixdemo_prop_lookup(path, length - 1, descriptor));
      assert(!fixdemo_prop_lookup(path, length + 1, descriptor));

      /* An exact slice need not be NUL terminated; every embedded NUL fails. */
      char slice[128];
      memset(slice, '!', sizeof(slice));
      memcpy(slice, path, length);
      assert(fixdemo_prop_lookup(slice, length, descriptor) == mapping);
      for (size_t byte = 0; byte < length; ++byte) {
        const char before = slice[byte];
        slice[byte] = '\0';
        assert(!fixdemo_prop_lookup(slice, length, descriptor));
        slice[byte] = before;
      }
      slice[0] = 'C';
      assert(!fixdemo_prop_lookup(slice, length, descriptor));
      memcpy(slice, path, length);
      slice[6] = '\\';
      assert(!fixdemo_prop_lookup(slice, length, descriptor));
      assert(!fixdemo_prop_lookup(path + 7, length - 7, descriptor));
      assert(!fixdemo_prop_lookup(strrchr(path, '/') + 1,
          strlen(strrchr(path, '/') + 1), descriptor));
      char prefixed[160];
      snprintf(prefixed, sizeof(prefixed), "./%s", path);
      assert(!fixdemo_prop_lookup(prefixed, strlen(prefixed), descriptor));
      snprintf(prefixed, sizeof(prefixed), "../%s", path);
      assert(!fixdemo_prop_lookup(prefixed, strlen(prefixed), descriptor));
      snprintf(prefixed, sizeof(prefixed), "/%s", path);
      assert(!fixdemo_prop_lookup(prefixed, strlen(prefixed), descriptor));
      snprintf(prefixed, sizeof(prefixed), "%s#Win", path);
      assert(!fixdemo_prop_lookup(prefixed, strlen(prefixed), descriptor));
      snprintf(prefixed, sizeof(prefixed), "%s.extra", path);
      assert(!fixdemo_prop_lookup(prefixed, strlen(prefixed), descriptor));
    }
  }
  const char *rejected[] = {
    "common/demo/prop/cup_other/cup_other.fpk",
    "common/demo/prop/cup_int_hi/#Win/cup_int_hi.fpk",
    "common/demo/prop/cup_int_hi/cup_int_hi.fpkd",
    "common/demo/fixdemoobj/winners_platform_common/winners_platform_common.fpkd",
    "common/demo/prop/cup_int_hi/../cup_int_hi/cup_int_hi.fpk",
  };
  for (size_t i = 0; i < COUNT(rejected); ++i)
    for (int descriptor = 0; descriptor <= 1; ++descriptor)
      assert(!fixdemo_prop_lookup(rejected[i], strlen(rejected[i]), descriptor));
  char long_path[128] = {0};
  assert(!fixdemo_prop_lookup(long_path, sizeof(long_path), 1));
  assert(!fixdemo_prop_lookup(NULL, 1, 1));
  assert(!fixdemo_prop_lookup("", 0, 0));
}

static void test_packages(void) {
  char marker[MARKER_SIZE + 1], sha[65], alternate[65];
  make_marker(marker);
  marker[MARKER_SIZE] = '\0';
  memcpy(sha, approved_package, sizeof(sha));
  memcpy(alternate, approved_package, sizeof(alternate));
  alternate[0] = 'a';
  assert(fixdemo_prop_valid_sha256(sha, 64));
  assert(!fixdemo_prop_valid_sha256(NULL, 64));
  assert(!fixdemo_prop_valid_sha256(sha, 63));
  assert(!fixdemo_prop_valid_sha256(sha, 65));
  for (size_t byte = 0; byte < 64; ++byte) {
    const char before = sha[byte];
    const char rejected[] = {'\0', 'A', 'g', '/', '\n', (char)0xff};
    for (size_t j = 0; j < COUNT(rejected); ++j) {
      sha[byte] = rejected[j];
      assert(!fixdemo_prop_valid_sha256(sha, 64));
    }
    sha[byte] = before;
  }
  memset(sha, '0', 64);
  assert(!fixdemo_prop_valid_sha256(sha, 64));
  sha[63] = '1';
  assert(fixdemo_prop_valid_sha256(sha, 64));

  assert(fixdemo_prop_package_matches(marker, MARKER_SIZE,
      approved_package, 64, approved_package, 64));
  for (size_t byte = 0; byte < MARKER_SIZE; ++byte) {
    marker[byte] ^= 1;
    assert(!fixdemo_prop_package_matches(marker, MARKER_SIZE,
        approved_package, 64, approved_package, 64));
    marker[byte] ^= 1;
  }
  assert(!fixdemo_prop_package_matches(NULL, MARKER_SIZE,
      approved_package, 64, approved_package, 64));
  assert(!fixdemo_prop_package_matches(marker, MARKER_SIZE - 1,
      approved_package, 64, approved_package, 64));
  assert(!fixdemo_prop_package_matches(marker, MARKER_SIZE + 1,
      approved_package, 64, approved_package, 64));
  assert(!fixdemo_prop_package_matches(marker, MARKER_SIZE,
      NULL, 64, approved_package, 64));
  assert(!fixdemo_prop_package_matches(marker, MARKER_SIZE,
      approved_package, 64, NULL, 64));
  assert(!fixdemo_prop_package_matches(marker, MARKER_SIZE,
      approved_package, 63, approved_package, 64));
  assert(!fixdemo_prop_package_matches(marker, MARKER_SIZE,
      approved_package, 64, approved_package, 65));
  assert(!fixdemo_prop_package_matches(marker, MARKER_SIZE,
      alternate, 64, approved_package, 64));
  assert(!fixdemo_prop_package_matches(marker, MARKER_SIZE,
      approved_package, 64, alternate, 64));
  /* A self-consistent marker and measurement still need separate approval. */
  memcpy(marker + sizeof(marker_prefix) - 1, alternate, 64);
  assert(!fixdemo_prop_package_matches(marker, MARKER_SIZE,
      alternate, 64, approved_package, 64));
  assert(fixdemo_prop_package_matches(marker, MARKER_SIZE,
      alternate, 64, alternate, 64));
  memset(sha, '0', 64);
  memcpy(marker + sizeof(marker_prefix) - 1, sha, 64);
  assert(!fixdemo_prop_package_matches(marker, MARKER_SIZE, sha, 64, sha, 64));
}

typedef struct {
  size_t calls;
  int fail_window, wrong_rva, corrupt_window, corrupt_byte;
} SymbolSnapshot;

static SymbolSnapshot symbols_clean(void) {
  const SymbolSnapshot snapshot = {0, -1, -1, -1, -1};
  return snapshot;
}

static int read_symbol(void *context, const char *symbol, uint32_t offset,
    unsigned char bytes[32], uint64_t *rva) {
  SymbolSnapshot *snapshot = context;
  const size_t index = snapshot->calls++;
  assert(index < WINDOW_COUNT);
  const FixDemoPropAbiWindow *window = &fixdemo_prop_abi_windows[index];
  assert(!strcmp(symbol, window->symbol) && offset == window->offset);
  if ((int)index == snapshot->fail_window) return 0;
  *rva = window->rva + ((int)index == snapshot->wrong_rva ? 4 : 0);
  for (size_t i = 0; i < 32; ++i)
    bytes[i] = (unsigned char)(window->words[i / 4] >> (8 * (i % 4)));
  if ((int)index == snapshot->corrupt_window) bytes[snapshot->corrupt_byte] ^= 1;
  return 1;
}

static FixDemoPropAbiEvidence abi_clean(SymbolSnapshot *snapshot) {
  const FixDemoPropAbiEvidence evidence = {
    fixdemo_prop_elf_sha256, 64, 64, 183, 1, read_symbol, snapshot
  };
  return evidence;
}

static void test_abi(void) {
  SymbolSnapshot snapshot = symbols_clean();
  FixDemoPropAbiEvidence evidence = abi_clean(&snapshot);
  assert(fixdemo_prop_validate_abi(&evidence));
  assert(snapshot.calls == WINDOW_COUNT);
  /* Failure in any window must stop before later reads, with no partial success. */
  for (size_t index = 0; index < WINDOW_COUNT; ++index) {
    snapshot = symbols_clean();
    snapshot.fail_window = (int)index;
    assert(!fixdemo_prop_validate_abi(&evidence) && snapshot.calls == index + 1);
    snapshot = symbols_clean();
    snapshot.wrong_rva = (int)index;
    assert(!fixdemo_prop_validate_abi(&evidence) && snapshot.calls == index + 1);
    for (int byte = 0; byte < 32; ++byte) {
      snapshot = symbols_clean();
      snapshot.corrupt_window = (int)index;
      snapshot.corrupt_byte = byte;
      assert(!fixdemo_prop_validate_abi(&evidence) && snapshot.calls == index + 1);
    }
  }
  char sha[65];
  memcpy(sha, fixdemo_prop_elf_sha256, sizeof(sha));
  evidence.elf_sha = sha;
  snapshot = symbols_clean();
  for (size_t byte = 0; byte < 64; ++byte) {
    sha[byte] ^= 1;
    assert(!fixdemo_prop_validate_abi(&evidence) && !snapshot.calls);
    sha[byte] ^= 1;
  }
  for (int failure = 0; failure < 9; ++failure) {
    evidence = abi_clean(&snapshot);
    switch (failure) {
      case 0: evidence.elf_sha = NULL; break;
      case 1: evidence.elf_sha_length = 63; break;
      case 2: evidence.elf_sha_length = 65; break;
      case 3: evidence.elf_bits = 32; break;
      case 4: evidence.machine = 62; break;
      case 5: evidence.little_endian = 0; break;
      case 6: evidence.little_endian = 2; break;
      case 7: evidence.read_symbol = NULL; break;
      case 8: evidence.elf_bits = 0; break;
    }
    assert(!fixdemo_prop_validate_abi(&evidence) && !snapshot.calls);
  }
  assert(!fixdemo_prop_validate_abi(NULL));
}

static void test_preflight(void) {
  char marker[MARKER_SIZE];
  make_marker(marker);
  SymbolSnapshot snapshot = symbols_clean();
  FixDemoPropAbiEvidence evidence = abi_clean(&snapshot);
  const int disabled[] = {-1, 0, 2, 99};
  for (size_t i = 0; i < COUNT(disabled); ++i) {
    assert(fixdemo_prop_preflight(disabled[i], NULL, 0, NULL, 0, NULL, 0,
        &evidence) == FIXDEMO_PROP_NOT_REQUESTED);
    assert(!snapshot.calls);
  }
  assert(fixdemo_prop_preflight(1, marker, MARKER_SIZE, approved_package, 64,
      NULL, 0, &evidence) == FIXDEMO_PROP_BAD_PACKAGE && !snapshot.calls);
  assert(fixdemo_prop_preflight(1, marker, MARKER_SIZE, approved_package, 64,
      approved_package, 64, NULL) == FIXDEMO_PROP_BAD_ABI);
  snapshot.fail_window = (int)WINDOW_COUNT - 1;
  assert(fixdemo_prop_preflight(1, marker, MARKER_SIZE, approved_package, 64,
      approved_package, 64, &evidence) == FIXDEMO_PROP_BAD_ABI);
  assert(snapshot.calls == WINDOW_COUNT);
  snapshot = symbols_clean();
  assert(fixdemo_prop_preflight(1, marker, MARKER_SIZE, approved_package, 64,
      approved_package, 64, &evidence) == FIXDEMO_PROP_VALIDATED_BUT_INACTIVE);
  assert(snapshot.calls == WINDOW_COUNT);
  for (int result = -1; result <= 99; ++result)
    assert(!fixdemo_prop_can_activate((enum FixDemoPropPreflight)result));
  assert(FIXDEMO_PROP_ACTIVATION_VALIDATED == 0);
}

typedef struct {
  size_t calls;
  uintptr_t address;
  uint64_t result;
  int readable;
} PointerSnapshot;

static void encode_pointer(unsigned char *bytes, uint64_t value) {
  for (unsigned i = 0; i < 8; ++i) bytes[i] = (unsigned char)(value >> (8 * i));
}

static int read_pointer(void *context, uintptr_t address, void *output, size_t size) {
  PointerSnapshot *snapshot = context;
  ++snapshot->calls;
  snapshot->address = address;
  assert(size == 8 && address <= UINTPTR_MAX - (size - 1));
  if (!snapshot->readable) return 0;
  encode_pointer(output, snapshot->result);
  return 1;
}

static void test_pointer_bounds(void) {
  PointerSnapshot snapshot = {0, 0, UINT64_C(0x1234567812345680), 1};
  uintptr_t value = 0;
  assert(fixdemo_prop_read_pointer(read_pointer, &snapshot, 0x1000, 8, &value));
  assert(value == snapshot.result && snapshot.address == 0x1008 && snapshot.calls == 1);
  /* The last valid 8-byte span ends exactly at UINTPTR_MAX. */
  assert(fixdemo_prop_read_pointer(read_pointer, &snapshot, UINTPTR_MAX - 7, 0, &value));
  assert(snapshot.address == UINTPTR_MAX - 7);
  assert(fixdemo_prop_read_pointer(read_pointer, &snapshot, 8, UINTPTR_MAX - 15, &value));
  assert(snapshot.address == UINTPTR_MAX - 7);
  const struct { uintptr_t base; size_t offset; } invalid[] = {
    {0, 0}, {1, 0}, {0x1001, 0},
    {UINTPTR_MAX - 7, 1}, {UINTPTR_MAX - 7, 8},
    {8, UINTPTR_MAX - 14}, {8, UINTPTR_MAX - 6}, {8, UINTPTR_MAX},
  };
  for (size_t i = 0; i < COUNT(invalid); ++i) {
    snapshot.calls = 0;
    value = 0xfeed;
    assert(!fixdemo_prop_read_pointer(read_pointer, &snapshot,
        invalid[i].base, invalid[i].offset, &value));
    assert(!snapshot.calls && value == 0xfeed);
  }
  assert(!fixdemo_prop_read_pointer(NULL, &snapshot, 0x1000, 0, &value));
  assert(!fixdemo_prop_read_pointer(read_pointer, &snapshot, 0x1000, 0, NULL));
  assert(!snapshot.calls);
  const uint64_t invalid_values[] = {0, 1, 0x1001, UINT64_MAX};
  for (size_t i = 0; i < COUNT(invalid_values); ++i) {
    snapshot.calls = 0;
    snapshot.result = invalid_values[i];
    assert(!fixdemo_prop_read_pointer(read_pointer, &snapshot, 0x1000, 0, &value));
    assert(snapshot.calls == 1 && value == 0xfeed);
  }
  snapshot.calls = 0;
  snapshot.readable = 0;
  assert(!fixdemo_prop_read_pointer(read_pointer, &snapshot, 0x1000, 0, &value));
  assert(snapshot.calls == 1 && value == 0xfeed);
}

enum { OWNER = 0x10000, DEMO = 0x20000, MODEL = 0x30000, UE = 0x40000,
       IMPL = 0x50000, ACTOR = 0x60000, COMPONENT = 0x70000, MESH = 0x80000 };
static const struct { uintptr_t base; size_t offset; uint64_t value; } chain[] = {
  {OWNER, 184, DEMO}, {DEMO, 8, MODEL}, {MODEL, 24, UE}, {UE, 8, IMPL},
  {IMPL, 520, ACTOR}, {ACTOR, 816, COMPONENT}, {ACTOR, 824, MESH},
  {COMPONENT, 1456, MESH},
};

typedef struct {
  unsigned char blocks[7][2048];
  size_t calls;
  int fail_call, replace_owner;
  const FixDemoPropMapping *mapping;
} MemorySnapshot;

static void memory_clean(MemorySnapshot *snapshot, const FixDemoPropMapping *mapping) {
  memset(snapshot, 0, sizeof(*snapshot));
  snapshot->fail_call = -1;
  snapshot->mapping = mapping;
  for (size_t i = 0; i < COUNT(chain); ++i)
    encode_pointer(snapshot->blocks[chain[i].base / 0x10000 - 1] + chain[i].offset,
        chain[i].value);
  memcpy(snapshot->blocks[IMPL / 0x10000 - 1], mapping->ue_name, strlen(mapping->ue_name) + 1);
}

/* Only explicit bounded mock regions are readable; no native pointer is dereferenced. */
static int read_memory(void *context, uintptr_t address, void *output, size_t size) {
  MemorySnapshot *snapshot = context;
  const size_t call = snapshot->calls++;
  assert(call < 10);
  if (call < COUNT(chain)) {
    assert(size == 8);
  } else if (call == 8) {
    assert(size == strlen(snapshot->mapping->ue_name) + 1 && address == IMPL);
  } else {
    assert(size == 8 && address == OWNER + 184);
  }
  if ((int)call == snapshot->fail_call) return 0;
  for (size_t block = 0; block < COUNT(snapshot->blocks); ++block) {
    const uintptr_t base = (block + 1) * 0x10000;
    if (address >= base && address - base <= sizeof(snapshot->blocks[block]) &&
        size <= sizeof(snapshot->blocks[block]) - (address - base)) {
      memcpy(output, snapshot->blocks[block] + (address - base), size);
      if (call == 9 && snapshot->replace_owner) encode_pointer(output, DEMO + 8);
      return 1;
    }
  }
  return 0;
}

static int mesh_ready(const FixDemoPropOwnerToken *token, MemorySnapshot *snapshot) {
  return fixdemo_prop_mesh_ready(FIXDEMO_PROP_VALIDATED_BUT_INACTIVE,
      token, 7, 1, read_memory, snapshot);
}

static void test_memory_chain(void) {
  MemorySnapshot snapshot;
  for (size_t kind = 0; kind < COUNT(fixdemo_prop_mappings); ++kind) {
    const FixDemoPropMapping *mapping = &fixdemo_prop_mappings[kind];
    FixDemoPropOwnerToken token = {OWNER, 7, mapping->kind};
    memory_clean(&snapshot, mapping);
    unsigned char before[sizeof(snapshot.blocks)];
    memcpy(before, snapshot.blocks, sizeof(before));
    assert(mesh_ready(&token, &snapshot) && snapshot.calls == 10);
    assert(!memcmp(before, snapshot.blocks, sizeof(before)));

    for (int failure = 0; failure < 10; ++failure) {
      memory_clean(&snapshot, mapping);
      snapshot.fail_call = failure;
      assert(!mesh_ready(&token, &snapshot) && snapshot.calls == (size_t)failure + 1);
    }
    for (size_t link = 0; link < COUNT(chain); ++link) {
      const uint64_t invalid[] = {0, 1, MESH + 1};
      for (size_t j = 0; j < COUNT(invalid); ++j) {
        memory_clean(&snapshot, mapping);
        encode_pointer(snapshot.blocks[chain[link].base / 0x10000 - 1] + chain[link].offset,
            invalid[j]);
        assert(!mesh_ready(&token, &snapshot) && snapshot.calls == link + 1);
      }
    }
    /* A valid-looking pointer outside the snapshot never becomes a raw dereference. */
    for (size_t link = 0; link < 6; ++link) {
      memory_clean(&snapshot, mapping);
      encode_pointer(snapshot.blocks[chain[link].base / 0x10000 - 1] + chain[link].offset,
          UINT64_C(0x90000));
      assert(!mesh_ready(&token, &snapshot));
    }
    memory_clean(&snapshot, mapping);
    encode_pointer(snapshot.blocks[COMPONENT / 0x10000 - 1] + 1456, MESH + 8);
    assert(!mesh_ready(&token, &snapshot) && snapshot.calls == 8);
    for (size_t byte = 0; byte <= strlen(mapping->ue_name); ++byte) {
      memory_clean(&snapshot, mapping);
      snapshot.blocks[IMPL / 0x10000 - 1][byte] ^= 1;
      assert(!mesh_ready(&token, &snapshot) && snapshot.calls == 9);
    }
    memory_clean(&snapshot, mapping);
    snapshot.replace_owner = 1;
    assert(!mesh_ready(&token, &snapshot) && snapshot.calls == 10);

    for (int failure = 0; failure < 11; ++failure) {
      memory_clean(&snapshot, mapping);
      token.owner = OWNER; token.epoch = 7; token.kind = mapping->kind;
      enum FixDemoPropPreflight state = FIXDEMO_PROP_VALIDATED_BUT_INACTIVE;
      uint64_t epoch = 7;
      int serialized = 1;
      switch (failure) {
        case 0: state = FIXDEMO_PROP_NOT_REQUESTED; break;
        case 1: state = FIXDEMO_PROP_BAD_PACKAGE; break;
        case 2: state = FIXDEMO_PROP_BAD_ABI; break;
        case 3: token.epoch = 0; break;
        case 4: epoch = 8; break;
        case 5: serialized = 0; break;
        case 6: serialized = 2; break;
        case 7: token.kind = FIXDEMO_PROP_NONE; break;
        case 8: token.kind = (enum FixDemoPropKind)99; break;
        case 9: token.owner = 0; break;
        case 10: token.owner = OWNER + 1; break;
      }
      assert(!fixdemo_prop_mesh_ready(state, &token, epoch, serialized, read_memory, &snapshot));
      assert(!snapshot.calls);
    }
    memory_clean(&snapshot, mapping);
    assert(!mesh_ready(NULL, &snapshot) && !snapshot.calls);
    token.owner = OWNER; token.epoch = 7; token.kind = mapping->kind;
    assert(!fixdemo_prop_mesh_ready(FIXDEMO_PROP_VALIDATED_BUT_INACTIVE,
        &token, 7, 1, NULL, &snapshot));
    assert(!snapshot.calls);
  }
}

static struct {
  int creates, destroys, type, expect_forgotten;
  void *owner, *skeleton, *colors;
  const char *path;
  FixDemoPropOwnerToken *token;
} native;

static void native_create(void *owner, int type, const char *path, void *skeleton, void *colors) {
  ++native.creates;
  assert(owner == native.owner && type == native.type && path == native.path);
  assert(skeleton == native.skeleton && colors == native.colors);
}

static void native_destroy(void *owner) {
  ++native.destroys;
  assert(owner == native.owner);
  if (native.expect_forgotten)
    assert(native.token && !native.token->owner && !native.token->epoch &&
        native.token->kind == FIXDEMO_PROP_NONE);
}

static void test_lifecycle(void) {
  unsigned char owner[64] = {0}, skeleton[8] = {0}, colors[8] = {0};
  native.owner = owner;
  native.skeleton = skeleton;
  native.colors = colors;
  const char *paths[] = {
    fixdemo_prop_mappings[0].descriptor_path, fixdemo_prop_mappings[0].runtime_path,
    fixdemo_prop_mappings[1].descriptor_path, fixdemo_prop_mappings[1].runtime_path,
    "common/character0/model/boots/boots.xml", "unrelated/skeleton.xml", NULL,
  };
  for (size_t i = 0; i < COUNT(paths); ++i) {
    native.path = paths[i];
    native.type = (int)i - 2;
    const int before = native.creates;
    assert(fixdemo_prop_forward_create(native_create, owner, native.type, native.path, skeleton, colors));
    assert(native.creates == before + 1);
    assert(!fixdemo_prop_forward_create(NULL, owner, native.type, native.path, skeleton, colors));
    assert(native.creates == before + 1);
  }
  native.owner = NULL; native.skeleton = NULL; native.colors = NULL; native.path = NULL;
  const int before = native.creates;
  assert(fixdemo_prop_forward_create(native_create, NULL, native.type, NULL, NULL, NULL));
  assert(native.creates == before + 1);
  native.owner = owner;

  FixDemoPropOwnerToken token = {(uintptr_t)owner, 7, FIXDEMO_PROP_CUP};
  native.token = &token;
  native.expect_forgotten = 1;
  assert(fixdemo_prop_forward_destroy(native_destroy, owner, &token));
  assert(native.destroys == 1 && !token.owner && !token.epoch && token.kind == FIXDEMO_PROP_NONE);
  native.expect_forgotten = 0;
  assert(fixdemo_prop_forward_destroy(native_destroy, owner, &token));
  assert(native.destroys == 2);
  token.owner = (uintptr_t)skeleton; token.epoch = 9; token.kind = FIXDEMO_PROP_PODIUM;
  assert(fixdemo_prop_forward_destroy(native_destroy, owner, &token));
  assert(native.destroys == 3 && token.owner == (uintptr_t)skeleton && token.epoch == 9 &&
      token.kind == FIXDEMO_PROP_PODIUM);
  assert(fixdemo_prop_forward_destroy(native_destroy, owner, NULL));
  assert(native.destroys == 4);
  assert(!fixdemo_prop_forward_destroy(NULL, owner, &token));
  assert(native.destroys == 4 && token.owner == (uintptr_t)skeleton && token.epoch == 9);
  fixdemo_prop_forget_owner(&token);
  assert(!token.owner && !token.epoch && token.kind == FIXDEMO_PROP_NONE);
  fixdemo_prop_forget_owner(NULL);
  for (size_t i = 0; i < sizeof(owner); ++i) assert(!owner[i]);
  for (size_t i = 0; i < sizeof(skeleton); ++i) assert(!skeleton[i] && !colors[i]);
}

int main(int argc, char **argv) {
  assert(argc == 2 && sizeof(uintptr_t) == 8);
  const struct { const char *name; void (*run)(void); } cases[] = {
    {"paths", test_paths}, {"packages", test_packages}, {"abi", test_abi},
    {"preflight", test_preflight}, {"pointer-bounds", test_pointer_bounds},
    {"memory-chain", test_memory_chain}, {"lifecycle", test_lifecycle},
  };
  for (size_t i = 0; i < COUNT(cases); ++i) {
    if (!strcmp(argv[1], cases[i].name)) {
      cases[i].run();
      printf("fixdemo prop bridge %s: pass\n", cases[i].name);
      return 0;
    }
  }
  assert(!"unknown test case");
  return 1;
}
