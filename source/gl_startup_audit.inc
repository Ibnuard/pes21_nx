/* Opt-in observation of native calls. No added GL queries, waits, or draw hooks.
 * Counts are cumulative across all native GL threads; events carry wrapper slot
 * numbers, not GL handles/pointers. A zero count is not proof of visibility. */
enum {
  NX_START_COMPILE_OK, NX_START_COMPILE_FAIL, NX_START_LINK_OK, NX_START_LINK_FAIL,
  NX_START_BINARY, NX_START_BINARY_OES, NX_START_LINK_QUERY, NX_START_LINK_REJECT,
  NX_START_MAP, NX_START_MAP_FAIL, NX_START_UNMAP, NX_START_UNMAP_FAIL,
  NX_START_ERROR_QUERY, NX_START_ERROR, NX_START_BUFFER, NX_START_TEXTURE,
  NX_START_FLUSH, NX_START_MAKE_OK, NX_START_MAKE_FAIL, NX_START_COUNTS
};
static uint64_t nx_start_counts[NX_START_COUNTS];
static struct { unsigned ready, kind, code, route; int slot; } nx_start_events[16];
static unsigned nx_start_event_next;

static void nx_start_count(unsigned kind) {
  __atomic_fetch_add(&nx_start_counts[kind], 1, __ATOMIC_RELAXED);
}
static void nx_start_failure(unsigned kind, unsigned code, unsigned route) {
  const unsigned i=__atomic_fetch_add(&nx_start_event_next,1,__ATOMIC_RELAXED);
  if (i>=16) return;
  nx_start_events[i].kind=kind; nx_start_events[i].code=code;
  nx_start_events[i].route=route; nx_start_events[i].slot=mc_current_slot();
  __atomic_store_n(&nx_start_events[i].ready,1,__ATOMIC_RELEASE);
}

static GLenum glGetError_startup(void) {
  const GLenum result=glGetError(); /* Exactly the engine's query. */
  nx_start_count(NX_START_ERROR_QUERY);
  if (result) {
    nx_start_count(NX_START_ERROR);
    nx_start_failure(NX_START_ERROR,result,0);
  }
  return result;
}
static void glGetProgramiv_startup(GLuint p, GLenum name, GLint *value) {
  glGetProgramiv(p,name,value);
  if (name==GL_LINK_STATUS && value) {
    nx_start_count(NX_START_LINK_QUERY);
    if (*value==GL_FALSE) {
      nx_start_count(NX_START_LINK_REJECT);
      nx_start_failure(NX_START_LINK_REJECT,0,0);
    }
  }
}
typedef void *(*NxStartMap)(GLenum,GLintptr,GLsizeiptr,GLbitfield);
typedef void *(*NxStartMapOes)(GLenum,GLenum);
typedef GLboolean (*NxStartUnmap)(GLenum);
static NxStartMap nx_start_map, nx_start_map_ext;
static NxStartMapOes nx_start_map_oes;
static NxStartUnmap nx_start_unmap, nx_start_unmap_oes;

#define NX_START_MAP_WRAPPER(api, pointer, route) \
static void *api(GLenum t,GLintptr o,GLsizeiptr n,GLbitfield a) { \
  const NxStartMap driver=__atomic_load_n(&pointer,__ATOMIC_ACQUIRE); \
  void *result=driver(t,o,n,a); nx_start_count(NX_START_MAP); \
  if (!result) { nx_start_count(NX_START_MAP_FAIL); \
    nx_start_failure(NX_START_MAP_FAIL,0,route); } return result; \
}
NX_START_MAP_WRAPPER(glMapBufferRange_startup,nx_start_map,1)
NX_START_MAP_WRAPPER(glMapBufferRangeEXT_startup,nx_start_map_ext,2)
#undef NX_START_MAP_WRAPPER
static void *glMapBufferOES_startup(GLenum t,GLenum a) {
  const NxStartMapOes driver=__atomic_load_n(&nx_start_map_oes,__ATOMIC_ACQUIRE);
  void *result=driver(t,a); nx_start_count(NX_START_MAP);
  if (!result) { nx_start_count(NX_START_MAP_FAIL);
    nx_start_failure(NX_START_MAP_FAIL,0,3); } return result;
}
#define NX_START_UNMAP_WRAPPER(api, pointer, route) \
static GLboolean api(GLenum t) { \
  const NxStartUnmap driver=__atomic_load_n(&pointer,__ATOMIC_ACQUIRE); \
  const GLboolean result=driver(t); nx_start_count(NX_START_UNMAP); \
  if (!result) { nx_start_count(NX_START_UNMAP_FAIL); \
    nx_start_failure(NX_START_UNMAP_FAIL,0,route); } return result; \
}
NX_START_UNMAP_WRAPPER(glUnmapBuffer_startup,nx_start_unmap,1)
NX_START_UNMAP_WRAPPER(glUnmapBufferOES_startup,nx_start_unmap_oes,3)
#undef NX_START_UNMAP_WRAPPER

