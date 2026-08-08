#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <math.h>
#include <poll.h>
#include <pthread.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/statvfs.h>
#include <time.h>
#include <unistd.h>

#include <switch.h>

#include "android_shim.h"
#include "config.h"
#include "error.h"
#include "imports.h"
#include "jni_fake.h"
#include "libc_shim.h"
#include "util.h"

#define AINPUT_EVENT_TYPE_KEY 1
#define AINPUT_EVENT_TYPE_MOTION 2
#define AKEY_EVENT_ACTION_DOWN 0
#define AKEY_EVENT_ACTION_UP 1
#define AMOTION_EVENT_ACTION_DOWN 0
#define AMOTION_EVENT_ACTION_UP 1
#define AMOTION_EVENT_ACTION_MOVE 2
#define AINPUT_SOURCE_KEYBOARD 0x00000101
#define AINPUT_SOURCE_GAMEPAD 0x00000401
#define AINPUT_SOURCE_TOUCHSCREEN 0x00001002
#define ALOOPER_EVENT_INPUT 1
#define ALOOPER_POLL_WAKE -1
#define ALOOPER_POLL_CALLBACK -2
#define ALOOPER_POLL_TIMEOUT -3
#define ALOOPER_POLL_ERROR -4

typedef struct ANativeActivity ANativeActivity;

typedef struct {
  void (*onStart)(ANativeActivity *activity);
  void (*onResume)(ANativeActivity *activity);
  void *(*onSaveInstanceState)(ANativeActivity *activity, size_t *out_size);
  void (*onPause)(ANativeActivity *activity);
  void (*onStop)(ANativeActivity *activity);
  void (*onDestroy)(ANativeActivity *activity);
  void (*onWindowFocusChanged)(ANativeActivity *activity, int focused);
  void (*onNativeWindowCreated)(ANativeActivity *activity, void *window);
  void (*onNativeWindowResized)(ANativeActivity *activity, void *window);
  void (*onNativeWindowRedrawNeeded)(ANativeActivity *activity, void *window);
  void (*onNativeWindowDestroyed)(ANativeActivity *activity, void *window);
  void (*onInputQueueCreated)(ANativeActivity *activity, void *queue);
  void (*onInputQueueDestroyed)(ANativeActivity *activity, void *queue);
  void (*onContentRectChanged)(ANativeActivity *activity, const void *rect);
  void (*onConfigurationChanged)(ANativeActivity *activity);
  void (*onLowMemory)(ANativeActivity *activity);
} ANativeActivityCallbacks;

struct ANativeActivity {
  ANativeActivityCallbacks *callbacks;
  void *vm;
  void *env;
  void *clazz;
  const char *internalDataPath;
  const char *externalDataPath;
  int32_t sdkVersion;
  void *instance;
  void *assetManager;
  const char *obbPath;
};

typedef struct {
  int fd;
  int ident;
  int events;
  int (*callback)(int, int, void *);
  void *data;
} FakeLooperFd;

typedef struct {
  FakeLooperFd fds[8];
  int count;
} FakeLooper;

typedef struct {
  int type;
  int device_id;
  int source;
  int action;
  int flags;
  int keycode;
  int meta_state;
  int button_state;
  int pointer_id;
  float x;
  float y;
} FakeInputEvent;

typedef struct {
  pthread_mutex_t mutex;
  FakeInputEvent *events[64];
  unsigned int head;
  unsigned int tail;
  int pipe_fd[2];
  FakeLooper *looper;
} FakeInputQueue;

static _Thread_local FakeLooper tls_looper;
static FakeInputQueue input_queue;
static ANativeActivity activity;
static ANativeActivityCallbacks activity_callbacks;
static u64 previous_buttons;
static int previous_touch_active;
static int previous_touch_id;
static float previous_touch_x;
static float previous_touch_y;

#define FAKE_PIPE_BASE 0x70000000
#define FAKE_PIPE_COUNT 32
#define FAKE_PIPE_CAPACITY 4096

typedef struct {
  int used;
  int read_open;
  int write_open;
  int flags;
  pthread_mutex_t mutex;
  unsigned char bytes[FAKE_PIPE_CAPACITY];
  size_t head;
  size_t count;
} FakePipe;

static FakePipe fake_pipes[FAKE_PIPE_COUNT];
static pthread_mutex_t fake_pipe_table_mutex = PTHREAD_MUTEX_INITIALIZER;
static int close_epoll_fd(int fd);

static FakePipe *fake_pipe_for_fd(int fd, int *write_end) {
  const int index = (fd - FAKE_PIPE_BASE) / 2;
  if (fd < FAKE_PIPE_BASE || index < 0 || index >= FAKE_PIPE_COUNT)
    return NULL;
  FakePipe *pipe = &fake_pipes[index];
  if (!pipe->used)
    return NULL;
  if (write_end)
    *write_end = (fd - FAKE_PIPE_BASE) & 1;
  return pipe;
}

int pipe_fake(int pipefd[2]) {
  if (!pipefd) {
    errno = EFAULT;
    return -1;
  }
  pthread_mutex_lock(&fake_pipe_table_mutex);
  for (int i = 0; i < FAKE_PIPE_COUNT; i++) {
    FakePipe *pipe = &fake_pipes[i];
    if (pipe->used)
      continue;
    memset(pipe, 0, sizeof(*pipe));
    pthread_mutex_init(&pipe->mutex, NULL);
    pipe->used = 1;
    pipe->read_open = 1;
    pipe->write_open = 1;
    pipefd[0] = FAKE_PIPE_BASE + i * 2;
    pipefd[1] = pipefd[0] + 1;
    pthread_mutex_unlock(&fake_pipe_table_mutex);
    return 0;
  }
  pthread_mutex_unlock(&fake_pipe_table_mutex);
  errno = EMFILE;
  return -1;
}

ssize_t read_dispatch_fake(int fd, void *buf, size_t count) {
  if (fd == FAKE_URANDOM_FD) {
    if (!buf && count) {
      errno = EFAULT;
      return -1;
    }
    randomGet(buf, count);
    return (ssize_t)count;
  }
  int write_end = 0;
  FakePipe *pipe = fake_pipe_for_fd(fd, &write_end);
  if (!pipe)
    return read(fd, buf, count);
  if (write_end || !pipe->read_open) {
    errno = EBADF;
    return -1;
  }

  pthread_mutex_lock(&pipe->mutex);
  if (!pipe->count) {
    const int writer_closed = !pipe->write_open;
    pthread_mutex_unlock(&pipe->mutex);
    if (writer_closed)
      return 0;
    errno = EAGAIN;
    return -1;
  }
  if (count > pipe->count)
    count = pipe->count;
  for (size_t i = 0; i < count; i++)
    ((unsigned char *)buf)[i] =
        pipe->bytes[(pipe->head + i) % FAKE_PIPE_CAPACITY];
  pipe->head = (pipe->head + count) % FAKE_PIPE_CAPACITY;
  pipe->count -= count;
  pthread_mutex_unlock(&pipe->mutex);
  return (ssize_t)count;
}

