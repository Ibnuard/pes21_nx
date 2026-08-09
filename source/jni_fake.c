/* jni_fake.c -- fake JNI environment for the GTA:SA oswrapper/GameNative layer
 *
 * The JNIEnv/JavaVM function tables here are the standard JNI ABI and are
 * framework-agnostic; only the dispatch in hal_* (keyed by the Java method
 * name) is specific to the oswrapper engine GTA:SA 2.11.311 uses.
 *
 * This software may be modified and distributed under the terms
 * of the MIT license. See the LICENSE file for details.
 */

#include <stdlib.h>
#include <stdio.h>
#include <stdint.h>
#include <stdarg.h>
#include <string.h>
#include <switch.h>

#include "config.h"
#include "util.h"
#include "jni_fake.h"

#define JNI_OK 0
#define JNI_VERSION_1_6 0x00010006

typedef uint64_t juint;

// ---------------------------------------------------------------------------
// fake object model
// ---------------------------------------------------------------------------

enum {
  TAG_OBJECT = 0x4f424a31, // 'OBJ1'
  TAG_STRING = 0x53545231, // 'STR1'
  TAG_OBJARR = 0x4f415231, // 'OAR1'
  TAG_PRIARR = 0x50415231, // 'PAR1'
  TAG_ID     = 0x4d494431, // 'MID1'
};

typedef struct {
  uint32_t tag;
  char label[96];
  int http_state;
  int http_status_code;
  int http_data_len;
  int http_state_polls;
  uint8_t *http_data;
  char http_file_path[256];
  char http_tmp_file_path[256];
  uint64_t http_assumed_file_size;
} FakeObject;

typedef struct {
  uint32_t tag;
  char *utf;
} FakeString;

typedef struct {
  uint32_t tag;
  int len;
  void **items;
} FakeObjArray;

typedef struct {
  uint32_t tag;
  int len;
  int elem_size;
  void *data;
} FakePriArray;

// method/field IDs are pointers to these records; calls dispatch by (class, name).
typedef struct {
  uint32_t tag;
  char cls[64];
  char name[80];
  char sig[80];
} FakeID;

volatile int jni_quit_requested = 0;
volatile int jni_frontend_ready = 0;
static void (*native_init_hmds_callback)(void *env, void *activity);
static void (*webview_finish_navigation_callback)(void);
static _Alignas(4) uint32_t webview_finish_navigation_pending;
static int software_keyboard_done;
static char software_keyboard_text[256];

void jni_set_native_init_hmds(void (*callback)(void *, void *)) {
  native_init_hmds_callback = callback;
}

void jni_set_webview_finish_navigation(void (*callback)(void)) {
  webview_finish_navigation_callback = callback;
}

void jni_poll_platform_callbacks(void) {
  if (__atomic_exchange_n(&webview_finish_navigation_pending, 0,
                          __ATOMIC_ACQ_REL) &&
      webview_finish_navigation_callback) {
    debugPrintf("JNI: KWebDialog navigation complete -> native callback\n");
    webview_finish_navigation_callback();
  }
}

// ---------------------------------------------------------------------------
// deferred native-callback queue (the Java->native completion direction)
// ---------------------------------------------------------------------------

#define CB_QUEUE_LEN 32
static JniCallback cb_queue[CB_QUEUE_LEN];
static int cb_head = 0, cb_tail = 0;

static void push_cb(JniCallbackType type, int arg0, int arg1) {
  const int next = (cb_tail + 1) % CB_QUEUE_LEN;
  if (next == cb_head) {
    debugPrintf("JNI: callback queue full, dropping %d\n", type);
    return;
  }
  cb_queue[cb_tail].type = type;
  cb_queue[cb_tail].arg0 = arg0;
  cb_queue[cb_tail].arg1 = arg1;
  cb_tail = next;
}

int jni_pop_callback(JniCallback *out) {
  if (cb_head == cb_tail)
    return 0;
  if (out)
    *out = cb_queue[cb_head];
  cb_head = (cb_head + 1) % CB_QUEUE_LEN;
  return 1;
}

void *jni_make_object(const char *label) {
  FakeObject *o = calloc(1, sizeof(*o));
  o->tag = TAG_OBJECT;
  strncpy(o->label, label, sizeof(o->label) - 1);
  o->label[sizeof(o->label) - 1] = '\0';   // strncpy may not NUL-terminate
  return o;
}

void *jni_make_string(const char *utf) {
  FakeString *s = calloc(1, sizeof(*s));
  s->tag = TAG_STRING;
  s->utf = strdup(utf ? utf : "");
  return s;
}

void *jni_make_string_array(int n, const char **strs) {
  FakeObjArray *a = calloc(1, sizeof(*a));
  a->tag = TAG_OBJARR;
  a->len = n;
  a->items = calloc(n ? n : 1, sizeof(void *));
  for (int i = 0; i < n; i++)
    a->items[i] = jni_make_string(strs[i]);
  return a;
}

void *jni_make_int_array(int n, const int *vals) {
  FakePriArray *a = calloc(1, sizeof(*a));
  a->tag = TAG_PRIARR;
  a->len = n;
  a->elem_size = sizeof(int);
  a->data = calloc(n ? n : 1, sizeof(int));
  if (vals)
    memcpy(a->data, vals, n * sizeof(int));
  return a;
}

static const char *obj_str(void *jstr) {
  FakeString *s = jstr;
  if (s && s->tag == TAG_STRING)
    return s->utf;
  return "";
}

static FakeObject *fake_object(void *obj) {
  FakeObject *o = obj;
  return o && o->tag == TAG_OBJECT ? o : NULL;
}

static void set_is_copy(uint8_t *is_copy, uint8_t value) {
  // Some game call sites pass JNI_TRUE instead of a jboolean pointer.
  if ((uintptr_t)is_copy > 0x1000)
    *is_copy = value;
}

static void *jni_make_byte_array(const void *data, int len) {
  FakePriArray *a = calloc(1, sizeof(*a));
  a->tag = TAG_PRIARR;
  a->len = len > 0 ? len : 0;
  a->elem_size = 1;
  a->data = calloc(a->len ? a->len : 1, 1);
  if (data && a->len)
    memcpy(a->data, data, a->len);
  return a;
}

enum {
  HTTP_S_DORMANT = 0,
  HTTP_S_CONNECTING = 1,
  HTTP_S_COMPLETE = 4,
  HTTP_S_ERROR = 5,
  HTTP_S_CANCELED = 6,
};

