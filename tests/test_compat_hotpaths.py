from pathlib import Path
import shutil
import sys
import unittest
from test_gameplan_editor import function
from test_result_flow import build_and_run

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from benchmark_compat_tls import PRELUDE,tls_block

TRACK=r'''
static unsigned test_rmw_calls,test_load_calls;
#define __sync_fetch_and_add(p,v) (__atomic_fetch_add(&test_rmw_calls,1,__ATOMIC_RELAXED),__atomic_fetch_add((p),(v),__ATOMIC_SEQ_CST))
#define __atomic_load_n(p,o) (__atomic_fetch_add(&test_load_calls,1,__ATOMIC_RELAXED),__atomic_load_n((p),(o)))
'''


class CompatHotpathTests(unittest.TestCase):
    def run_c(self,code):
        cc=shutil.which('gcc')
        if not cc:self.skipTest('host gcc unavailable')
        build_and_run(cc,code)

    def test_release_tls_keeps_values_and_has_no_trace_rmw(self):
        self.run_c(PRELUDE+TRACK+tls_block((ROOT/'source/imports.c').read_text())+r'''
int main(void) {
 pthread_key_t key;assert(!pthread_key_create_fake(&key,NULL));
 test_identity=(void *)0x10000;assert(pthread_getspecific_fake(key)==NULL);
 assert(!pthread_setspecific_fake(key,(void *)17));
 unsigned rmw=test_rmw_calls;
 for(unsigned i=0;i<100000;i++)assert(pthread_getspecific_fake(key)==(void *)17);
 assert(test_rmw_calls==rmw);
 test_identity=(void *)0x20000;assert(pthread_getspecific_fake(key)==NULL);
 assert(!pthread_setspecific_fake(key,(void *)23));
 test_identity=(void *)0x10000;assert(pthread_getspecific_fake(key)==(void *)17);
 assert(!pthread_setspecific_fake(key,NULL));assert(!pthread_getspecific_fake(key));
 test_identity=(void *)0x20000;assert(pthread_getspecific_fake(key)==(void *)23);
 assert(!pthread_key_delete_fake(key));assert(pthread_getspecific_fake(key)==NULL);
 assert(pthread_setspecific_fake(key,(void *)1)==EINVAL);
 assert(pthread_key_delete_fake(key)==EINVAL);
 assert(pthread_key_create_fake(NULL,NULL)==EINVAL);
 assert(!pthread_getspecific_fake(0));assert(!pthread_getspecific_fake(4096));
 /* A changed Android identity cannot use another thread's row when full. */
 pthread_key_t other;assert(!pthread_key_create_fake(&other,NULL));
 for(uintptr_t id=1;id<=62;id++) {test_identity=(void *)id;assert(!pthread_setspecific_fake(other,(void *)id));}
 test_identity=(void *)0x30000;assert(pthread_setspecific_fake(other,(void *)1)==EAGAIN);
 test_identity=(void *)1;assert(pthread_getspecific_fake(other)==(void *)1);
}
''')

    def test_thread_rows_remain_separate_under_hash_collisions(self):
        self.run_c(PRELUDE+tls_block((ROOT/'source/imports.c').read_text())+r'''
static pthread_key_t key;
static void *worker(void *arg) {
 uintptr_t id=(uintptr_t)arg;test_identity=(void *)id;
 assert(!pthread_getspecific_fake(key));assert(!pthread_setspecific_fake(key,(void *)id));
 for(unsigned i=0;i<20000;i++)assert(pthread_getspecific_fake(key)==(void *)id);
 return NULL;
}
int main(void) {
 assert(!pthread_key_create_fake(&key,NULL));pthread_t workers[4];unsigned count=0;
 for(uintptr_t id=0x10000;count<4;id+=16) {
  if(((id>>4)^(id>>12)^(id>>20))&63u)continue;
  assert(!pthread_create(&workers[count++],NULL,worker,(void *)id));
 }
 for(unsigned i=0;i<4;i++)assert(!pthread_join(workers[i],NULL));
 unsigned rows=0;for(unsigned i=0;i<64;i++)rows+=fake_tls_thread_ids[i]!=NULL;
 assert(rows==4);
}
''')

    def test_clock_values_and_errors_preserved_without_release_log_rmw(self):
        source=function((ROOT/'source/imports.c').read_text(),'clock_gettime_android')
        self.run_c(PRELUDE+TRACK+r'''
#include <sys/time.h>
static uint64_t armGetSystemTick(void) {return 1234567891;}
static uint64_t armGetSystemTickFreq(void) {return 1000000000;}
'''+source+r'''
int main(void) {
 struct timespec t;
 for(unsigned i=0;i<10000;i++) {
  assert(!clock_gettime_android(1,&t));assert(t.tv_sec==1&&t.tv_nsec==234567891);
 }
 assert(test_rmw_calls==0);
 assert(!clock_gettime_android(0,&t));assert(t.tv_sec>0);
 assert(clock_gettime_android(42,&t)==-1&&errno==EINVAL);
 assert(clock_gettime_android(1,NULL)==-1&&errno==EFAULT);
}
''')

    def test_debug_build_retains_bounded_tls_logging(self):
        self.run_c('#define DEBUG_LOG 1\n'+PRELUDE+TRACK+
                   tls_block((ROOT/'source/imports.c').read_text())+r'''
int main(void) {
 pthread_key_t key;test_identity=(void *)1;
 assert(!pthread_key_create_fake(&key,NULL));assert(!pthread_setspecific_fake(key,(void *)2));
 assert(pthread_getspecific_fake(key)==(void *)2);
 assert(pthread_tls_get_trace_count==1&&pthread_tls_set_trace_count==1);
}
''')