ssize_t write_dispatch_fake(int fd, const void *buf, size_t count) {
  int write_end = 0;
  FakePipe *pipe = fake_pipe_for_fd(fd, &write_end);
  if (!pipe)
    return write(fd, buf, count);
  if (!write_end || !pipe->write_open || !pipe->read_open) {
    errno = EPIPE;
    return -1;
  }

  pthread_mutex_lock(&pipe->mutex);
  const size_t available = FAKE_PIPE_CAPACITY - pipe->count;
  if (count > available)
    count = available;
  for (size_t i = 0; i < count; i++)
    pipe->bytes[(pipe->head + pipe->count + i) % FAKE_PIPE_CAPACITY] =
        ((const unsigned char *)buf)[i];
  pipe->count += count;
  pthread_mutex_unlock(&pipe->mutex);
  if (!count) {
    errno = EAGAIN;
    return -1;
  }
  return (ssize_t)count;
}

int close_dispatch_fake(int fd) {
  if (fd == FAKE_URANDOM_FD)
    return 0;
  int write_end = 0;
  FakePipe *pipe = fake_pipe_for_fd(fd, &write_end);
  if (!pipe)
    return close_epoll_fd(fd) ? 0 : close(fd);

  pthread_mutex_lock(&pipe->mutex);
  if (write_end)
    pipe->write_open = 0;
  else
    pipe->read_open = 0;
  const int release = !pipe->read_open && !pipe->write_open;
  pthread_mutex_unlock(&pipe->mutex);
  if (release) {
    pthread_mutex_lock(&fake_pipe_table_mutex);
    pthread_mutex_destroy(&pipe->mutex);
    memset(pipe, 0, sizeof(*pipe));
    pthread_mutex_unlock(&fake_pipe_table_mutex);
  }
  return 0;
}

int fcntl_dispatch_fake(int fd, int cmd, ...) {
  int write_end = 0;
  FakePipe *pipe = fake_pipe_for_fd(fd, &write_end);
  if (pipe) {
    if (cmd == F_GETFL)
      return pipe->flags;
    if (cmd == F_GETFD)
      return 0;
    va_list args;
    va_start(args, cmd);
    const int value = va_arg(args, int);
    va_end(args);
    if (cmd == F_SETFL) {
      pipe->flags = value;
      return 0;
    }
    if (cmd == F_SETFD)
      return 0;
    errno = EINVAL;
    return -1;
  }

  if (cmd == F_GETFL || cmd == F_GETFD)
    return fcntl_fake(fd, cmd);
  va_list args;
  va_start(args, cmd);
  const int value = va_arg(args, int);
  va_end(args);
  return fcntl_fake(fd, cmd, value);
}

static int poll_fake_pipes(struct pollfd *fds, nfds_t nfds) {
  int ready = 0;
  for (nfds_t i = 0; i < nfds; i++) {
    int write_end = 0;
    FakePipe *pipe = fake_pipe_for_fd(fds[i].fd, &write_end);
    if (!pipe)
      continue;
    fds[i].revents = 0;
    pthread_mutex_lock(&pipe->mutex);
    if (!write_end && (fds[i].events & POLLIN) && pipe->count)
      fds[i].revents |= POLLIN;
    if (write_end && (fds[i].events & POLLOUT) &&
        pipe->count < FAKE_PIPE_CAPACITY && pipe->read_open)
      fds[i].revents |= POLLOUT;
    if ((!write_end && !pipe->write_open) || (write_end && !pipe->read_open))
      fds[i].revents |= POLLHUP;
    pthread_mutex_unlock(&pipe->mutex);
    if (fds[i].revents)
      ready++;
  }
  return ready;
}

int poll_dispatch_fake(void *fds_ptr, unsigned long nfds_value, int timeout_ms) {
  struct pollfd *fds = fds_ptr;
  const nfds_t nfds = (nfds_t)nfds_value;
  struct pollfd *native = calloc(nfds ? nfds : 1, sizeof(*native));
  if (!native) {
    errno = ENOMEM;
    return -1;
  }

  int elapsed = 0;
  for (;;) {
    nfds_t native_count = 0;
    for (nfds_t i = 0; i < nfds; i++) {
      fds[i].revents = 0;
      if (fds[i].fd < 0 || fake_pipe_for_fd(fds[i].fd, NULL))
        continue;
      native[native_count] = fds[i];
      native[native_count].revents = 0;
      native_count++;
    }
    int ready = native_count ? poll(native, native_count, 0) : 0;
    if (ready < 0) {
      free(native);
      return -1;
    }
    nfds_t native_index = 0;
    for (nfds_t i = 0; i < nfds; i++) {
      if (fds[i].fd < 0 || fake_pipe_for_fd(fds[i].fd, NULL))
        continue;
      fds[i].revents = native[native_index++].revents;
    }
    ready += poll_fake_pipes(fds, nfds);
    if (ready || timeout_ms == 0 || (timeout_ms > 0 && elapsed >= timeout_ms)) {
      free(native);
      return ready;
    }
    svcSleepThread(1000000LL);
    elapsed++;
  }
}

ssize_t readv_fake(int fd, const void *iov_ptr, int iov_count) {
  const struct iovec *iov = iov_ptr;
  ssize_t total = 0;
  for (int i = 0; i < iov_count; i++) {
    const ssize_t result =
        read_dispatch_fake(fd, iov[i].iov_base, iov[i].iov_len);
    if (result < 0)
      return total ? total : result;
    total += result;
    if ((size_t)result < iov[i].iov_len)
      break;
  }
  return total;
}

ssize_t writev_fake(int fd, const void *iov_ptr, int iov_count) {
  const struct iovec *iov = iov_ptr;
  ssize_t total = 0;
  for (int i = 0; i < iov_count; i++) {
    const ssize_t result =
        write_dispatch_fake(fd, iov[i].iov_base, iov[i].iov_len);
    if (result < 0)
      return total ? total : result;
    total += result;
    if ((size_t)result < iov[i].iov_len)
      break;
  }
  return total;
}

static void input_queue_init(void) {
  memset(&input_queue, 0, sizeof(input_queue));
  pthread_mutex_init(&input_queue.mutex, NULL);
  if (pipe_fake(input_queue.pipe_fd) < 0)
    fatal_error("Could not create Android input pipe.");
  fcntl_dispatch_fake(input_queue.pipe_fd[0], F_SETFL, O_NONBLOCK);
  fcntl_dispatch_fake(input_queue.pipe_fd[1], F_SETFL, O_NONBLOCK);
}