typedef struct {
  const char *command;
  const char *asset;
} HttpResponseAlias;

static const HttpResponseAlias http_response_aliases[] = {
  { "CmdGetServerEnv", "CMD_GET_SERVER_ENV" },
  { "CmdGetCountryList", "GetCountryList" },
  { "CmdGetProductList", "get_product_list" },
  { "CmdGetMyclubMainmenuInfo", "get_myclub_mainmenu_info" },
  { "CmdGetMyclubCoachContractNorma", "get_myclub_coaches_norma" },
  { "CmdGetMyclubCommentaryInfo", "get_myclub_commentary_info" },
  { "CmdSetMyclubEntryInfo", "set_myclub_entry_info" },
};

static int read_http_payload(const char *path, uint8_t **out_data, int *out_len) {
  FILE *f = fopen(path, "rb");
  if (!f)
    return 0;

  if (fseek(f, 0, SEEK_END) != 0) {
    fclose(f);
    return 0;
  }
  const long size = ftell(f);
  if (size <= 0 || size > INT32_MAX || fseek(f, 0, SEEK_SET) != 0) {
    fclose(f);
    return 0;
  }

  uint8_t *data = malloc((size_t)size);
  if (!data || fread(data, 1, (size_t)size, f) != (size_t)size) {
    free(data);
    fclose(f);
    return 0;
  }
  fclose(f);
  *out_data = data;
  *out_len = (int)size;
  return 1;
}

static const char *http_asset_name(const char *command) {
  for (size_t i = 0; i < sizeof(http_response_aliases) / sizeof(http_response_aliases[0]); i++) {
    if (!strcmp(command, http_response_aliases[i].command))
      return http_response_aliases[i].asset;
  }
  return command;
}

static int load_http_response(FakeObject *o, const char *url) {
  char command[128] = { 0 };
  char path[256];
  const char *base = strrchr(url ? url : "", '/');
  base = base ? base + 1 : (url ? url : "");
  strlcpy(command, base, sizeof(command));

  char *query = strpbrk(command, "?#");
  if (query)
    *query = 0;
  char *php = strstr(command, ".php");
  if (php)
    *php = 0;

  const char *asset = http_asset_name(command);
  snprintf(path, sizeof(path), "assets/responses/%s.bin", asset);
  if (!read_http_payload(path, &o->http_data, &o->http_data_len) &&
      strcmp(asset, command)) {
    snprintf(path, sizeof(path), "assets/responses/%s.bin", command);
    (void)read_http_payload(path, &o->http_data, &o->http_data_len);
  }

  if (!o->http_data) {
    strlcpy(path, "assets/responses/generic.bin", sizeof(path));
    (void)read_http_payload(path, &o->http_data, &o->http_data_len);
  }

  if (!o->http_data) {
    debugPrintf("JNI HTTP: no payload for url=%s command=%s\n", url, command);
    return 0;
  }

  debugPrintf("JNI HTTP: url=%s command=%s asset=%s bytes=%d\n",
              url, command, path, o->http_data_len);
  return 1;
}

static void reset_http_response(FakeObject *o) {
  if (!o)
    return;
  free(o->http_data);
  o->http_data = NULL;
  o->http_data_len = 0;
  o->http_status_code = 0;
  o->http_state = HTTP_S_DORMANT;
  o->http_state_polls = 0;
}

// ---------------------------------------------------------------------------
// app-local key/value store (get/setAppLocalValue), persisted as tab-separated
// lines. Backs STORAGE_ROOT and the engine's misc settings.
// ---------------------------------------------------------------------------

#define KV_MAX 256

typedef struct {
  char key[64];
  char val[256];
} KvPair;

static KvPair kv_store[KV_MAX];
static int kv_count = 0;

static const char *kv_get(const char *key) {
  for (int i = 0; i < kv_count; i++)
    if (!strcmp(kv_store[i].key, key))
      return kv_store[i].val;
  return NULL;
}

static void kv_save(void) {
  FILE *f = fopen(APPSTATE_NAME, "w");
  if (!f)
    return;
  for (int i = 0; i < kv_count; i++)
    fprintf(f, "%s\t%s\n", kv_store[i].key, kv_store[i].val);
  fclose(f);
}

static void kv_set(const char *key, const char *val) {
  for (int i = 0; i < kv_count; i++) {
    if (!strcmp(kv_store[i].key, key)) {
      strlcpy(kv_store[i].val, val, sizeof(kv_store[i].val));
      kv_save();
      return;
    }
  }
  if (kv_count >= KV_MAX) {
    debugPrintf("JNI: app-local store full, dropping %s\n", key);
    return;
  }
  strlcpy(kv_store[kv_count].key, key, sizeof(kv_store[kv_count].key));
  strlcpy(kv_store[kv_count].val, val, sizeof(kv_store[kv_count].val));
  kv_count++;
  kv_save();
}

static void kv_load(void) {
  FILE *f = fopen(APPSTATE_NAME, "r");
  if (!f)
    return;
  char line[360];
  while (kv_count < KV_MAX && fgets(line, sizeof(line), f)) {
    char *tab = strchr(line, '\t');
    if (!tab)
      continue;
    *tab = 0;
    char *val = tab + 1;
    val[strcspn(val, "\r\n")] = 0;
    strlcpy(kv_store[kv_count].key, line, sizeof(kv_store[kv_count].key));
    strlcpy(kv_store[kv_count].val, val, sizeof(kv_store[kv_count].val));
    kv_count++;
  }
  fclose(f);
}

// method/field ID pool
#define MAX_IDS 512
static FakeID id_pool[MAX_IDS];
static int id_count = 0;

static FakeID *get_id(const char *cls, const char *name, const char *sig) {
  for (int i = 0; i < id_count; i++) {
    if (!strcmp(id_pool[i].name, name) && !strcmp(id_pool[i].sig, sig) &&
        !strcmp(id_pool[i].cls, cls))
      return &id_pool[i];
  }
  if (id_count >= MAX_IDS) {
    debugPrintf("JNI: id pool exhausted!\n");
    return &id_pool[0];
  }
  FakeID *id = &id_pool[id_count++];
  id->tag = TAG_ID;
  snprintf(id->cls, sizeof(id->cls), "%s", cls);
  snprintf(id->name, sizeof(id->name), "%s", name);
  snprintf(id->sig, sizeof(id->sig), "%s", sig);
  return id;
}

