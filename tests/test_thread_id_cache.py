"""Execute the actual libc routes; successful thread IDs need one kernel query."""
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_thread_identity_success_failure_and_syscall_routes():
    cc = shutil.which('gcc') or shutil.which('clang')
    if not cc:
        pytest.skip('host C compiler required')
    source = (ROOT/'source/libc_shim.c').read_text()
    block = source[source.index('int gettid_fake(void)'):source.index('void sincosf_fake')]
    harness = r'''
#include <assert.h>
#include <stdint.h>
#include <stdarg.h>
#include <stddef.h>
#include <string.h>
#include <errno.h>
#include <pthread.h>
typedef uint64_t u64;
#define R_SUCCEEDED(r) ((r)==0)
#define CUR_THREAD_HANDLE 42
#define debugPrintf(...) ((void)0)
static __thread u64 identity;
static __thread unsigned calls, failures;
static int svcGetThreadId(u64 *out, int handle) {
  assert(handle==42); ++calls;
  if(failures) {--failures; *out=99; return -1;}
  *out=identity; return 0;
}
''' + block + r'''
static void *worker(void *arg) {
  identity=(uintptr_t)arg;
  assert(calls==0);
  failures=1;
  assert(gettid_fake()==1 && calls==1); /* Failure must not cache fallback. */
  u64 good=identity; identity=0;
  assert(gettid_fake()==1 && calls==2); /* Zero must be retried too. */
  identity=good;
  const int expected=(int)(identity & 0x7fffffff);
  for(unsigned i=0;i<100000;i++) {
    assert(gettid_fake()==expected);
    assert(syscall_fake(178)==expected);
  }
  assert(calls==3); /* 200k successes share precisely one native query. */
  unsigned cpu=99,node=99;
  assert(syscall_fake(168,&cpu,&node,NULL)==0);
  assert(cpu==(unsigned)expected%3 && node==0 && calls==3);
  return NULL;
}
int main(void) {
  pthread_t t[4];
  for(unsigned round=0;round<3;round++) {
    for(uintptr_t i=0;i<4;i++)
      assert(!pthread_create(&t[i],NULL,worker,(void *)(0x80000000ULL+i+round*11)));
    for(unsigned i=0;i<4;i++)assert(!pthread_join(t[i],NULL));
  }
  /* Main-thread storage never borrowed a worker ID, even after thread reuse. */
  assert(calls==0);identity=456;assert(gettid_fake()==456 && calls==1);
  assert(syscall_fake(999)==-1 && errno==ENOSYS && calls==1);
}
'''
    with tempfile.TemporaryDirectory(prefix='pesnx-tid-') as temp:
        c, exe = Path(temp)/'tid.c', Path(temp)/'tid.exe'
        c.write_text(harness)
        subprocess.run([cc,'-O2','-std=c11','-Wall','-Wextra','-Werror','-pthread',
                        str(c),'-o',str(exe)],check=True,capture_output=True)
        subprocess.run([str(exe)],check=True,capture_output=True,timeout=30)


def test_both_android_imports_use_the_shared_identity_route():
    source = (ROOT/'source/imports.c').read_text()
    assert '{ "gettid", (uintptr_t)&gettid_fake }' in source
    assert '{ "syscall", (uintptr_t)&syscall_fake }' in source
