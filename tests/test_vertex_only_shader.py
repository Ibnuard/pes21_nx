"""Host exercise of the guarded depth-only compatibility retry."""
from pathlib import Path
import shutil
import unittest
from test_result_flow import build_and_run, function


class VertexOnlyShaderTests(unittest.TestCase):
    def test_only_missing_fragment_programs_are_retried(self):
        compiler = shutil.which('gcc')
        if not compiler:
            self.skipTest('gcc unavailable')
        source = (Path(__file__).resolve().parents[1] / 'source/imports.c').read_text()
        build_and_run(compiler, r'''
#include <assert.h>
#include <string.h>
#include <stddef.h>
typedef unsigned GLuint;
typedef int GLint;
typedef int GLsizei;
#define GL_ATTACHED_SHADERS 1
#define GL_SHADER_TYPE 2
#define GL_COMPILE_STATUS 3
#define GL_VERTEX_SHADER 4
#define GL_FRAGMENT_SHADER 5
#define GL_LINK_STATUS 6
#define GL_TRUE 1
#define GL_FALSE 0
static int count=1, type=GL_VERTEX_SHADER, compiled=1, linked=1;
static int attaches, detaches, deletes, links;
static const char *version="#version 310 es\nvoid main() {}";
static void glGetProgramiv(GLuint p,int q,GLint *v) {*v=q==1?count:linked;}
static void glGetAttachedShaders(GLuint p,int n,GLsizei *f,GLuint *v) {*f=1;*v=10;}
static void glGetShaderiv(GLuint s,int q,GLint *v) {*v=q==2?type:compiled;}
static void glGetShaderSource(GLuint s,int n,void *l,char *p) {strcpy(p,version);}
static GLuint glCreateShader(int t) {assert(t==GL_FRAGMENT_SHADER);return 11;}
static void glShaderSource(GLuint s,int n,const char **p,void *l) {
  assert(strstr(*p,"#version 310 es"));
  assert(!strstr(*p,"gl_FragColor"));
}
static void glCompileShader(GLuint s) {}
static void glDeleteShader(GLuint s) {deletes++;}
static void glAttachShader(GLuint p,GLuint s) {attaches++;}
static void glDetachShader(GLuint p,GLuint s) {detaches++;}
static void glLinkProgram(GLuint p) {links++;}
static void debugPrintf(const char *p,...) {}
''' + function(source, 'gl_complete_vertex_only_program') + r'''
int main(void) {
  const char *error="error: program lacks a fragment shader";
  assert(!gl_complete_vertex_only_program(1,"varying mismatch"));
  count=2; assert(!gl_complete_vertex_only_program(1,error)); count=1;
  type=GL_FRAGMENT_SHADER; assert(!gl_complete_vertex_only_program(1,error));
  type=GL_VERTEX_SHADER; compiled=0;
  assert(!gl_complete_vertex_only_program(1,error)); compiled=1;
  version="#version 450"; assert(!gl_complete_vertex_only_program(1,error));
  version="#version 310 es";
  assert(attaches==0 && links==0);
  assert(gl_complete_vertex_only_program(1,error));
  assert(attaches==1 && detaches==1 && deletes==1 && links==1);
  linked=0; assert(!gl_complete_vertex_only_program(1,error));
  assert(attaches==2 && detaches==2 && deletes==2 && links==3);
}
''')