static void input_queue_push(FakeInputEvent *event) {
  pthread_mutex_lock(&input_queue.mutex);
  const unsigned int next = (input_queue.tail + 1) % 64;
  if (next != input_queue.head) {
    input_queue.events[input_queue.tail] = event;
    input_queue.tail = next;
    const uint8_t wake = 1;
    (void)write_dispatch_fake(input_queue.pipe_fd[1], &wake, sizeof(wake));
    event = NULL;
  }
  pthread_mutex_unlock(&input_queue.mutex);
  free(event);
}

static void push_key(int keycode, int action) {
  FakeInputEvent *event = calloc(1, sizeof(*event));
  if (!event)
    return;
  event->type = AINPUT_EVENT_TYPE_KEY;
  event->device_id = 1;
  event->source = AINPUT_SOURCE_GAMEPAD;
  event->action = action;
  event->keycode = keycode;
  input_queue_push(event);
}

static void push_motion(int action, int pointer_id, float x, float y) {
  FakeInputEvent *event = calloc(1, sizeof(*event));
  if (!event)
    return;
  event->type = AINPUT_EVENT_TYPE_MOTION;
  event->device_id = 0;
  event->source = AINPUT_SOURCE_TOUCHSCREEN;
  event->action = action;
  event->pointer_id = pointer_id;
  event->x = x;
  event->y = y;
  input_queue_push(event);
}

void android_input_poll(void) {
  static const struct {
    u64 button;
    int keycode;
  } map[] = {
    { HidNpadButton_B, 96 }, { HidNpadButton_A, 97 },
    { HidNpadButton_Y, 99 }, { HidNpadButton_X, 100 },
    { HidNpadButton_L, 102 }, { HidNpadButton_R, 103 },
    { HidNpadButton_ZL, 104 }, { HidNpadButton_ZR, 105 },
    { HidNpadButton_StickL, 106 }, { HidNpadButton_StickR, 107 },
    { HidNpadButton_Plus, 108 }, { HidNpadButton_Minus, 109 },
    { HidNpadButton_Up, 19 }, { HidNpadButton_Down, 20 },
    { HidNpadButton_Left, 21 }, { HidNpadButton_Right, 22 },
  };

  // libnx aborts inside padUpdate when HID has already been torn down by a
  // game-side exit request. Read the valid shared-memory slots directly and
  // treat unavailable HID as no input so the original shutdown cause survives.
  if (!hidGetSharedmemAddr()) {
    static int warned;
    if (!warned++)
      debugPrintf("input: HID shared memory unavailable; polling disabled\n");
    previous_buttons = 0;
    previous_touch_active = 0;
    return;
  }

  static int touch_initialized;
  if (!touch_initialized) {
    hidInitializeTouchScreen();
    touch_initialized = 1;
    debugPrintf("input: touchscreen polling initialized\n");
  }

  HidNpadCommonState state;
  u64 buttons = 0;
  if (hidGetNpadStatesFullKey(HidNpadIdType_No1, &state, 1) &&
      (state.attributes & HidNpadAttribute_IsConnected))
    buttons |= state.buttons;
  if (hidGetNpadStatesJoyDual(HidNpadIdType_No1, &state, 1) &&
      (state.attributes & HidNpadAttribute_IsConnected))
    buttons |= state.buttons;
  if (hidGetNpadStatesJoyLeft(HidNpadIdType_No1, &state, 1) &&
      (state.attributes & HidNpadAttribute_IsConnected))
    buttons |= state.buttons;
  if (hidGetNpadStatesJoyRight(HidNpadIdType_No1, &state, 1) &&
      (state.attributes & HidNpadAttribute_IsConnected))
    buttons |= state.buttons;
  if (hidGetNpadStatesHandheld(HidNpadIdType_Handheld, &state, 1) &&
      (state.attributes & HidNpadAttribute_IsConnected))
    buttons |= state.buttons;
  const u64 changed = buttons ^ previous_buttons;
  for (unsigned int i = 0; i < sizeof(map) / sizeof(map[0]); i++) {
    if (changed & map[i].button)
      push_key(map[i].keycode,
               (buttons & map[i].button) ? AKEY_EVENT_ACTION_DOWN
                                         : AKEY_EVENT_ACTION_UP);
  }
  previous_buttons = buttons;

  HidTouchScreenState touch_state;
  memset(&touch_state, 0, sizeof(touch_state));
  const int has_touch = hidGetTouchScreenStates(&touch_state, 1) > 0 &&
                        touch_state.count > 0;
  const HidTouchState *touch = has_touch ? &touch_state.touches[0] : NULL;
  const int ended = touch && (touch->attributes & HidTouchAttribute_End);
  const int active = has_touch && !ended;
  const float x = touch ? (float)touch->x * (float)screen_width / 1280.0f
                        : previous_touch_x;
  const float y = touch ? (float)touch->y * (float)screen_height / 720.0f
                        : previous_touch_y;
  const int pointer_id = touch ? (int)touch->finger_id : previous_touch_id;

  if (active && !previous_touch_active) {
    push_motion(AMOTION_EVENT_ACTION_DOWN, pointer_id, x, y);
    debugPrintf("input: touch down raw=%u,%u android=%.1f,%.1f\n",
                touch->x, touch->y, x, y);
  } else if (active &&
             (x != previous_touch_x || y != previous_touch_y)) {
    push_motion(AMOTION_EVENT_ACTION_MOVE, pointer_id, x, y);
  } else if (!active && previous_touch_active) {
    push_motion(AMOTION_EVENT_ACTION_UP, pointer_id, x, y);
    debugPrintf("input: touch up android=%.1f,%.1f\n", x, y);
  }

  previous_touch_active = active;
  previous_touch_id = pointer_id;
  previous_touch_x = x;
  previous_touch_y = y;
}

void *ALooper_prepare_fake(int opts) {
  (void)opts;
  return &tls_looper;
}

int ALooper_addFd_fake(void *looper_ptr, int fd, int ident, int events,
                       int (*callback)(int, int, void *), void *data) {
  FakeLooper *looper = looper_ptr ? looper_ptr : &tls_looper;
  for (int i = 0; i < looper->count; i++) {
    if (looper->fds[i].fd == fd) {
      looper->fds[i] = (FakeLooperFd){fd, ident, events, callback, data};
      return 1;
    }
  }
  if (looper->count >= (int)(sizeof(looper->fds) / sizeof(looper->fds[0])))
    return -1;
  looper->fds[looper->count++] =
      (FakeLooperFd){fd, ident, events, callback, data};
  return 1;
}

