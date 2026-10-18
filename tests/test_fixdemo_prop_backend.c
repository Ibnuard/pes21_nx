#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define PESNX_FIXDEMO_PROP_BACKEND_PROBE 1
#include "../source/fixdemo_prop_backend.h"

static union { uint64_t alignment; unsigned char bytes[320]; } owner;
static struct {
  const FixDemoPropMapping *mapping;
  const char *path;
  int type, failure, creates, deletes, old_frees, new_frees;
  unsigned char skeleton[16], colors[16];
  void *old_string, *new_string, *demo;
  char events[32];
  size_t event_count;
  FixDemoPropBackendLoadId seen;
} mock;

enum { OK, ASSIGN_BEFORE, ASSIGN_AFTER, ALLOCATE, INIT_FALSE, NULL_MODEL,
       INVALID_KEY, MISALIGNED_MODEL, REPLACE_SLOT, REPLACE_ID, REPLACE_LOAD_ID };

static void event(char ch) {
  assert(mock.event_count + 1 < sizeof(mock.events));
  mock.events[mock.event_count++] = ch;
}

static void string_set(FixDemoPropBackendString *value, char *buffer, size_t size) {
  const uint64_t capacity = ((size + 16) & ~UINT64_C(15)) | 1;
  memset(value, 0, sizeof(*value));
  memcpy(value->bytes, &capacity, 8);
  memcpy(value->bytes + 8, &size, 8);
  memcpy(value->bytes + 16, &buffer, 8);
}

static const char *string_chars(const FixDemoPropBackendString *value) {
  if (!(value->bytes[0] & 1)) return (const char *)value->bytes + 1;
  char *buffer;
  memcpy(&buffer, value->bytes + 16, sizeof(buffer));
  return buffer;
}

static void reset_mock(size_t mapping, int type, uint32_t mode) {
  memset(&mock, 0, sizeof(mock));
  memset(&owner, 0xa5, sizeof(owner));
  mock.mapping = &fixdemo_prop_mappings[mapping];
  mock.path = mock.mapping->runtime_path;
  mock.type = type;
  const uint16_t id = 0x1234;
  memcpy(owner.bytes + 232, &id, sizeof(id));
  const uintptr_t previous[] = {0x11000, 0x12000, 0x13000};
  memcpy(owner.bytes + 184, previous, sizeof(previous));
  FixDemoPropBackendLoadId load = {0};
  load.object_id = 0x4444;
  load.mode = mode;
  load.has_color = 1;
  memset(load.color, 0xab, sizeof(load.color));
  const char *old = "the previous native allocated CobraString";
  mock.old_string = malloc(strlen(old) + 1);
  assert(mock.old_string);
  memcpy(mock.old_string, old, strlen(old) + 1);
  string_set(&load.name, mock.old_string, strlen(old));
  memcpy(owner.bytes + 240, &load, sizeof(load));
  for (size_t i = 0; i < sizeof(mock.colors); ++i) mock.colors[i] = (unsigned char)(i * 13);
}

static void original(void *object, int type, const char *path, void *skeleton, void *colors) {
  event('O'); ++mock.creates;
  assert(object == &owner && type == mock.type && path == mock.path);
  assert(skeleton == mock.skeleton && colors == mock.colors);
  /* The real function's skeleton branch first deletes all three render slots. */
  memset(owner.bytes + 184, 0, 24);
}

static void *assign_string(void *destination, const char *path, size_t size) {
  event('S');
  assert(!strcmp(path, mock.mapping->ue_name) && size == strlen(path));
  if (mock.failure == ASSIGN_BEFORE) return NULL;
  mock.new_string = malloc(size + 1); assert(mock.new_string);
  memcpy(mock.new_string, path, size + 1);
  string_set(destination, mock.new_string, size);
  return mock.failure == ASSIGN_AFTER ? NULL : destination;
}

static void basic_free(void *pointer) {
  if (pointer == mock.old_string) { event('o'); ++mock.old_frees; assert(mock.old_frees == 1); }
  else { event('n'); assert(pointer == mock.new_string); ++mock.new_frees; assert(mock.new_frees == 1); }
  free(pointer);
}

