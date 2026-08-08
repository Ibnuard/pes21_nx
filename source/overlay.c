/* overlay.c -- small FPS counter drawn over the game's output
 *
 * Rendered from the eglSwapBuffers hook when config.show_fps is set, using a
 * bitmap-font atlas and its own tiny GL program. Saves and restores every piece
 * of GL state it touches so the engine's rendering is unaffected.
 *
 * This software may be modified and distributed under the terms
 * of the MIT license. See the LICENSE file for details.
 */

#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <switch.h>

#include <EGL/egl.h>
#include <GLES2/gl2.h>

#include "config.h"
#include "overlay.h"
#include "font_atlas.h"

// text-overlay GL objects, created lazily on first draw
static struct {
  int ready;
  GLuint prog;
  GLuint tex;
  GLuint vbo;
  GLint loc_pos, loc_uv, loc_tex, loc_off, loc_color;
  int uploaded;
} gl;

static const char vshader_src[] =
  "attribute vec2 aPos;\n"
  "attribute vec2 aUV;\n"
  "uniform vec2 uOff;\n"
  "varying vec2 vUV;\n"
  "void main() {\n"
  "  vUV = aUV;\n"
  "  gl_Position = vec4(aPos + uOff, 0.0, 1.0);\n"
  "}\n";

static const char fshader_src[] =
  "precision mediump float;\n"
  "uniform sampler2D texFont;\n"
  "uniform vec4 uColor;\n"
  "varying vec2 vUV;\n"
  "void main() {\n"
  "  gl_FragColor = vec4(uColor.rgb, uColor.a * texture2D(texFont, vUV).r);\n"
  "}\n";

static GLuint compile_shader(GLenum type, const char *src) {
  GLuint s = glCreateShader(type);
  glShaderSource(s, 1, &src, NULL);
  glCompileShader(s);
  return s;
}

static int gl_init(void) {
  if (gl.ready)
    return gl.prog != 0;
  gl.ready = 1;

  const GLuint vs = compile_shader(GL_VERTEX_SHADER, vshader_src);
  const GLuint fs = compile_shader(GL_FRAGMENT_SHADER, fshader_src);
  gl.prog = glCreateProgram();
  glAttachShader(gl.prog, vs);
  glAttachShader(gl.prog, fs);
  glLinkProgram(gl.prog);
  glDeleteShader(vs);
  glDeleteShader(fs);
  GLint ok = 0;
  glGetProgramiv(gl.prog, GL_LINK_STATUS, &ok);
  if (!ok) {
    glDeleteProgram(gl.prog);
    gl.prog = 0;
    return 0;
  }
  gl.loc_pos = glGetAttribLocation(gl.prog, "aPos");
  gl.loc_uv = glGetAttribLocation(gl.prog, "aUV");
  gl.loc_tex = glGetUniformLocation(gl.prog, "texFont");
  gl.loc_off = glGetUniformLocation(gl.prog, "uOff");
  gl.loc_color = glGetUniformLocation(gl.prog, "uColor");
  glGenTextures(1, &gl.tex);
  glGenBuffers(1, &gl.vbo);
  return 1;
}

// uploads the glyph atlas on first use; binds texture unit 0 in the process,
// so only call this inside a texture-state save/restore region
static void atlas_ready(void) {
  if (gl.uploaded)
    return;
  GLint prev_align = 4;
  glGetIntegerv(GL_UNPACK_ALIGNMENT, &prev_align);
  glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
  glActiveTexture(GL_TEXTURE0);
  glBindTexture(GL_TEXTURE_2D, gl.tex);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
  glTexImage2D(GL_TEXTURE_2D, 0, GL_LUMINANCE, FONT_ATLAS_W, FONT_ATLAS_H, 0,
               GL_LUMINANCE, GL_UNSIGNED_BYTE, font_atlas);
  glPixelStorei(GL_UNPACK_ALIGNMENT, prev_align);
  gl.uploaded = 1;
}

