from pathlib import Path
import shutil
import unittest
from test_result_flow import build_and_run

ROOT=Path(__file__).resolve().parents[1]


class RenderControlTests(unittest.TestCase):
    def test_boot_token_is_exact_and_unrelated_files_keep_cache_enabled(self):
        cc=shutil.which('gcc')
        if not cc:self.skipTest('host gcc unavailable')
        build_and_run(cc,'#include <assert.h>\n#include "'+
                      (ROOT/'source/gl_render_probe_policy.h').as_posix()+'"\n'+r'''
int main(void) {
 const char *valid[]={"PESNX_GL_CACHE_BYPASS_V1","PESNX_GL_CACHE_BYPASS_V1\n","PESNX_GL_CACHE_BYPASS_V1\r\n"};
 const char *bad[]={"","off","PESNX_GL_CACHE_BYPASS_V2","PESNX_GL_CACHE_BYPASS_V1\nextra",
                    " PESNX_GL_CACHE_BYPASS_V1","PESNX_GL_CACHE_BYPASS_V1\0extra"};
 for(unsigned i=0;i<3;i++)assert(nx_gl_cache_bypass_line(valid[i],strlen(valid[i])));
 for(unsigned i=0;i<5;i++)assert(!nx_gl_cache_bypass_line(bad[i],strlen(bad[i])));
 assert(!nx_gl_cache_bypass_line(bad[5],28));
 assert(!nx_gl_cache_bypass_line(NULL,0));
 const char *native[]={"PESNX_NATIVE_PLAYER_CLASS_V1","PESNX_NATIVE_PLAYER_CLASS_V1\n","PESNX_NATIVE_PLAYER_CLASS_V1\r\n"};
 for(unsigned i=0;i<3;i++) {
   assert(nx_gl_native_player_class_line(native[i],strlen(native[i])));
   assert(!nx_gl_cache_bypass_line(native[i],strlen(native[i])));
   assert(!nx_gl_native_player_class_line(valid[i],strlen(valid[i])));
 }
 assert(!nx_gl_native_player_class_line(NULL,0));
 assert(!nx_gl_native_player_class_line("PESNX_NATIVE_PLAYER_CLASS_V1\nextra",32));
 assert(!nx_gl_native_player_class_line("PESNX_NATIVE_PLAYER_CLASS_V2",26));
}
''')