static void *allocate_demo(size_t size) {
  event('A'); assert(size == 24);
  if (mock.failure == ALLOCATE) return NULL;
  mock.demo = malloc(size); assert(mock.demo);
  return mock.demo;
}

static void construct_demo(void *demo) {
  event('C'); assert(demo == mock.demo);
  memset(demo, 0, 24);
  const uintptr_t table = 0x88000;
  memcpy(demo, &table, 8);
  ((unsigned char *)demo)[20] = 1;
}

static int init_demo(void *demo, void *load_id) {
  event('I'); assert(demo == mock.demo);
  const FixDemoPropBackendLoadId *load = load_id;
  assert(load->object_id == 0x1234);
  assert(!strcmp(string_chars(&load->name), mock.mapping->ue_name));
  assert(load->has_color == (mock.type == 1));
  if (load->has_color) assert(!memcmp(load->color, mock.colors, 16));
  mock.seen = *load;
  const uintptr_t model = mock.failure == NULL_MODEL ? 0 : mock.failure == MISALIGNED_MODEL ? 0x90001 : 0x90000;
  const uint32_t key = mock.failure == INVALID_KEY ? 192 : 17;
  memcpy((unsigned char *)demo + 8, &model, 8);
  memcpy((unsigned char *)demo + 16, &key, 4);
  if (mock.failure == REPLACE_SLOT) {
    const uintptr_t foreign = 0xa0000;
    memcpy(owner.bytes + 184, &foreign, 8);
  } else if (mock.failure == REPLACE_ID) {
    owner.bytes[232] ^= 1;
  } else if (mock.failure == REPLACE_LOAD_ID) {
    owner.bytes[272] ^= 1;
  }
  return mock.failure == INIT_FALSE ? 0 : 1;
}

static void set_display(void *demo, int visible) {
  event('H'); assert(demo == mock.demo && visible == 0);
  ((unsigned char *)demo)[20] = 0;
}

static void delete_demo(void *demo) {
  event('D'); assert(demo == mock.demo && ++mock.deletes == 1);
  uint32_t key;
  memcpy(&key, (unsigned char *)demo + 16, sizeof(key));
  assert(key == (mock.failure == INVALID_KEY ? 192u : 17u));
  assert(((unsigned char *)demo)[20] == 0);
  free(demo);
}

static FixDemoPropBackendOps ops(void) {
  const FixDemoPropBackendOps value = {
    original, assign_string, basic_free, allocate_demo, construct_demo, init_demo, set_display, delete_demo
  };
  return value;
}

static enum FixDemoPropBackendResult run(const FixDemoPropBackendOps *callbacks,
    enum FixDemoPropPreflight state, int thread, size_t span) {
  return fixdemo_prop_backend_candidate(callbacks, state, thread, &owner, span,
      mock.type, mock.path, mock.path ? strlen(mock.path) : 0, mock.skeleton, mock.colors);
}

static void finish(const FixDemoPropBackendOps *callbacks) {
  uintptr_t attached;
  memcpy(&attached, owner.bytes + 184, 8);
  if (attached && attached == (uintptr_t)mock.demo) callbacks->delete_demo((void *)attached);
  FixDemoPropBackendLoadId load;
  memcpy(&load, owner.bytes + 240, sizeof(load));
  fixdemo_prop_backend_release_string(callbacks, &load.name);
  assert(mock.old_frees == 1);
  if (mock.new_string) assert(mock.new_frees == 1);
}

