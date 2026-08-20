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
#include <math.h>
#include <string.h>
#include <switch.h>

#include <EGL/egl.h>
#include <GLES2/gl2.h>

#include "config.h"
#include "overlay.h"
#include "badge_atlas.h"
#include "font_atlas.h"
#include "ue4_hooks.h"

// text-overlay GL objects, created lazily on first draw
static struct {
  int ready;
  GLuint prog;
  GLuint tex;
  GLuint badge_tex;
  GLuint vbo;
  GLint loc_pos, loc_uv, loc_tex, loc_off, loc_color, loc_solid, loc_image;
  GLint loc_circle, loc_circle_feather;
  GLint loc_round_rect, loc_round_size, loc_round_radius, loc_round_feather;
  GLint loc_cursor, loc_cursor_border;
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
  "#ifdef GL_FRAGMENT_PRECISION_HIGH\n"
  "precision highp float;\n"
  "#else\n"
  "precision mediump float;\n"
  "#endif\n"
  "uniform sampler2D texFont;\n"
  "uniform vec4 uColor;\n"
  "uniform float uSolid;\n"
  "uniform float uImage;\n"
  "uniform float uCircle;\n"
  "uniform float uCircleFeather;\n"
  "uniform float uRoundRect;\n"
  "uniform vec2 uRoundSize;\n"
  "uniform float uRoundRadius;\n"
  "uniform float uRoundFeather;\n"
  "uniform float uCursor;\n"
  "uniform float uCursorBorder;\n"
  "varying vec2 vUV;\n"
  "float sdBox(vec2 p, vec2 halfSize) {\n"
  "  vec2 d = abs(p) - halfSize;\n"
  "  return length(max(d, vec2(0.0))) +\n"
  "         min(max(d.x, d.y), 0.0);\n"
  "}\n"
  "float cursorDistance(vec2 p) {\n"
  "  vec2 q = p - vec2(3.0);\n"
  "  float edge0 = -q.x;\n"
  "  float edge1 = (q.x - q.y) * 0.70710678;\n"
  "  float edge2 =\n"
  "      (q.y - (30.0 - q.x * 0.36363636)) * 0.93979342;\n"
  "  float head = max(max(edge0, edge1), edge2);\n"
  "  vec2 direction = vec2(0.44721360, 0.89442719);\n"
  "  vec2 normal = vec2(-direction.y, direction.x);\n"
  "  vec2 stemPoint = q - vec2(15.0, 31.0);\n"
  "  vec2 stemLocal = vec2(dot(stemPoint, normal),\n"
  "                        dot(stemPoint, direction));\n"
  "  float stem = sdBox(stemLocal, vec2(3.6, 11.18034));\n"
  "  return min(head, stem);\n"
  "}\n"
  "void main() {\n"
  "  vec4 sampled = texture2D(texFont, vUV);\n"
  "  if (uCursor > 0.5) {\n"
  "    float sd = cursorDistance(vUV * vec2(36.0, 48.0));\n"
  "    float a = 1.0 - smoothstep(uCursorBorder - 0.85,\n"
  "                               uCursorBorder + 0.85, sd);\n"
  "    gl_FragColor = vec4(uColor.rgb, uColor.a * a);\n"
  "  } else if (uRoundRect > 0.5) {\n"
  "    vec2 halfSize = uRoundSize * 0.5;\n"
  "    float radius = min(uRoundRadius, min(halfSize.x, halfSize.y));\n"
  "    vec2 p = (vUV - vec2(0.5)) * uRoundSize;\n"
  "    vec2 q = abs(p) - halfSize + vec2(radius);\n"
  "    float sd = length(max(q, vec2(0.0))) +\n"
  "               min(max(q.x, q.y), 0.0) - radius;\n"
  "    float a = 1.0 - smoothstep(-uRoundFeather, uRoundFeather, sd);\n"
  "    gl_FragColor = vec4(uColor.rgb, uColor.a * a);\n"
  "  } else if (uCircle > 0.5) {\n"
  "    float d = length(vUV - vec2(0.5));\n"
  "    float a = 1.0 - smoothstep(0.5 - uCircleFeather, 0.5, d);\n"
  "    gl_FragColor = vec4(uColor.rgb, uColor.a * a);\n"
  "  } else if (uSolid > 0.5)\n"
  "    gl_FragColor = uColor;\n"
  "  else if (uImage > 0.5)\n"
  "    gl_FragColor = vec4(sampled.rgb, sampled.a * uColor.a);\n"
  "  else\n"
  "    gl_FragColor = vec4(uColor.rgb, uColor.a * sampled.r);\n"
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
  gl.loc_solid = glGetUniformLocation(gl.prog, "uSolid");
  gl.loc_image = glGetUniformLocation(gl.prog, "uImage");
  gl.loc_circle = glGetUniformLocation(gl.prog, "uCircle");
  gl.loc_circle_feather =
      glGetUniformLocation(gl.prog, "uCircleFeather");
  gl.loc_round_rect = glGetUniformLocation(gl.prog, "uRoundRect");
  gl.loc_round_size = glGetUniformLocation(gl.prog, "uRoundSize");
  gl.loc_round_radius = glGetUniformLocation(gl.prog, "uRoundRadius");
  gl.loc_round_feather = glGetUniformLocation(gl.prog, "uRoundFeather");
  gl.loc_cursor = glGetUniformLocation(gl.prog, "uCursor");
  gl.loc_cursor_border = glGetUniformLocation(gl.prog, "uCursorBorder");
  glGenTextures(1, &gl.tex);
  glGenTextures(1, &gl.badge_tex);
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
  // Match the Townsmen overlay path: nouveau reliably samples this 8-bit
  // luminance atlas, while alpha from an RGBA upload becomes opaque here.
  glTexImage2D(GL_TEXTURE_2D, 0, GL_LUMINANCE, FONT_ATLAS_W,
               FONT_ATLAS_H, 0, GL_LUMINANCE, GL_UNSIGNED_BYTE,
               font_atlas_alpha);
  // Nouveau needs mipmap generation here to finalize the uploaded texture,
  // even though the direct overlay draw uses the base level with GL_LINEAR.
  glGenerateMipmap(GL_TEXTURE_2D);
  glBindTexture(GL_TEXTURE_2D, gl.badge_tex);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
  glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, BADGE_ATLAS_W, BADGE_ATLAS_H, 0,
               GL_RGBA, GL_UNSIGNED_BYTE, badge_atlas_rgba8);
  glGenerateMipmap(GL_TEXTURE_2D);
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
    const int idx = font_glyph_index(c);
    if (idx < 0)
      continue;
    const float u0 =
        ((float)((idx % FONT_COLS) * FONT_CELL_W) + 0.5f) /
        (float)FONT_ATLAS_W;
    const float v0 =
        ((float)((idx / FONT_COLS) * FONT_CELL_H) + 0.5f) /
        (float)FONT_ATLAS_H;
    const float u1 =
        ((float)(((idx % FONT_COLS) + 1) * FONT_CELL_W) - 0.5f) /
        (float)FONT_ATLAS_W;
    const float v1 =
        ((float)(((idx / FONT_COLS) + 1) * FONT_CELL_H) - 0.5f) /
        (float)FONT_ATLAS_H;
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

static int emit_rect(float x, float y, float width, float height,
                     GLfloat *verts);

