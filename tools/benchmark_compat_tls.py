"""Benchmark the authored TLS shim with 1/4 host threads, not Switch FPS.

Uses the exact shim block from imports.c or a saved authored baseline block.
No game library, assets, GPU, native Switch execution or installation needed.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def tls_block(text):
    start=text.index('#define FAKE_TLS_MAX_KEYS')
    stop=text.find('// Each pthread_create',start)
    return text[start:stop if stop>=0 else len(text)]


PRELUDE=r'''
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>
#include <time.h>
#include <stdarg.h>
/* Android/native wrapper keys are numeric; MSYS uses an opaque pointer. */
typedef unsigned TestAndroidKey;
#define pthread_key_t TestAndroidKey
static __thread void *test_identity;
static void *mc_thread_key(void) {return test_identity;}
static int debugPrintf(const char *text,...) {(void)text;return 0;}
'''

BENCH=r'''
static pthread_key_t shared_key;
static unsigned iterations;
static void *worker(void *arg) {
  uintptr_t id=(uintptr_t)arg+1;
  test_identity=(void *)(0x100000+id*0x100);
  assert(!pthread_setspecific_fake(shared_key,(void *)id));
  uintptr_t sum=0;
  for(unsigned i=0;i<iterations;i++)sum+=(uintptr_t)pthread_getspecific_fake(shared_key);
  assert(sum==id*iterations);return NULL;
}
static uint64_t now_ns(void) {
 struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);
 return (uint64_t)t.tv_sec*1000000000u+t.tv_nsec;
}
int main(int argc,char **argv) {
 assert(argc==3);unsigned count=(unsigned)atoi(argv[1]);iterations=(unsigned)atoi(argv[2]);
 assert(count && count<=4 && iterations);assert(!pthread_key_create_fake(&shared_key,NULL));
 pthread_t threads[4];uint64_t begin=now_ns();
 for(unsigned i=0;i<count;i++)assert(!pthread_create(&threads[i],NULL,worker,(void *)(uintptr_t)i));
 for(unsigned i=0;i<count;i++)assert(!pthread_join(threads[i],NULL));
 printf("{\"threads\":%u,\"lookups\":%llu,\"elapsed_ns\":%llu}\n",count,
        (unsigned long long)count*iterations,(unsigned long long)(now_ns()-begin));
}
'''


def benchmark(source,iterations=500000,trials=3):
    cc=shutil.which('gcc') or shutil.which('clang')
    if not cc:raise RuntimeError('Host C compiler required')
    with tempfile.TemporaryDirectory(prefix='pesnx-tls-bench-') as tmp:
        code=Path(tmp)/'bench.c';exe=Path(tmp)/'bench.exe'
        code.write_text(PRELUDE+tls_block(Path(source).read_text())+BENCH)
        subprocess.run([cc,'-O2','-pthread',str(code),'-o',str(exe)],check=True)
        rows=[]
        for threads in (1,4):
            for trial in range(trials):
                row=json.loads(subprocess.check_output([str(exe),str(threads),str(iterations)],text=True))
                row['trial']=trial+1;row['ns_per_lookup']=round(row['elapsed_ns']/row['lookups'],2)
                rows.append(row)
        return dict(source=str(Path(source).resolve()),compiler=cc,scope='host synthetic TLS throughput; not Switch FPS',results=rows)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=ROOT/'source/imports.c')
    p.add_argument('--iterations',type=int,default=500000)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=benchmark(a.source,a.iterations)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))


if __name__=='__main__':main()