// label of the FakeObject that FindClass produced for this jclass
static const char *class_label(void *cls) {
  FakeObject *o = cls;
  if (o && o->tag == TAG_OBJECT)
    return o->label;
  return "";
}

// va_list arg helpers (JNI variadic: small ints promote to int, jobject is a pointer)
static const char *next_str(va_list va) { return obj_str(va_arg(va, void *)); }
static int next_int(va_list va) { return va_arg(va, int); }

// ---------------------------------------------------------------------------
// HAL dispatch, keyed by the Java method name. Anything not handled returns a
// sane default (the engine treats missing services as "feature unavailable").
// ---------------------------------------------------------------------------

static int name_is(const FakeID *id, const char *n) { return strcmp(id->name, n) == 0; }

static void hal_void(void *obj, const FakeID *id, va_list va) {
  const char *name = id->name;
  FakeObject *o = fake_object(obj);

  if (!strcmp(id->cls, "jp/konami/SoftwareKeyboard") &&
      name_is(id, "show")) {
    (void)va_arg(va, void *); // Android Context
    const char *initial_text = obj_str(va_arg(va, void *));
    const int keyboard_type = va_arg(va, int);
    const int max_length = va_arg(va, int);
    const char *text = initial_text[0] ? initial_text : "revon";
    strlcpy(software_keyboard_text, text, sizeof(software_keyboard_text));
    if (max_length > 0 && max_length < (int)sizeof(software_keyboard_text))
      software_keyboard_text[max_length] = '\0';
    software_keyboard_done = 1;
    debugPrintf("JNI: SoftwareKeyboard.show(type=%d max=%d initial=\"%s\")"
                " -> \"%s\"\n",
                keyboard_type, max_length, initial_text,
                software_keyboard_text);
    return;
  }

  if (!strcmp(id->cls, "java/lang/Thread") && name_is(id, "setName")) {
    void *tls;
    __asm__ volatile("mrs %0, tpidr_el0" : "=r"(tls));
    debugPrintf("JNI: Thread.setName(tls=%p, name=%s)\n", tls, next_str(va));
    return;
  }

  if (name_is(id, "AndroidThunkJava_InitHMDs")) {
    debugPrintf("JNI: AndroidThunkJava_InitHMDs -> nativeInitHMDs\n");
    if (native_init_hmds_callback)
      native_init_hmds_callback(fake_env, NULL);
    return;
  }

  // UE4's Android error dialog is otherwise invisible on Switch. Log every
  // field so fatal startup errors remain diagnosable from debug.log.
  if (!strcmp(id->cls, "osobject") &&
      (name_is(id, "setCaption") || name_is(id, "setText") ||
       name_is(id, "addButton"))) {
    debugPrintf("JNI: osobject.%s(\"%s\")\n", name, next_str(va));
    return;
  }
  if (!strcmp(id->cls, "osobject") && name_is(id, "clear")) {
    debugPrintf("JNI: osobject.clear()\n");
    return;
  }

  if (!strcmp(id->cls, "osobject") && name_is(id, "Clear")) {
    (void)next_int(va);
    reset_http_response(o);
    debugPrintf("JNI HTTP: Clear -> dormant\n");
    return;
  }

  if (!strcmp(id->cls, "osobject") && name_is(id, "Cancel")) {
    if (o)
      o->http_state = HTTP_S_CANCELED;
    debugPrintf("JNI HTTP: Cancel -> canceled\n");
    return;
  }

  if (!strcmp(id->cls, "osobject") &&
      (name_is(id, "SetFilePath") || name_is(id, "SetTmpFilePath"))) {
    const char *value = next_str(va);
    if (o) {
      char *dst = name_is(id, "SetFilePath") ? o->http_file_path
                                               : o->http_tmp_file_path;
      strlcpy(dst, value, 256);
    }
    debugPrintf("JNI HTTP: %s(\"%s\")\n", name, value);
    return;
  }

  if (!strcmp(id->cls, "osobject") && name_is(id, "SetAssumedFileSize")) {
    const uint64_t value = va_arg(va, uint64_t);
    if (o)
      o->http_assumed_file_size = value;
    debugPrintf("JNI HTTP: SetAssumedFileSize(%llu)\n",
                (unsigned long long)value);
    return;
  }

  if (!strcmp(id->cls, "osobject") && name_is(id, "SetUserAgent")) {
    debugPrintf("JNI HTTP: SetUserAgent(\"%s\")\n", next_str(va));
    return;
  }

  if (!strcmp(id->cls, "osobject") && name_is(id, "SetContentType")) {
    debugPrintf("JNI HTTP: SetContentType(\"%s\")\n", next_str(va));
    return;
  }

  if (!strcmp(id->cls, "osobject") &&
      (name_is(id, "Close") || name_is(id, "close"))) {
    reset_http_response(o);
    debugPrintf("JNI HTTP: %s -> dormant\n", name);
    return;
  }

  if (!strcmp(id->cls, "osobject") &&
      (name_is(id, "SetTimeoutSec") || name_is(id, "SetAcceptEncoding"))) {
    debugPrintf("JNI HTTP: %s(%d)\n", name, next_int(va));
    return;
  }

  // app-local key/value store (STORAGE_ROOT etc. are written here at boot)
  if (name_is(id, "setAppLocalValue")) {
    const char *key = obj_str(va_arg(va, void *));
    const char *val = obj_str(va_arg(va, void *));
    kv_set(key, val);
    debugPrintf("JNI: setAppLocalValue(%s = %s)\n", key, val);
    return;
  }

  // splash / loading screen: no Java UI, so these are no-ops. hideSplashScreen
  // is the engine's "loading finished" signal.
  if (name_is(id, "showSplashScreen") || name_is(id, "setSplashImage") ||
      name_is(id, "setSplashText")) {
    return;
  }
  if (name_is(id, "hideSplashScreen")) {
    cpu_boost(0);
    jni_frontend_ready = 1;
    debugPrintf("JNI: hideSplashScreen -> frontend ready\n");
    return;
  }

  // The Android KWebDialog owns the actual WebView. There is no Java UI on
  // Switch, but menu::WebView still waits for Java's finish-navigation event
  // before it enables its native checkbox/footer controls. Queue the matching
  // native callback after openWebView returns; this preserves the native user
  // confirmation flow while avoiding a permanent loading spinner.
  if (!strcmp(id->cls, "osobject") && name_is(id, "openWebView")) {
    __atomic_store_n(&webview_finish_navigation_pending, 1,
                     __ATOMIC_RELEASE);
    debugPrintf("JNI: KWebDialog.openWebView -> queue navigation complete\n");
    return;
  }

  // --- async platform operations the engine blocks on until we call back ---
  // The engine stalls in early boot states until these completion callbacks
  // fire; we queue them and the main loop drives the matching impl* entry point.
  if (name_is(id, "playlistOpen")) {
    // report an empty user playlist opened so boot advances
    debugPrintf("JNI: playlistOpen -> queue OnPlaylistOpenComplete(1, 0)\n");
    push_cb(JNI_CB_PLAYLIST_OPEN_COMPLETE, 1, 0);
    return;
  }
  if (name_is(id, "rockstarShowInitial")) {
    debugPrintf("JNI: rockstarShowInitial -> queue OnRockstarInitialComplete\n");
    push_cb(JNI_CB_ROCKSTAR_INITIAL_COMPLETE, 0, 0);
    return;
  }
  if (name_is(id, "rockstarShowGate")) {
    const int gate = next_int(va);
    debugPrintf("JNI: rockstarShowGate(%d) -> queue OnRockstarGateComplete(%d, 1)\n", gate, gate);
    push_cb(JNI_CB_ROCKSTAR_GATE_COMPLETE, gate, 1); // 1 = gate passed
    return;
  }
  if (name_is(id, "rockstarSignIn")) {
    debugPrintf("JNI: rockstarSignIn -> queue OnRockstarSignInComplete\n");
    push_cb(JNI_CB_ROCKSTAR_SIGNIN_COMPLETE, 0, 0);
    return;
  }
  if (name_is(id, "rockstarSignOut")) {
    debugPrintf("JNI: rockstarSignOut -> queue OnRockstarSignOutComplete\n");
    push_cb(JNI_CB_ROCKSTAR_SIGNOUT_COMPLETE, 0, 0);
    return;
  }

  // lifecycle / misc
  if (name_is(id, "finish") || name_is(id, "exitGame") || name_is(id, "quit") ||
      name_is(id, "QuitApp")) {
    debugPrintf("JNI: %s -> request quit\n", name);
    jni_quit_requested = 1;
    return;
  }

  debugPrintf("JNI: CallVoidMethod %s.%s ignored\n", id->cls, name);
}