static int emit_badge(uint32_t slot, float x, float y, float width,
                      float height, GLfloat *verts) {
  if (slot >= BADGE_ATLAS_SLOTS)
    slot = 0;
  const uint32_t col = slot % BADGE_ATLAS_COLS;
  const uint32_t row = slot / BADGE_ATLAS_COLS;
  const float u0 = ((float)(col * BADGE_CELL_SIZE) + 0.5f) /
                   (float)BADGE_ATLAS_W;
  const float v0 = ((float)(row * BADGE_CELL_SIZE) + 0.5f) /
                   (float)BADGE_ATLAS_H;
  const float u1 = ((float)((col + 1u) * BADGE_CELL_SIZE) - 0.5f) /
                   (float)BADGE_ATLAS_W;
  const float v1 = ((float)((row + 1u) * BADGE_CELL_SIZE) - 0.5f) /
                   (float)BADGE_ATLAS_H;
  const float x0 = x * 2.0f / (float)screen_width - 1.0f;
  const float x1 = (x + width) * 2.0f / (float)screen_width - 1.0f;
  const float y0 = 1.0f - y * 2.0f / (float)screen_height;
  const float y1 = 1.0f - (y + height) * 2.0f / (float)screen_height;
  const GLfloat quad[24] = {
      x0, y0, u0, v0, x1, y0, u1, v0, x0, y1, u0, v1,
      x1, y0, u1, v0, x1, y1, u1, v1, x0, y1, u0, v1,
  };
  memcpy(verts, quad, sizeof(quad));
  return 1;
}

// The launch prompt sits on top of a native ring. Render its A as solid
// geometry as well as atlas text; this keeps the glyph visible on GLES paths
// where the tiny LUMINANCE atlas can be sampled inconsistently.
static int emit_solid_a(float x, float y, float size, GLfloat *verts) {
  static const uint8_t rows[7] = {14, 17, 17, 31, 17, 17, 17};
  const float cell = size / 7.0f;
  int quads = 0;
  for (int row = 0; row < 7; row++) {
    for (int col = 0; col < 5; col++) {
      if (!(rows[row] & (1u << (4 - col))))
        continue;
      quads += emit_rect(x + (float)col * cell,
                         y + (float)row * cell, cell + 0.5f, cell + 0.5f,
                         verts + quads * 24);
    }
  }
  return quads;
}

static int emit_rect(float x, float y, float width, float height,
                     GLfloat *verts) {
  const float x0 = x * 2.0f / (float)screen_width - 1.0f;
  const float x1 = (x + width) * 2.0f / (float)screen_width - 1.0f;
  const float y0 = 1.0f - y * 2.0f / (float)screen_height;
  const float y1 = 1.0f - (y + height) * 2.0f / (float)screen_height;
  const GLfloat quad[24] = {
      x0, y0, 0.0f, 0.0f, x1, y0, 0.0f, 0.0f,
      x0, y1, 0.0f, 0.0f, x1, y0, 0.0f, 0.0f,
      x1, y1, 0.0f, 0.0f, x0, y1, 0.0f, 0.0f,
  };
  memcpy(verts, quad, sizeof(quad));
  return 1;
}

typedef struct {
  float width;
  float height;
  float radius;
} RoundedRectStyle;

static int emit_round_rect_quad(float x, float y, float width, float height,
                                GLfloat *verts) {
  const float x0 = x * 2.0f / (float)screen_width - 1.0f;
  const float x1 = (x + width) * 2.0f / (float)screen_width - 1.0f;
  const float y0 = 1.0f - y * 2.0f / (float)screen_height;
  const float y1 = 1.0f - (y + height) * 2.0f / (float)screen_height;
  const GLfloat quad[24] = {
      x0, y0, 0.0f, 0.0f, x1, y0, 1.0f, 0.0f,
      x0, y1, 0.0f, 1.0f, x1, y0, 1.0f, 0.0f,
      x1, y1, 1.0f, 1.0f, x0, y1, 0.0f, 1.0f,
  };
  memcpy(verts, quad, sizeof(quad));
  return 1;
}

static void use_rounded_rect(const RoundedRectStyle *style) {
  if (!style || style->width <= 0.0f || style->height <= 0.0f) {
    glUniform1f(gl.loc_round_rect, 0.0f);
    return;
  }
  glUniform1f(gl.loc_round_rect, 1.0f);
  glUniform2f(gl.loc_round_size, style->width, style->height);
  glUniform1f(gl.loc_round_radius, style->radius);
}

static int emit_triangle(float x0, float y0, float x1, float y1, float x2,
                         float y2, GLfloat *verts) {
  const GLfloat triangle[24] = {
      x0 * 2.0f / (float)screen_width - 1.0f,
      1.0f - y0 * 2.0f / (float)screen_height, 0.0f, 0.0f,
      x1 * 2.0f / (float)screen_width - 1.0f,
      1.0f - y1 * 2.0f / (float)screen_height, 0.0f, 0.0f,
      x2 * 2.0f / (float)screen_width - 1.0f,
      1.0f - y2 * 2.0f / (float)screen_height, 0.0f, 0.0f,
      x0 * 2.0f / (float)screen_width - 1.0f,
      1.0f - y0 * 2.0f / (float)screen_height, 0.0f, 0.0f,
      x2 * 2.0f / (float)screen_width - 1.0f,
      1.0f - y2 * 2.0f / (float)screen_height, 0.0f, 0.0f,
      x0 * 2.0f / (float)screen_width - 1.0f,
      1.0f - y0 * 2.0f / (float)screen_height, 0.0f, 0.0f,
  };
  memcpy(verts, triangle, sizeof(triangle));
  return 1;
}

static int emit_rounded_rect(float x, float y, float width, float height,
                             float radius, GLfloat *verts) {
  radius = fmaxf(0.0f, fminf(radius, fminf(width, height) * 0.5f));
  if (radius < 1.0f)
    return emit_rect(x, y, width, height, verts);

  int quads = 0;
  quads += emit_rect(x + radius, y, width - radius * 2.0f, height,
                     verts + quads * 24);
  quads += emit_rect(x, y + radius, radius, height - radius * 2.0f,
                     verts + quads * 24);
  quads += emit_rect(x + width - radius, y + radius, radius,
                     height - radius * 2.0f, verts + quads * 24);

  const float centers[4][2] = {
      {x + radius, y + radius},
      {x + width - radius, y + radius},
      {x + width - radius, y + height - radius},
      {x + radius, y + height - radius},
  };
  const float start_angles[4] = {3.14159265f, 4.71238898f, 0.0f,
                                 1.57079633f};
  for (int corner = 0; corner < 4; corner++) {
    for (int segment = 0; segment < 12; segment++) {
      const float a0 = start_angles[corner] +
                       (float)segment * 1.57079633f / 12.0f;
      const float a1 = start_angles[corner] +
                       (float)(segment + 1) * 1.57079633f / 12.0f;
      quads += emit_triangle(
          centers[corner][0], centers[corner][1],
          centers[corner][0] + cosf(a0) * radius,
          centers[corner][1] + sinf(a0) * radius,
          centers[corner][0] + cosf(a1) * radius,
          centers[corner][1] + sinf(a1) * radius, verts + quads * 24);
    }
  }
  return quads;
}

static int emit_circle_quad(float center_x, float center_y, float radius,
                            GLfloat *verts) {
  const float x0 = (center_x - radius) * 2.0f / (float)screen_width - 1.0f;
  const float x1 = (center_x + radius) * 2.0f / (float)screen_width - 1.0f;
  const float y0 = 1.0f - (center_y - radius) * 2.0f / (float)screen_height;
  const float y1 = 1.0f - (center_y + radius) * 2.0f / (float)screen_height;
  const GLfloat quad[24] = {
      x0, y0, 0.0f, 0.0f, x1, y0, 1.0f, 0.0f,
      x0, y1, 0.0f, 1.0f, x1, y0, 1.0f, 0.0f,
      x1, y1, 1.0f, 1.0f, x0, y1, 0.0f, 1.0f,
  };
  memcpy(verts, quad, sizeof(quad));
  return 1;
}