int ALooper_pollAll_fake(int timeout_ms, int *out_fd, int *out_events,
                         void **out_data) {
  FakeLooper *looper = &tls_looper;
  if (looper->count == 0) {
    if (timeout_ms > 0)
      svcSleepThread((int64_t)timeout_ms * 1000000LL);
    return ALOOPER_POLL_TIMEOUT;
  }

  struct pollfd poll_fds[8];
  for (int i = 0; i < looper->count; i++) {
    poll_fds[i].fd = looper->fds[i].fd;
    poll_fds[i].events = POLLIN;
    poll_fds[i].revents = 0;
  }
  const int rc = poll_dispatch_fake(poll_fds, looper->count, timeout_ms);
  if (rc == 0)
    return ALOOPER_POLL_TIMEOUT;
  if (rc < 0)
    return errno == EINTR ? ALOOPER_POLL_WAKE : ALOOPER_POLL_ERROR;

  for (int i = 0; i < looper->count; i++) {
    if (!poll_fds[i].revents)
      continue;
    FakeLooperFd *entry = &looper->fds[i];
    if (out_fd)
      *out_fd = entry->fd;
    if (out_events)
      *out_events = entry->events;
    if (out_data)
      *out_data = entry->data;
    if (entry->callback) {
      entry->callback(entry->fd, entry->events, entry->data);
      return ALOOPER_POLL_CALLBACK;
    }
    return entry->ident;
  }
  return ALOOPER_POLL_WAKE;
}

int AInputQueue_attachLooper_fake(void *queue_ptr, void *looper_ptr, int ident,
                                  int (*callback)(int, int, void *), void *data) {
  FakeInputQueue *queue = queue_ptr;
  queue->looper = looper_ptr;
  return ALooper_addFd_fake(looper_ptr, queue->pipe_fd[0], ident,
                            ALOOPER_EVENT_INPUT, callback, data);
}

void AInputQueue_detachLooper_fake(void *queue_ptr) {
  FakeInputQueue *queue = queue_ptr;
  if (!queue || !queue->looper)
    return;
  FakeLooper *looper = queue->looper;
  for (int i = 0; i < looper->count; i++) {
    if (looper->fds[i].fd == queue->pipe_fd[0]) {
      memmove(&looper->fds[i], &looper->fds[i + 1],
              (looper->count - i - 1) * sizeof(looper->fds[0]));
      looper->count--;
      break;
    }
  }
  queue->looper = NULL;
}

int AInputQueue_getEvent_fake(void *queue_ptr, void **out_event) {
  FakeInputQueue *queue = queue_ptr;
  uint8_t wake;
  (void)read_dispatch_fake(queue->pipe_fd[0], &wake, sizeof(wake));
  pthread_mutex_lock(&queue->mutex);
  if (queue->head == queue->tail) {
    pthread_mutex_unlock(&queue->mutex);
    return -1;
  }
  *out_event = queue->events[queue->head];
  queue->head = (queue->head + 1) % 64;
  pthread_mutex_unlock(&queue->mutex);
  return 0;
}

int AInputQueue_preDispatchEvent_fake(void *queue, void *event) {
  (void)queue;
  (void)event;
  return 0;
}

void AInputQueue_finishEvent_fake(void *queue, void *event, int handled) {
  (void)queue;
  (void)handled;
  free(event);
}

int AInputEvent_getType_fake(void *event) { return ((FakeInputEvent *)event)->type; }
int AInputEvent_getDeviceId_fake(void *event) { return ((FakeInputEvent *)event)->device_id; }
int AInputEvent_getSource_fake(void *event) { return ((FakeInputEvent *)event)->source; }
int AKeyEvent_getAction_fake(void *event) { return ((FakeInputEvent *)event)->action; }
int AKeyEvent_getFlags_fake(void *event) { return ((FakeInputEvent *)event)->flags; }
int AKeyEvent_getKeyCode_fake(void *event) { return ((FakeInputEvent *)event)->keycode; }
int AKeyEvent_getMetaState_fake(void *event) { return ((FakeInputEvent *)event)->meta_state; }
int AMotionEvent_getAction_fake(void *event) { return ((FakeInputEvent *)event)->action; }
int AMotionEvent_getButtonState_fake(void *event) { return ((FakeInputEvent *)event)->button_state; }
size_t AMotionEvent_getPointerCount_fake(void *event) { (void)event; return 1; }
int AMotionEvent_getPointerId_fake(void *event, size_t pointer_index) {
  (void)pointer_index;
  return ((FakeInputEvent *)event)->pointer_id;
}
float AMotionEvent_getX_fake(void *event, size_t pointer_index) {
  (void)pointer_index;
  return ((FakeInputEvent *)event)->x;
}
float AMotionEvent_getY_fake(void *event, size_t pointer_index) {
  (void)pointer_index;
  return ((FakeInputEvent *)event)->y;
}

typedef struct {
  char **names;
  int count;
  int index;
} FakeAssetDir;

void *AAssetManager_openDir_fake(void *mgr, const char *path) {
  (void)mgr;
  FakeAssetDir *result = calloc(1, sizeof(*result));
  if (!result)
    return NULL;

  char candidate[0x400];
  DIR *dir = NULL;
  if (path && path[0])
    dir = opendir(path);
  else
    dir = opendir("assets");
  if (!dir) {
    snprintf(candidate, sizeof(candidate), "assets/%s", path ? path : "");
    dir = opendir(candidate);
  }
  if (!dir)
    return result;

  struct dirent *entry;
  while ((entry = readdir(dir))) {
    if (entry->d_name[0] == '.' &&
        (entry->d_name[1] == '\0' ||
         (entry->d_name[1] == '.' && entry->d_name[2] == '\0')))
      continue;
    char **names = realloc(result->names,
                           (size_t)(result->count + 1) * sizeof(*names));
    if (!names)
      break;
    result->names = names;
    result->names[result->count] = strdup(entry->d_name);
    if (!result->names[result->count])
      break;
    result->count++;
  }
  closedir(dir);
  return result;
}

const char *AAssetDir_getNextFileName_fake(void *dir_ptr) {
  FakeAssetDir *dir = dir_ptr;
  if (!dir || dir->index >= dir->count)
    return NULL;
  return dir->names[dir->index++];
}

void AAssetDir_close_fake(void *dir_ptr) {
  FakeAssetDir *dir = dir_ptr;
  if (!dir)
    return;
  for (int i = 0; i < dir->count; i++)
    free(dir->names[i]);
  free(dir->names);
  free(dir);
}