static void test_forward(void) {
  for (int reject = 0; reject < 15; ++reject) {
    reset_mock(0, 0, 0);
    FixDemoPropBackendOps callbacks = ops();
    enum FixDemoPropPreflight state = FIXDEMO_PROP_VALIDATED_BUT_INACTIVE;
    int thread = 1;
    size_t span = sizeof(owner);
    switch (reject) {
      case 0: state = FIXDEMO_PROP_NOT_REQUESTED; break;
      case 1: state = FIXDEMO_PROP_BAD_PACKAGE; break;
      case 2: state = FIXDEMO_PROP_BAD_ABI; break;
      case 3: thread = 0; break;
      case 4: thread = 2; break;
      case 5: mock.path = mock.mapping->descriptor_path; break;
      case 6: mock.path = "unrelated/model.xml"; break;
      case 7: mock.path = NULL; break;
      case 8: callbacks.assign_string = NULL; break;
      case 9: callbacks.basic_free = NULL; break;
      case 10: callbacks.allocate_demo = NULL; break;
      case 11: callbacks.construct_demo = NULL; break;
      case 12: callbacks.init_demo = NULL; break;
      case 13: callbacks.set_display = NULL; break;
      case 14: callbacks.delete_demo = NULL; break;
    }
    assert(run(&callbacks, state, thread, span) == FIXDEMO_PROP_BACKEND_FORWARDED);
    assert(mock.creates == 1 && !strcmp(mock.events, "O"));
    callbacks = ops(); finish(&callbacks);
  }
  reset_mock(0, 0, 0);
  FixDemoPropBackendOps callbacks = ops();
  assert(run(&callbacks, FIXDEMO_PROP_VALIDATED_BUT_INACTIVE, 1, 295) == FIXDEMO_PROP_BACKEND_BAD_OWNER);
  assert(mock.creates == 1 && !strcmp(mock.events, "O"));
  finish(&callbacks);
  reset_mock(0, 0, 0);
  callbacks = ops(); callbacks.create = NULL;
  assert(run(&callbacks, FIXDEMO_PROP_VALIDATED_BUT_INACTIVE, 1, sizeof(owner)) == FIXDEMO_PROP_BACKEND_NO_ORIGINAL);
  assert(!mock.creates && !mock.events[0]);
  assert(run(NULL, FIXDEMO_PROP_VALIDATED_BUT_INACTIVE, 1, sizeof(owner)) == FIXDEMO_PROP_BACKEND_NO_ORIGINAL);
  callbacks = ops(); finish(&callbacks);
}

static void test_attach(void) {
  for (size_t mapping = 0; mapping < 2; ++mapping) {
    for (int type = 0; type <= 2; ++type) {
      for (uint32_t mode = 0; mode <= 2; ++mode) {
        reset_mock(mapping, type, mode);
        const FixDemoPropBackendOps callbacks = ops();
        unsigned char before[sizeof(owner)];
        memcpy(before, &owner, sizeof(before));
        assert(run(&callbacks, FIXDEMO_PROP_VALIDATED_BUT_INACTIVE, 1, sizeof(owner)) ==
            FIXDEMO_PROP_BACKEND_ATTACHED_HIDDEN);
        assert(mock.creates == 1 && !strcmp(mock.events, "OSACIHo"));
        assert(mock.old_frees == 1 && !mock.new_frees && !mock.deletes);
        assert(mock.seen.mode == (mode < 2 ? mode : 0));
        uintptr_t attached;
        memcpy(&attached, owner.bytes + 184, 8);
        assert(attached == (uintptr_t)mock.demo && ((unsigned char *)mock.demo)[20] == 0);
        FixDemoPropBackendLoadId moved;
        memcpy(&moved, owner.bytes + 240, sizeof(moved));
        assert(!memcmp(&moved, &mock.seen, sizeof(moved)));
        assert(string_chars(&moved.name) == mock.new_string);
        /* Root/parent transforms, animation handle +208 and all other fields survive. */
        for (size_t byte = 0; byte < sizeof(before); ++byte)
          if (!(184 <= byte && byte < 208) && !(240 <= byte && byte < 296))
            assert(owner.bytes[byte] == before[byte]);
        assert(!fixdemo_prop_can_activate(FIXDEMO_PROP_VALIDATED_BUT_INACTIVE));
        finish(&callbacks);
        assert(mock.deletes == 1 && mock.new_frees == 1);
      }
    }
  }
}

