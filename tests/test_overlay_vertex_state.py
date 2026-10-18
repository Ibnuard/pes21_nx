"""Replay engine VAO reuse after HUD draws without resetting its pointers."""
from pathlib import Path
import shutil

import pytest
from test_gameplan_editor import function
from test_result_flow import build_and_run

ROOT = Path(__file__).resolve().parents[1]


def test_overlay_preserves_complete_engine_layout_and_context_lifetime():
    cc = shutil.which('gcc')
    if not cc:
        pytest.skip('host C compiler required')
    include = (ROOT/'source/overlay_vertex_state.inc').as_posix()
    build_and_run(cc, r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef unsigned GLuint, GLenum;
typedef int GLint, GLsizei, Mutex;
typedef unsigned char GLboolean;
typedef void *EGLContext;
#define EGL_NO_CONTEXT ((void *)0)
#define GL_ARRAY_BUFFER 0x8892
#define GL_ARRAY_BUFFER_BINDING 0x8894
#define GL_FLOAT 0x1406
#define GL_FALSE 0
typedef struct {unsigned buffer, size, type, stride, enabled, divisor, integer;
                uintptr_t pointer;} Attribute;
typedef struct {Attribute attribute[8];unsigned element;} Vao;
static Vao vaos[4][128];
static unsigned current=1, bound[4]={0,7,7,7}, array_buffer[4]={0,93,93,93};
static unsigned next[4]={0,20,20,20}, created, mutations, locks, mode, fail_gen;
static void mutexLock(Mutex *m) {(void)m;assert(!locks);locks=1;}
static void mutexUnlock(Mutex *m) {(void)m;assert(locks);locks=0;}
static EGLContext eglGetCurrentContext(void) {return (void *)(uintptr_t)current;}
static void gen(GLsizei n,GLuint *v) {
 assert(n==1);*v=fail_gen?0:next[current]++;if(*v)created++;
}
static void bind(GLuint v) {bound[current]=v;}
static void *eglGetProcAddress(const char *name) {
 if(mode==2 || (mode==1 && !strstr(name,"OES")))return 0;
 return strstr(name,"glGen")?(void *)gen:(void *)bind;
}
static void glGetIntegerv(GLenum p,GLint *v) {
 if(p==0x85b5)*v=bound[current];
 else {assert(p==GL_ARRAY_BUFFER_BINDING);*v=array_buffer[current];}
}
static void glBindBuffer(GLenum p,GLuint v) {assert(p==GL_ARRAY_BUFFER);array_buffer[current]=v;}
static void glEnableVertexAttribArray(GLuint i) {vaos[current][bound[current]].attribute[i].enabled=1;mutations++;}
static void glVertexAttribPointer(GLuint i,GLint size,GLenum type,GLboolean normalized,
                                  GLsizei stride,const void *pointer) {
 (void)normalized;Attribute *a=&vaos[current][bound[current]].attribute[i];
 a->buffer=array_buffer[current];a->size=size;a->type=type;a->stride=stride;
 a->pointer=(uintptr_t)pointer;a->integer=0;mutations++;
}
''' + '\n#include "' + include + '"\n' + r'''
int main(void) {
 Vao original={0};
 for(unsigned i=0;i<8;i++)original.attribute[i]=(Attribute){50+i,4,0x1404,40,1,i%2,1,128+i*4};
 original.element=99;
 vaos[1][7]=original;vaos[2][7]=original;
 GLint saved;
 /* The engine retains its input-layout cache across HUD draws. Its next
    player/ball/stadium draw does NOT resubmit pointers or the index buffer. */
 for(unsigned frame=0;frame<1000;frame++) {
  assert(overlay_vertex_begin(88,0,1,&saved) && saved==7);
  assert(bound[1]!=7 && array_buffer[1]==93);
  Vao *hud=&vaos[1][bound[1]];
  assert(hud->attribute[0].buffer==88 && hud->attribute[0].size==2);
  assert(!hud->attribute[0].integer && !hud->attribute[0].divisor);
  assert(hud->attribute[1].pointer==8 && !hud->attribute[2].enabled);
  assert(hud->element==0);
  overlay_vertex_end(saved);
  assert(bound[1]==7 && !memcmp(&original,&vaos[1][7],sizeof(original)));
 }
 assert(created==1 && mutations==4); /* Attribute setup occurs once. */
 current=2;assert(overlay_vertex_begin(88,0,1,&saved));overlay_vertex_end(saved);
 assert(created==2 && !memcmp(&original,&vaos[2][7],sizeof(original)));
 current=1;assert(overlay_vertex_begin(88,0,1,&saved));overlay_vertex_end(saved);assert(created==2);
 /* Destroy from a different thread/context, then reuse the EGL handle. */
 current=2;overlay_context_destroyed((void *)1);
 current=1;assert(overlay_vertex_begin(88,0,1,&saved));overlay_vertex_end(saved);assert(created==3);
 current=0;assert(!overlay_vertex_begin(88,0,1,&saved));assert(!locks);
 current=3;fail_gen=1;assert(!overlay_vertex_begin(88,0,1,&saved));assert(bound[3]==7 && !locks);
 fail_gen=0;overlay_gen_vertex_arrays=0;overlay_bind_vertex_array=0;mode=1;
 assert(overlay_vertex_begin(88,0,1,&saved));overlay_vertex_end(saved);assert(created==4);
 overlay_gen_vertex_arrays=0;overlay_bind_vertex_array=0;mode=2;
 assert(!overlay_vertex_begin(88,0,1,&saved) && bound[3]==7 && !locks);
}
''')


def test_all_overlay_draws_use_private_layout_and_separate_framebuffer_targets():
    source = (ROOT/'source/overlay.c').read_text()
    draw = function(source, 'overlay_render')
    assert draw.index('overlay_vertex_begin(') < draw.index('glBufferData(')
    assert draw.index('overlay_restore:') < draw.index('overlay_vertex_end(')
    assert 'glVertexAttribPointer(' not in draw and 'prev_va_pos' not in draw
    assert 'glBindFramebuffer(GL_FRAMEBUFFER,' not in source
    assert 'glBindFramebuffer(GL_DRAW_FRAMEBUFFER, prev_fb)' in draw
    assert 'glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING, &saved_framebuffer)' in source
    imports = (ROOT/'source/imports.c').read_text()
    swap = function(imports, 'eglSwapBuffers_cache')
    assert swap.index('gl_state_cache_reset();') < swap.index('eglSwapBuffersHook(')
    assert swap.rindex('gl_state_cache_reset();') > swap.index('eglSwapBuffersHook(')
    destroy = function(imports, 'eglDestroyContext_cache')
    assert 'if (result) {' in destroy and 'overlay_context_destroyed(ctx)' in destroy