void *AConfiguration_new_fake(void) { return calloc(1, 16); }
void AConfiguration_delete_fake(void *config) { free(config); }
void AConfiguration_fromAssetManager_fake(void *config, void *mgr) {
  (void)config;
  (void)mgr;
}
void AConfiguration_getLanguage_fake(void *config, char out[2]) {
  (void)config;
  out[0] = 'e';
  out[1] = 'n';
}
void AConfiguration_getCountry_fake(void *config, char out[2]) {
  (void)config;
  out[0] = 'U';
  out[1] = 'S';
}

void ANativeActivity_setWindowFormat_fake(void *activity_ptr, int format) {
  (void)activity_ptr;
  (void)format;
}
void ANativeWindow_acquire_fake(void *window) { (void)window; }

typedef struct MapAlloc {
  struct MapAlloc *next;
  void *ptr;
  size_t size;
  size_t page_count;
  uint8_t *mapped_pages;
} MapAlloc;

static MapAlloc *map_allocs;
static pthread_mutex_t map_mutex = PTHREAD_MUTEX_INITIALIZER;

void *mmap_fake(void *addr, size_t length, int prot, int flags, int fd,
                int64_t offset) {
  debugPrintf("mmap(addr=%p, len=%zu, prot=%x, flags=%x, fd=%d, off=%lld)\n",
              addr, length, prot, flags, fd, (long long)offset);
  void *ptr = NULL;
  const size_t aligned = (length + 0xfff) & ~0xfff;
  if (posix_memalign_fake(&ptr, 0x1000, aligned) != 0) {
    debugPrintf("mmap: allocation failed for %zu bytes\n", aligned);
    return (void *)-1;
  }
  memset(ptr, 0, aligned);
  if (fd >= 0)
    (void)pread64_fake(fd, ptr, length, offset);
  MapAlloc *item = malloc(sizeof(*item));
  const size_t page_count = aligned / 0x1000;
  uint8_t *mapped_pages = malloc(page_count);
  if (!item || !mapped_pages) {
    free(mapped_pages);
    free(item);
    free(ptr);
    return (void *)-1;
  }
  memset(mapped_pages, 1, page_count);
  item->ptr = ptr;
  item->size = aligned;
  item->page_count = page_count;
  item->mapped_pages = mapped_pages;
  pthread_mutex_lock(&map_mutex);
  item->next = map_allocs;
  map_allocs = item;
  pthread_mutex_unlock(&map_mutex);
  debugPrintf("mmap: -> %p (%zu bytes)\n", ptr, aligned);
  return ptr;
}

int munmap_fake(void *addr, size_t length) {
  const uintptr_t start = (uintptr_t)addr;
  if (!length || (start & 0xfff) || length > SIZE_MAX - 0xfff) {
    errno = EINVAL;
    return -1;
  }
  const size_t aligned = (length + 0xfff) & ~0xfff;
  if (start > UINTPTR_MAX - aligned) {
    errno = EINVAL;
    return -1;
  }
  const uintptr_t end = start + aligned;
  size_t pages_unmapped = 0;
  size_t backings_released = 0;

  pthread_mutex_lock(&map_mutex);
  MapAlloc **link = &map_allocs;
  while (*link) {
    MapAlloc *item = *link;
    const uintptr_t item_start = (uintptr_t)item->ptr;
    const uintptr_t item_end = item_start + item->size;
    const uintptr_t overlap_start = start > item_start ? start : item_start;
    const uintptr_t overlap_end = end < item_end ? end : item_end;

    if (overlap_start < overlap_end) {
      const size_t first_page = (overlap_start - item_start) / 0x1000;
      const size_t last_page =
          (overlap_end - item_start + 0xfff) / 0x1000;
      for (size_t page = first_page;
           page < last_page && page < item->page_count; page++) {
        if (item->mapped_pages[page]) {
          item->mapped_pages[page] = 0;
          pages_unmapped++;
        }
      }
    }

    int has_mapped_pages = 0;
    for (size_t page = 0; page < item->page_count; page++) {
      if (item->mapped_pages[page]) {
        has_mapped_pages = 1;
        break;
      }
    }
    if (has_mapped_pages) {
      link = &item->next;
      continue;
    }

    *link = item->next;
    free(item->mapped_pages);
    free(item->ptr);
    free(item);
    backings_released++;
  }
  pthread_mutex_unlock(&map_mutex);

  debugPrintf("munmap(addr=%p, len=%zu) -> 0, pages=%zu released=%zu\n",
              addr, length, pages_unmapped, backings_released);
  return 0;
}

int mprotect_fake(void *addr, size_t length, int prot) {
  debugPrintf("mprotect(%p, %zu, %x)\n", addr, length, prot);
  return 0;
}
int madvise_fake(void *addr, size_t length, int advice) {
  debugPrintf("madvise(%p, %zu, %x)\n", addr, length, advice);
  return 0;
}
int mlock_fake(const void *addr, size_t length) {
  debugPrintf("mlock(%p, %zu)\n", addr, length);
  return 0;
}

int clock_nanosleep_fake(int clock_id, int flags, const void *request_ptr,
                         void *remain_ptr) {
  const struct timespec *request = request_ptr;
  struct timespec delay = *request;
  if (flags & TIMER_ABSTIME) {
    struct timespec now;
    if (clock_gettime(clock_id, &now) < 0)
      return errno;
    delay.tv_sec -= now.tv_sec;
    delay.tv_nsec -= now.tv_nsec;
    if (delay.tv_nsec < 0) {
      delay.tv_sec--;
      delay.tv_nsec += 1000000000L;
    }
    if (delay.tv_sec < 0)
      return 0;
  }
  return nanosleep(&delay, remain_ptr) < 0 ? errno : 0;
}

int fdatasync_fake(int fd) { return fsync(fd); }

int64_t lseek64_fake(int fd, int64_t offset, int whence) {
  return (int64_t)lseek(fd, (off_t)offset, whence);
}

ssize_t pread64_fake(int fd, void *buf, size_t count, int64_t offset) {
  static pthread_mutex_t io_mutex = PTHREAD_MUTEX_INITIALIZER;
  pthread_mutex_lock(&io_mutex);
  const off_t position = lseek(fd, 0, SEEK_CUR);
  ssize_t result = -1;
  if (position >= 0 && lseek(fd, (off_t)offset, SEEK_SET) >= 0) {
    result = read_dispatch_fake(fd, buf, count);
    (void)lseek(fd, position, SEEK_SET);
  }
  pthread_mutex_unlock(&io_mutex);
  return result;
}

ssize_t pwrite64_fake(int fd, const void *buf, size_t count, int64_t offset) {
  static pthread_mutex_t io_mutex = PTHREAD_MUTEX_INITIALIZER;
  pthread_mutex_lock(&io_mutex);
  const off_t position = lseek(fd, 0, SEEK_CUR);
  ssize_t result = -1;
  if (position >= 0 && lseek(fd, (off_t)offset, SEEK_SET) >= 0) {
    result = write_dispatch_fake(fd, buf, count);
    (void)lseek(fd, position, SEEK_SET);
  }
  pthread_mutex_unlock(&io_mutex);
  return result;
}