static void test_rollback(void) {
  const enum FixDemoPropBackendResult expected[] = {
    FIXDEMO_PROP_BACKEND_ASSIGN_FAILED, FIXDEMO_PROP_BACKEND_ASSIGN_FAILED,
    FIXDEMO_PROP_BACKEND_ALLOCATION_FAILED, FIXDEMO_PROP_BACKEND_LOAD_FAILED,
    FIXDEMO_PROP_BACKEND_LOAD_FAILED, FIXDEMO_PROP_BACKEND_LOAD_FAILED,
    FIXDEMO_PROP_BACKEND_LOAD_FAILED
  };
  for (int failure = ASSIGN_BEFORE; failure <= MISALIGNED_MODEL; ++failure) {
    reset_mock(0, 1, 1); mock.failure = failure;
    const FixDemoPropBackendOps callbacks = ops();
    unsigned char before[sizeof(owner)]; memcpy(before, &owner, sizeof(before));
    memset(before + 184, 0, 24); /* Original cleanup is intentionally retained. */
    assert(run(&callbacks, FIXDEMO_PROP_VALIDATED_BUT_INACTIVE, 1, sizeof(owner)) == expected[failure - 1]);
    assert(mock.creates == 1 && !mock.old_frees);
    assert(!memcmp(before, &owner, sizeof(before)));
    assert(mock.deletes == (failure >= INIT_FALSE));
    assert(mock.new_frees == (failure >= ASSIGN_AFTER));
    finish(&callbacks);
  }
}

static void test_ownership(void) {
  for (int failure = REPLACE_SLOT; failure <= REPLACE_LOAD_ID; ++failure) {
    reset_mock(1, 0, 0); mock.failure = failure;
    const FixDemoPropBackendOps callbacks = ops();
    assert(run(&callbacks, FIXDEMO_PROP_VALIDATED_BUT_INACTIVE, 1, sizeof(owner)) ==
        FIXDEMO_PROP_BACKEND_OWNER_CHANGED);
    assert(mock.creates == 1 && mock.deletes == 1 && !mock.old_frees && mock.new_frees == 1);
    assert(!strcmp(mock.events, "OSACIHDn"));
    FixDemoPropBackendLoadId load;
    memcpy(&load, owner.bytes + 240, sizeof(load));
    assert(string_chars(&load.name) == mock.old_string);
    finish(&callbacks);
  }
  /* A native short string has no heap owner to free during the move. */
  reset_mock(0, 0, 0);
  const FixDemoPropBackendOps callbacks = ops();
  free(mock.old_string); mock.old_string = NULL;
  FixDemoPropBackendString small = {0};
  small.bytes[0] = 3 * 2;
  memcpy(small.bytes + 1, "old", 4);
  memcpy(owner.bytes + 248, &small, sizeof(small));
  assert(run(&callbacks, FIXDEMO_PROP_VALIDATED_BUT_INACTIVE, 1, sizeof(owner)) ==
      FIXDEMO_PROP_BACKEND_ATTACHED_HIDDEN);
  assert(!mock.old_frees && !mock.new_frees);
  callbacks.delete_demo(mock.demo);
  FixDemoPropBackendLoadId load;
  memcpy(&load, owner.bytes + 240, sizeof(load));
  fixdemo_prop_backend_release_string(&callbacks, &load.name);
  assert(mock.new_frees == 1);
  fixdemo_prop_backend_release_string(&callbacks, &load.name);
  assert(mock.new_frees == 1);
}

int main(int argc, char **argv) {
  assert(argc == 2 && sizeof(uintptr_t) == 8);
  if (!strcmp(argv[1], "forward")) test_forward();
  else if (!strcmp(argv[1], "attach")) test_attach();
  else if (!strcmp(argv[1], "rollback")) test_rollback();
  else if (!strcmp(argv[1], "ownership")) test_ownership();
  else assert(!"unknown case");
  printf("fixdemo prop backend %s: pass\n", argv[1]);
  return 0;
}