// two triangles per glyph into verts (x,y,u,v interleaved); spaces advance
// the pen without emitting geometry
static int emit_line(const char *text, int len, float x, float y,
                     float gw, float gh, GLfloat *verts) {
  int quads = 0;
  for (int j = 0; j < len; j++) {
    const char c = text[j];
    if (c == ' ')
      continue;
    if (c < FONT_FIRST || c >= FONT_FIRST + FONT_COUNT)
      continue;
    const int idx = c - FONT_FIRST;
    const float u0 = (float)((idx % FONT_COLS) * FONT_CELL_W) / (float)FONT_ATLAS_W;
    const float v0 = (float)((idx / FONT_COLS) * FONT_CELL_H) / (float)FONT_ATLAS_H;
    const float u1 = u0 + (float)FONT_CELL_W / (float)FONT_ATLAS_W;
    const float v1 = v0 + (float)FONT_CELL_H / (float)FONT_ATLAS_H;
    const float gx = x + j * gw;
    const float x0 = gx * 2.0f / (float)screen_width - 1.0f;
    const float x1 = (gx + gw) * 2.0f / (float)screen_width - 1.0f;
    const float y0 = 1.0f - y * 2.0f / (float)screen_height;
    const float y1 = 1.0f - (y + gh) * 2.0f / (float)screen_height;
    const GLfloat quad[24] = {
      x0, y0, u0, v0,  x1, y0, u1, v0,  x0, y1, u0, v1,
      x1, y0, u1, v0,  x1, y1, u1, v1,  x0, y1, u0, v1,
    };
    memcpy(verts + quads * 24, quad, sizeof(quad));
    quads++;
  }
  return quads;
}

// FPS counter (config.show_fps): draws the rate top-left, refreshed twice a
// second. Saves and restores all the GL state it touches.
static struct {
  u64 window_start;
  u32 frames;
  char text[8];
} fps;