extern so_module avs_mod;
extern so_module afp_mod;
extern so_module ue4_mod;

static _Thread_local char dl_error[128];

static void dl_set_error(const char *message) {
  strlcpy(dl_error, message, sizeof(dl_error));
}

void *dlopen_fake(const char *filename, int flags) {
  (void)flags;
  dl_error[0] = '\0';
  if (!filename)
    return (void *)-1;
  if (strstr(filename, "libUE4.so"))
    return &ue4_mod;
  if (strstr(filename, "libavs2-core.so"))
    return &avs_mod;
  if (strstr(filename, "libafp-core.so"))
    return &afp_mod;
  if (strstr(filename, "libc.so") || strstr(filename, "libm.so") ||
      strstr(filename, "libdl.so") || strstr(filename, "libandroid.so") ||
      strstr(filename, "libEGL.so") || strstr(filename, "libGLESv2.so") ||
      strstr(filename, "libOpenSLES.so") || strstr(filename, "libz.so"))
    return (void *)-1;
  dl_set_error("library is not part of the PES21 NX runtime");
  return NULL;
}

static uintptr_t lookup_module_symbol(so_module *module, const char *symbol) {
  if (!module || !module->load_virtbase)
    return 0;
  return so_try_find_addr_rx(module, symbol);
}

void *dlsym_fake(void *handle, const char *symbol) {
  dl_error[0] = '\0';
  if (!symbol) {
    dl_set_error("invalid symbol name");
    return NULL;
  }

  DynLibFunction *import =
      so_find_import(dynlib_functions, dynlib_numfunctions, symbol);
  if (import)
    return (void *)import->func;

  uintptr_t address = 0;
  if (handle == &ue4_mod)
    address = lookup_module_symbol(&ue4_mod, symbol);
  else if (handle == &avs_mod)
    address = lookup_module_symbol(&avs_mod, symbol);
  else if (handle == &afp_mod)
    address = lookup_module_symbol(&afp_mod, symbol);
  else {
    address = lookup_module_symbol(&ue4_mod, symbol);
    if (!address)
      address = lookup_module_symbol(&afp_mod, symbol);
    if (!address)
      address = lookup_module_symbol(&avs_mod, symbol);
  }
  if (!address)
    dl_set_error("symbol was not found");
  return (void *)address;
}

int dlclose_fake(void *handle) {
  (void)handle;
  return 0;
}

char *dlerror_fake(void) {
  if (!dl_error[0])
    return NULL;
  return dl_error;
}

typedef struct {
  const char *file_name;
  void *file_base;
  const char *symbol_name;
  void *symbol_address;
} FakeDlInfo;

int dladdr_fake(const void *address_ptr, void *info_ptr) {
  const uintptr_t address = (uintptr_t)address_ptr;
  FakeDlInfo *info = info_ptr;
  so_module *modules[] = {&ue4_mod, &afp_mod, &avs_mod};
  for (unsigned int i = 0; i < sizeof(modules) / sizeof(modules[0]); i++) {
    so_module *module = modules[i];
    const uintptr_t base = (uintptr_t)module->load_virtbase;
    if (base && address >= base && address < base + module->load_size) {
      if (info) {
        info->file_name = module->name;
        info->file_base = module->load_virtbase;
        info->symbol_name = NULL;
        info->symbol_address = NULL;
      }
      return 1;
    }
  }
  return 0;
}

#define FAKE_EPOLL_BASE 0x71000000
#define FAKE_EPOLL_COUNT 8
#define FAKE_EPOLL_FDS 64

typedef struct __attribute__((packed)) {
  uint32_t events;
  uint64_t data;
} FakeEpollEvent;

typedef struct {
  int used;
  int count;
  struct {
    int fd;
    FakeEpollEvent event;
  } entries[FAKE_EPOLL_FDS];
} FakeEpoll;

static FakeEpoll fake_epolls[FAKE_EPOLL_COUNT];

static int close_epoll_fd(int fd) {
  const int index = fd - FAKE_EPOLL_BASE;
  if (index < 0 || index >= FAKE_EPOLL_COUNT || !fake_epolls[index].used)
    return 0;
  memset(&fake_epolls[index], 0, sizeof(fake_epolls[index]));
  return 1;
}

static FakeEpoll *get_epoll(int epfd) {
  const int index = epfd - FAKE_EPOLL_BASE;
  if (index < 0 || index >= FAKE_EPOLL_COUNT || !fake_epolls[index].used)
    return NULL;
  return &fake_epolls[index];
}

int epoll_create_fake(int size) {
  (void)size;
  for (int i = 0; i < FAKE_EPOLL_COUNT; i++) {
    if (!fake_epolls[i].used) {
      memset(&fake_epolls[i], 0, sizeof(fake_epolls[i]));
      fake_epolls[i].used = 1;
      return FAKE_EPOLL_BASE + i;
    }
  }
  errno = EMFILE;
  return -1;
}

int epoll_ctl_fake(int epfd, int operation, int fd, void *event_ptr) {
  FakeEpoll *epoll = get_epoll(epfd);
  FakeEpollEvent *event = event_ptr;
  if (!epoll) {
    errno = EBADF;
    return -1;
  }
  int index = -1;
  for (int i = 0; i < epoll->count; i++)
    if (epoll->entries[i].fd == fd) {
      index = i;
      break;
    }
  if (operation == 1) {
    if (index >= 0 || !event || epoll->count >= FAKE_EPOLL_FDS) {
      errno = index >= 0 ? EEXIST : ENOSPC;
      return -1;
    }
    epoll->entries[epoll->count].fd = fd;
    epoll->entries[epoll->count].event = *event;
    epoll->count++;
    return 0;
  }
  if (operation == 2) {
    if (index < 0) {
      errno = ENOENT;
      return -1;
    }
    memmove(&epoll->entries[index], &epoll->entries[index + 1],
            (size_t)(epoll->count - index - 1) * sizeof(epoll->entries[0]));
    epoll->count--;
    return 0;
  }
  if (operation == 3 && index >= 0 && event) {
    epoll->entries[index].event = *event;
    return 0;
  }
  errno = EINVAL;
  return -1;
}

