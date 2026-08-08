/* libc_shim.c -- bionic-compatible libc wrappers for the 2.1.131 libs
 *
 * libGame.so and libc++_shared.so are linked against bionic. Where the
 * bionic and newlib ABIs differ (struct layouts, flag values, missing
 * functions) we provide converting wrappers here; everything that matches
 * is passed straight through from imports.c.
 *
 * This software may be modified and distributed under the terms
 * of the MIT license. See the LICENSE file for details.
 */

#define _GNU_SOURCE

#include <stdlib.h>
#include <stdio.h>
#include <stdint.h>
#include <stdarg.h>
#include <string.h>
#include <math.h>
#include <errno.h>
#include <ctype.h>
#include <fcntl.h>
#include <unistd.h>
#include <dirent.h>
#include <malloc.h>
#include <wchar.h>
#include <wctype.h>
#include <time.h>
#include <semaphore.h>
#include <sys/stat.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <switch.h>

#include "config.h"
#include "util.h"
#include "so_util.h"
#include "libc_shim.h"

// ---------------------------------------------------------------------------
// fortify (_chk) wrappers: ignore the object-size argument
// ---------------------------------------------------------------------------

void *__memcpy_chk_fake(void *dst, const void *src, size_t n, size_t dstlen) {
  (void)dstlen;
  return memcpy(dst, src, n);
}

void *__memmove_chk_fake(void *dst, const void *src, size_t n, size_t dstlen) {
  (void)dstlen;
  return memmove(dst, src, n);
}

char *__strcat_chk_fake(char *dst, const char *src, size_t dstlen) {
  (void)dstlen;
  return strcat(dst, src);
}

char *__strchr_chk_fake(const char *s, int c, size_t slen) {
  (void)slen;
  return strchr(s, c);
}

char *__strcpy_chk_fake(char *dst, const char *src, size_t dstlen) {
  (void)dstlen;
  return strcpy(dst, src);
}

size_t __strlen_chk_fake(const char *s, size_t slen) {
  (void)slen;
  return strlen(s);
}

char *__strncat_chk_fake(char *dst, const char *src, size_t n, size_t dstlen) {
  (void)dstlen;
  return strncat(dst, src, n);
}

char *__strncpy_chk_fake(char *dst, const char *src, size_t n, size_t dstlen) {
  (void)dstlen;
  return strncpy(dst, src, n);
}

char *__strncpy_chk2_fake(char *dst, const char *src, size_t n, size_t dstlen, size_t srclen) {
  (void)dstlen; (void)srclen;
  return strncpy(dst, src, n);
}

int __vsnprintf_chk_fake(char *s, size_t maxlen, int flag, size_t slen, const char *fmt, va_list va) {
  (void)flag; (void)slen;
  return vsnprintf(s, maxlen, fmt, va);
}

int __vsprintf_chk_fake(char *s, int flag, size_t slen, const char *fmt, va_list va) {
  (void)flag; (void)slen;
  return vsprintf(s, fmt, va);
}

// --- LCS extra fortify wrappers ---

void *__memset_chk_fake(void *s, int c, size_t n, size_t dstlen) {
  (void)dstlen;
  return memset(s, c, n);
}

char *__strrchr_chk_fake(const char *s, int c, size_t slen) {
  (void)slen;
  return strrchr(s, c);
}

// route through fread_fake so reads on the fake stdio FILEs are still absorbed
size_t fread_fake(void *ptr, size_t size, size_t n, FILE *f); // fwd decl
size_t __fread_chk_fake(void *ptr, size_t size, size_t n, FILE *f, size_t buf_size) {
  (void)buf_size;
  return fread_fake(ptr, size, n, f);
}

void __FD_SET_chk_fake(int fd, void *set, size_t setsize) {
  (void)setsize;
  FD_SET(fd, (fd_set *)set);
}

int __FD_ISSET_chk_fake(int fd, void *set, size_t setsize) {
  (void)setsize;
  return FD_ISSET(fd, (fd_set *)set);
}

// ---------------------------------------------------------------------------
// misc bionic functions
// ---------------------------------------------------------------------------

int __system_property_get_fake(const char *name, char *value) {
  (void)name;
  value[0] = '\0';
  return 0;
}

unsigned long getauxval_fake(unsigned long type) {
  (void)type;
  return 0;
}

int gettid_fake(void) {
  u64 thread_id = 1;
  if (R_SUCCEEDED(svcGetThreadId(&thread_id, CUR_THREAD_HANDLE)) && thread_id)
    return (int)(thread_id & 0x7fffffff);
  return 1;
}

#define ARM64_SYS_SCHED_SETAFFINITY 122
#define ARM64_SYS_SCHED_GETAFFINITY 123
#define ARM64_SYS_GETCPU 168
#define ARM64_SYS_GETTID 178

long syscall_fake(long number, ...) {
  va_list va;
  va_start(va, number);
  switch (number) {
    case ARM64_SYS_SCHED_SETAFFINITY:
      // Android CPU masks do not map to Switch cores. Leaving the thread
      // unpinned lets Horizon schedule UE4's worker pool across cores 0..2.
      va_end(va);
      return 0;
    case ARM64_SYS_SCHED_GETAFFINITY: {
      (void)va_arg(va, int); // pid/tid
      const size_t set_size = va_arg(va, size_t);
      void *set = va_arg(va, void *);
      if (set && set_size) {
        memset(set, 0, set_size);
        *(unsigned char *)set = 0x07;
      }
      va_end(va);
      return set_size;
    }
    case ARM64_SYS_GETCPU: {
      unsigned int *cpu = va_arg(va, unsigned int *);
      unsigned int *node = va_arg(va, unsigned int *);
      (void)va_arg(va, void *); // obsolete cache pointer
      if (cpu)
        *cpu = (unsigned int)gettid_fake() % 3;
      if (node)
        *node = 0;
      va_end(va);
      return 0;
    }
    case ARM64_SYS_GETTID:
      va_end(va);
      return gettid_fake();
  }
  va_end(va);
  debugPrintf("libc: syscall(%ld) -> ENOSYS\n", number);
  errno = ENOSYS;
  return -1;
}

void sincosf_fake(float x, float *s, float *c) {
  *s = sinf(x);
  *c = cosf(x);
}

int sched_get_priority_max_fake(int policy) {
  (void)policy;
  return 0;
}

void android_set_abort_message_fake(const char *msg) {
  debugPrintf("abort message: %s\n", msg ? msg : "(null)");
}

size_t __ctype_get_mb_cur_max_fake(void) {
  return 1;
}

int __register_atfork_fake(void) {
  return 0;
}

