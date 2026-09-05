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
#include <png.h>
#include <stdlib.h>
#include <string.h>
#include <switch.h>

#include <EGL/egl.h>
#include <GLES2/gl2.h>

#include "config.h"
#include "android_shim.h"
#include "overlay.h"
#include "badge_atlas.h"
#include "efootball_font_atlas.h"
#include "font_atlas.h"
#include "team_rating_star.h"
#include "team_select_background.h"
#include "ue4_hooks.h"

#ifndef GL_SAMPLER_BINDING
#define GL_SAMPLER_BINDING 0x8919
#endif

typedef void (*OverlayBindSamplerProc)(GLuint unit, GLuint sampler);

// text-overlay GL objects, created lazily on first draw
static struct {
  int ready;
  GLuint prog;
  GLuint tex;
  GLuint efootball_tex;
  GLuint badge_tex;
  GLuint team_rating_star_tex;
  GLuint team_select_bg_tex;
  GLuint native_uniform_texture[2];
  GLuint vbo;
  GLint loc_pos, loc_uv, loc_tex, loc_off, loc_color, loc_solid, loc_image;
  GLint loc_image_curve;
  GLint loc_circle, loc_circle_feather;
  GLint loc_round_rect, loc_round_size, loc_round_radius, loc_round_feather;
  GLint loc_cursor, loc_cursor_border;
  OverlayBindSamplerProc bind_sampler;
  int native_uniform_width;
  int native_uniform_height;
  int native_uniform_valid;
  uint32_t native_uniform_valid_mask;
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
  "uniform float uImageCurve;\n"
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
  "  else if (uImage > 0.5) {\n"
  "    vec3 imageColor = sampled.rgb;\n"
  "    float imageAlpha = sampled.a;\n"
  "    if (uImageCurve > 0.5) {\n"
  "      imageColor = pow(max(imageColor, vec3(0.0)), vec3(1.0 / 2.2));\n"
  "      imageAlpha = 1.0;\n"
  "    }\n"
  "    gl_FragColor = vec4(imageColor, imageAlpha * uColor.a);\n"
  "  }\n"
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
  gl.loc_image_curve = glGetUniformLocation(gl.prog, "uImageCurve");
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
  glGenTextures(1, &gl.efootball_tex);
  glGenTextures(1, &gl.badge_tex);
  glGenTextures(1, &gl.team_rating_star_tex);
  glGenTextures(1, &gl.team_select_bg_tex);
  glGenBuffers(1, &gl.vbo);
  gl.bind_sampler =
      (OverlayBindSamplerProc)eglGetProcAddress("glBindSampler");
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
  glBindTexture(GL_TEXTURE_2D, gl.efootball_tex);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
  glTexImage2D(GL_TEXTURE_2D, 0, GL_LUMINANCE, EFOOTBALL_FONT_ATLAS_W,
               EFOOTBALL_FONT_ATLAS_H, 0, GL_LUMINANCE, GL_UNSIGNED_BYTE,
               efootball_font_atlas_alpha);
  glGenerateMipmap(GL_TEXTURE_2D);
  glBindTexture(GL_TEXTURE_2D, gl.badge_tex);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
  glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, BADGE_ATLAS_W, BADGE_ATLAS_H, 0,
               GL_RGBA, GL_UNSIGNED_BYTE, badge_atlas_rgba8);
  glGenerateMipmap(GL_TEXTURE_2D);
  glBindTexture(GL_TEXTURE_2D, gl.team_rating_star_tex);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER,
                  GL_LINEAR_MIPMAP_LINEAR);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
  glTexImage2D(GL_TEXTURE_2D, 0, GL_LUMINANCE, TEAM_RATING_STAR_W,
               TEAM_RATING_STAR_H, 0, GL_LUMINANCE, GL_UNSIGNED_BYTE,
               team_rating_star_luminance);
  glGenerateMipmap(GL_TEXTURE_2D);
  glBindTexture(GL_TEXTURE_2D, gl.team_select_bg_tex);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
  glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, TEAM_SELECT_BG_W,
               TEAM_SELECT_BG_H, 0, GL_RGB, GL_UNSIGNED_SHORT_5_6_5,
               team_select_background_rgb565);
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

static float measure_efootball_line(const char *text, int len, float gh,
                                    uint32_t weight) {
  if (weight >= EFOOTBALL_FONT_WEIGHTS)
    weight = EFOOTBALL_FONT_REGULAR;
  float width = 0.0f;
  for (int index = 0; index < len; index++) {
    if (text[index] == ' ') {
      width += gh * 0.34f;
      continue;
    }
    const int glyph = efootball_font_glyph_index(text[index]);
    if (glyph < 0)
      continue;
    width += (float)efootball_font_advance[weight][glyph] * gh /
             (float)EFOOTBALL_FONT_CELL_H;
  }
  return width;
}

static int emit_efootball_line(const char *text, int len, float x, float y,
                               float gh, uint32_t weight, GLfloat *verts) {
  if (weight >= EFOOTBALL_FONT_WEIGHTS)
    weight = EFOOTBALL_FONT_REGULAR;
  const float gw = gh * (float)EFOOTBALL_FONT_CELL_W /
                   (float)EFOOTBALL_FONT_CELL_H;
  float pen_x = x;
  int quads = 0;
  for (int index = 0; index < len; index++) {
    const char c = text[index];
    if (c == ' ') {
      pen_x += gh * 0.34f;
      continue;
    }
    const int glyph = efootball_font_glyph_index(c);
    if (glyph < 0)
      continue;
    const float u0 =
        ((float)(glyph * EFOOTBALL_FONT_CELL_W) + 0.5f) /
        (float)EFOOTBALL_FONT_ATLAS_W;
    const float u1 =
        ((float)((glyph + 1) * EFOOTBALL_FONT_CELL_W) - 0.5f) /
        (float)EFOOTBALL_FONT_ATLAS_W;
    const float v0 =
        ((float)(weight * EFOOTBALL_FONT_CELL_H) + 0.5f) /
        (float)EFOOTBALL_FONT_ATLAS_H;
    const float v1 =
        ((float)((weight + 1u) * EFOOTBALL_FONT_CELL_H) - 0.5f) /
        (float)EFOOTBALL_FONT_ATLAS_H;
    const float px0 = pen_x * 2.0f / (float)screen_width - 1.0f;
    const float px1 = (pen_x + gw) * 2.0f / (float)screen_width - 1.0f;
    const float py0 = 1.0f - y * 2.0f / (float)screen_height;
    const float py1 = 1.0f - (y + gh) * 2.0f / (float)screen_height;
    const GLfloat quad[24] = {
        px0, py0, u0, v0, px1, py0, u1, v0, px0, py1, u0, v1,
        px1, py0, u1, v0, px1, py1, u1, v1, px0, py1, u0, v1,
    };
    memcpy(verts + quads * 24, quad, sizeof(quad));
    quads++;
    pen_x += (float)efootball_font_advance[weight][glyph] * gh /
             (float)EFOOTBALL_FONT_CELL_H;
  }
  return quads;
}

static uint32_t selector_position_color_band(const char *position) {
  if (strcmp(position, "GK") == 0)
    return 0u;
  if (strcmp(position, "CB") == 0 || strcmp(position, "LB") == 0 ||
      strcmp(position, "RB") == 0)
    return 1u;
  if (strcmp(position, "DMF") == 0 || strcmp(position, "CMF") == 0 ||
      strcmp(position, "LMF") == 0 || strcmp(position, "RMF") == 0 ||
      strcmp(position, "AMF") == 0)
    return 2u;
  return 3u;
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

// Solid rectangles intentionally pin every UV to the atlas origin. A
// full-screen image needs its own quad so the complete texture is sampled
// instead of stretching the top-left pixel across the screen.
static int emit_image_rect_uv(float x, float y, float width, float height,
                              float u0, float v0, float u1, float v1,
                              GLfloat *verts) {
  const float x0 = x * 2.0f / (float)screen_width - 1.0f;
  const float x1 = (x + width) * 2.0f / (float)screen_width - 1.0f;
  const float y0 = 1.0f - y * 2.0f / (float)screen_height;
  const float y1 = 1.0f - (y + height) * 2.0f / (float)screen_height;
  const GLfloat quad[24] = {
      x0, y0, u0, v0, x1, y0, u1, v0,
      x0, y1, u0, v1, x1, y0, u1, v0,
      x1, y1, u1, v1, x0, y1, u0, v1,
  };
  memcpy(verts, quad, sizeof(quad));
  return 1;
}

static int emit_image_rect(float x, float y, float width, float height,
                           GLfloat *verts) {
  return emit_image_rect_uv(x, y, width, height, 0.0f, 0.0f, 1.0f, 1.0f,
                            verts);
}

static int native_uniform_background_pixel(const unsigned char *rgba) {
  const unsigned char min_rgb =
      rgba[0] < rgba[1]
          ? (rgba[0] < rgba[2] ? rgba[0] : rgba[2])
          : (rgba[1] < rgba[2] ? rgba[1] : rgba[2]);
  const unsigned char max_rgb =
      rgba[0] > rgba[1]
          ? (rgba[0] > rgba[2] ? rgba[0] : rgba[2])
          : (rgba[1] > rgba[2] ? rgba[1] : rgba[2]);
  return rgba[3] && min_rgb >= 232u &&
         (unsigned int)max_rgb - (unsigned int)min_rgb <= 20u;
}

static void native_uniform_remove_enclosed_background(
    unsigned char *pixels, GLint width, GLint height, size_t *queue) {
  if (!pixels || !queue || width <= 2 || height <= 2)
    return;

  const size_t pixel_count = (size_t)width * (size_t)height;
  for (GLint y = 1; y + 1 < height; y++) {
    for (GLint x = 1; x + 1 < width; x++) {
      const size_t first = (size_t)y * (size_t)width + (size_t)x;
      unsigned char *first_rgba = pixels + first * 4u;
      if (first_rgba[3] != 255 ||
          !native_uniform_background_pixel(first_rgba))
        continue;

      size_t head = 0;
      size_t tail = 0;
      size_t min_x = (size_t)x;
      size_t max_x = (size_t)x;
      size_t min_y = (size_t)y;
      size_t max_y = (size_t)y;
      int touches_transparent = 0;
      first_rgba[3] = 254;
      queue[tail++] = first;

      while (head < tail) {
        const size_t pixel = queue[head++];
        const size_t current_x = pixel % (size_t)width;
        const size_t current_y = pixel / (size_t)width;
        if (current_x < min_x)
          min_x = current_x;
        if (current_x > max_x)
          max_x = current_x;
        if (current_y < min_y)
          min_y = current_y;
        if (current_y > max_y)
          max_y = current_y;

        size_t neighbors[4];
        size_t neighbor_count = 0;
        if (current_x)
          neighbors[neighbor_count++] = pixel - 1u;
        if (current_x + 1u < (size_t)width)
          neighbors[neighbor_count++] = pixel + 1u;
        if (current_y)
          neighbors[neighbor_count++] = pixel - (size_t)width;
        if (current_y + 1u < (size_t)height)
          neighbors[neighbor_count++] = pixel + (size_t)width;
        for (size_t neighbor = 0; neighbor < neighbor_count; neighbor++) {
          unsigned char *rgba = pixels + neighbors[neighbor] * 4u;
          if (!rgba[3]) {
            touches_transparent = 1;
            continue;
          }
          if (rgba[3] != 255 || !native_uniform_background_pixel(rgba))
            continue;
          rgba[3] = 254;
          queue[tail++] = neighbors[neighbor];
        }
      }

      const size_t component_width = max_x - min_x + 1u;
      const size_t component_height = max_y - min_y + 1u;
      const int central_x = min_x > (size_t)width / 5u &&
                            max_x < (size_t)width * 4u / 5u;
      const int central_y = min_y > (size_t)height / 8u &&
                            max_y < (size_t)height * 7u / 8u;
      const size_t center_x = (size_t)width / 2u;
      const size_t center_guard = (size_t)width / 32u + 1u;
      const int beside_torso = max_x + center_guard < center_x ||
                               min_x > center_x + center_guard;
      const int narrow_vertical =
          component_width <= (size_t)width / 8u + 1u &&
          component_height >= component_width * 2u &&
          component_height >= (size_t)height / 10u;
      const int small_component = tail <= pixel_count / 20u + 1u;
      const int remove = !touches_transparent && central_x && central_y &&
                         beside_torso && narrow_vertical && small_component;
      for (size_t index = 0; index < tail; index++)
        pixels[queue[index] * 4u + 3u] = remove ? 0 : 253;
    }
  }

  // Alpha was normalized to 255 before this pass, so 253 is only our visited
  // marker for pale components that must remain visible.
  for (size_t pixel = 0; pixel < pixel_count; pixel++) {
    unsigned char *rgba = pixels + pixel * 4u;
    if (rgba[3] == 253)
      rgba[3] = 255;
  }
}

static void prepare_native_uniform_preview(int active) {
  static unsigned char *capture_pixels;
  static size_t capture_capacity;
  static size_t *capture_flood_queue;
  static size_t capture_flood_capacity;

  if (!active || screen_width <= 0 || screen_height <= 0) {
    gl.native_uniform_valid = 0;
    return;
  }

  static const float capture_x_fraction[2] = {0.145f, 0.438f};
  const float capture_width_fraction = 0.125f;
  const float capture_top_fraction = 0.280f;
  const float capture_bottom_fraction = 0.815f;
  const GLint capture_width =
      (GLint)(capture_width_fraction * (float)screen_width + 0.5f);
  const GLint capture_height =
      (GLint)((capture_bottom_fraction - capture_top_fraction) *
                  (float)screen_height +
              0.5f);
  const GLint capture_bottom =
      (GLint)(capture_bottom_fraction * (float)screen_height + 0.5f);
  const GLint capture_y = screen_height - capture_bottom;
  const GLint capture_x[2] = {
      (GLint)(capture_x_fraction[0] * (float)screen_width + 0.5f),
      (GLint)(capture_x_fraction[1] * (float)screen_width + 0.5f),
  };
  if (capture_width <= 0 || capture_height <= 0 || capture_y < 0)
    return;
  const size_t capture_bytes =
      (size_t)capture_width * (size_t)capture_height * 4u;
  const size_t pixel_count =
      (size_t)capture_width * (size_t)capture_height;
  if (capture_capacity < capture_bytes) {
    unsigned char *next = realloc(capture_pixels, capture_bytes);
    if (!next)
      return;
    capture_pixels = next;
    capture_capacity = capture_bytes;
  }
  if (capture_flood_capacity < pixel_count) {
    size_t *next = realloc(capture_flood_queue,
                           pixel_count * sizeof(*capture_flood_queue));
    if (!next)
      return;
    capture_flood_queue = next;
    capture_flood_capacity = pixel_count;
  }

  // At eglSwapBuffers the native child has finished all scene and UI passes.
  // Snapshot its two model regions before this overlay paints the custom page.
  GLint saved_framebuffer = 0;
  GLint saved_active_texture = GL_TEXTURE0;
  GLint saved_texture = 0;
  GLint saved_pack_alignment = 4;
  GLint saved_unpack_alignment = 4;
  glGetIntegerv(GL_FRAMEBUFFER_BINDING, &saved_framebuffer);
  glGetIntegerv(GL_ACTIVE_TEXTURE, &saved_active_texture);
  glActiveTexture(GL_TEXTURE0);
  glGetIntegerv(GL_TEXTURE_BINDING_2D, &saved_texture);
  glGetIntegerv(GL_PACK_ALIGNMENT, &saved_pack_alignment);
  glGetIntegerv(GL_UNPACK_ALIGNMENT, &saved_unpack_alignment);
  glBindFramebuffer(GL_FRAMEBUFFER, 0);
  glPixelStorei(GL_PACK_ALIGNMENT, 1);
  glPixelStorei(GL_UNPACK_ALIGNMENT, 1);

  const int allocate =
      !gl.native_uniform_texture[0] || !gl.native_uniform_texture[1] ||
      gl.native_uniform_width != capture_width ||
      gl.native_uniform_height != capture_height;
  if (!gl.native_uniform_texture[0] || !gl.native_uniform_texture[1])
    glGenTextures(2, gl.native_uniform_texture);
  if (gl.native_uniform_texture[0] && gl.native_uniform_texture[1]) {
    if (allocate) {
      gl.native_uniform_valid = 0;
      for (uint32_t side = 0; side < 2; side++) {
        glBindTexture(GL_TEXTURE_2D, gl.native_uniform_texture[side]);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, capture_width,
                     capture_height, 0, GL_RGBA, GL_UNSIGNED_BYTE, NULL);
      }
    }

    int captured_sides = 0;
    for (uint32_t side = 0; side < 2; side++) {
      memset(capture_pixels, 0, capture_bytes);
      glReadPixels(capture_x[side], capture_y, capture_width, capture_height,
                   GL_RGBA, GL_UNSIGNED_BYTE, capture_pixels);
      unsigned int rgb_nonzero = 0;
      for (size_t pixel = 0; pixel < pixel_count; pixel++) {
        unsigned char *rgba = capture_pixels + pixel * 4u;
        rgb_nonzero |= (unsigned int)rgba[0] | (unsigned int)rgba[1] |
                       (unsigned int)rgba[2];
        // EGL surface alpha is not presentation data; keep the captured model
        // opaque when it is sampled by the overlay shader.
        rgba[3] = 255;
      }
      if (!rgb_nonzero)
        break;

      // Remove only the pale native card background connected to the crop
      // boundary. Enclosed white kit pixels remain opaque.
      size_t flood_head = 0;
      size_t flood_tail = 0;
      for (GLint y = 0; y < capture_height; y++) {
        for (GLint edge = 0; edge < 2; edge++) {
          const GLint x = edge ? capture_width - 1 : 0;
          const size_t pixel = (size_t)y * (size_t)capture_width +
                               (size_t)x;
          unsigned char *rgba = capture_pixels + pixel * 4u;
          if (native_uniform_background_pixel(rgba)) {
            rgba[3] = 0;
            capture_flood_queue[flood_tail++] = pixel;
          }
        }
      }
      for (GLint x = 1; x + 1 < capture_width; x++) {
        for (GLint edge = 0; edge < 2; edge++) {
          const GLint y = edge ? capture_height - 1 : 0;
          const size_t pixel = (size_t)y * (size_t)capture_width +
                               (size_t)x;
          unsigned char *rgba = capture_pixels + pixel * 4u;
          if (native_uniform_background_pixel(rgba)) {
            rgba[3] = 0;
            capture_flood_queue[flood_tail++] = pixel;
          }
        }
      }
      while (flood_head < flood_tail) {
        const size_t pixel = capture_flood_queue[flood_head++];
        const size_t x = pixel % (size_t)capture_width;
        const size_t y = pixel / (size_t)capture_width;
        size_t neighbors[4];
        size_t neighbor_count = 0;
        if (x)
          neighbors[neighbor_count++] = pixel - 1u;
        if (x + 1u < (size_t)capture_width)
          neighbors[neighbor_count++] = pixel + 1u;
        if (y)
          neighbors[neighbor_count++] = pixel - (size_t)capture_width;
        if (y + 1u < (size_t)capture_height)
          neighbors[neighbor_count++] = pixel + (size_t)capture_width;
        for (size_t neighbor = 0; neighbor < neighbor_count; neighbor++) {
          const size_t next_pixel = neighbors[neighbor];
          unsigned char *rgba = capture_pixels + next_pixel * 4u;
          if (!native_uniform_background_pixel(rgba))
            continue;
          rgba[3] = 0;
          capture_flood_queue[flood_tail++] = next_pixel;
        }
      }

      // The gaps between each arm and torso are enclosed by the model, so a
      // boundary flood cannot reach them. Remove only small, tall background
      // islands near the mannequin center; white kit surfaces remain intact.
      native_uniform_remove_enclosed_background(
          capture_pixels, capture_width, capture_height,
          capture_flood_queue);

      glBindTexture(GL_TEXTURE_2D, gl.native_uniform_texture[side]);
      glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, capture_width,
                      capture_height, GL_RGBA, GL_UNSIGNED_BYTE,
                      capture_pixels);
      glGenerateMipmap(GL_TEXTURE_2D);
      captured_sides++;
    }
    if (captured_sides == 2) {
      gl.native_uniform_width = capture_width;
      gl.native_uniform_height = capture_height;
      gl.native_uniform_valid = 1;
    }
  }

  glPixelStorei(GL_PACK_ALIGNMENT, saved_pack_alignment);
  glPixelStorei(GL_UNPACK_ALIGNMENT, saved_unpack_alignment);
  glBindTexture(GL_TEXTURE_2D, (GLuint)saved_texture);
  glActiveTexture((GLenum)saved_active_texture);
  glBindFramebuffer(GL_FRAMEBUFFER, (GLuint)saved_framebuffer);
}