int epoll_wait_fake(int epfd, void *events_ptr, int max_events,
                    int timeout_ms) {
  FakeEpoll *epoll = get_epoll(epfd);
  FakeEpollEvent *events = events_ptr;
  if (!epoll || !events || max_events <= 0) {
    errno = EINVAL;
    return -1;
  }
  struct pollfd poll_fds[FAKE_EPOLL_FDS];
  for (int i = 0; i < epoll->count; i++) {
    poll_fds[i].fd = epoll->entries[i].fd;
    poll_fds[i].events = (short)epoll->entries[i].event.events;
    poll_fds[i].revents = 0;
  }
  const int ready = poll_dispatch_fake(poll_fds, epoll->count, timeout_ms);
  if (ready <= 0)
    return ready;
  int output_count = 0;
  for (int i = 0; i < epoll->count && output_count < max_events; i++) {
    if (!poll_fds[i].revents)
      continue;
    events[output_count] = epoll->entries[i].event;
    events[output_count].events = (uint32_t)poll_fds[i].revents;
    output_count++;
  }
  return output_count;
}

typedef struct {
  uint64_t type;
  uint64_t block_size;
  uint64_t blocks;
  uint64_t blocks_free;
  uint64_t blocks_available;
  uint64_t files;
  uint64_t files_free;
  uint32_t fsid[2];
  uint64_t name_length;
  uint64_t fragment_size;
  uint64_t flags;
  uint64_t spare[4];
} BionicStatFs;

int statfs_fake(const char *path, void *buf_ptr) {
  struct statvfs source;
  BionicStatFs *buf = buf_ptr;
  if (!buf || statvfs(path, &source) < 0)
    return -1;
  memset(buf, 0, sizeof(*buf));
  buf->block_size = source.f_bsize;
  buf->blocks = source.f_blocks;
  buf->blocks_free = source.f_bfree;
  buf->blocks_available = source.f_bavail;
  buf->files = source.f_files;
  buf->files_free = source.f_ffree;
  buf->name_length = source.f_namemax;
  buf->fragment_size = source.f_frsize;
  buf->flags = source.f_flag;
  return 0;
}

typedef struct {
  int64_t uptime;
  uint64_t loads[3];
  uint64_t total_ram;
  uint64_t free_ram;
  uint64_t shared_ram;
  uint64_t buffer_ram;
  uint64_t total_swap;
  uint64_t free_swap;
  uint16_t processes;
  uint16_t padding;
  uint64_t total_high;
  uint64_t free_high;
  uint32_t memory_unit;
} BionicSysinfo;

int sysinfo_fake(void *info_ptr) {
  BionicSysinfo *info = info_ptr;
  if (!info) {
    errno = EFAULT;
    return -1;
  }
  memset(info, 0, sizeof(*info));
  uint64_t total = 0;
  uint64_t used = 0;
  svcGetInfo(&total, InfoType_TotalMemorySize, CUR_PROCESS_HANDLE, 0);
  svcGetInfo(&used, InfoType_UsedMemorySize, CUR_PROCESS_HANDLE, 0);
  info->total_ram = total;
  info->free_ram = total > used ? total - used : 0;
  info->processes = 1;
  info->memory_unit = 1;
  return 0;
}

int isfinitef_fake(float value) { return isfinite(value); }

int getpriority_fake(int which, int who) {
  (void)which;
  (void)who;
  return 0;
}

int setpriority_fake(int which, int who, int priority) {
  (void)which;
  (void)who;
  (void)priority;
  return 0;
}

typedef struct {
  uint64_t current;
  uint64_t maximum;
} BionicRLimit;

int getrlimit_fake(int resource, void *limit_ptr) {
  (void)resource;
  BionicRLimit *limit = limit_ptr;
  if (!limit) {
    errno = EFAULT;
    return -1;
  }
  limit->current = UINT64_MAX;
  limit->maximum = UINT64_MAX;
  return 0;
}

int setrlimit_fake(int resource, const void *limit) {
  (void)resource;
  (void)limit;
  return 0;
}

char *if_indextoname_fake(unsigned int index, char *name) {
  if (!name || index == 0) {
    errno = ENXIO;
    return NULL;
  }
  strlcpy(name, index == 1 ? "lo" : "wlan0", 16);
  return name;
}

int pthread_getschedparam_fake(uintptr_t thread, int *policy, void *param_ptr) {
  (void)thread;
  struct sched_param *param = param_ptr;
  if (policy)
    *policy = SCHED_OTHER;
  if (param)
    param->sched_priority = 0;
  return 0;
}

unsigned int getuid_fake(void) { return 0; }
unsigned int getgid_fake(void) { return 0; }

int pause_fake(void) {
  svcSleepThread(1000000LL);
  errno = EINTR;
  return -1;
}

int sigaction_fake(int signal_number, const void *action, void *old_action) {
  (void)signal_number;
  (void)action;
  if (old_action)
    memset(old_action, 0, 32);
  return 0;
}

int sigemptyset_fake(void *set) {
  if (!set) {
    errno = EINVAL;
    return -1;
  }
  memset(set, 0, 16);
  return 0;
}

long timezone_fake = 0;
char *tzname_fake[2] = {"UTC", "UTC"};

int pthread_rwlock_init_fake(void **rw, const void *attr) {
  (void)attr;
  *rw = NULL;
  return 0;
}
int pthread_rwlock_destroy_fake(void **rw) {
  if (rw && *rw) {
    free(*rw);
    *rw = NULL;
  }
  return 0;
}
int pthread_rwlock_tryrdlock_fake(void **rw) {
  return pthread_rwlock_rdlock_fake(rw);
}
int pthread_rwlock_trywrlock_fake(void **rw) {
  return pthread_rwlock_wrlock_fake(rw);
}

static uintptr_t require_export(so_module *mod, const char *name) {
  const uintptr_t addr = so_try_find_addr_rx(mod, name);
  if (!addr)
    fatal_error("Missing UE4 export:\n%s", name);
  debugPrintf("bootstrap: export %s = %p\n", name, (void *)addr);
  return addr;
}