int __cxa_thread_atexit_impl_fake(void (*fn)(void *), void *arg, void *dso) {
  // threads never exit cleanly here; leak instead of running dtors
  (void)fn; (void)arg; (void)dso;
  return 0;
}

// bionic sysconf constants
#define BIONIC_SC_PAGESIZE 39
#define BIONIC_SC_PAGE_SIZE 40
#define BIONIC_SC_NPROCESSORS_CONF 96
#define BIONIC_SC_NPROCESSORS_ONLN 97
#define BIONIC_SC_PHYS_PAGES 98

long sysconf_fake(int name) {
  switch (name) {
    case BIONIC_SC_PAGESIZE:
    case BIONIC_SC_PAGE_SIZE:
      return 0x1000;
    case BIONIC_SC_NPROCESSORS_CONF:
    case BIONIC_SC_NPROCESSORS_ONLN:
      return 3;
    case BIONIC_SC_PHYS_PAGES:
      return (3ll * 1024 * 1024 * 1024) / 0x1000;
    default:
      debugPrintf("libc: sysconf(%d) -> -1\n", name);
      return -1;
  }
}

// Real libc symbols referenced by Mesa's disk_cache.c (shader cache) that
// Horizon/newlib doesn't provide. Stubs suffice: the cache dir comes from
// MESA_GLSL_CACHE_DIR (the getpwuid path is never taken), getuid()==geteuid()
// keeps the cache enabled, and fstatat()->-1 just skips LRU eviction.
#include <pwd.h>
uid_t getuid(void)  { return 0; }
uid_t geteuid(void) { return 0; }
long sysconf(int name) { return sysconf_fake(name); }
int getpwuid_r(uid_t uid, struct passwd *pwd, char *buf, size_t buflen,
               struct passwd **result) {
  (void)uid; (void)pwd; (void)buf; (void)buflen;
  *result = NULL;
  return 0;
}
int dirfd(DIR *dirp) { (void)dirp; return -1; }
int fstatat(int fd, const char *path, struct stat *st, int flag) {
  (void)fd; (void)path; (void)st; (void)flag;
  errno = ENOSYS;
  return -1;
}

long pathconf_fake(const char *path, int name) {
  (void)path; (void)name;
  return -1;
}

// ---------------------------------------------------------------------------
// open() flag translation (bionic/linux -> newlib)
// ---------------------------------------------------------------------------

#define LINUX_O_CREAT  0100
#define LINUX_O_EXCL   0200
#define LINUX_O_TRUNC  01000
#define LINUX_O_APPEND 02000
#define LINUX_O_NONBLOCK 04000

static int convert_open_flags(int flags) {
  int out = flags & 3; // O_RDONLY/O_WRONLY/O_RDWR match
  if (flags & LINUX_O_CREAT)  out |= O_CREAT;
  if (flags & LINUX_O_EXCL)   out |= O_EXCL;
  if (flags & LINUX_O_TRUNC)  out |= O_TRUNC;
  if (flags & LINUX_O_APPEND) out |= O_APPEND;
  return out;
}

// Defined further down; used by the open shims to redirect absolute Android OBB
// paths to the flat copy in the game directory.
static int path_is_obb(const char *path);
static const char *path_basename(const char *path);

// Android UE4 uses paths rooted three levels above the executable. The Switch
// fsdev layer does not reliably normalize traversal past the mount root, while
// our extracted runtime tree already starts at PesMobile/ or Engine/.
static const char *runtime_relative_path(const char *path) {
  const char *p = path;
  while (p && !strncmp(p, "../", 3))
    p += 3;
  return p;
}

// This APK still probes the previous dt510 language-pack names, while its
// matching patch OBB ships the same packs as dt530. Redirect only a missing
// dt510 path so installs with genuine dt510 files continue to take priority.
static int rewrite_dt510_path(const char *path, char *out, size_t out_size) {
  const char *marker = path ? strstr(path, "dt510_mobile_") : NULL;
  if (!marker || strlen(path) + 1 > out_size)
    return 0;
  strlcpy(out, path, out_size);
  out[(size_t)(marker - path) + 3] = '3';
  return 1;
}

static int path_is_pak_trace(const char *path) {
  return path && (strstr(path, "Paks") || strstr(path, ".pak"));
}

int access_fake(const char *path, int mode) {
  int ret = access(path, mode);
  const char *relative = runtime_relative_path(path);
  if (ret < 0 && relative && relative != path)
    ret = access(relative, mode);
  char upgraded[0x400];
  if (ret < 0 && rewrite_dt510_path(relative, upgraded, sizeof(upgraded))) {
    ret = access(upgraded, mode);
    if (ret == 0)
      debugPrintf("access: %s -> %s\n", path, upgraded);
  }
  if (path_is_pak_trace(path))
    debugPrintf("access(%s -> %s, %d) -> %d errno=%d\n", path,
                relative ? relative : "(null)", mode, ret, ret < 0 ? errno : 0);
  return ret;
}

void *opendir_fake(const char *path) {
  DIR *dir = opendir(path);
  const char *relative = runtime_relative_path(path);
  if (!dir && relative && relative != path)
    dir = opendir(relative);
  if (path_is_pak_trace(path))
    debugPrintf("opendir(%s -> %s) -> %p errno=%d\n", path,
                relative ? relative : "(null)", dir,
                dir ? 0 : errno);
  return dir;
}

int open_fake(const char *path, int flags, ...) {
  int mode = 0666;
  if (flags & LINUX_O_CREAT) {
    va_list va;
    va_start(va, flags);
    mode = va_arg(va, int);
    va_end(va);
  }
  if (path && (!strcmp(path, "/dev/urandom") ||
               !strcmp(path, "/dev/random")) &&
      (flags & 3) == O_RDONLY) {
    debugPrintf("open(%s) -> fake random device\n", path);
    return FAKE_URANDOM_FD;
  }
  int fd = open(path, convert_open_flags(flags), mode);
  const char *relative = runtime_relative_path(path);
  if (fd < 0 && !(flags & LINUX_O_CREAT) && (flags & 3) == O_RDONLY &&
      relative && relative != path)
    fd = open(relative, convert_open_flags(flags), mode);
  char upgraded[0x400];
  if (fd < 0 && !(flags & LINUX_O_CREAT) && (flags & 3) == O_RDONLY &&
      rewrite_dt510_path(relative, upgraded, sizeof(upgraded))) {
    fd = open(upgraded, convert_open_flags(flags), mode);
    if (fd >= 0)
      debugPrintf("open: %s -> %s\n", path, upgraded);
  }
  // UE4's pak layer can re-open the located OBB via a raw read-only open using
  // the absolute Android storage path; retry the basename in the game dir.
  if (fd < 0 && !(flags & LINUX_O_CREAT) && (flags & 3) == O_RDONLY &&
      path_is_obb(path)) {
    const char *base = path_basename(path);
    if (base && base != path) {
      fd = open(base, convert_open_flags(flags), mode);
      if (fd >= 0)
        debugPrintf("open(%s) not found, using %s\n", path, base);
    }
  }
  if (path_is_pak_trace(path))
    debugPrintf("open(%s, %x) -> %d errno=%d\n", path, flags, fd,
                fd < 0 ? errno : 0);
  return fd;
}