static int decode_uniform_thumbnail(const PesUniformPreviewPng *preview,
                                    unsigned char **pixels_out,
                                    GLint *width_out, GLint *height_out) {
  if (!preview || !preview->byte_count || !pixels_out || !width_out ||
      !height_out)
    return 0;

  png_image image;
  memset(&image, 0, sizeof(image));
  image.version = PNG_IMAGE_VERSION;
  if (!png_image_begin_read_from_memory(&image, preview->bytes,
                                        preview->byte_count))
    return 0;
  if (!image.width || !image.height || image.width > 2048u ||
      image.height > 2048u) {
    png_image_free(&image);
    return 0;
  }

  image.format = PNG_FORMAT_RGBA;
  const size_t pixel_bytes = PNG_IMAGE_SIZE(image);
  unsigned char *pixels = malloc(pixel_bytes);
  if (!pixels) {
    png_image_free(&image);
    return 0;
  }
  if (!png_image_finish_read(&image, NULL, pixels, 0, NULL)) {
    free(pixels);
    png_image_free(&image);
    return 0;
  }

  *pixels_out = pixels;
  *width_out = (GLint)image.width;
  *height_out = (GLint)image.height;
  png_image_free(&image);
  return 1;
}

static void prepare_uniform_thumbnail_preview(int active) {
  PesUniformPreviewPng *pending[2] = {
      pes_controller_2p_take_uniform_preview_png(0),
      pes_controller_2p_take_uniform_preview_png(1),
  };
  if (!active) {
    gl.native_uniform_valid = 0;
    gl.native_uniform_valid_mask = 0;
    free(pending[0]);
    free(pending[1]);
    return;
  }
  if (!pending[0] && !pending[1])
    return;

  GLint saved_active_texture = GL_TEXTURE0;
  GLint saved_texture = 0;
  GLint saved_unpack_alignment = 4;
  glGetIntegerv(GL_ACTIVE_TEXTURE, &saved_active_texture);
  glActiveTexture(GL_TEXTURE0);
  glGetIntegerv(GL_TEXTURE_BINDING_2D, &saved_texture);
  glGetIntegerv(GL_UNPACK_ALIGNMENT, &saved_unpack_alignment);
  glPixelStorei(GL_UNPACK_ALIGNMENT, 1);

  for (uint32_t side = 0; side < 2; side++) {
    PesUniformPreviewPng *preview = pending[side];
    if (!preview)
      continue;
    gl.native_uniform_valid_mask &= ~(1u << side);

    unsigned char *pixels = NULL;
    GLint width = 0;
    GLint height = 0;
    if (decode_uniform_thumbnail(preview, &pixels, &width, &height)) {
      if (!gl.native_uniform_texture[side])
        glGenTextures(1, &gl.native_uniform_texture[side]);
      if (gl.native_uniform_texture[side]) {
        glBindTexture(GL_TEXTURE_2D, gl.native_uniform_texture[side]);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA,
                     GL_UNSIGNED_BYTE, pixels);
        gl.native_uniform_width = width;
        gl.native_uniform_height = height;
        gl.native_uniform_valid_mask |= 1u << side;
      }
    }
    free(pixels);
    free(preview);
  }

  gl.native_uniform_valid =
      (gl.native_uniform_valid_mask & 3u) == 3u;
  glPixelStorei(GL_UNPACK_ALIGNMENT, saved_unpack_alignment);
  glBindTexture(GL_TEXTURE_2D, (GLuint)saved_texture);
  glActiveTexture((GLenum)saved_active_texture);
}

