"""Actual context-local state wrappers: repeated material state and restores."""
from pathlib import Path
import shutil

import pytest
from test_gameplan_editor import function
from test_result_flow import build_and_run

ROOT=Path(__file__).resolve().parents[1]


def test_separate_factors_keep_alpha_restore_validation_bypass_and_reset():
    cc=shutil.which('gcc')
    if not cc:pytest.skip('host gcc required')
    source=(ROOT/'source/imports.c').read_text()
    start=source.index('#define GLC_MAXCAPS')
    declarations=source[start:source.index('// Invalidate the cache.',start)]
    helpers=''.join(function(source,name) for name in (
        'gl_state_cache_reset','glBlendFunc_c','gl_blend_factor_cacheable','glBlendFuncSeparate_c'))
    build_and_run(cc,r'''
#include <assert.h>
#include <string.h>
typedef unsigned GLenum,GLuint;
typedef unsigned char GLboolean;
#define GL_ZERO 0u
#define GL_ONE 1u
#define GL_SRC_COLOR 0x300u
#define GL_ONE_MINUS_DST_COLOR 0x307u
#define GL_SRC_ALPHA_SATURATE 0x308u
static int glc_enabled=1;
static unsigned requests, skipped, native_calls, errors;
#define NX_NEAR_BLEND(s) do {++requests;skipped+=!!(s);} while(0)
static unsigned actual[4];
static void glBlendFunc(GLenum s,GLenum d) {
  ++native_calls;actual[0]=actual[2]=s;actual[1]=actual[3]=d;
}
static void glBlendFuncSeparate(GLenum sc,GLenum dc,GLenum sa,GLenum da) {
  ++native_calls;
  if(dc==GL_SRC_ALPHA_SATURATE || sc==999) {++errors;return;}
  actual[0]=sc;actual[1]=dc;actual[2]=sa;actual[3]=da;
}
''' + declarations + helpers + r'''
int main(void) {
  glBlendFuncSeparate_c(0x302,0x303,1,0);assert(native_calls==1);
  for(unsigned i=0;i<10000;i++)glBlendFuncSeparate_c(0x302,0x303,1,0);
  assert(native_calls==1 && requests==10001 && skipped==10000);
  glBlendFuncSeparate_c(0x302,0x303,0,1);assert(native_calls==2);
  assert(actual[2]==0 && actual[3]==1); /* RGB equality cannot hide alpha change. */
  glBlendFunc_c(1,0);assert(native_calls==3 && actual[0]==1);
  glBlendFuncSeparate_c(0x302,0x303,0,1);assert(native_calls==4 && actual[0]==0x302);
  glBlendFunc_c(1,0);assert(native_calls==5 && actual[0]==1);
  glBlendFuncSeparate_c(0,GL_SRC_ALPHA_SATURATE,1,0);
  glBlendFuncSeparate_c(0,GL_SRC_ALPHA_SATURATE,1,0);
  assert(native_calls==7 && errors==2); /* Invalid calls always reach native validation. */
  glBlendFuncSeparate_c(999,0,1,0);glBlendFuncSeparate_c(999,0,1,0);
  assert(errors==4);
  /* Unknown/extension and constant colour/alpha factors remain pass-through. */
  unsigned before=native_calls;
  glBlendFuncSeparate_c(0x8001,0x8003,1,0);glBlendFuncSeparate_c(0x8001,0x8003,1,0);
  assert(native_calls==before+2);
  glBlendFuncSeparate_c(GL_SRC_ALPHA_SATURATE,0,1,0);
  before=native_calls;glBlendFuncSeparate_c(GL_SRC_ALPHA_SATURATE,0,1,0);
  assert(native_calls==before); /* Saturate is cacheable only for source RGB. */
  glc_enabled=0;
  for(unsigned i=0;i<20;i++)glBlendFuncSeparate_c(1,0,1,0);
  assert(native_calls==before+20);
  glc_enabled=1;gl_state_cache_reset();
  glBlendFuncSeparate_c(1,0,1,0);assert(native_calls==before+21);
  gl_state_cache_reset(); /* Context switch or wrapper overlay modified GL. */
  actual[0]=99;glBlendFuncSeparate_c(1,0,1,0);
  assert(native_calls==before+22 && actual[0]==1);
}
''')


def test_all_imported_and_resolved_mutators_share_the_same_context_cache():
    source=(ROOT/'source/imports.c').read_text()
    resolver=function(source,'gl_cached_state_proc')
    for api in ('glBlendFunc','glBlendFuncSeparate'):
        assert f'CACHED_GL({api}, {api}_c)' in resolver
        assert f'{{ "{api}", (uintptr_t)&{api}_c }}' in source
    for boundary in ('eglMakeCurrent_dedup','eglSwapBuffers_cache'):
        assert 'gl_state_cache_reset();' in function(source,boundary)