int openat_fake(int dirfd, const char *path, int flags, ...) {
  (void)dirfd; // assume AT_FDCWD or absolute paths
  int mode = 0666;
  if (flags & LINUX_O_CREAT) {
    va_list va;
    va_start(va, flags);
    mode = va_arg(va, int);
    va_end(va);
  }
  if (path && (!strcmp(path, "/dev/urandom") ||
               !strcmp(path, "/dev/random")) &&
      (flags & 3) == O_RDONLY) {
    debugPrintf("openat(%s) -> fake random device\n", path);
    return FAKE_URANDOM_FD;
  }
  int fd = open(path, convert_open_flags(flags), mode);
  char upgraded[0x400];
  if (fd < 0 && !(flags & LINUX_O_CREAT) && (flags & 3) == O_RDONLY &&
      rewrite_dt510_path(path, upgraded, sizeof(upgraded))) {
    fd = open(upgraded, convert_open_flags(flags), mode);
    if (fd >= 0)
      debugPrintf("openat: %s -> %s\n", path, upgraded);
  }
  if (fd < 0 && !(flags & LINUX_O_CREAT) && (flags & 3) == O_RDONLY &&
      path_is_obb(path)) {
    const char *base = path_basename(path);
    if (base && base != path) {
      fd = open(base, convert_open_flags(flags), mode);
      if (fd >= 0)
        debugPrintf("openat(%s) not found, using %s\n", path, base);
    }
  }
  return fd;
}

int unlinkat_fake(int dirfd, const char *path, int flags) {
  (void)dirfd; (void)flags;
  return unlink(path);
}

// fcntl with bionic->newlib flag translation for the netcode's F_SETFL.
// command numbers (F_DUPFD=0..F_SETFL=4) match between bionic and newlib.
int fcntl_fake(int fd, int cmd, ...) {
  if (cmd == F_GETFL || cmd == F_GETFD)
    return fcntl(fd, cmd);

  va_list va;
  va_start(va, cmd);
  if (cmd == F_SETFL) {
    const int flags = va_arg(va, int);
    va_end(va);
    int out = 0;
    if (flags & LINUX_O_NONBLOCK) out |= O_NONBLOCK;
    if (flags & LINUX_O_APPEND)   out |= O_APPEND;
    return fcntl(fd, F_SETFL, out);
  }
  // F_GETFL / F_GETFD / F_SETFD / F_DUPFD: forward the (optional) int arg
  const int arg = va_arg(va, int);
  va_end(va);
  return fcntl(fd, cmd, arg);
}

// The netcode passes Linux/bionic socket constants; libnx numbers SOL_SOCKET
// and the SO_* options differently, so translate before forwarding.
#define BIONIC_SOL_SOCKET 1
int setsockopt_fake(int fd, int level, int optname, const void *optval, uint32_t optlen) {
  int lv = level;
  int on = optname;
  if (level == BIONIC_SOL_SOCKET) {
    lv = SOL_SOCKET;
    switch (optname) {
      case 2:      on = SO_REUSEADDR; break;
      case 6:      on = SO_BROADCAST; break;
      case 9:      on = SO_KEEPALIVE; break;
      case 15:     on = SO_REUSEPORT; break;
      case 20:     on = SO_RCVTIMEO;  break;
      case 21:     on = SO_SNDTIMEO;  break;
      case 0x4000: on = SO_NO_OFFLOAD; break;
      default:     break; // pass unknown optnames through unchanged
    }
  }
  return setsockopt(fd, lv, on, optval, (socklen_t)optlen);
}

// ---------------------------------------------------------------------------
// struct stat conversion (bionic aarch64 layout)
// ---------------------------------------------------------------------------

struct bionic_timespec {
  int64_t tv_sec;
  int64_t tv_nsec;
};

struct bionic_stat {
  uint64_t st_dev;
  uint64_t st_ino;
  uint32_t st_mode;
  uint32_t st_nlink;
  uint32_t st_uid;
  uint32_t st_gid;
  uint64_t st_rdev;
  uint64_t __pad1;
  int64_t st_size;
  int32_t st_blksize;
  int32_t __pad2;
  int64_t st_blocks;
  struct bionic_timespec st_atim;
  struct bionic_timespec st_mtim;
  struct bionic_timespec st_ctim;
  uint32_t __unused4;
  uint32_t __unused5;
};

static void convert_stat(const struct stat *in, struct bionic_stat *out) {
  memset(out, 0, sizeof(*out));
  out->st_dev = in->st_dev;
  out->st_ino = in->st_ino;
  out->st_mode = in->st_mode;
  out->st_nlink = in->st_nlink;
  out->st_uid = in->st_uid;
  out->st_gid = in->st_gid;
  out->st_rdev = in->st_rdev;
  out->st_size = in->st_size;
  out->st_blksize = in->st_blksize;
  out->st_blocks = in->st_blocks;
  out->st_atim.tv_sec = in->st_atime;
  out->st_mtim.tv_sec = in->st_mtime;
  out->st_ctim.tv_sec = in->st_ctime;
}

int stat_fake(const char *path, struct bionic_stat *st) {
  struct stat real;
  int ret = stat(path, &real);
  const char *relative = runtime_relative_path(path);
  if (ret < 0 && relative && relative != path)
    ret = stat(relative, &real);
  char upgraded[0x400];
  if (ret < 0 && rewrite_dt510_path(relative, upgraded, sizeof(upgraded))) {
    ret = stat(upgraded, &real);
    if (ret == 0)
      debugPrintf("stat: %s -> %s\n", path, upgraded);
  }
  if (ret == 0)
    convert_stat(&real, st);
  if (path_is_pak_trace(path))
    debugPrintf("stat(%s) -> %d size=%lld errno=%d\n", path, ret,
                ret == 0 ? (long long)real.st_size : -1LL,
                ret < 0 ? errno : 0);
  return ret;
}

int fstat_fake(int fd, struct bionic_stat *st) {
  struct stat real;
  const int ret = fstat(fd, &real);
  if (ret == 0)
    convert_stat(&real, st);
  return ret;
}