static int emit_outline(float x, float y, float width, float height,
                        float thickness, GLfloat *verts) {
  int quads = 0;
  // Match the stock card geometry: larger tiles have a visibly rounded edge,
  // while compact rows keep a restrained radius instead of a pill shape.
  const float radius = fminf(28.0f, fminf(width, height) * 0.18f);
  const float inner_radius = fmaxf(0.0f, radius - thickness);
  const float centers[4][2] = {
      {x + radius, y + radius},
      {x + width - radius, y + radius},
      {x + width - radius, y + height - radius},
      {x + radius, y + height - radius},
  };
  const float start_angles[4] = {3.14159265f, 4.71238898f, 0.0f,
                                 1.57079633f};
  for (int corner = 0; corner < 4; corner++) {
    for (int segment = 0; segment < 10; segment++) {
      const float a0 = start_angles[corner] +
                       (float)segment * 1.57079633f / 10.0f;
      const float a1 = start_angles[corner] +
                       (float)(segment + 1) * 1.57079633f / 10.0f;
      const float ox0 = centers[corner][0] + cosf(a0) * radius;
      const float oy0 = centers[corner][1] + sinf(a0) * radius;
      const float ox1 = centers[corner][0] + cosf(a1) * radius;
      const float oy1 = centers[corner][1] + sinf(a1) * radius;
      const float ix0 = centers[corner][0] + cosf(a0) * inner_radius;
      const float iy0 = centers[corner][1] + sinf(a0) * inner_radius;
      const float ix1 = centers[corner][0] + cosf(a1) * inner_radius;
      const float iy1 = centers[corner][1] + sinf(a1) * inner_radius;
      const GLfloat quad[24] = {
          ox0 * 2.0f / (float)screen_width - 1.0f,
          1.0f - oy0 * 2.0f / (float)screen_height, 0.0f, 0.0f,
          ox1 * 2.0f / (float)screen_width - 1.0f,
          1.0f - oy1 * 2.0f / (float)screen_height, 0.0f, 0.0f,
          ix0 * 2.0f / (float)screen_width - 1.0f,
          1.0f - iy0 * 2.0f / (float)screen_height, 0.0f, 0.0f,
          ox1 * 2.0f / (float)screen_width - 1.0f,
          1.0f - oy1 * 2.0f / (float)screen_height, 0.0f, 0.0f,
          ix1 * 2.0f / (float)screen_width - 1.0f,
          1.0f - iy1 * 2.0f / (float)screen_height, 0.0f, 0.0f,
          ix0 * 2.0f / (float)screen_width - 1.0f,
          1.0f - iy0 * 2.0f / (float)screen_height, 0.0f, 0.0f,
      };
      memcpy(verts + quads * 24, quad, sizeof(quad));
      quads++;
    }
  }
  quads += emit_rect(x + radius, y, width - radius * 2.0f, thickness,
                     verts + quads * 24);
  quads += emit_rect(x + radius, y + height - thickness,
                     width - radius * 2.0f, thickness, verts + quads * 24);
  quads += emit_rect(x, y + radius, thickness, height - radius * 2.0f,
                     verts + quads * 24);
  quads += emit_rect(x + width - thickness, y + radius, thickness,
                     height - radius * 2.0f, verts + quads * 24);
  return quads;
}

// FPS counter (config.show_fps): draws the rate top-left, refreshed twice a
// second. Saves and restores all the GL state it touches.
static struct {
  u64 window_start;
  u32 frames;
  char text[8];
} fps;

