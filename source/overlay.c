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
#include "android_shim.h"
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
static int emit_line_advance(const char *text, int len, float x, float y,
                             float gw, float gh, float advance,
                             GLfloat *verts) {
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
    const float gx = x + j * advance;
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

static int emit_line(const char *text, int len, float x, float y,
                     float gw, float gh, GLfloat *verts) {
  return emit_line_advance(text, len, x, y, gw, gh, gw, verts);
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

static int emit_triangle(float x0, float y0, float x1, float y1, float x2,
                         float y2, GLfloat *verts);

// Geometry-backed helper circle. Some Switch GPU/driver combinations can
// leave the fragment-mask circle uniform stale after the game's own pass; a
// fan of solid triangles is deterministic and cannot fall back to a square.
static int emit_filled_circle(float center_x, float center_y, float radius,
                              GLfloat *verts) {
  int triangles = 0;
  // A 48-sided fan is visually smooth at the 14-18 px helper size. Rotate
  // each edge with a recurrence instead of evaluating sin/cos every frame.
  const int segments = 48;
  const float step_cos = 0.991444861f;
  const float step_sin = 0.130526192f;
  float edge_x = radius;
  float edge_y = 0.0f;
  for (int i = 0; i < segments; i++) {
    const float next_x = edge_x * step_cos - edge_y * step_sin;
    const float next_y = edge_x * step_sin + edge_y * step_cos;
    triangles += emit_triangle(
        center_x, center_y, center_x + edge_x, center_y + edge_y,
        center_x + next_x, center_y + next_y, verts + triangles * 24);
    edge_x = next_x;
    edge_y = next_y;
  }
  return triangles;
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

static const char *native_lab_event_name(uint32_t event) {
  switch (event) {
  case PES_NATIVE_LAB_EVENT_AIM:
    return "LS AIM";
  case PES_NATIVE_LAB_EVENT_SHORT_PRESS:
    return "B SHORT PRESS";
  case PES_NATIVE_LAB_EVENT_SHORT_RELEASE:
    return "B SHORT RELEASE";
  case PES_NATIVE_LAB_EVENT_LONG_PRESS:
    return "A LONG PRESS";
  case PES_NATIVE_LAB_EVENT_LONG_RELEASE:
    return "A LONG RELEASE";
  case PES_NATIVE_LAB_EVENT_SHOOT_PRESS:
    return "Y SHOOT PRESS";
  case PES_NATIVE_LAB_EVENT_SHOOT_RELEASE:
    return "Y SHOOT RELEASE";
  case PES_NATIVE_LAB_EVENT_SUPPORT_RELEASE:
    return "L SUPPORT RELEASE";
  default:
    return "NONE";
  }
}

static const char *native_lab_setplay_name(uint32_t context) {
  switch (context) {
  case PES_SETPLAY_GOAL_KICK:
    return "GOAL KICK";
  case PES_SETPLAY_CORNER:
    return "CORNER";
  case PES_SETPLAY_FREE_KICK:
    return "FREE KICK";
  default:
    return "--";
  }
}

static void overlay_render(void) {
  if (config.show_fps) {
    const u64 now = armGetSystemTick();
    const u64 freq = armGetSystemTickFreq();
    fps.frames++;
    if (!fps.window_start)
      fps.window_start = now;
    if (now - fps.window_start >= freq / 2) {
      const float rate = (float)fps.frames * (float)freq /
                         (float)(now - fps.window_start);
      snprintf(fps.text, sizeof(fps.text), "%.0f", rate);
      fps.frames = 0;
      fps.window_start = now;
    }
  } else if (fps.window_start || fps.frames || fps.text[0]) {
    memset(&fps, 0, sizeof(fps));
  }

  PesControllerSnapshot controller_snapshot = {0};
  // android_input_poll already resolves native replay/goal/set-play lifetimes
  // at 60 Hz. Reuse that published word here instead of repeating all timeout
  // checks and CAS work on the render thread for every eglSwap.
  pes_controller_surface_cached_snapshot(&controller_snapshot);
  const int goal_demo_active =
      controller_snapshot.surface == PES_CONTROLLER_SURFACE_GOAL_DEMO;
  const int goal_demo_player =
      goal_demo_active && controller_snapshot.goal_player;
  // Replay and generic demo input remains fully active, but does not need a
  // controller legend. Those short-lived surfaces can alternate around every
  // transition and made the old "ANY BUTTON - SKIP" text visibly blink. Keep
  // a helper only for the interactive GoalDemo page where A/B have distinct
  // meanings.
  const int cinematic_helper_active =
      goal_demo_active && controller_snapshot.goal_helper_visible;
  const int cinematic_goal_actions = goal_demo_player;
  const int cinematic_goal_skip_only =
      goal_demo_active && !goal_demo_player;
  uint32_t setplay_context =
      controller_snapshot.surface == PES_CONTROLLER_SURFACE_SETPLAY
          ? controller_snapshot.setplay_context
          : PES_SETPLAY_NONE;
  uint32_t setplay_options =
      controller_snapshot.surface == PES_CONTROLLER_SURFACE_SETPLAY
          ? controller_snapshot.setplay_options
          : 0;
  const int pause_camera_active = pes_controller_pause_camera_active();
  const int tutorial_play_active =
      pes_controller_inmatch_tutorial_active();
  const uint32_t penalty_role_p1 = pes_controller_penalty_role_for_pad(0);
  const int penalty_two_player = pes_controller_native_pad_lab_two_player();
  const uint32_t penalty_role_p2 =
      penalty_two_player ? pes_controller_penalty_role_for_pad(1)
                         : PES_PENALTY_NONE;
  const int set_piece_selector =
      pes_controller_set_piece_selector_active();
  float selector_x = 0.0f;
  float selector_y = 0.0f;
  float selector_width = 0.0f;
  float selector_height = 0.0f;
  const int selector = !set_piece_selector && pes_controller_selector_rect(
      &selector_x, &selector_y, &selector_width, &selector_height);
  const int selector_custom =
      selector && pes_controller_selector_custom_style();
  const int custom_team_popup = pes_controller_custom_team_popup_active();
  const int custom_cpu_popup = pes_controller_custom_cpu_popup_active();
  const int custom_settings_popup =
      pes_controller_custom_match_settings_active();
  const int custom_video_settings_popup =
      pes_controller_custom_video_settings_active();
  const int custom_info_popup = pes_controller_custom_info_popup_active();
  const int custom_popup =
      custom_team_popup || custom_cpu_popup || custom_settings_popup ||
      custom_video_settings_popup || custom_info_popup || set_piece_selector;
  float prompt_x = 0.0f;
  float prompt_y = 0.0f;
  const int start_prompt =
      pes_controller_start_prompt(&prompt_x, &prompt_y);
  const int native_lab = pes_controller_native_pad_lab_active();
  PesNativePadLabDebug native_debug = {0};
  if (native_lab)
    pes_controller_native_pad_lab_debug_snapshot(&native_debug);
  int native_setplay_debug =
      native_lab && native_debug.context != PES_SETPLAY_NONE;
  if (native_setplay_debug) {
    // The semantic snapshot can lag one frame behind ThinkUnitList. During
    // the native lab, the routed native context is authoritative; otherwise
    // corner/free kick briefly fall back to the exhibition ZR/X/Y legend.
    setplay_context = native_debug.context;
    setplay_options = 0;
  }
  const uint32_t setplay_owner_pad =
      native_setplay_debug && native_debug.setplay_pad == 1 ? 1u : 0u;
  const int single_joy_setplay =
      android_controller_profile(setplay_owner_pad) !=
      PES_CONTROLLER_PROFILE_FULL;
  const char *setplay_taker_key = single_joy_setplay ? "L1+R1" : ">";
  float gameplan_cursor_x = 0.0f;
  float gameplan_cursor_y = 0.0f;
  const int virtual_cursor_context = pes_controller_virtual_cursor_context();
  const int gameplan_cursor =
      !set_piece_selector && !tutorial_play_active &&
      pes_controller_gameplan_cursor_position(&gameplan_cursor_x,
                                              &gameplan_cursor_y);

  const int modal_match_frontend =
      virtual_cursor_context == PES_VIRTUAL_CURSOR_PAUSE ||
      virtual_cursor_context == PES_VIRTUAL_CURSOR_GAMEPLAN ||
      pause_camera_active;
  if (modal_match_frontend) {
    // Pause and its Game Plan/Camera children own the foreground. Keep the
    // set-play state latched underneath, but suppress its mapper until the
    // match resumes.
    setplay_context = PES_SETPLAY_NONE;
    setplay_options = 0;
    native_setplay_debug = 0;
  }

  // The custom selector owns the modal presentation. Do not let the
  // underlying match set-play legend bleed through its footer.
  if (set_piece_selector || tutorial_play_active) {
    setplay_context = PES_SETPLAY_NONE;
    setplay_options = 0;
  }
  // Penalty is a controller-owned surface, not a set-piece selector.  The
  // stock ButtonSetplay snapshot can still carry its old option bits for a
  // few frames, which used to repaint the exhibition `ZR SET PIECE TAKER`
  // helper over the native P1/P2 penalty legend.  Give the latched penalty
  // roles priority for the complete idle/aim/kick transition.
  const int penalty_session_active =
      penalty_role_p1 != PES_PENALTY_NONE ||
      penalty_role_p2 != PES_PENALTY_NONE;
  if (penalty_session_active) {
    setplay_context = PES_SETPLAY_NONE;
    setplay_options = 0;
    native_setplay_debug = 0;
  }

  if ((!config.show_fps || !fps.text[0]) && !selector &&
      !start_prompt && !custom_popup && !gameplan_cursor && !native_lab &&
      !setplay_options && !pause_camera_active && !tutorial_play_active &&
      !cinematic_helper_active && penalty_role_p1 == PES_PENALTY_NONE &&
      penalty_role_p2 == PES_PENALTY_NONE)
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
  int setplay_helper_circle_first_quad = 0;
  int setplay_helper_circle_quads = 0;
  int setplay_helper_icon_first_quad = 0;
  int setplay_helper_icon_quads = 0;
  int setplay_helper_text_first_quad = 0;
  int setplay_helper_text_quads = 0;
  int setplay_key_first_quads[5] = {0};
  int setplay_key_quads[5] = {0};
  int power_gauge_background_first_quad[2] = {0};
  int power_gauge_background_quads[2] = {0};
  int power_gauge_segment_first_quad[2] = {0};
  int power_gauge_segment_quads[2] = {0};
  int power_gauge_active_segments[2] = {0};
  int cinematic_helper_circle_first_quad = 0;
  int cinematic_helper_circle_quads = 0;
  int cinematic_helper_text_first_quad = 0;
  int cinematic_helper_text_quads = 0;
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
  } else if (custom_info_popup) {
    const float panel_x = 0.22f * (float)screen_width;
    const float panel_y = 0.18f * (float)screen_height;
    const float panel_w = 0.56f * (float)screen_width;
    const float panel_h = 0.64f * (float)screen_height;
    const float panel_radius = 0.025f * (float)screen_height;
    const float header_h = 0.12f * (float)screen_height;
    const float footer_y = 0.65f * (float)screen_height;
    const float back_button_w = 0.24f * (float)screen_width;
    const float back_button_h = 0.065f * (float)screen_height;
    const float back_button_x =
        (float)screen_width * 0.5f - back_button_w * 0.5f;
    const float back_button_y = 0.70f * (float)screen_height;
    const float back_key_radius = 0.020f * (float)screen_height;
    const float back_key_x =
        back_button_x + 0.030f * (float)screen_width;
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
    custom_rule_quads = emit_rect(
        panel_x + 0.04f * (float)screen_width, footer_y,
        panel_w - 0.08f * (float)screen_width,
        (float)screen_height / 600.0f, verts + quads * 24);
    quads += custom_rule_quads;
    custom_back_button_style = (RoundedRectStyle){
        back_button_w, back_button_h, 0.018f * (float)screen_height};
    custom_back_button_quads = emit_round_rect_quad(
        back_button_x, back_button_y, back_button_w, back_button_h,
        verts + quads * 24);
    quads += custom_back_button_quads;
    custom_back_key_bg_quads = emit_circle_quad(
        back_key_x, back_key_y, back_key_radius, verts + quads * 24);
    quads += custom_back_key_bg_quads;

    custom_dark_text_first_quad = quads;
    const float title_gh = (float)screen_height / 30.0f;
    const float title_gw =
        title_gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
    const float text_gh = (float)screen_height / 30.0f;
    const float text_gw =
        text_gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
    const float text_advance = text_gw * 0.84f;
    const char *title = pes_controller_custom_info_popup_title();
    int line_quads = emit_line(
        title, (int)strlen(title),
        (float)screen_width * 0.5f -
            (float)strlen(title) * title_gw * 0.5f,
        panel_y + (header_h - title_gh) * 0.5f, title_gw, title_gh,
        verts + quads * 24);
    custom_dark_text_quads += line_quads;
    quads += line_quads;

    const uint32_t line_count =
        pes_controller_custom_info_popup_line_count();
    const float line_step = 0.085f * (float)screen_height;
    const float content_center_y = 0.48f * (float)screen_height;
    const float line_y0 = content_center_y -
                          ((float)line_count - 1.0f) * line_step * 0.5f -
                          text_gh * 0.5f;
    for (uint32_t item = 0; item < line_count; item++) {
      const char *line = pes_controller_custom_info_popup_line(item);
      const int line_len = (int)strlen(line);
      const float line_width =
          line_len > 0 ? text_gw + (float)(line_len - 1) * text_advance
                       : 0.0f;
      line_quads = emit_line_advance(
          line, line_len,
          (float)screen_width * 0.5f - line_width * 0.5f,
          line_y0 + (float)item * line_step, text_gw, text_gh, text_advance,
          verts + quads * 24);
      custom_dark_text_quads += line_quads;
      quads += line_quads;
    }

    const float button_gh = (float)screen_height / 38.0f;
    const float button_gw =
        button_gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
    custom_white_text_first_quad = quads;
    custom_white_text_quads = emit_line(
        "BACK", 4, back_key_x + 0.027f * (float)screen_width,
        back_button_y + (back_button_h - button_gh) * 0.5f, button_gw,
        button_gh, verts + quads * 24);
    quads += custom_white_text_quads;
    custom_key_text_first_quad = quads;
    custom_key_text_quads = emit_line(
        "B", 1, back_key_x - button_gw * 0.5f,
        back_key_y - button_gh * 0.5f, button_gw, button_gh,
        verts + quads * 24);
    quads += custom_key_text_quads;
  } else if (set_piece_selector) {
    // Keep TouchKickerSelect completely controller-owned, but present the
    // roster as a compact modal instead of replacing the whole result view.
    // Five one-column rows keep NAME and FOOT TYPE readable from docked mode.
    const float panel_x = 0.205f * (float)screen_width;
    const float panel_y = 0.055f * (float)screen_height;
    const float panel_w = 0.590f * (float)screen_width;
    const float panel_h = 0.890f * (float)screen_height;
    const float panel_radius = 0.025f * (float)screen_height;
    const float header_h = 0.110f * (float)screen_height;
    const float row_x = panel_x + 0.030f * (float)screen_width;
    const float row_y0 = panel_y + 0.145f * (float)screen_height;
    const float row_w = panel_w - 0.060f * (float)screen_width;
    const float row_gap = 0.012f * (float)screen_height;
    const float row_h = 0.098f * (float)screen_height;
    const float footer_y = panel_y + 0.735f * (float)screen_height;
    const float button_y = panel_y + 0.785f * (float)screen_height;
    const float button_h = 0.068f * (float)screen_height;
    const float button_w = 0.205f * (float)screen_width;
    const float button_gap = 0.020f * (float)screen_width;
    const float back_x = panel_x + panel_w -
                         0.030f * (float)screen_width - button_w;
    const float action_x = back_x - button_gap - button_w;
    const float key_radius = 0.019f * (float)screen_height;
    const float action_key_x = action_x + 0.028f * (float)screen_width;
    const float back_key_x = back_x + 0.028f * (float)screen_width;
    const float key_y = button_y + button_h * 0.5f;
    const uint32_t count = pes_controller_set_piece_selector_count();
    uint32_t focus = pes_controller_set_piece_selector_focus();
    if (count && focus >= count)
      focus = count - 1u;
    const uint32_t page = focus / PES_SET_PIECE_SELECTOR_PAGE_SIZE;
    const uint32_t page_start = page * PES_SET_PIECE_SELECTOR_PAGE_SIZE;
    const uint32_t page_count =
        count ? (count + PES_SET_PIECE_SELECTOR_PAGE_SIZE - 1u) /
                    PES_SET_PIECE_SELECTOR_PAGE_SIZE
              : 1u;
    const uint32_t visible_count =
        count > page_start
            ? ((count - page_start) < PES_SET_PIECE_SELECTOR_PAGE_SIZE
                   ? count - page_start
                   : PES_SET_PIECE_SELECTOR_PAGE_SIZE)
            : 0u;
    const uint32_t local_focus = focus - page_start;
    const float selected_y =
        row_y0 + (float)local_focus * (row_h + row_gap);

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
    custom_selected_style = (RoundedRectStyle){
        row_w, row_h, 0.014f * (float)screen_height};
    if (count) {
      custom_selected_quads = emit_round_rect_quad(
          row_x, selected_y, row_w, row_h, verts + quads * 24);
      quads += custom_selected_quads;
    }
    for (uint32_t slot = 0; slot < visible_count; slot++) {
      const float card_y = row_y0 + (float)slot * (row_h + row_gap);
      const int outline_quads = emit_outline(
          row_x, card_y, row_w, row_h,
          fmaxf(1.5f, (float)screen_height / 480.0f),
          verts + quads * 24);
      custom_rule_quads += outline_quads;
      quads += outline_quads;
    }
    const int footer_rule_quads = emit_rect(
        row_x, footer_y, row_w, (float)screen_height / 600.0f,
        verts + quads * 24);
    custom_rule_quads += footer_rule_quads;
    quads += footer_rule_quads;
    custom_action_button_style =
        (RoundedRectStyle){button_w, button_h, 0.017f * (float)screen_height};
    custom_action_button_quads = emit_round_rect_quad(
        action_x, button_y, button_w, button_h, verts + quads * 24);
    quads += custom_action_button_quads;
    custom_back_button_style =
        (RoundedRectStyle){button_w, button_h, 0.017f * (float)screen_height};
    custom_back_button_quads = emit_round_rect_quad(
        back_x, button_y, button_w, button_h, verts + quads * 24);
    quads += custom_back_button_quads;
    custom_action_key_bg_quads = emit_circle_quad(
        action_key_x, key_y, key_radius, verts + quads * 24);
    quads += custom_action_key_bg_quads;
    custom_back_key_bg_quads = emit_circle_quad(
        back_key_x, key_y, key_radius, verts + quads * 24);
    quads += custom_back_key_bg_quads;

    const float title_gh = (float)screen_height / 29.0f;
    const float title_gw =
        title_gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
    const float text_gh = (float)screen_height / 42.0f;
    const float text_gw = text_gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
    const char *title = pes_controller_set_piece_selector_title();
    int line_quads = emit_line(
        title, (int)strlen(title),
        panel_x + panel_w * 0.5f -
            (float)strlen(title) * title_gw * 0.5f,
        panel_y + (header_h - title_gh) * 0.5f, title_gw, title_gh,
        verts + quads * 24);
    custom_dark_text_first_quad = quads;
    custom_dark_text_quads += line_quads;
    quads += line_quads;
    char page_label[24];
    snprintf(page_label, sizeof(page_label), "PAGE %u / %u", page + 1u,
             page_count);
    line_quads = emit_line(
        page_label, (int)strlen(page_label),
        panel_x + panel_w - 0.022f * (float)screen_width -
            (float)strlen(page_label) * text_gw,
        panel_y + (header_h - text_gh) * 0.5f, text_gw, text_gh,
        verts + quads * 24);
    custom_dark_text_quads += line_quads;
    quads += line_quads;
    if (!count) {
      const char *loading = "LOADING PLAYERS...";
      line_quads = emit_line(
          loading, (int)strlen(loading),
          panel_x + panel_w * 0.5f -
              (float)strlen(loading) * text_gw * 0.5f,
          panel_y + panel_h * 0.46f, text_gw, text_gh,
          verts + quads * 24);
      custom_dark_text_quads += line_quads;
      quads += line_quads;
    }
    for (uint32_t slot = 0; slot < visible_count; slot++) {
      const uint32_t player_index = page_start + slot;
      const float card_y = row_y0 + (float)slot * (row_h + row_gap);
      const char *player_name =
          pes_controller_set_piece_selector_name_at(player_index);
      const char *player_foot =
          pes_controller_set_piece_selector_foot_at(player_index);
      const int current_player =
          pes_controller_set_piece_selector_current_at(player_index);
      const float name_gh = (float)screen_height / 32.0f;
      const float name_gw =
          name_gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
      const float foot_gh = (float)screen_height / 45.0f;
      const float foot_gw =
          foot_gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
      char display_name[25];
      snprintf(display_name, sizeof(display_name), "%.24s", player_name);
      line_quads = emit_line(
          display_name, (int)strlen(display_name),
          row_x + 0.022f * (float)screen_width,
          card_y + (row_h - name_gh) * 0.5f, name_gw, name_gh,
          verts + quads * 24);
      custom_dark_text_quads += line_quads;
      quads += line_quads;
      char display_foot[25];
      snprintf(display_foot, sizeof(display_foot), "%.24s", player_foot);
      const int foot_len = (int)strlen(display_foot);
      const float foot_x =
          row_x + row_w - 0.022f * (float)screen_width -
          (float)foot_len * foot_gw;
      line_quads = emit_line(
          display_foot, foot_len, foot_x,
          card_y + (row_h - foot_gh) * 0.5f, foot_gw, foot_gh,
          verts + quads * 24);
      custom_dark_text_quads += line_quads;
      quads += line_quads;
      if (current_player) {
        const char *current_label = "CURRENT";
        const int current_len = 7;
        const float current_gh = (float)screen_height / 50.0f;
        const float current_gw =
            current_gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
        line_quads = emit_line(
            current_label, current_len,
            foot_x - 0.020f * (float)screen_width -
                (float)current_len * current_gw,
            card_y + (row_h - current_gh) * 0.5f, current_gw, current_gh,
            verts + quads * 24);
        custom_dark_text_quads += line_quads;
        quads += line_quads;
      }
    }

    custom_white_text_first_quad = quads;
    line_quads = emit_line(
        "SELECT", 6, action_key_x + 0.026f * (float)screen_width,
        button_y + (button_h - text_gh) * 0.5f, text_gw, text_gh,
        verts + quads * 24);
    custom_white_text_quads += line_quads;
    quads += line_quads;
    line_quads = emit_line(
        "BACK", 4, back_key_x + 0.026f * (float)screen_width,
        button_y + (button_h - text_gh) * 0.5f, text_gw, text_gh,
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
  } else if (custom_settings_popup || custom_video_settings_popup) {
    const uint32_t item_count = custom_video_settings_popup ? 2u : PES_MATCH_SETTINGS_COUNT;
    const float panel_x = (custom_video_settings_popup ? 0.20f : 0.17f) *
                          (float)screen_width;
    const float panel_y = (custom_video_settings_popup ? 0.16f : 0.08f) *
                          (float)screen_height;
    const float panel_w = (custom_video_settings_popup ? 0.60f : 0.66f) *
                          (float)screen_width;
    const float panel_h = (custom_video_settings_popup ? 0.68f : 0.84f) *
                          (float)screen_height;
    const float panel_radius = 0.025f * (float)screen_height;
    const float header_h = 0.115f * (float)screen_height;
    const float footer_y =
        (custom_video_settings_popup ? 0.64f : 0.785f) *
        (float)screen_height;
    const float row_x = panel_x + 0.030f * (float)screen_width;
    const float row_w = panel_w - 0.060f * (float)screen_width;
    const float row_y0 =
        (custom_video_settings_popup ? 0.32f : PES_MATCH_SETTINGS_ROW_Y) *
        (float)screen_height;
    const float row_h =
        (custom_video_settings_popup ? 0.12f : 0.090f) *
        (float)screen_height;
    const float row_step =
        (custom_video_settings_popup ? 0.145f : PES_MATCH_SETTINGS_ROW_STEP) *
        (float)screen_height;
    const float selector_inset = 0.006f * (float)screen_height;
    const float value_w = 0.200f * (float)screen_width;
    const float value_h = 0.065f * (float)screen_height;
    const float value_x =
        panel_x + panel_w - 0.035f * (float)screen_width - value_w;
    const uint32_t focus = custom_video_settings_popup
                               ? pes_controller_custom_video_settings_focus()
                               : pes_controller_custom_match_settings_focus();
    const float button_margin =
        (custom_video_settings_popup ? 0.025f : 0.035f) *
        (float)screen_width;
    const float action_button_x = panel_x + button_margin;
    const float action_button_y =
        (custom_video_settings_popup ? 0.69f : 0.823f) *
        (float)screen_height;
    const float action_button_w =
        (custom_video_settings_popup ? 0.160f : 0.250f) *
        (float)screen_width;
    const float apply_button_x =
        (float)screen_width * 0.5f - action_button_w * 0.5f;
    const float back_button_x =
        panel_x + panel_w - button_margin - action_button_w;
    const float back_button_w = action_button_w;
    const float button_h = 0.060f * (float)screen_height;
    const float key_radius = 0.019f * (float)screen_height;
    const float action_key_x =
        action_button_x + 0.030f * (float)screen_width;
    const float apply_key_x =
        apply_button_x + 0.030f * (float)screen_width;
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
    for (uint32_t row = 0; row + 1 < item_count; row++) {
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
    for (uint32_t item = 0; item < item_count; item++) {
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
    for (uint32_t item = 0; item < item_count; item++) {
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
    if (custom_video_settings_popup) {
      const int apply_quads = emit_round_rect_quad(
          apply_button_x, action_button_y, action_button_w, button_h,
          verts + quads * 24);
      custom_action_button_quads += apply_quads;
      quads += apply_quads;
    }
    custom_back_button_style = (RoundedRectStyle){
        back_button_w, button_h, 0.017f * (float)screen_height};
    custom_back_button_quads = emit_round_rect_quad(
        back_button_x, action_button_y, back_button_w, button_h,
        verts + quads * 24);
    quads += custom_back_button_quads;
    custom_action_key_bg_quads = emit_circle_quad(
        action_key_x, key_y, key_radius, verts + quads * 24);
    quads += custom_action_key_bg_quads;
    if (custom_video_settings_popup) {
      const int apply_key_quads = emit_circle_quad(
          apply_key_x, key_y, key_radius, verts + quads * 24);
      custom_action_key_bg_quads += apply_key_quads;
      quads += apply_key_quads;
    }
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
    const char *title = custom_video_settings_popup ? "VIDEO SETTINGS"
                                                     : "MATCH SETTINGS";
    int line_quads = emit_line(
        title, (int)strlen(title),
        (float)screen_width * 0.5f -
            (float)strlen(title) * title_gw * 0.5f,
        panel_y + (header_h - title_gh) * 0.5f, title_gw, title_gh,
        verts + quads * 24);
    custom_dark_text_quads += line_quads;
    quads += line_quads;
    for (uint32_t item = 0; item < item_count; item++) {
      const char *label = custom_video_settings_popup
                              ? pes_controller_custom_video_settings_label(item)
                              : pes_controller_custom_match_settings_label(item);
      const float y = row_y0 + row_step * (float)item +
                      (row_h - text_gh) * 0.5f;
      line_quads = emit_line(
          label, (int)strlen(label), row_x + 0.020f * (float)screen_width,
          y, text_gw, text_gh, verts + quads * 24);
      custom_dark_text_quads += line_quads;
      quads += line_quads;
    }

    custom_white_text_first_quad = quads;
    for (uint32_t item = 0; item < item_count; item++) {
      const char *value = custom_video_settings_popup
                              ? pes_controller_custom_video_settings_value(item)
                              : pes_controller_custom_match_settings_value(item);
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
    if (custom_video_settings_popup) {
      line_quads = emit_line(
          "APPLY", 5, apply_key_x + 0.026f * (float)screen_width,
          action_button_y + (button_h - text_gh) * 0.5f, text_gw, text_gh,
          verts + quads * 24);
      custom_white_text_quads += line_quads;
      quads += line_quads;
    }
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
    if (custom_video_settings_popup) {
      line_quads = emit_line(
          "X", 1, apply_key_x - text_gw * 0.5f, key_y - text_gh * 0.5f,
          text_gw, text_gh, verts + quads * 24);
      custom_key_text_quads += line_quads;
      quads += line_quads;
    }
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
    const int pause_cursor =
        virtual_cursor_context == PES_VIRTUAL_CURSOR_PAUSE;
    const int gameplan_pause_route =
        virtual_cursor_context == PES_VIRTUAL_CURSOR_GAMEPLAN &&
        pes_controller_gameplan_pause_route();
    const int back_only_cursor =
        pause_cursor || gameplan_pause_route ||
        virtual_cursor_context == PES_VIRTUAL_CURSOR_SET_PIECE_TAKER;
    // Pause and its Game Plan child both use the native Back footer at the
    // bottom-left. Keep their B badge attached to that footer; only pre-match
    // Game Plan owns the bottom-right A/Play action.
    const float helper_x =
        (pause_cursor || gameplan_pause_route ? 0.055f : 0.835f) *
        (float)screen_width;
    const float helper_y = 0.944f * (float)screen_height;
    const float helper_radius = 0.019f * (float)screen_height;
    gameplan_helper_circle_first_quad = quads;
    gameplan_helper_circle_quads = emit_filled_circle(
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
        back_only_cursor ? "B" : "A", 1, helper_x - helper_gw * 0.5f,
        helper_y - helper_gh * 0.5f, helper_gw, helper_gh,
        verts + quads * 24);
    quads += gameplan_helper_text_quads;
  } else if (pause_camera_active) {
    // Camera selection uses the same compact helper style as Game Plan. The
    // native camera dots remain visible; B is the only action on this page.
    const float helper_x = 0.835f * (float)screen_width;
    const float helper_y = 0.944f * (float)screen_height;
    const float helper_radius = 0.019f * (float)screen_height;
    gameplan_helper_circle_first_quad = quads;
    gameplan_helper_circle_quads = emit_filled_circle(
        helper_x, helper_y, helper_radius, verts + quads * 24);
    quads += gameplan_helper_circle_quads;
    const float helper_gh = (float)screen_height / 43.0f;
    const float helper_gw =
        helper_gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
    gameplan_helper_text_first_quad = quads;
    gameplan_helper_text_quads = emit_line(
        "B", 1, helper_x - helper_gw * 0.5f,
        helper_y - helper_gh * 0.5f, helper_gw, helper_gh,
        verts + quads * 24);
    quads += gameplan_helper_text_quads;
  } else if (tutorial_play_active) {
    // The stock tutorial already draws the blue Play footer. Add only its
    // missing controller key; the action itself is dispatched natively on the
    // tutorial UI thread.
    const float helper_x = 0.835f * (float)screen_width;
    const float helper_y = 0.944f * (float)screen_height;
    const float helper_radius = 0.019f * (float)screen_height;
    gameplan_helper_circle_first_quad = quads;
    gameplan_helper_circle_quads = emit_filled_circle(
        helper_x, helper_y, helper_radius, verts + quads * 24);
    quads += gameplan_helper_circle_quads;
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
  if (native_lab && !custom_popup) {
    const uint32_t status = native_debug.status;
    char label[192];
    snprintf(label, sizeof(label),
             "NATIVE 2P SETPLAY V8.16.15 H:%X P:%X O:%X R:%X U:%X B:%X PR:%X "
             "RAW2:%04X AX2:%d,%d K2:%06X LP2:%u G:%X/%u/%u PN:%u/%u%s",
             native_debug.connected_mask & 3u,
             native_debug.native_sample_mask & 3u,
             native_debug.owner_mask & 3u,
             native_debug.route_player_mask & 3u,
             native_debug.input_unit_mask & 3u,
             native_debug.accessor_bind_mask & 3u,
             native_debug.prime_mask & 3u,
             native_debug.buttons_p2 & 0xffffu,
             native_debug.axis_x_p2,
             native_debug.axis_y_p2,
             native_debug.native_keys_p2 & 0x00ffffffu,
             native_debug.native_power_milli_p2,
             native_debug.gauge_active_mask & 3u,
             native_debug.gauge_power_milli,
             native_debug.gauge_power_milli_p2,
             penalty_role_p1,
             penalty_role_p2,
             status & 128 ? " ABI ERROR" : "");
    const float gh = (float)screen_height / 50.0f;
    const float gw = gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
    quads += emit_line(label, (int)strlen(label), 12.0f,
                       (float)screen_height * 0.95f, gw, gh, verts + quads * 24);
    if (native_setplay_debug) {
      char debug_line[192];
      const int debug_p2 = native_debug.setplay_pad == 1;
      const uint32_t debug_buttons = debug_p2
                                         ? native_debug.buttons_p2
                                         : native_debug.buttons;
      const uint32_t debug_keys = debug_p2
                                      ? native_debug.native_keys_p2
                                      : native_debug.native_keys;
      const uint32_t debug_power = debug_p2
                                       ? native_debug.native_power_milli_p2
                                       : native_debug.native_power_milli;
      const uint32_t debug_right_power =
          debug_p2 ? native_debug.native_right_power_milli_p2
                   : native_debug.native_right_power_milli;
      const uint32_t debug_event = debug_p2
                                       ? native_debug.last_event_p2
                                       : native_debug.last_event;
      const uint32_t debug_command = debug_p2
                                         ? native_debug.last_command_p2
                                         : native_debug.last_command;
      const int32_t debug_axis_x = debug_p2
                                       ? native_debug.axis_x_p2
                                       : native_debug.axis_x;
      const int32_t debug_axis_y = debug_p2
                                       ? native_debug.axis_y_p2
                                       : native_debug.axis_y;
      const int32_t debug_right_axis_x = debug_p2
                                             ? native_debug.right_axis_x_p2
                                             : native_debug.right_axis_x;
      const int32_t debug_right_axis_y = debug_p2
                                             ? native_debug.right_axis_y_p2
                                             : native_debug.right_axis_y;
      const float debug_gh = (float)screen_height / 53.0f;
      const float debug_gw =
          debug_gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
      const float debug_y = 0.690f * (float)screen_height;
      const float debug_step = 1.32f * debug_gh;
      snprintf(debug_line, sizeof(debug_line),
               "P%u %s NATIVE KICK + CAMERA PLUGIN",
               debug_p2 ? 2u : 1u,
               native_lab_setplay_name(native_debug.context));
      quads += emit_line(debug_line, (int)strlen(debug_line), 12.0f,
                         debug_y, debug_gw, debug_gh, verts + quads * 24);
      if (native_debug.context == PES_SETPLAY_FREE_KICK)
        snprintf(debug_line, sizeof(debug_line),
                 "LS=KICK AIM + HEIGHT   RS=CAMERA (BALL ANCHOR)");
      else if (native_debug.context == PES_SETPLAY_THROW_IN)
        snprintf(debug_line, sizeof(debug_line), "LS=THROW DIRECTION/AIM");
      else
        snprintf(debug_line, sizeof(debug_line),
                 "LS=KICK AIM   RS=CAMERA (BALL ANCHOR)");
      quads += emit_line(debug_line, (int)strlen(debug_line), 12.0f,
                         debug_y + debug_step, debug_gw, debug_gh,
                         verts + quads * 24);
      if (native_debug.context == PES_SETPLAY_FREE_KICK)
        snprintf(debug_line, sizeof(debug_line),
                 "B=PASS   A=LOB/CROSS   Y=SHOOT   %s=KICKER",
                 single_joy_setplay ? "L1+R1" : "RIGHT");
      else if (native_debug.context == PES_SETPLAY_CORNER)
        snprintf(debug_line, sizeof(debug_line),
                 "B=SHORT PASS   A=LONG KICK   L=SHORT CORNER   %s=KICKER",
                 single_joy_setplay ? "L1+R1" : "RIGHT");
      else if (native_debug.context == PES_SETPLAY_THROW_IN)
        snprintf(debug_line, sizeof(debug_line),
                 "B=NORMAL THROW   Y=LONG THROW   %s=THROWER",
                 single_joy_setplay ? "L1+R1" : "RIGHT");
      else
        snprintf(debug_line, sizeof(debug_line),
                 "B=SHORT PASS   A=LONG KICK   L=POSITION SHIFT");
      quads += emit_line(debug_line, (int)strlen(debug_line), 12.0f,
                         debug_y + 2.0f * debug_step, debug_gw, debug_gh,
                         verts + quads * 24);
      snprintf(debug_line, sizeof(debug_line),
               "LIVE B:%u A:%u Y:%u X:%u L:%u  LS:%d,%d  RS:%d,%d",
               (debug_buttons >> 0) & 1u,
               (debug_buttons >> 1) & 1u,
               (debug_buttons >> 2) & 1u,
               (debug_buttons >> 3) & 1u,
               (debug_buttons >> 4) & 1u, debug_axis_x,
               debug_axis_y, debug_right_axis_x,
               debug_right_axis_y);
      quads += emit_line(debug_line, (int)strlen(debug_line), 12.0f,
                         debug_y + 3.0f * debug_step, debug_gw, debug_gh,
                         verts + quads * 24);
      snprintf(debug_line, sizeof(debug_line),
               "PADKEY:%06X  LPOW:%u  RPOW:%u",
               debug_keys & 0x00ffffffu,
               debug_power, debug_right_power);
      quads += emit_line(debug_line, (int)strlen(debug_line), 12.0f,
                         debug_y + 4.0f * debug_step, debug_gw, debug_gh,
                         verts + quads * 24);
      snprintf(debug_line, sizeof(debug_line),
               "LAST:%s CMD:%02X  STOCK:%02X ROUTED:%03X CONNECTED:%u",
               native_lab_event_name(debug_event),
               debug_command & 0xffu,
               native_debug.stock_mask & 0xffu,
               native_debug.route_mask & 0xfffu,
               native_debug.connected_mask & 3u);
      quads += emit_line(debug_line, (int)strlen(debug_line), 12.0f,
                         debug_y + 5.0f * debug_step, debug_gw, debug_gh,
                         verts + quads * 24);
    }
  }
  int prompt_label_quads = 0;
  if (start_prompt) {
    const float gh = (float)screen_height / 22.0f;
    const char *prompt_label = "PRESS A TO START";
    const int prompt_len = (int)strlen(prompt_label);
    const float label_gh = (float)screen_height / 38.0f;
    const float label_gw =
        label_gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
    const float label_x = prompt_x * (float)screen_width -
                          (float)prompt_len * label_gw * 0.5f;
    // Leave a clear gap below the native pulse instead of touching its rim.
    const float label_y = prompt_y * (float)screen_height + gh * 1.55f;
    prompt_label_quads = emit_line(prompt_label, prompt_len, label_x, label_y,
                                   label_gw, label_gh, verts + quads * 24);
    quads += prompt_label_quads;
  }
  if (config.show_fps && fps.text[0]) {
    const float gh = (float)screen_height / 30.0f;
    const float gw = gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
    quads += emit_line(fps.text, (int)strlen(fps.text), 10.0f, 8.0f,
                       gw, gh, verts + quads * 24);
  }
  if (cinematic_helper_active) {
    const float helper_radius = 0.022f * (float)screen_height;
    const float helper_x = 0.825f * (float)screen_width;
    const float skip_y = 0.865f * (float)screen_height;
    const float celebrate_y = 0.945f * (float)screen_height;
    cinematic_helper_circle_first_quad = quads;
    cinematic_helper_circle_quads = emit_filled_circle(
        helper_x, cinematic_goal_actions ? skip_y : 0.925f *
        (float)screen_height, helper_radius, verts + quads * 24);
    quads += cinematic_helper_circle_quads;
    if (cinematic_goal_actions) {
      const int celebrate_circle_quads = emit_filled_circle(
          helper_x, celebrate_y, helper_radius, verts + quads * 24);
      cinematic_helper_circle_quads += celebrate_circle_quads;
      quads += celebrate_circle_quads;
    }

    const float gh = (float)screen_height / 43.0f;
    const float gw = gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
    cinematic_helper_text_first_quad = quads;
    const float generic_y = 0.925f * (float)screen_height;
    const int key_quads = emit_line(
        (cinematic_goal_actions || cinematic_goal_skip_only) ? "B" : "A", 1,
        helper_x - gw * 0.5f,
        (cinematic_goal_actions ? skip_y : generic_y) - gh * 0.5f, gw, gh,
        verts + quads * 24);
    cinematic_helper_text_quads += key_quads;
    quads += key_quads;
    const float label_x = helper_x + helper_radius * 1.55f;
    const int skip_label_quads = emit_line(
        (cinematic_goal_actions || cinematic_goal_skip_only)
            ? "SKIP"
            : "ANY BUTTON - SKIP",
        (cinematic_goal_actions || cinematic_goal_skip_only) ? 4 : 17,
        label_x,
        (cinematic_goal_actions ? skip_y : generic_y) - gh * 0.5f,
        gw * 0.78f, gh,
        verts + quads * 24);
    cinematic_helper_text_quads += skip_label_quads;
    quads += skip_label_quads;
    if (cinematic_goal_actions) {
      const int celebrate_key_quads = emit_line(
          "A", 1, helper_x - gw * 0.5f, celebrate_y - gh * 0.5f, gw, gh,
          verts + quads * 24);
      cinematic_helper_text_quads += celebrate_key_quads;
      quads += celebrate_key_quads;
      const int celebrate_label_quads = emit_line(
          "CELEBRATE", 9, label_x, celebrate_y - gh * 0.5f, gw * 0.78f, gh,
          verts + quads * 24);
      cinematic_helper_text_quads += celebrate_label_quads;
      quads += celebrate_label_quads;
    }
  }
  const char *setplay_keys[5] = {NULL, NULL, NULL, NULL, NULL};
  const char *setplay_labels[5] = {NULL, NULL, NULL, NULL, NULL};
  unsigned int setplay_helper_count = 0;
  const int native_far_free_kick =
      native_setplay_debug && setplay_context == PES_SETPLAY_FREE_KICK &&
      (native_debug.stock_mask &
       (PES_NATIVE_LAB_STOCK_FREEKICK_TACTICS |
        PES_NATIVE_LAB_STOCK_FREEKICK_POSITION));
  if (native_setplay_debug &&
      setplay_context == PES_SETPLAY_GOAL_KICK) {
    setplay_keys[0] = "L";
    setplay_labels[0] = "POSITION SHIFT";
    setplay_keys[1] = "LS";
    setplay_labels[1] = "KICK AIM";
    setplay_keys[2] = "RS";
    setplay_labels[2] = "CAMERA";
    setplay_keys[3] = "R";
    setplay_labels[3] = native_debug.trajectory_enabled
                            ? "TRAJECTORY ON"
                            : "TRAJECTORY OFF";
    setplay_helper_count = 4;
  } else if (native_setplay_debug &&
             setplay_context == PES_SETPLAY_CORNER) {
    setplay_keys[0] = "L";
    setplay_labels[0] = "SHORT CORNER";
    setplay_keys[1] = setplay_taker_key;
    setplay_labels[1] = "SET PIECE TAKER";
    setplay_keys[2] = "LS";
    setplay_labels[2] = "KICK AIM";
    setplay_keys[3] = "RS";
    setplay_labels[3] = "CAMERA";
    setplay_keys[4] = "R";
    setplay_labels[4] = native_debug.trajectory_enabled
                            ? "TRAJECTORY ON"
                            : "TRAJECTORY OFF";
    setplay_helper_count = 5;
  } else if (native_far_free_kick) {
    // Far free kicks retain the stock overhead camera, but taker selection is
    // still our native-controller action rather than the old ZR touch legend.
    setplay_keys[0] = setplay_taker_key;
    setplay_labels[0] = "SET PIECE TAKER";
    setplay_helper_count = 1;
  } else if (native_setplay_debug &&
             setplay_context == PES_SETPLAY_FREE_KICK) {
    setplay_keys[0] = setplay_taker_key;
    setplay_labels[0] = "SET PIECE TAKER";
    setplay_keys[1] = "LS";
    setplay_labels[1] = "KICK AIM + HEIGHT";
    setplay_keys[2] = "RS";
    setplay_labels[2] = "CAMERA";
    setplay_keys[3] = "R";
    setplay_labels[3] = native_debug.trajectory_enabled
                            ? "TRAJECTORY ON"
                            : "TRAJECTORY OFF";
    setplay_helper_count = 4;
  } else if (native_setplay_debug &&
             setplay_context == PES_SETPLAY_THROW_IN) {
    setplay_keys[0] = setplay_taker_key;
    setplay_labels[0] = "SET THROWER";
    setplay_helper_count = 1;
  } else if (!native_setplay_debug && !native_lab &&
      setplay_context == PES_SETPLAY_GOAL_KICK) {
    setplay_keys[0] = "Y";
    setplay_labels[0] = "POSITION SHIFT";
    setplay_keys[1] = "X";
    setplay_labels[1] = "SWITCH VIEW";
    setplay_helper_count = 2;
  } else if (!native_setplay_debug && !native_lab &&
             setplay_context == PES_SETPLAY_CORNER) {
    setplay_keys[0] = "ZR";
    setplay_labels[0] = "SET PIECE TAKER";
    setplay_keys[1] = "X";
    setplay_labels[1] = "SHORT CORNER";
    setplay_keys[2] = "Y";
    setplay_labels[2] = "SWITCH VIEW";
    setplay_helper_count = 3;
  } else if (!native_setplay_debug && !native_lab &&
             setplay_context == PES_SETPLAY_FREE_KICK) {
    setplay_keys[0] = "ZR";
    setplay_labels[0] = "SET PIECE TAKER";
    setplay_keys[1] = "X";
    setplay_labels[1] = "SWITCH VIEW";
    setplay_helper_count = 2;
  } else if (setplay_context == PES_SETPLAY_THROW_IN) {
    setplay_keys[0] = setplay_taker_key;
    setplay_labels[0] = "SET THROWER";
    setplay_helper_count = 1;
  } else if (setplay_options) {
    // Native option bits are retained as a fallback for short transition
    // frames before the semantic set-piece context has settled.
    if ((setplay_options & PES_SETPLAY_OPTION_KICKER) &&
        setplay_helper_count < 3) {
      setplay_keys[setplay_helper_count] =
          single_joy_setplay ? "L1+R1" : "ZR";
      setplay_labels[setplay_helper_count++] = "SET PIECE TAKER";
    }
    if ((setplay_options & PES_SETPLAY_OPTION_TEAM_UP) &&
        setplay_helper_count < 3) {
      setplay_keys[setplay_helper_count] =
          (setplay_options & PES_SETPLAY_OPTION_KICKER) ? "X" : "Y";
      setplay_labels[setplay_helper_count++] = "POSITION SHIFT";
    }
    if ((setplay_options & PES_SETPLAY_OPTION_SHORT_CORNER) &&
        setplay_helper_count < 3) {
      setplay_keys[setplay_helper_count] = "X";
      setplay_labels[setplay_helper_count++] = "SHORT CORNER";
    }
    if ((setplay_options & PES_SETPLAY_OPTION_CAMERA) &&
        setplay_helper_count < 3) {
      setplay_keys[setplay_helper_count] =
          (setplay_options & PES_SETPLAY_OPTION_KICKER) ? "Y" : "X";
      setplay_labels[setplay_helper_count++] = "SWITCH VIEW";
    }
  }
  const int penalty_helper_active =
      (penalty_role_p1 != PES_PENALTY_NONE ||
       penalty_role_p2 != PES_PENALTY_NONE) &&
      !set_piece_selector && !tutorial_play_active &&
      !cinematic_helper_active &&
      controller_snapshot.surface != PES_CONTROLLER_SURFACE_REPLAY &&
      controller_snapshot.surface != PES_CONTROLLER_SURFACE_CINEMATIC;
  if (!setplay_helper_count && penalty_helper_active) {
    // A foul penalty keeps ButtonSetplay's native taker action alive.  A
    // shootout/imbalance penalty has no taker selector, so do not expose a
    // dead Right action there. Penalties have no trajectory preview.
    const int penalty_foul_mode =
        controller_snapshot.surface == PES_CONTROLLER_SURFACE_SETPLAY &&
        (controller_snapshot.setplay_button_mask &
         (1u << PES_SETPLAY_BUTTON_SET_PIECE_TAKER));
    if (penalty_foul_mode && setplay_helper_count < 5) {
      const uint32_t penalty_owner_pad =
          penalty_role_p1 == PES_PENALTY_KICKER ? 0u : 1u;
      const int penalty_single_joy =
          android_controller_profile(penalty_owner_pad) !=
          PES_CONTROLLER_PROFILE_FULL;
      setplay_keys[setplay_helper_count] =
          penalty_single_joy ? "L1+R1" : ">";
      setplay_labels[setplay_helper_count++] = "SET PENALTY TAKER";
    }
    if (penalty_role_p1 == PES_PENALTY_KICKER) {
      setplay_keys[setplay_helper_count] = "Y";
      setplay_labels[setplay_helper_count++] = "P1 KICKER (LS + Y)";
    } else if (penalty_role_p1 == PES_PENALTY_GOALKEEPER) {
      setplay_keys[setplay_helper_count] = "LS";
      setplay_labels[setplay_helper_count++] = "P1 GOALKEEPER (LS)";
    }
    if (penalty_two_player && penalty_role_p2 == PES_PENALTY_KICKER) {
      setplay_keys[setplay_helper_count] = "Y";
      setplay_labels[setplay_helper_count++] = "P2 KICKER (LS + Y)";
    } else if (penalty_two_player &&
               penalty_role_p2 == PES_PENALTY_GOALKEEPER) {
      setplay_keys[setplay_helper_count] = "LS";
      setplay_labels[setplay_helper_count++] = "P2 GOALKEEPER (LS)";
    }
  }
  // Keep these badges outside the generic white-text batch below. That pass
  // used to repaint both the colored key glyphs and their circle geometry.
  const int generic_text_end_quad = quads;
  if (setplay_helper_count) {
    const float helper_radius = 0.021f * (float)screen_height;
    const float helper_x = 0.815f * (float)screen_width;
    const float helper_step = 0.066f * (float)screen_height;
    const float helper_start_y =
        (setplay_helper_count == 5 ? 0.660f
         : setplay_helper_count == 4 ? 0.725f
         : setplay_helper_count == 3 ? 0.790f
         : setplay_helper_count == 2 ? 0.855f
                                     : 0.925f) *
        (float)screen_height;
    int setplay_has_chord = 0;
    for (unsigned int index = 0; index < setplay_helper_count; index++) {
      if (strcmp(setplay_keys[index], "L1+R1") == 0) {
        setplay_has_chord = 1;
        break;
      }
    }
    const float chord_second_x = helper_x + helper_radius * 2.85f;
    const float chord_plus_x = helper_x + helper_radius * 1.425f;
    const float helper_label_x =
        helper_x + helper_radius * (setplay_has_chord ? 4.25f : 1.55f);
    setplay_helper_circle_first_quad = quads;
    for (unsigned int index = 0; index < setplay_helper_count; index++) {
      int circle_quads = emit_filled_circle(
          helper_x, helper_start_y + (float)index * helper_step,
          helper_radius, verts + quads * 24);
      setplay_helper_circle_quads += circle_quads;
      quads += circle_quads;
      if (strcmp(setplay_keys[index], "L1+R1") == 0) {
        circle_quads = emit_filled_circle(
            chord_second_x,
            helper_start_y + (float)index * helper_step,
            helper_radius, verts + quads * 24);
        setplay_helper_circle_quads += circle_quads;
        quads += circle_quads;
      }
    }

    // The font atlas does not contain the Switch D-pad Right glyph. Draw its
    // actual right-pointing triangular cap as geometry inside the blue badge.
    setplay_helper_icon_first_quad = quads;
    for (unsigned int index = 0; index < setplay_helper_count; index++) {
      if (strcmp(setplay_keys[index], ">") != 0)
        continue;
      const float y = helper_start_y + (float)index * helper_step;
      const float half_w = helper_radius * 0.34f;
      const float half_h = helper_radius * 0.46f;
      setplay_helper_icon_quads += emit_triangle(
          helper_x - half_w, y - half_h,
          helper_x + half_w, y,
          helper_x - half_w, y + half_h,
          verts + quads * 24);
      quads++;
    }

    const float gh = (float)screen_height / 43.0f;
    const float gw = gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
    setplay_helper_text_first_quad = quads;
    for (unsigned int index = 0; index < setplay_helper_count; index++) {
      const float y = helper_start_y + (float)index * helper_step;
      const int key_len = (int)strlen(setplay_keys[index]);
      setplay_key_first_quads[index] = quads;
      int line_quads = 0;
      if (strcmp(setplay_keys[index], "L1+R1") == 0) {
        const float chord_gw = gw * 0.82f;
        line_quads += emit_line(
            "R1", 2, helper_x - chord_gw,
            y - gh * 0.5f, chord_gw, gh,
            verts + quads * 24);
        quads += line_quads;
        int part_quads = emit_line(
            "+", 1, chord_plus_x - gw * 0.5f,
            y - gh * 0.5f, gw, gh,
            verts + quads * 24);
        line_quads += part_quads;
        quads += part_quads;
        part_quads = emit_line(
            "L1", 2, chord_second_x - chord_gw,
            y - gh * 0.5f, chord_gw, gh,
            verts + quads * 24);
        line_quads += part_quads;
        quads += part_quads;
      } else if (strcmp(setplay_keys[index], ">") != 0) {
        line_quads = emit_line(
            setplay_keys[index], key_len,
            helper_x - (float)key_len *
                           (key_len > 2 ? gw * 0.58f : gw) * 0.5f,
            y - gh * 0.5f, key_len > 2 ? gw * 0.58f : gw, gh,
            verts + quads * 24);
        quads += line_quads;
      }
      setplay_key_quads[index] = line_quads;
      setplay_helper_text_quads += line_quads;
      const int label_len = (int)strlen(setplay_labels[index]);
      line_quads = emit_line(
          setplay_labels[index], label_len, helper_label_x,
          y - gh * 0.5f, gw * 0.72f, gh, verts + quads * 24);
      setplay_helper_text_quads += line_quads;
      quads += line_quads;
    }
  }
  if (native_lab && !custom_popup && (native_debug.gauge_active_mask & 3u)) {
    // Each local pad has an independent visual-only bar. Keeping both states
    // in the snapshot avoids the stock Screen2d PlayerNo/global gauge path,
    // which is why P2 previously appeared on P1's cursor.
    const int segment_count = 12;
    const float bar_w = 0.075f * (float)screen_width;
    const float bar_h = 0.0060f * (float)screen_height;
    const float padding = 0.0045f * (float)screen_height;
    // Adjacent colored quads share their edge exactly, producing one connected
    // spectrum bar while retaining the existing green-to-orange color ramp.
    const float gap = 0.0f;
    const float segment_w =
        (bar_w - gap * (float)(segment_count - 1)) /
        (float)segment_count;
    for (int pad = 0; pad < 2; pad++) {
      if (!(native_debug.gauge_active_mask & (1u << pad)))
        continue;
      const int anchor_valid =
          (native_debug.gauge_anchor_valid_mask & (1u << pad)) != 0;
      // Never render this as a fixed HUD widget. If the engine has not yet
      // published the controlled player's CursorName projection, wait for it.
      if (!anchor_valid)
        continue;
      const int32_t anchor_x_milli =
          pad == 0 ? native_debug.gauge_anchor_x_milli
                   : native_debug.gauge_anchor_x_milli_p2;
      const int32_t anchor_y_milli =
          pad == 0 ? native_debug.gauge_anchor_y_milli
                   : native_debug.gauge_anchor_y_milli_p2;
      float bar_x;
      float bar_y;
      // Projected point is the controlled player's foot position. Center the
      // compact bar there and move it a few pixels down, matching the reference
      // without touching the engine's player/cursor data.
      bar_x = (float)anchor_x_milli / 1000.0f - bar_w * 0.5f;
      bar_y = (float)anchor_y_milli / 1000.0f +
              0.007f * (float)screen_height;
      if (bar_x < padding)
        bar_x = padding;
      if (bar_x + bar_w + padding > (float)screen_width)
        bar_x = (float)screen_width - bar_w - padding;
      if (bar_y < padding)
        bar_y = padding;
      if (bar_y + bar_h + padding > (float)screen_height)
        bar_y = (float)screen_height - bar_h - padding;
      power_gauge_background_first_quad[pad] = quads;
      power_gauge_background_quads[pad] = emit_rect(
          bar_x, bar_y, bar_w, bar_h,
          verts + quads * 24);
      quads += power_gauge_background_quads[pad];
      power_gauge_segment_first_quad[pad] = quads;
      for (int index = 0; index < segment_count; index++) {
        power_gauge_segment_quads[pad] += emit_rect(
            bar_x + (segment_w + gap) * (float)index, bar_y,
            segment_w, bar_h, verts + quads * 24);
        quads++;
      }
      uint32_t power_milli =
          pad == 0 ? native_debug.gauge_power_milli
                    : native_debug.gauge_power_milli_p2;
      if (power_milli > 1000u)
        power_milli = 1000u;
      power_gauge_active_segments[pad] =
          (int)((power_milli * (uint32_t)segment_count + 999u) / 1000u);
    }
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
    glUniform1f(gl.loc_solid, 1.0f);
    glUniform1f(gl.loc_image, 0.0f);
    glUniform1f(gl.loc_round_rect, 0.0f);
    glUniform1f(gl.loc_cursor, 0.0f);
    glUniform1f(gl.loc_circle, 0.0f);
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
  if (setplay_helper_circle_quads) {
    glUniform1f(gl.loc_solid, 1.0f);
    glUniform1f(gl.loc_image, 0.0f);
    glUniform1f(gl.loc_round_rect, 0.0f);
    glUniform1f(gl.loc_cursor, 0.0f);
    glUniform1f(gl.loc_circle, 0.0f);
    glUniform4f(gl.loc_color, 0.0f, 0.0f, 0.32f, 1.0f);
    glDrawArrays(GL_TRIANGLES, setplay_helper_circle_first_quad * 6,
                 setplay_helper_circle_quads * 6);
    glUniform1f(gl.loc_circle, 0.0f);
  }
  if (setplay_helper_icon_quads) {
    glUniform1f(gl.loc_solid, 1.0f);
    glUniform1f(gl.loc_image, 0.0f);
    glUniform1f(gl.loc_round_rect, 0.0f);
    glUniform1f(gl.loc_cursor, 0.0f);
    glUniform1f(gl.loc_circle, 0.0f);
    glUniform4f(gl.loc_color, 1.0f, 0.94f, 0.0f, 1.0f);
    glDrawArrays(GL_TRIANGLES, setplay_helper_icon_first_quad * 6,
                 setplay_helper_icon_quads * 6);
  }
  for (int pad = 0; pad < 2; pad++) {
    if (!power_gauge_background_quads[pad])
      continue;
    glUniform1f(gl.loc_solid, 1.0f);
    glUniform1f(gl.loc_image, 0.0f);
    glUniform1f(gl.loc_round_rect, 0.0f);
    glUniform1f(gl.loc_cursor, 0.0f);
    glUniform1f(gl.loc_circle, 0.0f);
    glUniform4f(gl.loc_color, 0.005f, 0.015f, 0.035f, 0.82f);
    glDrawArrays(GL_TRIANGLES, power_gauge_background_first_quad[pad] * 6,
                 power_gauge_background_quads[pad] * 6);
    glUniform4f(gl.loc_color, 0.12f, 0.17f, 0.19f, 0.78f);
    glDrawArrays(GL_TRIANGLES, power_gauge_segment_first_quad[pad] * 6,
                 power_gauge_segment_quads[pad] * 6);
    for (int index = 0; index < power_gauge_active_segments[pad]; index++) {
      const float t = (float)index / 11.0f;
      glUniform4f(gl.loc_color,
                  0.12f + 0.88f * t,
                  0.88f - 0.38f * t,
                  0.28f - 0.20f * t, 1.0f);
      glDrawArrays(GL_TRIANGLES,
                   (power_gauge_segment_first_quad[pad] + index) * 6, 6);
    }
  }
  if (cinematic_helper_circle_quads) {
    glUniform1f(gl.loc_solid, 1.0f);
    glUniform1f(gl.loc_image, 0.0f);
    glUniform1f(gl.loc_round_rect, 0.0f);
    glUniform1f(gl.loc_cursor, 0.0f);
    glUniform1f(gl.loc_circle, 0.0f);
    glUniform4f(gl.loc_color, 0.98f, 0.99f, 1.0f, 1.0f);
    glDrawArrays(GL_TRIANGLES, cinematic_helper_circle_first_quad * 6,
                 cinematic_helper_circle_quads * 6);
    glUniform1f(gl.loc_circle, 0.0f);
  }
  if (cinematic_helper_text_quads) {
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform2f(gl.loc_off, 0.0f, 0.0f);
    glUniform4f(gl.loc_color, 0.02f, 0.36f, 0.62f, 1.0f);
    glDrawArrays(GL_TRIANGLES, cinematic_helper_text_first_quad * 6,
                 cinematic_helper_text_quads * 6);
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
  const int text_quads = generic_text_end_quad - text_first_quad;
  if (text_quads) {
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform2f(gl.loc_off, 3.0f / (float)screen_width,
                -3.0f / (float)screen_height);
    glUniform4f(gl.loc_color, 0.0f, 0.0f, 0.0f, 0.9f);
    glDrawArrays(GL_TRIANGLES, text_first_quad * 6, text_quads * 6);
    glUniform2f(gl.loc_off, 0.0f, 0.0f);
    glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, 1.0f);
    glDrawArrays(GL_TRIANGLES, text_first_quad * 6, text_quads * 6);
  }

  if (setplay_helper_text_quads) {
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform2f(gl.loc_off, 2.0f / (float)screen_width,
                -2.0f / (float)screen_height);
    glUniform4f(gl.loc_color, 0.0f, 0.0f, 0.0f, 0.85f);
    glDrawArrays(GL_TRIANGLES, setplay_helper_text_first_quad * 6,
                 setplay_helper_text_quads * 6);
    glUniform2f(gl.loc_off, 0.0f, 0.0f);
    glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, 1.0f);
    glDrawArrays(GL_TRIANGLES, setplay_helper_text_first_quad * 6,
                 setplay_helper_text_quads * 6);
    // Same high-contrast palette as the accepted scoreboard; labels stay white.
    glUniform4f(gl.loc_color, 1.0f, 0.94f, 0.0f, 1.0f);
    for (unsigned int i = 0; i < setplay_helper_count; i++)
      glDrawArrays(GL_TRIANGLES, setplay_key_first_quads[i] * 6,
                   setplay_key_quads[i] * 6);
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
