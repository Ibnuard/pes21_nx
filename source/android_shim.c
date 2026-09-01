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
#include "perf_trace.h"
#include "ue4_hooks.h"
#include "util.h"

#define AINPUT_EVENT_TYPE_KEY 1
#define AINPUT_EVENT_TYPE_MOTION 2
#define AMOTION_EVENT_ACTION_DOWN 0
#define AMOTION_EVENT_ACTION_UP 1
#define AMOTION_EVENT_ACTION_MOVE 2
#define AMOTION_EVENT_ACTION_POINTER_DOWN 5
#define AMOTION_EVENT_ACTION_POINTER_UP 6
#define AMOTION_EVENT_ACTION_POINTER_INDEX_SHIFT 8
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
  int pointer_id;
  float x;
  float y;
} FakeMotionPointer;

#define MAX_FAKE_MOTION_POINTERS 8

typedef struct {
  int type;
  int device_id;
  int source;
  int action;
  int flags;
  int keycode;
  int meta_state;
  int button_state;
  uint32_t pointer_count;
  FakeMotionPointer pointers[MAX_FAKE_MOTION_POINTERS];
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
static float previous_left_axis_x;
static float previous_left_axis_y;
static int previous_left_axis_valid;

typedef struct {
  FakeMotionPointer pointers[MAX_FAKE_MOTION_POINTERS];
  uint32_t count;
} FakeTouchState;

typedef enum {
  VIRTUAL_SURFACE_NONE = 0,
  VIRTUAL_SURFACE_BUTTON,
  VIRTUAL_SURFACE_CROSS,
} VirtualSurfaceOwner;

typedef struct {
  VirtualSurfaceOwner owner;
  uint64_t started_ms;
  int moved;
} VirtualSurfaceState;

static FakeTouchState active_touch_state;
static VirtualSurfaceState pass_surface;
static VirtualSurfaceState through_surface;
static VirtualSurfaceState shoot_surface;
static VirtualSurfaceState pause_surface;
static int replay_touch_requested;
static uint64_t previous_hid_buttons;
static uint64_t previous_hid_buttons_p2;
static uint32_t native_setplay_owner_pad;
static int previous_mobile_context_mode;
static float physical_touch_start_x;
static float physical_touch_start_y;
static float physical_touch_last_x;
static float physical_touch_last_y;
static int physical_touch_tracking;
static uint32_t synthetic_input_generation = 1;
static int previous_synthetic_input_context = -1;
static uint64_t compact_menu_tap_until_ms;
static float compact_menu_tap_x;
static float compact_menu_tap_y;

enum {
  SYNTHETIC_INPUT_NONE = 0,
  SYNTHETIC_INPUT_REPLAY = 1,
  SYNTHETIC_INPUT_GAMEPLAY = 2,
  SYNTHETIC_INPUT_MENU = 3,
  SYNTHETIC_INPUT_GOAL_DEMO = 4,
  SYNTHETIC_INPUT_SET_PIECE_SELECTOR = 5,
  SYNTHETIC_INPUT_TUTORIAL = 6,
  SYNTHETIC_INPUT_SETPLAY_BASE = 8,
  SYNTHETIC_INPUT_CURSOR_BASE = 16,
  SYNTHETIC_INPUT_PENALTY_BASE = 32,
};

enum {
  FAKE_POINTER_PHYSICAL = 0,
  // cobra::game::TouchPanel only accepts pointer IDs 0..9. Reserve 0 for the
  // real Switch touchscreen and keep every controller finger inside that ABI.
  FAKE_POINTER_STICK = 1,
  FAKE_POINTER_PASS = 2,
  FAKE_POINTER_THROUGH = 3,
  FAKE_POINTER_SHOOT = 4,
  FAKE_POINTER_DASH = 5,
  FAKE_POINTER_PAUSE = 6,
  FAKE_POINTER_MENU = 7,
  FAKE_POINTER_MENU_SCROLL = 8,
  FAKE_POINTER_MENU_BACK = 9,
  FAKE_POINTER_CAMERA = FAKE_POINTER_PAUSE,
  FAKE_POINTER_GAMEPLAN_CURSOR = FAKE_POINTER_MENU,
  FAKE_POINTER_GAMEPLAN_PLAY = FAKE_POINTER_MENU_SCROLL,
  FAKE_POINTER_CONTEXT_ACTION = FAKE_POINTER_MENU,
  // Replay and menu/gameplan surfaces never coexist; reuse the final slot.
  FAKE_POINTER_REPLAY = FAKE_POINTER_MENU_BACK,
  FAKE_POINTER_GOAL_DEMO = FAKE_POINTER_MENU_BACK,
  FAKE_POINTER_CINEMATIC = FAKE_POINTER_MENU_BACK,
  FAKE_POINTER_PENALTY = FAKE_POINTER_MENU_BACK,
};

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
  struct pollfd native_stack[64];
  struct pollfd *native = native_stack;
  if (nfds > sizeof(native_stack) / sizeof(native_stack[0])) {
    if (nfds > SIZE_MAX / sizeof(*native)) {
      errno = ENOMEM;
      return -1;
    }
    native = malloc(nfds * sizeof(*native));
    if (!native) {
      errno = ENOMEM;
      return -1;
    }
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
      if (native != native_stack)
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
      if (native != native_stack)
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

static int input_queue_push(FakeInputEvent *event) {
  int queued = 0;
  pthread_mutex_lock(&input_queue.mutex);

  // Android may batch touch MOVE samples before the application consumes
  // them.  Our producer runs independently from UE4, so retaining every
  // intermediate analog-stick position can otherwise fill the 64-event ring
  // while a gameplay frame is busy.  Replace the newest unconsumed MOVE when
  // its pointer topology is unchanged; DOWN/UP transitions are never merged.
  if ((event->action & 0xff) == AMOTION_EVENT_ACTION_MOVE &&
      input_queue.head != input_queue.tail) {
    const unsigned int previous_index =
        (input_queue.tail + 63) % 64;
    FakeInputEvent *previous = input_queue.events[previous_index];
    int same_topology =
        previous &&
        (previous->action & 0xff) == AMOTION_EVENT_ACTION_MOVE &&
        previous->pointer_count == event->pointer_count;
    for (uint32_t index = 0;
         same_topology && index < event->pointer_count; index++) {
      if (previous->pointers[index].pointer_id !=
          event->pointers[index].pointer_id)
        same_topology = 0;
    }
    if (same_topology) {
      *previous = *event;
      queued = 1;
      pthread_mutex_unlock(&input_queue.mutex);
      free(event);
      return queued;
    }
  }

  const unsigned int next = (input_queue.tail + 1) % 64;
  if (next != input_queue.head) {
    input_queue.events[input_queue.tail] = event;
    input_queue.tail = next;
    const uint8_t wake = 1;
    (void)write_dispatch_fake(input_queue.pipe_fd[1], &wake, sizeof(wake));
    event = NULL;
    queued = 1;
  }
  pthread_mutex_unlock(&input_queue.mutex);
  free(event);
  return queued;
}

static int push_motion_snapshot(int action, const FakeTouchState *state) {
  FakeInputEvent *event = calloc(1, sizeof(*event));
  if (!event)
    return 0;
  event->type = AINPUT_EVENT_TYPE_MOTION;
  event->device_id = 0;
  event->source = AINPUT_SOURCE_TOUCHSCREEN;
  event->action = action;
  event->pointer_count = state->count;
  memcpy(event->pointers, state->pointers,
         state->count * sizeof(state->pointers[0]));
  const int queued = input_queue_push(event);

#ifdef DEBUG_LOG
  static unsigned int transition_log_count;
  static unsigned int move_log_count;
  const int is_move = (action & 0xff) == AMOTION_EVENT_ACTION_MOVE;
  const int should_log =
      queued && ((is_move && move_log_count < 24) ||
                 (!is_move && transition_log_count < 256));
  if (should_log) {
    if (is_move)
      move_log_count++;
    else
      transition_log_count++;
    char line[384];
    int used = snprintf(line, sizeof(line),
                        "input: motion action=0x%x count=%u", action,
                        state->count);
    for (uint32_t index = 0;
         index < state->count && used > 0 && used < (int)sizeof(line);
         index++) {
      const int written = snprintf(
          line + used, sizeof(line) - (size_t)used, " id%d=%.0f,%.0f",
          state->pointers[index].pointer_id, state->pointers[index].x,
          state->pointers[index].y);
      if (written < 0)
        break;
      used += written;
    }
    debugPrintf("%s\n", line);
  }
#endif
  return queued;
}

static int touch_state_find(const FakeTouchState *state, int pointer_id) {
  for (uint32_t index = 0; index < state->count; index++) {
    if (state->pointers[index].pointer_id == pointer_id)
      return (int)index;
  }
  return -1;
}

static int touch_state_append(FakeTouchState *state, int pointer_id, float x,
                              float y) {
  if (state->count >= MAX_FAKE_MOTION_POINTERS ||
      touch_state_find(state, pointer_id) >= 0)
    return 0;
  state->pointers[state->count++] =
      (FakeMotionPointer){pointer_id, x, y};
  return 1;
}

// Reconcile one immutable Android MotionEvent snapshot at a time. Pointer
// additions/removals are committed only after their event enters the queue, so
// a temporarily full queue cannot leave UE4 with a permanently stuck finger.
static void reconcile_touch_state(const FakeTouchState *desired) {
  FakeTouchState moved = active_touch_state;
  int coordinates_changed = 0;
  for (uint32_t index = 0; index < moved.count; index++) {
    const int desired_index =
        touch_state_find(desired, moved.pointers[index].pointer_id);
    if (desired_index < 0)
      continue;
    const FakeMotionPointer *target = &desired->pointers[desired_index];
    if (fabsf(moved.pointers[index].x - target->x) >= 0.75f ||
        fabsf(moved.pointers[index].y - target->y) >= 0.75f) {
      moved.pointers[index].x = target->x;
      moved.pointers[index].y = target->y;
      coordinates_changed = 1;
    }
  }
  if (coordinates_changed) {
    if (!push_motion_snapshot(AMOTION_EVENT_ACTION_MOVE, &moved))
      return;
    active_touch_state = moved;
  }

  for (int index = (int)active_touch_state.count - 1; index >= 0; index--) {
    const int pointer_id = active_touch_state.pointers[index].pointer_id;
    if (touch_state_find(desired, pointer_id) >= 0)
      continue;
    const int action =
        active_touch_state.count == 1
            ? AMOTION_EVENT_ACTION_UP
            : AMOTION_EVENT_ACTION_POINTER_UP |
                  (index << AMOTION_EVENT_ACTION_POINTER_INDEX_SHIFT);
    if (!push_motion_snapshot(action, &active_touch_state))
      return;
    memmove(&active_touch_state.pointers[index],
            &active_touch_state.pointers[index + 1],
            (active_touch_state.count - (uint32_t)index - 1) *
                sizeof(active_touch_state.pointers[0]));
    active_touch_state.count--;
  }

  for (uint32_t desired_index = 0; desired_index < desired->count;
       desired_index++) {
    const FakeMotionPointer *point = &desired->pointers[desired_index];
    if (touch_state_find(&active_touch_state, point->pointer_id) >= 0)
      continue;
    FakeTouchState added = active_touch_state;
    if (!touch_state_append(&added, point->pointer_id, point->x, point->y))
      continue;
    const int action =
        added.count == 1
            ? AMOTION_EVENT_ACTION_DOWN
            : AMOTION_EVENT_ACTION_POINTER_DOWN |
                  ((int)(added.count - 1)
                   << AMOTION_EVENT_ACTION_POINTER_INDEX_SHIFT);
    if (!push_motion_snapshot(action, &added))
      return;
    active_touch_state = added;
  }
}

static void merge_npad_state(const HidNpadCommonState *state, u64 *buttons,
                             HidAnalogStickState *left_stick,
                             int *have_left_stick,
                             HidAnalogStickState *right_stick,
                             int *have_right_stick) {
  *buttons |= state->buttons;
  const int64_t candidate_magnitude =
      (int64_t)state->analog_stick_l.x * state->analog_stick_l.x +
      (int64_t)state->analog_stick_l.y * state->analog_stick_l.y;
  const int64_t current_magnitude =
      (int64_t)left_stick->x * left_stick->x +
      (int64_t)left_stick->y * left_stick->y;
  if (!*have_left_stick || candidate_magnitude > current_magnitude) {
    *left_stick = state->analog_stick_l;
    *have_left_stick = 1;
  }
  const int64_t right_candidate_magnitude =
      (int64_t)state->analog_stick_r.x * state->analog_stick_r.x +
      (int64_t)state->analog_stick_r.y * state->analog_stick_r.y;
  const int64_t right_current_magnitude =
      (int64_t)right_stick->x * right_stick->x +
      (int64_t)right_stick->y * right_stick->y;
  if (!*have_right_stick ||
      right_candidate_magnitude > right_current_magnitude) {
    *right_stick = state->analog_stick_r;
    *have_right_stick = 1;
  }
}

static uint32_t menu_pad_buttons(u64 buttons,
                                 const HidAnalogStickState *left_stick,
                                 int have_left_stick) {
  uint32_t mapped = 0;
  // Matchmaking screens use the synthetic touch target below for a single,
  // deterministic Back action; suppress the native B bit there to avoid a
  // double-pop/double-footer activation. Other menu windows retain native B.
  if ((buttons & HidNpadButton_B) &&
      !pes_controller_menu_back_target(NULL, NULL))
    mapped |= 1u << 0;
  if (buttons & HidNpadButton_A) mapped |= 1u << 1;
  if (buttons & HidNpadButton_Y) mapped |= 1u << 2;
  if (buttons & HidNpadButton_X) mapped |= 1u << 3;
  if (buttons & HidNpadButton_L) mapped |= 1u << 4;
  if (buttons & HidNpadButton_ZL) mapped |= 1u << 5;
  if (buttons & HidNpadButton_StickL) mapped |= 1u << 6;
  if (buttons & HidNpadButton_R) mapped |= 1u << 7;
  if (buttons & HidNpadButton_ZR) mapped |= 1u << 8;
  if (buttons & HidNpadButton_StickR) mapped |= 1u << 9;
  if (buttons & HidNpadButton_Up) mapped |= 1u << 10;
  if (buttons & HidNpadButton_Down) mapped |= 1u << 11;
  if (buttons & HidNpadButton_Left) mapped |= 1u << 12;
  if (buttons & HidNpadButton_Right) mapped |= 1u << 13;
  if (buttons & HidNpadButton_Plus) mapped |= 1u << 14;
  if (buttons & HidNpadButton_Minus) mapped |= 1u << 15;

  // The left stick is an alternate menu arrow pad. Gameplay keeps using the
  // same stick through the virtual touch controls, so this is only emitted
  // while the menu bridge is active.
  if (have_left_stick) {
    const int threshold = JOYSTICK_MAX / 3;
    // Switch HID reports positive Y when the stick is pushed upward.
    if (left_stick->y > threshold) mapped |= 1u << 10;
    if (left_stick->y < -threshold) mapped |= 1u << 11;
    if (left_stick->x < -threshold) mapped |= 1u << 12;
    if (left_stick->x > threshold) mapped |= 1u << 13;
  }
  return mapped;
}

static void emit_menu_pad_input(const HidAnalogStickState *left_stick,
                                int connected, u64 buttons,
                                int have_left_stick) {
  const uint32_t mapped = menu_pad_buttons(buttons, left_stick,
                                           have_left_stick);
  const int32_t x = connected ? left_stick->x : 0;
  const int32_t y = connected ? left_stick->y : 0;
  const int32_t up = y < 0 ? -y : 0;
  const int32_t down = y > 0 ? y : 0;
  const int32_t left = x < 0 ? -x : 0;
  const int32_t right = x > 0 ? x : 0;
  cobra_pad_set_input(mapped, up, down, left, right, connected);
}

static void emit_virtual_cursor_pad_input(int connected, u64 buttons,
                                          int cursor_context) {
  u64 reserved = HidNpadButton_A | HidNpadButton_ZL | HidNpadButton_ZR;
  if (cursor_context == PES_VIRTUAL_CURSOR_PAUSE ||
      cursor_context == PES_VIRTUAL_CURSOR_GAMEPLAN ||
      cursor_context == PES_VIRTUAL_CURSOR_SET_PIECE_TAKER)
    reserved |= HidNpadButton_B;
  const uint32_t mapped = menu_pad_buttons(buttons & ~reserved, NULL, 0);
  cobra_pad_set_input(mapped, 0, 0, 0, 0, connected);
}

static void emit_replay_pad_input(int connected, uint32_t buttons) {
  cobra_pad_set_input(buttons, 0, 0, 0, 0, connected);
}

static uint64_t monotonic_ms(void) {
  return armTicksToNs(armGetSystemTick()) / 1000000ULL;
}

static void normalize_stick(const HidAnalogStickState *stick,
                            int connected, float *out_x, float *out_y) {
  if (!connected || (stick->x == 0 && stick->y == 0)) {
    *out_x = 0.0f;
    *out_y = 0.0f;
    return;
  }
  float x = connected ? (float)stick->x / (float)JOYSTICK_MAX : 0.0f;
  // Android's Y axis is positive downward; libnx is positive upward.
  float y = connected ? -(float)stick->y / (float)JOYSTICK_MAX : 0.0f;
  float magnitude = sqrtf(x * x + y * y);
  if (magnitude > 1.0f) {
    x /= magnitude;
    y /= magnitude;
    magnitude = 1.0f;
  }
  const float deadzone = 0.12f;
  if (magnitude <= deadzone) {
    x = 0.0f;
    y = 0.0f;
  } else {
    const float scale = (magnitude - deadzone) /
                        ((1.0f - deadzone) * magnitude);
    x *= scale;
    y *= scale;
  }

  *out_x = x;
  *out_y = y;
}

static int mobile_gameplay_context(int *out_mode) {
  const int mode = pes_mobile_control_active_mode();
  const int active = mode == PES_MOBILE_CONTROL_OFFENSE ||
                     mode == PES_MOBILE_CONTROL_DEFENSE;
  if (mode != previous_mobile_context_mode) {
    debugPrintf("input: mobile control context mode=%s\n",
                mode == PES_MOBILE_CONTROL_OFFENSE
                    ? "offense"
                    : mode == PES_MOBILE_CONTROL_DEFENSE ? "defense"
                                                         : "unknown");
    previous_mobile_context_mode = mode;
  }
  *out_mode = mode;
  return active;
}

static int surface_should_remain(uint64_t now_ms, uint64_t started_ms,
                                 int physical_held, uint64_t minimum_ms) {
  return physical_held || now_ms - started_ms < minimum_ms;
}

static void reset_virtual_surfaces(void) {
  memset(&pass_surface, 0, sizeof(pass_surface));
  memset(&through_surface, 0, sizeof(through_surface));
  memset(&shoot_surface, 0, sizeof(shoot_surface));
  memset(&pause_surface, 0, sizeof(pause_surface));
}

static int synthetic_context_changed(int context) {
  if (context == previous_synthetic_input_context)
    return 0;
  previous_synthetic_input_context = context;
  synthetic_input_generation++;
  reset_virtual_surfaces();
  replay_touch_requested = 0;
  previous_hid_buttons = 0;
  previous_hid_buttons_p2 = 0;
  compact_menu_tap_until_ms = 0;
  return 1;
}

static void append_virtual_gamepad_touches(FakeTouchState *desired,
                                           float axis_x, float axis_y,
                                           int connected, u64 buttons,
                                           int gameplay_active,
                                           int control_mode,
                                           const PesControllerSnapshot *ui,
                                           uint64_t now_ms) {
  const int b_held = connected && (buttons & HidNpadButton_B) != 0;
  const int x_held = connected && (buttons & HidNpadButton_X) != 0;
  const int y_held = connected && (buttons & HidNpadButton_Y) != 0;
  const int a_held = connected && (buttons & HidNpadButton_A) != 0;
  const int l_held = connected && (buttons & HidNpadButton_L) != 0;
  const int r_held = connected && (buttons & HidNpadButton_R) != 0;
  const int plus_held = connected && (buttons & HidNpadButton_Plus) != 0;
  const int b_pressed = b_held && !(previous_hid_buttons & HidNpadButton_B);
  const int x_pressed = x_held && !(previous_hid_buttons & HidNpadButton_X);
  const int y_pressed = y_held && !(previous_hid_buttons & HidNpadButton_Y);
  const int a_pressed = a_held && !(previous_hid_buttons & HidNpadButton_A);
  const int l_pressed = l_held && !(previous_hid_buttons & HidNpadButton_L);
  const int plus_pressed =
      plus_held && !(previous_hid_buttons & HidNpadButton_Plus);
  const uint32_t setplay_options = ui ? ui->setplay_options : 0;
  const uint32_t setplay_context = ui ? ui->setplay_context : PES_SETPLAY_NONE;
  int x_is_context = 0;
  int y_is_context = 0;
  switch (setplay_context) {
  case PES_SETPLAY_GOAL_KICK:
  case PES_SETPLAY_CORNER:
    x_is_context = 1;
    y_is_context = 1;
    break;
  case PES_SETPLAY_FREE_KICK:
    // ZR owns the taker picker and X owns Switch View. Y must remain a
    // regular Shoot input so free kicks retain their normal kick control.
    x_is_context = 1;
    break;
  case PES_SETPLAY_THROW_IN:
    // Only ZR is reserved for Select Thrower.
    break;
  default:
    // During short native transition frames the semantic context may not yet
    // be published. Preserve the old option-based reservation as a fallback.
    x_is_context =
        (setplay_options & (PES_SETPLAY_OPTION_TEAM_UP |
                            PES_SETPLAY_OPTION_KICKER |
                            PES_SETPLAY_OPTION_SHORT_CORNER)) != 0;
    y_is_context =
        (setplay_options & PES_SETPLAY_OPTION_CAMERA) != 0;
    break;
  }

  if (!connected || !gameplay_active) {
    reset_virtual_surfaces();
    return;
  }

  const float stick_center_x = (float)screen_width * 0.15156f;
  const float stick_center_y = (float)screen_height * 0.80278f;
  // PES applies a fixed pixel threshold before its virtual stick leaves the
  // dead zone. A purely scaled 576p gesture tops out too early, so retain the
  // calibrated 720p travel distance while still scaling the stick center.
  const float stick_radius =
      fmaxf((float)screen_height * 0.10417f, 75.0f);
  const float pass_x = (float)screen_width * 0.76875f;
  const float pass_y = (float)screen_height * 0.86944f;
  const float through_x = (float)screen_width * 0.80000f;
  const float through_y = (float)screen_height * 0.64444f;
  const float shoot_x = (float)screen_width * 0.92500f;
  const float shoot_y = (float)screen_height * 0.58889f;
  const float dash_x = (float)screen_width * 0.91563f;
  const float dash_y = (float)screen_height * 0.85000f;
  const float pause_x = (float)screen_width * 0.95625f;
  const float pause_y = (float)screen_height * 0.06944f;
  // 160-DPI gameplay threshold is about 44 px for Cross at 720p. Keep the
  // gesture safely above it while avoiding the neighboring Through surface.
  const float cross_distance = (float)screen_height * 0.10000f;

  // Opening Pause changes the meaning and ownership of the complete mobile
  // touch surface. Never send the pause icon together with a held stick,
  // dash, or action button: release the gameplay fingers for one poll first,
  // then emit the isolated pause tap on the next poll.
  if (pause_surface.owner == VIRTUAL_SURFACE_NONE && plus_pressed) {
    memset(&pass_surface, 0, sizeof(pass_surface));
    memset(&through_surface, 0, sizeof(through_surface));
    memset(&shoot_surface, 0, sizeof(shoot_surface));
    pause_surface.owner = VIRTUAL_SURFACE_BUTTON;
    pause_surface.started_ms = now_ms;
    pause_surface.moved = 0;
    return;
  }
  if (pause_surface.owner == VIRTUAL_SURFACE_BUTTON) {
    if (!surface_should_remain(now_ms, pause_surface.started_ms, plus_held,
                               80)) {
      memset(&pause_surface, 0, sizeof(pause_surface));
      return;
    }
    if (!pause_surface.moved) {
      pause_surface.moved = 1;
      return;
    }
    touch_state_append(desired, FAKE_POINTER_PAUSE, pause_x, pause_y);
    return;
  }

  static float stick_target_x;
  static float stick_target_y;
  static uint64_t stick_target_ms;
  const int stick_requested = fabsf(axis_x) > 0.001f ||
                              fabsf(axis_y) > 0.001f;
  if (stick_requested) {
    if (touch_state_find(&active_touch_state, FAKE_POINTER_STICK) < 0) {
      stick_target_x = stick_center_x;
      stick_target_y = stick_center_y;
      stick_target_ms = now_ms;
    } else if (now_ms - stick_target_ms >= 12) {
      stick_target_x = stick_center_x + axis_x * stick_radius;
      stick_target_y = stick_center_y + axis_y * stick_radius;
      stick_target_ms = now_ms;
    }
    touch_state_append(desired, FAKE_POINTER_STICK, stick_target_x,
                       stick_target_y);
  }

  // Physical screen slots change meaning with possession. On offense this
  // lower-left action slot is Pass/Cross (B/A); on defense it is Switch (L1).
  // Keep a single owner so two controller buttons never place two fingers on
  // the same Android ButtonObject.
  if (pass_surface.owner == VIRTUAL_SURFACE_NONE) {
    if (control_mode == PES_MOBILE_CONTROL_OFFENSE && a_pressed) {
      pass_surface.owner = VIRTUAL_SURFACE_CROSS;
      pass_surface.started_ms = now_ms;
      pass_surface.moved = 0;
    } else if ((control_mode == PES_MOBILE_CONTROL_OFFENSE && b_pressed) ||
               (control_mode == PES_MOBILE_CONTROL_DEFENSE && l_pressed)) {
      pass_surface.owner = VIRTUAL_SURFACE_BUTTON;
      pass_surface.started_ms = now_ms;
    }
  }
  if (pass_surface.owner == VIRTUAL_SURFACE_BUTTON &&
      now_ms - pass_surface.started_ms >= 96)
    memset(&pass_surface, 0, sizeof(pass_surface));
  if (pass_surface.owner == VIRTUAL_SURFACE_CROSS) {
    if (now_ms - pass_surface.started_ms >= 40)
      pass_surface.moved = 1;
    if (!surface_should_remain(now_ms, pass_surface.started_ms, a_held, 120))
      memset(&pass_surface, 0, sizeof(pass_surface));
  }
  if (pass_surface.owner != VIRTUAL_SURFACE_NONE) {
    const float y = pass_surface.owner == VIRTUAL_SURFACE_CROSS &&
                            pass_surface.moved
                        ? pass_y - cross_distance
                        : pass_y;
    touch_state_append(desired, FAKE_POINTER_PASS, pass_x, y);
  }

  // The middle-left action slot is Through (X) on offense and Press (B) on
  // defense. Select its source button from the authoritative control mode.
  if (through_surface.owner == VIRTUAL_SURFACE_NONE) {
    if ((control_mode == PES_MOBILE_CONTROL_OFFENSE && x_pressed &&
         !x_is_context) ||
        (control_mode == PES_MOBILE_CONTROL_DEFENSE && b_pressed)) {
      through_surface.owner = VIRTUAL_SURFACE_BUTTON;
      through_surface.started_ms = now_ms;
    }
  }
  const int through_button_held =
      control_mode == PES_MOBILE_CONTROL_OFFENSE
          ? (x_held && !x_is_context)
          : b_held;
  if (through_surface.owner == VIRTUAL_SURFACE_BUTTON &&
      !surface_should_remain(now_ms, through_surface.started_ms,
                             through_button_held, 80))
    memset(&through_surface, 0, sizeof(through_surface));
  if (through_surface.owner != VIRTUAL_SURFACE_NONE)
    touch_state_append(desired, FAKE_POINTER_THROUGH, through_x, through_y);

  // The top-right action slot is Shoot (Y) on offense and Tackle (A) on
  // defense. Tackle is a normal press in this Classic-control layout; the old
  // forced swipe was the reason A could select the wrong defensive action.
  if (shoot_surface.owner == VIRTUAL_SURFACE_NONE) {
    if ((control_mode == PES_MOBILE_CONTROL_OFFENSE && y_pressed &&
         !y_is_context) ||
        (control_mode == PES_MOBILE_CONTROL_DEFENSE && a_pressed)) {
      shoot_surface.owner = VIRTUAL_SURFACE_BUTTON;
      shoot_surface.started_ms = now_ms;
    }
  }
  const int shoot_button_held =
      control_mode == PES_MOBILE_CONTROL_OFFENSE
          ? (y_held && !y_is_context)
          : a_held;
  if (shoot_surface.owner == VIRTUAL_SURFACE_BUTTON &&
      !surface_should_remain(now_ms, shoot_surface.started_ms,
                             shoot_button_held, 80))
    memset(&shoot_surface, 0, sizeof(shoot_surface));
  if (shoot_surface.owner != VIRTUAL_SURFACE_NONE)
    touch_state_append(desired, FAKE_POINTER_SHOOT, shoot_x, shoot_y);

  if (r_held)
    touch_state_append(desired, FAKE_POINTER_DASH, dash_x, dash_y);

}

static void append_menu_controller_tap(FakeTouchState *desired, int a_pressed,
                                        uint64_t now_ms) {
  static uint64_t tap_until_ms;
  static uint32_t generation_seen;
  if (generation_seen != synthetic_input_generation) {
    generation_seen = synthetic_input_generation;
    tap_until_ms = 0;
  }
  if (a_pressed && tap_until_ms <= now_ms)
    tap_until_ms = now_ms + 90;
  if (tap_until_ms <= now_ms)
    return;

  float normalized_x = 0.0f;
  float normalized_y = 0.0f;
  if (pes_controller_menu_touch_target(&normalized_x, &normalized_y))
    touch_state_append(desired, FAKE_POINTER_MENU,
                       normalized_x * (float)screen_width,
                       normalized_y * (float)screen_height);
}

static void append_menu_controller_back(FakeTouchState *desired,
                                         int b_pressed, uint64_t now_ms) {
  static uint64_t back_until_ms;
  static uint32_t generation_seen;
  if (generation_seen != synthetic_input_generation) {
    generation_seen = synthetic_input_generation;
    back_until_ms = 0;
  }
  if (b_pressed && back_until_ms <= now_ms) {
    back_until_ms = now_ms + 90;
  }
  if (back_until_ms <= now_ms)
    return;

  float normalized_x = 0.0f;
  float normalized_y = 0.0f;
  if (pes_controller_menu_back_target(&normalized_x, &normalized_y))
    touch_state_append(desired, FAKE_POINTER_MENU_BACK,
                       normalized_x * (float)screen_width,
                       normalized_y * (float)screen_height);
}

static void append_menu_controller_scroll(FakeTouchState *desired,
                                           uint64_t now_ms) {
  static uint64_t scroll_started_ms;
  static int scroll_direction;
  static uint32_t generation_seen;
  if (generation_seen != synthetic_input_generation) {
    generation_seen = synthetic_input_generation;
    scroll_started_ms = 0;
    scroll_direction = 0;
  }
  // A gesture lasts several poll frames. Ask the controller bridge for the
  // next logical row only when the previous synthetic swipe has completed;
  // otherwise a multi-step custom popup scroll would consume all requests in
  // the first frame.
  const int request = scroll_started_ms == 0
                          ? pes_controller_menu_scroll_request()
                          : 0;
  if (request && scroll_started_ms == 0) {
    scroll_started_ms = now_ms;
    scroll_direction = request;
  }
  if (!scroll_started_ms)
    return;
  const uint64_t elapsed = now_ms - scroll_started_ms;
  if (elapsed >= 180) {
    scroll_started_ms = 0;
    return;
  }
  const float t = (float)elapsed / 180.0f;
  // Move roughly one visible row per D-pad press. The old .43 viewport
  // sweep made the native list skip several leagues at a time.
  const float start_y = scroll_direction > 0 ? 0.72f : 0.30f;
  const float end_y = scroll_direction > 0 ? 0.61f : 0.41f;
  const float y = (start_y + (end_y - start_y) * t) * (float)screen_height;
  touch_state_append(desired, FAKE_POINTER_MENU_SCROLL,
                     (float)screen_width * 0.50f, y);
}

static void append_virtual_cursor_controller(FakeTouchState *desired,
                                             float axis_x, float axis_y,
                                             int connected, u64 buttons,
                                             uint64_t now_ms, int cursor_context) {
  static uint64_t cursor_previous_ms;
  static uint64_t play_until_ms;
  static uint64_t back_until_ms;
  static uint32_t generation_seen;
  if (generation_seen != synthetic_input_generation) {
    generation_seen = synthetic_input_generation;
    cursor_previous_ms = 0;
    play_until_ms = 0;
    back_until_ms = 0;
  }
  float cursor_x = 0.5f;
  float cursor_y = 0.45f;
  if (!pes_controller_gameplan_cursor_position(&cursor_x, &cursor_y)) {
    cursor_previous_ms = 0;
    play_until_ms = 0;
    back_until_ms = 0;
    return;
  }

  uint64_t elapsed_ms = cursor_previous_ms ? now_ms - cursor_previous_ms : 0;
  if (elapsed_ms > 40)
    elapsed_ms = 40;
  cursor_previous_ms = now_ms;
  if (connected && elapsed_ms && screen_width > 0 && screen_height > 0) {
    const float cursor_speed = 780.0f;
    cursor_x += axis_x * cursor_speed * (float)elapsed_ms /
                (1000.0f * (float)screen_width);
    cursor_y += axis_y * cursor_speed * (float)elapsed_ms /
                (1000.0f * (float)screen_height);
    pes_controller_gameplan_cursor_set(cursor_x, cursor_y);
    pes_controller_gameplan_cursor_position(&cursor_x, &cursor_y);
  }

  const int a_pressed = connected && (buttons & HidNpadButton_A) != 0 &&
                        (previous_hid_buttons & HidNpadButton_A) == 0;
  const int pre_match_gameplan =
      cursor_context == PES_VIRTUAL_CURSOR_GAMEPLAN &&
      !pes_controller_gameplan_pause_route();
  const int cursor_held = connected &&
                          ((buttons & (HidNpadButton_ZL |
                                       HidNpadButton_ZR)) != 0 ||
                           ((cursor_context == PES_VIRTUAL_CURSOR_PAUSE ||
                             (cursor_context == PES_VIRTUAL_CURSOR_GAMEPLAN &&
                              !pre_match_gameplan)) &&
                            (buttons & HidNpadButton_A) != 0));
  const int b_pressed = connected && (buttons & HidNpadButton_B) != 0 &&
                        (previous_hid_buttons & HidNpadButton_B) == 0;
  if (b_pressed && back_until_ms <= now_ms) {
    if (cursor_context == PES_VIRTUAL_CURSOR_PAUSE)
      pes_controller_pause_back_request();
    if (cursor_context == PES_VIRTUAL_CURSOR_PAUSE ||
        cursor_context == PES_VIRTUAL_CURSOR_GAMEPLAN ||
        cursor_context == PES_VIRTUAL_CURSOR_SET_PIECE_TAKER)
      back_until_ms = now_ms + 90;
  }
  const int back_active = back_until_ms > now_ms;

  if (b_pressed && (cursor_context == PES_VIRTUAL_CURSOR_HALF_TIME ||
                    cursor_context == PES_VIRTUAL_CURSOR_HALF_PREVIEW ||
                    cursor_context == PES_VIRTUAL_CURSOR_FULL_TIME))
    pes_controller_result_input(PES_PAUSE_INPUT_BACK);
  if (a_pressed && cursor_context == PES_VIRTUAL_CURSOR_FULL_TIME)
    pes_controller_result_input(PES_PAUSE_INPUT_DECIDE);

  if (cursor_held && !back_active)
    touch_state_append(desired, FAKE_POINTER_GAMEPLAN_CURSOR,
                       cursor_x * (float)screen_width,
                       cursor_y * (float)screen_height);

  // The native kicker list has no reliable full-JoyCon footer on every
  // mobile build. A confirms the currently highlighted card directly under
  // the virtual cursor; B remains the Back action and ZL/ZR keep drag mode.
  if (a_pressed && cursor_context == PES_VIRTUAL_CURSOR_SET_PIECE_TAKER &&
      !back_active && play_until_ms <= now_ms) {
    play_until_ms = now_ms + 90;
    touch_state_append(desired, FAKE_POINTER_GAMEPLAN_PLAY,
                       cursor_x * (float)screen_width,
                       cursor_y * (float)screen_height);
  }

  if (a_pressed && play_until_ms <= now_ms &&
      cursor_context != PES_VIRTUAL_CURSOR_PAUSE &&
      cursor_context != PES_VIRTUAL_CURSOR_SET_PIECE_TAKER &&
      cursor_context != PES_VIRTUAL_CURSOR_FULL_TIME &&
      (cursor_context != PES_VIRTUAL_CURSOR_GAMEPLAN ||
       pre_match_gameplan))
    play_until_ms = now_ms + 90;
  if (back_active && (cursor_context == PES_VIRTUAL_CURSOR_GAMEPLAN ||
                      cursor_context == PES_VIRTUAL_CURSOR_SET_PIECE_TAKER))
    touch_state_append(desired, FAKE_POINTER_GAMEPLAN_PLAY,
                       0.055f * (float)screen_width,
                       0.944f * (float)screen_height);
  else if (!back_active && play_until_ms > now_ms)
    touch_state_append(desired, FAKE_POINTER_GAMEPLAN_PLAY,
                       0.865f * (float)screen_width,
                       0.944f * (float)screen_height);
}

static void append_pause_camera_swipe(FakeTouchState *desired,
                                      int connected, u64 buttons,
                                      uint64_t now_ms) {
  static uint64_t until_ms;
  static float start_x;
  static float end_x;
  static uint32_t generation_seen;
  if (generation_seen != synthetic_input_generation) {
    generation_seen = synthetic_input_generation;
    until_ms = 0;
  }
  if (!connected || !pes_controller_pause_camera_active()) {
    until_ms = 0;
    return;
  }
  const u64 pressed = buttons & ~previous_hid_buttons;
  if (pressed & (HidNpadButton_Left | HidNpadButton_Right)) {
    // Keep the virtual gesture and the visible page indicator aligned with
    // the D-pad direction.
    const int right = (pressed & HidNpadButton_Right) != 0;
    start_x = right ? 0.18f : 0.48f;
    end_x = right ? 0.48f : 0.18f;
    until_ms = now_ms + 220;
  }
  if (until_ms > now_ms) {
    const float progress =
        1.0f - (float)(until_ms - now_ms) / 220.0f;
    const float x = start_x + (end_x - start_x) * progress;
    touch_state_append(desired, FAKE_POINTER_CAMERA,
                       x * (float)screen_width, 0.52f * (float)screen_height);
  }
}

static void queue_native_setplay_action(const PesControllerSnapshot *ui,
                                        int connected, u64 buttons) {
  if (!ui || !connected ||
      ui->surface != PES_CONTROLLER_SURFACE_SETPLAY)
    return;
  const u64 pressed = buttons & ~previous_hid_buttons;
  uint32_t action = 0;
  switch (ui->setplay_context) {
  case PES_SETPLAY_GOAL_KICK:
    if (pressed & HidNpadButton_Y)
      action = PES_SETPLAY_BUTTON_POSITION_SHIFT;
    else if (pressed & HidNpadButton_X)
      action = PES_SETPLAY_BUTTON_SWITCH_VIEW;
    break;
  case PES_SETPLAY_CORNER:
    if (pressed & HidNpadButton_ZR)
      action = PES_SETPLAY_BUTTON_SET_PIECE_TAKER;
    else if (pressed & HidNpadButton_X)
      action = PES_SETPLAY_BUTTON_SHORT_CORNER;
    else if (pressed & HidNpadButton_Y)
      action = PES_SETPLAY_BUTTON_SWITCH_VIEW;
    break;
  case PES_SETPLAY_FREE_KICK:
    if (pressed & HidNpadButton_ZR)
      action = PES_SETPLAY_BUTTON_SET_PIECE_TAKER;
    else if (pressed & HidNpadButton_X)
      action = PES_SETPLAY_BUTTON_SWITCH_VIEW;
    break;
  case PES_SETPLAY_THROW_IN:
    if (pressed & HidNpadButton_ZR)
      action = PES_SETPLAY_BUTTON_SELECT_THROWER;
    break;
  default:
    break;
  }
  if (action && (ui->setplay_button_mask & (1u << action)))
    pes_controller_setplay_request(action, ui->generation);
}

static void queue_native_lab_setplay_action(const PesControllerSnapshot *ui,
                                            int connected, u64 buttons,
                                            u64 previous_buttons) {
  if (!ui || !connected ||
      ui->surface != PES_CONTROLLER_SURFACE_SETPLAY)
    return;
  const u64 pressed = buttons & ~previous_buttons;
  if (!(pressed & HidNpadButton_Right))
    return;
  if ((ui->setplay_context == PES_SETPLAY_CORNER ||
       ui->setplay_context == PES_SETPLAY_FREE_KICK) &&
      (ui->setplay_button_mask &
       (1u << PES_SETPLAY_BUTTON_SET_PIECE_TAKER)))
    pes_controller_setplay_request(PES_SETPLAY_BUTTON_SET_PIECE_TAKER,
                                   ui->generation);
}

static void queue_set_piece_selector_input(int connected, u64 buttons,
                                           u64 previous_buttons,
                                           float axis_x, float axis_y,
                                           uint64_t now_ms) {
  static uint32_t generation_seen;
  static uint32_t held_direction;
  static uint64_t repeat_at_ms;
  if (generation_seen != synthetic_input_generation) {
    generation_seen = synthetic_input_generation;
    held_direction = 0;
    repeat_at_ms = 0;
  }
  if (!connected) {
    held_direction = 0;
    repeat_at_ms = 0;
    return;
  }

  const u64 pressed = buttons & ~previous_buttons;
  if (pressed & HidNpadButton_B) {
    held_direction = 0;
    repeat_at_ms = 0;
    pes_controller_set_piece_selector_input(PES_PAUSE_INPUT_BACK);
    return;
  }
  if (pressed & HidNpadButton_A) {
    held_direction = 0;
    repeat_at_ms = 0;
    pes_controller_set_piece_selector_input(PES_PAUSE_INPUT_DECIDE);
    return;
  }

  uint32_t direction = 0;
  const u64 vertical = buttons & (HidNpadButton_Up | HidNpadButton_Down);
  if (vertical == HidNpadButton_Up)
    direction = PES_PAUSE_INPUT_UP;
  else if (vertical == HidNpadButton_Down)
    direction = PES_PAUSE_INPUT_DOWN;
  else {
    const float threshold = 0.55f;
    if (fabsf(axis_y) >= fabsf(axis_x) && axis_y <= -threshold)
      direction = PES_PAUSE_INPUT_UP;
    else if (fabsf(axis_y) >= fabsf(axis_x) && axis_y >= threshold)
      direction = PES_PAUSE_INPUT_DOWN;
  }

  if (!direction) {
    held_direction = 0;
    repeat_at_ms = 0;
    return;
  }
  if (direction != held_direction) {
    held_direction = direction;
    repeat_at_ms = now_ms + 280;
    pes_controller_set_piece_selector_input(direction);
  } else if (now_ms >= repeat_at_ms) {
    repeat_at_ms = now_ms + 110;
    pes_controller_set_piece_selector_input(direction);
  }
}

static uint32_t append_replay_controller(FakeTouchState *desired,
                                         int connected, u64 buttons,
                                         u64 previous_buttons,
                                         uint64_t now_ms) {
  (void)desired;
  static uint64_t skip_until_ms;
  static uint32_t generation_seen;
  if (generation_seen != synthetic_input_generation) {
    generation_seen = synthetic_input_generation;
    skip_until_ms = 0;
  }

  replay_touch_requested = 0;
  if (!connected) {
    skip_until_ms = 0;
    return 0;
  }

  const u64 pressed = buttons & ~previous_buttons;
  if (pressed && skip_until_ms <= now_ms) {
    skip_until_ms = now_ms + 90;
    pes_controller_replay_feedback_set(
        (pressed & HidNpadButton_A) ? PES_REPLAY_FEEDBACK_A_SKIP
                                   : PES_REPLAY_FEEDBACK_SKIP);
  }
  return skip_until_ms > now_ms ? (1u << 25) : 0;
}

static uint32_t append_goal_demo_controller(FakeTouchState *desired,
                                            int connected, u64 buttons,
                                            u64 previous_buttons,
                                            int player_goal,
                                            uint64_t now_ms) {
  static uint64_t action_until_ms;
  static uint64_t skip_until_ms;
  static float action_x;
  static float action_y;
  static uint32_t generation_seen;
  if (generation_seen != synthetic_input_generation) {
    generation_seen = synthetic_input_generation;
    action_until_ms = 0;
    skip_until_ms = 0;
  }
  replay_touch_requested = 0;
  if (!connected)
    return 0;

  const u64 pressed = buttons & ~previous_buttons;
  if ((pressed & HidNpadButton_B) && skip_until_ms <= now_ms) {
    // GoalDemo's left helper is Skip. Also publish Cobra button 25 because
    // the native minimum-time gate consumes that path on some demo variants.
    action_x = 0.891f;
    action_y = 0.206f;
    action_until_ms = now_ms + 90;
    skip_until_ms = now_ms + 90;
    // Opponent-goal and other skip-only variants are also backed by a native
    // ThinkUnitSkip. Queue its exact command alongside the stock goal touch.
    pes_controller_demo_skip_request();
    pes_controller_goal_demo_consume();
    pes_controller_replay_feedback_set(PES_REPLAY_FEEDBACK_B_SKIP);
  } else if (player_goal && (pressed & HidNpadButton_A) &&
             action_until_ms <= now_ms) {
    action_x = 0.891f;
    action_y = 0.344f;
    action_until_ms = now_ms + 90;
    pes_controller_goal_demo_consume();
    pes_controller_replay_feedback_set(
        PES_REPLAY_FEEDBACK_GOAL_CELEBRATION);
  }
  if (action_until_ms > now_ms) {
    touch_state_append(desired, FAKE_POINTER_GOAL_DEMO,
                       action_x * (float)screen_width,
                        action_y * (float)screen_height);
    replay_touch_requested = 1;
  }
  return skip_until_ms > now_ms ? (1u << 25) : 0;
}

static uint32_t append_cinematic_skip_controller(FakeTouchState *desired,
                                                 int connected, u64 buttons,
                                                 u64 previous_buttons,
                                                 uint64_t now_ms) {
  (void)desired;
  (void)now_ms;
  replay_touch_requested = 0;
  if (!connected)
    return 0;
  const u64 pressed = buttons & ~previous_buttons;
  if (pressed) {
    pes_controller_demo_skip_request();
    pes_controller_replay_feedback_set(
        (pressed & HidNpadButton_A) ? PES_REPLAY_FEEDBACK_A_SKIP
                                   : PES_REPLAY_FEEDBACK_SKIP);
  }
  return 0;
}

static void append_penalty_controller(FakeTouchState *desired,
                                      int connected, u64 buttons,
                                      float left_x, float left_y,
                                      float right_x, float right_y,
                                      uint32_t role, uint64_t now_ms) {
  (void)right_x;
  (void)right_y;
  static uint32_t generation_seen;
  static uint64_t swipe_started_ms;
  static uint64_t swipe_until_ms;
  static float swipe_start_x;
  static float swipe_start_y;
  static float swipe_end_x;
  static float swipe_end_y;
  static int keeper_stick_armed = 1;
  if (generation_seen != synthetic_input_generation) {
    generation_seen = synthetic_input_generation;
    swipe_started_ms = 0;
    swipe_until_ms = 0;
    keeper_stick_armed = 1;
  }
  if (!connected || role == PES_PENALTY_NONE) {
    swipe_started_ms = 0;
    swipe_until_ms = 0;
    keeper_stick_armed = 1;
    return;
  }

  const u64 pressed = buttons & ~previous_hid_buttons;
  float direction_x = 0.0f;
  float direction_y = -1.0f;
  int begin_swipe = 0;
  if (role == PES_PENALTY_KICKER &&
      (pressed & HidNpadButton_Y) && swipe_until_ms <= now_ms) {
    const float magnitude = sqrtf(left_x * left_x + left_y * left_y);
    if (magnitude >= 0.20f) {
      direction_x = left_x / magnitude;
      direction_y = left_y / magnitude;
    }
    begin_swipe = 1;
  } else if (role == PES_PENALTY_GOALKEEPER) {
    const float magnitude = sqrtf(left_x * left_x + left_y * left_y);
    if (magnitude <= 0.24f)
      keeper_stick_armed = 1;
    if (keeper_stick_armed && magnitude >= 0.55f &&
        swipe_until_ms <= now_ms) {
      direction_x = left_x / magnitude;
      direction_y = left_y / magnitude;
      keeper_stick_armed = 0;
      begin_swipe = 1;
    }
  }

  if (begin_swipe) {
    // MobilePenaltyKick consumes ScreenTapInfo ButtonKind 0x10 and derives
    // both target height/side and goalkeeper saving angle from the gesture.
    // The kicker listens on the tutorial's right-hand gesture area.  The
    // goalkeeper variant is different: its native hit test requires DOWN to
    // begin on the goalkeeper model before the directional flick.
    if (role == PES_PENALTY_GOALKEEPER) {
      swipe_start_x = 0.50f;
      swipe_start_y = 0.40f;
      swipe_end_x = fmaxf(0.20f, fminf(0.80f,
                                      swipe_start_x + direction_x * 0.30f));
      swipe_end_y = fmaxf(0.12f, fminf(0.76f,
                                      swipe_start_y + direction_y * 0.32f));
    } else {
      swipe_start_x = 0.78f;
      swipe_start_y = 0.72f;
      swipe_end_x = fmaxf(0.56f, fminf(0.96f,
                                      swipe_start_x + direction_x * 0.22f));
      swipe_end_y = fmaxf(0.20f, fminf(0.90f,
                                      swipe_start_y + direction_y * 0.34f));
    }
    swipe_started_ms = now_ms;
    swipe_until_ms = now_ms + 170;
  }

  if (swipe_until_ms > now_ms) {
    const uint64_t elapsed = now_ms - swipe_started_ms;
    // A short stationary DOWN makes the subsequent MOVE a deterministic
    // native swipe instead of a one-frame tap on slower hardware frames.
    const float progress =
        elapsed <= 24 ? 0.0f
                      : fminf(1.0f, (float)(elapsed - 24) / 120.0f);
    const float x = swipe_start_x + (swipe_end_x - swipe_start_x) * progress;
    const float y = swipe_start_y + (swipe_end_y - swipe_start_y) * progress;
    touch_state_append(desired, FAKE_POINTER_PENALTY,
                       x * (float)screen_width, y * (float)screen_height);
  }
}

#ifdef DEBUG_LOG
static void log_controller_input(const HidAnalogStickState *stick,
                                 int connected, u64 buttons, float x,
                                 float y, int gameplay_active,
                                 int control_mode) {
  static u64 previous_buttons;
  static unsigned int input_log_count;
  const int changed = !previous_left_axis_valid ||
                      fabsf(x - previous_left_axis_x) >= 0.04f ||
                      fabsf(y - previous_left_axis_y) >= 0.04f ||
                      buttons != previous_buttons;
  if (changed && input_log_count < 192) {
    input_log_count++;
    debugPrintf("input: virtual gamepad hid=0x%llx stick=%d,%d "
                "axis=%.3f,%.3f connected=%d gameplay=%d mode=%d\n",
                (unsigned long long)buttons, connected ? stick->x : 0,
                connected ? stick->y : 0, x, y, connected,
                gameplay_active, control_mode);
  }
  previous_left_axis_x = x;
  previous_left_axis_y = y;
  previous_left_axis_valid = 1;
  previous_buttons = buttons;
}
#endif

static void disable_native_pad_bridge(void) {
  // PES Mobile consumes Android/native-pad events before its touch ThinkUnits.
  // Keep the old diagnostic hook inert so the original mobile cursor remains
  // on the touchscreen route used by the virtual controller below.
  cobra_pad_clear_native_inputs();
}

#if 0
// Retained as documentation of the rejected global native-pad mapping.
static void emit_cobra_pad_input(const HidAnalogStickState *stick,
                                 int connected, u64 buttons) {

  // Cobra's raw layout is positional: bottom/top/left/right are bits 0/3/2/1.
  // This gives the requested Switch mapping while leaving offense/defense
  // context to PES: B=Pass, X=Through, Y=Shoot, A=Cross/Sliding.
  uint32_t cobra_buttons = 0;
  if (buttons & HidNpadButton_B)      cobra_buttons |= 1u << 0;
  if (buttons & HidNpadButton_A)      cobra_buttons |= 1u << 1;
  if (buttons & HidNpadButton_Y)      cobra_buttons |= 1u << 2;
  if (buttons & HidNpadButton_X)      cobra_buttons |= 1u << 3;
  if (buttons & HidNpadButton_L)      cobra_buttons |= 1u << 4;
  if (buttons & HidNpadButton_ZL)     cobra_buttons |= 1u << 5;
  if (buttons & HidNpadButton_StickL) cobra_buttons |= 1u << 6;
  if (buttons & HidNpadButton_R)      cobra_buttons |= 1u << 7;
  if (buttons & HidNpadButton_ZR)     cobra_buttons |= 1u << 8;
  if (buttons & HidNpadButton_StickR) cobra_buttons |= 1u << 9;
  if (buttons & HidNpadButton_Up)     cobra_buttons |= 1u << 10;
  if (buttons & HidNpadButton_Down)   cobra_buttons |= 1u << 11;
  if (buttons & HidNpadButton_Left)   cobra_buttons |= 1u << 12;
  if (buttons & HidNpadButton_Right)  cobra_buttons |= 1u << 13;
  if (buttons & HidNpadButton_Plus)   cobra_buttons |= 1u << 14;
  if (buttons & HidNpadButton_Minus)  cobra_buttons |= 1u << 15;

  const int32_t up = y < 0.0f ? (int32_t)(-y * 32767.0f + 0.5f) : 0;
  const int32_t down = y > 0.0f ? (int32_t)(y * 32767.0f + 0.5f) : 0;
  const int32_t left = x < 0.0f ? (int32_t)(-x * 32767.0f + 0.5f) : 0;
  const int32_t right = x > 0.0f ? (int32_t)(x * 32767.0f + 0.5f) : 0;
  cobra_pad_set_input(cobra_buttons, up, down, left, right, connected);

  static uint32_t previous_cobra_buttons;
  static unsigned int input_log_count;
  const int changed = !previous_left_axis_valid ||
                      fabsf(x - previous_left_axis_x) >= 0.002f ||
                      fabsf(y - previous_left_axis_y) >= 0.002f ||
                      cobra_buttons != previous_cobra_buttons;
  if (changed && input_log_count < 48) {
    input_log_count++;
    debugPrintf("input: cobra pad hid=0x%llx mask=0x%x "
                "stick=%d,%d axis=%.3f,%.3f raw=%d,%d,%d,%d "
                "connected=%d\n",
                (unsigned long long)buttons, cobra_buttons,
                connected ? stick->x : 0, connected ? stick->y : 0, x, y,
                up, down, left, right, connected);
  }
  previous_left_axis_x = x;
  previous_left_axis_y = y;
  previous_left_axis_valid = 1;
  previous_cobra_buttons = cobra_buttons;
}
#endif

// Only the dedicated native lab uses Cobra/PadInput for gameplay.
// Normal Exhibition stays on the calibrated multi-touch mapper above.
static void emit_native_lab_pad_input(uint32_t port,
                                      const HidAnalogStickState *left_stick,
                                      const HidAnalogStickState *right_stick,
                                      int connected, u64 buttons) {
  uint32_t mapped = 0;
  if (buttons & HidNpadButton_B) mapped |= 1u << 0;
  if (buttons & HidNpadButton_A) mapped |= 1u << 1;
  if (buttons & HidNpadButton_Y) mapped |= 1u << 2;
  if (buttons & HidNpadButton_X) mapped |= 1u << 3;
  if (buttons & (HidNpadButton_L | HidNpadButton_AnySL)) mapped |= 1u << 4;
  if (buttons & HidNpadButton_ZL) mapped |= 1u << 5;
  if (buttons & HidNpadButton_StickL) mapped |= 1u << 6;
  if (buttons & (HidNpadButton_R | HidNpadButton_AnySR)) mapped |= 1u << 7;
  if (buttons & HidNpadButton_ZR) mapped |= 1u << 8;
  if (buttons & HidNpadButton_StickR) mapped |= 1u << 9;
  if (buttons & HidNpadButton_Up) mapped |= 1u << 10;
  if (buttons & HidNpadButton_Down) mapped |= 1u << 11;
  if (buttons & HidNpadButton_Left) mapped |= 1u << 12;
  if (buttons & HidNpadButton_Right) mapped |= 1u << 13;
  if (buttons & HidNpadButton_Plus) mapped |= 1u << 14;
  if (buttons & HidNpadButton_Minus) mapped |= 1u << 15;

  const int32_t x = connected ? left_stick->x : 0;
  const int32_t y = connected ? left_stick->y : 0;
  const int32_t right_x = connected ? right_stick->x : 0;
  const int32_t right_y = connected ? right_stick->y : 0;
  // Switch raw +Y is up; Cobra stores up as a negative combined axis.
  const int32_t up = y > 0 ? y : 0;
  const int32_t down = y < 0 ? -y : 0;
  const int32_t left = x < 0 ? -x : 0;
  const int32_t right = x > 0 ? x : 0;
  const int32_t right_up = right_y > 0 ? right_y : 0;
  const int32_t right_down = right_y < 0 ? -right_y : 0;
  const int32_t right_left = right_x < 0 ? -right_x : 0;
  const int32_t right_right = right_x > 0 ? right_x : 0;
  pes_controller_native_pad_lab_debug_input(port, mapped, x, y,
                                             right_x, right_y, connected);
  cobra_pad_set_native_input_for_port(
      port, mapped, up, down, left, right,
      right_up, right_down, right_left, right_right, connected);
}

void android_input_poll(void) {
  // libnx aborts inside padUpdate when HID has already been torn down by a
  // game-side exit request. Read the valid shared-memory slots directly and
  // treat unavailable HID as no input so the original shutdown cause survives.
  if (!hidGetSharedmemAddr()) {
    static int warned;
    if (!warned++)
      debugPrintf("input: HID shared memory unavailable; polling disabled\n");
    previous_left_axis_x = 0.0f;
    previous_left_axis_y = 0.0f;
    previous_left_axis_valid = 0;
    previous_hid_buttons = 0;
    previous_hid_buttons_p2 = 0;
    physical_touch_tracking = 0;
    replay_touch_requested = 0;
    pes_controller_native_hid_connection_update(0);
    reset_virtual_surfaces();
    FakeTouchState empty = {0};
    reconcile_touch_state(&empty);
    disable_native_pad_bridge();
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
  u64 buttons_p2 = 0;
  HidAnalogStickState left_stick = {0};
  HidAnalogStickState right_stick = {0};
  HidAnalogStickState left_stick_p2 = {0};
  HidAnalogStickState right_stick_p2 = {0};
  int have_left_stick = 0;
  int have_right_stick = 0;
  int have_left_stick_p2 = 0;
  int have_right_stick_p2 = 0;
  int controller_slot_connected = 0;
  int controller_slot_connected_p2 = 0;
  if (hidGetNpadStatesFullKey(HidNpadIdType_No1, &state, 1) &&
      (state.attributes & HidNpadAttribute_IsConnected)) {
    controller_slot_connected = 1;
    merge_npad_state(&state, &buttons, &left_stick, &have_left_stick,
                     &right_stick, &have_right_stick);
  }
  if (hidGetNpadStatesJoyDual(HidNpadIdType_No1, &state, 1) &&
      (state.attributes & HidNpadAttribute_IsConnected)) {
    controller_slot_connected = 1;
    merge_npad_state(&state, &buttons, &left_stick, &have_left_stick,
                     &right_stick, &have_right_stick);
  }
  if (hidGetNpadStatesJoyLeft(HidNpadIdType_No1, &state, 1) &&
      (state.attributes & HidNpadAttribute_IsConnected)) {
    controller_slot_connected = 1;
    merge_npad_state(&state, &buttons, &left_stick, &have_left_stick,
                     &right_stick, &have_right_stick);
  }
  if (hidGetNpadStatesJoyRight(HidNpadIdType_No1, &state, 1) &&
      (state.attributes & HidNpadAttribute_IsConnected)) {
    controller_slot_connected = 1;
    merge_npad_state(&state, &buttons, &left_stick, &have_left_stick,
                     &right_stick, &have_right_stick);
  }
  if (hidGetNpadStatesHandheld(HidNpadIdType_Handheld, &state, 1) &&
      (state.attributes & HidNpadAttribute_IsConnected)) {
    controller_slot_connected = 1;
    merge_npad_state(&state, &buttons, &left_stick, &have_left_stick,
                     &right_stick, &have_right_stick);
  }
  if (hidGetNpadStatesFullKey(HidNpadIdType_No2, &state, 1) &&
      (state.attributes & HidNpadAttribute_IsConnected)) {
    controller_slot_connected_p2 = 1;
    merge_npad_state(&state, &buttons_p2, &left_stick_p2,
                     &have_left_stick_p2, &right_stick_p2,
                     &have_right_stick_p2);
  }
  if (hidGetNpadStatesJoyDual(HidNpadIdType_No2, &state, 1) &&
      (state.attributes & HidNpadAttribute_IsConnected)) {
    controller_slot_connected_p2 = 1;
    merge_npad_state(&state, &buttons_p2, &left_stick_p2,
                     &have_left_stick_p2, &right_stick_p2,
                     &have_right_stick_p2);
  }
  if (hidGetNpadStatesJoyLeft(HidNpadIdType_No2, &state, 1) &&
      (state.attributes & HidNpadAttribute_IsConnected)) {
    controller_slot_connected_p2 = 1;
    merge_npad_state(&state, &buttons_p2, &left_stick_p2,
                     &have_left_stick_p2, &right_stick_p2,
                     &have_right_stick_p2);
  }
  if (hidGetNpadStatesJoyRight(HidNpadIdType_No2, &state, 1) &&
      (state.attributes & HidNpadAttribute_IsConnected)) {
    controller_slot_connected_p2 = 1;
    merge_npad_state(&state, &buttons_p2, &left_stick_p2,
                     &have_left_stick_p2, &right_stick_p2,
                     &have_right_stick_p2);
  }
  pes_controller_native_hid_connection_update(
      (controller_slot_connected ? 1u : 0u) |
      (controller_slot_connected_p2 ? 2u : 0u));

  float axis_x = 0.0f;
  float axis_y = 0.0f;
  float right_axis_x = 0.0f;
  float right_axis_y = 0.0f;
  float axis_x_p2 = 0.0f;
  float axis_y_p2 = 0.0f;
  float right_axis_x_p2 = 0.0f;
  float right_axis_y_p2 = 0.0f;
  normalize_stick(&left_stick, have_left_stick, &axis_x, &axis_y);
  normalize_stick(&right_stick, have_right_stick, &right_axis_x,
                  &right_axis_y);
  normalize_stick(&left_stick_p2, have_left_stick_p2, &axis_x_p2,
                  &axis_y_p2);
  normalize_stick(&right_stick_p2, have_right_stick_p2,
                  &right_axis_x_p2, &right_axis_y_p2);
  const int controller_connected = controller_slot_connected;
  const int controller_connected_p2 = controller_slot_connected_p2;
  const uint64_t now_ms = monotonic_ms();
  int control_mode = 0;
  const int gameplay_active = mobile_gameplay_context(&control_mode);
  const int native_pad_lab_active =
      pes_controller_native_pad_lab_active();
  const int set_piece_selector_active =
      pes_controller_set_piece_selector_active();
  static int set_piece_selector_release_pending;
  if (set_piece_selector_active) {
    set_piece_selector_release_pending = 1;
  } else if (set_piece_selector_release_pending) {
    // Do not leak the button that opened/closed the picker into gameplay or
    // ButtonSetplay after the synthetic context changes. Require a complete
    // controller release, including X/Y/ZR and the shoulder buttons.
    if (!buttons && !buttons_p2 && fabsf(axis_x) < 0.55f &&
        fabsf(axis_y) < 0.55f && fabsf(axis_x_p2) < 0.55f &&
        fabsf(axis_y_p2) < 0.55f)
      set_piece_selector_release_pending = 0;
  }
  const int set_piece_selector_isolated =
      set_piece_selector_active || set_piece_selector_release_pending;
  const int inmatch_tutorial_active =
      pes_controller_inmatch_tutorial_active();
  static int inmatch_tutorial_release_pending;
  if (inmatch_tutorial_active) {
    inmatch_tutorial_release_pending = 1;
  } else if (inmatch_tutorial_release_pending && !buttons &&
             fabsf(axis_x) < 0.30f && fabsf(axis_y) < 0.30f &&
             fabsf(right_axis_x) < 0.30f &&
             fabsf(right_axis_y) < 0.30f) {
    inmatch_tutorial_release_pending = 0;
  }
  const int inmatch_tutorial_isolated =
      inmatch_tutorial_active || inmatch_tutorial_release_pending;
  const int pause_camera_active = pes_controller_pause_camera_active();
  const int custom_prematch_gameplan_active =
      pes_controller_custom_prematch_gameplan_active();
  const int custom_postmatch_active =
      pes_controller_custom_postmatch_active();
  const int main_menu_controller_active = pes_main_menu_controller_active();
  const int menu_controller_active = pes_controller_menu_active();
  if (gameplay_active || main_menu_controller_active)
    pes_controller_result_cursor_clear();
  const int cursor_context = pes_controller_virtual_cursor_context();
  const int cursor_active = cursor_context != PES_VIRTUAL_CURSOR_NONE;
  const uint32_t penalty_role = pes_controller_penalty_role();
  const int penalty_active = penalty_role != PES_PENALTY_NONE;
  PesControllerSnapshot controller_snapshot;
  pes_controller_surface_snapshot(&controller_snapshot);
  if (native_pad_lab_active &&
      controller_snapshot.surface == PES_CONTROLLER_SURFACE_SETPLAY) {
    PesNativePadLabDebug native_debug = {0};
    pes_controller_native_pad_lab_debug_snapshot(&native_debug);
    if (native_debug.context != PES_SETPLAY_NONE)
      native_setplay_owner_pad = native_debug.setplay_pad == 1 ? 1u : 0u;
  }
  const int replay_active =
      controller_snapshot.surface == PES_CONTROLLER_SURFACE_REPLAY;
  const int goal_demo_active =
      controller_snapshot.surface == PES_CONTROLLER_SURFACE_GOAL_DEMO;
  const int generic_cinematic_active =
      controller_snapshot.surface == PES_CONTROLLER_SURFACE_CINEMATIC;
  const uint32_t setplay_context = controller_snapshot.setplay_context;
  pes_controller_native_pad_lab_publish_setplay_context(
      native_pad_lab_active &&
              controller_snapshot.surface == PES_CONTROLLER_SURFACE_SETPLAY
          ? setplay_context
          : PES_SETPLAY_NONE);
  const int cinematic_active = goal_demo_active || replay_active ||
                               generic_cinematic_active;
  int synthetic_context = SYNTHETIC_INPUT_NONE;
  if (set_piece_selector_isolated)
    synthetic_context = SYNTHETIC_INPUT_SET_PIECE_SELECTOR;
  else if (inmatch_tutorial_isolated)
    synthetic_context = SYNTHETIC_INPUT_TUTORIAL;
  else if (replay_active)
    synthetic_context = SYNTHETIC_INPUT_REPLAY;
  else if (goal_demo_active)
    synthetic_context = SYNTHETIC_INPUT_GOAL_DEMO;
  else if (generic_cinematic_active)
    synthetic_context = SYNTHETIC_INPUT_REPLAY;
  else if (penalty_active)
    synthetic_context = SYNTHETIC_INPUT_PENALTY_BASE + (int)penalty_role;
  else if (cursor_active)
    synthetic_context = SYNTHETIC_INPUT_CURSOR_BASE + cursor_context;
  else if (controller_snapshot.surface == PES_CONTROLLER_SURFACE_SETPLAY)
    synthetic_context = SYNTHETIC_INPUT_SETPLAY_BASE + setplay_context;
  else if (gameplay_active)
    synthetic_context = SYNTHETIC_INPUT_GAMEPLAY;
  else if (menu_controller_active)
    synthetic_context = SYNTHETIC_INPUT_MENU;
  const int context_changed = synthetic_context_changed(synthetic_context);
  pes_controller_friend_press_update(
      !native_pad_lab_active && controller_connected && !context_changed &&
          synthetic_context == SYNTHETIC_INPUT_GAMEPLAY &&
          control_mode == PES_MOBILE_CONTROL_DEFENSE &&
          (buttons & HidNpadButton_Y) && !(buttons & HidNpadButton_Plus),
      now_ms);
  const int replay_pointer_was_active = replay_touch_requested;
  if (!cinematic_active)
    replay_touch_requested = 0;
  const int gameplan_cursor_active = !set_piece_selector_isolated &&
                                     !inmatch_tutorial_isolated &&
                                     !penalty_active &&
                                     !cinematic_active && cursor_active;

  HidTouchScreenState touch_state;
  memset(&touch_state, 0, sizeof(touch_state));
  const int has_touch = hidGetTouchScreenStates(&touch_state, 1) > 0 &&
                        touch_state.count > 0;
  const HidTouchState *touch = has_touch ? &touch_state.touches[0] : NULL;
  const int ended = touch && (touch->attributes & HidTouchAttribute_End);
  const int physical_active = has_touch && !ended;
  const float touch_x =
      touch ? (float)touch->x * (float)screen_width / 1280.0f : 0.0f;
  const float touch_y =
      touch ? (float)touch->y * (float)screen_height / 720.0f : 0.0f;
  const int physical_was_active =
      touch_state_find(&active_touch_state, FAKE_POINTER_PHYSICAL) >= 0;
  const int compact_main_menu_active = main_menu_controller_active;
  if (set_piece_selector_isolated) {
    physical_touch_tracking = 0;
  } else if (physical_active) {
    physical_touch_last_x = touch_x;
    physical_touch_last_y = touch_y;
    if (!physical_touch_tracking) {
      physical_touch_start_x = touch_x;
      physical_touch_start_y = touch_y;
      physical_touch_tracking = 1;
    }
  } else if (ended) {
    physical_touch_last_x = touch_x;
    physical_touch_last_y = touch_y;
  }

  if (!set_piece_selector_isolated && compact_main_menu_active &&
      physical_touch_tracking &&
      !physical_active && screen_width > 0 && screen_height > 0) {
    const float dx = physical_touch_last_x - physical_touch_start_x;
    const float dy = physical_touch_last_y - physical_touch_start_y;
    if (fabsf(dx) <= (float)screen_width * 0.06f &&
        fabsf(dy) <= (float)screen_height * 0.08f) {
      const float normalized_x =
          physical_touch_last_x / (float)screen_width;
      const float normalized_y =
          physical_touch_last_y / (float)screen_height;
      if (pes_controller_menu_physical_tap(normalized_x, normalized_y)) {
        compact_menu_tap_x = physical_touch_last_x;
        compact_menu_tap_y = physical_touch_last_y;
        compact_menu_tap_until_ms = now_ms + 90;
      }
    }
    physical_touch_tracking = 0;
  }

  // An End sample carries the final coordinate. Put it in the UP snapshot even
  // though the desired set no longer contains the physical pointer.
  if (ended) {
    const int active_index =
        touch_state_find(&active_touch_state, FAKE_POINTER_PHYSICAL);
    if (active_index >= 0) {
      active_touch_state.pointers[active_index].x = touch_x;
      active_touch_state.pointers[active_index].y = touch_y;
    }
  }

  FakeTouchState desired = {0};
  if (!set_piece_selector_isolated && physical_active &&
      !compact_main_menu_active)
    touch_state_append(&desired, FAKE_POINTER_PHYSICAL, touch_x, touch_y);
  uint32_t replay_pad_buttons = 0;
  if (!context_changed) {
    if (!set_piece_selector_isolated && compact_main_menu_active &&
        compact_menu_tap_until_ms > now_ms)
      touch_state_append(&desired, FAKE_POINTER_MENU, compact_menu_tap_x,
                         compact_menu_tap_y);
    if (set_piece_selector_isolated) {
      reset_virtual_surfaces();
      if (set_piece_selector_active) {
        if (native_pad_lab_active && native_setplay_owner_pad == 1)
          queue_set_piece_selector_input(
              controller_connected_p2, buttons_p2, previous_hid_buttons_p2,
              axis_x_p2, axis_y_p2, now_ms);
        else
          queue_set_piece_selector_input(
              controller_connected, buttons, previous_hid_buttons,
              axis_x, axis_y, now_ms);
      }
    } else if (inmatch_tutorial_isolated) {
      reset_virtual_surfaces();
      if (inmatch_tutorial_active &&
          (buttons & HidNpadButton_A) &&
          !(previous_hid_buttons & HidNpadButton_A))
        pes_controller_inmatch_tutorial_play_request();
    } else if (replay_active) {
      reset_virtual_surfaces();
      const u64 any_buttons = buttons | buttons_p2;
      const u64 any_pressed =
          (buttons & ~previous_hid_buttons) |
          (buttons_p2 & ~previous_hid_buttons_p2);
      replay_pad_buttons =
          append_replay_controller(&desired,
                                   controller_connected ||
                                       controller_connected_p2,
                                   any_buttons,
                                   any_buttons & ~any_pressed, now_ms);
    } else if (goal_demo_active) {
      reset_virtual_surfaces();
      const u64 any_buttons = buttons | buttons_p2;
      const u64 any_pressed =
          (buttons & ~previous_hid_buttons) |
          (buttons_p2 & ~previous_hid_buttons_p2);
      replay_pad_buttons = append_goal_demo_controller(
          &desired, controller_connected || controller_connected_p2,
          any_buttons, any_buttons & ~any_pressed,
          controller_snapshot.goal_player, now_ms);
    } else if (generic_cinematic_active) {
      reset_virtual_surfaces();
      const u64 any_buttons = buttons | buttons_p2;
      const u64 any_pressed =
          (buttons & ~previous_hid_buttons) |
          (buttons_p2 & ~previous_hid_buttons_p2);
      replay_pad_buttons = append_cinematic_skip_controller(
          &desired, controller_connected || controller_connected_p2,
          any_buttons, any_buttons & ~any_pressed, now_ms);
    } else if (penalty_active) {
      reset_virtual_surfaces();
      append_penalty_controller(&desired, controller_connected, buttons,
                                axis_x, axis_y, right_axis_x, right_axis_y,
                                penalty_role, now_ms);
    } else {
      if (native_pad_lab_active && gameplay_active) {
        if (native_setplay_owner_pad == 1)
          queue_native_lab_setplay_action(
              &controller_snapshot, controller_connected_p2, buttons_p2,
              previous_hid_buttons_p2);
        else
          queue_native_lab_setplay_action(
              &controller_snapshot, controller_connected, buttons,
              previous_hid_buttons);
      } else {
        queue_native_setplay_action(&controller_snapshot, have_left_stick,
                                    buttons);
        append_virtual_gamepad_touches(
            &desired, axis_x, axis_y, have_left_stick, buttons,
            gameplay_active, control_mode, &controller_snapshot, now_ms);
      }
      if (gameplan_cursor_active) {
        if (cursor_context == PES_VIRTUAL_CURSOR_PAUSE &&
            pes_controller_custom_pause_active()) {
          const u64 pressed = buttons & ~previous_hid_buttons;
          if (pressed & HidNpadButton_Up)
            pes_controller_custom_pause_input(PES_PAUSE_INPUT_UP);
          else if (pressed & HidNpadButton_Down)
            pes_controller_custom_pause_input(PES_PAUSE_INPUT_DOWN);
          else if (pressed & HidNpadButton_Left)
            pes_controller_custom_pause_input(PES_PAUSE_INPUT_LEFT);
          else if (pressed & HidNpadButton_Right)
            pes_controller_custom_pause_input(PES_PAUSE_INPUT_RIGHT);
          else if (pressed & HidNpadButton_A)
            pes_controller_custom_pause_input(PES_PAUSE_INPUT_DECIDE);
          else if (pressed & HidNpadButton_B)
            pes_controller_custom_pause_input(PES_PAUSE_INPUT_BACK);
        } else {
          append_virtual_cursor_controller(&desired, axis_x, axis_y,
                                           have_left_stick, buttons, now_ms,
                                           cursor_context);
        }
      }
    }
    if (!set_piece_selector_isolated && !inmatch_tutorial_isolated &&
        !penalty_active && pause_camera_active) {
      append_pause_camera_swipe(&desired, have_left_stick, buttons, now_ms);
      const u64 pressed = buttons & ~previous_hid_buttons;
      if (pressed & HidNpadButton_Left)
        pes_controller_pause_camera_input(PES_PAUSE_INPUT_LEFT);
      else if (pressed & HidNpadButton_Right)
        pes_controller_pause_camera_input(PES_PAUSE_INPUT_RIGHT);
      else if (pressed & HidNpadButton_B)
        pes_controller_pause_camera_input(PES_PAUSE_INPUT_BACK);
    }
    if (!set_piece_selector_isolated && !inmatch_tutorial_isolated &&
        !penalty_active && custom_postmatch_active) {
      const u64 pressed = buttons & ~previous_hid_buttons;
      if (pressed & HidNpadButton_Up)
        pes_controller_custom_postmatch_input(PES_PAUSE_INPUT_UP);
      else if (pressed & HidNpadButton_Down)
        pes_controller_custom_postmatch_input(PES_PAUSE_INPUT_DOWN);
      else if (pressed & HidNpadButton_Left)
        pes_controller_custom_postmatch_input(PES_PAUSE_INPUT_LEFT);
      else if (pressed & HidNpadButton_Right)
        pes_controller_custom_postmatch_input(PES_PAUSE_INPUT_RIGHT);
      else if (pressed & HidNpadButton_A)
        pes_controller_custom_postmatch_input(PES_PAUSE_INPUT_DECIDE);
      else if (pressed & HidNpadButton_B)
        pes_controller_custom_postmatch_input(PES_PAUSE_INPUT_BACK);
    }
    if (!set_piece_selector_isolated && !inmatch_tutorial_isolated &&
        !penalty_active && custom_prematch_gameplan_active) {
      const u64 pressed = buttons & ~previous_hid_buttons;
      if (pressed & HidNpadButton_Up)
        pes_controller_custom_prematch_gameplan_input(PES_PAUSE_INPUT_UP);
      else if (pressed & HidNpadButton_Down)
        pes_controller_custom_prematch_gameplan_input(PES_PAUSE_INPUT_DOWN);
      else if (pressed & HidNpadButton_Left)
        pes_controller_custom_prematch_gameplan_input(PES_PAUSE_INPUT_LEFT);
      else if (pressed & HidNpadButton_Right)
        pes_controller_custom_prematch_gameplan_input(PES_PAUSE_INPUT_RIGHT);
      else if (pressed & HidNpadButton_A)
        pes_controller_custom_prematch_gameplan_input(
            PES_PAUSE_INPUT_DECIDE);
      else if (pressed & HidNpadButton_B)
        pes_controller_custom_prematch_gameplan_input(PES_PAUSE_INPUT_BACK);
    }
    if (!set_piece_selector_isolated && !inmatch_tutorial_isolated &&
        !penalty_active && !pause_camera_active &&
        !custom_prematch_gameplan_active &&
        !custom_postmatch_active &&
        !cinematic_active && !gameplay_active &&
        !gameplan_cursor_active &&
        menu_controller_active) {
      const u64 pressed_p1 = buttons & ~previous_hid_buttons;
      const u64 pressed_p2 = buttons_p2 & ~previous_hid_buttons_p2;
      const u64 start_buttons =
          HidNpadButton_A | HidNpadButton_B | HidNpadButton_X |
          HidNpadButton_Y | HidNpadButton_Up | HidNpadButton_Down |
          HidNpadButton_Left | HidNpadButton_Right |
          HidNpadButton_AnySL | HidNpadButton_AnySR;
      const int a_pressed = pes_controller_start_prompt(NULL, NULL)
                                ? ((pressed_p1 | pressed_p2) &
                                   start_buttons) != 0
                                : (pressed_p1 & HidNpadButton_A) != 0;
      const int b_pressed = (buttons & HidNpadButton_B) != 0 &&
                            (previous_hid_buttons & HidNpadButton_B) == 0;
      append_menu_controller_tap(&desired, a_pressed, now_ms);
      append_menu_controller_back(&desired, b_pressed, now_ms);
      append_menu_controller_scroll(&desired, now_ms);
    }
  }
  const int menu_back_was_active =
      touch_state_find(&active_touch_state, FAKE_POINTER_MENU_BACK);
  const int menu_was_active =
      touch_state_find(&active_touch_state, FAKE_POINTER_MENU);
  float menu_x = 0.0f;
  float menu_y = 0.0f;
  if (menu_was_active >= 0) {
    menu_x = active_touch_state.pointers[menu_was_active].x;
    menu_y = active_touch_state.pointers[menu_was_active].y;
  }
  reconcile_touch_state(&desired);
  if (menu_was_active >= 0 &&
      !context_changed &&
      !set_piece_selector_isolated &&
      !cinematic_active && !replay_pointer_was_active &&
      touch_state_find(&active_touch_state, FAKE_POINTER_MENU) < 0 &&
      screen_width > 0 && screen_height > 0)
    pes_controller_menu_tap(menu_x / (float)screen_width,
                            menu_y / (float)screen_height);
  if (menu_back_was_active >= 0 &&
      !context_changed &&
      !set_piece_selector_isolated &&
      !cinematic_active && !replay_pointer_was_active &&
      touch_state_find(&active_touch_state, FAKE_POINTER_MENU_BACK) < 0)
    pes_controller_menu_back_pressed();

  const int physical_is_active =
      touch_state_find(&active_touch_state, FAKE_POINTER_PHYSICAL) >= 0;
  if (!set_piece_selector_isolated && !compact_main_menu_active &&
      physical_was_active &&
      !physical_is_active &&
      physical_touch_tracking && screen_width > 0 && screen_height > 0) {
    const float dx = physical_touch_last_x - physical_touch_start_x;
    const float dy = physical_touch_last_y - physical_touch_start_y;
    // Only a short click may activate the Matchmaking cards; normal swipes
    // continue exclusively through Android's original touch stream.
    if (!cinematic_active && !replay_pointer_was_active &&
        fabsf(dx) <= (float)screen_width * 0.06f &&
        fabsf(dy) <= (float)screen_height * 0.08f) {
      const int menu_consumed = pes_controller_menu_physical_tap(
          physical_touch_last_x / (float)screen_width,
          physical_touch_last_y / (float)screen_height);
      if (!menu_consumed)
        pes_exhibition_matchmaking_tap(
            physical_touch_last_x / (float)screen_width,
            physical_touch_last_y / (float)screen_height);
    } else if (!cinematic_active && !replay_pointer_was_active &&
               !gameplay_active && menu_controller_active) {
      // Let the team picker move its custom focus to the visible edge after
      // a native list swipe. The Android stream still performs the scrolling.
      pes_controller_menu_physical_swipe(
          physical_touch_start_x / (float)screen_width,
          physical_touch_start_y / (float)screen_height,
          physical_touch_last_x / (float)screen_width,
          physical_touch_last_y / (float)screen_height);
    }
    physical_touch_tracking = 0;
  }
  if (!physical_was_active && physical_is_active && touch)
    debugPrintf("input: touch down raw=%u,%u android=%.1f,%.1f\n",
                touch->x, touch->y, touch_x, touch_y);
  else if (physical_was_active && !physical_is_active)
    debugPrintf("input: touch up android=%.1f,%.1f\n", touch_x, touch_y);

#ifdef DEBUG_LOG
  log_controller_input(&left_stick, have_left_stick, buttons, axis_x, axis_y,
                       gameplay_active, control_mode);
#endif
  if (context_changed)
    disable_native_pad_bridge();
  else if (set_piece_selector_isolated || inmatch_tutorial_isolated ||
           penalty_active)
    disable_native_pad_bridge();
  else if (cinematic_active)
    emit_replay_pad_input(controller_connected || controller_connected_p2,
                          replay_pad_buttons);
  else if (gameplan_cursor_active)
    emit_virtual_cursor_pad_input(have_left_stick, buttons, cursor_context);
  else if (pause_camera_active)
    disable_native_pad_bridge();
  else if (custom_prematch_gameplan_active)
    disable_native_pad_bridge();
  else if (custom_postmatch_active)
    disable_native_pad_bridge();
  else if (native_pad_lab_active && gameplay_active)
  {
    u64 native_buttons = buttons;
    u64 native_buttons_p2 = buttons_p2;
    if (controller_snapshot.surface == PES_CONTROLLER_SURFACE_SETPLAY) {
      // Right opens our horizontal-Joy-Con-friendly taker selector. Minus is
      // deliberately suppressed so the hidden stock picker cannot race it.
      const u64 reserved = HidNpadButton_Right | HidNpadButton_Minus;
      native_buttons &= ~reserved;
      native_buttons_p2 &= ~reserved;
    }
    emit_native_lab_pad_input(0, &left_stick, &right_stick,
                              controller_connected, native_buttons);
    emit_native_lab_pad_input(1, &left_stick_p2, &right_stick_p2,
                              controller_connected_p2, native_buttons_p2);
  }
  else if (!gameplay_active && menu_controller_active)
    emit_menu_pad_input(&left_stick, have_left_stick, buttons,
                        have_left_stick);
  else
    disable_native_pad_bridge();
  previous_hid_buttons =
      context_changed ? 0 : (controller_connected ? buttons : 0);
  previous_hid_buttons_p2 =
      context_changed ? 0 : (controller_connected_p2 ? buttons_p2 : 0);
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
#ifdef PERF_TRACE
  const uint64_t perf_begin = perf_trace_now_ns();
  void *const perf_caller = __builtin_return_address(0);
#define ALOOPER_RETURN(value)                                                  \
  do {                                                                         \
    const int perf_result = (value);                                            \
    perf_trace_record(PERF_TRACE_LOOPER, perf_caller,                           \
                      timeout_ms > 0 ? (uint64_t)timeout_ms * 1000000ULL : 0,   \
                      perf_trace_now_ns() - perf_begin, perf_result < -3);      \
    return perf_result;                                                         \
  } while (0)
#else
#define ALOOPER_RETURN(value) return (value)
#endif
  FakeLooper *looper = &tls_looper;
  if (looper->count == 0) {
    if (timeout_ms > 0)
      svcSleepThread((int64_t)timeout_ms * 1000000LL);
    ALOOPER_RETURN(ALOOPER_POLL_TIMEOUT);
  }

  struct pollfd poll_fds[8];
  for (int i = 0; i < looper->count; i++) {
    poll_fds[i].fd = looper->fds[i].fd;
    poll_fds[i].events = POLLIN;
    poll_fds[i].revents = 0;
  }
  const int rc = poll_dispatch_fake(poll_fds, looper->count, timeout_ms);
  if (rc == 0)
    ALOOPER_RETURN(ALOOPER_POLL_TIMEOUT);
  if (rc < 0)
    ALOOPER_RETURN(errno == EINTR ? ALOOPER_POLL_WAKE : ALOOPER_POLL_ERROR);

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
      ALOOPER_RETURN(ALOOPER_POLL_CALLBACK);
    }
    ALOOPER_RETURN(entry->ident);
  }
  ALOOPER_RETURN(ALOOPER_POLL_WAKE);
#undef ALOOPER_RETURN
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
size_t AMotionEvent_getPointerCount_fake(void *event) {
  return ((FakeInputEvent *)event)->pointer_count;
}
int AMotionEvent_getPointerId_fake(void *event, size_t pointer_index) {
  FakeInputEvent *input = event;
  if (pointer_index >= input->pointer_count)
    return -1;
  return input->pointers[pointer_index].pointer_id;
}
float AMotionEvent_getX_fake(void *event, size_t pointer_index) {
  FakeInputEvent *input = event;
  if (pointer_index >= input->pointer_count)
    return 0.0f;
  return input->pointers[pointer_index].x;
}
float AMotionEvent_getY_fake(void *event, size_t pointer_index) {
  FakeInputEvent *input = event;
  if (pointer_index >= input->pointer_count)
    return 0.0f;
  return input->pointers[pointer_index].y;
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
  const uint64_t perf_begin = perf_trace_now_ns();
  void *const perf_caller = __builtin_return_address(0);
  const struct timespec *request = request_ptr;
  struct timespec delay = *request;
  if (flags & TIMER_ABSTIME) {
    struct timespec now;
    if (clock_gettime(clock_id, &now) < 0) {
      const int result = errno;
      perf_trace_record(PERF_TRACE_CLOCK_NANOSLEEP, perf_caller, 0,
                        perf_trace_now_ns() - perf_begin, result);
      return result;
    }
    delay.tv_sec -= now.tv_sec;
    delay.tv_nsec -= now.tv_nsec;
    if (delay.tv_nsec < 0) {
      delay.tv_sec--;
      delay.tv_nsec += 1000000000L;
    }
    if (delay.tv_sec < 0) {
      perf_trace_record(PERF_TRACE_CLOCK_NANOSLEEP, perf_caller, 0,
                        perf_trace_now_ns() - perf_begin, 0);
      return 0;
    }
  }
  uint64_t requested_ns = 0;
  if (delay.tv_sec >= 0 && delay.tv_nsec >= 0)
    requested_ns = (uint64_t)delay.tv_sec * 1000000000ULL +
                   (uint64_t)delay.tv_nsec;
  const int result = nanosleep(&delay, remain_ptr) < 0 ? errno : 0;
  perf_trace_record(PERF_TRACE_CLOCK_NANOSLEEP, perf_caller, requested_ns,
                    perf_trace_now_ns() - perf_begin, result);
  return result;
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
  if (strstr(filename, "libaaudio.so")) {
    debugPrintf("dlopen: exposing AAudio shim for %s\n", filename);
    return (void *)-1;
  }
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
  if (import) {
    if (strncmp(symbol, "AAudio", 6) == 0)
      debugPrintf("dlsym: %s -> %p\n", symbol, (void *)import->func);
    return (void *)import->func;
  }

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

  padConfigureInput(2, HidNpadStyleSet_NpadStandard);
  debugPrintf("input: HID shared memory=%p\n", hidGetSharedmemAddr());
  debugPrintf("Android NativeActivity bootstrap complete.\n");
}