static void overlay_render(void) {
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

  const int control_mode = pes_mobile_control_active_mode();
  const char *controls = NULL;
  if (control_mode == PES_MOBILE_CONTROL_OFFENSE)
    controls = "ATTACK: B PASS  X THROUGH  Y SHOOT  A CROSS  R DASH  + PAUSE";
  else if (control_mode == PES_MOBILE_CONTROL_DEFENSE)
    controls = "DEFEND: B PRESS  A TACKLE  L SWITCH  R DASH  + PAUSE";

  float selector_x = 0.0f;
  float selector_y = 0.0f;
  float selector_width = 0.0f;
  float selector_height = 0.0f;
  const int selector = pes_controller_selector_rect(
      &selector_x, &selector_y, &selector_width, &selector_height);
  const int selector_custom =
      selector && pes_controller_selector_custom_style();
  const int custom_team_popup = pes_controller_custom_team_popup_active();
  const int custom_cpu_popup = pes_controller_custom_cpu_popup_active();
  const int custom_settings_popup =
      pes_controller_custom_match_settings_active();
  const int custom_popup =
      custom_team_popup || custom_cpu_popup || custom_settings_popup;
  float prompt_x = 0.0f;
  float prompt_y = 0.0f;
  const int start_prompt =
      pes_controller_start_prompt(&prompt_x, &prompt_y);
  float gameplan_cursor_x = 0.0f;
  float gameplan_cursor_y = 0.0f;
  const int gameplan_cursor = pes_controller_gameplan_cursor_position(
      &gameplan_cursor_x, &gameplan_cursor_y);

  if ((!config.show_fps || !fps.text[0]) && !controls && !selector &&
      !start_prompt && !custom_popup && !gameplan_cursor)
    return;
  if (!gl_init())
    return;

  static GLfloat verts[4096 * 24];
  int quads = 0;
  int custom_backdrop_quads = 0;
  int custom_panel_quads = 0;
  int custom_header_round_quads = 0;
  int custom_header_fill_quads = 0;
  int custom_selected_quads = 0;
  int custom_rule_quads = 0;
  int custom_value_plate_quads = 0;
  int custom_arrow_quads = 0;
  int custom_badge_plate_quads = 0;
  int custom_action_button_quads = 0;
  int custom_back_button_quads = 0;
  int custom_action_key_bg_quads = 0;
  int custom_back_key_bg_quads = 0;
  int custom_icon_quads = 0;
  int custom_dark_text_first_quad = 0;
  int custom_dark_text_quads = 0;
  int custom_white_text_first_quad = 0;
  int custom_white_text_quads = 0;
  int custom_key_text_first_quad = 0;
  int custom_key_text_quads = 0;
  int selector_fill_quads = 0;
  int selector_glow_quads = 0;
  int selector_color_quads = 0;
  int gameplan_helper_circle_first_quad = 0;
  int gameplan_helper_circle_quads = 0;
  int gameplan_helper_text_first_quad = 0;
  int gameplan_helper_text_quads = 0;
  int gameplan_cursor_first_quad = 0;
  int gameplan_cursor_quads = 0;
  RoundedRectStyle custom_panel_style = {0};
  RoundedRectStyle custom_header_style = {0};
  RoundedRectStyle custom_selected_style = {0};
  RoundedRectStyle custom_value_plate_style = {0};
  RoundedRectStyle custom_action_button_style = {0};
  RoundedRectStyle custom_back_button_style = {0};
  if (custom_team_popup) {
    const float panel_x = 0.15f * (float)screen_width;
    const float panel_y = 0.055f * (float)screen_height;
    const float panel_w = 0.70f * (float)screen_width;
    const float panel_h = 0.89f * (float)screen_height;
    const float panel_radius = 0.025f * (float)screen_height;
    const float header_h = 0.105f * (float)screen_height;
    const float footer_y = 0.780f * (float)screen_height;
    const float cell_x[2] = {panel_x + 0.035f * (float)screen_width,
                             panel_x + 0.365f * (float)screen_width};
    const float cell_w = 0.30f * (float)screen_width;
    const float cell_h = 0.125f * (float)screen_height;
    const float cell_step = 0.145f * (float)screen_height;
    const float cell_y0 = 0.185f * (float)screen_height;
    const float selector_inset = 0.012f * (float)screen_height;
    const uint32_t focus = pes_controller_custom_team_popup_focus();
    const uint32_t scroll = pes_controller_custom_team_popup_scroll();
    const uint32_t visible = pes_controller_custom_team_popup_visible_count();
    const float selected_x = cell_x[focus & 1u] + selector_inset;
    const float selected_y =
        cell_y0 + cell_step * (float)(focus / 2u) + selector_inset;
    const float icon_size = 0.078f * (float)screen_height;
    const float back_button_x = panel_x + 0.035f * (float)screen_width;
    const float back_button_y = 0.852f * (float)screen_height;
    const float back_button_w = 0.205f * (float)screen_width;
    const float back_button_h = 0.065f * (float)screen_height;
    const float back_key_radius = 0.020f * (float)screen_height;
    const float back_key_x = back_button_x + 0.030f * (float)screen_width;
    const float back_key_y = back_button_y + back_button_h * 0.5f;

    custom_backdrop_quads = emit_rect(
        0.0f, 0.0f, (float)screen_width, (float)screen_height,
        verts + quads * 24);
    quads += custom_backdrop_quads;
    custom_panel_style =
        (RoundedRectStyle){panel_w, panel_h, panel_radius};
    custom_panel_quads = emit_round_rect_quad(
        panel_x, panel_y, panel_w, panel_h, verts + quads * 24);
    quads += custom_panel_quads;
    custom_header_style =
        (RoundedRectStyle){panel_w, header_h, panel_radius};
    custom_header_round_quads = emit_round_rect_quad(
        panel_x, panel_y, panel_w, header_h, verts + quads * 24);
    quads += custom_header_round_quads;
    custom_header_fill_quads = emit_rect(
        panel_x, panel_y + header_h - panel_radius, panel_w, panel_radius,
        verts + quads * 24);
    quads += custom_header_fill_quads;
    custom_selected_style = (RoundedRectStyle){
        cell_w - selector_inset * 2.0f,
        cell_h - selector_inset * 2.0f,
        0.016f * (float)screen_height};
    custom_selected_quads = emit_round_rect_quad(
        selected_x, selected_y, cell_w - selector_inset * 2.0f,
        cell_h - selector_inset * 2.0f, verts + quads * 24);
    quads += custom_selected_quads;
    // Three internal rules plus one footer rule avoid the doubled divider at
    // the bottom of the final content row.
    for (int row = 0; row < 3; row++) {
      const float y = cell_y0 + cell_step * (float)row;
      custom_rule_quads += emit_rect(
          panel_x + 0.035f * (float)screen_width,
          y + cell_h + 0.010f * (float)screen_height,
          panel_w - 0.070f * (float)screen_width,
          (float)screen_height / 600.0f, verts + quads * 24);
      quads++;
    }
    custom_rule_quads += emit_rect(
        panel_x + 0.35f * (float)screen_width, cell_y0,
        (float)screen_height / 600.0f, footer_y - cell_y0,
        verts + quads * 24);
    quads++;
    custom_rule_quads += emit_rect(
        panel_x + 0.04f * (float)screen_width, footer_y,
        panel_w - 0.08f * (float)screen_width,
        (float)screen_height / 600.0f, verts + quads * 24);
    quads++;
    for (uint32_t item = 0; item < visible; item++) {
      const float icon_x = cell_x[item & 1u] + 0.018f * (float)screen_width;
      const float icon_y = cell_y0 + cell_step * (float)(item / 2u) +
                           (cell_h - icon_size) * 0.5f;
      custom_badge_plate_quads += emit_circle_quad(
          icon_x + icon_size * 0.5f, icon_y + icon_size * 0.5f,
          icon_size * 0.53f, verts + quads * 24);
      quads++;
    }
    custom_back_button_style = (RoundedRectStyle){
        back_button_w, back_button_h, 0.018f * (float)screen_height};
    custom_back_button_quads = emit_round_rect_quad(
        back_button_x, back_button_y, back_button_w, back_button_h,
        verts + quads * 24);
    quads += custom_back_button_quads;
    custom_back_key_bg_quads = emit_circle_quad(
        back_key_x, back_key_y, back_key_radius, verts + quads * 24);
    quads += custom_back_key_bg_quads;
    for (uint32_t item = 0; item < visible; item++) {
      const uint32_t index = scroll + item;
      const float icon_x = cell_x[item & 1u] + 0.018f * (float)screen_width;
      const float icon_y = cell_y0 + cell_step * (float)(item / 2u) +
                           (cell_h - icon_size) * 0.5f;
      custom_icon_quads += emit_badge(
          pes_controller_custom_team_popup_badge(index), icon_x, icon_y,
          icon_size, icon_size, verts + quads * 24);
      quads++;
    }

    custom_dark_text_first_quad = quads;
    const float title_gh = (float)screen_height / 30.0f;
    const float title_gw =
        title_gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
    const float text_gh = (float)screen_height / 40.0f;
    const float text_gw =
        text_gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
    const char *title = pes_controller_custom_team_popup_title();
    int line_quads = emit_line(
        title, (int)strlen(title),
        (float)screen_width * 0.5f -
            (float)strlen(title) * title_gw * 0.5f,
        panel_y + (header_h - title_gh) * 0.5f, title_gw, title_gh,
        verts + quads * 24);
    custom_dark_text_quads += line_quads;
    quads += line_quads;
    for (uint32_t item = 0; item < visible; item++) {
      const uint32_t index = scroll + item;
      const char *label = pes_controller_custom_team_popup_label(index);
      if (!label || !label[0])
        continue;
      const float x = cell_x[item & 1u] + 0.072f * (float)screen_width;
      const float y = cell_y0 + cell_step * (float)(item / 2u) +
                      (cell_h - text_gh) * 0.5f;
      line_quads = emit_line(label, (int)strlen(label), x, y, text_gw,
                             text_gh, verts + quads * 24);
      custom_dark_text_quads += line_quads;
      quads += line_quads;
    }
    char page_text[24];
    snprintf(page_text, sizeof(page_text), "PAGE %u OF %u",
             pes_controller_custom_team_popup_page() + 1,
             pes_controller_custom_team_popup_page_count());
    const int page_len = (int)strlen(page_text);
    line_quads = emit_line(
        page_text, page_len,
        (float)screen_width * 0.5f - (float)page_len * text_gw * 0.5f,
        0.802f * (float)screen_height, text_gw, text_gh,
        verts + quads * 24);
    custom_dark_text_quads += line_quads;
    quads += line_quads;

    custom_white_text_first_quad = quads;
    custom_white_text_quads = emit_line(
        "BACK", 4, back_key_x + 0.027f * (float)screen_width,
        back_button_y + (back_button_h - text_gh) * 0.5f, text_gw, text_gh,
        verts + quads * 24);
    quads += custom_white_text_quads;
    custom_key_text_first_quad = quads;
    custom_key_text_quads = emit_line(
        "B", 1, back_key_x - text_gw * 0.5f,
        back_key_y - text_gh * 0.5f, text_gw, text_gh,
        verts + quads * 24);
    quads += custom_key_text_quads;
  } else if (custom_cpu_popup) {
    const float panel_x = 0.22f * (float)screen_width;
    const float panel_y = 0.08f * (float)screen_height;
    const float panel_w = 0.56f * (float)screen_width;
    const float panel_h = 0.84f * (float)screen_height;
    const float panel_radius = 0.025f * (float)screen_height;
    const float header_h = 0.115f * (float)screen_height;
    const float footer_y = 0.785f * (float)screen_height;
    const float row_x = panel_x + 0.035f * (float)screen_width;
    const float row_w = panel_w - 0.070f * (float)screen_width;
    const float row_y0 = 0.205f * (float)screen_height;
    const float row_h = 0.068f * (float)screen_height;
    const float row_step = 0.077f * (float)screen_height;
    const float selector_inset = 0.006f * (float)screen_height;
    const uint32_t level_count = pes_controller_custom_cpu_popup_count();
    const uint32_t focus = pes_controller_custom_cpu_popup_focus();
    const uint32_t current = pes_controller_custom_cpu_popup_value();
    const float action_button_x = panel_x + 0.035f * (float)screen_width;
    const float action_button_y = 0.823f * (float)screen_height;
    const float action_button_w = 0.220f * (float)screen_width;
    const float back_button_x =
        panel_x + panel_w - 0.035f * (float)screen_width -
        0.200f * (float)screen_width;
    const float back_button_w = 0.200f * (float)screen_width;
    const float button_h = 0.060f * (float)screen_height;
    const float key_radius = 0.019f * (float)screen_height;
    const float action_key_x =
        action_button_x + 0.030f * (float)screen_width;
    const float back_key_x = back_button_x + 0.030f * (float)screen_width;
    const float key_y = action_button_y + button_h * 0.5f;

    custom_backdrop_quads = emit_rect(
        0.0f, 0.0f, (float)screen_width, (float)screen_height,
        verts + quads * 24);
    quads += custom_backdrop_quads;
    custom_panel_style =
        (RoundedRectStyle){panel_w, panel_h, panel_radius};
    custom_panel_quads = emit_round_rect_quad(
        panel_x, panel_y, panel_w, panel_h, verts + quads * 24);
    quads += custom_panel_quads;
    custom_header_style =
        (RoundedRectStyle){panel_w, header_h, panel_radius};
    custom_header_round_quads = emit_round_rect_quad(
        panel_x, panel_y, panel_w, header_h, verts + quads * 24);
    quads += custom_header_round_quads;
    custom_header_fill_quads = emit_rect(
        panel_x, panel_y + header_h - panel_radius, panel_w, panel_radius,
        verts + quads * 24);
    quads += custom_header_fill_quads;
    custom_selected_style = (RoundedRectStyle){
        row_w - selector_inset * 2.0f, row_h - selector_inset * 2.0f,
        0.012f * (float)screen_height};
    custom_selected_quads = emit_round_rect_quad(
        row_x + selector_inset,
        row_y0 + row_step * (float)focus + selector_inset,
        row_w - selector_inset * 2.0f, row_h - selector_inset * 2.0f,
        verts + quads * 24);
    quads += custom_selected_quads;
    for (uint32_t row = 0; row + 1 < level_count; row++) {
      const float rule_y = row_y0 + row_step * (float)(row + 1) -
                           (row_step - row_h) * 0.5f;
      custom_rule_quads += emit_rect(
          row_x, rule_y, row_w, (float)screen_height / 600.0f,
          verts + quads * 24);
      quads++;
    }
    custom_rule_quads += emit_rect(
        panel_x + 0.04f * (float)screen_width, footer_y,
        panel_w - 0.08f * (float)screen_width,
        (float)screen_height / 600.0f, verts + quads * 24);
    quads++;
    const float active_w = 0.115f * (float)screen_width;
    const float active_h = 0.044f * (float)screen_height;
    const float active_x =
        panel_x + panel_w - 0.035f * (float)screen_width - active_w;
    const float active_y = row_y0 + row_step * (float)current +
                           (row_h - active_h) * 0.5f;
    custom_value_plate_style =
        (RoundedRectStyle){active_w, active_h, active_h * 0.5f};
    custom_value_plate_quads = emit_round_rect_quad(
        active_x, active_y, active_w, active_h, verts + quads * 24);
    quads += custom_value_plate_quads;
    custom_action_button_style = (RoundedRectStyle){
        action_button_w, button_h, 0.017f * (float)screen_height};
    custom_action_button_quads = emit_round_rect_quad(
        action_button_x, action_button_y, action_button_w, button_h,
        verts + quads * 24);
    quads += custom_action_button_quads;
    custom_back_button_style = (RoundedRectStyle){
        back_button_w, button_h, 0.017f * (float)screen_height};
    custom_back_button_quads = emit_round_rect_quad(
        back_button_x, action_button_y, back_button_w, button_h,
        verts + quads * 24);
    quads += custom_back_button_quads;
    custom_action_key_bg_quads = emit_circle_quad(
        action_key_x, key_y, key_radius, verts + quads * 24);
    quads += custom_action_key_bg_quads;
    custom_back_key_bg_quads = emit_circle_quad(
        back_key_x, key_y, key_radius, verts + quads * 24);
    quads += custom_back_key_bg_quads;

    custom_dark_text_first_quad = quads;
    const float title_gh = (float)screen_height / 30.0f;
    const float title_gw =
        title_gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
    const float text_gh = (float)screen_height / 38.0f;
    const float text_gw =
        text_gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
    const char *title = "SELECT COM LEVEL";
    int line_quads = emit_line(
        title, (int)strlen(title),
        (float)screen_width * 0.5f -
            (float)strlen(title) * title_gw * 0.5f,
        panel_y + (header_h - title_gh) * 0.5f, title_gw, title_gh,
        verts + quads * 24);
    custom_dark_text_quads += line_quads;
    quads += line_quads;
    for (uint32_t item = 0; item < level_count; item++) {
      const char *label = pes_controller_custom_cpu_popup_label(item);
      const float y = row_y0 + row_step * (float)item +
                      (row_h - text_gh) * 0.5f;
      line_quads = emit_line(
          label, (int)strlen(label), row_x + 0.025f * (float)screen_width,
          y, text_gw, text_gh, verts + quads * 24);
      custom_dark_text_quads += line_quads;
      quads += line_quads;
    }

    custom_white_text_first_quad = quads;
    const float small_gh = (float)screen_height / 48.0f;
    const float small_gw =
        small_gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
    line_quads = emit_line(
        "ACTIVE", 6, active_x + (active_w - 6.0f * small_gw) * 0.5f,
        active_y + (active_h - small_gh) * 0.5f, small_gw, small_gh,
        verts + quads * 24);
    custom_white_text_quads += line_quads;
    quads += line_quads;
    line_quads = emit_line(
        "SELECT", 6, action_key_x + 0.026f * (float)screen_width,
        action_button_y + (button_h - text_gh) * 0.5f, text_gw, text_gh,
        verts + quads * 24);
    custom_white_text_quads += line_quads;
    quads += line_quads;
    line_quads = emit_line(
        "BACK", 4, back_key_x + 0.026f * (float)screen_width,
        action_button_y + (button_h - text_gh) * 0.5f, text_gw, text_gh,
        verts + quads * 24);
    custom_white_text_quads += line_quads;
    quads += line_quads;

    custom_key_text_first_quad = quads;
    line_quads = emit_line(
        "A", 1, action_key_x - text_gw * 0.5f, key_y - text_gh * 0.5f,
        text_gw, text_gh, verts + quads * 24);
    custom_key_text_quads += line_quads;
    quads += line_quads;
    line_quads = emit_line(
        "B", 1, back_key_x - text_gw * 0.5f, key_y - text_gh * 0.5f,
        text_gw, text_gh, verts + quads * 24);
    custom_key_text_quads += line_quads;
    quads += line_quads;
  } else if (custom_settings_popup) {
    const float panel_x = 0.17f * (float)screen_width;
    const float panel_y = 0.08f * (float)screen_height;
    const float panel_w = 0.66f * (float)screen_width;
    const float panel_h = 0.84f * (float)screen_height;
    const float panel_radius = 0.025f * (float)screen_height;
    const float header_h = 0.115f * (float)screen_height;
    const float footer_y = 0.785f * (float)screen_height;
    const float row_x = panel_x + 0.030f * (float)screen_width;
    const float row_w = panel_w - 0.060f * (float)screen_width;
    const float row_y0 = 0.225f * (float)screen_height;
    const float row_h = 0.105f * (float)screen_height;
    const float row_step = 0.125f * (float)screen_height;
    const float selector_inset = 0.006f * (float)screen_height;
    const float value_w = 0.200f * (float)screen_width;
    const float value_h = 0.065f * (float)screen_height;
    const float value_x =
        panel_x + panel_w - 0.035f * (float)screen_width - value_w;
    const uint32_t focus = pes_controller_custom_match_settings_focus();
    const float action_button_x = panel_x + 0.035f * (float)screen_width;
    const float action_button_y = 0.823f * (float)screen_height;
    const float action_button_w = 0.250f * (float)screen_width;
    const float back_button_x =
        panel_x + panel_w - 0.035f * (float)screen_width -
        0.250f * (float)screen_width;
    const float back_button_w = 0.250f * (float)screen_width;
    const float button_h = 0.060f * (float)screen_height;
    const float key_radius = 0.019f * (float)screen_height;
    const float action_key_x =
        action_button_x + 0.030f * (float)screen_width;
    const float back_key_x = back_button_x + 0.030f * (float)screen_width;
    const float key_y = action_button_y + button_h * 0.5f;

    custom_backdrop_quads = emit_rect(
        0.0f, 0.0f, (float)screen_width, (float)screen_height,
        verts + quads * 24);
    quads += custom_backdrop_quads;
    custom_panel_style =
        (RoundedRectStyle){panel_w, panel_h, panel_radius};
    custom_panel_quads = emit_round_rect_quad(
        panel_x, panel_y, panel_w, panel_h, verts + quads * 24);
    quads += custom_panel_quads;
    custom_header_style =
        (RoundedRectStyle){panel_w, header_h, panel_radius};
    custom_header_round_quads = emit_round_rect_quad(
        panel_x, panel_y, panel_w, header_h, verts + quads * 24);
    quads += custom_header_round_quads;
    custom_header_fill_quads = emit_rect(
        panel_x, panel_y + header_h - panel_radius, panel_w, panel_radius,
        verts + quads * 24);
    quads += custom_header_fill_quads;
    custom_selected_style = (RoundedRectStyle){
        row_w - selector_inset * 2.0f, row_h - selector_inset * 2.0f,
        0.016f * (float)screen_height};
    custom_selected_quads = emit_round_rect_quad(
        row_x + selector_inset,
        row_y0 + row_step * (float)focus + selector_inset,
        row_w - selector_inset * 2.0f, row_h - selector_inset * 2.0f,
        verts + quads * 24);
    quads += custom_selected_quads;
    for (int row = 0; row < 3; row++) {
      const float rule_y = row_y0 + row_step * (float)(row + 1) -
                           (row_step - row_h) * 0.5f;
      custom_rule_quads += emit_rect(
          row_x, rule_y, row_w, (float)screen_height / 600.0f,
          verts + quads * 24);
      quads++;
    }
    custom_rule_quads += emit_rect(
        panel_x + 0.04f * (float)screen_width, footer_y,
        panel_w - 0.08f * (float)screen_width,
        (float)screen_height / 600.0f, verts + quads * 24);
    quads++;
    for (uint32_t item = 0; item < 4; item++) {
      const float value_y = row_y0 + row_step * (float)item +
                            (row_h - value_h) * 0.5f;
      custom_value_plate_style =
          (RoundedRectStyle){value_w, value_h, value_h * 0.5f};
      const int plate_quads = emit_round_rect_quad(
          value_x, value_y, value_w, value_h, verts + quads * 24);
      custom_value_plate_quads += plate_quads;
      quads += plate_quads;
    }
    const float arrow_half_w = 0.007f * (float)screen_width;
    const float arrow_half_h = 0.012f * (float)screen_height;
    for (uint32_t item = 0; item < 4; item++) {
      const float center_y =
          row_y0 + row_step * (float)item + row_h * 0.5f;
      const float left_x = value_x - 0.014f * (float)screen_width;
      custom_arrow_quads += emit_triangle(
          left_x + arrow_half_w, center_y - arrow_half_h,
          left_x - arrow_half_w, center_y,
          left_x + arrow_half_w, center_y + arrow_half_h,
          verts + quads * 24);
      quads++;
      const float right_x =
          value_x + value_w + 0.014f * (float)screen_width;
      custom_arrow_quads += emit_triangle(
          right_x - arrow_half_w, center_y - arrow_half_h,
          right_x + arrow_half_w, center_y,
          right_x - arrow_half_w, center_y + arrow_half_h,
          verts + quads * 24);
      quads++;
    }
    custom_action_button_style = (RoundedRectStyle){
        action_button_w, button_h, 0.017f * (float)screen_height};
    custom_action_button_quads = emit_round_rect_quad(
        action_button_x, action_button_y, action_button_w, button_h,
        verts + quads * 24);
    quads += custom_action_button_quads;
    custom_back_button_style = (RoundedRectStyle){
        back_button_w, button_h, 0.017f * (float)screen_height};
    custom_back_button_quads = emit_round_rect_quad(
        back_button_x, action_button_y, back_button_w, button_h,
        verts + quads * 24);
    quads += custom_back_button_quads;
    custom_action_key_bg_quads = emit_circle_quad(
        action_key_x, key_y, key_radius, verts + quads * 24);
    quads += custom_action_key_bg_quads;
    custom_back_key_bg_quads = emit_circle_quad(
        back_key_x, key_y, key_radius, verts + quads * 24);
    quads += custom_back_key_bg_quads;

    custom_dark_text_first_quad = quads;
    const float title_gh = (float)screen_height / 30.0f;
    const float title_gw =
        title_gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
    const float text_gh = (float)screen_height / 36.0f;
    const float text_gw =
        text_gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
    const char *title = "MATCH SETTINGS";
    int line_quads = emit_line(
        title, (int)strlen(title),
        (float)screen_width * 0.5f -
            (float)strlen(title) * title_gw * 0.5f,
        panel_y + (header_h - title_gh) * 0.5f, title_gw, title_gh,
        verts + quads * 24);
    custom_dark_text_quads += line_quads;
    quads += line_quads;
    for (uint32_t item = 0; item < 4; item++) {
      const char *label = pes_controller_custom_match_settings_label(item);
      const float y = row_y0 + row_step * (float)item +
                      (row_h - text_gh) * 0.5f;
      line_quads = emit_line(
          label, (int)strlen(label), row_x + 0.020f * (float)screen_width,
          y, text_gw, text_gh, verts + quads * 24);
      custom_dark_text_quads += line_quads;
      quads += line_quads;
    }

    custom_white_text_first_quad = quads;
    for (uint32_t item = 0; item < 4; item++) {
      const char *value = pes_controller_custom_match_settings_value(item);
      const int value_len = (int)strlen(value);
      const float value_y = row_y0 + row_step * (float)item +
                            (row_h - text_gh) * 0.5f;
      line_quads = emit_line(
          value, value_len,
          value_x + (value_w - (float)value_len * text_gw) * 0.5f,
          value_y, text_gw, text_gh, verts + quads * 24);
      custom_white_text_quads += line_quads;
      quads += line_quads;
    }
    line_quads = emit_line(
        "CHANGE", 6, action_key_x + 0.026f * (float)screen_width,
        action_button_y + (button_h - text_gh) * 0.5f, text_gw, text_gh,
        verts + quads * 24);
    custom_white_text_quads += line_quads;
    quads += line_quads;
    line_quads = emit_line(
        "BACK", 4, back_key_x + 0.026f * (float)screen_width,
        action_button_y + (button_h - text_gh) * 0.5f, text_gw, text_gh,
        verts + quads * 24);
    custom_white_text_quads += line_quads;
    quads += line_quads;

    custom_key_text_first_quad = quads;
    line_quads = emit_line(
        "A", 1, action_key_x - text_gw * 0.5f, key_y - text_gh * 0.5f,
        text_gw, text_gh, verts + quads * 24);
    custom_key_text_quads += line_quads;
    quads += line_quads;
    line_quads = emit_line(
        "B", 1, back_key_x - text_gw * 0.5f, key_y - text_gh * 0.5f,
        text_gw, text_gh, verts + quads * 24);
    custom_key_text_quads += line_quads;
    quads += line_quads;
  }
  if (selector) {
    const float x = selector_x * (float)screen_width;
    const float y = selector_y * (float)screen_height;
    const float width = selector_width * (float)screen_width;
    const float height = selector_height * (float)screen_height;
    const float margin = fmaxf(5.0f, (float)screen_height / 144.0f);
    const float sx = x + margin;
    const float sy = y + margin;
    const float sw = fmaxf(1.0f, width - margin * 2.0f);
    const float sh = fmaxf(1.0f, height - margin * 2.0f);
    const float thickness = (float)screen_height / 150.0f;
    if (selector_custom)
      selector_fill_quads = emit_rounded_rect(
          sx + thickness, sy + thickness, sw - thickness * 2.0f,
          sh - thickness * 2.0f,
          fminf(22.0f, sh * 0.16f), verts + quads * 24);
    quads += selector_fill_quads;
    selector_glow_quads = emit_outline(
        sx - 3.0f, sy - 3.0f, sw + 6.0f, sh + 6.0f,
        thickness + 5.0f, verts + quads * 24);
    quads += selector_glow_quads;
    selector_color_quads = emit_outline(sx, sy, sw, sh, thickness,
                                        verts + quads * 24);
    quads += selector_color_quads;
  }
  if (gameplan_cursor) {
    const float helper_x = 0.835f * (float)screen_width;
    const float helper_y = 0.944f * (float)screen_height;
    const float helper_radius = 0.019f * (float)screen_height;
    gameplan_helper_circle_first_quad = quads;
    gameplan_helper_circle_quads = emit_circle_quad(
        helper_x, helper_y, helper_radius, verts + quads * 24);
    quads += gameplan_helper_circle_quads;

    const float cursor_w = 0.050f * (float)screen_height;
    const float cursor_h = 0.0666667f * (float)screen_height;
    const float cursor_left =
        gameplan_cursor_x * (float)screen_width - cursor_w / 12.0f;
    const float cursor_top =
        gameplan_cursor_y * (float)screen_height - cursor_h / 16.0f;
    gameplan_cursor_first_quad = quads;
    gameplan_cursor_quads = emit_round_rect_quad(
        cursor_left, cursor_top, cursor_w, cursor_h, verts + quads * 24);
    quads += gameplan_cursor_quads;

    const float helper_gh = (float)screen_height / 43.0f;
    const float helper_gw =
        helper_gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
    gameplan_helper_text_first_quad = quads;
    gameplan_helper_text_quads = emit_line(
        "A", 1, helper_x - helper_gw * 0.5f,
        helper_y - helper_gh * 0.5f, helper_gw, helper_gh,
        verts + quads * 24);
    quads += gameplan_helper_text_quads;
  }
  const int text_first_quad = quads;
  int prompt_quads = 0;
  int prompt_solid_quads = 0;
  if (start_prompt) {
    const float gh = (float)screen_height / 22.0f;
    const float gw = gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
    prompt_solid_quads = emit_solid_a(
        prompt_x * (float)screen_width - gw * 0.5f,
        prompt_y * (float)screen_height - gh * 0.5f, gh,
        verts + quads * 24);
    quads += prompt_solid_quads;
    prompt_quads = emit_line(
        "A", 1, prompt_x * (float)screen_width - gw * 0.5f,
        prompt_y * (float)screen_height - gh * 0.5f, gw, gh,
        verts + quads * 24);
    quads += prompt_quads;
  }
  if (config.show_fps && fps.text[0]) {
    const float gh = (float)screen_height / 30.0f;
    const float gw = gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
    quads += emit_line(fps.text, (int)strlen(fps.text), 10.0f, 8.0f,
                       gw, gh, verts + quads * 24);
  }
  if (controls) {
    const int len = (int)strlen(controls);
    const float gh = (float)screen_height / 54.0f;
    const float gw = gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
    float x = (float)screen_width - 12.0f - (float)len * gw;
    if (x < 12.0f)
      x = 12.0f;
    const float y = (float)screen_height - gh - 12.0f;
    quads += emit_line(controls, len, x, y, gw, gh,
                       verts + quads * 24);
  }
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

  glUniform2f(gl.loc_off, 0.0f, 0.0f);
  glUniform1f(gl.loc_image, 0.0f);
  glUniform1f(gl.loc_circle, 0.0f);
  glUniform1f(gl.loc_circle_feather, 0.02f);
  glUniform1f(gl.loc_round_rect, 0.0f);
  glUniform1f(gl.loc_round_feather, 1.15f);
  glUniform1f(gl.loc_cursor, 0.0f);
  glUniform1f(gl.loc_cursor_border, 0.0f);
  if (custom_popup) {
    int custom_offset = 0;
    glUniform1f(gl.loc_solid, 1.0f);
    glUniform4f(gl.loc_color, 0.0f, 0.0f, 0.0f, 0.56f);
    glDrawArrays(GL_TRIANGLES, custom_offset * 6,
                 custom_backdrop_quads * 6);
    custom_offset += custom_backdrop_quads;
    glUniform4f(gl.loc_color, 0.98f, 0.98f, 0.98f, 1.0f);
    use_rounded_rect(&custom_panel_style);
    glDrawArrays(GL_TRIANGLES, custom_offset * 6,
                 custom_panel_quads * 6);
    custom_offset += custom_panel_quads;
    glUniform4f(gl.loc_color, 0.78f, 0.88f, 0.96f, 1.0f);
    use_rounded_rect(&custom_header_style);
    glDrawArrays(GL_TRIANGLES, custom_offset * 6,
                 custom_header_round_quads * 6);
    custom_offset += custom_header_round_quads;
    use_rounded_rect(NULL);
    glDrawArrays(GL_TRIANGLES, custom_offset * 6,
                 custom_header_fill_quads * 6);
    custom_offset += custom_header_fill_quads;
    glUniform4f(gl.loc_color, 0.25f, 0.78f, 0.96f, 0.42f);
    use_rounded_rect(&custom_selected_style);
    glDrawArrays(GL_TRIANGLES, custom_offset * 6,
                 custom_selected_quads * 6);
    custom_offset += custom_selected_quads;
    use_rounded_rect(NULL);
    glUniform4f(gl.loc_color, 0.70f, 0.74f, 0.78f, 0.85f);
    glDrawArrays(GL_TRIANGLES, custom_offset * 6,
                 custom_rule_quads * 6);
    custom_offset += custom_rule_quads;
    glUniform4f(gl.loc_color, 0.02f, 0.42f, 0.72f, 1.0f);
    use_rounded_rect(&custom_value_plate_style);
    glDrawArrays(GL_TRIANGLES, custom_offset * 6,
                 custom_value_plate_quads * 6);
    custom_offset += custom_value_plate_quads;
    use_rounded_rect(NULL);
    glDrawArrays(GL_TRIANGLES, custom_offset * 6,
                 custom_arrow_quads * 6);
    custom_offset += custom_arrow_quads;
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform1f(gl.loc_circle, 1.0f);
    glUniform1f(gl.loc_circle_feather, 0.020f);
    glUniform4f(gl.loc_color, 0.98f, 0.99f, 1.0f, 1.0f);
    glDrawArrays(GL_TRIANGLES, custom_offset * 6,
                 custom_badge_plate_quads * 6);
    custom_offset += custom_badge_plate_quads;
    glUniform1f(gl.loc_circle, 0.0f);
    glUniform1f(gl.loc_solid, 1.0f);
    glUniform4f(gl.loc_color, 0.02f, 0.42f, 0.72f, 1.0f);
    use_rounded_rect(&custom_action_button_style);
    glDrawArrays(GL_TRIANGLES, custom_offset * 6,
                 custom_action_button_quads * 6);
    custom_offset += custom_action_button_quads;
    use_rounded_rect(&custom_back_button_style);
    glDrawArrays(GL_TRIANGLES, custom_offset * 6,
                 custom_back_button_quads * 6);
    custom_offset += custom_back_button_quads;
    use_rounded_rect(NULL);
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform1f(gl.loc_circle, 1.0f);
    glUniform1f(gl.loc_circle_feather, 0.035f);
    glUniform4f(gl.loc_color, 0.98f, 0.99f, 1.0f, 1.0f);
    glDrawArrays(GL_TRIANGLES, custom_offset * 6,
                 custom_action_key_bg_quads * 6);
    custom_offset += custom_action_key_bg_quads;
    glDrawArrays(GL_TRIANGLES, custom_offset * 6,
                 custom_back_key_bg_quads * 6);
    custom_offset += custom_back_key_bg_quads;
    glUniform1f(gl.loc_circle, 0.0f);
    glUniform1f(gl.loc_round_rect, 0.0f);
    glBindTexture(GL_TEXTURE_2D, gl.badge_tex);
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform1f(gl.loc_image, 1.0f);
    glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, 1.0f);
    glDrawArrays(GL_TRIANGLES, custom_offset * 6,
                 custom_icon_quads * 6);
    glBindTexture(GL_TEXTURE_2D, gl.tex);
    glUniform1f(gl.loc_image, 0.0f);
  }
  if (selector_fill_quads) {
    glUniform1f(gl.loc_solid, 1.0f);
    glUniform4f(gl.loc_color, 0.0f, 0.70f, 1.0f, 0.10f);
    glDrawArrays(GL_TRIANGLES, 0, selector_fill_quads * 6);
  }
  if (selector_glow_quads) {
    const u64 freq = armGetSystemTickFreq();
    const float phase = freq ?
        (float)(armGetSystemTick() % freq) / (float)freq : 0.0f;
    const float pulse = 0.5f + 0.5f * cosf(phase * 6.2831853f);
    glUniform1f(gl.loc_solid, 1.0f);
    glUniform4f(gl.loc_color, 0.0f, 0.55f, 1.0f, 0.18f + 0.12f * pulse);
    glDrawArrays(GL_TRIANGLES, selector_fill_quads * 6,
                 selector_glow_quads * 6);
    glUniform4f(gl.loc_color, 0.0f, 0.78f, 1.0f, 0.72f + 0.28f * pulse);
    glDrawArrays(GL_TRIANGLES,
                 (selector_fill_quads + selector_glow_quads) * 6,
                 selector_color_quads * 6);
  }
  if (gameplan_helper_circle_quads) {
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform1f(gl.loc_round_rect, 0.0f);
    glUniform1f(gl.loc_cursor, 0.0f);
    glUniform1f(gl.loc_circle, 1.0f);
    glUniform1f(gl.loc_circle_feather, 0.035f);
    glUniform4f(gl.loc_color, 0.98f, 0.99f, 1.0f, 1.0f);
    glDrawArrays(GL_TRIANGLES, gameplan_helper_circle_first_quad * 6,
                 gameplan_helper_circle_quads * 6);
    glUniform1f(gl.loc_circle, 0.0f);
  }
  if (gameplan_helper_text_quads) {
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform2f(gl.loc_off, 0.0f, 0.0f);
    glUniform4f(gl.loc_color, 0.02f, 0.36f, 0.62f, 1.0f);
    glDrawArrays(GL_TRIANGLES, gameplan_helper_text_first_quad * 6,
                 gameplan_helper_text_quads * 6);
  }
  if (gameplan_cursor_quads) {
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform1f(gl.loc_circle, 0.0f);
    glUniform1f(gl.loc_round_rect, 0.0f);
    glUniform1f(gl.loc_cursor, 1.0f);
    glUniform1f(gl.loc_cursor_border, 2.2f);
    glUniform4f(gl.loc_color, 0.01f, 0.03f, 0.04f, 0.90f);
    glDrawArrays(GL_TRIANGLES, gameplan_cursor_first_quad * 6,
                 gameplan_cursor_quads * 6);
    glUniform1f(gl.loc_cursor_border, 0.0f);
    glUniform4f(gl.loc_color, 0.98f, 0.99f, 1.0f, 1.0f);
    glDrawArrays(GL_TRIANGLES, gameplan_cursor_first_quad * 6,
                 gameplan_cursor_quads * 6);
    glUniform1f(gl.loc_cursor, 0.0f);
  }
  if (custom_dark_text_quads) {
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform2f(gl.loc_off, 0.0f, 0.0f);
    glUniform4f(gl.loc_color, 0.025f, 0.075f, 0.12f, 1.0f);
    glDrawArrays(GL_TRIANGLES, custom_dark_text_first_quad * 6,
                 custom_dark_text_quads * 6);
  }
  if (custom_white_text_quads) {
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform2f(gl.loc_off, 0.0f, 0.0f);
    glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, 1.0f);
    glDrawArrays(GL_TRIANGLES, custom_white_text_first_quad * 6,
                 custom_white_text_quads * 6);
  }
  if (custom_key_text_quads) {
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform4f(gl.loc_color, 0.02f, 0.36f, 0.62f, 1.0f);
    glDrawArrays(GL_TRIANGLES, custom_key_text_first_quad * 6,
                 custom_key_text_quads * 6);
  }
  const int text_quads = quads - text_first_quad;
  if (text_quads) {
    if (prompt_solid_quads) {
      glUniform1f(gl.loc_solid, 1.0f);
      glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, 1.0f);
      glDrawArrays(GL_TRIANGLES, text_first_quad * 6,
                   prompt_solid_quads * 6);
    }
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform2f(gl.loc_off, 3.0f / (float)screen_width,
                -3.0f / (float)screen_height);
    glUniform4f(gl.loc_color, 0.0f, 0.0f, 0.0f, 0.9f);
    glDrawArrays(GL_TRIANGLES, text_first_quad * 6, text_quads * 6);
    glUniform2f(gl.loc_off, 0.0f, 0.0f);
    glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, 1.0f);
    glDrawArrays(GL_TRIANGLES, text_first_quad * 6, text_quads * 6);
    if (prompt_quads) {
      glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, 1.0f);
      glDrawArrays(GL_TRIANGLES, text_first_quad * 6, prompt_quads * 6);
    }
  }

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
  overlay_render();
  return eglSwapBuffers((EGLDisplay)display, (EGLSurface)surface);
}