static int emit_segment(float x0, float y0, float x1, float y1,
                        float thickness, GLfloat *verts) {
  const float dx = x1 - x0;
  const float dy = y1 - y0;
  const float length = sqrtf(dx * dx + dy * dy);
  if (length <= 0.001f)
    return 0;
  const float px = -dy * thickness * 0.5f / length;
  const float py = dx * thickness * 0.5f / length;
  const float ax = (x0 + px) * 2.0f / (float)screen_width - 1.0f;
  const float ay = 1.0f - (y0 + py) * 2.0f / (float)screen_height;
  const float bx = (x1 + px) * 2.0f / (float)screen_width - 1.0f;
  const float by = 1.0f - (y1 + py) * 2.0f / (float)screen_height;
  const float cx = (x0 - px) * 2.0f / (float)screen_width - 1.0f;
  const float cy = 1.0f - (y0 - py) * 2.0f / (float)screen_height;
  const float dx2 = (x1 - px) * 2.0f / (float)screen_width - 1.0f;
  const float dy2 = 1.0f - (y1 - py) * 2.0f / (float)screen_height;
  const GLfloat quad[24] = {
      ax, ay, 0.0f, 0.0f, bx, by, 0.0f, 0.0f,
      cx, cy, 0.0f, 0.0f, bx, by, 0.0f, 0.0f,
      dx2, dy2, 0.0f, 0.0f, cx, cy, 0.0f, 0.0f,
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

// The source mask is supersampled and downscaled offline. Drawing it as one
// linearly filtered quad gives the small Switch UI stars clean edges; u_limit
// also lets a half-star crop both geometry and UVs without a hard center seam.
static int emit_star_mask(float center_x, float center_y, float outer_radius,
                          float u_limit, GLfloat *verts) {
  const float size = outer_radius * 2.0f / 0.91f;
  const float x = center_x - size * 0.5f;
  const float y = center_y - size * 0.5f;
  const float width = size * u_limit;
  const float x0 = x * 2.0f / (float)screen_width - 1.0f;
  const float x1 = (x + width) * 2.0f / (float)screen_width - 1.0f;
  const float y0 = 1.0f - y * 2.0f / (float)screen_height;
  const float y1 = 1.0f - (y + size) * 2.0f / (float)screen_height;
  const GLfloat quad[24] = {
      x0, y0, 0.0f, 0.0f, x1, y0, u_limit, 0.0f,
      x0, y1, 0.0f, 1.0f, x1, y0, u_limit, 0.0f,
      x1, y1, u_limit, 1.0f, x0, y1, 0.0f, 1.0f,
  };
  memcpy(verts, quad, sizeof(quad));
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
  const int custom_2p_transition = pes_controller_2p_transition_active();
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
      !custom_2p_transition && goal_demo_active &&
      controller_snapshot.goal_helper_visible;
  const int cinematic_goal_actions = goal_demo_player;
  const int cinematic_goal_skip_only =
      goal_demo_active && !goal_demo_player;
  uint32_t setplay_context =
      !custom_2p_transition &&
      controller_snapshot.surface == PES_CONTROLLER_SURFACE_SETPLAY
          ? controller_snapshot.setplay_context
          : PES_SETPLAY_NONE;
  uint32_t setplay_options =
      !custom_2p_transition &&
      controller_snapshot.surface == PES_CONTROLLER_SURFACE_SETPLAY
          ? controller_snapshot.setplay_options
          : 0;
  const int pause_camera_active =
      !custom_2p_transition && pes_controller_pause_camera_active();
  const int tutorial_play_active =
      !custom_2p_transition && pes_controller_inmatch_tutorial_active();
  const uint32_t penalty_role_p1 =
      custom_2p_transition ? PES_PENALTY_NONE
                           : pes_controller_penalty_role_for_pad(0);
  const int penalty_two_player = pes_controller_native_pad_lab_two_player();
  const uint32_t penalty_role_p2 =
      (!custom_2p_transition && penalty_two_player)
          ? pes_controller_penalty_role_for_pad(1)
          : PES_PENALTY_NONE;
  const int set_piece_selector =
      !custom_2p_transition && pes_controller_set_piece_selector_active();
  float selector_x = 0.0f;
  float selector_y = 0.0f;
  float selector_width = 0.0f;
  float selector_height = 0.0f;
  const int custom_2p_team_selector =
      pes_controller_2p_team_selector_active();
  const int custom_2p_prematch_hub_raw =
      pes_controller_2p_prematch_hub_active();
  const int custom_settings_popup =
      pes_controller_custom_match_settings_active();
  const int custom_hub_settings_popup =
      custom_settings_popup && custom_2p_prematch_hub_raw;
  const uint32_t custom_hub_page = custom_2p_prematch_hub_raw
                                       ? pes_controller_2p_prematch_hub_page()
                                       : PES_2P_PREMATCH_HUB_PAGE_MAIN;
  const int custom_hub_kits_page =
      custom_2p_prematch_hub_raw && !custom_settings_popup &&
      custom_hub_page == PES_2P_PREMATCH_HUB_PAGE_KITS;
  const int custom_hub_stadium_page =
      custom_2p_prematch_hub_raw && !custom_settings_popup &&
      custom_hub_page == PES_2P_PREMATCH_HUB_PAGE_STADIUM;
  const int custom_hub_choice_page =
      custom_hub_kits_page || custom_hub_stadium_page;
  // The stock selector's blue focus/glow belongs to the native menu.  Both
  // custom 2P surfaces fully own the frame, so letting that geometry draw on
  // top makes the entire hub look like a blue selection wash.
  const int selector = !set_piece_selector && !custom_2p_team_selector &&
                       !custom_2p_prematch_hub_raw && !custom_2p_transition &&
                       pes_controller_selector_rect(
      &selector_x, &selector_y, &selector_width, &selector_height);
  const int selector_custom =
      selector && pes_controller_selector_custom_style();
  const int custom_team_popup = pes_controller_custom_team_popup_active();
  const int custom_cpu_popup = pes_controller_custom_cpu_popup_active();
  const int custom_video_settings_popup =
      pes_controller_custom_video_settings_active();
  const int custom_info_popup = pes_controller_custom_info_popup_active();
  // Match Settings is a modal child of the hub.  Let the existing settings
  // renderer own the foreground while retaining the hub as its visual host.
  const int custom_2p_prematch_hub =
      custom_2p_prematch_hub_raw && !custom_settings_popup &&
      custom_hub_page == PES_2P_PREMATCH_HUB_PAGE_MAIN;
  const int custom_popup =
      custom_team_popup || custom_cpu_popup || custom_settings_popup ||
      custom_video_settings_popup || custom_info_popup || set_piece_selector ||
      custom_2p_team_selector || custom_2p_prematch_hub_raw ||
      custom_2p_transition;
  // Keep the ready transition entirely presentation-side. The controller
  // state remains a simple lock while the focused card eases toward its
  // header for the PES-style confirmed layout.
  static int team_selector_was_active = 0;
  static int team_selector_previous_confirmed[2] = {0, 0};
  static u64 team_selector_confirm_started_tick[2] = {0, 0};
  float team_selector_confirm_progress[2] = {0.0f, 0.0f};
  uint32_t team_selector_ratings[2][3] = {{0}}; // FW, MF, DF
  uint32_t team_selector_grade_half_steps[2] = {0, 0};
  int team_selector_stats_valid[2] = {0, 0};
  if (custom_2p_team_selector) {
    const u64 now = armGetSystemTick();
    for (uint32_t pad = 0; pad < 2; pad++) {
      const int confirmed =
          pes_controller_2p_team_selector_confirmed(pad);
      if (confirmed &&
          (!team_selector_was_active ||
           !team_selector_previous_confirmed[pad]))
        team_selector_confirm_started_tick[pad] = now;
      if (!confirmed)
        team_selector_confirm_started_tick[pad] = 0;
      if (confirmed) {
        float t = team_selector_confirm_started_tick[pad]
                      ? (float)armTicksToNs(
                            now - team_selector_confirm_started_tick[pad]) /
                            240000000.0f
                      : 1.0f;
        if (t > 1.0f)
          t = 1.0f;
        // Smoothstep avoids the mechanical stop of a linear slide.
        team_selector_confirm_progress[pad] = t * t * (3.0f - 2.0f * t);
      }
      team_selector_previous_confirmed[pad] = confirmed;
      team_selector_stats_valid[pad] =
          pes_controller_2p_team_selector_team_stats(
              pad, &team_selector_ratings[pad][0],
              &team_selector_ratings[pad][1],
              &team_selector_ratings[pad][2],
              &team_selector_grade_half_steps[pad]);
    }
    team_selector_was_active = 1;
  } else {
    team_selector_was_active = 0;
    memset(team_selector_previous_confirmed, 0,
           sizeof(team_selector_previous_confirmed));
    memset(team_selector_confirm_started_tick, 0,
           sizeof(team_selector_confirm_started_tick));
  }
  float prompt_x = 0.0f;
  float prompt_y = 0.0f;
  const int start_prompt =
      !custom_2p_transition && pes_controller_start_prompt(&prompt_x,
                                                           &prompt_y);
  const int native_lab = pes_controller_native_pad_lab_active();
  PesNativePadLabDebug native_debug = {0};
  if (native_lab)
    pes_controller_native_pad_lab_debug_snapshot(&native_debug);
  int native_setplay_debug =
      !custom_2p_transition && native_lab &&
      native_debug.context != PES_SETPLAY_NONE;
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
      !custom_2p_transition && !set_piece_selector && !tutorial_play_active &&
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
  prepare_uniform_thumbnail_preview(custom_hub_kits_page);

  static GLfloat verts[4096 * 24];
  int quads = 0;
  int custom_backdrop_quads = 0;
  int custom_panel_quads = 0;
  int custom_header_round_quads = 0;
  int custom_header_fill_quads = 0;
  int custom_selected_quads = 0;
  int custom_confirm_bar_quads = 0;
  int custom_kit_preview_first_quad[2] = {0};
  int custom_kit_preview_side_quads[2] = {0};
  int custom_kit_preview_quads = 0;
  int custom_rule_quads = 0;
  int custom_team_stat_track_first_quad[2][3] = {{0}};
  int custom_team_stat_track_quads[2][3] = {{0}};
  int custom_team_stat_fill_first_quad[2][3] = {{0}};
  int custom_team_stat_fill_quads[2][3] = {{0}};
  RoundedRectStyle custom_team_stat_track_style = {0};
  RoundedRectStyle custom_team_stat_fill_style[2][3] = {{{0}}};
  int custom_team_star_border_first_quad = 0;
  int custom_team_star_border_quads = 0;
  int custom_team_star_empty_first_quad = 0;
  int custom_team_star_empty_quads = 0;
  int custom_team_star_fill_first_quad = 0;
  int custom_team_star_fill_quads = 0;
  int custom_team_stat_shape_quads = 0;
  int custom_value_plate_quads = 0;
  int custom_arrow_quads = 0;
  int custom_badge_plate_quads = 0;
  int custom_action_button_quads = 0;
  int custom_back_button_quads = 0;
  int custom_action_key_bg_quads = 0;
  int custom_back_key_bg_quads = 0;
  int custom_icon_quads = 0;
  int custom_hub_button_text_first_quad = 0;
  int custom_hub_button_text_quads = 0;
  int custom_dark_text_first_quad = 0;
  int custom_dark_text_quads = 0;
  int custom_focus_text_first_quad = 0;
  int custom_focus_text_quads = 0;
  int custom_ok_text_first_quad = 0;
  int custom_ok_text_quads = 0;
  int custom_rating_first_quad[10] = {0};
  int custom_rating_quads[10] = {0};
  int selector_position_first_quad[4] = {0};
  int selector_position_quads[4] = {0};
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
  if (custom_2p_team_selector) {
    // PES-PC-style dual carousel: the focused entry expands into the large
    // centre card, with its two neighbours above and below. Each controller
    // owns one half and the opaque backdrop fully replaces the stock page.
    const float panel_y = 0.040f * (float)screen_height;
    const float panel_w = 0.430f * (float)screen_width;
    const float panel_x[2] = {0.035f * (float)screen_width,
                              0.535f * (float)screen_width};
    const float header_h = 0.120f * (float)screen_height;
    const float row_x_inset = 0.0f;
    const float row_w = panel_w - row_x_inset * 2.0f;
    const float row_h = 0.340f * (float)screen_height;
    const float row_y0 = 0.350f * (float)screen_height;
    const float row_confirm_y = panel_y + header_h;
    const float confirm_bar_h = 0.085f * (float)screen_height;
    float focused_y[2] = {row_y0, row_y0};
    for (uint32_t pad = 0; pad < 2; pad++)
      focused_y[pad] =
          row_y0 + (row_confirm_y - row_y0) *
                        team_selector_confirm_progress[pad];
    // Four compact neighbours use exactly one quarter of the focused card.
    const float small_row_h = row_h * 0.25f;
    const float team_badge_size = 0.185f * (float)screen_height;
    const float team_badge_x_offset = 0.030f * (float)screen_width;
    const float team_badge_y_offset = 0.100f * (float)screen_height;
    const float team_stat_x_offset = 0.170f * (float)screen_width;
    const float team_stat_y_offset = 0.090f * (float)screen_height;
    const float team_stat_row_step = 0.066f * (float)screen_height;
    const float team_stat_bar_w = 0.225f * (float)screen_width;
    const float team_stat_track_h = 0.012f * (float)screen_height;
    const float team_stat_fill_h = 0.0075f * (float)screen_height;
    const float team_stat_bar_y_offset = 0.026f * (float)screen_height;
    const float team_star_y_offset = 0.302f * (float)screen_height;
    const float team_star_outer_radius = 0.0180f * (float)screen_height;
    const float team_star_fill_outer = team_star_outer_radius * 0.82f;

    custom_backdrop_quads = emit_image_rect(
        0.0f, 0.0f, (float)screen_width, (float)screen_height,
        verts + quads * 24);
    quads += custom_backdrop_quads;
    // Deliberately no side-container layer: backdrop -> header -> carousel.
    custom_panel_style = (RoundedRectStyle){0};
    custom_header_style = (RoundedRectStyle){0};
    for (uint32_t pad = 0; pad < 2; pad++) {
      int header_quads = emit_rect(
          panel_x[pad], panel_y, panel_w, header_h, verts + quads * 24);
      custom_header_round_quads += header_quads;
      quads += header_quads;
    }
    // A plain rectangle keeps the five carousel blocks perfectly joined.
    custom_selected_style = (RoundedRectStyle){0};
    for (uint32_t pad = 0; pad < 2; pad++) {
      custom_selected_quads += emit_rect(
          panel_x[pad] + row_x_inset, focused_y[pad], row_w, row_h,
          verts + quads * 24);
      quads++;
    }
    // The ready state gets its own full-width strip. It is deliberately not
    // painted over the badge card, matching the detached OK row in PES PC.
    for (uint32_t pad = 0; pad < 2; pad++) {
      if (!pes_controller_2p_team_selector_confirmed(pad))
        continue;
      custom_confirm_bar_quads += emit_rect(
          panel_x[pad] + row_x_inset, focused_y[pad] + row_h, row_w,
          confirm_bar_h, verts + quads * 24);
      quads++;
    }
    for (uint32_t pad = 0; pad < 2; pad++) {
      if (pes_controller_2p_team_selector_confirmed(pad))
        continue;
      const uint32_t focus = pes_controller_2p_team_selector_focus(pad);
      const uint32_t scroll = pes_controller_2p_team_selector_scroll(pad);
      const uint32_t visible =
          pes_controller_2p_team_selector_visible_count(pad);
      for (uint32_t item = 0; item < visible; item++) {
        const int relative = (int)(scroll + item) - (int)focus;
        if (!relative || relative < -2 || relative > 2)
          continue;
        const float small_y =
            (relative < 0 ? 0.180f + (float)(relative + 2) * 0.085f
                          : 0.690f + (float)(relative - 1) * 0.085f) *
            (float)screen_height;
        custom_rule_quads += emit_rect(
            panel_x[pad] + row_x_inset, small_y, row_w, small_row_h,
            verts + quads * 24);
        quads++;
      }
    }

    // Team cards use the mobile database's positional OVR values. Tracks and
    // fills remain separate rounded quads so FW/MF/DF can keep the PC color
    // language without baking another texture atlas.
    custom_team_stat_track_style = (RoundedRectStyle){
        team_stat_bar_w, team_stat_track_h, team_stat_track_h * 0.5f};
    for (uint32_t pad = 0; pad < 2; pad++) {
      if (pes_controller_2p_team_selector_phase(pad) !=
              PES_2P_TEAM_SELECTOR_PHASE_TEAM ||
          !team_selector_stats_valid[pad])
        continue;
      const float stat_x = panel_x[pad] + team_stat_x_offset;
      for (uint32_t role = 0; role < 3; role++) {
        const float stat_y = focused_y[pad] + team_stat_y_offset +
                             (float)role * team_stat_row_step;
        const float track_y = stat_y + team_stat_bar_y_offset;
        custom_team_stat_track_first_quad[pad][role] = quads;
        const int track_quads = emit_round_rect_quad(
            stat_x, track_y, team_stat_bar_w, team_stat_track_h,
            verts + quads * 24);
        custom_team_stat_track_quads[pad][role] = track_quads;
        custom_team_stat_shape_quads += track_quads;
        quads += track_quads;

        float fill_w = team_stat_bar_w *
                       (float)team_selector_ratings[pad][role] / 100.0f;
        if (fill_w < team_stat_fill_h)
          fill_w = team_stat_fill_h;
        if (fill_w > team_stat_bar_w)
          fill_w = team_stat_bar_w;
        const float fill_y =
            track_y + (team_stat_track_h - team_stat_fill_h) * 0.5f;
        custom_team_stat_fill_first_quad[pad][role] = quads;
        const int fill_quads = emit_round_rect_quad(
            stat_x, fill_y, fill_w, team_stat_fill_h,
            verts + quads * 24);
        custom_team_stat_fill_quads[pad][role] = fill_quads;
        custom_team_stat_fill_style[pad][role] = (RoundedRectStyle){
            fill_w, team_stat_fill_h, team_stat_fill_h * 0.5f};
        custom_team_stat_shape_quads += fill_quads;
        quads += fill_quads;
      }
    }

    custom_team_star_border_first_quad = quads;
    for (uint32_t pad = 0; pad < 2; pad++) {
      if (pes_controller_2p_team_selector_phase(pad) !=
              PES_2P_TEAM_SELECTOR_PHASE_TEAM ||
          !team_selector_stats_valid[pad])
        continue;
      const float stat_x = panel_x[pad] + team_stat_x_offset;
      const float star_y = focused_y[pad] + team_star_y_offset;
      for (uint32_t star = 0; star < 5; star++) {
        const float star_x = stat_x +
            team_stat_bar_w * ((float)star + 0.5f) / 5.0f;
        const int star_quads = emit_star_mask(
            star_x, star_y, team_star_outer_radius, 1.0f,
            verts + quads * 24);
        custom_team_star_border_quads += star_quads;
        custom_team_stat_shape_quads += star_quads;
        quads += star_quads;
      }
    }
    custom_team_star_empty_first_quad = quads;
    for (uint32_t pad = 0; pad < 2; pad++) {
      if (pes_controller_2p_team_selector_phase(pad) !=
              PES_2P_TEAM_SELECTOR_PHASE_TEAM ||
          !team_selector_stats_valid[pad])
        continue;
      const float stat_x = panel_x[pad] + team_stat_x_offset;
      const float star_y = focused_y[pad] + team_star_y_offset;
      for (uint32_t star = 0; star < 5; star++) {
        const float star_x = stat_x +
            team_stat_bar_w * ((float)star + 0.5f) / 5.0f;
        const int star_quads = emit_star_mask(
            star_x, star_y, team_star_fill_outer, 1.0f,
            verts + quads * 24);
        custom_team_star_empty_quads += star_quads;
        custom_team_stat_shape_quads += star_quads;
        quads += star_quads;
      }
    }
    custom_team_star_fill_first_quad = quads;
    for (uint32_t pad = 0; pad < 2; pad++) {
      if (pes_controller_2p_team_selector_phase(pad) !=
              PES_2P_TEAM_SELECTOR_PHASE_TEAM ||
          !team_selector_stats_valid[pad])
        continue;
      const uint32_t full_stars =
          team_selector_grade_half_steps[pad] / 2u;
      const uint32_t half_star =
          team_selector_grade_half_steps[pad] & 1u;
      const float stat_x = panel_x[pad] + team_stat_x_offset;
      const float star_y = focused_y[pad] + team_star_y_offset;
      for (uint32_t star = 0; star < 5; star++) {
        const float star_x = stat_x +
            team_stat_bar_w * ((float)star + 0.5f) / 5.0f;
        int star_quads = 0;
        if (star < full_stars)
          star_quads = emit_star_mask(
              star_x, star_y, team_star_fill_outer, 1.0f,
              verts + quads * 24);
        else if (star == full_stars && half_star)
          star_quads = emit_star_mask(
              star_x, star_y, team_star_fill_outer, 0.5f,
              verts + quads * 24);
        custom_team_star_fill_quads += star_quads;
        custom_team_stat_shape_quads += star_quads;
        quads += star_quads;
      }
    }

    // Emit footer key circles before badge textures because
    // the shared draw pass renders those categories in that order.
    const float helper_y = 0.958f * (float)screen_height;
    const float helper_r = 0.021f * (float)screen_height;
    custom_action_key_bg_quads += emit_circle_quad(
        0.745f * (float)screen_width, helper_y, helper_r,
        verts + quads * 24);
    quads++;
    custom_action_key_bg_quads += emit_circle_quad(
        0.875f * (float)screen_width, helper_y, helper_r,
        verts + quads * 24);
    quads++;

    for (uint32_t pad = 0; pad < 2; pad++) {
      const uint32_t focus = pes_controller_2p_team_selector_focus(pad);
      const uint32_t scroll = pes_controller_2p_team_selector_scroll(pad);
      const uint32_t visible =
          pes_controller_2p_team_selector_visible_count(pad);
      const int team_phase =
          pes_controller_2p_team_selector_phase(pad) ==
          PES_2P_TEAM_SELECTOR_PHASE_TEAM;
      const float feature_size = team_phase
                                     ? team_badge_size
                                     : 0.205f * (float)screen_height;
      const float feature_x = team_phase
                                  ? panel_x[pad] + team_badge_x_offset
                                  : panel_x[pad] + panel_w * 0.5f -
                                        feature_size * 0.5f;
      const float feature_y = team_phase
                                  ? focused_y[pad] + team_badge_y_offset
                                  : focused_y[pad] +
                                        0.105f * (float)screen_height;
      custom_icon_quads += emit_badge(
          pes_controller_2p_team_selector_badge(pad, focus),
          feature_x, feature_y, feature_size, feature_size,
          verts + quads * 24);
      quads++;
      if (pes_controller_2p_team_selector_confirmed(pad))
        continue;
      for (uint32_t item = 0; item < visible; item++) {
        const int relative = (int)(scroll + item) - (int)focus;
        if (!relative || relative < -2 || relative > 2)
          continue;
        const float small_y =
            (relative < 0 ? 0.180f + (float)(relative + 2) * 0.085f
                          : 0.690f + (float)(relative - 1) * 0.085f) *
            (float)screen_height;
        const float icon_size = 0.055f * (float)screen_height;
        const float x = panel_x[pad] + row_x_inset +
                        0.010f * (float)screen_width;
        const float y = small_y + (small_row_h - icon_size) * 0.5f;
        custom_icon_quads += emit_badge(
            pes_controller_2p_team_selector_badge(pad, scroll + item), x, y,
            icon_size, icon_size, verts + quads * 24);
        quads++;
      }
    }

    const float text_gh = (float)screen_height / 52.0f;
    const float small_text_gh = (float)screen_height / 57.0f;
    const float feature_text_gh = (float)screen_height / 31.0f;
    const float stat_text_gh = (float)screen_height / 43.0f;
    custom_dark_text_first_quad = quads;
    for (uint32_t pad = 0; pad < 2; pad++) {
      const float left = panel_x[pad];
      const uint32_t focus = pes_controller_2p_team_selector_focus(pad);
      const uint32_t scroll = pes_controller_2p_team_selector_scroll(pad);
      const uint32_t visible =
          pes_controller_2p_team_selector_visible_count(pad);
      const char *feature =
          pes_controller_2p_team_selector_label(pad, focus);
      int line_quads = 0;
      if (pes_controller_2p_team_selector_confirmed(pad)) {
        line_quads = emit_efootball_line(
            feature, (int)strlen(feature), left + row_x_inset +
                                                0.015f * (float)screen_width,
            focused_y[pad] + 0.020f * (float)screen_height,
            feature_text_gh, EFOOTBALL_FONT_STENCIL,
            verts + quads * 24);
        custom_dark_text_quads += line_quads;
        quads += line_quads;
        line_quads = emit_efootball_line(
            feature, (int)strlen(feature), left + row_x_inset +
                                                0.0158f * (float)screen_width,
            focused_y[pad] + 0.020f * (float)screen_height,
            feature_text_gh, EFOOTBALL_FONT_STENCIL,
            verts + quads * 24);
        custom_dark_text_quads += line_quads;
        quads += line_quads;
      }
      if (pes_controller_2p_team_selector_phase(pad) ==
              PES_2P_TEAM_SELECTOR_PHASE_TEAM &&
          team_selector_stats_valid[pad]) {
        static const char *const role_labels[3] = {"FW", "MF", "DF"};
        const float stat_x = left + team_stat_x_offset;
        for (uint32_t role = 0; role < 3; role++) {
          const float stat_y = focused_y[pad] + team_stat_y_offset +
                               (float)role * team_stat_row_step;
          line_quads = emit_efootball_line(
              role_labels[role], 2, stat_x, stat_y, stat_text_gh,
              EFOOTBALL_FONT_BOLD, verts + quads * 24);
          custom_dark_text_quads += line_quads;
          quads += line_quads;
          char rating_text[4];
          snprintf(rating_text, sizeof(rating_text), "%u",
                   team_selector_ratings[pad][role]);
          const int rating_length = (int)strlen(rating_text);
          const float rating_width = measure_efootball_line(
              rating_text, rating_length, stat_text_gh,
              EFOOTBALL_FONT_BOLD);
          line_quads = emit_efootball_line(
              rating_text, rating_length,
              stat_x + team_stat_bar_w - rating_width, stat_y,
              stat_text_gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
          custom_dark_text_quads += line_quads;
          quads += line_quads;
        }
      }
      for (uint32_t item = 0;
           !pes_controller_2p_team_selector_confirmed(pad) && item < visible;
           item++) {
        const uint32_t index = scroll + item;
        const int relative = (int)index - (int)focus;
        if (!relative || relative < -2 || relative > 2)
          continue;
        const float small_y =
            (relative < 0 ? 0.180f + (float)(relative + 2) * 0.085f
                          : 0.690f + (float)(relative - 1) * 0.085f) *
            (float)screen_height;
        const char *label =
            pes_controller_2p_team_selector_label(pad, index);
        line_quads = emit_efootball_line(
            label, (int)strlen(label), left + row_x_inset +
                                            0.052f * (float)screen_width,
            small_y + (small_row_h - small_text_gh) * 0.5f,
            small_text_gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
        custom_dark_text_quads += line_quads;
        quads += line_quads;
      }
    }

    // While browsing, the focused team/league name is the red accent. Once
    // confirmed it moves back into the neutral text pass above.
    custom_focus_text_first_quad = quads;
    for (uint32_t pad = 0; pad < 2; pad++) {
      if (pes_controller_2p_team_selector_confirmed(pad))
        continue;
      const char *feature = pes_controller_2p_team_selector_label(
          pad, pes_controller_2p_team_selector_focus(pad));
      const float feature_x = panel_x[pad] + row_x_inset +
                              0.015f * (float)screen_width;
      int line_quads = emit_efootball_line(
          feature, (int)strlen(feature), feature_x,
          focused_y[pad] + 0.020f * (float)screen_height,
          feature_text_gh, EFOOTBALL_FONT_STENCIL, verts + quads * 24);
      custom_focus_text_quads += line_quads;
      quads += line_quads;
      line_quads = emit_efootball_line(
          feature, (int)strlen(feature),
          feature_x + 0.0008f * (float)screen_width,
          focused_y[pad] + 0.020f * (float)screen_height,
          feature_text_gh, EFOOTBALL_FONT_STENCIL, verts + quads * 24);
      custom_focus_text_quads += line_quads;
      quads += line_quads;
    }

    custom_ok_text_first_quad = quads;
    for (uint32_t pad = 0; pad < 2; pad++) {
      if (!pes_controller_2p_team_selector_confirmed(pad))
        continue;
      static const char ok[] = "OK";
      const float ok_width = measure_efootball_line(
          ok, 2, feature_text_gh, EFOOTBALL_FONT_BOLD);
      const int line_quads = emit_efootball_line(
          ok, 2, panel_x[pad] + panel_w * 0.5f - ok_width * 0.5f,
          focused_y[pad] + row_h +
              (confirm_bar_h - feature_text_gh) * 0.5f,
          feature_text_gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
      custom_ok_text_quads += line_quads;
      quads += line_quads;
    }

    custom_white_text_first_quad = quads;
    for (uint32_t pad = 0; pad < 2; pad++) {
      const float left = panel_x[pad];
      const char *player = pad == 0 ? "HOME" : "AWAY";
      const float player_gh = (float)screen_height / 29.0f;
      float line_width = measure_efootball_line(
          player, (int)strlen(player), player_gh, EFOOTBALL_FONT_BOLD);
      int line_quads = emit_efootball_line(
          player, (int)strlen(player), left + panel_w * 0.5f -
                                         line_width * 0.5f,
          panel_y + 0.018f * (float)screen_height, player_gh,
          EFOOTBALL_FONT_BOLD, verts + quads * 24);
      custom_white_text_quads += line_quads;
      quads += line_quads;
      const char *title = pes_controller_2p_team_selector_title(pad);
      line_width = measure_efootball_line(
          title, (int)strlen(title), text_gh, EFOOTBALL_FONT_BOLD);
      line_quads = emit_efootball_line(
          title, (int)strlen(title), left + panel_w * 0.5f -
                                       line_width * 0.5f,
          panel_y + 0.078f * (float)screen_height, text_gh,
          EFOOTBALL_FONT_BOLD, verts + quads * 24);
      custom_white_text_quads += line_quads;
      quads += line_quads;
    }
    // Global footer mirrors PES: B backs out, A confirms the focused entry.
    int line_quads = emit_efootball_line(
        "CANCEL", 6, 0.770f * (float)screen_width,
        helper_y - text_gh * 0.5f, text_gh, EFOOTBALL_FONT_BOLD,
        verts + quads * 24);
    custom_white_text_quads += line_quads;
    quads += line_quads;
    line_quads = emit_efootball_line(
        "CONFIRM", 7, 0.900f * (float)screen_width,
        helper_y - text_gh * 0.5f, text_gh, EFOOTBALL_FONT_BOLD,
        verts + quads * 24);
    custom_white_text_quads += line_quads;
    quads += line_quads;
    custom_key_text_first_quad = quads;
    line_quads = emit_efootball_line(
        "B", 1, 0.745f * (float)screen_width - text_gh * 0.30f,
        helper_y - text_gh * 0.5f, text_gh, EFOOTBALL_FONT_BOLD,
        verts + quads * 24);
    custom_key_text_quads += line_quads;
    quads += line_quads;
    line_quads = emit_efootball_line(
        "A", 1, 0.875f * (float)screen_width - text_gh * 0.30f,
        helper_y - text_gh * 0.5f, text_gh, EFOOTBALL_FONT_BOLD,
        verts + quads * 24);
    custom_key_text_quads += line_quads;
    quads += line_quads;
  } else if (custom_2p_transition) {
    // Keep the native Game Plan hand-off covered while presenting the actual
    // matchup, without another card competing with the background artwork.
    custom_backdrop_quads = emit_image_rect(
        0.0f, 0.0f, (float)screen_width, (float)screen_height,
        verts + quads * 24);
    quads += custom_backdrop_quads;
    const float badge_size = 0.215f * (float)screen_height;
    const float badge_y = 0.285f * (float)screen_height;
    static const float team_center_x[2] = {0.325f, 0.675f};
    for (uint32_t side = 0; side < 2; side++) {
      const float badge_x =
          team_center_x[side] * (float)screen_width - badge_size * 0.5f;
      custom_icon_quads += emit_badge(
          pes_controller_2p_prematch_hub_badge(side), badge_x, badge_y,
          badge_size, badge_size, verts + quads * 24);
      quads++;
    }

    custom_white_text_first_quad = quads;
    const float name_y = badge_y + badge_size +
                         0.030f * (float)screen_height;
    const float max_name_w = 0.285f * (float)screen_width;
    for (uint32_t side = 0; side < 2; side++) {
      const char *team = pes_controller_2p_prematch_hub_team_name(side);
      const int team_len = (int)strlen(team);
      float team_gh = (float)screen_height / 31.0f;
      float team_w = measure_efootball_line(
          team, team_len, team_gh, EFOOTBALL_FONT_STENCIL);
      if (team_w > max_name_w && team_w > 0.0f) {
        team_gh *= max_name_w / team_w;
        team_w = measure_efootball_line(
            team, team_len, team_gh, EFOOTBALL_FONT_STENCIL);
      }
      const int line_quads = emit_efootball_line(
          team, team_len,
          team_center_x[side] * (float)screen_width - team_w * 0.5f,
          name_y, team_gh, EFOOTBALL_FONT_STENCIL,
          verts + quads * 24);
      custom_white_text_quads += line_quads;
      quads += line_quads;
    }
    const char *versus = "VS";
    const float versus_gh = (float)screen_height / 22.0f;
    const float versus_w = measure_efootball_line(
        versus, 2, versus_gh, EFOOTBALL_FONT_BOLD);
    const int versus_quads = emit_efootball_line(
        versus, 2, ((float)screen_width - versus_w) * 0.5f,
        badge_y + (badge_size - versus_gh) * 0.5f,
        versus_gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
    custom_white_text_quads += versus_quads;
    quads += versus_quads;
  } else if (custom_hub_settings_popup) {
    // Match Settings is a child of the pre-match hub, but it gets its own
    // console-style page: dark title band, light selected row, blue value
    // capsules and eFootball typography over the same custom background.
    // TIME (DAY/NIGHT) has moved to Stadium. The hub therefore maps its four
    // visible rows to native Match Settings indices 1..4.
    const uint32_t item_count = PES_MATCH_SETTINGS_COUNT - 1u;
    const uint32_t native_focus =
        pes_controller_custom_match_settings_focus();
    const uint32_t focus = native_focus > 0 ? native_focus - 1u : 0u;
    const float panel_x = 0.17f * (float)screen_width;
    const float panel_y = 0.095f * (float)screen_height;
    const float panel_w = 0.66f * (float)screen_width;
    const float panel_h = 0.700f * (float)screen_height;
    const float panel_radius = 0.025f * (float)screen_height;
    const float header_h = 0.125f * (float)screen_height;
    const float row_x = panel_x + 0.040f * (float)screen_width;
    const float row_w = panel_w - 0.080f * (float)screen_width;
    const float row_y0 = panel_y + header_h +
                         0.045f * (float)screen_height;
    const float row_h = 0.078f * (float)screen_height;
    const float row_step = 0.105f * (float)screen_height;
    const float value_w = 0.205f * (float)screen_width;
    const float value_h = 0.058f * (float)screen_height;
    // Keep the focused row symmetric. Move the selector group left so both
    // arrows live inside the white surface instead of stretching that surface
    // toward the panel's right edge.
    const float value_x = panel_x + panel_w -
                          0.070f * (float)screen_width - value_w;
    const float key_r = 0.021f * (float)screen_height;
    const float action_key_x = 0.875f * (float)screen_width;
    const float back_key_x = 0.745f * (float)screen_width;
    const float key_y = 0.958f * (float)screen_height;

    custom_backdrop_quads = emit_image_rect(
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
    const float selector_inset = 0.006f * (float)screen_height;
    custom_selected_style = (RoundedRectStyle){
        row_w - selector_inset * 2.0f,
        row_h - selector_inset * 2.0f,
        0.014f * (float)screen_height};
    custom_selected_quads = emit_round_rect_quad(
        row_x + selector_inset,
        row_y0 + row_step * (float)focus + selector_inset,
        row_w - selector_inset * 2.0f,
        row_h - selector_inset * 2.0f,
        verts + quads * 24);
    quads += custom_selected_quads;
    for (uint32_t row = 0; row + 1 < item_count; row++) {
      const float rule_y = row_y0 + row_step * (float)(row + 1) -
                           (row_step - row_h) * 0.5f;
      custom_rule_quads += emit_rect(
          row_x, rule_y, row_w, (float)screen_height / 720.0f,
          verts + quads * 24);
      quads++;
    }
    for (uint32_t item = 0; item < item_count; item++) {
      const float value_y = row_y0 + row_step * (float)item +
                            (row_h - value_h) * 0.5f;
      custom_value_plate_style =
          (RoundedRectStyle){value_w, value_h, value_h * 0.5f};
      custom_value_plate_quads += emit_round_rect_quad(
          value_x, value_y, value_w, value_h, verts + quads * 24);
      quads++;
    }
    const float arrow_w = 0.007f * (float)screen_width;
    const float arrow_h = 0.012f * (float)screen_height;
    for (uint32_t item = 0; item < item_count; item++) {
      const float center_y = row_y0 + row_step * (float)item + row_h * 0.5f;
      const float left_x = value_x - 0.014f * (float)screen_width;
      custom_arrow_quads += emit_triangle(
          left_x + arrow_w, center_y - arrow_h,
          left_x - arrow_w, center_y,
          left_x + arrow_w, center_y + arrow_h,
          verts + quads * 24);
      quads++;
      const float right_x = value_x + value_w +
                            0.014f * (float)screen_width;
      custom_arrow_quads += emit_triangle(
          right_x - arrow_w, center_y - arrow_h,
          right_x + arrow_w, center_y,
          right_x - arrow_w, center_y + arrow_h,
          verts + quads * 24);
      quads++;
    }
    custom_action_key_bg_quads = emit_circle_quad(
        action_key_x, key_y, key_r, verts + quads * 24);
    quads += custom_action_key_bg_quads;
    custom_back_key_bg_quads = emit_circle_quad(
        back_key_x, key_y, key_r, verts + quads * 24);
    quads += custom_back_key_bg_quads;

    const float title_gh = (float)screen_height / 27.0f;
    const float label_gh = (float)screen_height / 42.0f;
    const float value_gh = (float)screen_height / 43.0f;
    custom_dark_text_first_quad = quads;
    int line_quads = 0;
    custom_focus_text_first_quad = quads;
    if (focus < item_count) {
      const char *label =
          pes_controller_custom_match_settings_label(focus + 1u);
      line_quads = emit_efootball_line(
          label, (int)strlen(label), row_x + 0.020f * (float)screen_width,
          row_y0 + row_step * (float)focus +
              (row_h - label_gh) * 0.5f,
          label_gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
      custom_focus_text_quads += line_quads;
      quads += line_quads;
    }
    custom_white_text_first_quad = quads;
    for (uint32_t item = 0; item < item_count; item++) {
      if (item == focus)
        continue;
      const char *label =
          pes_controller_custom_match_settings_label(item + 1u);
      line_quads = emit_efootball_line(
          label, (int)strlen(label), row_x + 0.020f * (float)screen_width,
          row_y0 + row_step * (float)item +
              (row_h - label_gh) * 0.5f,
          label_gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
      custom_white_text_quads += line_quads;
      quads += line_quads;
    }
    const char *title = "GENERAL SETTINGS";
    const float title_w = measure_efootball_line(
        title, (int)strlen(title), title_gh, EFOOTBALL_FONT_BOLD);
    line_quads = emit_efootball_line(
        title, (int)strlen(title), panel_x + (panel_w - title_w) * 0.5f,
        panel_y + (header_h - title_gh) * 0.5f, title_gh,
        EFOOTBALL_FONT_BOLD, verts + quads * 24);
    custom_white_text_quads += line_quads;
    quads += line_quads;
    for (uint32_t item = 0; item < item_count; item++) {
      const char *value =
          pes_controller_custom_match_settings_value(item + 1u);
      const float width = measure_efootball_line(
          value, (int)strlen(value), value_gh, EFOOTBALL_FONT_BOLD);
      const float value_y = row_y0 + row_step * (float)item +
                            (row_h - value_gh) * 0.5f;
      line_quads = emit_efootball_line(
          value, (int)strlen(value), value_x + (value_w - width) * 0.5f,
          value_y, value_gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
      custom_white_text_quads += line_quads;
      quads += line_quads;
    }
    const float button_gh = (float)screen_height / 58.0f;
    line_quads = emit_efootball_line(
        "CHANGE", 6, 0.900f * (float)screen_width,
        key_y - button_gh * 0.5f, button_gh,
        EFOOTBALL_FONT_BOLD, verts + quads * 24);
    custom_white_text_quads += line_quads;
    quads += line_quads;
    line_quads = emit_efootball_line(
        "BACK", 4, 0.770f * (float)screen_width,
        key_y - button_gh * 0.5f, button_gh,
        EFOOTBALL_FONT_BOLD, verts + quads * 24);
    custom_white_text_quads += line_quads;
    quads += line_quads;
    custom_key_text_first_quad = quads;
    line_quads = emit_efootball_line(
        "A", 1, action_key_x - button_gh * 0.32f,
        key_y - button_gh * 0.5f, button_gh, EFOOTBALL_FONT_BOLD,
        verts + quads * 24);
    custom_key_text_quads += line_quads;
    quads += line_quads;
    line_quads = emit_efootball_line(
        "B", 1, back_key_x - button_gh * 0.32f,
        key_y - button_gh * 0.5f, button_gh, EFOOTBALL_FONT_BOLD,
        verts + quads * 24);
    custom_key_text_quads += line_quads;
    quads += line_quads;
  } else if (custom_hub_choice_page) {
    // Kits and Stadium use the same native-console settings language: one
    // modal card, a dark title band, white focused row, blue value capsule,
    // and arrows that remain completely inside the selected surface.
    const uint32_t focus =
        pes_controller_2p_prematch_hub_page_focus() & 1u;
    const float panel_x = 0.17f * (float)screen_width;
    const float panel_y = 0.075f * (float)screen_height;
    const float panel_w = 0.66f * (float)screen_width;
    const float panel_h = 0.790f * (float)screen_height;
    const float panel_radius = 0.025f * (float)screen_height;
    const float header_h = 0.125f * (float)screen_height;
    const float row_x = panel_x + 0.040f * (float)screen_width;
    const float row_w = panel_w - 0.080f * (float)screen_width;
    const float content_y = panel_y + header_h +
                            0.045f * (float)screen_height;
    const float row_y0 = content_y +
                         (custom_hub_kits_page
                              ? 0.330f * (float)screen_height
                              : 0.0f);
    const float row_h = 0.082f * (float)screen_height;
    const float row_step = 0.110f * (float)screen_height;
    const float value_w = 0.205f * (float)screen_width;
    const float value_h = 0.058f * (float)screen_height;
    const float value_x = panel_x + panel_w -
                          0.070f * (float)screen_width - value_w;
    const float key_r = 0.021f * (float)screen_height;
    const float action_key_x = 0.875f * (float)screen_width;
    const float back_key_x = 0.745f * (float)screen_width;
    const float key_y = 0.958f * (float)screen_height;

    custom_backdrop_quads = emit_image_rect(
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

    const float selector_inset = 0.006f * (float)screen_height;
    custom_selected_style = (RoundedRectStyle){
        row_w - selector_inset * 2.0f,
        row_h - selector_inset * 2.0f,
        0.014f * (float)screen_height};
    custom_selected_quads = emit_round_rect_quad(
        row_x + selector_inset,
        row_y0 + row_step * (float)focus + selector_inset,
        row_w - selector_inset * 2.0f,
        row_h - selector_inset * 2.0f, verts + quads * 24);
    quads += custom_selected_quads;

    if (custom_hub_kits_page) {
      const float preview_y = content_y;
      const float preview_w = 0.245f * (float)screen_width;
      const float preview_x[2] = {
          panel_x + 0.055f * (float)screen_width,
          panel_x + panel_w - 0.055f * (float)screen_width - preview_w};
      const float shirt_size = 0.20f * (float)screen_height;
      const float shirt_y = preview_y + 0.065f * (float)screen_height;
      for (uint32_t side = 0; side < 2; side++) {
        if (!(gl.native_uniform_valid_mask & (1u << side)))
          continue;
        custom_kit_preview_first_quad[side] = quads;
        custom_kit_preview_side_quads[side] = emit_image_rect(
            preview_x[side] + (preview_w - shirt_size) * 0.5f, shirt_y,
            shirt_size, shirt_size, verts + quads * 24);
        custom_kit_preview_quads += custom_kit_preview_side_quads[side];
        quads += custom_kit_preview_side_quads[side];
      }
    }

    custom_rule_quads += emit_rect(
        row_x, row_y0 + row_step - (row_step - row_h) * 0.5f,
        row_w, (float)screen_height / 720.0f, verts + quads * 24);
    quads++;
    for (uint32_t row = 0; row < 2; row++) {
      const float value_y = row_y0 + row_step * (float)row +
                            (row_h - value_h) * 0.5f;
      custom_value_plate_style =
          (RoundedRectStyle){value_w, value_h, value_h * 0.5f};
      custom_value_plate_quads += emit_round_rect_quad(
          value_x, value_y, value_w, value_h, verts + quads * 24);
      quads++;
    }
    const float arrow_w = 0.007f * (float)screen_width;
    const float arrow_h = 0.012f * (float)screen_height;
    for (uint32_t row = 0; row < 2; row++) {
      const float center_y = row_y0 + row_step * (float)row + row_h * 0.5f;
      const float left_x = value_x - 0.014f * (float)screen_width;
      custom_arrow_quads += emit_triangle(
          left_x + arrow_w, center_y - arrow_h,
          left_x - arrow_w, center_y,
          left_x + arrow_w, center_y + arrow_h,
          verts + quads * 24);
      quads++;
      const float right_x = value_x + value_w +
                            0.014f * (float)screen_width;
      custom_arrow_quads += emit_triangle(
          right_x - arrow_w, center_y - arrow_h,
          right_x + arrow_w, center_y,
          right_x - arrow_w, center_y + arrow_h,
          verts + quads * 24);
      quads++;
    }
    custom_action_key_bg_quads = emit_circle_quad(
        action_key_x, key_y, key_r, verts + quads * 24);
    quads += custom_action_key_bg_quads;
    custom_back_key_bg_quads = emit_circle_quad(
        back_key_x, key_y, key_r, verts + quads * 24);
    quads += custom_back_key_bg_quads;
    const float title_gh = (float)screen_height / 27.0f;
    const float label_gh = (float)screen_height / 42.0f;
    const float value_gh = (float)screen_height / 43.0f;
    int line_quads = 0;
    custom_dark_text_first_quad = quads;
    custom_focus_text_first_quad = quads;
    const char *focused_label = custom_hub_kits_page
                                    ? (focus ? "AWAY KIT" : "HOME KIT")
                                    : (focus ? "MATCH TIME" : "STADIUM");
    line_quads = emit_efootball_line(
        focused_label, (int)strlen(focused_label),
        row_x + 0.020f * (float)screen_width,
        row_y0 + row_step * (float)focus + (row_h - label_gh) * 0.5f,
        label_gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
    custom_focus_text_quads += line_quads;
    quads += line_quads;

    custom_white_text_first_quad = quads;
    if (custom_hub_kits_page) {
      const float preview_y = content_y;
      const float preview_w = 0.245f * (float)screen_width;
      const float preview_x[2] = {
          panel_x + 0.055f * (float)screen_width,
          panel_x + panel_w - 0.055f * (float)screen_width - preview_w};
      for (uint32_t side = 0; side < 2; side++) {
        const char *team = pes_controller_2p_prematch_hub_team_name(side);
        const float team_w = measure_efootball_line(
            team, (int)strlen(team), label_gh, EFOOTBALL_FONT_STENCIL);
        line_quads = emit_efootball_line(
            team, (int)strlen(team),
            preview_x[side] + (preview_w - team_w) * 0.5f,
            preview_y + 0.018f * (float)screen_height, label_gh,
            EFOOTBALL_FONT_STENCIL, verts + quads * 24);
        custom_white_text_quads += line_quads;
        quads += line_quads;
      }
    }
    const char *other_label = custom_hub_kits_page
                                  ? (focus ? "HOME KIT" : "AWAY KIT")
                                  : (focus ? "STADIUM" : "MATCH TIME");
    const uint32_t other_row = focus ^ 1u;
    line_quads = emit_efootball_line(
        other_label, (int)strlen(other_label),
        row_x + 0.020f * (float)screen_width,
        row_y0 + row_step * (float)other_row +
            (row_h - label_gh) * 0.5f,
        label_gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
    custom_white_text_quads += line_quads;
    quads += line_quads;
    const char *title = custom_hub_kits_page ? "KITS" : "STADIUM";
    const float title_w = measure_efootball_line(
        title, (int)strlen(title), title_gh, EFOOTBALL_FONT_BOLD);
    line_quads = emit_efootball_line(
        title, (int)strlen(title), panel_x + (panel_w - title_w) * 0.5f,
        panel_y + (header_h - title_gh) * 0.5f, title_gh,
        EFOOTBALL_FONT_BOLD, verts + quads * 24);
    custom_white_text_quads += line_quads;
    quads += line_quads;
    for (uint32_t row = 0; row < 2; row++) {
      char kit_value[24];
      const char *value = NULL;
      if (custom_hub_kits_page) {
        const uint32_t kit_number =
            pes_controller_2p_prematch_hub_kit_number(row);
        const uint32_t count =
            pes_controller_2p_prematch_hub_kit_count(row);
        snprintf(kit_value, sizeof(kit_value), "KIT %u%s%u",
                 kit_number ? kit_number : 1u, count > 1 ? " / " : "",
                 count > 1 ? count : 0u);
        if (count <= 1)
          snprintf(kit_value, sizeof(kit_value), "KIT %u",
                   kit_number ? kit_number : 1u);
        value = kit_value;
      } else if (row == 0) {
        static const char *const stadium_options[3] = {
            "AUTO", "HOME", "AWAY"};
        value = stadium_options[
            pes_controller_2p_prematch_hub_stadium_index()];
      } else {
        value = pes_controller_custom_match_settings_value(0);
      }
      const float width = measure_efootball_line(
          value, (int)strlen(value), value_gh, EFOOTBALL_FONT_BOLD);
      line_quads = emit_efootball_line(
          value, (int)strlen(value), value_x + (value_w - width) * 0.5f,
          row_y0 + row_step * (float)row + (row_h - value_gh) * 0.5f,
          value_gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
      custom_white_text_quads += line_quads;
      quads += line_quads;
    }
    const float button_gh = (float)screen_height / 58.0f;
    line_quads = emit_efootball_line(
        "CHANGE", 6, 0.900f * (float)screen_width,
        key_y - button_gh * 0.5f, button_gh,
        EFOOTBALL_FONT_BOLD, verts + quads * 24);
    custom_white_text_quads += line_quads;
    quads += line_quads;
    line_quads = emit_efootball_line(
        "BACK", 4, 0.770f * (float)screen_width,
        key_y - button_gh * 0.5f, button_gh,
        EFOOTBALL_FONT_BOLD, verts + quads * 24);
    custom_white_text_quads += line_quads;
    quads += line_quads;
    custom_key_text_first_quad = quads;
    line_quads = emit_efootball_line(
        "A", 1, action_key_x - button_gh * 0.32f,
        key_y - button_gh * 0.5f, button_gh, EFOOTBALL_FONT_BOLD,
        verts + quads * 24);
    custom_key_text_quads += line_quads;
    quads += line_quads;
    line_quads = emit_efootball_line(
        "B", 1, back_key_x - button_gh * 0.32f,
        key_y - button_gh * 0.5f, button_gh, EFOOTBALL_FONT_BOLD,
        verts + quads * 24);
    custom_key_text_quads += line_quads;
    quads += line_quads;
  } else if (custom_2p_prematch_hub) {
    // The pre-match hub is deliberately a thin full-screen layer: the same
    // field-pattern background as team selection, two team columns, and a
    // compact controller-owned action rail.  P1 owns this page; P2's state is
    // presentation-only until the user returns to team selection.
    const uint32_t page = pes_controller_2p_prematch_hub_page();
    const uint32_t hub_focus = pes_controller_2p_prematch_hub_focus();
    const uint32_t page_side = pes_controller_2p_prematch_hub_page_focus();
    const float header_y = 0.035f * (float)screen_height;
    const float header_h = 0.105f * (float)screen_height;
    const float column_x[2] = {0.035f * (float)screen_width,
                               0.535f * (float)screen_width};
    const float column_w = 0.430f * (float)screen_width;
    const float card_y = 0.205f * (float)screen_height;
    const float card_h = 0.585f * (float)screen_height;
    const float badge_size = 0.155f * (float)screen_height;
    const float action_y = 0.855f * (float)screen_height;
    const float action_h = 0.064f * (float)screen_height;
    const float action_gap = 0.012f * (float)screen_width;
    const float action_w =
        (0.93f * (float)screen_width - 4.0f * action_gap) / 5.0f;
    static const char *const action_labels[PES_2P_PREMATCH_HUB_BUTTON_COUNT] = {
        "STADIUM", "KITS", "KICK OFF", "GAME PLAN", "GENERAL SETTING"};

    custom_backdrop_quads = emit_image_rect(
        0.0f, 0.0f, (float)screen_width, (float)screen_height,
        verts + quads * 24);
    quads += custom_backdrop_quads;

    // These two layers are plain rectangles; keeping round-rect disabled is
    // important because emit_rect intentionally pins UVs to (0,0).
    custom_header_style = (RoundedRectStyle){0};
    for (uint32_t side = 0; side < 2; side++) {
      custom_header_round_quads += emit_rect(
          column_x[side], header_y, column_w, header_h,
          verts + quads * 24);
      quads++;
    }

    custom_selected_style = (RoundedRectStyle){0};
    for (uint32_t side = 0; side < 2; side++) {
      custom_selected_quads += emit_rect(
          column_x[side], card_y, column_w, card_h,
          verts + quads * 24);
      quads++;
    }

    custom_action_button_style =
        (RoundedRectStyle){action_w, action_h, 0.018f * (float)screen_height};
    for (uint32_t action = 0;
         action < PES_2P_PREMATCH_HUB_BUTTON_COUNT; action++) {
      const float x = 0.035f * (float)screen_width +
                      (action_w + action_gap) * (float)action;
      custom_action_button_quads += emit_round_rect_quad(
          x, action_y, action_w, action_h, verts + quads * 24);
      quads++;
    }

    // Badge atlas quads are emitted after the button category because the
    // shared draw pass renders them after action buttons.
    if (page == PES_2P_PREMATCH_HUB_PAGE_MAIN ||
        page == PES_2P_PREMATCH_HUB_PAGE_KITS) {
      for (uint32_t side = 0; side < 2; side++) {
        const float x = column_x[side] + column_w * 0.055f;
        const float y = card_y + card_h * 0.24f;
        custom_icon_quads += emit_badge(
            pes_controller_2p_prematch_hub_badge(side), x, y, badge_size,
            badge_size, verts + quads * 24);
        quads++;
      }
    }

    const float header_gh = (float)screen_height / 27.0f;
    const float title_gh = (float)screen_height / 47.0f;
    const float body_gh = (float)screen_height / 52.0f;
    const float lineup_gh = (float)screen_height / 50.0f;
    const float page_title_gh = (float)screen_height / 34.0f;
    const float action_label_gh = (float)screen_height / 46.0f;

    custom_dark_text_first_quad = quads;
    int line_quads = 0;
    if (page == PES_2P_PREMATCH_HUB_PAGE_MAIN) {
      for (uint32_t side = 0; side < 2; side++) {
        const char *team = pes_controller_2p_prematch_hub_team_name(side);
        line_quads = emit_efootball_line(
            team, (int)strlen(team), column_x[side] + 0.028f * (float)screen_width,
            card_y + 0.030f * (float)screen_height, title_gh,
            EFOOTBALL_FONT_STENCIL, verts + quads * 24);
        custom_dark_text_quads += line_quads;
        quads += line_quads;
        const uint32_t count =
            pes_controller_2p_prematch_hub_lineup_count(side);
        const float lineup_x = column_x[side] + column_w * 0.405f;
        for (uint32_t index = 0; index < count; index++) {
          const char *name =
              pes_controller_2p_prematch_hub_lineup_name(side, index);
          line_quads = emit_efootball_line(
              name, (int)strlen(name), lineup_x,
              card_y + 0.055f * (float)screen_height +
                  (float)index * 0.043f * (float)screen_height,
              lineup_gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
          custom_dark_text_quads += line_quads;
          quads += line_quads;
        }
      }
    } else if (page == PES_2P_PREMATCH_HUB_PAGE_KITS) {
      line_quads = emit_efootball_line(
          "SELECT KITS", 11, (float)screen_width * 0.5f -
                         measure_efootball_line("SELECT KITS", 11,
                                                page_title_gh,
                                                EFOOTBALL_FONT_BOLD) * 0.5f,
          card_y + 0.030f * (float)screen_height, page_title_gh,
          EFOOTBALL_FONT_BOLD, verts + quads * 24);
      custom_dark_text_quads += line_quads;
      quads += line_quads;
      for (uint32_t side = 0; side < 2; side++) {
        const char *team = pes_controller_2p_prematch_hub_team_name(side);
        if (side != page_side) {
          line_quads = emit_efootball_line(
              team, (int)strlen(team),
              column_x[side] + 0.028f * (float)screen_width,
              card_y + 0.030f * (float)screen_height, title_gh,
              EFOOTBALL_FONT_STENCIL, verts + quads * 24);
          custom_dark_text_quads += line_quads;
          quads += line_quads;
        }
        const uint32_t count = pes_controller_2p_prematch_hub_kit_count(side);
        const uint32_t kit_number =
            pes_controller_2p_prematch_hub_kit_number(side);
        char kit_text[40];
        if (count && kit_number)
          snprintf(kit_text, sizeof(kit_text), "%s KIT %u  (%u OF %u)",
                   side ? "AWAY" : "HOME", kit_number,
                   pes_controller_2p_prematch_hub_kit_index(side) + 1u,
                   count);
        else
          snprintf(kit_text, sizeof(kit_text), "%s KIT UNAVAILABLE",
                   side ? "AWAY" : "HOME");
        line_quads = emit_efootball_line(
            kit_text, (int)strlen(kit_text),
            column_x[side] + column_w * 0.405f,
            card_y + 0.19f * (float)screen_height, body_gh,
            EFOOTBALL_FONT_BOLD, verts + quads * 24);
        custom_dark_text_quads += line_quads;
        quads += line_quads;
        const char *hint = side == page_side ? "UP/DOWN CHANGE KIT"
                                             : "LEFT/RIGHT SELECT TEAM";
        line_quads = emit_efootball_line(
            hint, (int)strlen(hint), column_x[side] + column_w * 0.405f,
            card_y + 0.27f * (float)screen_height, lineup_gh,
            EFOOTBALL_FONT_BOLD, verts + quads * 24);
        custom_dark_text_quads += line_quads;
        quads += line_quads;
      }
    } else {
      const char *stadium_title = "STADIUM";
      static const char *const stadium_options[3] = {
          "AUTO STADIUM", "HOME STADIUM", "AWAY STADIUM"};
      const uint32_t stadium_focus =
          pes_controller_2p_prematch_hub_stadium_index();
      line_quads = emit_efootball_line(
          stadium_title, 7,
          (float)screen_width * 0.5f -
              measure_efootball_line(stadium_title, 7, page_title_gh,
                                     EFOOTBALL_FONT_BOLD) * 0.5f,
          card_y + 0.16f * (float)screen_height, page_title_gh,
          EFOOTBALL_FONT_BOLD, verts + quads * 24);
      custom_dark_text_quads += line_quads;
      quads += line_quads;
      const char *stadium_hint = "UP/DOWN SELECT  -  B BACK";
      line_quads = emit_efootball_line(
          stadium_hint, (int)strlen(stadium_hint),
          (float)screen_width * 0.5f -
              measure_efootball_line(stadium_hint, (int)strlen(stadium_hint),
                                     lineup_gh, EFOOTBALL_FONT_BOLD) * 0.5f,
          card_y + 0.40f * (float)screen_height, lineup_gh,
          EFOOTBALL_FONT_BOLD, verts + quads * 24);
      custom_dark_text_quads += line_quads;
      quads += line_quads;
      for (uint32_t option = 0; option < 3; option++) {
        if (option == stadium_focus)
          continue;
        const char *stadium_value = stadium_options[option];
        const float value_width = measure_efootball_line(
            stadium_value, (int)strlen(stadium_value), title_gh,
            EFOOTBALL_FONT_STENCIL);
        line_quads = emit_efootball_line(
            stadium_value, (int)strlen(stadium_value),
            (float)screen_width * 0.5f - value_width * 0.5f,
            card_y + (0.235f + 0.080f * (float)option) *
                         (float)screen_height,
            title_gh, EFOOTBALL_FONT_STENCIL, verts + quads * 24);
        custom_dark_text_quads += line_quads;
        quads += line_quads;
      }
    }

    custom_white_text_first_quad = quads;
    for (uint32_t side = 0; side < 2; side++) {
      const char *header = side == 0 ? "HOME" : "AWAY";
      const float width = measure_efootball_line(
          header, (int)strlen(header), header_gh, EFOOTBALL_FONT_BOLD);
      line_quads = emit_efootball_line(
          header, (int)strlen(header),
          column_x[side] + (column_w - width) * 0.5f,
          header_y + 0.020f * (float)screen_height, header_gh,
          EFOOTBALL_FONT_BOLD, verts + quads * 24);
      custom_white_text_quads += line_quads;
      quads += line_quads;
    }
    const char *page_title = page == PES_2P_PREMATCH_HUB_PAGE_KITS
                                 ? "KITS"
                                 : page == PES_2P_PREMATCH_HUB_PAGE_STADIUM
                                       ? "STADIUM"
                                       : "PRE-MATCH";
    const float page_width = measure_efootball_line(
        page_title, (int)strlen(page_title), body_gh, EFOOTBALL_FONT_BOLD);
    line_quads = emit_efootball_line(
        page_title, (int)strlen(page_title),
        (float)screen_width * 0.5f - page_width * 0.5f,
        header_y + header_h - body_gh - 0.015f * (float)screen_height,
        body_gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
    custom_white_text_quads += line_quads;
    quads += line_quads;

    custom_hub_button_text_first_quad = quads;
    for (uint32_t action = 0;
         action < PES_2P_PREMATCH_HUB_BUTTON_COUNT; action++) {
      const float x = 0.035f * (float)screen_width +
                      (action_w + action_gap) * (float)action;
      const char *label = action_labels[action];
      const float width = measure_efootball_line(
          label, (int)strlen(label), action_label_gh, EFOOTBALL_FONT_BOLD);
      line_quads = emit_efootball_line(
          label, (int)strlen(label), x + (action_w - width) * 0.5f,
          action_y + (action_h - action_label_gh) * 0.5f, action_label_gh,
          EFOOTBALL_FONT_BOLD, verts + quads * 24);
      custom_hub_button_text_quads += line_quads;
      quads += line_quads;
    }
    custom_focus_text_first_quad = quads;
    if (page == PES_2P_PREMATCH_HUB_PAGE_KITS) {
      const char *team = pes_controller_2p_prematch_hub_team_name(page_side);
      line_quads = emit_efootball_line(
          team, (int)strlen(team),
          column_x[page_side] + 0.028f * (float)screen_width,
          card_y + 0.030f * (float)screen_height, title_gh,
          EFOOTBALL_FONT_STENCIL, verts + quads * 24);
      custom_focus_text_quads += line_quads;
      quads += line_quads;
    } else if (page == PES_2P_PREMATCH_HUB_PAGE_STADIUM) {
      static const char *const stadium_options[3] = {
          "AUTO STADIUM", "HOME STADIUM", "AWAY STADIUM"};
      const uint32_t stadium_focus =
          pes_controller_2p_prematch_hub_stadium_index();
      const char *stadium_value = stadium_options[stadium_focus];
      const float stadium_width = measure_efootball_line(
          stadium_value, (int)strlen(stadium_value), title_gh,
          EFOOTBALL_FONT_STENCIL);
      line_quads = emit_efootball_line(
          stadium_value, (int)strlen(stadium_value),
          (float)screen_width * 0.5f - stadium_width * 0.5f,
          card_y + (0.235f + 0.080f * (float)stadium_focus) *
                       (float)screen_height,
          title_gh, EFOOTBALL_FONT_STENCIL, verts + quads * 24);
      custom_focus_text_quads += line_quads;
      quads += line_quads;
    }
    if (hub_focus < PES_2P_PREMATCH_HUB_BUTTON_COUNT) {
      const float x = 0.035f * (float)screen_width +
                      (action_w + action_gap) * (float)hub_focus;
      const char *label = action_labels[hub_focus];
      const float width = measure_efootball_line(
          label, (int)strlen(label), action_label_gh, EFOOTBALL_FONT_BOLD);
      line_quads = emit_efootball_line(
          label, (int)strlen(label), x + (action_w - width) * 0.5f,
          action_y + (action_h - action_label_gh) * 0.5f, action_label_gh,
          EFOOTBALL_FONT_BOLD, verts + quads * 24);
      custom_focus_text_quads += line_quads;
      quads += line_quads;
    }
    (void)page_side;
  } else if (custom_team_popup) {
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
    // Mirror TouchKickerSelect's compact list, but retain our stable native
    // controller state machine. The viewport follows focus by one row instead
    // of snapping between pages, so no touchscreen swipe is required.
    const float panel_x = 0.160f * (float)screen_width;
    const float panel_y = 0.060f * (float)screen_height;
    const float panel_w = 0.680f * (float)screen_width;
    const float panel_h = 0.880f * (float)screen_height;
    const float panel_radius = 0.012f * (float)screen_height;
    const float header_h = 0.100f * (float)screen_height;
    const float row_x = panel_x + 0.020f * (float)screen_width;
    const float row_y0 = panel_y + 0.120f * (float)screen_height;
    const float row_w = panel_w - 0.050f * (float)screen_width;
    const float row_h = 0.077f * (float)screen_height;
    const float row_step = 0.085f * (float)screen_height;
    const float divider_h = fmaxf(1.0f, (float)screen_height / 720.0f);
    const uint32_t count = pes_controller_set_piece_selector_count();
    uint32_t focus = pes_controller_set_piece_selector_focus();
    if (count && focus >= count)
      focus = count - 1u;
    const uint32_t first_visible =
        focus < PES_SET_PIECE_SELECTOR_VISIBLE_ROWS
            ? 0u
            : focus - PES_SET_PIECE_SELECTOR_VISIBLE_ROWS + 1u;
    const uint32_t visible_count =
        count > first_visible
            ? ((count - first_visible) < PES_SET_PIECE_SELECTOR_VISIBLE_ROWS
                   ? count - first_visible
                   : PES_SET_PIECE_SELECTOR_VISIBLE_ROWS)
            : 0u;
    const uint32_t local_focus = focus - first_visible;
    const float selected_y = row_y0 + (float)local_focus * row_step;

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
        row_w, row_h, 0.006f * (float)screen_height};
    if (count) {
      custom_selected_quads = emit_round_rect_quad(
          row_x, selected_y, row_w, row_h, verts + quads * 24);
      quads += custom_selected_quads;
    }
    custom_rule_quads += emit_rect(
        panel_x, panel_y + header_h, panel_w, divider_h,
        verts + quads * 24);
    quads++;
    for (uint32_t slot = 0; slot < visible_count; slot++) {
      const float rule_y = row_y0 + (float)(slot + 1u) * row_step -
                           (row_step - row_h) * 0.5f;
      custom_rule_quads += emit_rect(
          row_x, rule_y, row_w, divider_h, verts + quads * 24);
      quads++;
    }
    if (count > PES_SET_PIECE_SELECTOR_VISIBLE_ROWS) {
      const float rail_x = panel_x + panel_w -
                           0.013f * (float)screen_width;
      const float rail_y = row_y0;
      const float rail_w = fmaxf(2.0f, 0.0022f * (float)screen_width);
      const float rail_h =
          row_step * (float)PES_SET_PIECE_SELECTOR_VISIBLE_ROWS;
      custom_rule_quads += emit_rect(
          rail_x, rail_y, rail_w, rail_h, verts + quads * 24);
      quads++;
      const float thumb_h = rail_h *
                            (float)PES_SET_PIECE_SELECTOR_VISIBLE_ROWS /
                            (float)count;
      const uint32_t max_first =
          count - PES_SET_PIECE_SELECTOR_VISIBLE_ROWS;
      const float thumb_y = rail_y +
                            (rail_h - thumb_h) *
                                (float)first_visible / (float)max_first;
      custom_value_plate_style =
          (RoundedRectStyle){rail_w, thumb_h, rail_w * 0.5f};
      custom_value_plate_quads = emit_round_rect_quad(
          rail_x, thumb_y, rail_w, thumb_h, verts + quads * 24);
      quads += custom_value_plate_quads;
    }

    // Use the stock selector's checkmark language instead of spelling a
    // debug-style V. Two vector strokes remain sharp without an extra atlas.
    for (uint32_t slot = 0; slot < visible_count; slot++) {
      const uint32_t player_index = first_visible + slot;
      if (!pes_controller_set_piece_selector_current_at(player_index))
        continue;
      const float card_y = row_y0 + (float)slot * row_step;
      const float check_x = row_x + row_w - 0.020f * (float)screen_width;
      const float check_y = card_y + row_h * 0.5f;
      const float check_thickness =
          fmaxf(2.0f, 0.0042f * (float)screen_height);
      custom_arrow_quads += emit_segment(
          check_x - 0.009f * (float)screen_width,
          check_y - 0.001f * (float)screen_height,
          check_x - 0.003f * (float)screen_width,
          check_y + 0.008f * (float)screen_height, check_thickness,
          verts + quads * 24);
      quads++;
      custom_arrow_quads += emit_segment(
          check_x - 0.003f * (float)screen_width,
          check_y + 0.008f * (float)screen_height,
          check_x + 0.010f * (float)screen_width,
          check_y - 0.010f * (float)screen_height, check_thickness,
          verts + quads * 24);
      quads++;
    }

    // The stock mobile list represents preferred foot with a compact glyph.
    // Use a neutral circular plate plus R/L in our atlas-backed renderer so it
    // stays legible at every Switch resolution without introducing a new
    // texture dependency.
    const float foot_badge_x =
        row_x + row_w - 0.120f * (float)screen_width;
    const float foot_badge_radius = 0.017f * (float)screen_height;
    for (uint32_t slot = 0; slot < visible_count; slot++) {
      const float card_y = row_y0 + (float)slot * row_step;
      custom_badge_plate_quads += emit_circle_quad(
          foot_badge_x, card_y + row_h * 0.5f, foot_badge_radius,
          verts + quads * 24);
      quads++;
    }

    const float title_gh = (float)screen_height / 31.0f;
    const float text_gh = (float)screen_height / 44.0f;
    const char *title = pes_controller_set_piece_selector_title();
    int line_quads = emit_efootball_line(
        title, (int)strlen(title),
        panel_x + 0.022f * (float)screen_width,
        panel_y + (header_h - title_gh) * 0.5f, title_gh,
        EFOOTBALL_FONT_BOLD,
        verts + quads * 24);
    custom_dark_text_first_quad = quads;
    custom_dark_text_quads += line_quads;
    quads += line_quads;
    if (!count) {
      const char *loading = "LOADING PLAYERS...";
      const float loading_width = measure_efootball_line(
          loading, (int)strlen(loading), text_gh, EFOOTBALL_FONT_REGULAR);
      line_quads = emit_efootball_line(
          loading, (int)strlen(loading),
          panel_x + panel_w * 0.5f - loading_width * 0.5f,
          panel_y + panel_h * 0.46f, text_gh, EFOOTBALL_FONT_REGULAR,
          verts + quads * 24);
      custom_dark_text_quads += line_quads;
      quads += line_quads;
    }
    for (uint32_t slot = 0; slot < visible_count; slot++) {
      const uint32_t player_index = first_visible + slot;
      const float card_y = row_y0 + (float)slot * row_step;
      const char *player_name =
          pes_controller_set_piece_selector_name_at(player_index);
      const char *player_foot =
          pes_controller_set_piece_selector_foot_at(player_index);
      const float name_gh = (float)screen_height / 37.0f;
      const float foot_gh = (float)screen_height / 44.0f;
      char display_name[25];
      snprintf(display_name, sizeof(display_name), "%.24s", player_name);
      line_quads = emit_efootball_line(
          display_name, (int)strlen(display_name),
          row_x + 0.065f * (float)screen_width,
          card_y + (row_h - name_gh) * 0.5f, name_gh,
          EFOOTBALL_FONT_REGULAR,
          verts + quads * 24);
      custom_dark_text_quads += line_quads;
      quads += line_quads;
      char display_foot[2] = {player_foot[0] ? player_foot[0] : '-', '\0'};
      const int foot_len = (int)strlen(display_foot);
      const float foot_width = measure_efootball_line(
          display_foot, foot_len, foot_gh, EFOOTBALL_FONT_BOLD);
      const float foot_x = foot_badge_x - foot_width * 0.5f;
      line_quads = emit_efootball_line(
          display_foot, foot_len, foot_x,
          card_y + (row_h - foot_gh) * 0.5f, foot_gh,
          EFOOTBALL_FONT_BOLD,
          verts + quads * 24);
      custom_dark_text_quads += line_quads;
      quads += line_quads;
    }
    // Console-style role coding: the stencil label identifies each line at a
    // glance while names remain neutral. Emit by category so each batch can
    // receive its own color without another texture or shader branch.
    for (uint32_t role_band = 0; role_band < 4u; role_band++) {
      selector_position_first_quad[role_band] = quads;
      for (uint32_t slot = 0; slot < visible_count; slot++) {
        const uint32_t player_index = first_visible + slot;
        const char *player_position =
            pes_controller_set_piece_selector_position_at(player_index);
        if (selector_position_color_band(player_position) != role_band)
          continue;
        const float card_y = row_y0 + (float)slot * row_step;
        const float position_gh = (float)screen_height / 42.0f;
        line_quads = emit_efootball_line(
            player_position, (int)strlen(player_position),
            row_x + 0.014f * (float)screen_width,
            card_y + (row_h - position_gh) * 0.5f, position_gh,
            EFOOTBALL_FONT_STENCIL, verts + quads * 24);
        selector_position_quads[role_band] += line_quads;
        quads += line_quads;
      }
    }
    // Emit ratings grouped into ten contiguous color bands. The spectrum
    // moves from green through yellow/orange to red as shot power approaches
    // 100, matching the visual range requested for the selector.
    for (uint32_t band = 0; band < 10u; band++) {
      custom_rating_first_quad[band] = quads;
      for (uint32_t slot = 0; slot < visible_count; slot++) {
        const uint32_t player_index = first_visible + slot;
        const uint32_t player_ability =
            pes_controller_set_piece_selector_ability_at(player_index);
        if (!player_ability)
          continue;
        const uint32_t player_band =
            player_ability >= 100u ? 9u : player_ability / 10u;
        if (player_band != band)
          continue;
        const float card_y = row_y0 + (float)slot * row_step;
        const float ability_gh = (float)screen_height / 39.0f;
        char ability_text[4];
        snprintf(ability_text, sizeof(ability_text), "%u", player_ability);
        const int ability_len = (int)strlen(ability_text);
        const float ability_width = measure_efootball_line(
            ability_text, ability_len, ability_gh,
            EFOOTBALL_FONT_REGULAR);
        line_quads = emit_efootball_line(
            ability_text, ability_len,
            row_x + row_w - 0.048f * (float)screen_width - ability_width,
            card_y + (row_h - ability_gh) * 0.5f, ability_gh,
            EFOOTBALL_FONT_REGULAR, verts + quads * 24);
        custom_rating_quads[band] += line_quads;
        quads += line_quads;
      }
    }
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
    const char *helper_key = back_only_cursor ? "B" : "A";
    const float helper_key_w = measure_efootball_line(
        helper_key, 1, helper_gh, EFOOTBALL_FONT_BOLD);
    gameplan_helper_text_first_quad = quads;
    gameplan_helper_text_quads = emit_efootball_line(
        helper_key, 1, helper_x - helper_key_w * 0.5f,
        helper_y - helper_gh * 0.5f, helper_gh, EFOOTBALL_FONT_BOLD,
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
    const float helper_key_w = measure_efootball_line(
        "B", 1, helper_gh, EFOOTBALL_FONT_BOLD);
    gameplan_helper_text_first_quad = quads;
    gameplan_helper_text_quads = emit_efootball_line(
        "B", 1, helper_x - helper_key_w * 0.5f,
        helper_y - helper_gh * 0.5f, helper_gh, EFOOTBALL_FONT_BOLD,
        verts + quads * 24);
    quads += gameplan_helper_text_quads;
  } else if (tutorial_play_active && !custom_2p_transition) {
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
    const float helper_key_w = measure_efootball_line(
        "A", 1, helper_gh, EFOOTBALL_FONT_BOLD);
    gameplan_helper_text_first_quad = quads;
    gameplan_helper_text_quads = emit_efootball_line(
        "A", 1, helper_x - helper_key_w * 0.5f,
        helper_y - helper_gh * 0.5f, helper_gh, EFOOTBALL_FONT_BOLD,
        verts + quads * 24);
    quads += gameplan_helper_text_quads;
  }
  const int text_first_quad = quads;
  if (native_lab && !custom_popup) {
    const uint32_t status = native_debug.status;
    char label[192];
    snprintf(label, sizeof(label),
             "NATIVE 2P SETPLAY V8.17.12 H:%X P:%X O:%X R:%X U:%X B:%X PR:%X "
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
  const int generic_text_end_quad = quads;
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
    cinematic_helper_text_first_quad = quads;
    const float generic_y = 0.925f * (float)screen_height;
    const char *cinematic_key =
        (cinematic_goal_actions || cinematic_goal_skip_only) ? "B" : "A";
    const float cinematic_key_w = measure_efootball_line(
        cinematic_key, 1, gh, EFOOTBALL_FONT_BOLD);
    const int key_quads = emit_efootball_line(
        cinematic_key, 1, helper_x - cinematic_key_w * 0.5f,
        (cinematic_goal_actions ? skip_y : generic_y) - gh * 0.5f,
        gh, EFOOTBALL_FONT_BOLD,
        verts + quads * 24);
    cinematic_helper_text_quads += key_quads;
    quads += key_quads;
    const float label_x = helper_x + helper_radius * 1.55f;
    const int skip_label_quads = emit_efootball_line(
        (cinematic_goal_actions || cinematic_goal_skip_only)
            ? "SKIP"
            : "ANY BUTTON - SKIP",
        (cinematic_goal_actions || cinematic_goal_skip_only) ? 4 : 17,
        label_x,
        (cinematic_goal_actions ? skip_y : generic_y) - gh * 0.5f,
        gh, EFOOTBALL_FONT_REGULAR,
        verts + quads * 24);
    cinematic_helper_text_quads += skip_label_quads;
    quads += skip_label_quads;
    if (cinematic_goal_actions) {
      const float celebrate_key_w = measure_efootball_line(
          "A", 1, gh, EFOOTBALL_FONT_BOLD);
      const int celebrate_key_quads = emit_efootball_line(
          "A", 1, helper_x - celebrate_key_w * 0.5f,
          celebrate_y - gh * 0.5f, gh, EFOOTBALL_FONT_BOLD,
          verts + quads * 24);
      cinematic_helper_text_quads += celebrate_key_quads;
      quads += celebrate_key_quads;
      const int celebrate_label_quads = emit_efootball_line(
          "CELEBRATE", 9, label_x, celebrate_y - gh * 0.5f, gh,
          EFOOTBALL_FONT_REGULAR,
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
    setplay_helper_text_first_quad = quads;
    for (unsigned int index = 0; index < setplay_helper_count; index++) {
      const float y = helper_start_y + (float)index * helper_step;
      const int key_len = (int)strlen(setplay_keys[index]);
      setplay_key_first_quads[index] = quads;
      int line_quads = 0;
      if (strcmp(setplay_keys[index], "L1+R1") == 0) {
        const float r1_width = measure_efootball_line(
            "R1", 2, gh, EFOOTBALL_FONT_BOLD);
        line_quads += emit_efootball_line(
            "R1", 2, helper_x - r1_width * 0.5f,
            y - gh * 0.5f, gh, EFOOTBALL_FONT_BOLD,
            verts + quads * 24);
        quads += line_quads;
        const float plus_width = measure_efootball_line(
            "+", 1, gh, EFOOTBALL_FONT_BOLD);
        int part_quads = emit_efootball_line(
            "+", 1, chord_plus_x - plus_width * 0.5f,
            y - gh * 0.5f, gh, EFOOTBALL_FONT_BOLD,
            verts + quads * 24);
        line_quads += part_quads;
        quads += part_quads;
        const float l1_width = measure_efootball_line(
            "L1", 2, gh, EFOOTBALL_FONT_BOLD);
        part_quads = emit_efootball_line(
            "L1", 2, chord_second_x - l1_width * 0.5f,
            y - gh * 0.5f, gh, EFOOTBALL_FONT_BOLD,
            verts + quads * 24);
        line_quads += part_quads;
        quads += part_quads;
      } else if (strcmp(setplay_keys[index], ">") != 0) {
        const float key_width = measure_efootball_line(
            setplay_keys[index], key_len, gh, EFOOTBALL_FONT_BOLD);
        line_quads = emit_efootball_line(
            setplay_keys[index], key_len,
            helper_x - key_width * 0.5f, y - gh * 0.5f, gh,
            EFOOTBALL_FONT_BOLD,
            verts + quads * 24);
        quads += line_quads;
      }
      setplay_key_quads[index] = line_quads;
      setplay_helper_text_quads += line_quads;
      const int label_len = (int)strlen(setplay_labels[index]);
      line_quads = emit_efootball_line(
          setplay_labels[index], label_len, helper_label_x,
          y - gh * 0.5f, gh, EFOOTBALL_FONT_REGULAR,
          verts + quads * 24);
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
  glUniform1f(gl.loc_image_curve, 0.0f);
  glUniform1f(gl.loc_circle, 0.0f);
  glUniform1f(gl.loc_circle_feather, 0.02f);
  glUniform1f(gl.loc_round_rect, 0.0f);
  glUniform1f(gl.loc_round_feather, 1.15f);
  glUniform1f(gl.loc_cursor, 0.0f);
  glUniform1f(gl.loc_cursor_border, 0.0f);
  if (custom_popup) {
    int custom_offset = 0;
    if (custom_2p_team_selector || custom_2p_prematch_hub_raw ||
        custom_2p_transition) {
      glBindTexture(GL_TEXTURE_2D, gl.team_select_bg_tex);
      glUniform1f(gl.loc_solid, 0.0f);
      glUniform1f(gl.loc_image, 1.0f);
      glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, 1.0f);
      glDrawArrays(GL_TRIANGLES, custom_offset * 6,
                   custom_backdrop_quads * 6);
      glUniform1f(gl.loc_image, 0.0f);
      glBindTexture(GL_TEXTURE_2D, gl.tex);
      glUniform1f(gl.loc_solid, 1.0f);
    } else {
      glUniform1f(gl.loc_solid, 1.0f);
      glUniform4f(gl.loc_color, 0.0f, 0.0f, 0.0f,
                  set_piece_selector ? 0.46f : 0.56f);
      glDrawArrays(GL_TRIANGLES, custom_offset * 6,
                   custom_backdrop_quads * 6);
    }
    custom_offset += custom_backdrop_quads;
    if (custom_2p_team_selector)
      glUniform4f(gl.loc_color, 0.20f, 0.015f, 0.025f, 1.0f);
    else if (custom_hub_settings_popup || custom_hub_choice_page)
      glUniform4f(gl.loc_color, 0.06f, 0.09f, 0.17f,
                  custom_hub_choice_page ? 1.0f : 0.92f);
    else if (custom_2p_prematch_hub)
      glUniform4f(gl.loc_color, 0.0f, 0.015f, 0.045f, 0.0f);
    else if (custom_2p_transition)
      glUniform4f(gl.loc_color, 0.01f, 0.025f, 0.075f, 0.92f);
    else
      glUniform4f(gl.loc_color, 0.98f, 0.98f, 0.98f, 1.0f);
    use_rounded_rect(&custom_panel_style);
    glDrawArrays(GL_TRIANGLES, custom_offset * 6,
                 custom_panel_quads * 6);
    custom_offset += custom_panel_quads;
    if (custom_2p_team_selector)
      glUniform4f(gl.loc_color, 0.035f, 0.035f, 0.038f, 1.0f);
    else if (custom_hub_settings_popup || custom_hub_choice_page)
      glUniform4f(gl.loc_color, 0.025f, 0.045f, 0.11f,
                  custom_hub_choice_page ? 1.0f : 0.97f);
    else if (custom_2p_prematch_hub)
      glUniform4f(gl.loc_color, 0.01f, 0.01f, 0.015f, 1.0f);
    else if (set_piece_selector)
      glUniform4f(gl.loc_color, 0.98f, 0.98f, 0.98f, 1.0f);
    else
      glUniform4f(gl.loc_color, 0.78f, 0.88f, 0.96f, 1.0f);
    use_rounded_rect(&custom_header_style);
    glDrawArrays(GL_TRIANGLES, custom_offset * 6,
                 custom_header_round_quads * 6);
    custom_offset += custom_header_round_quads;
    use_rounded_rect(NULL);
    glDrawArrays(GL_TRIANGLES, custom_offset * 6,
                 custom_header_fill_quads * 6);
    custom_offset += custom_header_fill_quads;
    if (custom_2p_team_selector)
      glUniform4f(gl.loc_color, 0.94f, 0.93f, 0.93f, 0.96f);
    else if (custom_hub_settings_popup || custom_hub_choice_page)
      glUniform4f(gl.loc_color, 0.93f, 0.96f, 1.0f, 0.78f);
    else if (custom_2p_prematch_hub)
      glUniform4f(gl.loc_color, 0.92f, 0.94f, 0.98f, 0.90f);
    else
      glUniform4f(gl.loc_color,
                  set_piece_selector ? 0.55f : 0.25f,
                  set_piece_selector ? 0.82f : 0.78f,
                  set_piece_selector ? 0.98f : 0.96f,
                  set_piece_selector ? 0.48f : 0.42f);
    use_rounded_rect(&custom_selected_style);
    glDrawArrays(GL_TRIANGLES, custom_offset * 6,
                 custom_selected_quads * 6);
    custom_offset += custom_selected_quads;
    use_rounded_rect(NULL);
    glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, 1.0f);
    glDrawArrays(GL_TRIANGLES, custom_offset * 6,
                 custom_confirm_bar_quads * 6);
    custom_offset += custom_confirm_bar_quads;
    if (custom_kit_preview_quads) {
      GLint previous_sampler = 0;
      if (gl.bind_sampler) {
        glGetIntegerv(GL_SAMPLER_BINDING, &previous_sampler);
        gl.bind_sampler(0, 0);
      }
      glUniform1f(gl.loc_solid, 0.0f);
      glUniform1f(gl.loc_image, 1.0f);
      glUniform1f(gl.loc_image_curve, 0.0f);
      use_rounded_rect(NULL);
      glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, 1.0f);
      for (uint32_t side = 0; side < 2; side++) {
        if (!custom_kit_preview_side_quads[side] ||
            !(gl.native_uniform_valid_mask & (1u << side)))
          continue;
        glBindTexture(GL_TEXTURE_2D, gl.native_uniform_texture[side]);
        glDrawArrays(GL_TRIANGLES,
                     custom_kit_preview_first_quad[side] * 6,
                     custom_kit_preview_side_quads[side] * 6);
      }
      if (gl.bind_sampler)
        gl.bind_sampler(0, (GLuint)previous_sampler);
      glBindTexture(GL_TEXTURE_2D, gl.tex);
      glUniform1f(gl.loc_image, 0.0f);
      glUniform1f(gl.loc_solid, 1.0f);
    }
    custom_offset += custom_kit_preview_quads;
    if (custom_2p_team_selector)
      glUniform4f(gl.loc_color, 0.86f, 0.84f, 0.84f, 0.88f);
    else if (custom_hub_settings_popup || custom_hub_choice_page)
      glUniform4f(gl.loc_color, 0.80f, 0.86f, 0.93f, 0.34f);
    else
      glUniform4f(gl.loc_color,
                  set_piece_selector ? 0.84f : 0.70f,
                  set_piece_selector ? 0.86f : 0.74f,
                  set_piece_selector ? 0.88f : 0.78f,
                  set_piece_selector ? 0.72f : 0.85f);
    glDrawArrays(GL_TRIANGLES, custom_offset * 6,
                 custom_rule_quads * 6);
    custom_offset += custom_rule_quads;
    if (custom_2p_team_selector && custom_team_stat_shape_quads) {
      glUniform1f(gl.loc_solid, 1.0f);
      glUniform1f(gl.loc_image, 0.0f);
      glUniform4f(gl.loc_color, 0.055f, 0.050f, 0.052f, 1.0f);
      for (uint32_t pad = 0; pad < 2; pad++) {
        for (uint32_t role = 0; role < 3; role++) {
          if (!custom_team_stat_track_quads[pad][role])
            continue;
          use_rounded_rect(&custom_team_stat_track_style);
          glDrawArrays(
              GL_TRIANGLES,
              custom_team_stat_track_first_quad[pad][role] * 6,
              custom_team_stat_track_quads[pad][role] * 6);
        }
      }
      static const float team_stat_colors[3][3] = {
          {0.96f, 0.04f, 0.36f}, // FW: PES magenta
          {0.24f, 0.83f, 0.14f}, // MF: pitch green
          {0.10f, 0.75f, 0.90f}, // DF: cyan blue
      };
      for (uint32_t role = 0; role < 3; role++) {
        glUniform4f(gl.loc_color, team_stat_colors[role][0],
                    team_stat_colors[role][1],
                    team_stat_colors[role][2], 1.0f);
        for (uint32_t pad = 0; pad < 2; pad++) {
          if (!custom_team_stat_fill_quads[pad][role])
            continue;
          use_rounded_rect(&custom_team_stat_fill_style[pad][role]);
          glDrawArrays(
              GL_TRIANGLES,
              custom_team_stat_fill_first_quad[pad][role] * 6,
              custom_team_stat_fill_quads[pad][role] * 6);
        }
      }
      use_rounded_rect(NULL);
      glBindTexture(GL_TEXTURE_2D, gl.team_rating_star_tex);
      glUniform1f(gl.loc_solid, 0.0f);
      glUniform1f(gl.loc_image, 0.0f);
      glUniform4f(gl.loc_color, 0.035f, 0.030f, 0.025f, 1.0f);
      glDrawArrays(GL_TRIANGLES, custom_team_star_border_first_quad * 6,
                   custom_team_star_border_quads * 6);
      glUniform4f(gl.loc_color, 0.68f, 0.68f, 0.65f, 1.0f);
      glDrawArrays(GL_TRIANGLES, custom_team_star_empty_first_quad * 6,
                   custom_team_star_empty_quads * 6);
      glUniform4f(gl.loc_color, 0.98f, 0.94f, 0.04f, 1.0f);
      glDrawArrays(GL_TRIANGLES, custom_team_star_fill_first_quad * 6,
                   custom_team_star_fill_quads * 6);
      glBindTexture(GL_TEXTURE_2D, gl.tex);
      glUniform1f(gl.loc_solid, 1.0f);
    }
    custom_offset += custom_team_stat_shape_quads;
    if (custom_hub_settings_popup || custom_hub_choice_page)
      glUniform4f(gl.loc_color, 0.04f, 0.43f, 0.76f, 0.96f);
    else if (custom_2p_prematch_hub)
      glUniform4f(gl.loc_color, 0.86f, 0.90f, 0.96f, 0.84f);
    else
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
    glUniform4f(gl.loc_color,
                set_piece_selector ? 0.82f : 0.98f,
                set_piece_selector ? 0.84f : 0.99f,
                set_piece_selector ? 0.86f : 1.0f,
                1.0f);
    glDrawArrays(GL_TRIANGLES, custom_offset * 6,
                 custom_badge_plate_quads * 6);
    custom_offset += custom_badge_plate_quads;
    glUniform1f(gl.loc_circle, 0.0f);
    glUniform1f(gl.loc_solid, 1.0f);
    if (custom_2p_prematch_hub)
      glUniform4f(gl.loc_color, 0.97f, 0.98f, 1.0f, 0.75f);
    else if (custom_hub_settings_popup || custom_hub_choice_page)
      glUniform4f(gl.loc_color, 0.04f, 0.43f, 0.76f, 0.96f);
    else
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
    glBindTexture(GL_TEXTURE_2D, gl.efootball_tex);
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform2f(gl.loc_off, 0.0f, 0.0f);
    glUniform4f(gl.loc_color, 0.02f, 0.36f, 0.62f, 1.0f);
    glDrawArrays(GL_TRIANGLES, gameplan_helper_text_first_quad * 6,
                 gameplan_helper_text_quads * 6);
    glBindTexture(GL_TEXTURE_2D, gl.tex);
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
    glBindTexture(GL_TEXTURE_2D, gl.efootball_tex);
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform2f(gl.loc_off, 0.0f, 0.0f);
    glUniform4f(gl.loc_color, 0.02f, 0.36f, 0.62f, 1.0f);
    glDrawArrays(GL_TRIANGLES, cinematic_helper_text_first_quad * 6,
                 cinematic_helper_text_quads * 6);
    glBindTexture(GL_TEXTURE_2D, gl.tex);
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
  if (set_piece_selector || custom_2p_team_selector ||
      custom_2p_prematch_hub_raw || custom_2p_transition)
    glBindTexture(GL_TEXTURE_2D, gl.efootball_tex);
  if (custom_dark_text_quads) {
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform2f(gl.loc_off, 0.0f, 0.0f);
    glUniform4f(gl.loc_color, 0.025f, 0.075f, 0.12f, 1.0f);
    glDrawArrays(GL_TRIANGLES, custom_dark_text_first_quad * 6,
                 custom_dark_text_quads * 6);
  }
  if (custom_hub_button_text_quads) {
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform2f(gl.loc_off, 0.0f, 0.0f);
    glUniform4f(gl.loc_color, 0.02f, 0.03f, 0.05f, 1.0f);
    glDrawArrays(GL_TRIANGLES, custom_hub_button_text_first_quad * 6,
                 custom_hub_button_text_quads * 6);
  }
  if (custom_focus_text_quads) {
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform2f(gl.loc_off, 0.0f, 0.0f);
    glUniform4f(gl.loc_color, 0.72f, 0.025f, 0.055f, 1.0f);
    glDrawArrays(GL_TRIANGLES, custom_focus_text_first_quad * 6,
                 custom_focus_text_quads * 6);
  }
  if (custom_ok_text_quads) {
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform2f(gl.loc_off, 0.0f, 0.0f);
    glUniform4f(gl.loc_color, 0.02f, 0.68f, 0.52f, 1.0f);
    glDrawArrays(GL_TRIANGLES, custom_ok_text_first_quad * 6,
                 custom_ok_text_quads * 6);
  }
  static const float position_colors[4][3] = {
      {0.96f, 0.55f, 0.10f}, // goalkeeper: orange
      {0.08f, 0.45f, 0.88f}, // backs: blue
      {0.05f, 0.68f, 0.36f}, // midfielders: green
      {0.88f, 0.18f, 0.20f}, // forwards: red
  };
  for (uint32_t role_band = 0; role_band < 4u; role_band++) {
    if (!selector_position_quads[role_band])
      continue;
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform2f(gl.loc_off, 0.0f, 0.0f);
    glUniform4f(gl.loc_color, position_colors[role_band][0],
                position_colors[role_band][1],
                position_colors[role_band][2], 1.0f);
    glDrawArrays(GL_TRIANGLES, selector_position_first_quad[role_band] * 6,
                 selector_position_quads[role_band] * 6);
  }
  static const float rating_colors[10][3] = {
      {0.09f, 0.78f, 0.52f}, {0.18f, 0.80f, 0.44f},
      {0.33f, 0.84f, 0.36f}, {0.49f, 0.87f, 0.27f},
      {0.68f, 0.90f, 0.18f}, {0.88f, 0.87f, 0.13f},
      {0.95f, 0.75f, 0.12f}, {0.95f, 0.56f, 0.11f},
      {0.94f, 0.37f, 0.12f}, {0.90f, 0.22f, 0.21f},
  };
  for (uint32_t band = 0; band < 10u; band++) {
    if (!custom_rating_quads[band])
      continue;
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform2f(gl.loc_off, 0.0f, 0.0f);
    glUniform4f(gl.loc_color, rating_colors[band][0],
                rating_colors[band][1], rating_colors[band][2], 1.0f);
    glDrawArrays(GL_TRIANGLES, custom_rating_first_quad[band] * 6,
                 custom_rating_quads[band] * 6);
  }
  if (set_piece_selector || custom_2p_team_selector ||
      custom_2p_prematch_hub_raw || custom_2p_transition)
    glBindTexture(GL_TEXTURE_2D, gl.tex);
  if (custom_white_text_quads) {
    if (custom_2p_team_selector || custom_2p_prematch_hub_raw ||
        custom_2p_transition)
      glBindTexture(GL_TEXTURE_2D, gl.efootball_tex);
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform2f(gl.loc_off, 0.0f, 0.0f);
    glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, 1.0f);
    glDrawArrays(GL_TRIANGLES, custom_white_text_first_quad * 6,
                 custom_white_text_quads * 6);
    if (custom_2p_team_selector || custom_2p_prematch_hub_raw ||
        custom_2p_transition)
      glBindTexture(GL_TEXTURE_2D, gl.tex);
  }
  if (custom_key_text_quads) {
    if (custom_2p_team_selector || custom_hub_settings_popup ||
        custom_hub_choice_page)
      glBindTexture(GL_TEXTURE_2D, gl.efootball_tex);
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform4f(gl.loc_color, 0.02f, 0.36f, 0.62f, 1.0f);
    glDrawArrays(GL_TRIANGLES, custom_key_text_first_quad * 6,
                 custom_key_text_quads * 6);
    if (custom_2p_team_selector || custom_hub_settings_popup ||
        custom_hub_choice_page)
      glBindTexture(GL_TEXTURE_2D, gl.tex);
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
    glBindTexture(GL_TEXTURE_2D, gl.efootball_tex);
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
    glBindTexture(GL_TEXTURE_2D, gl.tex);
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