int lstat_fake(const char *path, struct bionic_stat *st) {
  return stat_fake(path, st);
}

// ---------------------------------------------------------------------------
// dirent conversion (bionic dirent64 layout)
// ---------------------------------------------------------------------------

struct bionic_dirent {
  uint64_t d_ino;
  int64_t d_off;
  uint16_t d_reclen;
  uint8_t d_type;
  char d_name[256];
};

void *readdir_fake(void *dirp) {
  static struct bionic_dirent out; // not thread-safe
  struct dirent *e = readdir((DIR *)dirp);
  if (!e)
    return NULL;
  memset(&out, 0, sizeof(out));
  out.d_ino = e->d_ino;
  out.d_reclen = sizeof(out);
  out.d_type = e->d_type;
  snprintf(out.d_name, sizeof(out.d_name), "%s", e->d_name);
  return &out;
}

// ---------------------------------------------------------------------------
// locale: ignore the locale argument and use the C locale versions
// ---------------------------------------------------------------------------

void *newlocale_fake(int mask, const char *locale, void *base) {
  (void)mask; (void)locale; (void)base;
  return (void *)1;
}

void freelocale_fake(void *loc) {
  (void)loc;
}

void *uselocale_fake(void *loc) {
  (void)loc;
  return (void *)1;
}

#define WRAP_ISW_L(fn) int fn##_l_fake(int wc, void *loc) { (void)loc; return fn(wc); }
WRAP_ISW_L(iswalpha)
WRAP_ISW_L(iswblank)
WRAP_ISW_L(iswcntrl)
WRAP_ISW_L(iswdigit)
WRAP_ISW_L(iswlower)
WRAP_ISW_L(iswprint)
WRAP_ISW_L(iswpunct)
WRAP_ISW_L(iswspace)
WRAP_ISW_L(iswupper)
WRAP_ISW_L(iswxdigit)
WRAP_ISW_L(towlower)
WRAP_ISW_L(towupper)

// narrow ctype _l variants (imported by the libc++ in the donor); ignore locale
#define WRAP_IS_L(fn) int fn##_l_fake(int c, void *loc) { (void)loc; return fn(c); }
WRAP_IS_L(isdigit)
WRAP_IS_L(isxdigit)
WRAP_IS_L(islower)
WRAP_IS_L(isupper)
int toupper_l_fake(int c, void *loc) { (void)loc; return toupper(c); }
int tolower_l_fake(int c, void *loc) { (void)loc; return tolower(c); }

int strcoll_l_fake(const char *a, const char *b, void *loc) {
  (void)loc;
  return strcoll(a, b);
}

size_t strxfrm_l_fake(char *dst, const char *src, size_t n, void *loc) {
  (void)loc;
  return strxfrm(dst, src, n);
}

size_t strftime_l_fake(char *s, size_t max, const char *fmt, const void *tm, void *loc) {
  (void)loc;
  return strftime(s, max, fmt, (const struct tm *)tm);
}

long double strtold_l_fake(const char *s, char **end, void *loc) {
  (void)loc;
  return strtold(s, end);
}

long long strtoll_l_fake(const char *s, char **end, int base, void *loc) {
  (void)loc;
  return strtoll(s, end, base);
}

unsigned long long strtoull_l_fake(const char *s, char **end, int base, void *loc) {
  (void)loc;
  return strtoull(s, end, base);
}

int wcscoll_l_fake(const wchar_t *a, const wchar_t *b, void *loc) {
  (void)loc;
  return wcscoll(a, b);
}

size_t wcsxfrm_l_fake(wchar_t *dst, const wchar_t *src, size_t n, void *loc) {
  (void)loc;
  return wcsxfrm(dst, src, n);
}

size_t mbsnrtowcs_fake(wchar_t *dst, const char **src, size_t nms, size_t len, void *ps) {
  (void)ps;
  // ascii-ish naive conversion
  size_t i = 0;
  const char *s = *src;
  while (i < nms && s[i] && (!dst || i < len)) {
    if (dst) dst[i] = (unsigned char)s[i];
    i++;
  }
  if (dst && i < len) {
    dst[i] = 0;
    *src = NULL;
  }
  return i;
}

size_t wcsnrtombs_fake(char *dst, const wchar_t **src, size_t nwc, size_t len, void *ps) {
  (void)ps;
  size_t i = 0;
  const wchar_t *s = *src;
  while (i < nwc && s[i] && (!dst || i < len)) {
    if (dst) dst[i] = (char)s[i];
    i++;
  }
  if (dst && i < len) {
    dst[i] = 0;
    *src = NULL;
  }
  return i;
}

// ---------------------------------------------------------------------------
// memory
// ---------------------------------------------------------------------------

int posix_memalign_fake(void **out, size_t align, size_t size) {
  void *p = memalign(align, size);
  if (!p)
    return ENOMEM;
  *out = p;
  return 0;
}

// ---------------------------------------------------------------------------
// filesystem odds and ends
// ---------------------------------------------------------------------------

char *realpath_fake(const char *path, char *resolved) {
  if (!resolved)
    resolved = malloc(0x1000);
  strcpy(resolved, path);
  return resolved;
}

int strerror_r_fake(int err, char *buf, size_t len) {
  snprintf(buf, len, "%s", strerror(err));
  return 0;
}

int statvfs_fake(const char *path, void *buf) {
  (void)path;
  memset(buf, 0, 0x70);
  return 0;
}

// ---------------------------------------------------------------------------
// stdio over the fake bionic __sF (stdin/stdout/stderr): libc++_shared binds
// std::cout/cerr to &__sF[1]/[2]; these wrappers absorb accesses to those fake
// FILEs and forward everything else to real stdio.
// ---------------------------------------------------------------------------

uint8_t fake_sF[3][0x100]; // referenced by imports.c too

// fake stdout FILE for libGame.so's `stdout` import, inside the fake __sF array
void *fake_stdout = &fake_sF[1];

static int is_fake_file(const void *f) {
  const uint8_t *p = f;
  const uint8_t *base = (const uint8_t *)fake_sF;
  return p >= base && p < base + sizeof(fake_sF);
}

size_t fwrite_fake(const void *ptr, size_t size, size_t n, FILE *f) {
  if (is_fake_file(f)) {
#ifdef DEBUG_LOG
    static char buf[0x400];
    const size_t total = size * n < sizeof(buf) - 1 ? size * n : sizeof(buf) - 1;
    memcpy(buf, ptr, total);
    buf[total] = '\0';
    debugPrintf("stdio: %s", buf);
#endif
    return n;
  }
  return fwrite(ptr, size, n, f);
}