static juint hal_int(void *obj, const FakeID *id, va_list va) {
  FakeObject *o = fake_object(obj);

  if (!strcmp(id->cls, "osobject") && name_is(id, "SendRequest")) {
    const char *url = obj_str(va_arg(va, void *));
    const char *sign = "";
    FakePriArray *body = NULL;
    int is_post = 0;

    if (!strcmp(id->sig, "(Ljava/lang/String;Ljava/lang/String;[BZ)I")) {
      sign = obj_str(va_arg(va, void *));
      body = va_arg(va, void *);
      is_post = va_arg(va, int);
    } else {
      is_post = va_arg(va, int);
      sign = obj_str(va_arg(va, void *));
      body = va_arg(va, void *);
      (void)va_arg(va, int);
    }
    const int body_len = body && body->tag == TAG_PRIARR ? body->len : 0;

    reset_http_response(o);
    if (!o || !load_http_response(o, url)) {
      if (o)
        o->http_state = HTTP_S_ERROR;
      return (juint)-1;
    }
    o->http_state = HTTP_S_CONNECTING;
    o->http_status_code = 200;
    debugPrintf("JNI HTTP: SendRequest post=%d sign=%s body=%d -> success\n",
                is_post, sign, body_len);
    return 0;
  }

  if (!strcmp(id->cls, "osobject") && name_is(id, "GetState")) {
    if (!o)
      return HTTP_S_DORMANT;
    if (o->http_state == HTTP_S_CONNECTING && o->http_state_polls++ > 0) {
      o->http_state = HTTP_S_COMPLETE;
      debugPrintf("JNI HTTP: state -> complete (%d bytes)\n", o->http_data_len);
    }
    return o->http_state;
  }

  if (!strcmp(id->cls, "osobject") &&
      (name_is(id, "GetCurrentReceiveDataLength") ||
       name_is(id, "GetReceiveDataLength") ||
       name_is(id, "GetReceivedDataLength") ||
       name_is(id, "GetContentLength")))
    return o ? o->http_data_len : 0;

  if (!strcmp(id->cls, "osobject") && name_is(id, "GetStatusCode"))
    return o ? o->http_status_code : 0;

  if (!strcmp(id->cls, "osobject") && name_is(id, "GetLastError"))
    return 0;

  if (!strcmp(id->cls, "osobject") && name_is(id, "GetLogicalProcessorNums"))
    return 4;

  if (!strcmp(id->cls, "osobject") && name_is(id, "show")) {
    debugPrintf("JNI: osobject.show() -> 0\n");
    return 0;
  }
  debugPrintf("JNI: CallIntMethod %s.%s -> 0\n", id->cls, id->name);
  return 0;
}

static juint hal_bool(void *obj, const FakeID *id, va_list va) {
  const char *name = id->name;
  FakeObject *o = fake_object(obj);

  if (!strcmp(id->cls, "jp/konami/SoftwareKeyboard") &&
      name_is(id, "isDone")) {
    debugPrintf("JNI: SoftwareKeyboard.isDone -> %s\n",
                software_keyboard_done ? "true" : "false");
    return software_keyboard_done;
  }

  if (!strcmp(id->cls, "osobject") && name_is(id, "IsEnd")) {
    if (!o)
      return 0;
    if (o->http_state == HTTP_S_CONNECTING && o->http_state_polls++ > 0) {
      o->http_state = HTTP_S_COMPLETE;
      debugPrintf("JNI HTTP: HttpImpl end (%d bytes)\n", o->http_data_len);
    }
    return o->http_state == HTTP_S_COMPLETE;
  }

  if (!strcmp(id->cls, "osobject") && name_is(id, "IsError"))
    return o && o->http_state == HTTP_S_ERROR;

  // no Java splash, so it is never "visible"
  if (name_is(id, "isSplashScreenVisible"))
    return 0;

  // Switch is a console/TV device, not a phone (affects mobile UI scaling)
  if (name_is(id, "isPhone") || name_is(id, "isPhoneDevice"))
    return 0;

  // The runtime data is already present on SD, so Android storage permission is granted.
  if (name_is(id, "PermissionRequestCheck") || name_is(id, "DownloadCheck")) {
    debugPrintf("JNI: CallBooleanMethod %s.%s -> true\n", id->cls, name);
    return 1;
  }

  if (!strcmp(id->cls, "osobject") && name_is(id, "isExistAssetFile")) {
    (void)va_arg(va, void *); // Android Context
    const char *path = next_str(va);
    debugPrintf("JNI: osobject.isExistAssetFile(\"%s\") -> false\n", path);
    return 0;
  }

  debugPrintf("JNI: CallBooleanMethod %s.%s -> false\n", id->cls, name);
  return 0;
}