static void fps_render(void) {
  const u64 now = armGetSystemTick();
  const u64 freq = armGetSystemTickFreq();
  fps.frames++;
  if (!fps.window_start)
    fps.window_start = now;
  if (now - fps.window_start >= freq / 2) {
    const float rate = (float)fps.frames * (float)freq / (float)(now - fps.window_start);
    snprintf(fps.text, sizeof(fps.text), "%.0f", rate);
    fps.frames = 0;
    fps.window_start = now;
  }

  if (!fps.text[0] || !gl_init())
    return;

  const float gh = (float)screen_height / 30.0f;
  const float gw = gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
  static GLfloat verts[8 * 24];
  const int quads = emit_line(fps.text, (int)strlen(fps.text), 10.0f, 8.0f, gw, gh, verts);
  if (!quads)
    return;

  GLint prev_fb, prev_prog, prev_active, prev_tex0, prev_array_buf, prev_viewport[4];
  GLint bsrc_rgb, bdst_rgb, bsrc_a, bdst_a, beq_rgb, beq_a;
  GLboolean color_mask[4];
  const GLboolean prev_blend = glIsEnabled(GL_BLEND);
  const GLboolean prev_depth = glIsEnabled(GL_DEPTH_TEST);
  const GLboolean prev_stencil = glIsEnabled(GL_STENCIL_TEST);
  const GLboolean prev_scissor = glIsEnabled(GL_SCISSOR_TEST);
  const GLboolean prev_cull = glIsEnabled(GL_CULL_FACE);
  glGetIntegerv(GL_FRAMEBUFFER_BINDING, &prev_fb);
  glGetIntegerv(GL_CURRENT_PROGRAM, &prev_prog);
  glGetIntegerv(GL_ACTIVE_TEXTURE, &prev_active);
  glGetIntegerv(GL_ARRAY_BUFFER_BINDING, &prev_array_buf);
  glGetIntegerv(GL_VIEWPORT, prev_viewport);
  glGetIntegerv(GL_BLEND_SRC_RGB, &bsrc_rgb);
  glGetIntegerv(GL_BLEND_DST_RGB, &bdst_rgb);
  glGetIntegerv(GL_BLEND_SRC_ALPHA, &bsrc_a);
  glGetIntegerv(GL_BLEND_DST_ALPHA, &bdst_a);
  glGetIntegerv(GL_BLEND_EQUATION_RGB, &beq_rgb);
  glGetIntegerv(GL_BLEND_EQUATION_ALPHA, &beq_a);
  glGetBooleanv(GL_COLOR_WRITEMASK, color_mask);
  glActiveTexture(GL_TEXTURE0);
  glGetIntegerv(GL_TEXTURE_BINDING_2D, &prev_tex0);
  GLint prev_va_pos = 0, prev_va_uv = 0;
  glGetVertexAttribiv(gl.loc_pos, GL_VERTEX_ATTRIB_ARRAY_ENABLED, &prev_va_pos);
  glGetVertexAttribiv(gl.loc_uv, GL_VERTEX_ATTRIB_ARRAY_ENABLED, &prev_va_uv);

  atlas_ready();
  glBindFramebuffer(GL_FRAMEBUFFER, 0);
  glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);
  glDisable(GL_DEPTH_TEST);
  glDisable(GL_STENCIL_TEST);
  glDisable(GL_SCISSOR_TEST);
  glDisable(GL_CULL_FACE);
  glEnable(GL_BLEND);
  glBlendEquation(GL_FUNC_ADD);
  glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
  // upload into our own VBO: the engine only ever draws from buffer objects,
  // so mesa/nouveau's client-array streaming path is untested here and wedges
  // the GPU channel. Matching the engine's pattern avoids it.
  glBindBuffer(GL_ARRAY_BUFFER, gl.vbo);
  glBufferData(GL_ARRAY_BUFFER, (GLsizeiptr)quads * 24 * sizeof(GLfloat), verts, GL_DYNAMIC_DRAW);
  glViewport(0, 0, screen_width, screen_height);
  glUseProgram(gl.prog);
  glBindTexture(GL_TEXTURE_2D, gl.tex);
  glUniform1i(gl.loc_tex, 0);
  glEnableVertexAttribArray(gl.loc_pos);
  glEnableVertexAttribArray(gl.loc_uv);
  glVertexAttribPointer(gl.loc_pos, 2, GL_FLOAT, GL_FALSE, 16, (const void *)0);
  glVertexAttribPointer(gl.loc_uv, 2, GL_FLOAT, GL_FALSE, 16, (const void *)8);

  // drop shadow first, then the text itself
  glUniform2f(gl.loc_off, 3.0f / (float)screen_width, -3.0f / (float)screen_height);
  glUniform4f(gl.loc_color, 0.0f, 0.0f, 0.0f, 0.9f);
  glDrawArrays(GL_TRIANGLES, 0, quads * 6);
  glUniform2f(gl.loc_off, 0.0f, 0.0f);
  glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, 1.0f);
  glDrawArrays(GL_TRIANGLES, 0, quads * 6);

  // restore the two attrib arrays to whatever the engine had (it uses the same
  // low indices); leaving them forced-off would break its next draw
  if (!prev_va_pos) glDisableVertexAttribArray(gl.loc_pos);
  if (!prev_va_uv) glDisableVertexAttribArray(gl.loc_uv);

  glBindFramebuffer(GL_FRAMEBUFFER, prev_fb);
  glColorMask(color_mask[0], color_mask[1], color_mask[2], color_mask[3]);
  glBlendEquationSeparate(beq_rgb, beq_a);
  glBlendFuncSeparate(bsrc_rgb, bdst_rgb, bsrc_a, bdst_a);
  if (!prev_blend) glDisable(GL_BLEND);
  if (prev_depth) glEnable(GL_DEPTH_TEST);
  if (prev_stencil) glEnable(GL_STENCIL_TEST);
  if (prev_scissor) glEnable(GL_SCISSOR_TEST);
  if (prev_cull) glEnable(GL_CULL_FACE);
  glBindTexture(GL_TEXTURE_2D, prev_tex0);
  glActiveTexture(prev_active);
  glUseProgram(prev_prog);
  glBindBuffer(GL_ARRAY_BUFFER, prev_array_buf);
  glViewport(prev_viewport[0], prev_viewport[1], prev_viewport[2], prev_viewport[3]);
}

unsigned int eglSwapBuffersHook(void *display, void *surface) {
  if (config.show_fps)
    fps_render();
  return eglSwapBuffers((EGLDisplay)display, (EGLSurface)surface);
}