size_t fread_fake(void *ptr, size_t size, size_t n, FILE *f) {
  if (is_fake_file(f))
    return 0;
  return fread(ptr, size, n, f);
}

int fputc_fake(int c, FILE *f) {
  if (is_fake_file(f))
    return c;
  return fputc(c, f);
}

int fputs_fake(const char *s, FILE *f) {
  if (is_fake_file(f)) {
    debugPrintf("stdio: %s", s);
    return 0;
  }
  return fputs(s, f);
}

int fflush_fake(FILE *f) {
  if (is_fake_file(f) || f == NULL)
    return 0;
  return fflush(f);
}

int fclose_fake(FILE *f) {
  if (is_fake_file(f))
    return 0;
  return fclose(f);
}

int ferror_fake(FILE *f) {
  if (is_fake_file(f))
    return 0;
  return ferror(f);
}

int fileno_fake(FILE *f) {
  if (is_fake_file(f))
    return ((const uint8_t *)f - &fake_sF[0][0]) / 0x100;
  return fileno(f);
}

int fprintf_fake(FILE *f, const char *fmt, ...) {
  va_list va;
  va_start(va, fmt);
  int ret;
  if (is_fake_file(f)) {
#ifdef DEBUG_LOG
    static char buf[0x400];
    ret = vsnprintf(buf, sizeof(buf), fmt, va);
    debugPrintf("stdio: %s", buf);
#else
    ret = 0;
#endif
  } else {
    ret = vfprintf(f, fmt, va);
  }
  va_end(va);
  return ret;
}

int vfprintf_fake(FILE *f, const char *fmt, va_list va) {
  if (is_fake_file(f)) {
#ifdef DEBUG_LOG
    static char buf[0x400];
    int ret = vsnprintf(buf, sizeof(buf), fmt, va);
    debugPrintf("stdio: %s", buf);
    return ret;
#else
    return 0;
#endif
  }
  return vfprintf(f, fmt, va);
}

int fseek_fake(FILE *f, long off, int whence) {
  if (is_fake_file(f))
    return -1;
  return fseek(f, off, whence);
}

int getc_fake(FILE *f) {
  if (is_fake_file(f))
    return -1; // EOF
  return getc(f);
}

int ungetc_fake(int c, FILE *f) {
  if (is_fake_file(f))
    return -1;
  return ungetc(c, f);
}

void setbuf_fake(FILE *f, char *buf) {
  if (is_fake_file(f))
    return;
  setbuf(f, buf);
}

// ---------------------------------------------------------------------------
// AAsset emulation: read "APK assets" straight from the game directory
// ---------------------------------------------------------------------------

typedef struct {
  FILE *f;
  long size;
  void *buffer;
  long position;
  int embedded_uproject;
} Asset;

void *AAssetManager_fromJava_fake(void *env, void *mgr) {
  (void)env; (void)mgr;
  return (void *)1; // any non-NULL token
}

extern FILE *fmemopen(void *buf, size_t size, const char *mode);
static const char *path_basename(const char *path);

// Packaged Android UE4 builds do not ship the source .uproject as a loose
// file. Android's platform layer still makes the descriptor visible during
// FEngineLoop startup, so provide the equivalent metadata from memory.
static void *open_embedded_uproject(const char *path) {
  static const char descriptor[] =
      "{\n"
      "  \"FileVersion\": 3,\n"
      "  \"EngineAssociation\": \"4.22\",\n"
      "  \"Category\": \"\",\n"
      "  \"Description\": \"\",\n"
      "  \"Modules\": [\n"
      "    {\"Name\": \"PesMobile\", \"Type\": \"Runtime\", "
      "\"LoadingPhase\": \"Default\"}\n"
      "  ],\n"
      "  \"TargetPlatforms\": [\"Android\"]\n"
      "}\n";
  const char *base = path_basename(path);
  if (!base || strcasecmp(base, "PesMobile.uproject") != 0)
    return NULL;
  FILE *f = fopen("PesMobile.uproject", "w+b");
  if (!f) {
    debugPrintf("AAsset: could not create PesMobile.uproject backing file\n");
    return NULL;
  }
  const size_t descriptor_size = strlen(descriptor);
  if (fwrite(descriptor, 1, descriptor_size, f) != descriptor_size ||
      fflush(f) != 0 || fseek(f, 0, SEEK_SET) != 0) {
    fclose(f);
    debugPrintf("AAsset: could not populate PesMobile.uproject backing file\n");
    return NULL;
  }
  Asset *asset = calloc(1, sizeof(*asset));
  if (!asset) {
    fclose(f);
    return NULL;
  }
  asset->f = f;
  asset->size = (long)descriptor_size;
  asset->embedded_uproject = 1;
  debugPrintf("AAsset: open(%s) -> embedded PesMobile.uproject\n", path);
  return asset;
}

static FILE *open_proc_file(const char *path) {
  static char meminfo[] =
      "MemTotal:        3251200 kB\n"
      "MemFree:         2097152 kB\n"
      "MemAvailable:    2097152 kB\n"
      "Buffers:               0 kB\n"
      "Cached:           262144 kB\n"
      "SwapCached:            0 kB\n"
      "SwapTotal:             0 kB\n"
      "SwapFree:              0 kB\n";
  static char self_status[] =
      "Name:\tpes21_nx\n"
      "State:\tR (running)\n"
      "Pid:\t1\n"
      "Threads:\t1\n"
      "VmPeak:\t3000000 kB\n"
      "VmSize:\t3000000 kB\n"
      "VmHWM:\t512000 kB\n"
      "VmRSS:\t512000 kB\n"
      "VmData:\t2500000 kB\n"
      "VmStk:\t8192 kB\n"
      "VmExe:\t170000 kB\n"
      "VmLib:\t0 kB\n"
      "VmSwap:\t0 kB\n";
  static char cpuinfo[] =
      "processor\t: 0\n"
      "model name\t: ARM Cortex-A57\n"
      "BogoMIPS\t: 38.40\n"
      "Features\t: fp asimd aes pmull sha1 sha2 crc32\n"
      "CPU implementer\t: 0x41\n"
      "CPU architecture: 8\n"
      "CPU variant\t: 0x1\n"
      "CPU part\t: 0xd07\n"
      "CPU revision\t: 1\n";
  static char proc_stat[] =
      "cpu  100 0 100 1000 0 0 0 0 0 0\n"
      "cpu0 25 0 25 250 0 0 0 0 0 0\n"
      "cpu1 25 0 25 250 0 0 0 0 0 0\n"
      "cpu2 25 0 25 250 0 0 0 0 0 0\n"
      "cpu3 25 0 25 250 0 0 0 0 0 0\n"
      "intr 0\nctxt 0\nbtime 0\nprocesses 1\nprocs_running 1\n"
      "procs_blocked 0\n";
  static char net_route[] =
      "Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask\tMTU\tWindow\tIRTT\n"
      "wlan0\t00000000\t0101A8C0\t0003\t0\t0\t0\t00000000\t0\t0\t0\n";

  char *contents = NULL;
  if (!strcmp(path, "/proc/meminfo"))
    contents = meminfo;
  else if (!strcmp(path, "/proc/self/status"))
    contents = self_status;
  else if (!strcmp(path, "/proc/cpuinfo"))
    contents = cpuinfo;
  else if (!strcmp(path, "/proc/stat"))
    contents = proc_stat;
  else if (!strcmp(path, "/proc/net/route"))
    contents = net_route;
  if (!contents)
    return NULL;

  debugPrintf("fopen(%s) -> virtual Android procfs\n", path);
  return fmemopen(contents, strlen(contents), "r");
}

