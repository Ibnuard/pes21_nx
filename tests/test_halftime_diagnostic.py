"""Run the actual halftime initializer in release and diagnostic configurations."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from test_gameplan_editor import function

ROOT=Path(__file__).resolve().parents[1]


class HalftimeDiagnosticTests(unittest.TestCase):
    def test_loading_retry_never_touches_unready_layout(self):
        cc=shutil.which('gcc')
        if not cc:self.skipTest('Host C compiler unavailable')
        hooks=(ROOT/'source/ue4_hooks.c').read_text()
        source=r'''
#include <stdint.h>
#include <stdio.h>
#include <assert.h>
enum { MATCH_RESULT_PAGE_STATS=1, MATCH_RESULT_SURFACE_HALF_STATS=2, MATCH_RESULT_SURFACE_FULL_STATS=3 };
static uint32_t match_result_page,skin_calls,native_ready,native_calls;
static uint64_t match_result_seen_tick,match_result_cover_tick;
static void match_result_clear_handoff(void){}
static uint32_t match_result_interval_surface(uint32_t a,uint32_t b){(void)b;return a;}
static void match_result_set_surface(uint32_t a){(void)a;}
static uint64_t armGetSystemTick(void){return 42u;}
static int match_stats_init_original(void *p){assert(p);native_calls++;return native_ready;}
static void match_result_prepare_skin(void *p){assert(p && native_ready);skin_calls++;}
#ifdef DEBUG_LOG
static int ml_frontend_match_active(void){return 1;}
#define debugPrintf(...) printf(__VA_ARGS__)
#endif
'''+function(hooks,'pes_match_stats_init')+r'''
int main(void){
 int window=0;
 for(int i=0;i<12;i++)assert(!pes_match_stats_init(&window));
 assert(!skin_calls && native_calls==12 && match_result_cover_tick==42);
 native_ready=1;assert(pes_match_stats_init(&window));
 assert(skin_calls==1 && native_calls==13);return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'halftime.c';path.write_text(source)
            for diagnostic in (False,True):
                exe=Path(tmp)/'halftime.exe'
                subprocess.run([cc,'-std=c11','-Wall','-Wextra','-Werror',
                    *(['-DDEBUG_LOG=1'] if diagnostic else []),str(path),'-o',str(exe)],check=True)
                result=subprocess.run([str(exe)],check=True,capture_output=True,text=True)
                self.assertEqual(result.stdout.count('halftime stats init begin'),8 if diagnostic else 0)

    def test_diagnostic_logging_flushes_each_breadcrumb(self):
        util=(ROOT/'source/util.c').read_text()
        self.assertIn('fflush',function(util,'debugPrintf'))
        hooks=(ROOT/'source/ue4_hooks.c').read_text()
        for marker in ('ml-v5-diag: stats native InitMobile enter',
                       'ml-v5-diag: result create enter',
                       'ml-v5-diag: substitute native begin',
                       'ml-v5-diag: halftime menu enter'):
            self.assertIn(marker,hooks)
