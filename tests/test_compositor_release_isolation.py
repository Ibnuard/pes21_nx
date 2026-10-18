"""Replay the real compositor boundary; release must not sample/drain GL."""
from pathlib import Path
import shutil

import pytest

from test_result_flow import build_and_run, function

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('defines', ['', '#define NEAR_CAMERA_TRACE 1\n'])
def test_composition_preserves_errors_and_avoids_pixel_readback(defines):
    cc = shutil.which('gcc')
    if not cc:
        pytest.skip('gcc required for compositor replay')
    source = (ROOT / 'source/imports.c').read_text()
    end = source.index('} GLComposeExperiment;') + len('} GLComposeExperiment;')
    begin = source.rindex('typedef struct {', 0, end)
    build_and_run(cc, defines + r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef unsigned GLuint, GLenum;
typedef int GLint, GLsizei;
#define GL_TEXTURE0 100
#define GL_TEXTURE_2D 101
#define GL_TRIANGLES 102
#define GL_NO_ERROR 0
#define GL_IMPLEMENTATION_COLOR_READ_FORMAT 103
#define GL_IMPLEMENTATION_COLOR_READ_TYPE 104
#define GL_READ_FRAMEBUFFER_BINDING 105
#define GL_DRAW_FRAMEBUFFER_BINDING 106
#define GL_READ_FRAMEBUFFER 107
#define GL_DRAW_FRAMEBUFFER 108
#define GL_COLOR_BUFFER_BIT 109
#define GL_NEAREST 110
static struct {
    GLuint framebuffer, scene_texture, scene_framebuffer, texture2d[8], sampler[8];
    unsigned scene_compose_pending, scene_compose_count, active_texture;
    GLint viewport[4];
    struct { GLuint texture, framebuffer; GLint width,height; } completed_scene[8];
} g_mc[1];
static int mc_current_slot(void) { return 0; }
static unsigned active=GL_TEXTURE0+2, textures[8]={11,22}, samplers[8]={31,32};
static unsigned read_fbo=67, draw_fbo, reads, errors, gets, draws, blits;
static unsigned pending_error=0x502, fallback_ok=1;
static void bind_sampler(GLuint unit,GLuint sampler) { samplers[unit]=sampler; }
static void (*eglGetProcAddress(const char *name))(GLuint,GLuint) {
    assert(!strcmp(name,"glBindSampler")); return bind_sampler;
}
static void glActiveTexture(GLenum unit) { active=unit; }
static void glBindTexture(GLenum target,GLuint texture) {
    assert(target==GL_TEXTURE_2D); textures[active-GL_TEXTURE0]=texture;
}
static int gl_diag_draw_fallback(GLenum mode,unsigned curve) {
    assert(mode==GL_TRIANGLES && curve==2);
    assert(textures[0]==22 && samplers[0]==32); ++draws; return fallback_ok;
}
static GLenum glGetError(void) { ++errors; unsigned r=pending_error;pending_error=0;return r; }
static void glGetIntegerv(GLenum param,GLint *out) {
    ++gets; *out=param==GL_READ_FRAMEBUFFER_BINDING?read_fbo:
                  param==GL_DRAW_FRAMEBUFFER_BINDING?draw_fbo:0;
}
static void glBindFramebuffer(GLenum target,GLuint fbo) {
    if(target==GL_READ_FRAMEBUFFER) read_fbo=fbo;
    else { assert(target==GL_DRAW_FRAMEBUFFER); draw_fbo=fbo; }
}
static void blit(int a,int b,int c,int d,int e,int f,int g,int h,unsigned mask,unsigned filter) {
    assert(read_fbo==44 && draw_fbo==0 && b==576 && d==0 && h==576);
    assert(mask==GL_COLOR_BUFFER_BIT && filter==GL_NEAREST); ++blits;
}
static void (*gl_blit_framebuffer_real)(int,int,int,int,int,int,int,int,unsigned,unsigned)=blit;
static void gl_diag_sample_rgb(const GLint *v,GLint f,GLint t,unsigned *a,unsigned *b,
    unsigned long long *c,unsigned *d,unsigned *e,unsigned long long *g) { ++reads; }
static const char *gl_diag_compose_mode_name(unsigned mode) { return "test"; }
static void debugPrintf(const char *fmt,...) {}
''' + source[begin:end] + '\n'
        + function(source, 'gl_diag_prepare_compose_experiment')
        + function(source, 'gl_diag_finish_compose_experiment') + r'''
int main(void) {
    g_mc[0].texture2d[0]=11; g_mc[0].texture2d[1]=22;
    g_mc[0].sampler[0]=31; g_mc[0].sampler[1]=32;
    g_mc[0].active_texture=2; g_mc[0].viewport[2]=1024;g_mc[0].viewport[3]=576;
    for(unsigned frame=0;frame<240;++frame) {
        g_mc[0].completed_scene[0].texture=22;
        g_mc[0].completed_scene[0].framebuffer=44;
        g_mc[0].completed_scene[0].width=1024;
        g_mc[0].completed_scene[0].height=576;
        GLComposeExperiment e=gl_diag_prepare_compose_experiment(3);
        assert(e.matched && e.source_framebuffer==44 && e.texture==22);
        gl_diag_finish_compose_experiment(&e);
        assert(reads==0 && errors==0 && gets==0);
        assert(pending_error==0x502); // native errors belong to the caller
        assert(textures[0]==11 && samplers[0]==31 && active==GL_TEXTURE0+2);
        assert(read_fbo==67 && draw_fbo==0);
        assert(!g_mc[0].scene_compose_pending);
    }
    assert(draws==240 && blits==0);
    // If shader composition fails, the accepted flipped blit still works.
    fallback_ok=0;g_mc[0].scene_compose_pending=1;
    GLComposeExperiment e={0};e.matched=1;e.texture=22;e.sampler=32;
    e.source_framebuffer=44;e.viewport[2]=1024;e.viewport[3]=576;e.log_result=1;
    gl_diag_finish_compose_experiment(&e);
    assert(blits==1 && read_fbo==67 && draw_fbo==0);
    assert(reads==0 && errors==0 && gets==2 && pending_error==0x502);
    assert(textures[0]==11 && samplers[0]==31 && active==GL_TEXTURE0+2);
}
''')