static float hal_float(const FakeID *id, va_list va) {
  (void)va;
  if (name_is(id, "getDisplayDPI")) {
    debugPrintf("JNI: getDisplayDPI -> 160\n");
    return 160.0f;
  }
  debugPrintf("JNI: CallFloatMethod %s.%s -> 0\n", id->cls, id->name);
  return 0.0f;
}

static void *hal_object(void *obj, const FakeID *id, va_list va) {
  const char *name = id->name;
  FakeObject *o = fake_object(obj);

  if (!strcmp(id->cls, "java/lang/ClassLoader") && name_is(id, "loadClass")) {
    const char *class_name = next_str(va);
    if (!strcmp(class_name, "jp/konami/SoftwareKeyboard")) {
      debugPrintf("JNI: ClassLoader.loadClass(%s) -> software keyboard\n",
                  class_name);
      return jni_make_object(class_name);
    }
    debugPrintf("JNI: ClassLoader.loadClass(%s) -> osobject\n", class_name);
    return jni_make_object("osobject");
  }

  if (!strcmp(id->cls, "jp/konami/SoftwareKeyboard") &&
      name_is(id, "getText")) {
    debugPrintf("JNI: SoftwareKeyboard.getText -> \"%s\"\n",
                software_keyboard_text);
    return jni_make_string(software_keyboard_text);
  }

  if (!strcmp(id->cls, "osobject") &&
      (name_is(id, "GetReceiveData") || name_is(id, "GetReceivedData"))) {
    debugPrintf("JNI HTTP: %s -> %d bytes\n", name, o ? o->http_data_len : 0);
    return jni_make_byte_array(o ? o->http_data : NULL,
                               o ? o->http_data_len : 0);
  }

  if (!strcmp(id->cls, "osobject") && name_is(id, "GetContentEncoding"))
    return jni_make_string("");

  if (name_is(id, "GetManufacturer"))
    return jni_make_string("Nintendo");

  if (name_is(id, "GetModelName"))
    return jni_make_string("Switch");

  if (name_is(id, "GetOSVersion"))
    return jni_make_string("12");

  if (name_is(id, "getCurrentNetworkInfo"))
    return jni_make_string("WIFI");

  const char *return_sig = strrchr(id->sig, ')');
  if (return_sig && !strcmp(return_sig, ")[B")) {
    debugPrintf("JNI: CallObjectMethod %s.%s -> empty byte array\n",
                id->cls, name);
    return jni_make_byte_array(NULL, 0);
  }

  if (name_is(id, "getApplicationDirectory") ||
      name_is(id, "getExternalFilesDirectory") ||
      name_is(id, "getExternalStorageDirectory") ||
      name_is(id, "getDebugDirectory"))
    return jni_make_string(".");

  if (name_is(id, "getCacheDirectory"))
    return jni_make_string("cache");

  if (name_is(id, "getMainExpansionFilePath")) {
    debugPrintf("JNI: getMainExpansionFilePath -> empty (loose PAK)\n");
    return jni_make_string("");
  }

  if (name_is(id, "getPatchExpansionFilePath")) {
    const char *path = "/Android/obb/jp.nyan2021.pesam/"
                       "patch.305030001.jp.nyan2021.pesam.obb";
    debugPrintf("JNI: getPatchExpansionFilePath -> %s\n", path);
    return jni_make_string(path);
  }

  if (name_is(id, "getLocaleCode"))
    return jni_make_string("en_US");

  // STORAGE_ROOT / STORAGE_ROOT_BASE anchor every engine file root; "." points
  // them at the NRO's directory, where data is read and saves are written.
  if (name_is(id, "getAppLocalValue")) {
    const char *key = next_str(va);
    if (!strcmp(key, "STORAGE_ROOT") || !strcmp(key, "STORAGE_ROOT_BASE"))
      return jni_make_string(".");
    const char *v = kv_get(key);
    debugPrintf("JNI: getAppLocalValue(%s) -> %s\n", key, v ? v : "(empty)");
    return jni_make_string(v ? v : "");
  }

  if (name_is(id, "getAppVersion") || name_is(id, "GetVersionName"))
    return jni_make_string("2.11");

  if (name_is(id, "getDeviceLocale") || name_is(id, "GetDeviceLanguage"))
    return jni_make_string("en");

  if (name_is(id, "AndroidThunkJava_GetMetaDataString")) {
    const char *key = next_str(va);
    const char *value = !strcmp(key, "ue4.displaymetrics.dpi")
                            ? "160,160"
                            : "";
    debugPrintf("JNI: AndroidThunkJava_GetMetaDataString(%s) -> %s\n",
                key, value);
    return jni_make_string(value);
  }

  // toImage / getInstance / getParameter / other getters -> a fresh fake obj
  debugPrintf("JNI: CallObjectMethod %s.%s -> fake object\n", id->cls, name);
  return jni_make_object("osobject");
}

// ---------------------------------------------------------------------------
// field reads: sane defaults keyed by field name
// ---------------------------------------------------------------------------

static juint get_boolean_field(const char *name) {
  if (!strcmp(name, "isTvDevice"))     return 1;
  if (!strcmp(name, "hasTouchScreen")) return 1;
  if (!strcmp(name, "hasVibrator"))    return 0;
  return 0;
}

static juint get_int_field(const char *name) {
  if (!strcmp(name, "osVersion"))    return 30;
  if (!strcmp(name, "cpuFrequency")) return 1785;
  return 0;
}

