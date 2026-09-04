#ifndef PES21_ANDROID_SHIM_H
#define PES21_ANDROID_SHIM_H

#include <stddef.h>
#include <stdint.h>
#include <sys/types.h>

#include "so_util.h"

void android_runtime_bootstrap(so_module *ue4);
void android_input_poll(void);

#define PES_CONTROLLER_PROFILE_FULL 0u
#define PES_CONTROLLER_PROFILE_SINGLE_LEFT 1u
#define PES_CONTROLLER_PROFILE_SINGLE_RIGHT 2u
uint32_t android_controller_profile(uint32_t pad);

void *AConfiguration_new_fake(void);
void AConfiguration_delete_fake(void *config);
void AConfiguration_fromAssetManager_fake(void *config, void *mgr);
void AConfiguration_getLanguage_fake(void *config, char out[2]);
void AConfiguration_getCountry_fake(void *config, char out[2]);

void *AAssetManager_openDir_fake(void *mgr, const char *path);
const char *AAssetDir_getNextFileName_fake(void *dir);
void AAssetDir_close_fake(void *dir);

int pipe_fake(int pipefd[2]);
ssize_t read_dispatch_fake(int fd, void *buf, size_t count);
ssize_t write_dispatch_fake(int fd, const void *buf, size_t count);
int close_dispatch_fake(int fd);
int fcntl_dispatch_fake(int fd, int cmd, ...);
int poll_dispatch_fake(void *fds, unsigned long nfds, int timeout_ms);
ssize_t readv_fake(int fd, const void *iov, int iov_count);
ssize_t writev_fake(int fd, const void *iov, int iov_count);

void *ALooper_prepare_fake(int opts);
int ALooper_addFd_fake(void *looper, int fd, int ident, int events,
                       int (*callback)(int, int, void *), void *data);
int ALooper_pollAll_fake(int timeout_ms, int *out_fd, int *out_events,
                         void **out_data);

int AInputQueue_attachLooper_fake(void *queue, void *looper, int ident,
                                  int (*callback)(int, int, void *), void *data);
void AInputQueue_detachLooper_fake(void *queue);
int AInputQueue_getEvent_fake(void *queue, void **event);
int AInputQueue_preDispatchEvent_fake(void *queue, void *event);
void AInputQueue_finishEvent_fake(void *queue, void *event, int handled);

int AInputEvent_getType_fake(void *event);
int AInputEvent_getDeviceId_fake(void *event);
int AInputEvent_getSource_fake(void *event);
int AKeyEvent_getAction_fake(void *event);
int AKeyEvent_getFlags_fake(void *event);
int AKeyEvent_getKeyCode_fake(void *event);
int AKeyEvent_getMetaState_fake(void *event);
int AMotionEvent_getAction_fake(void *event);
int AMotionEvent_getButtonState_fake(void *event);
size_t AMotionEvent_getPointerCount_fake(void *event);
int AMotionEvent_getPointerId_fake(void *event, size_t pointer_index);
float AMotionEvent_getX_fake(void *event, size_t pointer_index);
float AMotionEvent_getY_fake(void *event, size_t pointer_index);

void ANativeActivity_setWindowFormat_fake(void *activity, int format);
void ANativeWindow_acquire_fake(void *window);

void *mmap_fake(void *addr, size_t length, int prot, int flags, int fd,
                int64_t offset);
int munmap_fake(void *addr, size_t length);
int mprotect_fake(void *addr, size_t length, int prot);
int madvise_fake(void *addr, size_t length, int advice);
int mlock_fake(const void *addr, size_t length);

int clock_nanosleep_fake(int clock_id, int flags, const void *request,
                         void *remain);
int fdatasync_fake(int fd);
int64_t lseek64_fake(int fd, int64_t offset, int whence);
ssize_t pread64_fake(int fd, void *buf, size_t count, int64_t offset);
ssize_t pwrite64_fake(int fd, const void *buf, size_t count, int64_t offset);

void *dlopen_fake(const char *filename, int flags);
void *dlsym_fake(void *handle, const char *symbol);
int dlclose_fake(void *handle);
char *dlerror_fake(void);
int dladdr_fake(const void *address, void *info);

int epoll_create_fake(int size);
int epoll_ctl_fake(int epfd, int operation, int fd, void *event);
int epoll_wait_fake(int epfd, void *events, int max_events, int timeout_ms);
int statfs_fake(const char *path, void *buf);
int sysinfo_fake(void *info);
int isfinitef_fake(float value);
int getpriority_fake(int which, int who);
int setpriority_fake(int which, int who, int priority);
int getrlimit_fake(int resource, void *limit);
int setrlimit_fake(int resource, const void *limit);
char *if_indextoname_fake(unsigned int index, char *name);
int pthread_getschedparam_fake(uintptr_t thread, int *policy, void *param);
unsigned int getuid_fake(void);
unsigned int getgid_fake(void);
int pause_fake(void);
int sigaction_fake(int signal_number, const void *action, void *old_action);
int sigemptyset_fake(void *set);

int pthread_rwlock_init_fake(void **rw, const void *attr);
int pthread_rwlock_destroy_fake(void **rw);
int pthread_rwlock_tryrdlock_fake(void **rw);
int pthread_rwlock_trywrlock_fake(void **rw);

extern long timezone_fake;
extern char *tzname_fake[2];

#endif