// The runtime keeps the OBBs flat in the game directory, but UE4 asks for them
// through absolute Android storage paths (/Android/obb/<pkg>/... or
// /obb/<pkg>/...). Detect those so a failed open can retry with the basename.
static int path_is_obb(const char *path) {
  if (!path)
    return 0;
  const char *ext = strrchr(path, '.');
  if (ext && strcasecmp(ext, ".obb") == 0)
    return 1;
  return strstr(path, "/obb/") != NULL;
}

static const char *path_basename(const char *path) {
  if (!path)
    return NULL;
  const char *slash = strrchr(path, '/');
  return slash ? slash + 1 : path;
}

static FILE *open_runtime_basename(const char *path, const char *mode,
                                   char *resolved, size_t resolved_size) {
  const char *base = path_basename(path);
  if (!base || !base[0])
    return NULL;
  snprintf(resolved, resolved_size, "sdmc:/switch/pes21_nx/%s", base);
  return fopen(resolved, mode);
}

// fopen with a large stream buffer for the big archives (.ras/.msf), which issue
// many small reads/seeks where fsdev round trips would dominate.
FILE *fopen_fake(const char *path, const char *mode) {
  if (path && mode && strchr(mode, 'r')) {
    FILE *proc = open_proc_file(path);
    if (proc)
      return proc;
  }
  FILE *f = fopen(path, mode);
  const char *relative = runtime_relative_path(path);
  if (!f && path && mode && strchr(mode, 'r') && relative && relative != path) {
    f = fopen(relative, mode);
    if (f)
      debugPrintf("fopen(%s) not found, using %s\n", path, relative);
  }
  char upgraded[0x400];
  if (!f && path && mode && strchr(mode, 'r') &&
      rewrite_dt510_path(relative, upgraded, sizeof(upgraded))) {
    f = fopen(upgraded, mode);
    if (f)
      debugPrintf("fopen: %s -> %s\n", path, upgraded);
  }
  // UE4 opens the OBB via an absolute Android storage path; retry read opens
  // with the basename so the flat game-dir copy resolves.
  if (!f && path && mode && strchr(mode, 'r') && path_is_obb(path)) {
    const char *base = path_basename(path);
    if (base && base != path) {
      f = fopen(base, mode);
      if (f)
        debugPrintf("fopen(%s) not found, using %s\n", path, base);
      else {
        char resolved[0x400];
        f = open_runtime_basename(path, mode, resolved, sizeof(resolved));
        if (f)
          debugPrintf("fopen(%s) not found, using %s\n", path, resolved);
      }
    }
  }
  if (!f)
    debugPrintf("fopen(%s, %s) -> FAIL\n", path ? path : "(null)", mode);
  if (f && path) {
    const char *trace_ext = strrchr(path, '.');
    if (trace_ext && (!strcasecmp(trace_ext, ".cpk") ||
                      !strcasecmp(trace_ext, ".obb")))
      debugPrintf("fopen(%s, %s) -> OK\n", path, mode);
  }
  if (f && strchr(mode, 'r')) {
    const char *ext = strrchr(path, '.');
    if (ext && (strcasecmp(ext, ".ras") == 0 || strcasecmp(ext, ".msf") == 0))
      setvbuf(f, NULL, _IOFBF, 128 * 1024);
  }
  return f;
}

// ---------------------------------------------------------------------------
// loose-file existence index: the engine probes disk for a loose-file override
// before every .ras read. data/ and es2/ are immutable, so index them once and
// answer probes from memory; other paths always hit the filesystem.
// ---------------------------------------------------------------------------

static char **asset_index = NULL;
static int asset_index_count = 0;
static int asset_index_cap = 0;
static int asset_index_ready = 0;

static void index_add(const char *path) {
  if (asset_index_count == asset_index_cap) {
    asset_index_cap = asset_index_cap ? asset_index_cap * 2 : 1024;
    asset_index = realloc(asset_index, asset_index_cap * sizeof(char *));
  }
  char *s = strdup(path);
  for (char *p = s; *p; p++)
    *p = tolower((unsigned char)*p);
  asset_index[asset_index_count++] = s;
}

static void index_scan_dir(const char *dir) {
  DIR *d = opendir(dir);
  if (!d)
    return;
  struct dirent *e;
  char path[0x400];
  while ((e = readdir(d))) {
    if (e->d_name[0] == '.' &&
        (e->d_name[1] == '\0' || (e->d_name[1] == '.' && e->d_name[2] == '\0')))
      continue;
    snprintf(path, sizeof(path), "%s/%s", dir, e->d_name);
    if (e->d_type == DT_DIR)
      index_scan_dir(path);
    else
      index_add(path);
  }
  closedir(d);
}

static int index_cmp(const void *a, const void *b) {
  return strcmp(*(const char *const *)a, *(const char *const *)b);
}

static int index_lookup_cmp(const void *key, const void *elem) {
  return strcmp((const char *)key, *(const char *const *)elem);
}

// returns 0 only when the path is inside an indexed tree and known absent
static int index_maybe_exists(const char *path) {
  if (!asset_index_ready) {
    index_scan_dir("data");
    index_scan_dir("es2");
    if (asset_index_count)
      qsort(asset_index, asset_index_count, sizeof(char *), index_cmp);
    asset_index_ready = 1;
    debugPrintf("AAsset: indexed %d loose files\n", asset_index_count);
  }
  if (strncasecmp(path, "data/", 5) != 0 && strncasecmp(path, "es2/", 4) != 0)
    return 1;
  char lower[0x400];
  size_t i;
  for (i = 0; path[i] && i < sizeof(lower) - 1; i++)
    lower[i] = tolower((unsigned char)path[i]);
  lower[i] = '\0';
  return bsearch(lower, asset_index, asset_index_count, sizeof(char *), index_lookup_cmp) != NULL;
}