static void *get_object_field(const char *name) {
  if (!strcmp(name, "manufacturer")) return jni_make_string("Nintendo");
  if (!strcmp(name, "model"))        return jni_make_string("Switch");
  if (!strcmp(name, "hardware"))     return jni_make_string("nx");
  if (!strcmp(name, "product"))      return jni_make_string("switch");
  return NULL;
}

// ---------------------------------------------------------------------------
// JNIEnv function table
// ---------------------------------------------------------------------------

static juint j_GetVersion(void *env) { (void)env; return JNI_VERSION_1_6; }

static void *j_FindClass(void *env, const char *name) {
  (void)env;
  debugPrintf("JNI: FindClass(%s)\n", name);
  return jni_make_object(name);
}

static void *j_GetMethodID(void *env, void *cls, const char *name, const char *sig) {
  (void)env;
  debugPrintf("JNI: GetMethodID(%s::%s %s)\n", class_label(cls), name, sig);
  return get_id(class_label(cls), name, sig);
}

static void *j_GetFieldID(void *env, void *cls, const char *name, const char *sig) {
  (void)env;
  return get_id(class_label(cls), name, sig);
}

static void *j_GetObjectClass(void *env, void *obj) {
  (void)env; (void)obj;
  return jni_make_object("class");
}

static void *j_NewGlobalRef(void *env, void *obj) { (void)env; return obj; }
static void *j_NewLocalRef(void *env, void *obj) { (void)env; return obj; }
static juint j_ret0_2(void *env, void *a) { (void)env; (void)a; return 0; }
static juint j_ret0_3(void *env, void *a, void *b) { (void)env; (void)a; (void)b; return 0; }

// --- Call<type>Method ---

static juint j_CallBooleanMethodV(void *env, void *obj, FakeID *id, va_list va) {
  (void)env;
  return hal_bool(obj, id, va);
}
static juint j_CallBooleanMethod(void *env, void *obj, FakeID *id, ...) {
  va_list va; va_start(va, id);
  juint r = hal_bool(obj, id, va);
  va_end(va);
  return r;
}

static juint j_CallIntMethodV(void *env, void *obj, FakeID *id, va_list va) {
  (void)env;
  return hal_int(obj, id, va);
}
static juint j_CallIntMethod(void *env, void *obj, FakeID *id, ...) {
  va_list va; va_start(va, id);
  juint r = hal_int(obj, id, va);
  va_end(va);
  return r;
}

static void *j_CallObjectMethodV(void *env, void *obj, FakeID *id, va_list va) {
  (void)env;
  return hal_object(obj, id, va);
}
static void *j_CallObjectMethod(void *env, void *obj, FakeID *id, ...) {
  va_list va; va_start(va, id);
  void *r = hal_object(obj, id, va);
  va_end(va);
  return r;
}

static void j_CallVoidMethodV(void *env, void *obj, FakeID *id, va_list va) {
  (void)env;
  hal_void(obj, id, va);
}
static void j_CallVoidMethod(void *env, void *obj, FakeID *id, ...) {
  va_list va; va_start(va, id);
  hal_void(obj, id, va);
  va_end(va);
}

static float j_CallFloatMethodV(void *env, void *obj, FakeID *id, va_list va) {
  (void)env; (void)obj;
  return hal_float(id, va);
}
static float j_CallFloatMethod(void *env, void *obj, FakeID *id, ...) {
  va_list va; va_start(va, id);
  float r = hal_float(id, va);
  va_end(va);
  return r;
}

static juint j_CallLongMethodV(void *env, void *obj, FakeID *id, va_list va) {
  (void)env; (void)obj; (void)va;
  debugPrintf("JNI: CallLongMethod %s.%s -> 0\n", id->cls, id->name);
  return 0;
}

// static variants share the dispatchers (the receiver doesn't matter)
static void *j_CallStaticObjectMethodV(void *env, void *cls, FakeID *id, va_list va) {
  (void)env;
  return hal_object(cls, id, va);
}
static void *j_CallStaticObjectMethod(void *env, void *cls, FakeID *id, ...) {
  va_list va; va_start(va, id);
  void *r = hal_object(cls, id, va);
  va_end(va);
  return r;
}
static juint j_CallStaticBooleanMethodV(void *env, void *cls, FakeID *id, va_list va) {
  (void)env;
  return hal_bool(cls, id, va);
}
static juint j_CallStaticBooleanMethod(void *env, void *cls, FakeID *id, ...) {
  va_list va; va_start(va, id);
  juint r = hal_bool(cls, id, va);
  va_end(va);
  return r;
}
static juint j_CallStaticIntMethodV(void *env, void *cls, FakeID *id, va_list va) {
  (void)env;
  return hal_int(cls, id, va);
}
static juint j_CallStaticIntMethod(void *env, void *cls, FakeID *id, ...) {
  va_list va; va_start(va, id);
  juint r = hal_int(cls, id, va);
  va_end(va);
  return r;
}
static void j_CallStaticVoidMethodV(void *env, void *cls, FakeID *id, va_list va) {
  (void)env;
  hal_void(cls, id, va);
}
static void j_CallStaticVoidMethod(void *env, void *cls, FakeID *id, ...) {
  va_list va; va_start(va, id);
  hal_void(cls, id, va);
  va_end(va);
}
static float j_CallStaticFloatMethodV(void *env, void *cls, FakeID *id, va_list va) {
  (void)env; (void)cls;
  return hal_float(id, va);
}
static float j_CallStaticFloatMethod(void *env, void *cls, FakeID *id, ...) {
  va_list va; va_start(va, id);
  float r = hal_float(id, va);
  va_end(va);
  return r;
}

static void *j_NewObjectV(void *env, void *cls, FakeID *id, va_list va) {
  (void)env; (void)id; (void)va;
  return jni_make_object(class_label(cls));
}
static void *j_NewObject(void *env, void *cls, FakeID *id, ...) {
  va_list va; va_start(va, id);
  void *r = j_NewObjectV(env, cls, id, va);
  va_end(va);
  return r;
}

// --- fields ---

static void *j_GetObjectField(void *env, void *obj, FakeID *id) {
  (void)env; (void)obj;
  return get_object_field(id->name);
}
static juint j_GetBooleanField(void *env, void *obj, FakeID *id) {
  (void)env; (void)obj;
  return get_boolean_field(id->name);
}
static juint j_GetIntField(void *env, void *obj, FakeID *id) {
  (void)env; (void)obj;
  return get_int_field(id->name);
}
static juint j_GetLongField(void *env, void *obj, FakeID *id) {
  (void)env; (void)obj; (void)id;
  return 0;
}
static float j_GetFloatField(void *env, void *obj, FakeID *id) {
  (void)env; (void)obj; (void)id;
  return 0.0f;
}