static __eglMustCastToProperFunctionPointerType nx_start_proc(
    const char *name,__eglMustCastToProperFunctionPointerType proc) {
  if (!name || !proc) return NULL;
  if (!strcmp(name,"glGetError"))
    return (__eglMustCastToProperFunctionPointerType)glGetError_startup;
  if (!strcmp(name,"glGetProgramiv"))
    return (__eglMustCastToProperFunctionPointerType)glGetProgramiv_startup;
#define NX_START_PROC(api, pointer, type) \
  if (!strcmp(name,#api)) { \
    __atomic_store_n(&pointer,(type)proc,__ATOMIC_RELEASE); \
    return (__eglMustCastToProperFunctionPointerType)api##_startup; }
  NX_START_PROC(glMapBufferRange,nx_start_map,NxStartMap)
  NX_START_PROC(glMapBufferRangeEXT,nx_start_map_ext,NxStartMap)
  NX_START_PROC(glMapBufferOES,nx_start_map_oes,NxStartMapOes)
  NX_START_PROC(glUnmapBuffer,nx_start_unmap,NxStartUnmap)
  NX_START_PROC(glUnmapBufferOES,nx_start_unmap_oes,NxStartUnmap)
#undef NX_START_PROC
  return NULL;
}

/* Called only at presentation boundaries. No journal I/O while in live play.
 * Loading/driver errors remain in RAM until Pause; at most eight snapshots. */
static void nx_start_present(int live,unsigned session) {
  static unsigned began, was_live, snapshots, emitted;
  if (!live && (!began || was_live) && snapshots<8) {
    if (!began) {
      scene_runtime_note("startup render audit",
        "v56 observe-only; build=" PESNX_BUILD_ID
        "; no extra GL queries/waits; binary counts are attempts, not cache hits");
      began=1;
    }
    uint64_t v[NX_START_COUNTS];
    for (unsigned i=0;i<NX_START_COUNTS;++i)
      v[i]=__atomic_load_n(&nx_start_counts[i],__ATOMIC_RELAXED);
    char line[768];
    snprintf(line,sizeof(line),"snapshot=%u session=%u compile=%llu/%llu link=%llu/%llu binary_attempts=%llu/%llu native_link_queries=%llu native_link_rejects=%llu",
      ++snapshots,session,(unsigned long long)v[0],(unsigned long long)v[1],
      (unsigned long long)v[2],(unsigned long long)v[3],
      (unsigned long long)v[4],(unsigned long long)v[5],
      (unsigned long long)v[6],(unsigned long long)v[7]);
    scene_runtime_note("startup shaders",line);
    snprintf(line,sizeof(line),"snapshot=%u buffer_data=%llu texture_image=%llu periodic_flush=%llu map_calls=%llu map_failures=%llu unmap_calls=%llu unmap_failures=%llu native_error_checks=%llu native_errors=%llu make_current=%llu/%llu (all threads; wrapped calls only; no visibility proof)",
      snapshots,(unsigned long long)v[14],(unsigned long long)v[15],
      (unsigned long long)v[16],(unsigned long long)v[8],(unsigned long long)v[9],
      (unsigned long long)v[10],(unsigned long long)v[11],
      (unsigned long long)v[12],(unsigned long long)v[13],
      (unsigned long long)v[17],(unsigned long long)v[18]);
    scene_runtime_note("startup resources",line);
    while (emitted<16 && __atomic_load_n(&nx_start_events[emitted].ready,__ATOMIC_ACQUIRE)) {
      snprintf(line,sizeof(line),"index=%u kind=%u code=0x%x route=%u context_slot=%d",
        emitted,nx_start_events[emitted].kind,nx_start_events[emitted].code,
        nx_start_events[emitted].route,nx_start_events[emitted].slot);
      scene_runtime_note("startup observed failure",line); ++emitted;
    }
  }
  was_live=live!=0;
}