// Open `path`; on miss, retry with any "assets/" component stripped so that
// files dropped directly in the game dir resolve as well as ./assets/ ones.
static FILE *open_asset_with_fallback(const char *path) {
  FILE *f = fopen(path, "rb");
  if (f)
    return f;
  const char *relative = runtime_relative_path(path);
  if (relative && relative != path) {
    f = fopen(relative, "rb");
    if (f) {
      debugPrintf("AAsset: %s not found, using %s\n", path, relative);
      return f;
    }
  }
  const char *as = strstr(path, "assets/");
  if (as) {
    char alt[0x400];
    const size_t pre = (size_t)(as - path);
    if (pre < sizeof(alt)) {
      memcpy(alt, path, pre);
      strlcpy(alt + pre, as + 7, sizeof(alt) - pre); // skip "assets/"
      f = fopen(alt, "rb");
      if (f)
        debugPrintf("AAsset: %s not found, using %s\n", path, alt);
    }
  }
  // The OBBs live flat in the game dir, but UE4 asks via an absolute Android
  // storage path (/Android/obb/<pkg>/... or /obb/<pkg>/...); retry the basename.
  if (!f && path_is_obb(path)) {
    const char *base = path_basename(path);
    if (base && base != path) {
      f = fopen(base, "rb");
      if (f)
        debugPrintf("AAsset: %s not found, using %s\n", path, base);
      else {
        char resolved[0x400];
        f = open_runtime_basename(path, "rb", resolved, sizeof(resolved));
        if (f)
          debugPrintf("AAsset: %s not found, using %s\n", path, resolved);
      }
    }
  }
  return f;
}

// Streamed-audio never-hang guard: the engine retries a failed *.mp3 open in a
// tight loop forever, so hand back a valid silent MP3 on miss to let the open +
// mpg123 decode succeed and proceed.
#include "silent_bin.h"   // silent MP3 bytes embedded as data/silent.bin
static int path_is_mp3(const char *p) {
  size_t n = p ? strlen(p) : 0;
  return n >= 4 && p[n - 4] == '.' &&
         (p[n - 3] == 'm' || p[n - 3] == 'M') &&
         (p[n - 2] == 'p' || p[n - 2] == 'P') && p[n - 1] == '3';
}

extern volatile int g_hide_saves; // main.c: set during New Game to hide saves

void *AAssetManager_open_fake(void *mgr, const char *path, int mode) {
  (void)mgr; (void)mode;
  // New Game: make GTA3LCSsf* slots look absent so game-init builds a fresh game
  if (g_hide_saves && path && strstr(path, "GTA3LCSsf")) {
    debugPrintf("AAsset: open(%s) -> HIDDEN (new game)\n", path);
    return NULL;
  }
  if (!index_maybe_exists(path))
    return NULL;
  void *embedded = open_embedded_uproject(path);
  if (embedded)
    return embedded;
  FILE *f = open_asset_with_fallback(path);
  if (!f) {
    if (path_is_mp3(path)) {
      FILE *sf = fmemopen((void *)silent_bin, silent_bin_size, "rb");
      if (sf) {
        debugPrintf("AAsset: open(%s) -> MISSING, silent.mp3 stand-in\n", path);
        Asset *a = calloc(1, sizeof(*a));
        a->f = sf;
        a->size = (long)silent_bin_size;
        a->buffer = NULL;
        return a;
      }
    }
    debugPrintf("AAsset: open(%s) -> MISSING\n", path);
    return NULL;
  }
  // fewer fsdev round trips for the parsers that read in small chunks
  setvbuf(f, NULL, _IOFBF, 16 * 1024);
  Asset *a = calloc(1, sizeof(*a));
  a->f = f;
  a->buffer = NULL;
  a->position = 0;
  fseek(f, 0, SEEK_END);
  a->size = ftell(f);
  fseek(f, 0, SEEK_SET);
  return a;
}

void AAsset_close_fake(void *asset) {
  Asset *a = asset;
  if (a) {
    if (a->f)
      fclose(a->f);
    free(a->buffer);
    free(a);
  }
}

int AAsset_read_fake(void *asset, void *buf, size_t count) {
  Asset *a = asset;
  if (!a)
    return -1;
  if (a->f)
    return (int)fread(buf, 1, count, a->f);
  const size_t requested = count;
  const size_t remaining = (size_t)(a->size - a->position);
  if (count > remaining)
    count = remaining;
  memcpy(buf, (const char *)a->buffer + a->position, count);
  a->position += (long)count;
  if (a->embedded_uproject)
    debugPrintf("AAsset: uproject read(%zu) -> %zu at %ld/%ld\n", requested,
                count, a->position, a->size);
  return (int)count;
}

long AAsset_seek_fake(void *asset, long off, int whence) {
  Asset *a = asset;
  if (!a)
    return -1;
  if (a->f) {
    if (fseek(a->f, off, whence) < 0)
      return -1;
    return ftell(a->f);
  }
  long next;
  if (whence == SEEK_SET)
    next = off;
  else if (whence == SEEK_CUR)
    next = a->position + off;
  else if (whence == SEEK_END)
    next = a->size + off;
  else
    return -1;
  if (next < 0 || next > a->size)
    return -1;
  a->position = next;
  if (a->embedded_uproject)
    debugPrintf("AAsset: uproject seek(%ld, %d) -> %ld\n", off, whence, next);
  return next;
}

int64_t AAsset_seek64_fake(void *asset, int64_t off, int whence) {
  return AAsset_seek_fake(asset, (long)off, whence);
}

long AAsset_getLength_fake(void *asset) {
  Asset *a = asset;
  if (a && a->embedded_uproject)
    debugPrintf("AAsset: uproject getLength -> %ld\n", a->size);
  return a ? a->size : 0;
}

int64_t AAsset_getLength64_fake(void *asset) {
  Asset *a = asset;
  if (a && a->embedded_uproject)
    debugPrintf("AAsset: uproject getLength64 -> %ld\n", a->size);
  return a ? a->size : 0;
}

long AAsset_getRemainingLength_fake(void *asset) {
  Asset *a = asset;
  if (!a)
    return 0;
  return a->size - (a->f ? ftell(a->f) : a->position);
}

int64_t AAsset_getRemainingLength64_fake(void *asset) {
  Asset *a = asset;
  if (!a)
    return 0;
  return a->size - (a->f ? ftell(a->f) : a->position);
}