// --- strings ---

static void *j_NewStringUTF(void *env, const char *utf) {
  (void)env;
  return jni_make_string(utf);
}

static const char *j_GetStringUTFChars(void *env, void *jstr, uint8_t *is_copy) {
  (void)env;
  set_is_copy(is_copy, 0);
  return obj_str(jstr);
}

static void j_ReleaseStringUTFChars(void *env, void *jstr, const char *utf) {
  (void)env; (void)jstr; (void)utf;
}

static juint j_GetStringUTFLength(void *env, void *jstr) {
  (void)env;
  return strlen(obj_str(jstr));
}

static juint j_GetStringLength(void *env, void *jstr) {
  (void)env;
  return strlen(obj_str(jstr));
}

static const uint16_t *j_GetStringChars(void *env, void *jstr, uint8_t *is_copy) {
  (void)env;
  set_is_copy(is_copy, 1);
  const char *utf = obj_str(jstr);
  const int len = strlen(utf);
  uint16_t *out = calloc(len + 1, sizeof(uint16_t));
  for (int i = 0; i < len; i++)
    out[i] = (uint8_t)utf[i];
  return out;
}

static void j_ReleaseStringChars(void *env, void *jstr, const uint16_t *chars) {
  (void)env; (void)jstr;
  free((void *)chars);
}

// --- arrays ---

static juint j_GetArrayLength(void *env, void *arr) {
  (void)env;
  FakeObjArray *a = arr;
  if (a && (a->tag == TAG_OBJARR || a->tag == TAG_PRIARR))
    return a->len;
  return 0;
}

static void *j_GetObjectArrayElement(void *env, void *arr, int idx) {
  (void)env;
  FakeObjArray *a = arr;
  if (a && a->tag == TAG_OBJARR && idx >= 0 && idx < a->len)
    return a->items[idx];
  return jni_make_string("");
}

static void j_SetObjectArrayElement(void *env, void *arr, int idx, void *val) {
  (void)env;
  FakeObjArray *a = arr;
  if (a && a->tag == TAG_OBJARR && idx >= 0 && idx < a->len)
    a->items[idx] = val;
}

static void *j_NewObjectArray(void *env, int len, void *cls, void *init) {
  (void)env; (void)cls;
  FakeObjArray *a = calloc(1, sizeof(*a));
  a->tag = TAG_OBJARR;
  a->len = len;
  a->items = calloc(len ? len : 1, sizeof(void *));
  for (int i = 0; i < len; i++)
    a->items[i] = init;
  return a;
}

static void *new_pri_array(int len, int elem_size) {
  FakePriArray *a = calloc(1, sizeof(*a));
  a->tag = TAG_PRIARR;
  a->len = len;
  a->elem_size = elem_size;
  a->data = calloc(len ? len : 1, elem_size);
  return a;
}

static void *j_NewByteArray(void *env, int len)  { (void)env; return new_pri_array(len, 1); }
static void *j_NewIntArray(void *env, int len)   { (void)env; return new_pri_array(len, 4); }
static void *j_NewFloatArray(void *env, int len) { (void)env; return new_pri_array(len, 4); }

static void *j_GetPriArrayElements(void *env, void *arr, uint8_t *is_copy) {
  (void)env;
  set_is_copy(is_copy, 0);
  FakePriArray *a = arr;
  if (a && a->tag == TAG_PRIARR)
    return a->data;
  return NULL;
}

static void j_ReleasePriArrayElements(void *env, void *arr, void *elems, int mode) {
  (void)env; (void)arr; (void)elems; (void)mode;
}

static void j_GetPriArrayRegion(void *env, void *arr, int start, int len, void *buf) {
  (void)env;
  FakePriArray *a = arr;
  if (a && a->tag == TAG_PRIARR && start >= 0 && start + len <= a->len)
    memcpy(buf, (char *)a->data + start * a->elem_size, len * a->elem_size);
}

static void j_SetPriArrayRegion(void *env, void *arr, int start, int len, const void *buf) {
  (void)env;
  FakePriArray *a = arr;
  if (a && a->tag == TAG_PRIARR && start >= 0 && start + len <= a->len)
    memcpy((char *)a->data + start * a->elem_size, buf, len * a->elem_size);
}

// --- misc ---

static juint j_RegisterNatives(void *env, void *cls, void *methods, int n) {
  (void)env; (void)cls; (void)methods;
  debugPrintf("JNI: RegisterNatives(%d methods) ignored\n", n);
  return 0;
}

static juint j_GetJavaVM(void *env, void **vm) {
  (void)env;
  *vm = fake_vm;
  return JNI_OK;
}

static juint j_ExceptionCheck(void *env) { (void)env; return 0; }
static void *j_ExceptionOccurred(void *env) { (void)env; return NULL; }
static void j_ExceptionClearDescribe(void *env) { (void)env; }
static void j_DeleteRef(void *env, void *obj) { (void)env; (void)obj; }
static juint j_PushLocalFrame(void *env, int cap) { (void)env; (void)cap; return 0; }
static void *j_PopLocalFrame(void *env, void *result) { (void)env; return result; }

static juint j_unimplemented(void) {
  debugPrintf("JNI: call to unimplemented function slot\n");
  return 0;
}

// ---------------------------------------------------------------------------
// table assembly (indices per the JNI specification)
// ---------------------------------------------------------------------------

static void *env_table[233];
static void **env_table_ptr = env_table;
void *fake_env = &env_table_ptr;

static juint vm_DestroyJavaVM(void *vm) { (void)vm; return JNI_OK; }
static juint vm_AttachCurrentThread(void *vm, void **env, void *args) {
  (void)vm; (void)args;
  if (env) *env = fake_env;
  return JNI_OK;
}
static juint vm_DetachCurrentThread(void *vm) { (void)vm; return JNI_OK; }
static juint vm_GetEnv(void *vm, void **env, int version) {
  (void)vm; (void)version;
  if (env) *env = fake_env;
  return JNI_OK;
}

static void *vm_table[8];
static void **vm_table_ptr = vm_table;
void *fake_vm = &vm_table_ptr;