void android_runtime_bootstrap(so_module *ue4) {
  void (*native_activity_on_create)(ANativeActivity *, void *, size_t) =
      (void *)require_export(ue4, "ANativeActivity_onCreate");
  void (*set_global)(void *, void *, int, void *, void *, int, void *) =
      (void *)require_export(
          ue4, "Java_com_epicgames_ue4_GameActivity_nativeSetGlobalActivity");
  void (*set_window)(void *, void *, int, int) = (void *)require_export(
      ue4, "Java_com_epicgames_ue4_GameActivity_nativeSetWindowInfo");
  void (*set_startup)(void *, void *, int) = (void *)require_export(
      ue4, "Java_com_epicgames_ue4_GameActivity_nativeSetAndroidStartupState");
  void (*set_affinity)(void *, void *, int, int, int) =
      (void *)require_export(
          ue4, "Java_com_epicgames_ue4_GameActivity_nativeSetAffinityInfo");
  void (*set_config_rules)(void *, void *, void *) =
      (void *)require_export(
          ue4,
          "Java_com_epicgames_ue4_GameActivity_nativeSetConfigRulesVariables");
  void (*set_version)(void *, void *, void *, void *, void *, void *, void *) =
      (void *)require_export(
          ue4,
          "Java_com_epicgames_ue4_GameActivity_nativeSetAndroidVersionInformation");
  void (*set_obb)(void *, void *, void *, void *, int, int, void *) =
      (void *)require_export(ue4,
                             "Java_com_epicgames_ue4_GameActivity_nativeSetObbInfo");
  void (*set_surface)(void *, void *, int, int) = (void *)require_export(
      ue4, "Java_com_epicgames_ue4_GameActivity_nativeSetSurfaceViewInfo");
  void (*resume_main)(void *, void *) = (void *)require_export(
      ue4, "Java_com_epicgames_ue4_GameActivity_nativeResumeMainInit");
  void (*init_hmds)(void *, void *) = (void *)require_export(
      ue4, "Java_com_epicgames_ue4_GameActivity_nativeInitHMDs");
  jni_set_native_init_hmds(init_hmds);

  debugPrintf("bootstrap: activity setup begin\n");
  memset(&activity, 0, sizeof(activity));
  memset(&activity_callbacks, 0, sizeof(activity_callbacks));
  activity.callbacks = &activity_callbacks;
  activity.vm = fake_vm;
  activity.env = fake_env;
  activity.clazz = jni_make_object("com/epicgames/ue4/GameActivity");
  activity.internalDataPath = ".";
  activity.externalDataPath = ".";
  activity.sdkVersion = 29;
  activity.assetManager = (void *)1;
  activity.obbPath = "";
  debugPrintf("bootstrap: activity setup done clazz=%p callbacks=%p\n",
              activity.clazz, activity.callbacks);

  debugPrintf("bootstrap: input queue init begin\n");
  input_queue_init();
  debugPrintf("bootstrap: input queue init done\n");
  debugPrintf("bootstrap: ANativeActivity_onCreate begin\n");
  native_activity_on_create(&activity, NULL, 0);
  debugPrintf("bootstrap: ANativeActivity_onCreate done callbacks=%p\n",
              activity.callbacks);

  debugPrintf("bootstrap: JNI argument setup begin\n");
  void *internal = jni_make_string(".");
  void *external = jni_make_string(".");
  void *apk = jni_make_string("PES21.apk");
  void *project = jni_make_string("PesMobile");
  void *package = jni_make_string("jp.nyan2021.pesam");
  void *app_type = jni_make_string("");
  debugPrintf("bootstrap: JNI argument setup done\n");

  debugPrintf("bootstrap: nativeSetGlobalActivity begin\n");
  set_global(fake_env, activity.clazz, 1, internal, external, 0, apk);
  debugPrintf("bootstrap: nativeSetGlobalActivity done\n");
  debugPrintf("bootstrap: nativeSetWindowInfo begin\n");
  set_window(fake_env, activity.clazz, 0, 0);
  debugPrintf("bootstrap: nativeSetWindowInfo done\n");
  debugPrintf("bootstrap: nativeSetAndroidStartupState begin\n");
  set_startup(fake_env, activity.clazz, 0);
  debugPrintf("bootstrap: nativeSetAndroidStartupState done\n");
  debugPrintf("bootstrap: nativeSetAffinityInfo begin\n");
  set_affinity(fake_env, activity.clazz, 0, 0, 0);
  debugPrintf("bootstrap: nativeSetAffinityInfo done\n");
  debugPrintf("bootstrap: nativeSetConfigRulesVariables begin\n");
  set_config_rules(fake_env, activity.clazz, jni_make_string_array(0, NULL));
  debugPrintf("bootstrap: nativeSetConfigRulesVariables done\n");
  debugPrintf("bootstrap: nativeSetAndroidVersionInformation begin\n");
  set_version(fake_env, activity.clazz, jni_make_string("10"),
              jni_make_string("Nintendo"), jni_make_string("Switch"),
              jni_make_string("Horizon"), jni_make_string("en_US"));
  debugPrintf("bootstrap: nativeSetAndroidVersionInformation done\n");
  debugPrintf("bootstrap: nativeSetObbInfo begin\n");
  set_obb(fake_env, activity.clazz, project, package, 305030001, 0, app_type);
  debugPrintf("bootstrap: nativeSetObbInfo done\n");
  debugPrintf("bootstrap: nativeSetSurfaceViewInfo begin\n");
  set_surface(fake_env, activity.clazz, screen_width, screen_height);
  debugPrintf("bootstrap: nativeSetSurfaceViewInfo done\n");

  if (!activity.callbacks)
    fatal_error("UE4 did not install NativeActivity callbacks.");

  NWindow *window = nwindowGetDefault();
  nwindowSetDimensions(window, screen_width, screen_height);
  debugPrintf("bootstrap: window ready %p callbacks=%p\n", window,
              activity.callbacks);
  if (activity.callbacks->onStart) {
    debugPrintf("bootstrap: callback onStart begin\n");
    activity.callbacks->onStart(&activity);
    debugPrintf("bootstrap: callback onStart done\n");
  }
  if (activity.callbacks->onResume) {
    debugPrintf("bootstrap: callback onResume begin\n");
    activity.callbacks->onResume(&activity);
    debugPrintf("bootstrap: callback onResume done\n");
  }
  if (activity.callbacks->onNativeWindowCreated) {
    debugPrintf("bootstrap: callback onNativeWindowCreated begin\n");
    activity.callbacks->onNativeWindowCreated(&activity, window);
    debugPrintf("bootstrap: callback onNativeWindowCreated done\n");
  }
  if (activity.callbacks->onInputQueueCreated) {
    debugPrintf("bootstrap: callback onInputQueueCreated begin\n");
    activity.callbacks->onInputQueueCreated(&activity, &input_queue);
    debugPrintf("bootstrap: callback onInputQueueCreated done\n");
  }
  if (activity.callbacks->onWindowFocusChanged) {
    debugPrintf("bootstrap: callback onWindowFocusChanged begin\n");
    activity.callbacks->onWindowFocusChanged(&activity, 1);
    debugPrintf("bootstrap: callback onWindowFocusChanged done\n");
  }

  debugPrintf("bootstrap: nativeResumeMainInit begin\n");
  resume_main(fake_env, activity.clazz);
  debugPrintf("bootstrap: nativeResumeMainInit done\n");

  padConfigureInput(1, HidNpadStyleSet_NpadStandard);
  debugPrintf("input: HID shared memory=%p\n", hidGetSharedmemAddr());
  debugPrintf("Android NativeActivity bootstrap complete.\n");
}
