/* Included by imports.c only in the bounded NearCameraTrace build. */
#include "gpu_timestamp_probe.h"
typedef void (*NxGenQueries)(int,unsigned *);
typedef const unsigned char *(*NxGetStringi)(unsigned,unsigned);
static struct {
  NxGpuProbe probe;
  NxGpuApi api;
  NxNearContext context;
  unsigned initialized, first_draw, disjoint, supported;
  uint64_t camera;
  uintptr_t owner;
} gpu_probes[MC_SLOTS];

static void nx_gpu_check_owner(unsigned slot) {
  const uintptr_t owner=(uintptr_t)g_mc[slot].ctx;
  if (gpu_probes[slot].owner!=owner) {
    memset(&gpu_probes[slot],0,sizeof(gpu_probes[slot]));
    gpu_probes[slot].owner=owner;
  }
}

static void *nx_gpu_proc(const char *core,const char *ext) {
  void *p=(void *)eglGetProcAddress(core);
  return p?p:(void *)eglGetProcAddress(ext);
}
static int nx_gpu_has_extension(const char *name,int major) {
  NxGetStringi get_string_i=(void *)eglGetProcAddress("glGetStringi");
  if (major>=3 && get_string_i) {
    GLint count=0; glGetIntegerv(0x821du,&count); /* GL_NUM_EXTENSIONS */
    if (count<0 || count>4096) return 0;
    for (int i=0;i<count;++i) {
      const char *s=(const char *)get_string_i(GL_EXTENSIONS,(unsigned)i);
      if (s && !strcmp(s,name)) return 1;
    }
    return 0;
  }
  const char *s=(const char *)glGetString(GL_EXTENSIONS);
  if (!s) return 0;
  const size_t n=strlen(name);
  for (const char *at=s;(at=strstr(at,name));at+=n)
    if ((at==s || at[-1]==' ') && (!at[n] || at[n]==' ')) return 1;
  return 0;
}
static void nx_gpu_init(unsigned slot) {
  if (gpu_probes[slot].initialized) return;
  gpu_probes[slot].initialized=1;
  const char *version=(const char *)glGetString(GL_VERSION);
  int major=0,minor=0;
  const int es=version && strstr(version,"OpenGL ES");
  if (version) {
    const char *digit=version;
    while (*digit && (*digit<'0' || *digit>'9')) ++digit;
    if (*digit) sscanf(digit,"%d.%d",&major,&minor);
  }
  const int core=!es && (major>3 || (major==3 && minor>=3));
  const int ext=nx_gpu_has_extension("GL_EXT_disjoint_timer_query",major);
  if (!core && !ext && !nx_gpu_has_extension("GL_ARB_timer_query",major)) return;
  NxGenQueries gen=(void *)nx_gpu_proc("glGenQueries","glGenQueriesEXT");
  NxGpuApi *a=&gpu_probes[slot].api;
  a->counter=(void *)nx_gpu_proc("glQueryCounter","glQueryCounterEXT");
  a->available=(void *)nx_gpu_proc("glGetQueryObjectuiv","glGetQueryObjectuivEXT");
  a->result=(void *)nx_gpu_proc("glGetQueryObjectui64v","glGetQueryObjectui64vEXT");
  if (!gen || !a->counter || !a->available || !a->result) return;
  unsigned ids[NX_GPU_SLOTS*2]={0}; gen(NX_GPU_SLOTS*2,ids);
  for (unsigned i=0;i<NX_GPU_SLOTS;++i) {
    if (!ids[i*2] || !ids[i*2+1]) return;
    memcpy(gpu_probes[slot].probe.samples[i].query,&ids[i*2],sizeof(unsigned)*2);
  }
  gpu_probes[slot].disjoint=ext && !core;
  gpu_probes[slot].probe.enabled=1;
  gpu_probes[slot].supported=1;
}
static void nx_gpu_draw_begin(void) {
  const int slot=mc_current_slot();
  if (slot<0) return;
  nx_gpu_check_owner((unsigned)slot);
  if (gpu_probes[slot].first_draw++) return;
  if (!gpu_probes[slot].context.live) return;
  nx_gpu_init((unsigned)slot);
  gpu_probes[slot].camera=nx_near_view_sample();
  nx_gpu_begin(&gpu_probes[slot].probe,&gpu_probes[slot].api,
               gpu_probes[slot].camera);
}
static void nx_gpu_before_swap(int slot) {
  if (slot>=0) nx_gpu_end(&gpu_probes[slot].probe,&gpu_probes[slot].api);
}
static void nx_gpu_after_swap(int slot,const NxNearContext *context) {
  if (slot<0) return;
  nx_gpu_check_owner((unsigned)slot);
  NxGpuProbe *p=&gpu_probes[slot].probe;
  const int changed=memcmp(context,&gpu_probes[slot].context,sizeof(*context));
  if (changed || !context->live) nx_gpu_discard(p);
  GLint disjoint=0;
  if (p->enabled && gpu_probes[slot].disjoint)
    glGetIntegerv(0x8fbbu,&disjoint); /* GL_GPU_DISJOINT_EXT */
  if (disjoint) nx_gpu_discard(p);
  if (p->enabled && !changed && context->live)
    for (unsigned i=0;i<NX_GPU_SLOTS;++i) {
      uint64_t tag,ns;
      if (nx_gpu_poll(p,&gpu_probes[slot].api,i,&tag,&ns)) nx_near_gpu(ns,tag);
    }
  nx_near_gpu_support(gpu_probes[slot].supported);
  gpu_probes[slot].context=*context; gpu_probes[slot].first_draw=0;
}