void jni_init(void) {
  kv_load();

  for (int i = 0; i < 233; i++)
    env_table[i] = (void *)j_unimplemented;

  env_table[4]  = (void *)j_GetVersion;
  env_table[6]  = (void *)j_FindClass;
  env_table[15] = (void *)j_ExceptionOccurred;
  env_table[16] = (void *)j_ExceptionClearDescribe; // ExceptionDescribe
  env_table[17] = (void *)j_ExceptionClearDescribe; // ExceptionClear
  env_table[19] = (void *)j_PushLocalFrame;
  env_table[20] = (void *)j_PopLocalFrame;
  env_table[21] = (void *)j_NewGlobalRef;
  env_table[22] = (void *)j_DeleteRef;  // DeleteGlobalRef
  env_table[23] = (void *)j_DeleteRef;  // DeleteLocalRef
  env_table[24] = (void *)j_ret0_3;     // IsSameObject
  env_table[25] = (void *)j_NewLocalRef;
  env_table[26] = (void *)j_ret0_2;     // EnsureLocalCapacity
  env_table[28] = (void *)j_NewObject;
  env_table[29] = (void *)j_NewObjectV;
  env_table[31] = (void *)j_GetObjectClass;
  env_table[33] = (void *)j_GetMethodID;
  env_table[34] = (void *)j_CallObjectMethod;
  env_table[35] = (void *)j_CallObjectMethodV;
  env_table[37] = (void *)j_CallBooleanMethod;
  env_table[38] = (void *)j_CallBooleanMethodV;
  env_table[49] = (void *)j_CallIntMethod;
  env_table[50] = (void *)j_CallIntMethodV;
  env_table[53] = (void *)j_CallLongMethodV;
  env_table[55] = (void *)j_CallFloatMethod;
  env_table[56] = (void *)j_CallFloatMethodV;
  env_table[61] = (void *)j_CallVoidMethod;
  env_table[62] = (void *)j_CallVoidMethodV;
  env_table[94] = (void *)j_GetFieldID;
  env_table[95] = (void *)j_GetObjectField;
  env_table[96] = (void *)j_GetBooleanField;
  env_table[100] = (void *)j_GetIntField;
  env_table[101] = (void *)j_GetLongField;
  env_table[102] = (void *)j_GetFloatField;
  env_table[113] = (void *)j_GetMethodID;               // GetStaticMethodID
  env_table[114] = (void *)j_CallStaticObjectMethod;
  env_table[115] = (void *)j_CallStaticObjectMethodV;
  env_table[117] = (void *)j_CallStaticBooleanMethod;
  env_table[118] = (void *)j_CallStaticBooleanMethodV;
  env_table[129] = (void *)j_CallStaticIntMethod;
  env_table[130] = (void *)j_CallStaticIntMethodV;
  env_table[135] = (void *)j_CallStaticFloatMethod;   // s0 must be set for float returns
  env_table[136] = (void *)j_CallStaticFloatMethodV;
  env_table[141] = (void *)j_CallStaticVoidMethod;
  env_table[142] = (void *)j_CallStaticVoidMethodV;
  env_table[144] = (void *)j_GetFieldID;                // GetStaticFieldID
  env_table[145] = (void *)j_GetObjectField;            // GetStaticObjectField
  env_table[146] = (void *)j_GetBooleanField;           // GetStaticBooleanField
  env_table[150] = (void *)j_GetIntField;               // GetStaticIntField
  env_table[164] = (void *)j_GetStringLength;
  env_table[165] = (void *)j_GetStringChars;
  env_table[166] = (void *)j_ReleaseStringChars;
  env_table[167] = (void *)j_NewStringUTF;
  env_table[168] = (void *)j_GetStringUTFLength;
  env_table[169] = (void *)j_GetStringUTFChars;
  env_table[170] = (void *)j_ReleaseStringUTFChars;
  env_table[171] = (void *)j_GetArrayLength;
  env_table[172] = (void *)j_NewObjectArray;
  env_table[173] = (void *)j_GetObjectArrayElement;
  env_table[174] = (void *)j_SetObjectArrayElement;
  env_table[176] = (void *)j_NewByteArray;
  env_table[179] = (void *)j_NewIntArray;
  env_table[181] = (void *)j_NewFloatArray;
  env_table[183] = (void *)j_GetPriArrayElements; // boolean
  env_table[184] = (void *)j_GetPriArrayElements; // byte
  env_table[185] = (void *)j_GetPriArrayElements; // char
  env_table[186] = (void *)j_GetPriArrayElements; // short
  env_table[187] = (void *)j_GetPriArrayElements; // int
  env_table[188] = (void *)j_GetPriArrayElements; // long
  env_table[189] = (void *)j_GetPriArrayElements; // float
  env_table[190] = (void *)j_GetPriArrayElements; // double
  for (int i = 191; i <= 198; i++)
    env_table[i] = (void *)j_ReleasePriArrayElements;
  for (int i = 199; i <= 206; i++)
    env_table[i] = (void *)j_GetPriArrayRegion;
  for (int i = 207; i <= 214; i++)
    env_table[i] = (void *)j_SetPriArrayRegion;
  env_table[215] = (void *)j_RegisterNatives;
  env_table[216] = (void *)j_ret0_2;    // UnregisterNatives
  env_table[217] = (void *)j_ret0_2;    // MonitorEnter
  env_table[218] = (void *)j_ret0_2;    // MonitorExit
  env_table[219] = (void *)j_GetJavaVM;
  env_table[222] = (void *)j_GetPriArrayElements;     // GetPrimitiveArrayCritical
  env_table[223] = (void *)j_ReleasePriArrayElements; // ReleasePrimitiveArrayCritical
  env_table[226] = (void *)j_NewGlobalRef; // NewWeakGlobalRef
  env_table[227] = (void *)j_DeleteRef;    // DeleteWeakGlobalRef
  env_table[228] = (void *)j_ExceptionCheck;

  vm_table[3] = (void *)vm_DestroyJavaVM;
  vm_table[4] = (void *)vm_AttachCurrentThread;
  vm_table[5] = (void *)vm_DetachCurrentThread;
  vm_table[6] = (void *)vm_GetEnv;
  vm_table[7] = (void *)vm_AttachCurrentThread; // AttachCurrentThreadAsDaemon

  debugPrintf("JNI: fake environment initialized (env=%p vm=%p)\n", fake_env, fake_vm);
}
