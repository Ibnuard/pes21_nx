"""Exercise the production Nouveau pool with refcounted fake BOs, not a GPU.

No native game payload is required. These detect retention/fragmentation;
they cannot establish the cause of a hardware frame-rate regression.
"""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

STUBS = r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#undef assert
#define assert(c) do { if (!(c)) { fprintf(stderr, "line %d: %s\n", __LINE__, #c); exit(97); } } while (0)
typedef struct { void *dev; unsigned char pad[840]; uint32_t domain,config; } Cache;
_Static_assert(offsetof(Cache,domain)==848 && offsetof(Cache,config)==852,"cache ABI");
typedef struct { unsigned refs; uint64_t size; } Bo;
static uint64_t live_bytes, peak_bytes;
static unsigned created, failed_bo, failed_malloc;
static pthread_mutex_t bo_mutex=PTHREAD_MUTEX_INITIALIZER;
int nouveau_bo_new(void *dev,uint32_t flags,uint32_t align,uint64_t size,const void *config,void **out) {
  (void)dev;(void)flags;(void)align;(void)config;
  if(failed_bo) { --failed_bo; *out=NULL; return -1; }
  Bo *bo=calloc(1,sizeof(*bo)); assert(bo); bo->size=size;bo->refs=1;
  pthread_mutex_lock(&bo_mutex);
  live_bytes+=size; if(live_bytes>peak_bytes)peak_bytes=live_bytes;created++;
  pthread_mutex_unlock(&bo_mutex);*out=bo;return 0;
}
int nouveau_bo_ref(void *in,void **out) {
  pthread_mutex_lock(&bo_mutex);
  Bo *bo=in,*old=*out;
  if(bo) { assert(bo->refs);bo->refs++; }
  *out=bo;
  if(old) { assert(old->refs); if(!--old->refs) { live_bytes-=old->size;free(old); } }
  pthread_mutex_unlock(&bo_mutex);return 0;
}
static void *test_malloc(size_t size) {
  if(failed_malloc) { --failed_malloc;return NULL; } return malloc(size);
}
#define malloc test_malloc
'''

DRIVER = r'''
#undef malloc
static void release(void *handle,void **bo) {
  __wrap_nouveau_mm_free_work(handle);nouveau_bo_ref(NULL,bo);
}
static void clear_pool(void) {
  for(int i=0;i<g_nmm_nslabs;i++) {
    struct nmm_slab *s=&g_nmm_slabs[i];
    while(s->free_list) { struct nmm_alloc *next=s->free_list->next;free(s->free_list);s->free_list=next; }
    if(s->bo)nouveau_bo_ref(NULL,&s->bo);
  }
  memset(g_nmm_slabs,0,sizeof(g_nmm_slabs));g_nmm_nslabs=0;
  assert(live_bytes==0);
}
static void *stress(void *arg) {
  Cache *cache=arg;
  for(unsigned cycle=0;cycle<300;cycle++) {
    void *bo[24]={0},*h[24];uint32_t off;
    for(unsigned i=0;i<24;i++) {
      h[i]=__wrap_nouveau_mm_allocate(cache,(i+1)*256,&bo[i],&off);
      assert(h[i] && bo[i] && off%256==0);
      for(unsigned j=0;j<i;j++)if(bo[j]==bo[i]) {
        struct nmm_alloc *a=h[i],*b=h[j];
        assert(a->offset+a->size<=b->offset || b->offset+b->size<=a->offset);
      }
    }
    for(unsigned i=0;i<24;i+=2)release(h[i],&bo[i]);
    for(unsigned i=1;i<24;i+=2)release(h[i],&bo[i]);
  }
  return NULL;
}
int main(int argc,char **argv) {
  assert(argc==2);Cache cache={0},other={0};uint32_t off=0;
  if(!strcmp(argv[1],"split")) {
    void *anchor_bo=NULL,*big_bo=NULL,*small_bo=NULL,*next_bo=NULL;
    void *anchor=__wrap_nouveau_mm_allocate(&cache,256,&anchor_bo,&off);
    void *big=__wrap_nouveau_mm_allocate(&cache,512*1024,&big_bo,&off);
    release(big,&big_bo);
    struct nmm_alloc *small=__wrap_nouveau_mm_allocate(&cache,256,&small_bo,&off);
    assert(small && small->size==256 && off==256);
    struct nmm_alloc *next=__wrap_nouveau_mm_allocate(&cache,512*1024-256,&next_bo,&off);
    assert(next && off==512 && created==1);
    release(small,&small_bo);release(next,&next_bo);release(anchor,&anchor_bo);
  } else if(!strcmp(argv[1],"retention")) {
    for(unsigned cycle=0;cycle<250;cycle++) {
      void *bo[48]={0},*h[48];
      for(unsigned i=0;i<48;i++) { h[i]=__wrap_nouveau_mm_allocate(&cache,512*1024,&bo[i],&off);assert(h[i]); }
      for(unsigned i=0;i<48;i++)release(h[i],&bo[i]);
      assert(live_bytes<=NMM_SLAB_BYTES);
      assert(g_nmm_nslabs<=12); // Freed descriptors are reused, not appended forever.
    }
    assert(peak_bytes==12u*NMM_SLAB_BYTES);
  } else if(!strcmp(argv[1],"failure")) {
    void *bo=NULL;failed_malloc=1;
    assert(!__wrap_nouveau_mm_allocate(&cache,256,&bo,&off) && !bo && !live_bytes);
    failed_bo=2;
    assert(!__wrap_nouveau_mm_allocate(&cache,256,&bo,&off) && !bo && !live_bytes);
    assert(!__wrap_nouveau_mm_allocate(&cache,UINT32_MAX,&bo,&off) && !bo && !live_bytes);
    void *h=__wrap_nouveau_mm_allocate(&cache,0,&bo,&off);assert(h && bo);release(h,&bo);
    h=__wrap_nouveau_mm_allocate(&cache,NMM_BIG_THRESH+1,&bo,&off);
    assert(!h && bo && !off);release(h,&bo);
  } else if(!strcmp(argv[1],"lifetime")) {
    void *bo[16]={0},*h[16],*held=NULL;
    for(unsigned i=0;i<16;i++)h[i]=__wrap_nouveau_mm_allocate(i%2?&cache:&other,512*1024,&bo[i],&off);
    nouveau_bo_ref(bo[0],&held);
    for(unsigned i=0;i<16;i++)release(h[i],&bo[i]);
    assert(((Bo*)held)->refs && ((Bo*)held)->size==NMM_SLAB_BYTES);
    nouveau_bo_ref(NULL,&held);assert(live_bytes<=2u*NMM_SLAB_BYTES);
  } else if(!strcmp(argv[1],"threaded")) {
    pthread_t threads[4];
    for(unsigned i=0;i<4;i++)assert(!pthread_create(&threads[i],NULL,stress,i<2?&cache:&other));
    for(unsigned i=0;i<4;i++)assert(!pthread_join(threads[i],NULL));
    assert(live_bytes<=2u*NMM_SLAB_BYTES);
  } else assert(0);
  clear_pool();return 0;
}
'''


class GpuBufferPoolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which('gcc') or shutil.which('clang')
        if not compiler:
            raise unittest.SkipTest('Host C compiler unavailable')
        cls.temp = tempfile.TemporaryDirectory(prefix='pesnx-gpu-pool-')
        cls.addClassCleanup(cls.temp.cleanup)
        source = (ROOT/'source/imports.c').read_text()
        pool = source.split('extern int nouveau_bo_new(', 1)[1]
        pool = 'extern int nouveau_bo_new(' + pool.split('// The world load creates', 1)[0]
        path = Path(cls.temp.name)/'pool.c'
        path.write_text(STUBS + pool + DRIVER)
        cls.exe = Path(cls.temp.name)/'pool.exe'
        sanitizers = os.environ.get('PESNX_POOL_SANITIZERS', '')
        sanitizer_flags = (['-g', '-fno-omit-frame-pointer',
                            '-fsanitize=' + sanitizers] if sanitizers else [])
        subprocess.run([compiler,'-std=c11','-Wall','-Wextra','-Werror','-pthread',
                        *sanitizer_flags, str(path),'-o',str(cls.exe)],
                       check=True,capture_output=True)

    def test_pool_lifecycle(self):
        for case in ('split','retention','failure','lifetime','threaded'):
            with self.subTest(case=case):
                result = subprocess.run([str(self.exe),case],capture_output=True,text=True,timeout=30)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__ == '__main__':
    unittest.main()