const void *AAsset_getBuffer_fake(void *asset) {
  Asset *a = asset;
  if (!a)
    return NULL;
  if (!a->f) {
    if (a->embedded_uproject)
      debugPrintf("AAsset: uproject getBuffer -> %p\n", a->buffer);
    return a->buffer;
  }
  if (a->buffer)
    return a->buffer;

  const long position = ftell(a->f);
  a->buffer = malloc((size_t)a->size + 1);
  if (!a->buffer)
    return NULL;
  if (fseek(a->f, 0, SEEK_SET) < 0 ||
      fread(a->buffer, 1, (size_t)a->size, a->f) != (size_t)a->size) {
    free(a->buffer);
    a->buffer = NULL;
    return NULL;
  }
  ((unsigned char *)a->buffer)[a->size] = 0;
  if (position >= 0)
    fseek(a->f, position, SEEK_SET);
  return a->buffer;
}

int AAsset_openFileDescriptor_fake(void *asset, long *start, long *length) {
  Asset *a = asset;
  if (!a || !a->f) {
    if (a && a->embedded_uproject)
      debugPrintf("AAsset: uproject openFileDescriptor -> unavailable\n");
    return -1;
  }
  const int fd = dup(fileno(a->f));
  if (fd < 0)
    return -1;
  if (start)
    *start = 0;
  if (length)
    *length = a->size;
  if (a->embedded_uproject)
    debugPrintf("AAsset: uproject openFileDescriptor -> fd=%d len=%ld\n", fd,
                a->size);
  return fd;
}

int AAsset_openFileDescriptor64_fake(void *asset, int64_t *start,
                                     int64_t *length) {
  long start32 = 0;
  long length32 = 0;
  const int fd = AAsset_openFileDescriptor_fake(asset, &start32, &length32);
  if (fd >= 0) {
    if (start)
      *start = start32;
    if (length)
      *length = length32;
  }
  return fd;
}

// ---------------------------------------------------------------------------
// ANativeWindow -> NWindow mapping
// ---------------------------------------------------------------------------

void *ANativeWindow_fromSurface_fake(void *env, void *surface) {
  (void)env; (void)surface;
  NWindow *win = nwindowGetDefault();
  nwindowSetDimensions(win, screen_width, screen_height);
  debugPrintf("ANativeWindow_fromSurface -> %p (%dx%d)\n", win, screen_width, screen_height);
  return win;
}

int ANativeWindow_getWidth_fake(void *win) {
  (void)win;
  return screen_width;
}

int ANativeWindow_getHeight_fake(void *win) {
  (void)win;
  return screen_height;
}

void ANativeWindow_release_fake(void *win) {
  (void)win;
}

int ANativeWindow_setBuffersGeometry_fake(void *win, int w, int h, int format) {
  (void)format;
  debugPrintf("ANativeWindow_setBuffersGeometry(%d, %d)\n", w, h);
  if (w > 0 && h > 0)
    nwindowSetDimensions((NWindow *)win, w, h);
  return 0;
}

// ---------------------------------------------------------------------------
// pthread extras: rwlocks and semaphores via pointer indirection. The game
// allocates the bionic type; we stash a real-object pointer in its first bytes.
// ---------------------------------------------------------------------------

typedef struct {
  RwLock lock;
} FakeRwLock;

static FakeRwLock *get_rwlock(void **storage) {
  if (!*storage) {
    FakeRwLock *l = calloc(1, sizeof(*l));
    rwlockInit(&l->lock);
    *storage = l;
  }
  return *storage;
}

int pthread_rwlock_rdlock_fake(void **rw) {
  rwlockReadLock(&get_rwlock(rw)->lock);
  return 0;
}

int pthread_rwlock_wrlock_fake(void **rw) {
  rwlockWriteLock(&get_rwlock(rw)->lock);
  return 0;
}

int pthread_rwlock_unlock_fake(void **rw) {
  FakeRwLock *l = get_rwlock(rw);
  // libnx needs to know which way it was locked
  if (rwlockIsWriteLockHeldByCurrentThread(&l->lock))
    rwlockWriteUnlock(&l->lock);
  else
    rwlockReadUnlock(&l->lock);
  return 0;
}

typedef struct {
  Semaphore sem;
} FakeSem;

int sem_init_fake(void **s, int pshared, unsigned int value) {
  (void)pshared;
  FakeSem *fs = calloc(1, sizeof(*fs));
  semaphoreInit(&fs->sem, value);
  *s = fs;
  return 0;
}

int sem_destroy_fake(void **s) {
  if (s && *s) {
    free(*s);
    *s = NULL;
  }
  return 0;
}

int sem_post_fake(void **s) {
  if (s && *s)
    semaphoreSignal(&((FakeSem *)*s)->sem);
  return 0;
}

int sem_wait_fake(void **s) {
  if (s && *s)
    semaphoreWait(&((FakeSem *)*s)->sem);
  return 0;
}

int sem_trywait_fake(void **s) {
  if (s && *s && semaphoreTryWait(&((FakeSem *)*s)->sem))
    return 0;
  errno = EAGAIN;
  return -1;
}

int sem_getvalue_fake(void **s, int *val) {
  if (s && *s)
    *val = (int)((FakeSem *)*s)->sem.count;
  else
    *val = 0;
  return 0;
}

// Named POSIX semaphores: return a heap holder pointing at a FakeSem (the shape
// sem_init_fake leaves) so the unnamed sem_*_fake reuse it. Name ignored.
void *sem_open_fake(const char *name, int oflag, ...) {
  (void)name;
  unsigned int value = 0;
  if (oflag & LINUX_O_CREAT) {
    va_list va;
    va_start(va, oflag);
    (void)va_arg(va, int);             // mode_t
    value = va_arg(va, unsigned int);  // initial value
    va_end(va);
  }
  void **holder = calloc(1, sizeof(void *));
  if (!holder)
    return (void *)-1; // SEM_FAILED
  sem_init_fake(holder, 0, value);     // allocates the FakeSem into *holder
  return holder;
}

int sem_close_fake(void *s) {
  if (s) {
    sem_destroy_fake((void **)s);      // frees the FakeSem, nulls *s
    free(s);
  }
  return 0;
}

int sem_unlink_fake(const char *name) {
  (void)name;
  return 0;
}

int pthread_attr_getstacksize_fake(const void *attr, size_t *size) {
  (void)attr;
  *size = 512 * 1024;
  return 0;
}

int pthread_attr_getschedparam_fake(const void *attr, void *param) {
  (void)attr;
  memset(param, 0, 8);
  return 0;
}
