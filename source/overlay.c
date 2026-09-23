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
#include "competition_frontend.h"
#include "exhibition_team_catalog.h"
#include "overlay.h"
#include "badge_atlas.h"
#include "efootball_font_atlas.h"
#include "font_atlas.h"
#include "main_menu_assets.h"
#include "switch_button_assets.h"
#include "team_rating_star.h"
#include "team_select_background.h"
#include "ue4_hooks.h"
#include "util.h"

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
  GLuint main_menu_background_tex;
  GLuint main_menu_icons_tex;
  GLuint main_menu_brand_tex;
  GLuint main_menu_button_a_tex;
  GLuint main_menu_button_b_tex;
  GLuint switch_button_tex[SWITCH_BUTTON_COUNT];
  int switch_buttons_uploaded;
  GLuint main_menu_portrait_tex[4];
  GLuint native_uniform_texture[2];
#define PREMATCH_GAMEPLAN_PORTRAIT_CACHE_SIZE 80
  GLuint player_portrait_texture[PREMATCH_GAMEPLAN_PORTRAIT_CACHE_SIZE];
  uint32_t player_portrait_id[PREMATCH_GAMEPLAN_PORTRAIT_CACHE_SIZE];
  uint32_t player_portrait_stamp[PREMATCH_GAMEPLAN_PORTRAIT_CACHE_SIZE];
  uint32_t player_portrait_clock;
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
  int main_menu_uploaded;
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
  glGenTextures(1, &gl.main_menu_background_tex);
  glGenTextures(1, &gl.main_menu_icons_tex);
  glGenTextures(1, &gl.main_menu_brand_tex);
  glGenTextures(1, &gl.main_menu_button_a_tex);
  glGenTextures(1, &gl.main_menu_button_b_tex);
  glGenTextures(SWITCH_BUTTON_COUNT, gl.switch_button_tex);
  glGenTextures(4, gl.main_menu_portrait_tex);
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
  const int small = gh <= 21.0f;
  const uint8_t *advances = small ? efootball_font_small_advance[weight]
                                  : efootball_font_advance[weight];
  const float source_height = small ? (float)EFOOTBALL_FONT_SMALL_CELL_H
                                    : (float)EFOOTBALL_FONT_CELL_H;
  float width = 0.0f;
  for (int index = 0; index < len; index++) {
    if (text[index] == ' ') {
      width += gh * 0.34f;
      continue;
    }
    const int glyph = efootball_font_glyph_index(text[index]);
    if (glyph < 0)
      continue;
    width += (float)advances[glyph] * gh / source_height;
  }
  return width;
}

static int emit_efootball_line(const char *text, int len, float x, float y,
                               float gh, uint32_t weight, GLfloat *verts) {
  if (weight >= EFOOTBALL_FONT_WEIGHTS)
    weight = EFOOTBALL_FONT_REGULAR;
  const int small = gh <= 21.0f;
  const float source_width = small ? (float)EFOOTBALL_FONT_SMALL_CELL_W
                                   : (float)EFOOTBALL_FONT_CELL_W;
  const float source_height = small ? (float)EFOOTBALL_FONT_SMALL_CELL_H
                                    : (float)EFOOTBALL_FONT_CELL_H;
  const uint8_t *advances = small ? efootball_font_small_advance[weight]
                                  : efootball_font_advance[weight];
  const uint32_t atlas_row = weight + (small ? EFOOTBALL_FONT_WEIGHTS : 0u);
  const float gw = gh * source_width / source_height;
  const float draw_y = small ? floorf(y + 0.5f) : y;
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
        ((float)(glyph * EFOOTBALL_FONT_CELL_W) + source_width - 0.5f) /
        (float)EFOOTBALL_FONT_ATLAS_W;
    const float v0 =
        ((float)(atlas_row * EFOOTBALL_FONT_CELL_H) + 0.5f) /
        (float)EFOOTBALL_FONT_ATLAS_H;
    const float v1 =
        ((float)(atlas_row * EFOOTBALL_FONT_CELL_H) + source_height - 0.5f) /
        (float)EFOOTBALL_FONT_ATLAS_H;
    const float draw_x = small ? floorf(pen_x + 0.5f) : pen_x;
    const float px0 = draw_x * 2.0f / (float)screen_width - 1.0f;
    const float px1 = (draw_x + gw) * 2.0f / (float)screen_width - 1.0f;
    const float py0 = 1.0f - draw_y * 2.0f / (float)screen_height;
    const float py1 = 1.0f - (draw_y + gh) * 2.0f / (float)screen_height;
    const GLfloat quad[24] = {
        px0, py0, u0, v0, px1, py0, u1, v0, px0, py1, u0, v1,
        px1, py0, u1, v0, px1, py1, u1, v1, px0, py1, u0, v1,
    };
    memcpy(verts + quads * 24, quad, sizeof(quad));
    quads++;
    pen_x += (float)advances[glyph] * gh / source_height;
  }
  return quads;
}

static int emit_efootball_fit_line(const char *text, int len, float x, float y,
                                   float max_width, float max_gh,
                                   float min_gh, uint32_t weight,
                                   GLfloat *verts) {
  if (!text || len <= 0 || max_width <= 0.0f)
    return 0;
  float gh = max_gh;
  float width = measure_efootball_line(text, len, gh, weight);
  while (width > max_width && gh > min_gh) {
    gh *= 0.92f;
    width = measure_efootball_line(text, len, gh, weight);
  }
  return emit_efootball_line(text, len, x, y, gh, weight, verts);
}

static int emit_efootball_right_fit_line(
    const char *text, int len, float right_x, float y, float max_width,
    float max_gh, float min_gh, uint32_t weight, GLfloat *verts) {
  if (!text || len <= 0 || max_width <= 0.0f)
    return 0;
  float gh = max_gh;
  float width = measure_efootball_line(text, len, gh, weight);
  while (width > max_width && gh > min_gh) {
    gh *= 0.92f;
    width = measure_efootball_line(text, len, gh, weight);
  }
  return emit_efootball_line(text, len, right_x - width, y, gh, weight,
                             verts);
}

static int emit_efootball_centered_fit_line(
    const char *text, int len, float center_x, float y, float max_width,
    float max_gh, float min_gh, uint32_t weight, GLfloat *verts) {
  if (!text || len <= 0 || max_width <= 0.0f)
    return 0;
  float gh = max_gh;
  float width = measure_efootball_line(text, len, gh, weight);
  while (width > max_width && gh > min_gh) {
    gh *= 0.92f;
    width = measure_efootball_line(text, len, gh, weight);
  }
  return emit_efootball_line(text, len, center_x - width * 0.5f, y, gh,
                             weight, verts);
}

// Keep on-field labels at one readable size. Long names scroll only while the
// player is focused, avoiding the tiny blurred text produced by fit-to-width.
static int emit_efootball_name_line(const char *text, int len, float anchor_x,
                                    float y, float max_width, float gh,
                                    int focused, double focused_seconds,
                                    int left_aligned, GLfloat *verts) {
  if (!text || len <= 0 || max_width <= 0.0f)
    return 0;
  const float width = measure_efootball_line(text, len, gh,
                                             EFOOTBALL_FONT_BOLD);
  if (width <= max_width)
    return emit_efootball_line(text, len,
                               left_aligned ? anchor_x
                                            : anchor_x - width * 0.5f,
                               y, gh,
                               EFOOTBALL_FONT_BOLD, verts);
  if (!focused) {
    char clipped[64];
    const int limit = len < (int)sizeof(clipped) - 4
                          ? len
                          : (int)sizeof(clipped) - 4;
    memcpy(clipped, text, (size_t)limit);
    clipped[limit] = '\0';
    while (strlen(clipped) > 1) {
      char candidate[64];
      snprintf(candidate, sizeof(candidate), "%s...", clipped);
      if (measure_efootball_line(candidate, (int)strlen(candidate), gh,
                                 EFOOTBALL_FONT_BOLD) <= max_width)
        break;
      clipped[strlen(clipped) - 1] = '\0';
    }
    strcat(clipped, "...");
    const float clipped_width = measure_efootball_line(
        clipped, (int)strlen(clipped), gh, EFOOTBALL_FONT_BOLD);
    return emit_efootball_line(clipped, (int)strlen(clipped),
                               left_aligned ? anchor_x
                                            : anchor_x - clipped_width * 0.5f,
                               y, gh,
                               EFOOTBALL_FONT_BOLD, verts);
  }
  const float travel = width - max_width;
  const float speed = gh * 1.8f;
  const float duration = travel / speed;
  const float pause = 0.85f;
  const float phase = (float)fmod(focused_seconds,
                                 2.0 * (duration + pause));
  float offset;
  if (phase < pause)
    offset = 0.0f;
  else if (phase < pause + duration)
    offset = (phase - pause) * speed;
  else if (phase < 2.0f * pause + duration)
    offset = travel;
  else
    offset = travel - (phase - 2.0f * pause - duration) * speed;
  const float left = left_aligned ? anchor_x : anchor_x - max_width * 0.5f;
  const int emitted = emit_efootball_line(
      text, len, left - offset, y, gh, EFOOTBALL_FONT_BOLD, verts);
  const float clip_left = left * 2.0f / (float)screen_width - 1.0f;
  const float clip_right =
      (left + max_width) * 2.0f / (float)screen_width - 1.0f;
  int quads = 0;
  // Clip the existing glyph geometry and interpolate within that glyph's UVs.
  for (int index = 0; index < emitted; index++) {
    GLfloat quad[24];
    memcpy(quad, verts + index * 24, sizeof(quad));
    const float x0 = quad[0], x1 = quad[4];
    const float u0 = quad[2], u1 = quad[6];
    if (x1 <= clip_left || x0 >= clip_right)
      continue;
    for (int vertex = 0; vertex < 6; vertex++) {
      const float x = fmaxf(clip_left, fminf(clip_right, quad[vertex * 4]));
      quad[vertex * 4] = x;
      quad[vertex * 4 + 2] = u0 + (x - x0) / (x1 - x0) * (u1 - u0);
    }
    memcpy(verts + quads * 24, quad, sizeof(quad));
    quads++;
  }
  return quads;
}

static double gameplan_name_focus_seconds(uint32_t side, int active,
                                          const char *name) {
  static char focused_name[2][128];
  static u64 focus_tick[2];
  const u64 now = armGetSystemTick();
  if (!active) {
    focused_name[side][0] = '\0';
    focus_tick[side] = now;
    return 0.0;
  }
  if (strcmp(focused_name[side], name) != 0) {
    snprintf(focused_name[side], sizeof(focused_name[side]), "%s", name);
    focus_tick[side] = now;
  }
  return (double)armTicksToNs(now - focus_tick[side]) / 1e9;
}

static void compact_player_name(char *destination, size_t capacity,
                                const char *source) {
  if (!destination || !capacity)
    return;
  destination[0] = '\0';
  if (!source || !source[0])
    return;
  const size_t source_length = strlen(source);
  const char *start = source;
  if (source_length >= capacity) {
    const char *last_space = strrchr(source, ' ');
    if (last_space && last_space[1])
      start = last_space + 1;
  }
  size_t length = strlen(start);
  if (length >= capacity)
    length = capacity - 1;
  while (length && ((unsigned char)start[length] & 0xc0u) == 0x80u)
    length--;
  memcpy(destination, start, length);
  destination[length] = '\0';
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

/* The selector catalog keeps full names, while the compact bracket uses a
 * scoreboard-sized code.  Preserve familiar codes for the most prominent
 * clubs and derive a stable three-letter fallback for the rest. */
static void cup_team_code(uint32_t team, char code[4]) {
  if (team == 100u) {
    memcpy(code, "MUN", 4);
    return;
  }
  if (team == 108u) {
    memcpy(code, "BAR", 4);
    return;
  }
  const char *name = exhibition_team_catalog_name(team);
  if ((name[0] == 'F' && name[1] == 'C' && name[2] == ' ') ||
      (name[0] == 'A' && name[1] == 'C' && name[2] == ' '))
    name += 3;
  uint32_t length = 0;
  while (*name && length < 3u) {
    if ((*name >= 'A' && *name <= 'Z') ||
        (*name >= '0' && *name <= '9'))
      code[length++] = *name;
    name++;
  }
  while (length < 3u) code[length++] = '-';
  code[3] = '\0';
}

/* An unresolved future fixture is not a bye. Keep card, badge and text
 * geometry on the same rule so TBD never straddles two slots. */
static int cup_fixture_is_bye(const CupFixture *fixture) {
  return fixture && fixture->complete && fixture->home && !fixture->away;
}

static int emit_cup_slot_text(uint32_t team, int has_score, uint32_t score,
                              float x, float y, float width, float height,
                              GLfloat *verts) {
  char label[24];
  if (team) {
    char code[4];
    cup_team_code(team, code);
    const uint32_t player = competition_frontend_cup_player_slot(team);
    if (player)
      snprintf(label, sizeof(label), "%s - P%u", code, player);
    else
      snprintf(label, sizeof(label), "%s - COM", code);
  } else {
    memcpy(label, "TBD", 4);
  }
  const float glyph_h = roundf(fminf(height * 0.58f,
                                     (float)screen_height / 38.0f));
  const float text_x = x + 0.008f * (float)screen_width +
                       0.035f * (float)screen_height +
                       0.008f * (float)screen_width;
  const float text_y = y + (height - glyph_h) * 0.5f;
  int count = emit_efootball_line(label, (int)strlen(label), text_x, text_y,
                                   glyph_h, EFOOTBALL_FONT_BOLD, verts);
  if (has_score && team) {
    char score_text[8];
    snprintf(score_text, sizeof(score_text), "%u", score);
    const float score_w = measure_efootball_line(
        score_text, (int)strlen(score_text), glyph_h, EFOOTBALL_FONT_BOLD);
    count += emit_efootball_line(
        score_text, (int)strlen(score_text),
        x + width - 0.008f * (float)screen_width - score_w,
        text_y, glyph_h, EFOOTBALL_FONT_BOLD, verts + count * 24);
  }
  return count;
}

static int emit_cup_history_match_text(uint32_t home, uint32_t away,
                                        uint32_t home_goals,
                                        uint32_t away_goals,
                                        float x, float y, float width,
                                        float height, GLfloat *verts) {
  char home_code[4], away_code[4], score[24];
  if (home) cup_team_code(home, home_code);
  else memcpy(home_code, "TBD", 4);
  if (away) cup_team_code(away, away_code);
  else memcpy(away_code, "TBD", 4);
  snprintf(score, sizeof(score), "%u - %u", home_goals, away_goals);
  const float glyph_h = roundf(fminf(height * 0.35f,
                                     (float)screen_height / 37.0f));
  const float text_y = y + (height - glyph_h) * 0.5f;
  const float badge = 0.032f * (float)screen_height;
  const float home_x = x + 0.010f * (float)screen_width + badge +
                       0.007f * (float)screen_width;
  int count = emit_efootball_line(home_code, 3, home_x, text_y,
                                   glyph_h, EFOOTBALL_FONT_BOLD, verts);
  const float score_w = measure_efootball_line(
      score, (int)strlen(score), glyph_h, EFOOTBALL_FONT_BOLD);
  count += emit_efootball_line(
      score, (int)strlen(score), x + (width - score_w) * 0.5f,
      text_y, glyph_h, EFOOTBALL_FONT_BOLD, verts + count * 24);
  const float away_x = x + width * 0.67f + badge +
                       0.007f * (float)screen_width;
  count += emit_efootball_line(away_code, 3, away_x, text_y,
                                glyph_h, EFOOTBALL_FONT_BOLD,
                                verts + count * 24);
  return count;
}

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
  // Capture coordinates are framebuffer pixels, not logical config pixels.
  // On the Switch the swap surface may stay at 1024x576 while the cfg asks
  // for 1280x720; reading with the latter would sample outside the target and
  // make the two kit previews appear enlarged or offset.
  GLint capture_viewport[4] = {0};
  glGetIntegerv(GL_VIEWPORT, capture_viewport);
  const GLint canvas_width = capture_viewport[2] > 0 ? capture_viewport[2]
                                                     : screen_width;
  const GLint canvas_height = capture_viewport[3] > 0 ? capture_viewport[3]
                                                       : screen_height;

  static const float capture_x_fraction[2] = {0.145f, 0.438f};
  const float capture_width_fraction = 0.125f;
  const float capture_top_fraction = 0.280f;
  const float capture_bottom_fraction = 0.815f;
  const GLint capture_width =
      (GLint)(capture_width_fraction * (float)canvas_width + 0.5f);
  const GLint capture_height =
      (GLint)((capture_bottom_fraction - capture_top_fraction) *
                  (float)canvas_height +
              0.5f);
  const GLint capture_bottom =
      (GLint)(capture_bottom_fraction * (float)canvas_height + 0.5f);
  const GLint capture_y = canvas_height - capture_bottom;
  const GLint capture_x[2] = {
      (GLint)(capture_x_fraction[0] * (float)canvas_width + 0.5f),
      (GLint)(capture_x_fraction[1] * (float)canvas_width + 0.5f),
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

static int decode_png_memory(const unsigned char *bytes, uint32_t byte_count,
                             unsigned char **pixels_out, GLint *width_out,
                             GLint *height_out) {
  if (!bytes || !byte_count || !pixels_out || !width_out || !height_out)
    return 0;

  png_image image;
  memset(&image, 0, sizeof(image));
  image.version = PNG_IMAGE_VERSION;
  if (!png_image_begin_read_from_memory(&image, bytes, byte_count))
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

static int upload_main_menu_png(GLuint texture, const uint8_t *begin,
                                const uint8_t *end) {
  if (!texture || !begin || !end || end <= begin)
    return 0;
  const uintptr_t byte_count = (uintptr_t)(end - begin);
  if (byte_count > UINT32_MAX)
    return 0;

  unsigned char *pixels = NULL;
  GLint width = 0;
  GLint height = 0;
  if (!decode_png_memory(begin, (uint32_t)byte_count, &pixels, &width,
                         &height))
    return 0;
  glBindTexture(GL_TEXTURE_2D, texture);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER,
                  GL_LINEAR_MIPMAP_LINEAR);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
  glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA,
               GL_UNSIGNED_BYTE, pixels);
  glGenerateMipmap(GL_TEXTURE_2D);
  free(pixels);
  return 1;
}

static void prepare_switch_button_assets(int active) {
  if (!active || gl.switch_buttons_uploaded) return;
  GLint active_texture, texture, unpack;
  glGetIntegerv(GL_ACTIVE_TEXTURE, &active_texture);
  glActiveTexture(GL_TEXTURE0);
  glGetIntegerv(GL_TEXTURE_BINDING_2D, &texture);
  glGetIntegerv(GL_UNPACK_ALIGNMENT, &unpack);
  glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
  int uploaded = 1;
#define SWITCH_UPLOAD(name, key) \
  uploaded &= upload_main_menu_png(gl.switch_button_tex[SWITCH_BUTTON_##name], \
      switch_button_##name##_bin, switch_button_##name##_bin_end);
  SWITCH_BUTTON_ASSETS(SWITCH_UPLOAD)
#undef SWITCH_UPLOAD
  glPixelStorei(GL_UNPACK_ALIGNMENT, unpack);
  glBindTexture(GL_TEXTURE_2D, texture);
  glActiveTexture(active_texture);
  gl.switch_buttons_uploaded = uploaded;
}

static GLuint switch_button_texture(const char *key) {
  if (!strcmp(key, "A")) return gl.main_menu_button_a_tex;
  if (!strcmp(key, "B")) return gl.main_menu_button_b_tex;
#define SWITCH_MATCH(name, label) \
  if (!strcmp(key, label)) return gl.switch_button_tex[SWITCH_BUTTON_##name];
  SWITCH_BUTTON_ASSETS(SWITCH_MATCH)
#undef SWITCH_MATCH
  return 0;
}

static void prepare_main_menu_assets(int active) {
  if (!active || gl.main_menu_uploaded)
    return;

  static const uint8_t *const portrait_begin[4] = {
      main_menu_portrait_exhibition_bin,
      main_menu_portrait_2player_bin,
      main_menu_portrait_settings_bin,
      main_menu_portrait_credits_bin,
  };
  static const uint8_t *const portrait_end[4] = {
      main_menu_portrait_exhibition_bin_end,
      main_menu_portrait_2player_bin_end,
      main_menu_portrait_settings_bin_end,
      main_menu_portrait_credits_bin_end,
  };

  GLint saved_active_texture = GL_TEXTURE0;
  GLint saved_texture = 0;
  GLint saved_unpack_alignment = 4;
  glGetIntegerv(GL_ACTIVE_TEXTURE, &saved_active_texture);
  glActiveTexture(GL_TEXTURE0);
  glGetIntegerv(GL_TEXTURE_BINDING_2D, &saved_texture);
  glGetIntegerv(GL_UNPACK_ALIGNMENT, &saved_unpack_alignment);
  glPixelStorei(GL_UNPACK_ALIGNMENT, 1);

  int uploaded = upload_main_menu_png(
      gl.main_menu_background_tex, main_menu_background_bin,
      main_menu_background_bin_end);
  uploaded &= upload_main_menu_png(gl.main_menu_button_a_tex,
      main_menu_button_a_bin, main_menu_button_a_bin_end);
  uploaded &= upload_main_menu_png(gl.main_menu_button_b_tex,
      main_menu_button_b_bin, main_menu_button_b_bin_end);
  uploaded &= upload_main_menu_png(gl.main_menu_icons_tex,
                                   main_menu_icons_bin,
                                   main_menu_icons_bin_end);
  uploaded &= upload_main_menu_png(gl.main_menu_brand_tex,
                                   main_menu_brand_bin,
                                   main_menu_brand_bin_end);
  for (uint32_t index = 0; index < 4; index++)
    uploaded &= upload_main_menu_png(gl.main_menu_portrait_tex[index],
                                     portrait_begin[index],
                                     portrait_end[index]);

  glPixelStorei(GL_UNPACK_ALIGNMENT, saved_unpack_alignment);
  glBindTexture(GL_TEXTURE_2D, (GLuint)saved_texture);
  glActiveTexture((GLenum)saved_active_texture);
  if (uploaded)
    gl.main_menu_uploaded = 1;
}

static int decode_uniform_thumbnail(const PesUniformPreviewPng *preview,
                                    unsigned char **pixels_out,
                                    GLint *width_out, GLint *height_out) {
  if (!preview || !preview->byte_count || !pixels_out || !width_out ||
      !height_out)
    return 0;
  // decode_png_memory uses libpng's png_image_begin_read_from_memory entry
  // point, keeping the native uniform and portrait paths identical.
  return decode_png_memory(preview->bytes, preview->byte_count, pixels_out,
                           width_out, height_out);
}

static int gameplan_portrait_cache_slot(uint32_t portrait_id) {
  if (!portrait_id)
    return -1;
  for (int slot = 0; slot < PREMATCH_GAMEPLAN_PORTRAIT_CACHE_SIZE; slot++) {
    if (gl.player_portrait_id[slot] == portrait_id &&
        gl.player_portrait_texture[slot]) {
      gl.player_portrait_stamp[slot] = ++gl.player_portrait_clock;
      return slot;
    }
  }
  return -1;
}

static int gameplan_portrait_replacement_slot(uint32_t portrait_id) {
  int oldest = 0;
  for (int slot = 0; slot < PREMATCH_GAMEPLAN_PORTRAIT_CACHE_SIZE; slot++) {
    if (gl.player_portrait_id[slot] == portrait_id)
      return slot;
    if (!gl.player_portrait_id[slot])
      return slot;
    if (gl.player_portrait_stamp[slot] <
        gl.player_portrait_stamp[oldest])
      oldest = slot;
  }
  return oldest;
}

static void prepare_gameplan_portraits(int active) {
  if (!active)
    return;

  PesPrematchGameplanPortraitPng *pending[2][40] = {{0}};
  int have_pending = 0;
  for (uint32_t side = 0; side < 2; side++) {
    for (uint32_t index = 0; index < 40; index++) {
      pending[side][index] =
          pes_controller_custom_prematch_gameplan_take_portrait_png(side,
                                                                    index);
      have_pending |= pending[side][index] != NULL;
    }
  }
  if (!have_pending)
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
    for (uint32_t index = 0; index < 40; index++) {
      PesPrematchGameplanPortraitPng *portrait = pending[side][index];
      if (!portrait)
        continue;
      unsigned char *pixels = NULL;
      GLint width = 0;
      GLint height = 0;
      if (decode_png_memory(portrait->bytes, portrait->byte_count, &pixels,
                            &width, &height)) {
        const int slot =
            gameplan_portrait_replacement_slot(portrait->portrait_id);
        if (!gl.player_portrait_texture[slot])
          glGenTextures(1, &gl.player_portrait_texture[slot]);
        if (gl.player_portrait_texture[slot]) {
          glBindTexture(GL_TEXTURE_2D, gl.player_portrait_texture[slot]);
          glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
          glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
          glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S,
                          GL_CLAMP_TO_EDGE);
          glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T,
                          GL_CLAMP_TO_EDGE);
          glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA,
                       GL_UNSIGNED_BYTE, pixels);
          gl.player_portrait_id[slot] = portrait->portrait_id;
          gl.player_portrait_stamp[slot] = ++gl.player_portrait_clock;
        }
      }
      free(pixels);
      free(portrait);
    }
  }

  glPixelStorei(GL_UNPACK_ALIGNMENT, saved_unpack_alignment);
  glBindTexture(GL_TEXTURE_2D, (GLuint)saved_texture);
  glActiveTexture((GLenum)saved_active_texture);
}

static GLuint gameplan_portrait_texture(uint32_t portrait_id) {
  const int slot = gameplan_portrait_cache_slot(portrait_id);
  return slot >= 0 ? gl.player_portrait_texture[slot] : 0;
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

static int emit_corner_outline(float x, float y, float width, float height,
                               float length, float thickness,
                               GLfloat *verts) {
  int quads = 0;
  length = fminf(length, fminf(width, height) * 0.45f);
  quads += emit_rect(x, y, length, thickness, verts + quads * 24);
  quads += emit_rect(x, y, thickness, length, verts + quads * 24);
  quads += emit_rect(x + width - length, y, length, thickness,
                     verts + quads * 24);
  quads += emit_rect(x + width - thickness, y, thickness, length,
                     verts + quads * 24);
  quads += emit_rect(x, y + height - thickness, length, thickness,
                     verts + quads * 24);
  quads += emit_rect(x, y + height - length, thickness, length,
                     verts + quads * 24);
  quads += emit_rect(x + width - length, y + height - thickness, length,
                     thickness, verts + quads * 24);
  quads += emit_rect(x + width - thickness, y + height - length, thickness,
                     length, verts + quads * 24);
  return quads;
}

// FPS counter (config.show_fps): draws the rate top-left, refreshed twice a
// second. Saves and restores all the GL state it touches.
static struct {
  u64 window_start;
  u32 frames;
  char text[8];
} fps;

static uint32_t main_menu_visual_row(uint32_t native_index) {
  static const uint8_t native_to_visual[4] = {0, 3, 1, 2};
  return native_index < 4 ? native_to_visual[native_index] : 0;
}

static struct {
  int initialized;
  uint32_t previous;
  uint32_t current;
  u64 started_tick;
} main_menu_portrait_transition;

static float update_main_menu_portrait_transition(int active,
                                                  uint32_t visual_row) {
  if (!active) {
    memset(&main_menu_portrait_transition, 0,
           sizeof(main_menu_portrait_transition));
    return 1.0f;
  }
  if (!main_menu_portrait_transition.initialized) {
    main_menu_portrait_transition.initialized = 1;
    main_menu_portrait_transition.previous = visual_row;
    main_menu_portrait_transition.current = visual_row;
    main_menu_portrait_transition.started_tick = armGetSystemTick();
    return 1.0f;
  }
  if (main_menu_portrait_transition.current != visual_row) {
    main_menu_portrait_transition.previous =
        main_menu_portrait_transition.current;
    main_menu_portrait_transition.current = visual_row;
    main_menu_portrait_transition.started_tick = armGetSystemTick();
  }
  float progress = (float)armTicksToNs(
                       armGetSystemTick() -
                       main_menu_portrait_transition.started_tick) /
                   220000000.0f;
  if (progress >= 1.0f)
    return 1.0f;
  if (progress < 0.0f)
    progress = 0.0f;
  return progress * progress * (3.0f - 2.0f * progress);
}

static float main_menu_row_focus_amount(uint32_t row, float transition) {
  if (row == main_menu_portrait_transition.current)
    return transition;
  if (row == main_menu_portrait_transition.previous &&
      main_menu_portrait_transition.previous !=
          main_menu_portrait_transition.current)
    return 1.0f - transition;
  return 0.0f;
}

static struct {
  int initialized;
  u64 started_tick;
} title_portrait_cycle;

static float update_title_portrait_cycle(int active, uint32_t *previous,
                                         uint32_t *current) {
  if (!active) {
    memset(&title_portrait_cycle, 0, sizeof(title_portrait_cycle));
    if (previous) *previous = 0;
    if (current) *current = 0;
    return 1.0f;
  }

  const u64 now = armGetSystemTick();
  if (!title_portrait_cycle.initialized) {
    title_portrait_cycle.initialized = 1;
    title_portrait_cycle.started_tick = now;
  }

  const uint64_t elapsed_ns = armTicksToNs(
      now - title_portrait_cycle.started_tick);
  const uint64_t hold_ns = 5000000000ULL;
  const uint64_t fade_ns = 450000000ULL;
  const uint64_t slot = elapsed_ns / hold_ns;
  const uint32_t next = (uint32_t)(slot % 4ULL);
  const uint32_t prior = slot ? (next + 3u) % 4u : next;
  if (previous) *previous = prior;
  if (current) *current = next;

  if (!slot)
    return 1.0f;
  const uint64_t phase_ns = elapsed_ns % hold_ns;
  if (phase_ns >= fade_ns)
    return 1.0f;
  float progress = (float)phase_ns / (float)fade_ns;
  return progress * progress * (3.0f - 2.0f * progress);
}

#if defined(DEBUG_LOG) && DEBUG_LOG
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

#endif
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
  const uint32_t custom_2p_transition_kind =
      custom_2p_transition ? pes_controller_2p_transition_kind()
                           : PES_2P_TRANSITION_NONE;
  const int goal_demo_active =
      controller_snapshot.surface == PES_CONTROLLER_SURFACE_GOAL_DEMO;
  const int goal_demo_player =
      goal_demo_active && controller_snapshot.goal_player;
  // Replay and generic demo input remains fully active, but does not need a
  // controller legend. Those short-lived surfaces can alternate around every
  // transition and made the old "ANY BUTTON - SKIP" text visibly blink. Keep
  // a helper only for the interactive GoalDemo page where A/B have distinct
  // meanings.
  int cinematic_helper_active =
      !custom_2p_transition && goal_demo_active &&
      controller_snapshot.goal_helper_visible &&
      !pes_controller_replay_active();
  const int cinematic_goal_actions = goal_demo_player;
  const int cinematic_goal_two_player =
      goal_demo_active && pes_controller_native_pad_lab_two_player();
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
  uint32_t penalty_role_p1 =
      custom_2p_transition ? PES_PENALTY_NONE
                           : pes_controller_penalty_role_for_pad(0);
  const int penalty_two_player = pes_controller_native_pad_lab_two_player();
  uint32_t penalty_role_p2 =
      (!custom_2p_transition && penalty_two_player)
          ? pes_controller_penalty_role_for_pad(1)
          : PES_PENALTY_NONE;
  const int set_piece_selector =
      !custom_2p_transition && pes_controller_set_piece_selector_active();
  float selector_x = 0.0f;
  float selector_y = 0.0f;
  float selector_width = 0.0f;
  float selector_height = 0.0f;
  const int cup_team_picker = competition_frontend_cup_team_picker_active();
  const int cup_settings_popup =
      competition_frontend_state() == COMPETITION_FRONTEND_CUP_SETTINGS;
  const int custom_2p_team_selector =
      pes_controller_2p_team_selector_active() || cup_team_picker;
  const int custom_selector_exhibition =
      custom_2p_team_selector && !cup_team_picker &&
      pes_controller_2p_team_selector_exhibition_mode();
  const int custom_2p_prematch_hub_raw =
      pes_controller_2p_prematch_hub_active();
  const int custom_settings_popup =
      pes_controller_custom_match_settings_active();
  const int pause_settings_popup = pes_controller_pause_camera_active();
  const int custom_hub_settings_popup = cup_settings_popup ||
      pause_settings_popup ||
      (custom_settings_popup && custom_2p_prematch_hub_raw);
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
  const int main_menu_host = pes_main_menu_controller_active();
  const int custom_competition = competition_frontend_active() &&
                                 !cup_settings_popup && !cup_team_picker;
  static CompetitionFrontendState competition_previous_state =
      COMPETITION_FRONTEND_NONE;
  static CompetitionFrontendState competition_render_state =
      COMPETITION_FRONTEND_NONE;
  static uint32_t competition_render_focus;
  static uint32_t competition_render_item_count;
  static u64 competition_transition_tick;
  static int competition_closing_transition;
  const CompetitionFrontendState competition_current_state =
      competition_frontend_state();
  if (custom_competition && competition_current_state !=
                              COMPETITION_FRONTEND_NONE) {
    if (competition_current_state != competition_previous_state ||
        competition_closing_transition) {
      competition_transition_tick = armGetSystemTick();
      competition_closing_transition = 0;
    }
    competition_previous_state = competition_current_state;
    competition_render_state = competition_current_state;
    competition_render_focus = competition_frontend_focus();
    competition_render_item_count = competition_frontend_item_count();
  } else if (custom_competition && competition_frontend_closing()) {
    if (!competition_closing_transition) {
      competition_transition_tick = armGetSystemTick();
      competition_closing_transition = 1;
    }
  } else if (!custom_competition) {
    competition_previous_state = COMPETITION_FRONTEND_NONE;
    competition_render_state = COMPETITION_FRONTEND_NONE;
    competition_transition_tick = 0;
    competition_closing_transition = 0;
  }
  float competition_menu_mix = 1.0f;
  if (custom_competition && competition_transition_tick) {
    const u64 elapsed = armTicksToNs(armGetSystemTick() -
                                     competition_transition_tick);
    competition_menu_mix = (float)elapsed / 240000000.0f;
    if (competition_menu_mix > 1.0f)
      competition_menu_mix = 1.0f;
    competition_menu_mix = competition_menu_mix * competition_menu_mix *
                           (3.0f - 2.0f * competition_menu_mix);
    if (competition_closing_transition) {
      competition_menu_mix = 1.0f - competition_menu_mix;
      if (competition_menu_mix <= 0.001f) {
        competition_frontend_finish_close();
        competition_menu_mix = 0.0f;
      }
    }
  }
  const CompetitionFrontendState competition_display_state =
      competition_render_state;
  const uint32_t competition_display_focus = competition_render_focus;
  const uint32_t competition_display_item_count = competition_render_item_count;
  // The stock selector's blue focus/glow belongs to the native menu.  Both
  // custom 2P surfaces fully own the frame, so letting that geometry draw on
  // top makes the entire hub look like a blue selection wash.
  const int selector = !set_piece_selector && !custom_2p_team_selector &&
                       !custom_2p_prematch_hub_raw && !custom_2p_transition &&
                       !main_menu_host && !custom_competition &&
                       pes_controller_selector_rect(
      &selector_x, &selector_y, &selector_width, &selector_height);
  const int selector_custom =
      selector && pes_controller_selector_custom_style();
  const int custom_team_popup = pes_controller_custom_team_popup_active();
  const int custom_cpu_popup = pes_controller_custom_cpu_popup_active();
  const int custom_video_settings_popup =
      pes_controller_custom_video_settings_active();
  const int custom_gameplan =
      pes_controller_custom_prematch_gameplan_active();
  const int custom_gameplan_exhibition =
      custom_gameplan && pes_controller_exhibition_single_controller_mode();
  const int pause_skin = pes_controller_pause_skin_active();
  const uint32_t pause_transition = pes_controller_pause_transition();
  // The result surfaces reuse the pause layout. Pause wins if both claim the
  // frame so a lingering result heartbeat can never cover a live pause menu.
  const uint32_t result_surface =
      pause_skin ? PES_MATCH_RESULT_SURFACE_NONE
                 : pes_controller_match_result_skin();
  const int result_skin = result_surface != PES_MATCH_RESULT_SURFACE_NONE;
  // Loading cover for the result pages, same treatment as pause -> Game Plan:
  // the custom background is the whole screen with a small corner spinner. It
  // outlives the skin so a page being rebuilt never flashes its native stats.
  const int result_transition =
      !pause_skin && pes_controller_match_result_transition() != 0;
  const int custom_info_popup =
      pes_controller_custom_info_popup_active() && !pause_skin && !result_skin;
  const int custom_main_menu_dark_popup =
      main_menu_host && (custom_video_settings_popup || custom_info_popup);
  // Match Settings is a modal child of the hub.  Let the existing settings
  // renderer own the foreground while retaining the hub as its visual host.
  const int custom_2p_prematch_hub =
      custom_2p_prematch_hub_raw && !custom_settings_popup &&
      !custom_gameplan &&
      custom_hub_page == PES_2P_PREMATCH_HUB_PAGE_MAIN;
  const int custom_popup =
      pause_settings_popup || custom_team_popup || custom_cpu_popup || custom_settings_popup ||
      custom_video_settings_popup || custom_info_popup || set_piece_selector ||
      custom_2p_team_selector || custom_hub_settings_popup ||
      custom_2p_prematch_hub_raw ||
      custom_2p_transition || custom_gameplan || custom_competition;
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
  const int startup_transition =
      !custom_2p_transition && pes_controller_startup_transition_active();
  const int start_prompt =
      !startup_transition && !custom_2p_transition &&
      pes_controller_start_prompt(NULL, NULL);
  uint32_t title_portrait_previous = 0;
  uint32_t title_portrait_current = 0;
  const float title_portrait_mix = update_title_portrait_cycle(
      start_prompt, &title_portrait_previous, &title_portrait_current);
  const int custom_main_menu =
      main_menu_host && !start_prompt && !custom_competition &&
      !cup_settings_popup &&
      !custom_2p_team_selector &&
      !custom_2p_prematch_hub_raw && !custom_2p_transition &&
      !startup_transition &&
      !custom_gameplan && !pause_skin && !result_skin && !result_transition &&
      !pause_camera_active && !tutorial_play_active;
  const uint32_t custom_main_menu_row =
      main_menu_visual_row(pes_main_menu_focus_index());
  const float custom_main_menu_mix = update_main_menu_portrait_transition(
      custom_main_menu, custom_main_menu_row);
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
    // corner/free kick briefly fall back to the exhibition helper legend.
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
      !pause_settings_popup &&
      pes_controller_gameplan_cursor_position(&gameplan_cursor_x,
                                              &gameplan_cursor_y) &&
      !pause_skin && !result_skin && !result_transition &&
      !pes_controller_custom_prematch_gameplan_active();

  const int modal_match_frontend =
      pause_skin || pause_transition ||
      virtual_cursor_context == PES_VIRTUAL_CURSOR_PAUSE ||
      virtual_cursor_context == PES_VIRTUAL_CURSOR_GAMEPLAN || result_skin ||
      result_transition ||
      pause_camera_active || pes_controller_custom_prematch_gameplan_active();
  if (modal_match_frontend) {
    // Pause and its Game Plan/Camera children own the foreground. Keep the
    // set-play state latched underneath, but suppress its mapper until the
    // match resumes.
    setplay_context = PES_SETPLAY_NONE;
    setplay_options = 0;
    native_setplay_debug = 0;
    cinematic_helper_active = 0;
    penalty_role_p1 = PES_PENALTY_NONE;
    penalty_role_p2 = PES_PENALTY_NONE;
  }

  // The custom selector owns the modal presentation. Do not let the
  // underlying match set-play legend bleed through its footer.
  if (set_piece_selector || tutorial_play_active) {
    setplay_context = PES_SETPLAY_NONE;
    setplay_options = 0;
  }
  // Penalty is a controller-owned surface, not a set-piece selector.  The
  // stock ButtonSetplay snapshot can still carry its old option bits for a
  // few frames, which used to repaint the stale set-piece-taker helper
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

  PesStaminaBarSnapshot stamina_bars[PES_STAMINA_BAR_CAPACITY] = {{0}};
  float stamina_reveal[PES_STAMINA_BAR_CAPACITY] = {0.0f};
  uint32_t stamina_bar_count = 0;
#ifdef DEBUG_LOG
  static uint32_t hud_diag_draws;
#endif
  if (!custom_popup && !modal_match_frontend && !tutorial_play_active &&
      !startup_transition && !start_prompt && !custom_main_menu &&
      controller_snapshot.surface == PES_CONTROLLER_SURFACE_NONE) {
    stamina_bar_count = pes_controller_stamina_bars(
        stamina_bars, PES_STAMINA_BAR_CAPACITY);
  }

  // Replay/pause/loading is a hard visibility cut, but not a new presentation
  // session. The entrance animation is played once per MatchSetup and never
  // again for cursor changes or temporary gameplay transitions.
  static uint32_t stamina_introduced_mask = 0;
  static uint32_t stamina_reveal_session = UINT32_MAX;
  static uint32_t stamina_player_no[PES_STAMINA_BAR_CAPACITY] = {
      UINT32_MAX, UINT32_MAX};
  static float stamina_display_power[PES_STAMINA_BAR_CAPACITY] = {0.0f};
  static uint64_t stamina_appeared_tick[PES_STAMINA_BAR_CAPACITY] = {0};
  const uint64_t stamina_now = armGetSystemTick();
  const uint32_t stamina_session = pes_controller_match_hud_session();
  if (stamina_reveal_session != stamina_session) {
    stamina_reveal_session = stamina_session;
    stamina_introduced_mask = 0;
    memset(stamina_appeared_tick, 0, sizeof(stamina_appeared_tick));
    for (uint32_t side = 0; side < PES_STAMINA_BAR_CAPACITY; ++side)
      stamina_player_no[side] = UINT32_MAX;
  }
  for (uint32_t i = 0; i < stamina_bar_count; ++i) {
    const uint32_t side = stamina_bars[i].side;
    if (side >= PES_STAMINA_BAR_CAPACITY)
      continue;
    const uint32_t bit = 1u << side;
    const int switched = stamina_player_no[side] != stamina_bars[i].player_no;
    if (!(stamina_introduced_mask & bit)) {
      stamina_appeared_tick[side] = stamina_now;
      stamina_display_power[side] = stamina_bars[i].power;
      stamina_player_no[side] = stamina_bars[i].player_no;
      stamina_introduced_mask |= bit;
    } else if (switched) {
      // A control switch replaces the value immediately but must not replay
      // the kickoff reveal every time selection moves to another player.
      stamina_display_power[side] = stamina_bars[i].power;
      stamina_player_no[side] = stamina_bars[i].player_no;
    } else {
      // Native stamina changes in discrete percentage steps. A short visual
      // ease keeps depletion organic without adding simulation latency.
      stamina_display_power[side] +=
          (stamina_bars[i].power - stamina_display_power[side]) * 0.18f;
    }
    stamina_bars[i].power = stamina_display_power[side];
    float reveal = stamina_appeared_tick[side]
                       ? (float)armTicksToNs(
                             stamina_now - stamina_appeared_tick[side]) /
                             220000000.0f
                       : 1.0f;
    if (reveal > 1.0f)
      reveal = 1.0f;
    if (reveal < 0.0f)
      reveal = 0.0f;
    stamina_reveal[i] = reveal * reveal * (3.0f - 2.0f * reveal);
  }
#ifdef DEBUG_LOG
  pes_controller_hud_diagnostic(
      (!!custom_popup) | ((!!modal_match_frontend) << 1) |
      ((!!tutorial_play_active) << 2) | ((!!startup_transition) << 3) |
      ((!!start_prompt) << 4) | ((!!custom_main_menu) << 5) |
      ((controller_snapshot.surface != PES_CONTROLLER_SURFACE_NONE) << 6),
      stamina_bar_count, hud_diag_draws, stamina_reveal[0], stamina_reveal[1]);
#endif
  if ((!config.show_fps || !fps.text[0]) && !selector && !custom_main_menu &&
      !custom_competition &&
      !startup_transition && !start_prompt && !custom_popup &&
      !gameplan_cursor &&
      !native_lab &&
      !stamina_bar_count &&
      !result_skin && !result_transition &&
      !setplay_options && !pause_camera_active && !tutorial_play_active &&
      !cinematic_helper_active && penalty_role_p1 == PES_PENALTY_NONE &&
      penalty_role_p2 == PES_PENALTY_NONE)
    return;
  if (!gl_init())
    return;
  prepare_uniform_thumbnail_preview(custom_hub_kits_page);
  prepare_gameplan_portraits(custom_gameplan || stamina_bar_count);
  // A/B helper glyphs share the main-menu button textures. GoalDemo can be the
  // first custom surface in a session, so include it in the upload gate rather
  // than binding two generated-but-empty texture names.
  prepare_main_menu_assets(start_prompt ||
                           custom_main_menu || custom_competition ||
                           custom_popup || pause_skin ||
                           result_skin || cinematic_helper_active);
  prepare_switch_button_assets(custom_competition || custom_popup ||
                               pause_skin || result_skin ||
                               cinematic_helper_active || native_lab ||
                               setplay_options ||
                               penalty_session_active);

  static GLfloat verts[4096 * 24];
  int quads = 0;
  // Controller legends use one optical text size across every custom page.
  // Content labels retain their own hierarchy.
  const float helper_text_gh = roundf((float)screen_height / 43.0f);
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
  int custom_loading_spinner_first_quad = 0;
  int custom_loading_spinner_quads = 0;
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
  int setplay_helper_text_first_quad = 0;
  int setplay_helper_text_quads = 0;
  int power_gauge_background_first_quad[2] = {0};
  int power_gauge_background_quads[2] = {0};
  int power_gauge_segment_first_quad[2] = {0};
  int power_gauge_segment_quads[2] = {0};
  int power_gauge_active_segments[2] = {0};
  int stamina_shadow_first_quad[2] = {0};
  int stamina_shadow_quads[2] = {0};
  int stamina_track_first_quad[2] = {0};
  int stamina_track_quads[2] = {0};
  int stamina_fill_first_quad[2] = {0};
  int stamina_fill_quads[2] = {0};
  int stamina_highlight_first_quad[2] = {0};
  int stamina_highlight_quads[2] = {0};
  RoundedRectStyle stamina_shadow_style[2] = {{0}};
  RoundedRectStyle stamina_track_style[2] = {{0}};
  RoundedRectStyle stamina_fill_style[2] = {{0}};
  RoundedRectStyle stamina_highlight_style[2] = {{0}};
  float stamina_alpha[2] = {0.0f};
  float stamina_fill_rgb[2][3] = {{0}};
  int hud_card_quad[2] = {0}, hud_portrait_quad[2] = {0};
  int hud_badge_quad[2] = {0}, hud_text_quad[2] = {0}, hud_text_count[2] = {0};
  GLuint hud_portrait_texture[2] = {0};
  RoundedRectStyle hud_card_style[2] = {{0}};
  int cinematic_helper_text_first_quad = 0;
  int cinematic_helper_text_quads = 0;
  int gameplan_cursor_first_quad = 0;
  int pause_skin_cards[4] = {0};
  int pause_skin_text = 0, pause_skin_text_quads = 0;
  int pause_stats_panel = 0, pause_stats_text = 0, pause_stats_quads = 0;
  int pause_helper_text = 0, pause_helper_text_quads = 0;
  int pause_background = 0, pause_badges = 0, pause_header = 0, pause_header_count = 0;
  int pause_skin_focus = -1;
  int pause_transition_spinner = 0, pause_transition_spinner_count = 0;
  int pause_confirm_backdrop = 0, pause_confirm_panel = 0;
  int pause_confirm_buttons[2] = {0, 0};
  int pause_confirm_title = 0, pause_confirm_message = 0;
  int pause_confirm_button_text[2] = {0, 0};
  int pause_confirm_button_text_quads[2] = {0, 0};
  int pause_confirm_title_quads = 0, pause_confirm_message_quads = 0;
  RoundedRectStyle pause_confirm_panel_style = {0};
  RoundedRectStyle pause_confirm_button_style = {0};
  int gameplan_locked_rows = 0, gameplan_locked_row_count = 0;
  RoundedRectStyle pause_skin_style = {0};
  // Half/full time result skin: identical layout to the pause skin, only the
  // card row differs, so it keeps its own quad ranges but the same geometry.
  int result_cards[3] = {0};
  int result_card_count = 0;
  int result_card_text = 0, result_card_text_quads = 0;
  int result_stats_panel = 0, result_stats_text = 0, result_stats_quads = 0;
  int result_helper_text = 0, result_helper_text_quads = 0;
  int result_background = 0, result_badges = 0;
  int result_header = 0, result_header_count = 0;
  int result_focus = -1;
  RoundedRectStyle result_card_style = {0};
  int result_cover_background = 0;
  int result_cover_spinner = 0, result_cover_spinner_count = 0;
  int startup_transition_background_quad = 0;
  int startup_transition_spinner_first_quad = 0;
  int startup_transition_spinner_quads = 0;
  int startup_transition_text_first_quad = 0;
  int startup_transition_text_quads = 0;
  int title_background_quad = 0;
  int title_portrait_quad = 0;
  int title_brand_quad = 0;
  int title_button_a_quad = 0;
  int title_prompt_text_first_quad = 0, title_prompt_text_quads = 0;
  int title_footer_first_quad = 0, title_footer_quads = 0;
  int main_menu_background_quad = 0;
  int main_menu_portrait_quad = 0;
  int main_menu_card_quads[4] = {0};
  int main_menu_icon_quads[4] = {0};
  int main_menu_label_first_quad[4] = {0};
  int main_menu_label_quads[4] = {0};
  int main_menu_brand_quad = 0;
  int main_menu_button_a_quad = 0;
  int main_menu_helper_first_quad = 0, main_menu_helper_quads = 0;
  int competition_background_quad = 0;
  int competition_brand_quad = 0;
  int competition_portrait_quad = 0;
  int competition_departing_card_quads[4] = {0};
  int competition_departing_icon_quads[4] = {0};
  int competition_departing_label_first_quad[4] = {0};
  int competition_departing_label_quads[4] = {0};
  int competition_focus_quad = -1;
  int competition_row_quads[12] = {0};
  int competition_icon_quads[12] = {0};
  int competition_value_plate_quads[12] = {0};
  int competition_title_first_quad = 0, competition_title_quads = 0;
  int competition_label_first_quad[12] = {0};
  int competition_label_quads[12] = {0};
  int competition_value_first_quad[12] = {0};
  int competition_value_quads[12] = {0};
  int competition_status_first_quad = 0, competition_status_quads = 0;
  int competition_helper_first_quad = 0, competition_helper_quads = 0;
  int competition_bracket_card_quads[8] = {0};
  int competition_bracket_text_first_quad[8] = {0};
  int competition_bracket_text_quads[8] = {0};
  int cup_shell_quad = 0, cup_header_quad = 0;
  int cup_left_quad = 0, cup_right_quad = 0;
  int cup_fixture_quads[8] = {0};
  int cup_fixture_away_quads[8] = {0};
  int cup_bye_quads[8] = {0};
  int cup_border_first = 0, cup_border_count = 0;
  int cup_next_quads[4] = {0};
  int cup_next_away_quads[4] = {0};
  int cup_history_quads[5] = {0};
  int cup_action_quads[2] = {0};
  int cup_focus_fixture = -1;
  int cup_connector_first = 0, cup_connector_count = 0;
  int cup_badge_first = 0, cup_badge_count = 0;
  int cup_text_first = 0, cup_text_count = 0;
  int cup_action_text_first[2] = {0};
  int cup_action_text_count[2] = {0};
  RoundedRectStyle cup_shell_style = {0};
  RoundedRectStyle cup_header_style = {0};
  RoundedRectStyle cup_left_style = {0};
  RoundedRectStyle cup_right_style = {0};
  RoundedRectStyle cup_fixture_style = {0};
  RoundedRectStyle cup_bye_style = {0};
  RoundedRectStyle cup_next_style = {0};
  RoundedRectStyle cup_history_style = {0};
  RoundedRectStyle cup_action_style = {0};
  int competition_full_panel_quad = 0;
  int competition_full_header_round_quad = 0;
  int competition_full_header_fill_quad = 0;
  int competition_full_selected_quad = 0;
  int competition_full_rule_first_quad = 0;
  int competition_full_rule_quads = 0;
  int competition_full_arrow_first_quad = 0;
  int competition_full_arrow_quads = 0;
  int competition_full_action_button_quad = 0;
  int competition_full_action_text_first_quad = 0;
  int competition_full_action_text_quads = 0;
  int competition_team_picker_quad = 0;
  int competition_team_picker_candidate_quad = 0;
  int competition_team_picker_title_first_quad = 0;
  int competition_team_picker_title_quads = 0;
  int competition_team_picker_value_first_quad = 0;
  int competition_team_picker_value_quads = 0;
  int competition_team_picker_row_quads[5] = {0};
  int competition_team_picker_row_text_first_quad[5] = {0};
  int competition_team_picker_row_text_quads[5] = {0};
  int competition_team_slot_quads[8] = {0};
  int competition_team_slot_badge_quads[8] = {0};
  RoundedRectStyle competition_team_picker_style = {0};
  RoundedRectStyle competition_team_picker_candidate_style = {0};
  RoundedRectStyle competition_team_slot_style = {0};
  int switch_helper_quads[48], switch_helper_count = 0;
  GLuint switch_helper_textures[48];
#define ADD_SWITCH_HELPER(KEY, CENTER_X, CENTER_Y, SIZE)                 \
  do {                                                                  \
    if (switch_helper_count <                                           \
        (int)(sizeof(switch_helper_quads) /                              \
              sizeof(switch_helper_quads[0]))) {                         \
      switch_helper_quads[switch_helper_count] = quads;                 \
      switch_helper_textures[switch_helper_count++] =                   \
          switch_button_texture((KEY));                                 \
    }                                                                   \
    quads += emit_image_rect((CENTER_X) - (SIZE) * 0.5f,                \
                             (CENTER_Y) - (SIZE) * 0.5f, (SIZE), (SIZE),\
                             verts + quads * 24);                        \
  } while (0)
  RoundedRectStyle main_menu_card_style = {0};
  RoundedRectStyle competition_departing_style = {0};
  RoundedRectStyle competition_row_style = {0};
  RoundedRectStyle competition_value_style = {0};
  RoundedRectStyle competition_full_panel_style = {0};
  RoundedRectStyle competition_full_header_style = {0};
  RoundedRectStyle competition_full_selected_style = {0};
  RoundedRectStyle competition_full_value_style = {0};
  RoundedRectStyle competition_full_action_style = {0};
  int gameplan_cursor_quads = 0;
  enum {
    PREMATCH_GAMEPLAN_FIELD_SLOTS = 11,
    PREMATCH_GAMEPLAN_VISIBLE_BENCH = 8,
    PREMATCH_GAMEPLAN_VISIBLE_PICKER = 7,
  };
  int prematch_gameplan_backdrop_first_quad = 0;
  int prematch_gameplan_backdrop_quads = 0;
  int prematch_gameplan_panel_first_quad = 0;
  int prematch_gameplan_panel_quads = 0;
  int prematch_gameplan_header_first_quad[2] = {0};
  int prematch_gameplan_header_quads[2] = {0};
  int prematch_gameplan_pitch_first_quad[2] = {0};
  int prematch_gameplan_pitch_quads[2] = {0};
  int prematch_gameplan_stripe_first_quad[2] = {0};
  int prematch_gameplan_stripe_quads[2] = {0};
  int prematch_gameplan_line_first_quad[2] = {0};
  int prematch_gameplan_line_quads[2] = {0};
  int prematch_gameplan_neutral_first_quad[2] = {0};
  int prematch_gameplan_neutral_quads[2] = {0};
  int prematch_gameplan_modal_first_quad[2] = {0};
  int prematch_gameplan_modal_quads[2] = {0};
  int prematch_gameplan_accent_first_quad[2] = {0};
  int prematch_gameplan_accent_quads[2] = {0};
  int prematch_gameplan_focus_outline_first_quad[2] = {0};
  int prematch_gameplan_focus_outline_quads[2] = {0};
  int prematch_gameplan_selected_outline_first_quad[2] = {0};
  int prematch_gameplan_selected_outline_quads[2] = {0};
  int prematch_gameplan_context_plate_first_quad[2] = {0};
  int prematch_gameplan_context_plate_quads[2] = {0};
  int prematch_gameplan_badge_first_quad[2] = {0};
  int prematch_gameplan_badge_quads[2] = {0};
  int prematch_gameplan_action_first_quad[2] = {0};
  int prematch_gameplan_action_quads[2] = {0};
  int prematch_gameplan_action_selected_first_quad[2] = {0};
  int prematch_gameplan_action_selected_quads[2] = {0};
  int prematch_gameplan_portrait_quad[2][2][40];
  memset(prematch_gameplan_portrait_quad, -1,
         sizeof(prematch_gameplan_portrait_quad));
  int prematch_gameplan_field_plate_first_quad[2] = {0};
  int prematch_gameplan_field_plate_quads[2] = {0};
  int prematch_gameplan_waiting_first_quad[2] = {0};
  int prematch_gameplan_waiting_quads[2] = {0};
  int prematch_gameplan_waiting_text_first_quad[2] = {0};
  int prematch_gameplan_waiting_text_quads[2] = {0};
  int prematch_gameplan_field_metric_first[2][11];
  int prematch_gameplan_field_metric_quads[2][11];
  int prematch_gameplan_field_role_first[2][11];
  int prematch_gameplan_field_role_quads[2][11];
  uint32_t prematch_gameplan_field_role_band[2][11];
  int prematch_gameplan_bench_metric_first[2][8];
  int prematch_gameplan_bench_metric_quads[2][8];
  int prematch_gameplan_picker_metric_first[2][7];
  int prematch_gameplan_picker_metric_quads[2][7];
  int prematch_gameplan_picker_foot_first_quad[2] = {0};
  int prematch_gameplan_picker_foot_quads[2] = {0};
  int prematch_gameplan_picker_active_text_first[2][7];
  int prematch_gameplan_picker_active_text_quads[2][7];
  int prematch_gameplan_auto_gain_first[2][2];
  int prematch_gameplan_auto_gain_quads[2][2];
  memset(prematch_gameplan_field_metric_first, -1,
         sizeof(prematch_gameplan_field_metric_first));
  memset(prematch_gameplan_field_role_first, -1,
         sizeof(prematch_gameplan_field_role_first));
  memset(prematch_gameplan_field_role_quads, 0,
         sizeof(prematch_gameplan_field_role_quads));
  memset(prematch_gameplan_field_role_band, 0,
         sizeof(prematch_gameplan_field_role_band));
  memset(prematch_gameplan_bench_metric_first, -1,
         sizeof(prematch_gameplan_bench_metric_first));
  memset(prematch_gameplan_picker_metric_first, -1,
         sizeof(prematch_gameplan_picker_metric_first));
  memset(prematch_gameplan_field_metric_quads, 0,
         sizeof(prematch_gameplan_field_metric_quads));
  memset(prematch_gameplan_bench_metric_quads, 0,
         sizeof(prematch_gameplan_bench_metric_quads));
  memset(prematch_gameplan_picker_metric_quads, 0,
         sizeof(prematch_gameplan_picker_metric_quads));
  memset(prematch_gameplan_picker_active_text_first, -1,
         sizeof(prematch_gameplan_picker_active_text_first));
  memset(prematch_gameplan_picker_active_text_quads, 0,
         sizeof(prematch_gameplan_picker_active_text_quads));
  memset(prematch_gameplan_auto_gain_first, -1,
         sizeof(prematch_gameplan_auto_gain_first));
  memset(prematch_gameplan_auto_gain_quads, 0,
         sizeof(prematch_gameplan_auto_gain_quads));
  int prematch_gameplan_role_plate_first_quad[4] = {0};
  int prematch_gameplan_role_plate_quads[4] = {0};
  int prematch_gameplan_role_text_first_quad = 0;
  int prematch_gameplan_role_text_quads = 0;
  int prematch_gameplan_white_text_first_quad = 0;
  int prematch_gameplan_white_text_quads = 0;
  int prematch_gameplan_header_text_first_quad[2] = {0};
  int prematch_gameplan_header_text_quads[2] = {0};
  int prematch_gameplan_body_text_first_quad[2] = {0};
  int prematch_gameplan_body_text_quads[2] = {0};
  int prematch_gameplan_field_text_first_quad[2] = {0};
  int prematch_gameplan_field_text_quads[2] = {0};
  int prematch_gameplan_action_text_first_quad[2] = {0};
  int prematch_gameplan_action_text_quads[2] = {0};
  int prematch_gameplan_focus_text_first_quad[2] = {0};
  int prematch_gameplan_focus_text_quads[2] = {0};
  int prematch_gameplan_muted_text_first_quad = 0;
  int prematch_gameplan_muted_text_quads = 0;
  int prematch_gameplan_accent_text_first_quad[2] = {0};
  int prematch_gameplan_accent_text_quads[2] = {0};
  float prematch_gameplan_field_rect[2][PREMATCH_GAMEPLAN_FIELD_SLOTS][4] =
      {{{0}}};
  float prematch_gameplan_bench_rect[2][PREMATCH_GAMEPLAN_VISIBLE_BENCH][4] =
      {{{0}}};
  uint32_t prematch_gameplan_bench_start[2] = {0};
  uint32_t prematch_gameplan_bench_visible[2] = {0};
  float prematch_gameplan_picker_rect[2][PREMATCH_GAMEPLAN_VISIBLE_PICKER][4] =
      {{{0}}};
  float prematch_gameplan_context_rect[2][4] = {{0}};
  uint32_t prematch_gameplan_picker_start[2] = {0};
  uint32_t prematch_gameplan_picker_visible[2] = {0};
  RoundedRectStyle custom_panel_style = {0};
  RoundedRectStyle custom_header_style = {0};
  RoundedRectStyle custom_selected_style = {0};
  RoundedRectStyle custom_value_plate_style = {0};
  RoundedRectStyle custom_action_button_style = {0};
  RoundedRectStyle custom_back_button_style = {0};
  RoundedRectStyle prematch_gameplan_panel_style = {0};
  RoundedRectStyle prematch_gameplan_action_style = {0};
  RoundedRectStyle prematch_gameplan_waiting_style = {0};
  RoundedRectStyle prematch_gameplan_modal_style[2] = {{0}};
  RoundedRectStyle prematch_gameplan_field_plate_style = {0};
  RoundedRectStyle prematch_gameplan_context_plate_style = {0};


  for (uint32_t i = 0; i < stamina_bar_count; ++i) {
    const uint32_t side = stamina_bars[i].side;
    if (side >= PES_STAMINA_BAR_CAPACITY)
      continue;
    float power = stamina_bars[i].power;
    if (power < 0.0f)
      power = 0.0f;
    if (power > 1.0f)
      power = 1.0f;
    const float reveal = stamina_reveal[i];
    const float card_w = 0.275f * screen_width;
    const float card_h = 0.057f * screen_height;
    const float card_x = side ? screen_width * 0.98f - card_w : screen_width * 0.02f;
    const float card_y = screen_height * 0.918f + (1.0f - reveal) * 0.020f * screen_height;
    const float horizontal_pad = 0.00625f * screen_width;
    const float cell_gap = 0.0050f * screen_width;
    const float portrait_size = 0.072f * screen_height;
    const float badge_size = 0.032f * screen_height;
    const float badge_x = side ? card_x + card_w - horizontal_pad - badge_size
                               : card_x + horizontal_pad;
    const float portrait_x = side ? badge_x - cell_gap - portrait_size
                                  : badge_x + badge_size + cell_gap;
    const float text_x = side ? card_x + horizontal_pad
                              : portrait_x + portrait_size + cell_gap;
    const float text_right = side ? portrait_x - cell_gap
                                  : card_x + card_w - horizontal_pad;
    const float text_w = fmaxf(1.0f, text_right - text_x);
    hud_card_style[side] = (RoundedRectStyle){card_w, card_h, 1.5f};
    hud_card_quad[side] = quads;
    quads += emit_round_rect_quad(card_x, card_y, card_w, card_h, verts + quads * 24);
    hud_portrait_quad[side] = quads;
    hud_portrait_texture[side] = gameplan_portrait_texture(stamina_bars[i].portrait_id);
    quads += emit_image_rect(portrait_x, card_y + card_h - portrait_size,
                            portrait_size, portrait_size, verts + quads * 24);
    hud_badge_quad[side] = quads;
    quads += emit_badge(stamina_bars[i].badge, badge_x,
                        card_y + (card_h - badge_size) * 0.5f,
                        badge_size, badge_size, verts + quads * 24);
    char label[80];
    if (side)
      snprintf(label, sizeof(label), "%s  %u", stamina_bars[i].name, stamina_bars[i].shirt_number);
    else
      snprintf(label, sizeof(label), "%u  %s", stamina_bars[i].shirt_number, stamina_bars[i].name);
    hud_text_quad[side] = quads;
    hud_text_count[side] = side
        ? emit_efootball_right_fit_line(
              label, (int)strlen(label), text_right,
              card_y + card_h * 0.31f, text_w,
              screen_height * 0.025f, screen_height * 0.019f,
              EFOOTBALL_FONT_REGULAR, verts + quads * 24)
        : emit_efootball_fit_line(
              label, (int)strlen(label), text_x,
              card_y + card_h * 0.31f, text_w,
              screen_height * 0.025f, screen_height * 0.019f,
              EFOOTBALL_FONT_REGULAR, verts + quads * 24);
    quads += hud_text_count[side];
    // The stamina meter belongs to the text plate, not the complete card.
    // Mirror the content flow: home fills from the left, away from the right
    // next to its number and portrait.
    const float bar_w = text_w;
    const float bar_h = 0.0030f * screen_height;
    float x = text_x;
    float y = card_y + 0.0030f * screen_height;
    const float edge = 0.008f * (float)screen_width;
    if (x < edge)
      x = edge;
    if (x + bar_w > (float)screen_width - edge)
      x = (float)screen_width - edge - bar_w;
    if (y < edge)
      y = edge;
    if (y + bar_h > (float)screen_height - edge)
      y = (float)screen_height - edge - bar_h;

    const float inset = 0.25f;
    const float inner_h = fmaxf(1.0f, bar_h - inset * 2.0f);
    const float fill_w = fmaxf(0.0f, (bar_w - inset * 2.0f) * power);
    const float fill_x = side ? x + bar_w - inset - fill_w : x + inset;
    stamina_alpha[side] = reveal;

    stamina_shadow_first_quad[side] = quads;
    stamina_shadow_style[side] = (RoundedRectStyle){
        bar_w, bar_h, bar_h * 0.5f};
    stamina_shadow_quads[side] = emit_round_rect_quad(
        x + 0.0012f * (float)screen_width,
        y + 0.0018f * (float)screen_height, bar_w, bar_h,
        verts + quads * 24);
    quads += stamina_shadow_quads[side];

    stamina_track_first_quad[side] = quads;
    stamina_track_style[side] = (RoundedRectStyle){
        bar_w, bar_h, bar_h * 0.5f};
    stamina_track_quads[side] = emit_round_rect_quad(
        x, y, bar_w, bar_h, verts + quads * 24);
    quads += stamina_track_quads[side];

    if (fill_w > 0.1f) {
      stamina_fill_first_quad[side] = quads;
      stamina_fill_style[side] = (RoundedRectStyle){
          fill_w, inner_h, inner_h * 0.5f};
      stamina_fill_quads[side] = emit_round_rect_quad(
          fill_x, y + inset, fill_w, inner_h, verts + quads * 24);
      quads += stamina_fill_quads[side];

      const float highlight_h = fmaxf(0.75f, inner_h * 0.28f);
      stamina_highlight_first_quad[side] = quads;
      stamina_highlight_style[side] = (RoundedRectStyle){
          fill_w, highlight_h, highlight_h * 0.5f};
      stamina_highlight_quads[side] = emit_round_rect_quad(
          fill_x, y + inset, fill_w, highlight_h,
          verts + quads * 24);
      quads += stamina_highlight_quads[side];
    }

    // Healthy stamina uses the same restrained turquoise family as the
    // native eFootball UI. Only the final quarter warms toward amber/red.
    if (power >= 0.45f) {
      stamina_fill_rgb[side][0] = 0.03f;
      stamina_fill_rgb[side][1] = 0.92f;
      stamina_fill_rgb[side][2] = 0.70f;
    } else if (power >= 0.22f) {
      const float t = (power - 0.22f) / 0.23f;
      stamina_fill_rgb[side][0] = 1.00f - 0.97f * t;
      stamina_fill_rgb[side][1] = 0.72f + 0.20f * t;
      stamina_fill_rgb[side][2] = 0.12f + 0.58f * t;
    } else {
      const float t = power / 0.22f;
      stamina_fill_rgb[side][0] = 0.92f + 0.08f * t;
      stamina_fill_rgb[side][1] = 0.24f + 0.48f * t;
      stamina_fill_rgb[side][2] = 0.18f - 0.06f * t;
    }
  }

  if (custom_gameplan) {
    const float margin_x = 0.018f * (float)screen_width;
    const float center_gap = 0.014f * (float)screen_width;
    const float half_w =
        ((float)screen_width - margin_x * 2.0f - center_gap) * 0.5f;
    const float half_x[2] = {margin_x, margin_x + half_w + center_gap};
    const float header_y = 0.025f * (float)screen_height;
    const float header_h = 0.120f * (float)screen_height;
    const float content_y = 0.145f * (float)screen_height;
    const float content_h = 0.670f * (float)screen_height;
    const float action_y = 0.838f * (float)screen_height;
    const float action_h = 0.078f * (float)screen_height;
    const float action_gap = 0.006f * (float)screen_width;
    const float action_w = (half_w - action_gap * 3.0f) * 0.25f;
    const float pitch_x_offset = 0.009f * (float)screen_width;
    const float pitch_w = 0.278f * (float)screen_width;
    const float pitch_y = content_y + 0.010f * (float)screen_height;
    const float pitch_h = content_h - 0.020f * (float)screen_height;
    const float bench_gap = 0.007f * (float)screen_width;
    const float bench_x_offset = pitch_x_offset + pitch_w + bench_gap;
    const float bench_w = half_w - bench_x_offset -
                          0.009f * (float)screen_width;
    // Player entries float directly on the pitch. This bounding box reserves
    // a square portrait, a compact black role/rating plate and one name line.
    const float player_w = 0.052f * (float)screen_width;
    const float player_h = 0.094f * (float)screen_height;
    const float line_thickness = 0.0015f * (float)screen_width;
    static const char *const action_labels[
        PES_PREMATCH_GAMEPLAN_ACTION_COUNT] = {
        "SUBSTITUTE", "FORMATION", "AUTO LINE UP", "POSITIONS"};

    prematch_gameplan_backdrop_first_quad = quads;
    prematch_gameplan_backdrop_quads = emit_image_rect(
        0.0f, 0.0f, (float)screen_width, (float)screen_height,
        verts + quads * 24);
    quads += prematch_gameplan_backdrop_quads;

    prematch_gameplan_panel_first_quad = quads;
    prematch_gameplan_panel_style = (RoundedRectStyle){
        half_w, content_y + content_h - header_y,
        0.012f * (float)screen_height};
    for (uint32_t side = 0; side < 2; side++) {
      prematch_gameplan_panel_quads += emit_round_rect_quad(
          half_x[side], header_y, half_w,
          content_y + content_h - header_y, verts + quads * 24);
      quads++;
    }
    for (uint32_t side = 0; side < 2; side++) {
      prematch_gameplan_header_first_quad[side] = quads;
      prematch_gameplan_header_quads[side] = emit_rect(
          half_x[side], header_y, half_w, header_h,
          verts + quads * 24);
      quads += prematch_gameplan_header_quads[side];
    }

    for (uint32_t side = 0; side < 2; side++) {
      const uint32_t page =
          pes_controller_custom_prematch_gameplan_page(side);
      const uint32_t root_focus =
          pes_controller_custom_prematch_gameplan_root_focus(side);
      const int waiting =
          pes_controller_custom_prematch_gameplan_waiting(side);
      const float pitch_x = half_x[side] + pitch_x_offset;
      const float bench_x = half_x[side] + bench_x_offset;

      if (!waiting && (page == PES_PREMATCH_GAMEPLAN_PAGE_ROOT ||
                       page == PES_PREMATCH_GAMEPLAN_PAGE_SUBSTITUTE)) {
        prematch_gameplan_pitch_first_quad[side] = quads;
        prematch_gameplan_pitch_quads[side] = emit_rect(
            pitch_x, pitch_y, pitch_w, pitch_h, verts + quads * 24);
        quads += prematch_gameplan_pitch_quads[side];

        prematch_gameplan_stripe_first_quad[side] = quads;
        for (uint32_t stripe = 0; stripe < 6; stripe += 2) {
          prematch_gameplan_stripe_quads[side] += emit_rect(
              pitch_x, pitch_y + pitch_h * (float)stripe / 6.0f,
              pitch_w, pitch_h / 6.0f, verts + quads * 24);
          quads++;
        }

        prematch_gameplan_line_first_quad[side] = quads;
        prematch_gameplan_line_quads[side] += emit_rect(
            pitch_x, pitch_y, pitch_w, line_thickness,
            verts + quads * 24);
        quads++;
        prematch_gameplan_line_quads[side] += emit_rect(
            pitch_x, pitch_y + pitch_h - line_thickness, pitch_w,
            line_thickness, verts + quads * 24);
        quads++;
        prematch_gameplan_line_quads[side] += emit_rect(
            pitch_x, pitch_y, line_thickness, pitch_h,
            verts + quads * 24);
        quads++;
        prematch_gameplan_line_quads[side] += emit_rect(
            pitch_x + pitch_w - line_thickness, pitch_y, line_thickness,
            pitch_h, verts + quads * 24);
        quads++;
        prematch_gameplan_line_quads[side] += emit_rect(
            pitch_x, pitch_y + pitch_h * 0.5f, pitch_w,
            line_thickness, verts + quads * 24);
        quads++;
        const float box_w = pitch_w * 0.48f;
        const float box_h = pitch_h * 0.14f;
        const float box_x = pitch_x + (pitch_w - box_w) * 0.5f;
        for (uint32_t end = 0; end < 2; end++) {
          const float box_y = end ? pitch_y + pitch_h - box_h : pitch_y;
          prematch_gameplan_line_quads[side] += emit_rect(
              box_x, box_y, line_thickness, box_h,
              verts + quads * 24);
          quads++;
          prematch_gameplan_line_quads[side] += emit_rect(
              box_x + box_w - line_thickness, box_y, line_thickness,
              box_h, verts + quads * 24);
          quads++;
          prematch_gameplan_line_quads[side] += emit_rect(
              box_x, end ? box_y : box_y + box_h - line_thickness,
              box_w, line_thickness, verts + quads * 24);
          quads++;
        }
      }

      if (waiting) {
        const float waiting_x = half_x[side] + 0.042f * (float)screen_width;
        const float waiting_y = content_y + 0.150f * (float)screen_height;
        const float waiting_w = half_w - 0.084f * (float)screen_width;
        const float waiting_h = 0.315f * (float)screen_height;
        prematch_gameplan_waiting_first_quad[side] = quads;
        prematch_gameplan_waiting_style = (RoundedRectStyle){
            waiting_w, waiting_h, 0.016f * (float)screen_height};
        prematch_gameplan_waiting_quads[side] = emit_round_rect_quad(
            waiting_x, waiting_y, waiting_w, waiting_h,
            verts + quads * 24);
        quads++;
      } else if (page == PES_PREMATCH_GAMEPLAN_PAGE_AUTO_LINEUP) {
        const float modal_x = half_x[side] + 0.035f * (float)screen_width;
        const float modal_y = content_y + 0.065f * (float)screen_height;
        const float modal_w = half_w - 0.070f * (float)screen_width;
        const float modal_h = 0.505f * (float)screen_height;
        prematch_gameplan_modal_first_quad[side] = quads;
        prematch_gameplan_modal_style[side] = (RoundedRectStyle){modal_w, modal_h, 0.022f * (float)screen_height};
        prematch_gameplan_modal_quads[side] += emit_round_rect_quad(
            modal_x, modal_y, modal_w, modal_h, verts + quads * 24);
        quads++;
      } else if ((page == PES_PREMATCH_GAMEPLAN_PAGE_POSITIONS &&
                  pes_controller_custom_prematch_gameplan_position_picker_active(side)) ||
                 (page == PES_PREMATCH_GAMEPLAN_PAGE_FORMATION &&
                  pes_controller_custom_prematch_gameplan_formation_picker_active(side))) {
        const float modal_x = half_x[side] + 0.025f * (float)screen_width;
        const float modal_y = content_y + 0.025f * (float)screen_height;
        const float modal_w = half_w - 0.050f * (float)screen_width;
        const float modal_h = page == PES_PREMATCH_GAMEPLAN_PAGE_FORMATION
            ? 0.470f * (float)screen_height : content_h - 0.050f * (float)screen_height;
        prematch_gameplan_modal_first_quad[side] = quads;
        prematch_gameplan_modal_style[side] = (RoundedRectStyle){modal_w, modal_h, 0.022f * (float)screen_height};
        prematch_gameplan_modal_quads[side] += emit_round_rect_quad(
            modal_x, modal_y, modal_w, modal_h, verts + quads * 24);
        quads++;
      }

      prematch_gameplan_neutral_first_quad[side] = quads;
      if (!waiting &&
          (page == PES_PREMATCH_GAMEPLAN_PAGE_ROOT ||
           page == PES_PREMATCH_GAMEPLAN_PAGE_SUBSTITUTE)) {
        uint32_t field_count =
            pes_controller_custom_prematch_gameplan_field_count(side);
        if (field_count > PREMATCH_GAMEPLAN_FIELD_SLOTS)
          field_count = PREMATCH_GAMEPLAN_FIELD_SLOTS;
        for (uint32_t index = 0; index < field_count; index++) {
          const float nx = (float)pes_controller_custom_prematch_gameplan_player_pitch_x(
                               side, index) /
                           255.0f;
          const float ny = (float)pes_controller_custom_prematch_gameplan_player_pitch_y(
                               side, index) /
                           255.0f;
          float x = pitch_x + nx * (pitch_w - player_w);
          float y = pitch_y + ny * (pitch_h - player_h);
          if (x < pitch_x)
            x = pitch_x;
          if (x + player_w > pitch_x + pitch_w)
            x = pitch_x + pitch_w - player_w;
          if (y < pitch_y)
            y = pitch_y;
          if (y + player_h > pitch_y + pitch_h)
            y = pitch_y + pitch_h - player_h;
          prematch_gameplan_field_rect[side][index][0] = x;
          prematch_gameplan_field_rect[side][index][1] = y;
          prematch_gameplan_field_rect[side][index][2] = player_w;
          prematch_gameplan_field_rect[side][index][3] = player_h;
          // Field players float directly on the pitch. Only the compact
          // black role/OVR plate below the portrait gets a solid surface.
        }

        const uint32_t bench_count =
            pes_controller_custom_prematch_gameplan_bench_count(side);
        uint32_t visible = bench_count;
        if (visible > PREMATCH_GAMEPLAN_VISIBLE_BENCH)
          visible = PREMATCH_GAMEPLAN_VISIBLE_BENCH;
        uint32_t start = 0;
        const uint32_t bench_focus =
            pes_controller_custom_prematch_gameplan_substitute_focus(
                side, PES_PREMATCH_GAMEPLAN_AREA_BENCH);
        if (bench_count > visible && visible) {
          start = bench_focus > visible / 2 ? bench_focus - visible / 2 : 0;
          if (start + visible > bench_count)
            start = bench_count - visible;
        }
        prematch_gameplan_bench_start[side] = start;
        prematch_gameplan_bench_visible[side] = visible;
        const float bench_content_y = pitch_y;
        const float bench_content_h = pitch_h;
        const float bench_step =
            visible ? bench_content_h / (float)visible : bench_content_h;
        const float bench_row_h = bench_step -
                                  0.006f * (float)screen_height;
        for (uint32_t slot = 0; slot < visible; slot++) {
          const float y = bench_content_y + bench_step * (float)slot;
          prematch_gameplan_bench_rect[side][slot][0] = bench_x;
          prematch_gameplan_bench_rect[side][slot][1] = y;
          prematch_gameplan_bench_rect[side][slot][2] = bench_w;
          prematch_gameplan_bench_rect[side][slot][3] = bench_row_h;
          prematch_gameplan_neutral_quads[side] += emit_rect(
              bench_x, y, bench_w, bench_row_h, verts + quads * 24);
          quads++;
        }
      } else if (page == PES_PREMATCH_GAMEPLAN_PAGE_FORMATION) {
        const float row_x = half_x[side] + 0.025f * (float)screen_width;
        const float row_w = half_w - 0.050f * (float)screen_width;
        const float row_y = content_y + 0.155f * (float)screen_height;
        const float row_h = (pes_controller_custom_prematch_gameplan_formation_picker_active(side)
            ? 0.060f : 0.105f) * (float)screen_height;
        for (uint32_t row = 0; row < pes_controller_custom_prematch_gameplan_formation_row_count(side); row++) {
          prematch_gameplan_neutral_quads[side] += emit_rect(
              row_x, row_y + (float)row * row_h, row_w,
              row_h - 0.008f * (float)screen_height,
              verts + quads * 24);
          quads++;
        }
      } else if (page == PES_PREMATCH_GAMEPLAN_PAGE_AUTO_LINEUP) {
        const float modal_x = half_x[side] + 0.035f * (float)screen_width;
        const float modal_y = content_y + 0.065f * (float)screen_height;
        const float modal_w = half_w - 0.070f * (float)screen_width;
        const float button_gap = 0.012f * (float)screen_width;
        const float button_w = (modal_w - button_gap -
                                0.040f * (float)screen_width) * 0.5f;
        const float button_y = modal_y + 0.390f * (float)screen_height;
        for (uint32_t button = 0; button < 2; button++) {
          prematch_gameplan_neutral_quads[side] += emit_rect(
              modal_x + 0.020f * (float)screen_width +
                  (button_w + button_gap) * (float)button,
              button_y, button_w, 0.075f * (float)screen_height,
              verts + quads * 24);
          quads++;
        }
      } else if (page == PES_PREMATCH_GAMEPLAN_PAGE_POSITIONS) {
        const int picker =
            pes_controller_custom_prematch_gameplan_position_picker_active(
                side);
        if (!picker) {
          const float row_x = half_x[side] + 0.010f * (float)screen_width;
          const float row_w = half_w - 0.020f * (float)screen_width;
          const float row_y = content_y + 0.055f * (float)screen_height;
          const float row_step = 0.062f * (float)screen_height;
          for (uint32_t row = 0;
               row < PES_PREMATCH_GAMEPLAN_POSITION_COUNT; row++) {
            prematch_gameplan_neutral_quads[side] += emit_rect(
                row_x, row_y + row_step * (float)row, row_w,
                row_step - 0.005f * (float)screen_height,
                verts + quads * 24);
            quads++;
          }
        } else {
          const uint32_t picker_count =
              pes_controller_custom_prematch_gameplan_position_picker_count(
                  side);
          uint32_t visible = picker_count;
          if (visible > PREMATCH_GAMEPLAN_VISIBLE_PICKER)
            visible = PREMATCH_GAMEPLAN_VISIBLE_PICKER;
          const uint32_t picker_focus =
              pes_controller_custom_prematch_gameplan_position_picker_focus(
                  side);
          uint32_t start = 0;
          if (picker_count > visible && visible) {
            start = picker_focus > visible / 2
                        ? picker_focus - visible / 2
                        : 0;
            if (start + visible > picker_count)
              start = picker_count - visible;
          }
          prematch_gameplan_picker_start[side] = start;
          prematch_gameplan_picker_visible[side] = visible;
          const float row_x = half_x[side] + 0.060f * (float)screen_width;
          const float row_w = half_w - 0.100f * (float)screen_width;
          const float row_y = content_y + 0.125f * (float)screen_height;
          const float row_step = 0.067f * (float)screen_height;
          for (uint32_t slot = 0; slot < visible; slot++) {
            const float y = row_y + row_step * (float)slot;
            prematch_gameplan_picker_rect[side][slot][0] = row_x;
            prematch_gameplan_picker_rect[side][slot][1] = y;
            prematch_gameplan_picker_rect[side][slot][2] = row_w;
            prematch_gameplan_picker_rect[side][slot][3] =
                row_step - 0.006f * (float)screen_height;
            prematch_gameplan_neutral_quads[side] += emit_rect(
                row_x, y, row_w,
                row_step - 0.006f * (float)screen_height,
                verts + quads * 24);
            quads++;
          }
        }
      }

      if (!waiting && (!custom_gameplan_exhibition || side == 0)) {
        prematch_gameplan_action_first_quad[side] = quads;
        prematch_gameplan_action_style = (RoundedRectStyle){
            action_w, action_h, 0.012f * (float)screen_height};
        for (uint32_t action = 0;
             action < PES_PREMATCH_GAMEPLAN_ACTION_COUNT; action++) {
          prematch_gameplan_action_quads[side] += emit_round_rect_quad(
              half_x[side] + (action_w + action_gap) * (float)action,
              action_y, action_w, action_h, verts + quads * 24);
          quads++;
        }

        prematch_gameplan_action_selected_first_quad[side] = quads;
        prematch_gameplan_action_selected_quads[side] +=
            emit_round_rect_quad(
                half_x[side] + (action_w + action_gap) * (float)root_focus,
                action_y, action_w, action_h, verts + quads * 24);
        quads++;
      }
      prematch_gameplan_accent_first_quad[side] = quads;
      if (!waiting && page == PES_PREMATCH_GAMEPLAN_PAGE_FORMATION) {
        const uint32_t focus =
            pes_controller_custom_prematch_gameplan_formation_focus(side) -
            pes_controller_custom_prematch_gameplan_formation_scroll(side);
        const float row_x = half_x[side] + 0.025f * (float)screen_width;
        const float row_w = half_w - 0.050f * (float)screen_width;
        const float row_y = content_y + 0.155f * (float)screen_height;
        const float row_h = (pes_controller_custom_prematch_gameplan_formation_picker_active(side)
            ? 0.060f : 0.105f) * (float)screen_height;
        prematch_gameplan_accent_quads[side] += emit_rect(
            row_x, row_y + (float)focus * row_h, row_w,
            row_h - 0.008f * (float)screen_height,
            verts + quads * 24);
        quads++;
      } else if (page == PES_PREMATCH_GAMEPLAN_PAGE_AUTO_LINEUP) {
        const uint32_t focus =
            pes_controller_custom_prematch_gameplan_auto_focus(side) & 1u;
        const float modal_x = half_x[side] + 0.035f * (float)screen_width;
        const float modal_y = content_y + 0.065f * (float)screen_height;
        const float modal_w = half_w - 0.070f * (float)screen_width;
        const float button_gap = 0.012f * (float)screen_width;
        const float button_w = (modal_w - button_gap -
                                0.040f * (float)screen_width) * 0.5f;
        prematch_gameplan_accent_quads[side] += emit_rect(
            modal_x + 0.020f * (float)screen_width +
                (button_w + button_gap) * (float)focus,
            modal_y + 0.390f * (float)screen_height, button_w,
            0.075f * (float)screen_height, verts + quads * 24);
        quads++;
      } else if (page == PES_PREMATCH_GAMEPLAN_PAGE_POSITIONS) {
        if (pes_controller_custom_prematch_gameplan_position_picker_active(
                side)) {
          const uint32_t focus =
              pes_controller_custom_prematch_gameplan_position_picker_focus(
                  side);
          if (focus >= prematch_gameplan_picker_start[side] &&
              focus < prematch_gameplan_picker_start[side] +
                          prematch_gameplan_picker_visible[side]) {
            const float *rect = prematch_gameplan_picker_rect[side]
                [focus - prematch_gameplan_picker_start[side]];
            prematch_gameplan_accent_quads[side] += emit_rect(
                rect[0], rect[1], rect[2], rect[3], verts + quads * 24);
            quads++;
          }
        } else {
          const uint32_t focus =
              pes_controller_custom_prematch_gameplan_position_focus(side);
          const float row_x = half_x[side] + 0.010f * (float)screen_width;
          const float row_w = half_w - 0.020f * (float)screen_width;
          const float row_y = content_y + 0.055f * (float)screen_height;
          const float row_step = 0.062f * (float)screen_height;
          prematch_gameplan_accent_quads[side] += emit_rect(
              row_x, row_y + row_step * (float)focus, row_w,
              row_step - 0.005f * (float)screen_height,
              verts + quads * 24);
          quads++;
        }
      }

      prematch_gameplan_focus_outline_first_quad[side] = quads;
      if (!waiting && page == PES_PREMATCH_GAMEPLAN_PAGE_SUBSTITUTE) {
        const uint32_t area =
            pes_controller_custom_prematch_gameplan_substitute_area(side);
        const uint32_t focus =
            pes_controller_custom_prematch_gameplan_substitute_focus(
                side, area);
        const float *rect = NULL;
        if (area == PES_PREMATCH_GAMEPLAN_AREA_FIELD &&
            focus < PREMATCH_GAMEPLAN_FIELD_SLOTS) {
          rect = prematch_gameplan_field_rect[side][focus];
        } else if (area == PES_PREMATCH_GAMEPLAN_AREA_BENCH &&
                   focus >= prematch_gameplan_bench_start[side] &&
                   focus < prematch_gameplan_bench_start[side] +
                               prematch_gameplan_bench_visible[side]) {
          rect = prematch_gameplan_bench_rect[side]
              [focus - prematch_gameplan_bench_start[side]];
        }
        if (rect && rect[2] > 0.0f) {
          const float cursor_w = 0.034f * (float)screen_height;
          const float cursor_h = 0.046f * (float)screen_height;
          float cursor_x;
          float cursor_y;
          if (area == PES_PREMATCH_GAMEPLAN_AREA_FIELD) {
            const float portrait_size =
                fminf(rect[2] * 0.72f, 0.053f * (float)screen_height);
            const float plate_h = 0.022f * (float)screen_height;
            const float plate_w = rect[2] * 0.92f;
            const float plate_x = rect[0] + (rect[2] - plate_w) * 0.5f;
            const float plate_y = rect[1] + portrait_size -
                                  0.002f * (float)screen_height;
            cursor_x = plate_x + plate_w - cursor_w * 0.12f;
            cursor_y = plate_y + plate_h - cursor_h * 0.24f;
          } else {
            cursor_x = rect[0] + rect[2] - cursor_w * 0.58f;
            cursor_y = rect[1] + rect[3] - cursor_h * 0.68f;
          }
          prematch_gameplan_focus_outline_quads[side] =
              emit_round_rect_quad(cursor_x, cursor_y, cursor_w, cursor_h,
                                   verts + quads * 24);
          quads += prematch_gameplan_focus_outline_quads[side];

          if (area == PES_PREMATCH_GAMEPLAN_AREA_FIELD) {
            const uint32_t drag =
                pes_controller_custom_prematch_gameplan_drag_state(side);
            const char *context_label =
                drag == 1 ? "DROP PLAYER" : "HOLD TO MOVE";
            const float context_icon_size =
                0.031f * (float)screen_height;
            const float context_pad_x = 0.008f * (float)screen_width;
            const float context_gap = 0.005f * (float)screen_width;
            const float context_label_w = measure_efootball_line(
                context_label, (int)strlen(context_label), helper_text_gh,
                EFOOTBALL_FONT_BOLD);
            const float context_w = context_pad_x * 2.0f +
                                    context_icon_size + context_gap +
                                    context_label_w;
            const float context_h = 0.046f * (float)screen_height;
            float context_x = rect[0] + rect[2] * 0.5f - context_w * 0.5f;
            float context_y = rect[1] + rect[3] +
                              0.006f * (float)screen_height;
            const float min_x = half_x[side] + 0.006f * (float)screen_width;
            const float max_x = half_x[side] + half_w - context_w -
                                0.006f * (float)screen_width;
            if (context_x < min_x) context_x = min_x;
            if (context_x > max_x) context_x = max_x;
            if (context_y + context_h > action_y -
                                        0.006f * (float)screen_height)
              context_y = rect[1] - context_h -
                          0.006f * (float)screen_height;
            prematch_gameplan_context_rect[side][0] = context_x;
            prematch_gameplan_context_rect[side][1] = context_y;
            prematch_gameplan_context_rect[side][2] = context_w;
            prematch_gameplan_context_rect[side][3] = context_h;
            prematch_gameplan_context_plate_first_quad[side] = quads;
            prematch_gameplan_context_plate_style = (RoundedRectStyle){
                context_w, context_h, context_h * 0.22f};
            const int context_quads = emit_round_rect_quad(
                context_x, context_y, context_w, context_h,
                verts + quads * 24);
            prematch_gameplan_context_plate_quads[side] = context_quads;
            quads += context_quads;
          }
        }
      }

      prematch_gameplan_selected_outline_first_quad[side] = quads;
      if (!waiting && page == PES_PREMATCH_GAMEPLAN_PAGE_SUBSTITUTE) {
        for (uint32_t area = 0; area < 2; area++) {
          const uint32_t count = area == PES_PREMATCH_GAMEPLAN_AREA_FIELD
                                     ? pes_controller_custom_prematch_gameplan_field_count(
                                           side)
                                     : pes_controller_custom_prematch_gameplan_bench_count(
                                           side);
          for (uint32_t index = 0; index < count; index++) {
            if (!pes_controller_custom_prematch_gameplan_substitute_selected(
                    side, area, index))
              continue;
            const float *rect = NULL;
            if (area == PES_PREMATCH_GAMEPLAN_AREA_FIELD &&
                index < PREMATCH_GAMEPLAN_FIELD_SLOTS) {
              rect = prematch_gameplan_field_rect[side][index];
            } else if (area == PES_PREMATCH_GAMEPLAN_AREA_BENCH &&
                       index >= prematch_gameplan_bench_start[side] &&
                       index < prematch_gameplan_bench_start[side] +
                                   prematch_gameplan_bench_visible[side]) {
              rect = prematch_gameplan_bench_rect[side]
                  [index - prematch_gameplan_bench_start[side]];
            }
            if (rect && rect[2] > 0.0f) {
              const float pad = 0.0060f * (float)screen_height;
              const int outline_quads = emit_corner_outline(
                  rect[0] - pad, rect[1] - pad, rect[2] + pad * 2.0f,
                  rect[3] + pad * 2.0f,
                  0.018f * (float)screen_height,
                  0.0024f * (float)screen_height, verts + quads * 24);
              prematch_gameplan_selected_outline_quads[side] +=
                  outline_quads;
              quads += outline_quads;
            }
          }
        }
      }
    }

    // Keep all portrait geometry outside the solid-color batches. Each quad
    // is drawn separately with the matching native player texture.
    for (uint32_t side = 0; side < 2; side++) {
      const uint32_t page =
          pes_controller_custom_prematch_gameplan_page(side);
      const int waiting =
          pes_controller_custom_prematch_gameplan_waiting(side);
      if (!waiting &&
          (page == PES_PREMATCH_GAMEPLAN_PAGE_ROOT ||
           page == PES_PREMATCH_GAMEPLAN_PAGE_SUBSTITUTE)) {
        uint32_t field_count =
            pes_controller_custom_prematch_gameplan_field_count(side);
        if (field_count > PREMATCH_GAMEPLAN_FIELD_SLOTS)
          field_count = PREMATCH_GAMEPLAN_FIELD_SLOTS;
        for (uint32_t index = 0; index < field_count; index++) {
          const uint32_t portrait_id =
              pes_controller_custom_prematch_gameplan_player_portrait_id(
                  side, 1, index);
          if (!gameplan_portrait_texture(portrait_id))
            continue;
          const float *rect = prematch_gameplan_field_rect[side][index];
          const float portrait_size =
              fminf(rect[2] * 0.72f, 0.053f * (float)screen_height);
          const float portrait_x =
              rect[0] + (rect[2] - portrait_size) * 0.5f;
          prematch_gameplan_portrait_quad[side][0][index] = quads;
          emit_image_rect(portrait_x, rect[1], portrait_size, portrait_size,
                          verts + quads * 24);
          quads++;
        }
      }
    }

    // The field has no card background. A compact black plate anchors the
    // role and OVR directly below each portrait.
    for (uint32_t side = 0; side < 2; side++) {
      const uint32_t page =
          pes_controller_custom_prematch_gameplan_page(side);
      if (pes_controller_custom_prematch_gameplan_waiting(side) ||
          (page != PES_PREMATCH_GAMEPLAN_PAGE_ROOT &&
           page != PES_PREMATCH_GAMEPLAN_PAGE_SUBSTITUTE))
        continue;
      uint32_t field_count =
          pes_controller_custom_prematch_gameplan_field_count(side);
      if (field_count > PREMATCH_GAMEPLAN_FIELD_SLOTS)
        field_count = PREMATCH_GAMEPLAN_FIELD_SLOTS;
      prematch_gameplan_field_plate_first_quad[side] = quads;
      prematch_gameplan_field_plate_style = (RoundedRectStyle){
          player_w * 0.92f, 0.022f * (float)screen_height,
          0.004f * (float)screen_height};
      for (uint32_t index = 0; index < field_count; index++) {
        const float *rect = prematch_gameplan_field_rect[side][index];
        const float portrait_size =
            fminf(rect[2] * 0.72f, 0.053f * (float)screen_height);
        const float plate_h = 0.022f * (float)screen_height;
        const float plate_w = rect[2] * 0.92f;
        const int plate_quads = emit_round_rect_quad(
            rect[0] + (rect[2] - plate_w) * 0.5f,
            rect[1] + portrait_size - 0.002f * (float)screen_height,
            plate_w, plate_h, verts + quads * 24);
        prematch_gameplan_field_plate_quads[side] += plate_quads;
        quads += plate_quads;
      }
    }

    // Bench and assignment rows use the same native position color language
    // as the in-match set-piece picker. Group the geometry by role so a
    // single draw call can color every GK/DF/MF/FW plate consistently.
    for (uint32_t role_band = 0; role_band < 4; role_band++) {
      prematch_gameplan_role_plate_first_quad[role_band] = quads;
      for (uint32_t side = 0; side < 2; side++) {
        const uint32_t page =
            pes_controller_custom_prematch_gameplan_page(side);
        if (pes_controller_custom_prematch_gameplan_waiting(side))
          continue;
        if (page == PES_PREMATCH_GAMEPLAN_PAGE_ROOT ||
            page == PES_PREMATCH_GAMEPLAN_PAGE_SUBSTITUTE) {
          for (uint32_t slot = 0;
               slot < prematch_gameplan_bench_visible[side]; slot++) {
            const uint32_t index =
                prematch_gameplan_bench_start[side] + slot;
            const char *role =
                pes_controller_custom_prematch_gameplan_player_role(
                    side, 0, index);
            if (selector_position_color_band(role) != role_band)
              continue;
            const float *rect = prematch_gameplan_bench_rect[side][slot];
            const float plate_w = 0.036f * (float)screen_width;
            const float plate_h =
                fminf(rect[3] - 0.012f * (float)screen_height,
                      0.036f * (float)screen_height);
            const int plate_quads = emit_rounded_rect(
                rect[0] + 0.006f * (float)screen_width,
                rect[1] + (rect[3] - plate_h) * 0.5f,
                plate_w, plate_h, plate_h * 0.22f,
                verts + quads * 24);
            prematch_gameplan_role_plate_quads[role_band] += plate_quads;
            quads += plate_quads;
          }
        } else if (
            page == PES_PREMATCH_GAMEPLAN_PAGE_POSITIONS &&
            pes_controller_custom_prematch_gameplan_position_picker_active(
                side)) {
          for (uint32_t slot = 0;
               slot < prematch_gameplan_picker_visible[side]; slot++) {
            const uint32_t index =
                prematch_gameplan_picker_start[side] + slot;
            const char *role =
                pes_controller_custom_prematch_gameplan_position_picker_role(
                    side, index);
            if (!role || !role[0] || strcmp(role, "-") == 0 ||
                selector_position_color_band(role) != role_band)
              continue;
            const float *rect = prematch_gameplan_picker_rect[side][slot];
            const float plate_w = 0.047f * (float)screen_width;
            const float plate_h =
                fminf(rect[3] - 0.012f * (float)screen_height,
                      0.039f * (float)screen_height);
            const int plate_quads = emit_rounded_rect(
                rect[0] + 0.012f * (float)screen_width,
                rect[1] + (rect[3] - plate_h) * 0.5f,
                plate_w, plate_h, plate_h * 0.22f,
                verts + quads * 24);
            prematch_gameplan_role_plate_quads[role_band] += plate_quads;
            quads += plate_quads;
          }
        }
      }
    }

    // No stable native foot-icon texture is exposed by this screen. Mirror
    // the set-piece picker with a compact circular R/L badge instead.
    for (uint32_t side = 0; side < 2; side++) {
      prematch_gameplan_picker_foot_first_quad[side] = quads;
      if (pes_controller_custom_prematch_gameplan_waiting(side) ||
          pes_controller_custom_prematch_gameplan_page(side) !=
              PES_PREMATCH_GAMEPLAN_PAGE_POSITIONS ||
          !pes_controller_custom_prematch_gameplan_position_picker_active(
              side))
        continue;
      for (uint32_t slot = 0;
           slot < prematch_gameplan_picker_visible[side]; slot++) {
        const uint32_t index =
            prematch_gameplan_picker_start[side] + slot;
        const char *name =
            pes_controller_custom_prematch_gameplan_position_picker_name(
                side, index);
        if (!name || strcmp(name, "NONE") == 0)
          continue;
        const float *rect = prematch_gameplan_picker_rect[side][slot];
        const float center_x =
            rect[0] + rect[2] - 0.070f * (float)screen_width;
        prematch_gameplan_picker_foot_quads[side] += emit_circle_quad(
            center_x, rect[1] + rect[3] * 0.5f,
            0.016f * (float)screen_height, verts + quads * 24);
        quads++;
      }
    }

    for (uint32_t side = 0; side < 2; side++) {
      const float badge_size = header_h -
                               0.020f * (float)screen_height;
      prematch_gameplan_badge_first_quad[side] = quads;
      prematch_gameplan_badge_quads[side] = emit_badge(
          pes_controller_2p_prematch_hub_badge(side),
          half_x[side] + 0.008f * (float)screen_width,
          header_y + 0.010f * (float)screen_height, badge_size, badge_size,
          verts + quads * 24);
      quads += prematch_gameplan_badge_quads[side];
    }

    const float header_name_gh = (float)screen_height / 29.0f;
    const float header_meta_gh = (float)screen_height / 36.0f;
    const float card_main_gh = (float)screen_height / 52.0f;
    const float card_name_gh = roundf((float)screen_height / 36.0f);
    const float body_gh = (float)screen_height / 34.0f;
    const float small_gh = (float)screen_height / 38.0f;
    const float title_gh = (float)screen_height / 28.0f;
    const float action_gh = (float)screen_height / 42.0f;
    int line_quads = 0;

    prematch_gameplan_white_text_first_quad = quads;
    for (uint32_t side = 0; side < 2; side++) {
      const uint32_t page =
          pes_controller_custom_prematch_gameplan_page(side);
      const uint32_t root_focus =
          pes_controller_custom_prematch_gameplan_root_focus(side);
      const float pitch_x = half_x[side] + pitch_x_offset;
      const float badge_size = header_h -
                               0.020f * (float)screen_height;
      prematch_gameplan_header_text_first_quad[side] = quads;
      char team_name[28];
      compact_player_name(
          team_name, sizeof(team_name),
          pes_controller_2p_prematch_hub_team_name(side));
      line_quads = emit_efootball_line(
          team_name, (int)strlen(team_name),
          half_x[side] + 0.013f * (float)screen_width + badge_size,
          header_y + 0.017f * (float)screen_height, header_name_gh,
          EFOOTBALL_FONT_STENCIL, verts + quads * 24);
      prematch_gameplan_white_text_quads += line_quads;
      quads += line_quads;
      char stats[48];
      snprintf(stats, sizeof(stats), "SPIRIT %u  POWER %u",
               pes_controller_custom_prematch_gameplan_team_spirit(side),
               pes_controller_custom_prematch_gameplan_team_power(side));
      const float stats_w = measure_efootball_line(
          stats, (int)strlen(stats), header_meta_gh, EFOOTBALL_FONT_BOLD);
      line_quads = emit_efootball_line(
          stats, (int)strlen(stats),
          half_x[side] + half_w - stats_w -
              0.012f * (float)screen_width,
          header_y + header_h - header_meta_gh -
              0.012f * (float)screen_height,
          header_meta_gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
      prematch_gameplan_white_text_quads += line_quads;
      quads += line_quads;

      prematch_gameplan_header_text_quads[side] =
          quads - prematch_gameplan_header_text_first_quad[side];
      const int waiting =
          pes_controller_custom_prematch_gameplan_waiting(side);
      const uint32_t field_focus =
          pes_controller_custom_prematch_gameplan_substitute_focus(
              side, PES_PREMATCH_GAMEPLAN_AREA_FIELD);
      const uint32_t bench_focus =
          pes_controller_custom_prematch_gameplan_substitute_focus(
              side, PES_PREMATCH_GAMEPLAN_AREA_BENCH);
      const uint32_t substitute_area =
          pes_controller_custom_prematch_gameplan_substitute_area(side);
      const int focus_on_field = !waiting &&
          page == PES_PREMATCH_GAMEPLAN_PAGE_SUBSTITUTE &&
          substitute_area == PES_PREMATCH_GAMEPLAN_AREA_FIELD;
      const int focus_on_bench = !waiting &&
          page == PES_PREMATCH_GAMEPLAN_PAGE_SUBSTITUTE &&
          substitute_area == PES_PREMATCH_GAMEPLAN_AREA_BENCH;
      const char *focused_name = focus_on_bench
          ? pes_controller_custom_prematch_gameplan_player_name(
                side, 0, bench_focus)
          : pes_controller_custom_prematch_gameplan_player_name(
                side, 1, field_focus);
      const double name_focus_seconds = gameplan_name_focus_seconds(
          side, focus_on_field || focus_on_bench, focused_name);
      if (waiting) {
        const float waiting_x = half_x[side] + 0.042f * (float)screen_width;
        const float waiting_y = content_y + 0.150f * (float)screen_height;
        const float waiting_w = half_w - 0.084f * (float)screen_width;
        const float waiting_h = 0.315f * (float)screen_height;
        const char *message = "WAITING FOR OPPONENT";
        const float message_w = measure_efootball_line(
            message, (int)strlen(message), title_gh,
            EFOOTBALL_FONT_STENCIL);
        prematch_gameplan_body_text_first_quad[side] = quads;
        prematch_gameplan_waiting_text_first_quad[side] = quads;
        line_quads = emit_efootball_line(
            message, (int)strlen(message),
            waiting_x + (waiting_w - message_w) * 0.5f,
            waiting_y + waiting_h * 0.38f, title_gh,
            EFOOTBALL_FONT_STENCIL, verts + quads * 24);
        prematch_gameplan_white_text_quads += line_quads;
        quads += line_quads;
        const char *cancel = "CANCEL";
        const float cancel_w = measure_efootball_line(
            cancel, (int)strlen(cancel), body_gh, EFOOTBALL_FONT_BOLD);
        line_quads = emit_efootball_line(
            cancel, (int)strlen(cancel),
            waiting_x + (waiting_w - cancel_w) * 0.5f,
            waiting_y + waiting_h * 0.62f, body_gh,
            EFOOTBALL_FONT_BOLD, verts + quads * 24);
        prematch_gameplan_white_text_quads += line_quads;
        quads += line_quads;
        prematch_gameplan_waiting_text_quads[side] =
            quads - prematch_gameplan_waiting_text_first_quad[side];
      } else if (page == PES_PREMATCH_GAMEPLAN_PAGE_ROOT ||
                 page == PES_PREMATCH_GAMEPLAN_PAGE_SUBSTITUTE) {
        uint32_t field_count =
            pes_controller_custom_prematch_gameplan_field_count(side);
        if (field_count > PREMATCH_GAMEPLAN_FIELD_SLOTS)
          field_count = PREMATCH_GAMEPLAN_FIELD_SLOTS;
        prematch_gameplan_field_text_first_quad[side] = quads;
        for (uint32_t index = 0; index < field_count; index++) {
          const float *rect = prematch_gameplan_field_rect[side][index];
          const char *role =
              pes_controller_custom_prematch_gameplan_player_role(
                  side, 1, index);
          const uint32_t overall =
              pes_controller_custom_prematch_gameplan_player_overall(
                  side, 1, index);
          const float portrait_size =
              fminf(rect[2] * 0.72f, 0.053f * (float)screen_height);
          const float plate_w = rect[2] * 0.92f;
          const float plate_h = 0.022f * (float)screen_height;
          const float plate_x = rect[0] + (rect[2] - plate_w) * 0.5f;
          const float plate_y =
              rect[1] + portrait_size - 0.002f * (float)screen_height;
          prematch_gameplan_field_role_first[side][index] = quads;
          prematch_gameplan_field_role_band[side][index] =
              selector_position_color_band(role);
          line_quads = emit_efootball_fit_line(
              role, (int)strlen(role),
              plate_x + 0.004f * (float)screen_width,
              plate_y + (plate_h - card_main_gh) * 0.5f,
              plate_w * 0.52f, card_main_gh,
              (float)screen_height / 66.0f, EFOOTBALL_FONT_STENCIL,
              verts + quads * 24);
          prematch_gameplan_field_role_quads[side][index] = line_quads;
          prematch_gameplan_white_text_quads += line_quads;
          quads += line_quads;
          char overall_text[4];
          snprintf(overall_text, sizeof(overall_text), "%u", overall);
          const float overall_w = measure_efootball_line(
              overall_text, (int)strlen(overall_text), card_main_gh,
              EFOOTBALL_FONT_STENCIL);
          prematch_gameplan_field_metric_first[side][index] = quads;
          line_quads = emit_efootball_line(
              overall_text, (int)strlen(overall_text),
              plate_x + plate_w - overall_w -
                  0.004f * (float)screen_width,
              plate_y + (plate_h - card_main_gh) * 0.5f, card_main_gh,
              EFOOTBALL_FONT_STENCIL, verts + quads * 24);
          prematch_gameplan_field_metric_quads[side][index] = line_quads;
          prematch_gameplan_white_text_quads += line_quads;
          quads += line_quads;
          const char *name =
              pes_controller_custom_prematch_gameplan_player_name(
                  side, 1, index);
          const int field_name_focused =
              focus_on_field && field_focus == index;
          line_quads = emit_efootball_name_line(
              name, (int)strlen(name),
              rect[0] + rect[2] * 0.5f,
              plate_y + plate_h + 0.001f * (float)screen_height,
              rect[2] * 1.22f, card_name_gh, field_name_focused,
              name_focus_seconds, 0, verts + quads * 24);
          prematch_gameplan_white_text_quads += line_quads;
          quads += line_quads;
        }
        const char *formation =
            pes_controller_custom_prematch_gameplan_formation_label(side);
        line_quads = emit_efootball_line(
            formation, (int)strlen(formation),
            pitch_x + 0.008f * (float)screen_width,
            pitch_y + pitch_h - body_gh -
                0.008f * (float)screen_height,
            body_gh, EFOOTBALL_FONT_STENCIL, verts + quads * 24);
        prematch_gameplan_white_text_quads += line_quads;
        quads += line_quads;
        prematch_gameplan_field_text_quads[side] =
            quads - prematch_gameplan_field_text_first_quad[side];
        prematch_gameplan_body_text_first_quad[side] = quads;
        for (uint32_t slot = 0;
             slot < prematch_gameplan_bench_visible[side]; slot++) {
          const uint32_t index = prematch_gameplan_bench_start[side] + slot;
          const float *rect = prematch_gameplan_bench_rect[side][slot];
          const uint32_t overall =
              pes_controller_custom_prematch_gameplan_player_overall(
                  side, 0, index);
          const char *name =
              pes_controller_custom_prematch_gameplan_player_name(
                  side, 0, index);
          const float name_x = rect[0] + 0.048f * (float)screen_width;
          const float name_w =
              rect[2] - 0.083f * (float)screen_width;
          line_quads = emit_efootball_name_line(
              name, (int)strlen(name), name_x,
              rect[1] + (rect[3] - small_gh) * 0.5f,
              name_w, small_gh, focus_on_bench && bench_focus == index,
              name_focus_seconds, 1, verts + quads * 24);
          prematch_gameplan_white_text_quads += line_quads;
          quads += line_quads;
          char overall_text[4];
          snprintf(overall_text, sizeof(overall_text), "%u", overall);
          const float overall_w = measure_efootball_line(
              overall_text, (int)strlen(overall_text), small_gh,
              EFOOTBALL_FONT_STENCIL);
          prematch_gameplan_bench_metric_first[side][slot] = quads;
          line_quads = emit_efootball_line(
              overall_text, (int)strlen(overall_text),
              rect[0] + rect[2] - overall_w -
                  0.009f * (float)screen_width,
              rect[1] + (rect[3] - small_gh) * 0.5f, small_gh,
              EFOOTBALL_FONT_STENCIL, verts + quads * 24);
          prematch_gameplan_bench_metric_quads[side][slot] = line_quads;
          prematch_gameplan_white_text_quads += line_quads;
          quads += line_quads;
        }
      } else {
        prematch_gameplan_body_text_first_quad[side] = quads;
        if (page == PES_PREMATCH_GAMEPLAN_PAGE_FORMATION) {
        const int shape_picker = pes_controller_custom_prematch_gameplan_formation_picker_active(side);
        const char *title = shape_picker ? "CHOOSE FORMATION" : "FORMATION SETTINGS";
        const float title_width = measure_efootball_line(title, (int)strlen(title), title_gh, EFOOTBALL_FONT_STENCIL);
        line_quads = emit_efootball_line(
            title, (int)strlen(title),
            half_x[side] + (shape_picker ? (half_w - title_width) * 0.5f : 0.025f * (float)screen_width),
            content_y + (shape_picker ? 0.055f : 0.025f) * (float)screen_height, title_gh,
            EFOOTBALL_FONT_STENCIL, verts + quads * 24);
        prematch_gameplan_white_text_quads += line_quads;
        quads += line_quads;
        char formation[64];
        snprintf(formation, sizeof(formation), "CURRENT SHAPE  %s",
                 pes_controller_custom_prematch_gameplan_formation_label(
                     side));
        if (shape_picker) {
          snprintf(formation, sizeof(formation), "CURRENT %s   |   %u / 11",
              pes_controller_custom_prematch_gameplan_formation_label(side),
              pes_controller_custom_prematch_gameplan_formation_focus(side) + 1u);
        }
        const float formation_width = measure_efootball_line(formation, (int)strlen(formation), body_gh, EFOOTBALL_FONT_BOLD);
        line_quads = emit_efootball_line(
            formation, (int)strlen(formation),
            half_x[side] + (shape_picker ? (half_w - formation_width) * 0.5f : 0.025f * (float)screen_width),
            content_y + (shape_picker ? 0.105f : 0.085f) * (float)screen_height, body_gh,
            EFOOTBALL_FONT_BOLD, verts + quads * 24);
        prematch_gameplan_white_text_quads += line_quads;
        quads += line_quads;
        static const char *const formation_rows[PES_PREMATCH_FORMATION_ROW_COUNT] = {
            "FORMATION STYLE", "SHAPE PRESET", "AUTO OFFSIDE TRAP",
            "AUTO SUBSTITUTE"};
        const float row_x = half_x[side] + 0.041f * (float)screen_width;
        const float row_w = half_w - 0.082f * (float)screen_width;
        const float row_y = content_y + 0.155f * (float)screen_height;
        const float row_h = (pes_controller_custom_prematch_gameplan_formation_picker_active(side)
            ? 0.060f : 0.105f) * (float)screen_height;
        for (uint32_t row = 0; row < pes_controller_custom_prematch_gameplan_formation_row_count(side); row++) {
          const uint32_t option = row + pes_controller_custom_prematch_gameplan_formation_scroll(side);
          const char *label = shape_picker
              ? pes_controller_custom_prematch_gameplan_formation_value(side, option)
              : formation_rows[row];
          const int active = shape_picker && pes_controller_custom_prematch_gameplan_formation_option_active(side, option);
          if (active) prematch_gameplan_picker_active_text_first[side][0] = quads;
          line_quads = emit_efootball_line(
              label, (int)strlen(label), row_x,
              row_y + row_h * (float)row +
                  (row_h - small_gh) * 0.5f,
              small_gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
          if (active) prematch_gameplan_picker_active_text_quads[side][0] = line_quads;
          prematch_gameplan_white_text_quads += line_quads;
          quads += line_quads;
          const char *value =
              shape_picker ? "" : pes_controller_custom_prematch_gameplan_formation_value(
                  side, row);
          const float value_max_w = row_w * 0.54f;
          const float value_w = fminf(
              value_max_w,
              measure_efootball_line(value, (int)strlen(value), body_gh,
                                     EFOOTBALL_FONT_STENCIL));
          line_quads = emit_efootball_fit_line(
              value, (int)strlen(value),
              row_x + row_w - value_w,
              row_y + row_h * (float)row +
                  (row_h - body_gh) * 0.5f,
              value_max_w, body_gh, (float)screen_height / 46.0f,
              EFOOTBALL_FONT_STENCIL, verts + quads * 24);
          prematch_gameplan_white_text_quads += line_quads;
          quads += line_quads;
        }
      } else if (page == PES_PREMATCH_GAMEPLAN_PAGE_AUTO_LINEUP) {
        const float modal_x = half_x[side] + 0.035f * (float)screen_width;
        const float modal_y = content_y + 0.065f * (float)screen_height;
        const float modal_w = half_w - 0.070f * (float)screen_width;
        const char *title = "AUTO LINE UP";
        const float title_w = measure_efootball_line(
            title, (int)strlen(title), title_gh, EFOOTBALL_FONT_STENCIL);
        line_quads = emit_efootball_line(
            title, (int)strlen(title),
            modal_x + (modal_w - title_w) * 0.5f,
            modal_y + 0.035f * (float)screen_height, title_gh,
            EFOOTBALL_FONT_STENCIL, verts + quads * 24);
        prematch_gameplan_white_text_quads += line_quads;
        quads += line_quads;
        const char *question = "APPLY NATIVE BEST LINEUP?";
        const float question_w = measure_efootball_line(
            question, (int)strlen(question), body_gh, EFOOTBALL_FONT_BOLD);
        line_quads = emit_efootball_line(
            question, (int)strlen(question),
            modal_x + (modal_w - question_w) * 0.5f,
            modal_y + 0.105f * (float)screen_height, body_gh,
            EFOOTBALL_FONT_BOLD, verts + quads * 24);
        prematch_gameplan_white_text_quads += line_quads;
        quads += line_quads;
        if (pes_controller_custom_prematch_gameplan_auto_preview_valid(side)) {
          const uint32_t before[2] = {
              pes_controller_custom_prematch_gameplan_auto_power(side, 0),
              pes_controller_custom_prematch_gameplan_auto_spirit(side, 0),
          };
          const uint32_t after[2] = {
              pes_controller_custom_prematch_gameplan_auto_power(side, 1),
              pes_controller_custom_prematch_gameplan_auto_spirit(side, 1),
          };
          static const char *const labels[2] = {
              "TEAM STRENGTH", "TEAM SPIRIT"};
          for (uint32_t metric = 0; metric < 2; metric++) {
            char prefix[64];
            snprintf(prefix, sizeof(prefix), "%s  %u  ->  ",
                     labels[metric], before[metric]);
            const float text_x = modal_x + 0.035f * (float)screen_width;
            const float text_y = modal_y +
                                 (0.205f + 0.060f * (float)metric) *
                                     (float)screen_height;
            line_quads = emit_efootball_line(
                prefix, (int)strlen(prefix), text_x, text_y, body_gh,
                EFOOTBALL_FONT_BOLD, verts + quads * 24);
            prematch_gameplan_white_text_quads += line_quads;
            quads += line_quads;

            char result[8];
            snprintf(result, sizeof(result), "%u", after[metric]);
            prematch_gameplan_auto_gain_first[side][metric] = quads;
            line_quads = emit_efootball_line(
                result, (int)strlen(result),
                text_x + measure_efootball_line(
                             prefix, (int)strlen(prefix), body_gh,
                             EFOOTBALL_FONT_BOLD),
                text_y, body_gh, EFOOTBALL_FONT_STENCIL,
                verts + quads * 24);
            prematch_gameplan_auto_gain_quads[side][metric] =
                before[metric] != after[metric] ? line_quads : 0;
            prematch_gameplan_white_text_quads += line_quads;
            quads += line_quads;
          }
        } else {
          const char *unavailable = "NATIVE AUTO LINEUP UNAVAILABLE";
          line_quads = emit_efootball_line(
              unavailable, (int)strlen(unavailable),
              modal_x + 0.035f * (float)screen_width,
              modal_y + 0.205f * (float)screen_height, body_gh,
              EFOOTBALL_FONT_BOLD, verts + quads * 24);
          prematch_gameplan_white_text_quads += line_quads;
          quads += line_quads;
          const char *return_hint = "RETURN";
          line_quads = emit_efootball_line(
              return_hint, (int)strlen(return_hint),
              modal_x + 0.035f * (float)screen_width,
              modal_y + 0.265f * (float)screen_height, body_gh,
              EFOOTBALL_FONT_BOLD, verts + quads * 24);
          prematch_gameplan_white_text_quads += line_quads;
          quads += line_quads;
        }
        static const char *const choices[2] = {"CANCEL", "APPLY"};
        const float button_gap = 0.012f * (float)screen_width;
        const float button_w = (modal_w - button_gap -
                                0.040f * (float)screen_width) * 0.5f;
        for (uint32_t button = 0; button < 2; button++) {
          const float width = measure_efootball_line(
              choices[button], (int)strlen(choices[button]), body_gh,
              EFOOTBALL_FONT_BOLD);
          line_quads = emit_efootball_line(
              choices[button], (int)strlen(choices[button]),
              modal_x + 0.020f * (float)screen_width +
                  (button_w + button_gap) * (float)button +
                  (button_w - width) * 0.5f,
              modal_y + 0.390f * (float)screen_height +
                  (0.075f * (float)screen_height - body_gh) * 0.5f,
              body_gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
          prematch_gameplan_white_text_quads += line_quads;
          quads += line_quads;
        }
      } else if (page == PES_PREMATCH_GAMEPLAN_PAGE_POSITIONS) {
        const int picker =
            pes_controller_custom_prematch_gameplan_position_picker_active(
                side);
        const char *title = picker ? "SELECT PLAYER" : "POSITION SETTINGS";
        const float title_base_offset = (picker ? 0.040f : 0.015f);
        const float title_y = content_y +
                              (title_base_offset +
                               (picker ? 0.022f : 0.0f)) *
                                  (float)screen_height;
        line_quads = emit_efootball_line(
            title, (int)strlen(title),
            half_x[side] + (picker ? 0.060f : 0.025f) * (float)screen_width,
            title_y, title_gh,
            EFOOTBALL_FONT_STENCIL, verts + quads * 24);
        prematch_gameplan_white_text_quads += line_quads;
        quads += line_quads;
        if (!picker) {
          const float row_y = content_y + 0.055f * (float)screen_height;
          const float row_step = 0.062f * (float)screen_height;
          for (uint32_t row = 0;
               row < PES_PREMATCH_GAMEPLAN_POSITION_COUNT; row++) {
            const char *label =
                pes_controller_custom_prematch_gameplan_position_label(row);
            line_quads = emit_efootball_line(
                label, (int)strlen(label),
                half_x[side] + 0.020f * (float)screen_width,
                row_y + row_step * (float)row +
                    (row_step - small_gh) * 0.5f,
                small_gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
            prematch_gameplan_white_text_quads += line_quads;
            quads += line_quads;
            char value[22];
            compact_player_name(
                value, sizeof(value),
                pes_controller_custom_prematch_gameplan_position_value(
                    side, row));
            const float value_w = measure_efootball_line(
                value, (int)strlen(value), small_gh, EFOOTBALL_FONT_BOLD);
            line_quads = emit_efootball_line(
                value, (int)strlen(value),
                half_x[side] + half_w - value_w -
                    0.020f * (float)screen_width,
                row_y + row_step * (float)row +
                    (row_step - small_gh) * 0.5f,
                small_gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
            prematch_gameplan_white_text_quads += line_quads;
            quads += line_quads;
          }
        } else {
          for (uint32_t slot = 0;
               slot < prematch_gameplan_picker_visible[side]; slot++) {
            const uint32_t index =
                prematch_gameplan_picker_start[side] + slot;
            const float *rect = prematch_gameplan_picker_rect[side][slot];
            const char *name =
                pes_controller_custom_prematch_gameplan_position_picker_name(
                    side, index);
            const int have_player = strcmp(name, "NONE") != 0;
            const int assigned =
                have_player &&
                pes_controller_custom_prematch_gameplan_position_picker_assigned(
                    side, index);
            const float text_y = rect[1] + (rect[3] - small_gh) * 0.5f;
            const float foot_center_x =
                rect[0] + rect[2] - 0.070f * (float)screen_width;
            const float name_x =
                rect[0] + 0.067f * (float)screen_width;
            if (assigned)
              prematch_gameplan_picker_active_text_first[side][slot] = quads;
            line_quads = emit_efootball_fit_line(
                name, (int)strlen(name), name_x, text_y,
                foot_center_x - name_x -
                    0.028f * (float)screen_width,
                small_gh,
                (float)screen_height / 60.0f,
                EFOOTBALL_FONT_BOLD, verts + quads * 24);
            if (assigned)
              prematch_gameplan_picker_active_text_quads[side][slot] =
                  line_quads;
            prematch_gameplan_white_text_quads += line_quads;
            quads += line_quads;
            const uint32_t foot =
                pes_controller_custom_prematch_gameplan_position_picker_preferred_foot(
                    side, index);
            const uint32_t shot_power =
                pes_controller_custom_prematch_gameplan_position_picker_shot_power(
                    side, index);
            if (have_player) {
              const char foot_text[2] = {foot ? 'L' : 'R', '\0'};
              const float foot_w = measure_efootball_line(
                  foot_text, 1, small_gh, EFOOTBALL_FONT_BOLD);
              line_quads = emit_efootball_line(
                  foot_text, 1, foot_center_x - foot_w * 0.5f, text_y,
                  small_gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
              prematch_gameplan_white_text_quads += line_quads;
              quads += line_quads;
            }
            char shot_text[4];
            if (have_player)
              snprintf(shot_text, sizeof(shot_text), "%u", shot_power);
            else
              strcpy(shot_text, "--");
            const float shot_w = measure_efootball_line(
                shot_text, (int)strlen(shot_text), small_gh,
                EFOOTBALL_FONT_STENCIL);
            if (have_player) {
              prematch_gameplan_picker_metric_first[side][slot] = quads;
            }
            line_quads = emit_efootball_line(
                shot_text, (int)strlen(shot_text),
                rect[0] + rect[2] - shot_w -
                    0.010f * (float)screen_width,
                text_y, small_gh, EFOOTBALL_FONT_STENCIL,
                verts + quads * 24);
            if (have_player)
              prematch_gameplan_picker_metric_quads[side][slot] = line_quads;
            prematch_gameplan_white_text_quads += line_quads;
            quads += line_quads;
          }
        }
      }
      }

      prematch_gameplan_body_text_quads[side] =
          quads - prematch_gameplan_body_text_first_quad[side];
      prematch_gameplan_action_text_first_quad[side] = quads;
      if (!waiting && (!custom_gameplan_exhibition || side == 0))
        for (uint32_t action = 0;
             action < PES_PREMATCH_GAMEPLAN_ACTION_COUNT; action++) {
          const char *action_label = action == 2 && pes_controller_live_gameplan_active()
                                         ? "AUTO LOCKED" : action_labels[action];
          const float width = measure_efootball_line(
              action_label, (int)strlen(action_label),
              action_gh, EFOOTBALL_FONT_BOLD);
          line_quads = emit_efootball_line(
              action_label, (int)strlen(action_label),
              half_x[side] + (action_w + action_gap) * (float)action +
                  (action_w - width) * 0.5f,
              action_y + (action_h - action_gh) * 0.5f, action_gh,
              EFOOTBALL_FONT_BOLD, verts + quads * 24);
          prematch_gameplan_white_text_quads += line_quads;
          quads += line_quads;
        }
      prematch_gameplan_action_text_quads[side] =
          quads - prematch_gameplan_action_text_first_quad[side];

      // Repaint only the active tab label in white over the colored focus
      // tile. Normal tabs stay dark on their translucent white buttons.
      prematch_gameplan_focus_text_first_quad[side] = quads;
      line_quads = 0;
      if (!waiting && (!custom_gameplan_exhibition || side == 0)) {
        const char *focused_action = root_focus == 2 && pes_controller_live_gameplan_active()
                                        ? "AUTO LOCKED" : action_labels[root_focus];
        const float focused_action_w = measure_efootball_line(
            focused_action, (int)strlen(focused_action), action_gh,
            EFOOTBALL_FONT_BOLD);
        line_quads = emit_efootball_line(
            focused_action, (int)strlen(focused_action),
            half_x[side] + (action_w + action_gap) * (float)root_focus +
                (action_w - focused_action_w) * 0.5f,
            action_y + (action_h - action_gh) * 0.5f, action_gh,
            EFOOTBALL_FONT_BOLD, verts + quads * 24);
      }
      prematch_gameplan_focus_text_quads[side] = line_quads;
      prematch_gameplan_white_text_quads += line_quads;
      quads += line_quads;
    }

    prematch_gameplan_role_text_first_quad = quads;
    const float role_gh = (float)screen_height / 48.0f;
    for (uint32_t side = 0; side < 2; side++) {
      const uint32_t page =
          pes_controller_custom_prematch_gameplan_page(side);
      if (pes_controller_custom_prematch_gameplan_waiting(side))
        continue;
      if (page == PES_PREMATCH_GAMEPLAN_PAGE_ROOT ||
          page == PES_PREMATCH_GAMEPLAN_PAGE_SUBSTITUTE) {
        for (uint32_t slot = 0;
             slot < prematch_gameplan_bench_visible[side]; slot++) {
          const uint32_t index = prematch_gameplan_bench_start[side] + slot;
          const float *rect = prematch_gameplan_bench_rect[side][slot];
          const char *role =
              pes_controller_custom_prematch_gameplan_player_role(
                  side, 0, index);
          const float plate_x = rect[0] + 0.006f * (float)screen_width;
          const float plate_w = 0.036f * (float)screen_width;
          const float role_w = measure_efootball_line(
              role, (int)strlen(role), role_gh, EFOOTBALL_FONT_STENCIL);
          line_quads = emit_efootball_fit_line(
              role, (int)strlen(role),
              plate_x + fmaxf(0.0f, (plate_w - role_w) * 0.5f),
              rect[1] + (rect[3] - role_gh) * 0.5f, plate_w, role_gh,
              (float)screen_height / 64.0f, EFOOTBALL_FONT_STENCIL,
              verts + quads * 24);
          prematch_gameplan_role_text_quads += line_quads;
          prematch_gameplan_white_text_quads += line_quads;
          quads += line_quads;
        }
      } else if (
          page == PES_PREMATCH_GAMEPLAN_PAGE_POSITIONS &&
          pes_controller_custom_prematch_gameplan_position_picker_active(
              side)) {
        for (uint32_t slot = 0;
             slot < prematch_gameplan_picker_visible[side]; slot++) {
          const uint32_t index = prematch_gameplan_picker_start[side] + slot;
          const float *rect = prematch_gameplan_picker_rect[side][slot];
          const char *role =
              pes_controller_custom_prematch_gameplan_position_picker_role(
                  side, index);
          if (!role || !role[0] || strcmp(role, "-") == 0)
            continue;
          const float plate_x = rect[0] + 0.012f * (float)screen_width;
          const float plate_w = 0.047f * (float)screen_width;
          const float role_w = measure_efootball_line(
              role, (int)strlen(role), role_gh, EFOOTBALL_FONT_STENCIL);
          line_quads = emit_efootball_fit_line(
              role, (int)strlen(role),
              plate_x + fmaxf(0.0f, (plate_w - role_w) * 0.5f),
              rect[1] + (rect[3] - role_gh) * 0.5f, plate_w, role_gh,
              (float)screen_height / 64.0f, EFOOTBALL_FONT_STENCIL,
              verts + quads * 24);
          prematch_gameplan_role_text_quads += line_quads;
          prematch_gameplan_white_text_quads += line_quads;
          quads += line_quads;
        }
      }
    }

    const char *footer_keys[2][3] = {{0}};
    const char *footer_labels[2][3] = {{0}};
    float footer_icon_x[2][3] = {{0}};
    float footer_label_x[2][3] = {{0}};
    uint32_t footer_count[2] = {0};
    const char *context_keys[2] = {0};
    const char *context_labels[2] = {0};
    const float footer_icon_size = 0.037f * (float)screen_height;
    const float context_icon_size = 0.031f * (float)screen_height;
    const float footer_y = 0.958f * (float)screen_height;
    const float footer_gh = helper_text_gh;
    for (uint32_t side = 0; side < 2; side++) {
      if (custom_gameplan_exhibition && side == 1)
        continue;
      const uint32_t page =
          pes_controller_custom_prematch_gameplan_page(side);
      const int waiting =
          pes_controller_custom_prematch_gameplan_waiting(side);
      const uint32_t profile = android_controller_profile(side);
      const char *select_key = profile == PES_CONTROLLER_PROFILE_SINGLE_LEFT
                                   ? "DOWN" :
                               profile == PES_CONTROLLER_PROFILE_SINGLE_RIGHT
                                   ? "X" : "A";
      const char *back_key = profile == PES_CONTROLLER_PROFILE_SINGLE_LEFT
                                 ? "LEFT" :
                             profile == PES_CONTROLLER_PROFILE_SINGLE_RIGHT
                                 ? "A" : "B";
      const char *role_key = profile == PES_CONTROLLER_PROFILE_SINGLE_LEFT
                                 ? "UP" :
                             profile == PES_CONTROLLER_PROFILE_SINGLE_RIGHT
                                 ? "B" : "Y";
      if (waiting) {
        footer_keys[side][0] = back_key;
        footer_labels[side][0] = "CANCEL";
        footer_count[side] = 1;
      } else {
        footer_keys[side][0] = select_key;
        footer_keys[side][1] = back_key;
        footer_count[side] = 2;
      }
      if (waiting) {
        // The waiting surface only accepts Back; keep the footer truthful.
      } else if (page == PES_PREMATCH_GAMEPLAN_PAGE_ROOT) {
        footer_labels[side][0] = "SELECT";
        footer_labels[side][1] = pes_controller_live_gameplan_active()
                                     ? "READY / PAUSE"
                                     : (side ? "READY" : "HUB");
      } else if (page == PES_PREMATCH_GAMEPLAN_PAGE_SUBSTITUTE) {
        footer_labels[side][0] = "SELECT / SWAP";
        footer_labels[side][1] = "BACK";
        if (pes_controller_custom_prematch_gameplan_substitute_area(side) ==
            PES_PREMATCH_GAMEPLAN_AREA_FIELD) {
          footer_keys[side][2] = role_key;
          footer_labels[side][2] = "CHANGE ROLE";
          footer_count[side] = 3;
        }
        context_keys[side] = select_key;
        if (pes_controller_custom_prematch_gameplan_substitute_area(side) ==
            PES_PREMATCH_GAMEPLAN_AREA_FIELD) {
          const uint32_t drag =
              pes_controller_custom_prematch_gameplan_drag_state(side);
          context_labels[side] = drag == 1 ? "DROP PLAYER" : "HOLD TO MOVE";
        }
      } else {
        footer_labels[side][0] =
            page == PES_PREMATCH_GAMEPLAN_PAGE_POSITIONS ? "SELECT PLAYER"
                                                         : "CHANGE";
        footer_labels[side][1] = "BACK";
      }

      float x = half_x[side] + 0.012f * (float)screen_width;
      for (uint32_t helper = 0; helper < footer_count[side]; helper++) {
        footer_icon_x[side][helper] = x + footer_icon_size * 0.5f;
        footer_label_x[side][helper] = x + footer_icon_size +
                                      0.005f * (float)screen_width;
        const float label_w = measure_efootball_line(
            footer_labels[side][helper],
            (int)strlen(footer_labels[side][helper]), footer_gh,
            EFOOTBALL_FONT_BOLD);
        x = footer_label_x[side][helper] + label_w +
            0.014f * (float)screen_width;
        ADD_SWITCH_HELPER(footer_keys[side][helper],
                          footer_icon_x[side][helper], footer_y,
                          footer_icon_size);
      }
      if (context_labels[side] &&
          prematch_gameplan_context_rect[side][2] > 0.0f) {
        const float *context = prematch_gameplan_context_rect[side];
        ADD_SWITCH_HELPER(context_keys[side],
                          context[0] + 0.008f * (float)screen_width +
                              context_icon_size * 0.5f,
                          context[1] + context[3] * 0.5f,
                          context_icon_size);
      }
    }

    prematch_gameplan_muted_text_first_quad = quads;
    for (uint32_t side = 0; side < 2; side++) {
      for (uint32_t helper = 0; helper < footer_count[side]; helper++) {
        line_quads = emit_efootball_line(
            footer_labels[side][helper],
            (int)strlen(footer_labels[side][helper]),
            footer_label_x[side][helper], footer_y - footer_gh * 0.5f,
            footer_gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
        prematch_gameplan_muted_text_quads += line_quads;
        quads += line_quads;
      }
      if (context_labels[side] &&
          prematch_gameplan_context_rect[side][2] > 0.0f) {
        const float *context = prematch_gameplan_context_rect[side];
        line_quads = emit_efootball_line(
            context_labels[side], (int)strlen(context_labels[side]),
            context[0] + 0.008f * (float)screen_width + context_icon_size +
                0.005f * (float)screen_width,
            context[1] + (context[3] - helper_text_gh) * 0.5f,
            helper_text_gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
        prematch_gameplan_muted_text_quads += line_quads;
        quads += line_quads;
      }
    }

    for (uint32_t side = 0; side < 2; side++) {
      prematch_gameplan_accent_text_first_quad[side] = quads;
      const char *owner = side ? "P2  AWAY" : "P1  HOME";
      if (custom_gameplan_exhibition && side == 1)
        owner = "COM  AWAY";
      line_quads = emit_efootball_line(
          owner, (int)strlen(owner),
          half_x[side] + 0.013f * (float)screen_width +
              header_h - 0.020f * (float)screen_height,
          header_y + header_h - header_meta_gh -
              0.012f * (float)screen_height,
          header_meta_gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
      prematch_gameplan_accent_text_quads[side] += line_quads;
      quads += line_quads;
    }
  } else if (custom_competition) {
    /*
     * Competition pages deliberately live in their own render branch.  The
     * input/state machine is in competition_frontend.c; this adapter only
     * turns its small, stable data surface into PES-style cards.  Keeping the
     * two concerns separate lets Cup grow without adding another switch to
     * the 10k-line native hook file.
     */
    const CompetitionFrontendState state = competition_display_state;
    const int bracket_page =
        state == COMPETITION_FRONTEND_CUP_BRACKET ||
        state == COMPETITION_FRONTEND_CUP_CHECKPOINT;
    const int competition_settings_page =
        state == COMPETITION_FRONTEND_CUP_SETTINGS ||
        state == COMPETITION_FRONTEND_CUP_TEAMS;
    const int competition_team_page =
        state == COMPETITION_FRONTEND_CUP_TEAMS;
    const int competition_team_picker_page =
        competition_team_page && competition_frontend_cup_team_picker_active();
    const int competition_tile_page =
        state == COMPETITION_FRONTEND_MATCH_MODE ||
        state == COMPETITION_FRONTEND_MODES ||
        state == COMPETITION_FRONTEND_CUP_LANDING ||
        state == COMPETITION_FRONTEND_CUP_SLOTS;
    const float panel_x = competition_team_picker_page
                              ? 0.035f * (float)screen_width
                              : competition_settings_page
                                    ? 0.170f * (float)screen_width
                              : 0.055f * (float)screen_width;
    const float panel_y = bracket_page
                              ? 0.070f * (float)screen_height
                              : competition_team_picker_page
                                    ? 0.040f * (float)screen_height
                              : competition_settings_page
                                    ? 0.080f * (float)screen_height
                                    : 0.275f * (float)screen_height;
    const float panel_w = bracket_page
                              ? 0.890f * (float)screen_width
                              : competition_team_picker_page
                                    ? 0.430f * (float)screen_width
                              : competition_settings_page
                                    ? 0.660f * (float)screen_width
                                    : 0.450f * (float)screen_width;
    const float panel_h = bracket_page
                              ? 0.690f * (float)screen_height
                              : competition_team_picker_page
                                    ? 0.850f * (float)screen_height
                              : competition_team_page
                                    ? 0.600f * (float)screen_height
                              : competition_settings_page
                                    ? 0.770f * (float)screen_height
                                    : 0.590f * (float)screen_height;
    const float header_h = competition_settings_page
                               ? (competition_team_picker_page
                                      ? 0.120f * (float)screen_height
                                      : 0.115f * (float)screen_height)
                               : 0.0f;
    const float title_h = screen_height / 21.0f;
    const float subtitle_h = screen_height / 39.0f;
    const float body_x = panel_x +
                         (bracket_page ? 0.0f
                                       : (1.0f - competition_menu_mix) *
                                             0.500f * (float)screen_width);
    const float body_w = panel_w;
    const float body_top = bracket_page
                               ? 0.270f * (float)screen_height
                               : competition_settings_page
                                     ? panel_y + header_h +
                                           0.030f * (float)screen_height
                                     : competition_tile_page
                                           ? 0.365f * (float)screen_height
                                           : 0.315f * (float)screen_height;
    const float helper_y = 0.945f * (float)screen_height;

    competition_background_quad = quads;
    quads += emit_image_rect(0.0f, 0.0f, (float)screen_width,
                             (float)screen_height, verts + quads * 24);
    /* Keep the brand and portrait in the same places as the main page. */
    competition_brand_quad = quads;
    quads += emit_image_rect(0.055f * screen_width,
                             0.052f * screen_height,
                             0.245f * screen_width,
                             0.245f * screen_width * (496.0f / 1310.0f),
                             verts + quads * 24);
    competition_portrait_quad = quads;
    quads += emit_image_rect(0.540f * screen_width,
                             0.035f * screen_height,
                             0.425f * screen_width,
                             1.010f * screen_height,
                             verts + quads * 24);
    /* The four native tiles leave to the left while the submenu cards enter
     * from the right.  The transition is driven by the frontend state and is
     * shared by Match, Modes, and the Cup landing page. */
    static const char *const departing_labels[4] = {
        "MATCH", "MODES", "SETTINGS", "CREDITS"};
    const float departing_x =
        0.055f * screen_width - (1.0f - competition_menu_mix) *
                                   0.550f * screen_width;
    const float departing_y = 0.315f * screen_height;
    const float departing_w = 0.450f * screen_width;
    const float departing_h = 0.115f * screen_height;
    const float departing_step = 0.135f * screen_height;
    competition_departing_style =
        (RoundedRectStyle){departing_w, departing_h,
                           0.014f * (float)screen_height};
    for (uint32_t row = 0; row < 4; row++) {
      competition_departing_card_quads[row] = quads;
      quads += emit_round_rect_quad(
          departing_x, departing_y + row * departing_step, departing_w,
          departing_h, verts + quads * 24);
      const float icon_size = 0.078f * screen_height;
      const float icon_x = departing_x + departing_w -
                           0.022f * screen_width - icon_size;
      const float icon_y = departing_y + row * departing_step +
                           (departing_h - icon_size) * 0.5f;
      const float u0 = (row & 1u) ? 0.5f : 0.0f;
      const float v0 = (row >= 2u) ? 0.5f : 0.0f;
      competition_departing_icon_quads[row] = quads;
      quads += emit_image_rect_uv(icon_x, icon_y, icon_size, icon_size,
                                  u0, v0, u0 + 0.5f, v0 + 0.5f,
                                  verts + quads * 24);
      const float departing_label_h = screen_height / 20.0f;
      competition_departing_label_first_quad[row] = quads;
      competition_departing_label_quads[row] = emit_efootball_line(
          departing_labels[row], (int)strlen(departing_labels[row]),
          departing_x + 0.030f * screen_width,
          departing_y + row * departing_step +
              (departing_h - departing_label_h) * 0.5f,
          departing_label_h, EFOOTBALL_FONT_STENCIL, verts + quads * 24);
      quads += competition_departing_label_quads[row];
    }
    if (!competition_settings_page && !bracket_page) {
      competition_title_first_quad = quads;
      competition_title_quads = emit_efootball_fit_line(
          competition_frontend_title(),
          (int)strlen(competition_frontend_title()), panel_x,
          bracket_page ? 0.120f * (float)screen_height
                       : 0.285f * (float)screen_height,
          panel_w * 0.96f, title_h,
          title_h * 0.65f, EFOOTBALL_FONT_STENCIL, verts + quads * 24);
      quads += competition_title_quads;
    }
    if (bracket_page) {
      const CupTournament *cup = competition_frontend_cup_tournament();
      const uint32_t view_round = competition_frontend_cup_view_round();
      const uint32_t first = competition_frontend_cup_view_first_fixture();
      const uint32_t fixture_count = cup
          ? cup_tournament_fixture_count(cup, view_round) : 0u;
      const uint32_t visible = fixture_count > first
          ? (fixture_count - first < 4u ? fixture_count - first : 4u) : 0u;
      const float inner_x = panel_x + 0.020f * (float)screen_width;
      const float inner_w = panel_w - 0.040f * (float)screen_width;
      const float gap = 0.018f * (float)screen_width;
      const float left_w = (inner_w - gap) * 0.60f;
      const float right_w = inner_w - gap - left_w;
      const float right_x = inner_x + left_w + gap;
      const float body_y = panel_y + 0.132f * (float)screen_height;
      const float body_h = 0.540f * (float)screen_height;
      const float card_y = body_y + 0.084f * (float)screen_height;
      const float card_step = 0.108f * (float)screen_height;
      const float card_h = 0.092f * (float)screen_height;
      const float child_slot_h = card_h * 0.48f;
      const float child_x = inner_x + 0.012f * (float)screen_width;
      const float slot_glyph_h = roundf(fminf(child_slot_h * 0.58f,
                                              (float)screen_height / 38.0f));
      /* Reserve only what a crest, three-letter name, ownership, and score
       * need. Both columns use the same compact card width. */
      const float child_w = 0.024f * (float)screen_width +
          0.035f * (float)screen_height +
          measure_efootball_line("MUN - COM", 9, slot_glyph_h,
                                 EFOOTBALL_FONT_BOLD) +
          measure_efootball_line("99", 2, slot_glyph_h,
                                 EFOOTBALL_FONT_BOLD);
      const float parent_w = child_w;
      const float parent_x = inner_x + left_w - parent_w -
                             0.012f * (float)screen_width;
      const float parent_h = 0.092f * (float)screen_height;
      const float parent_slot_h = parent_h * 0.48f;
      const float hist_x = right_x + 0.012f * (float)screen_width;
      const float hist_w = right_w - 0.024f * (float)screen_width;
      const float history_y = body_y + 0.072f * (float)screen_height;
      const float history_h = 0.075f * (float)screen_height;
      const float history_step = 0.087f * (float)screen_height;
      const float action_y = body_y + body_h +
                             0.034f * (float)screen_height;
      const float action_w = 0.190f * (float)screen_width;
      const float action_h = 0.075f * (float)screen_height;
      const float action_gap = 0.018f * (float)screen_width;
      const float action_x = ((float)screen_width - 2.0f * action_w -
                              action_gap) * 0.5f;
      cup_shell_style = (RoundedRectStyle){panel_w, panel_h,
                                           0.023f * (float)screen_height};
      cup_shell_quad = quads;
      quads += emit_round_rect_quad(panel_x, panel_y, panel_w, panel_h,
                                    verts + quads * 24);
      cup_header_style = (RoundedRectStyle){panel_w,
          0.105f * (float)screen_height, 0.023f * (float)screen_height};
      cup_header_quad = quads;
      quads += emit_round_rect_quad(panel_x, panel_y, panel_w,
                                    0.105f * (float)screen_height,
                                    verts + quads * 24);
      cup_left_style = (RoundedRectStyle){left_w, body_h,
                                          0.015f * (float)screen_height};
      cup_left_quad = quads;
      quads += emit_round_rect_quad(inner_x, body_y, left_w, body_h,
                                    verts + quads * 24);
      cup_right_style = (RoundedRectStyle){right_w, body_h,
                                           0.015f * (float)screen_height};
      cup_right_quad = quads;
      quads += emit_round_rect_quad(right_x, body_y, right_w, body_h,
                                    verts + quads * 24);
      cup_fixture_style = (RoundedRectStyle){child_w, child_slot_h,
                                              0.008f * (float)screen_height};
      cup_bye_style = cup_fixture_style;
      uint32_t next_round = 0, next_index = 0;
      const int has_next = competition_frontend_cup_next_fixture(
          &next_round, &next_index);
      const CupFixture *upcoming = has_next
          ? cup_tournament_fixture(cup, next_round, next_index) : NULL;
      for (uint32_t i = 0; i < visible; i++) {
        const float y = card_y + card_step * (float)i;
        const CupFixture *fixture = cup_tournament_fixture(
            cup, view_round, first + i);
        if (cup_fixture_is_bye(fixture)) {
          cup_bye_quads[i] = quads;
          quads += emit_round_rect_quad(child_x,
              y + (card_h - child_slot_h) * 0.5f,
              child_w, child_slot_h,
              verts + quads * 24);
        } else {
          cup_fixture_quads[i] = quads;
          quads += emit_round_rect_quad(child_x, y, child_w,
                                        child_slot_h,
                                        verts + quads * 24);
          cup_fixture_away_quads[i] = quads;
          quads += emit_round_rect_quad(child_x,
              y + card_h - child_slot_h, child_w, child_slot_h,
              verts + quads * 24);
        }
        if (has_next && next_round == view_round &&
            next_index == first + i)
          cup_focus_fixture = (int)i;
      }
      const uint32_t parent_count = view_round + 1u < cup->round_count
          ? (visible + 1u) / 2u : (visible ? 1u : 0u);
      cup_next_style = (RoundedRectStyle){parent_w, parent_slot_h,
          0.008f * (float)screen_height};
      for (uint32_t i = 0; i < parent_count && i < 4u; i++) {
        const float y = view_round + 1u == cup->round_count
            ? card_y + (card_h - parent_h) * 0.5f
            : card_y + card_step * (float)(2u * i) +
                  card_step * 0.5f - (parent_h - card_h) * 0.5f;
        cup_next_quads[i] = quads;
        quads += emit_round_rect_quad(parent_x,
            y + (view_round + 1u == cup->round_count
                     ? (parent_h - parent_slot_h) * 0.5f : 0.0f),
            parent_w, parent_slot_h,
                                      verts + quads * 24);
        if (view_round + 1u < cup->round_count) {
          cup_next_away_quads[i] = quads;
          quads += emit_round_rect_quad(parent_x,
              y + parent_h - parent_slot_h,
              parent_w, parent_slot_h, verts + quads * 24);
        }
      }
      cup_border_first = quads;
      const float border = fmaxf(1.4f, (float)screen_height / 520.0f);
      for (uint32_t i = 0; i < visible; i++) {
        const int bye = cup_bye_quads[i] != 0;
        for (uint32_t side = 0; side < (bye ? 1u : 2u); side++) {
          const float y = card_y + card_step * (float)i +
              (bye ? (card_h - child_slot_h) * 0.5f
                   : side ? card_h - child_slot_h : 0.0f);
          quads += emit_rect(child_x, y, child_w, border,
                             verts + quads * 24);
          quads += emit_rect(child_x, y + child_slot_h - border,
                             child_w, border, verts + quads * 24);
          quads += emit_rect(child_x, y, border, child_slot_h,
                             verts + quads * 24);
          quads += emit_rect(child_x + child_w - border, y, border,
                             child_slot_h, verts + quads * 24);
          cup_border_count += 4;
        }
      }
      for (uint32_t i = 0; i < parent_count && i < 4u; i++) {
        const int final = view_round + 1u == cup->round_count;
        const float base_y = final
            ? card_y + (card_h - parent_h) * 0.5f
            : card_y + card_step * (float)(2u * i) +
                  card_step * 0.5f - (parent_h - card_h) * 0.5f;
        for (uint32_t side = 0; side < (final ? 1u : 2u); side++) {
          const float y = base_y +
              (final ? (parent_h - parent_slot_h) * 0.5f
                     : side ? parent_h - parent_slot_h : 0.0f);
          quads += emit_rect(parent_x, y, parent_w, border,
                             verts + quads * 24);
          quads += emit_rect(parent_x, y + parent_slot_h - border,
                             parent_w, border, verts + quads * 24);
          quads += emit_rect(parent_x, y, border, parent_slot_h,
                             verts + quads * 24);
          quads += emit_rect(parent_x + parent_w - border, y, border,
                             parent_slot_h, verts + quads * 24);
          cup_border_count += 4;
        }
      }
      cup_connector_first = quads;
      for (uint32_t i = 0; i < parent_count && i < 4u; i++) {
        const float y0 = card_y + card_step * (float)(2u * i) + card_h * 0.5f;
        const float y1 = y0 + card_step;
        const float mid_x = child_x + child_w +
                            (parent_x - child_x - child_w) * 0.50f;
        const float thick = 1.8f;
        if (view_round + 1u == cup->round_count) {
          quads += emit_rect(child_x + child_w, y0,
                             parent_x - child_x - child_w, thick,
                             verts + quads * 24);
          cup_connector_count++;
          continue;
        }
        quads += emit_rect(child_x + child_w, y0, mid_x - child_x - child_w,
                           thick, verts + quads * 24);
        cup_connector_count++;
        if (2u * i + 1u < visible) {
          quads += emit_rect(child_x + child_w, y1,
                             mid_x - child_x - child_w, thick,
                             verts + quads * 24);
          cup_connector_count++;
          quads += emit_rect(mid_x, y0, thick, y1 - y0,
                             verts + quads * 24);
          cup_connector_count++;
        }
        quads += emit_rect(mid_x, (y0 + y1) * 0.5f,
                           parent_x - mid_x, thick, verts + quads * 24);
        cup_connector_count++;
      }
      cup_history_style = (RoundedRectStyle){hist_w, history_h,
          0.009f * (float)screen_height};
      const uint32_t history_cards = cup->history_count < 4u
          ? cup->history_count : 4u;
      for (uint32_t i = 0; i <= history_cards; i++) {
        cup_history_quads[i] = quads;
        quads += emit_round_rect_quad(hist_x, history_y +
            history_step * (float)i, hist_w, history_h, verts + quads * 24);
      }
      cup_action_style = (RoundedRectStyle){action_w, action_h,
          0.016f * (float)screen_height};
      for (uint32_t i = 0; i < 2u; i++) {
        cup_action_quads[i] = quads;
        quads += emit_round_rect_quad(action_x + (action_w + action_gap) * i,
                                      action_y, action_w, action_h,
                                      verts + quads * 24);
      }
      cup_badge_first = quads;
      for (uint32_t i = 0; i < visible; i++) {
        const CupFixture *fixture = cup_tournament_fixture(
            cup, view_round, first + i);
        const float y = card_y + card_step * (float)i;
        const int bye = cup_fixture_is_bye(fixture);
        const float badge = 0.034f * (float)screen_height;
        if (fixture && fixture->home) {
          quads += emit_badge(exhibition_team_catalog_badge(fixture->home),
                              child_x + 0.008f * (float)screen_width,
                              y + (bye ? (card_h - child_slot_h) * 0.5f
                                       : 0.0f) +
                                  (child_slot_h - badge) * 0.5f,
                              badge, badge, verts + quads * 24);
          cup_badge_count++;
        }
        if (fixture && fixture->away) {
          quads += emit_badge(exhibition_team_catalog_badge(fixture->away),
                              child_x + 0.008f * (float)screen_width,
                              y + card_h - child_slot_h +
                                  (child_slot_h - badge) * 0.5f,
                              badge, badge, verts + quads * 24);
          cup_badge_count++;
        }
      }
      for (uint32_t i = 0; i < parent_count && i < 4u; i++) {
        const float y = view_round + 1u == cup->round_count
            ? card_y + (card_h - parent_h) * 0.5f
            : card_y + card_step * (float)(2u * i) +
                  card_step * 0.5f - (parent_h - card_h) * 0.5f;
        if (view_round + 1u == cup->round_count) {
          const CupFixture *fixture = cup_tournament_fixture(
              cup, view_round, first + i);
          if (fixture && fixture->winner) {
            const float badge = 0.034f * (float)screen_height;
            quads += emit_badge(exhibition_team_catalog_badge(fixture->winner),
                parent_x + 0.008f * (float)screen_width,
                y + (parent_h - parent_slot_h) * 0.5f +
                    (parent_slot_h - badge) * 0.5f,
                badge, badge, verts + quads * 24);
            cup_badge_count++;
          }
        } else {
          const CupFixture *fixture = cup_tournament_fixture(
              cup, view_round + 1u, first / 2u + i);
          const uint32_t teams[2] = {
              fixture ? fixture->home : 0u,
              fixture ? fixture->away : 0u};
          for (uint32_t side = 0; side < 2u; side++) {
            if (!teams[side]) continue;
            const float badge = 0.034f * (float)screen_height;
            quads += emit_badge(exhibition_team_catalog_badge(teams[side]),
                parent_x + 0.008f * (float)screen_width,
                y + (side ? parent_h - parent_slot_h : 0.0f) +
                    (parent_slot_h - badge) * 0.5f,
                badge, badge, verts + quads * 24);
            cup_badge_count++;
          }
        }
      }
      const float history_badge = 0.032f * (float)screen_height;
      if (cup->champion || upcoming) {
        const uint32_t teams[2] = {
            cup->champion ? cup->champion : upcoming->home,
            cup->champion ? 0u : upcoming->away};
        for (uint32_t side = 0; side < 2u; side++) {
          if (!teams[side]) continue;
          quads += emit_badge(exhibition_team_catalog_badge(teams[side]),
              hist_x + (side ? hist_w * 0.67f
                             : 0.010f * (float)screen_width),
              history_y + (history_h - history_badge) * 0.5f,
              history_badge, history_badge, verts + quads * 24);
          cup_badge_count++;
        }
      }
      for (uint32_t i = 0; i < history_cards; i++) {
        const uint32_t h = cup->history_count - 1u - i;
        const CupFixture *fixture = cup_tournament_fixture(
            cup, cup->history_round[h], cup->history_index[h]);
        if (!fixture) continue;
        const uint32_t teams[2] = {fixture->home, fixture->away};
        const float y = history_y + history_step * (float)(i + 1u);
        for (uint32_t side = 0; side < 2u; side++) {
          if (!teams[side]) continue;
          quads += emit_badge(exhibition_team_catalog_badge(teams[side]),
              hist_x + (side ? hist_w * 0.67f
                             : 0.010f * (float)screen_width),
              y + (history_h - history_badge) * 0.5f,
              history_badge, history_badge, verts + quads * 24);
          cup_badge_count++;
        }
      }
      cup_text_first = quads;
      const float title_size = (float)screen_height / 20.0f;
      const float head_size = (float)screen_height / 43.0f;
      const float row_size = roundf((float)screen_height / 39.0f);
      const char *cup_name = competition_frontend_cup_name();
      quads += emit_efootball_centered_fit_line(
          cup_name, (int)strlen(cup_name), (float)screen_width * 0.5f,
          panel_y + 0.026f * (float)screen_height, panel_w * 0.86f,
          title_size, title_size * 0.62f, EFOOTBALL_FONT_STENCIL,
          verts + quads * 24);
      const char *round_name = competition_frontend_cup_round_name(view_round);
      char round_heading[64];
      snprintf(round_heading, sizeof(round_heading), "%s  %u / %u",
               round_name, competition_frontend_cup_view_index() + 1u,
               competition_frontend_cup_view_count());
      quads += emit_efootball_fit_line(
          round_heading, (int)strlen(round_heading), child_x,
          body_y + 0.025f * (float)screen_height, child_w,
          head_size, head_size * 0.60f, EFOOTBALL_FONT_STENCIL,
          verts + quads * 24);
      const char *advance_label = view_round + 1u < cup->round_count
                                      ? competition_frontend_cup_round_name(view_round + 1u)
                                      : "CHAMPION";
      quads += emit_efootball_fit_line(
          advance_label, (int)strlen(advance_label), parent_x,
          body_y + 0.025f * (float)screen_height, parent_w,
          head_size, head_size * 0.60f, EFOOTBALL_FONT_STENCIL,
          verts + quads * 24);
      for (uint32_t i = 0; i < visible; i++) {
        const CupFixture *fixture = cup_tournament_fixture(
            cup, view_round, first + i);
        if (!fixture) continue;
        const float y = card_y + card_step * (float)i;
        const int bye = cup_fixture_is_bye(fixture);
        const uint32_t teams[2] = {fixture->home, fixture->away};
        const uint32_t sides = bye ? 1u : 2u;
        for (uint32_t side = 0; side < sides; side++) {
          const float slot_y = y + (bye
              ? (card_h - child_slot_h) * 0.5f
              : side ? card_h - child_slot_h : 0.0f);
          quads += emit_cup_slot_text(
              teams[side], fixture->home && fixture->away,
              side ? fixture->away_goals : fixture->home_goals,
              child_x, slot_y, child_w, child_slot_h, verts + quads * 24);
        }
      }
      for (uint32_t i = 0; i < parent_count && i < 4u; i++) {
        const int final = view_round + 1u == cup->round_count;
        const CupFixture *fixture = cup_tournament_fixture(
            cup, final ? view_round : view_round + 1u,
            final ? first + i : first / 2u + i);
        const float y = final
            ? card_y + (card_h - parent_h) * 0.5f
            : card_y + card_step * (float)(2u * i) +
                  card_step * 0.5f - (parent_h - card_h) * 0.5f;
        if (final) {
          quads += emit_cup_slot_text(
              fixture ? fixture->winner : 0u, 0, 0u,
              parent_x, y + (parent_h - parent_slot_h) * 0.5f,
              parent_w, parent_slot_h, verts + quads * 24);
          continue;
        }
        const uint32_t teams[2] = {fixture ? fixture->home : 0u,
                                   fixture ? fixture->away : 0u};
        for (uint32_t side = 0; side < 2u; side++) {
          quads += emit_cup_slot_text(
              teams[side], fixture && fixture->home && fixture->away,
              fixture ? (side ? fixture->away_goals
                              : fixture->home_goals) : 0u,
              parent_x, y + (side ? parent_h - parent_slot_h : 0.0f),
              parent_w, parent_slot_h, verts + quads * 24);
        }
      }
      const char *right_title = "MATCH HISTORY";
      quads += emit_efootball_fit_line(
          right_title, (int)strlen(right_title), hist_x,
          body_y + 0.025f * (float)screen_height, hist_w,
          head_size, head_size, EFOOTBALL_FONT_STENCIL,
          verts + quads * 24);
      if (cup->champion) {
        char champion_code[4];
        cup_team_code(cup->champion, champion_code);
        quads += emit_efootball_line(
            champion_code, 3,
            hist_x + 0.010f * (float)screen_width + history_badge +
                0.007f * (float)screen_width,
            history_y + (history_h - row_size) * 0.5f,
            row_size, EFOOTBALL_FONT_BOLD, verts + quads * 24);
        const char *champion_label = "CHAMPION";
        const float champion_w = measure_efootball_line(
            champion_label, 8, row_size, EFOOTBALL_FONT_BOLD);
        quads += emit_efootball_line(
            champion_label, 8, hist_x + hist_w - champion_w -
                0.018f * (float)screen_width,
            history_y + (history_h - row_size) * 0.5f,
            row_size, EFOOTBALL_FONT_BOLD, verts + quads * 24);
      } else if (upcoming) {
        quads += emit_cup_history_match_text(
            upcoming->home, upcoming->away, 0u, 0u,
            hist_x, history_y, hist_w, history_h, verts + quads * 24);
      } else {
        const char *waiting = "WAITING FOR RESULT";
        quads += emit_efootball_centered_fit_line(
            waiting, (int)strlen(waiting), hist_x + hist_w * 0.5f,
            history_y + (history_h - row_size) * 0.5f,
            hist_w * 0.90f, row_size, row_size,
            EFOOTBALL_FONT_BOLD, verts + quads * 24);
      }
      for (uint32_t i = 0; i < history_cards; i++) {
        const uint32_t h = cup->history_count - 1u - i;
        const CupFixture *fixture = cup_tournament_fixture(
            cup, cup->history_round[h], cup->history_index[h]);
        if (!fixture) continue;
        const float y = history_y + history_step * (float)(i + 1u);
        quads += emit_cup_history_match_text(
            fixture->home, fixture->away, fixture->home_goals,
            fixture->away_goals, hist_x, y, hist_w, history_h,
            verts + quads * 24);
      }
      const char *status = competition_frontend_status();
      if (status && status[0])
        quads += emit_efootball_centered_fit_line(
            status, (int)strlen(status), (float)screen_width * 0.5f,
            body_y + body_h - 0.028f * (float)screen_height,
            panel_w * 0.86f, row_size, row_size,
            EFOOTBALL_FONT_BOLD, verts + quads * 24);
      cup_text_count = quads - cup_text_first;
      const char *const actions[2] = {"NEXT", "TOP TO MENU"};
      for (uint32_t i = 0; i < 2u; i++) {
        cup_action_text_first[i] = quads;
        quads += emit_efootball_centered_fit_line(
            actions[i], (int)strlen(actions[i]),
            action_x + (action_w + action_gap) * i + action_w * 0.5f,
            action_y + (action_h - head_size) * 0.5f,
            action_w * 0.86f, head_size, head_size * 0.60f,
            EFOOTBALL_FONT_BOLD, verts + quads * 24);
        cup_action_text_count[i] = quads - cup_action_text_first[i];
      }
    } else if (competition_settings_page) {
      /* Cup setup follows the Hub Settings vocabulary.  Settings expose at
       * most five rows at once; team assignment gets its own centered slot
       * strip and a single-sided team picker instead of arrow/value rows. */
      const uint32_t focus = competition_display_focus;
      const uint32_t row_count = 8u;
      const uint32_t visible_rows = 5u;
      const float row_x = panel_x + 0.040f * (float)screen_width;
      const float row_w = panel_w - 0.080f * (float)screen_width;
      const float row_h = 0.082f * (float)screen_height;
      const float row_step = 0.108f * (float)screen_height;
      const float value_w = 0.205f * (float)screen_width;
      const float value_h = 0.058f * (float)screen_height;
      const float value_x = panel_x + panel_w -
                            0.070f * (float)screen_width - value_w;
      const float selector_inset = 0.006f * (float)screen_height;

      competition_full_panel_style =
          (RoundedRectStyle){panel_w, panel_h,
                             0.025f * (float)screen_height};
      competition_full_panel_quad = quads;
      quads += emit_round_rect_quad(panel_x, panel_y, panel_w, panel_h,
                                    verts + quads * 24);
      competition_full_header_style =
          (RoundedRectStyle){panel_w, header_h,
                             0.025f * (float)screen_height};
      competition_full_header_round_quad = quads;
      quads += emit_round_rect_quad(panel_x, panel_y, panel_w, header_h,
                                    verts + quads * 24);
      competition_full_header_fill_quad = quads;
      quads += emit_rect(panel_x, panel_y + header_h -
                                   0.025f * (float)screen_height,
                         panel_w, 0.025f * (float)screen_height,
                         verts + quads * 24);

      if (competition_team_page && !competition_team_picker_page) {
        const uint32_t slots = competition_frontend_cup_player_count() > 8u
                                   ? 8u
                                   : competition_frontend_cup_player_count();
        const float slot_gap = 0.012f * (float)screen_width;
        const float slot_w = fminf(0.160f * (float)screen_width,
                                   (panel_w - 0.075f * (float)screen_width -
                                    slot_gap * (slots ? slots - 1u : 0u)) /
                                       (float)(slots ? slots : 1u));
        const float slot_h = fminf(0.245f * (float)screen_height,
                                   slot_w * 0.94f);
        const float slots_w = slots * slot_w +
                              (slots ? slots - 1u : 0u) * slot_gap;
        const float slot_x0 = panel_x + (panel_w - slots_w) * 0.5f;
        const float slot_y = panel_y + header_h +
                             (panel_h - header_h - slot_h) * 0.5f;
        competition_team_slot_style =
            (RoundedRectStyle){slot_w, slot_h,
                               0.014f * (float)screen_height};
        const float slot_label_h = (float)screen_height / 40.0f;
        const float slot_value_h = (float)screen_height / 52.0f;
        for (uint32_t slot = 0; slot < slots; slot++) {
          const float x = slot_x0 + slot * (slot_w + slot_gap);
          competition_team_slot_quads[slot] = quads;
          quads += emit_round_rect_quad(x, slot_y, slot_w, slot_h,
                                        verts + quads * 24);
          char player_label[8];
          snprintf(player_label, sizeof(player_label), "P%u", slot + 1u);
          competition_label_first_quad[slot] = quads;
          competition_label_quads[slot] = emit_efootball_centered_fit_line(
              player_label, (int)strlen(player_label), x + slot_w * 0.5f,
              slot_y + 0.020f * (float)screen_height, slot_w * 0.78f,
              slot_label_h, slot_label_h * 0.62f, EFOOTBALL_FONT_STENCIL,
              verts + quads * 24);
          quads += competition_label_quads[slot];
          const char *value = competition_frontend_item_value(slot);
          competition_value_first_quad[slot] = quads;
          competition_value_quads[slot] = emit_efootball_centered_fit_line(
              value, (int)strlen(value), x + slot_w * 0.5f,
              slot_y + slot_h - 0.035f * (float)screen_height,
              slot_w * 0.88f, slot_value_h, slot_value_h * 0.58f,
              EFOOTBALL_FONT_BOLD, verts + quads * 24);
          quads += competition_value_quads[slot];
        }
        for (uint32_t slot = 0; slot < slots; slot++) {
          if (!competition_frontend_cup_team_selected(slot))
            continue;
          const float badge_size = fminf(slot_w * 0.55f, slot_h * 0.52f);
          competition_team_slot_badge_quads[slot] = quads;
          quads += emit_badge(
              competition_frontend_cup_team_badge(slot),
              slot_x0 + slot * (slot_w + slot_gap) +
                  (slot_w - badge_size) * 0.5f,
              slot_y + (slot_h - badge_size) * 0.48f,
              badge_size, badge_size, verts + quads * 24);
        }

      } else if (competition_team_picker_page) {
        const float picker_x = panel_x;
        const float picker_w = panel_w;
        const float picker_y = panel_y + header_h;
        const float picker_h = panel_h - header_h;
        const float card_h = 0.340f * (float)screen_height;
        const float card_y = 0.350f * (float)screen_height;
        const float text_h = (float)screen_height / 52.0f;
        const float small_h = (float)screen_height / 57.0f;
        competition_team_picker_style =
            (RoundedRectStyle){picker_w, picker_h, 0.014f * (float)screen_height};
        competition_team_picker_candidate_style =
            (RoundedRectStyle){picker_w, card_h, 0.014f * (float)screen_height};
        competition_team_picker_quad = quads;
        quads += emit_round_rect_quad(picker_x, picker_y, picker_w, picker_h,
                                      verts + quads * 24);
        competition_team_picker_candidate_quad = quads;
        quads += emit_round_rect_quad(picker_x, card_y, picker_w, card_h,
                                      verts + quads * 24);
        competition_team_picker_title_first_quad = quads;
        competition_team_picker_title_quads = emit_efootball_centered_fit_line(
            "SELECT TEAM", 11, picker_x + picker_w * 0.5f,
            panel_y + 0.078f * (float)screen_height, picker_w * 0.86f,
            text_h, text_h * 0.62f, EFOOTBALL_FONT_BOLD,
            verts + quads * 24);
        quads += competition_team_picker_title_quads;
        const char *candidate = competition_frontend_cup_team_picker_name();
        competition_team_picker_value_first_quad = quads;
        competition_team_picker_value_quads = emit_efootball_centered_fit_line(
            candidate, (int)strlen(candidate), picker_x + picker_w * 0.5f,
            card_y + 0.020f * (float)screen_height,
            picker_w * 0.84f, (float)screen_height / 31.0f,
            (float)screen_height / 44.0f, EFOOTBALL_FONT_STENCIL,
            verts + quads * 24);
        quads += competition_team_picker_value_quads;
        const float small_row_h = card_h * 0.25f;
        for (uint32_t item = 0; item < 5u; item++) {
          const int relative = (int)item - 2;
          if (!relative)
            continue;
          const float row_y =
              (relative < 0
                   ? 0.180f + (float)(relative + 2) * 0.085f
                   : 0.690f + (float)(relative - 1) * 0.085f) *
              (float)screen_height;
          competition_team_picker_row_quads[item] = quads;
          quads += emit_round_rect_quad(picker_x, row_y, picker_w, small_row_h,
                                        verts + quads * 24);
          const char *name =
              competition_frontend_cup_team_picker_name_at(relative);
          competition_team_picker_row_text_first_quad[item] = quads;
          competition_team_picker_row_text_quads[item] = emit_efootball_fit_line(
              name, (int)strlen(name), picker_x + 0.052f * (float)screen_width,
              row_y + (small_row_h - small_h) * 0.5f, picker_w * 0.82f,
              small_h, small_h * 0.60f, EFOOTBALL_FONT_BOLD,
              verts + quads * 24);
          quads += competition_team_picker_row_text_quads[item];
        }
      } else {
        uint32_t start_row = 0;
        if (focus >= visible_rows)
          start_row = focus - visible_rows + 1u;
        if (start_row > row_count - visible_rows)
          start_row = row_count - visible_rows;
        const uint32_t end_row = start_row + visible_rows;
        competition_full_selected_style =
            (RoundedRectStyle){row_w - selector_inset * 2.0f,
                               row_h - selector_inset * 2.0f,
                               0.014f * (float)screen_height};
        if (focus < row_count) {
          const uint32_t visible_focus = focus - start_row;
          competition_full_selected_quad = quads;
          quads += emit_round_rect_quad(
              row_x + selector_inset,
              body_top + row_step * (float)visible_focus + selector_inset,
              row_w - selector_inset * 2.0f,
              row_h - selector_inset * 2.0f, verts + quads * 24);
        }
        competition_full_rule_first_quad = quads;
        for (uint32_t visible = 1; visible < visible_rows; visible++) {
          const float rule_y = floorf(body_top + row_step * (float)visible -
                                      (row_step - row_h) * 0.5f);
          competition_full_rule_quads += emit_rect(
              row_x, rule_y, row_w,
              fmaxf(1.8f, (float)screen_height / 450.0f),
              verts + quads * 24);
          quads++;
        }
        competition_full_value_style =
            (RoundedRectStyle){value_w, value_h, value_h * 0.5f};
        for (uint32_t row = start_row; row < end_row && row < 12u; row++) {
          const uint32_t visible = row - start_row;
          const float value_y = body_top + row_step * (float)visible +
                                (row_h - value_h) * 0.5f;
          competition_value_plate_quads[row] = quads;
          quads += emit_round_rect_quad(value_x, value_y, value_w, value_h,
                                        verts + quads * 24);
          const float center_y = body_top + row_step * (float)visible +
                                 row_h * 0.5f;
          const float arrow_w = 0.007f * (float)screen_width;
          const float arrow_h = 0.012f * (float)screen_height;
          if (competition_frontend_item_enabled(row)) {
            if (!competition_full_arrow_quads)
              competition_full_arrow_first_quad = quads;
            const float left_x = value_x - 0.014f * (float)screen_width;
            competition_full_arrow_quads += emit_triangle(
                left_x + arrow_w, center_y - arrow_h,
                left_x - arrow_w, center_y,
                left_x + arrow_w, center_y + arrow_h, verts + quads * 24);
            quads++;
            const float right_x = value_x + value_w +
                                  0.014f * (float)screen_width;
            competition_full_arrow_quads += emit_triangle(
                right_x - arrow_w, center_y - arrow_h,
                right_x + arrow_w, center_y,
                right_x - arrow_w, center_y + arrow_h, verts + quads * 24);
            quads++;
          }
        }
        const float label_h = (float)screen_height / 42.0f;
        const float value_gh = (float)screen_height / 43.0f;
        for (uint32_t row = start_row; row < end_row && row < 12u; row++) {
          const uint32_t visible = row - start_row;
          const float row_y = body_top + row_step * (float)visible;
          const char *label = competition_frontend_item_label(row);
          competition_label_first_quad[row] = quads;
          competition_label_quads[row] = emit_efootball_fit_line(
              label, (int)strlen(label), row_x + 0.020f * (float)screen_width,
              row_y + (row_h - label_h) * 0.5f, row_w * 0.50f, label_h,
              label_h * 0.65f, EFOOTBALL_FONT_BOLD, verts + quads * 24);
          quads += competition_label_quads[row];
          const char *value = competition_frontend_item_value(row);
          if (value && value[0]) {
            competition_value_first_quad[row] = quads;
            competition_value_quads[row] = emit_efootball_fit_line(
                value, (int)strlen(value), value_x + 0.016f * (float)screen_width,
                row_y + (row_h - value_gh) * 0.5f, value_w * 0.90f, value_gh,
                value_gh * 0.60f, EFOOTBALL_FONT_STENCIL,
                verts + quads * 24);
            quads += competition_value_quads[row];
          }
        }
      }

      const float action_w = 0.260f * (float)screen_width;
      const float action_h = (competition_team_page ? 0.085f : 0.074f) *
                             (float)screen_height;
      const float action_x = (screen_width - action_w) * 0.5f;
      const float action_y = panel_y + panel_h +
                             (competition_team_page ? 0.035f : 0.015f) *
                                 (float)screen_height;
      competition_full_action_style =
          (RoundedRectStyle){action_w, action_h,
                             0.018f * (float)screen_height};
      competition_full_action_button_quad = quads;
      quads += emit_round_rect_quad(action_x, action_y, action_w, action_h,
                                    verts + quads * 24);
      competition_full_action_text_first_quad = quads;
      competition_full_action_text_quads = emit_efootball_centered_fit_line(
          "NEXT", 4, action_x + action_w * 0.5f,
          action_y + (action_h - (float)screen_height / 46.0f) * 0.5f,
          action_w * 0.86f, (float)screen_height / 46.0f,
          (float)screen_height / 64.0f, EFOOTBALL_FONT_BOLD,
          verts + quads * 24);
      quads += competition_full_action_text_quads;

      competition_title_first_quad = quads;
      competition_title_quads = emit_efootball_centered_fit_line(
          competition_frontend_title(),
          (int)strlen(competition_frontend_title()), panel_x + panel_w * 0.5f,
          panel_y + (header_h - title_h) * 0.5f, panel_w * 0.90f,
          title_h, title_h * 0.65f, EFOOTBALL_FONT_STENCIL,
          verts + quads * 24);
      quads += competition_title_quads;
    } else {
      uint32_t item_count = competition_display_item_count;
      if (item_count > 12u)
        item_count = 12u;
      const float available_h =
          panel_h - header_h - 0.170f * (float)screen_height;
      const float row_h = competition_tile_page
                              ? 0.115f * (float)screen_height
                              : fmaxf(0.045f * (float)screen_height,
                                      available_h /
                                              (float)(item_count ? item_count : 1u) -
                                          0.006f * (float)screen_height);
      const float row_gap = competition_tile_page
                                ? 0.020f * (float)screen_height
                                : 0.008f * (float)screen_height;
      const float value_x = body_x + body_w * 0.59f;
      const float value_w = body_w * 0.35f;
      competition_row_style =
          (RoundedRectStyle){body_w, row_h,
                             (competition_tile_page ? 0.014f : 0.010f) *
                                 (float)screen_height};
      competition_value_style =
          (RoundedRectStyle){value_w, row_h * 0.78f,
                             0.008f * (float)screen_height};
      for (uint32_t index = 0; index < item_count; index++) {
        const float y = body_top + (float)index * (row_h + row_gap);
        competition_row_quads[index] = quads;
        quads += emit_round_rect_quad(body_x, y, body_w, row_h,
                                      verts + quads * 24);
        if (index == competition_display_focus)
          competition_focus_quad = competition_row_quads[index];
        const char *label = competition_frontend_item_label(index);
        const char *value = competition_frontend_item_value(index);
        const float label_h = competition_tile_page
                                  ? (float)screen_height / 20.0f
                                  : subtitle_h;
        const float tile_focus_amount =
            competition_tile_page && index == competition_display_focus
                ? 1.0f
                : 0.0f;
        competition_label_first_quad[index] = quads;
        competition_label_quads[index] = emit_efootball_fit_line(
            label, (int)strlen(label),
            body_x + (competition_tile_page
                           ? (0.030f + 0.012f * tile_focus_amount)
                           : 0.020f) *
                         (float)screen_width,
            y + (row_h - label_h) * 0.5f, body_w * 0.50f, label_h,
            label_h * 0.65f,
            competition_tile_page ? EFOOTBALL_FONT_STENCIL
                                   : EFOOTBALL_FONT_BOLD,
            verts + quads * 24);
        quads += competition_label_quads[index];
        if (value && value[0]) {
          competition_value_plate_quads[index] = quads;
          quads += emit_round_rect_quad(
              value_x, y + (row_h - row_h * 0.78f) * 0.5f, value_w,
              row_h * 0.78f, verts + quads * 24);
          competition_value_first_quad[index] = quads;
          competition_value_quads[index] = emit_efootball_fit_line(
              value, (int)strlen(value), value_x + 0.016f * (float)screen_width,
              y + (row_h - label_h) * 0.5f, value_w * 0.90f, label_h,
              label_h * 0.60f, EFOOTBALL_FONT_STENCIL, verts + quads * 24);
          quads += competition_value_quads[index];
        } else {
          const float focus_amount = index == competition_display_focus
                                         ? 1.0f
                                         : 0.0f;
          const float icon_size =
              (0.078f + 0.006f * focus_amount) * (float)screen_height;
          const float icon_x = body_x + body_w -
                               0.022f * (float)screen_width - icon_size -
                               0.004f * (float)screen_width * focus_amount;
          const float icon_y = y + (row_h - icon_size) * 0.5f;
          const uint32_t icon_index = index % 4u;
          const float u0 = (icon_index & 1u) ? 0.5f : 0.0f;
          const float v0 = (icon_index >= 2u) ? 0.5f : 0.0f;
          competition_icon_quads[index] = quads;
          quads += emit_image_rect_uv(
              icon_x, icon_y, icon_size, icon_size, u0, v0, u0 + 0.5f,
              v0 + 0.5f, verts + quads * 24);
        }
      }
      const char *status = competition_frontend_status();
      if (status && status[0]) {
        competition_status_first_quad = quads;
        competition_status_quads = emit_efootball_centered_fit_line(
            status, (int)strlen(status), screen_width * 0.5f,
            panel_y + panel_h - 0.135f * (float)screen_height,
            panel_w * 0.88f, subtitle_h, subtitle_h * 0.65f,
            EFOOTBALL_FONT_BOLD, verts + quads * 24);
        quads += competition_status_quads;
      }
    }
    const int show_a = state != COMPETITION_FRONTEND_CUP_CHECKPOINT;
    const char *a_label = "SELECT";
    const char *b_label = bracket_page ? "TOP TO MENU" : "BACK";
    const float helper_icon_size = 0.034f * (float)screen_height;
    float helper_x = panel_x + 0.030f * (float)screen_width;
    if (show_a) {
      ADD_SWITCH_HELPER("A", helper_x + helper_icon_size * 0.5f,
                        helper_y, helper_icon_size);
      helper_x += helper_icon_size +
                  measure_efootball_line(a_label, (int)strlen(a_label),
                                         helper_text_gh,
                                         EFOOTBALL_FONT_BOLD) +
                  0.035f * (float)screen_width;
    }
    ADD_SWITCH_HELPER("B", helper_x + helper_icon_size * 0.5f, helper_y,
                      helper_icon_size);
    helper_x += helper_icon_size +
                measure_efootball_line(b_label, (int)strlen(b_label),
                                       helper_text_gh,
                                       EFOOTBALL_FONT_BOLD) +
                0.025f * (float)screen_width;
    float bracket_label_x = 0.0f;
    if (bracket_page) {
      const char *nav_label = "BRACKET";
      const float label_w = measure_efootball_line(
          nav_label, 7, helper_text_gh, EFOOTBALL_FONT_BOLD);
      bracket_label_x = panel_x + panel_w -
                        0.018f * (float)screen_width - label_w;
      const float right_key_x = bracket_label_x -
          0.010f * (float)screen_width - helper_icon_size * 0.5f;
      const float left_key_x = right_key_x - helper_icon_size -
          0.006f * (float)screen_width;
      /* SL/SR are the physical shoulder pair on a horizontal Joy-Con and
       * map to the same bracket paging bits as L/R on a full controller. */
      ADD_SWITCH_HELPER("SL", left_key_x, helper_y, helper_icon_size);
      ADD_SWITCH_HELPER("SR", right_key_x, helper_y, helper_icon_size);
    }
    competition_helper_first_quad = quads;
    if (show_a) {
      int n = emit_efootball_line(
          a_label, (int)strlen(a_label),
          panel_x + 0.030f * (float)screen_width + helper_icon_size +
              0.009f * (float)screen_width,
          helper_y - helper_text_gh * 0.5f, helper_text_gh,
          EFOOTBALL_FONT_BOLD, verts + quads * 24);
      competition_helper_quads += n;
      quads += n;
    }
    const float back_label_x =
        show_a ? panel_x + 0.030f * (float)screen_width + helper_icon_size +
                     measure_efootball_line(a_label, (int)strlen(a_label),
                                            helper_text_gh,
                                            EFOOTBALL_FONT_BOLD) +
                     0.070f * (float)screen_width
               : panel_x + 0.030f * (float)screen_width + helper_icon_size +
                     0.009f * (float)screen_width;
    int n = emit_efootball_line(
        b_label, (int)strlen(b_label), back_label_x,
        helper_y - helper_text_gh * 0.5f, helper_text_gh,
        EFOOTBALL_FONT_BOLD, verts + quads * 24);
    competition_helper_quads += n;
    quads += n;
    if (bracket_page) {
      n = emit_efootball_line(
          "BRACKET", 7, bracket_label_x,
          helper_y - helper_text_gh * 0.5f,
          helper_text_gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
      competition_helper_quads += n;
      quads += n;
    }
  } else if (custom_2p_team_selector) {
    // Exhibition, 2P, and Cup share the same atlas-backed carousel. Cup
    // renders one panel and supplies its league/team state through the same
    // selector accessors.
    const uint32_t selector_sides = cup_team_picker ? 1u : 2u;
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
    for (uint32_t pad = 0; pad < selector_sides; pad++)
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
    const uint32_t selector_active_side =
        custom_selector_exhibition
            ? pes_controller_2p_team_selector_active_side()
            : UINT32_MAX;

    custom_backdrop_quads = emit_image_rect(
        0.0f, 0.0f, (float)screen_width, (float)screen_height,
        verts + quads * 24);
    quads += custom_backdrop_quads;
    // Deliberately no side-container layer: backdrop -> header -> carousel.
    custom_panel_style = (RoundedRectStyle){0};
    custom_header_style = (RoundedRectStyle){0};
    for (uint32_t pad = 0; pad < selector_sides; pad++) {
      int header_quads = emit_rect(
          panel_x[pad], panel_y, panel_w, header_h, verts + quads * 24);
      custom_header_round_quads += header_quads;
      quads += header_quads;
    }
    // A plain rectangle keeps the five carousel blocks perfectly joined.
    custom_selected_style = (RoundedRectStyle){0};
    for (uint32_t pad = 0; pad < selector_sides; pad++) {
      custom_selected_quads += emit_rect(
          panel_x[pad] + row_x_inset, focused_y[pad], row_w, row_h,
          verts + quads * 24);
      quads++;
    }
    // The ready state gets its own full-width strip. It is deliberately not
    // painted over the badge card, matching the detached OK row in PES PC.
    for (uint32_t pad = 0; pad < selector_sides; pad++) {
      if (!pes_controller_2p_team_selector_confirmed(pad))
        continue;
      custom_confirm_bar_quads += emit_rect(
          panel_x[pad] + row_x_inset, focused_y[pad] + row_h, row_w,
          confirm_bar_h, verts + quads * 24);
      quads++;
    }
    for (uint32_t pad = 0; pad < selector_sides; pad++) {
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
    for (uint32_t pad = 0; pad < selector_sides; pad++) {
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
    for (uint32_t pad = 0; pad < selector_sides; pad++) {
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
    for (uint32_t pad = 0; pad < selector_sides; pad++) {
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
    for (uint32_t pad = 0; pad < selector_sides; pad++) {
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
    custom_action_key_bg_quads += 2;
    ADD_SWITCH_HELPER("B", 0.745f * (float)screen_width, helper_y,
                      helper_r * 2.0f);
    ADD_SWITCH_HELPER("A", 0.875f * (float)screen_width, helper_y,
                      helper_r * 2.0f);

    for (uint32_t pad = 0; pad < selector_sides; pad++) {
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
    for (uint32_t pad = 0; pad < selector_sides; pad++) {
      const float left = panel_x[pad];
      const uint32_t focus = pes_controller_2p_team_selector_focus(pad);
      const uint32_t scroll = pes_controller_2p_team_selector_scroll(pad);
      const uint32_t visible =
          pes_controller_2p_team_selector_visible_count(pad);
      const char *feature =
          pes_controller_2p_team_selector_label(pad, focus);
      int line_quads = 0;
      const int inactive_exhibition_side =
          custom_selector_exhibition && pad != selector_active_side &&
          !pes_controller_2p_team_selector_confirmed(pad);
      if (pes_controller_2p_team_selector_confirmed(pad) ||
          inactive_exhibition_side) {
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
    for (uint32_t pad = 0; pad < selector_sides; pad++) {
      if (custom_selector_exhibition &&
          pad != selector_active_side)
        continue;
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
    for (uint32_t pad = 0; pad < selector_sides; pad++) {
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
    for (uint32_t pad = 0; pad < selector_sides; pad++) {
      const float left = panel_x[pad];
      const char *player = cup_team_picker ? "P1" :
                           pad == 0 ? "HOME" : "AWAY";
      if (custom_selector_exhibition && pad == 1)
        player = "COM";
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
        helper_y - helper_text_gh * 0.5f, helper_text_gh,
        EFOOTBALL_FONT_BOLD,
        verts + quads * 24);
    custom_white_text_quads += line_quads;
    quads += line_quads;
    line_quads = emit_efootball_line(
        "CONFIRM", 7, 0.900f * (float)screen_width,
        helper_y - helper_text_gh * 0.5f, helper_text_gh,
        EFOOTBALL_FONT_BOLD,
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
    custom_backdrop_quads = emit_image_rect(
        0.0f, 0.0f, (float)screen_width, (float)screen_height,
        verts + quads * 24);
    quads += custom_backdrop_quads;
    if (custom_2p_transition_kind == PES_2P_TRANSITION_VS) {
      // The matchup card belongs exclusively to Kick Off.
      const float badge_size = 0.215f * (float)screen_height;
      // Center the complete badge/name group rather than centering the badge
      // alone; the old baseline left the matchup visibly high on screen.
      const float team_name_gh = (float)screen_height / 31.0f;
      const float name_gap = 0.030f * (float)screen_height;
      const float badge_y =
          ((float)screen_height - badge_size - name_gap - team_name_gh) * 0.5f;
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
        float team_gh = team_name_gh;
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
    } else {
      // Menu hand-offs use the artwork alone plus a compact animated loader.
      custom_white_text_first_quad = quads;
      const char *loading = "LOADING";
      const float loading_gh = (float)screen_height / 42.0f;
      const float loading_w = measure_efootball_line(
          loading, 7, loading_gh, EFOOTBALL_FONT_BOLD);
      const int loading_quads = emit_efootball_line(
          loading, 7,
          0.932f * (float)screen_width - loading_w,
          0.905f * (float)screen_height - loading_gh * 0.5f,
          loading_gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
      custom_white_text_quads += loading_quads;
      quads += loading_quads;
    }
      const float center_x = 0.956f * (float)screen_width;
      const float center_y = 0.905f * (float)screen_height;
      const float radius = 0.017f * (float)screen_height;
      const float thickness = 0.004f * (float)screen_height;
      const u64 frequency = armGetSystemTickFreq();
      const float phase = frequency
                              ? (float)(armGetSystemTick() % frequency) /
                                    (float)frequency * 6.2831853f
                              : 0.0f;
      custom_loading_spinner_first_quad = quads;
      for (uint32_t segment = 0; segment < 8; segment++) {
        const float a0 = phase + (float)segment * 0.43f;
        const float a1 = a0 + 0.25f;
        custom_loading_spinner_quads += emit_segment(
            center_x + cosf(a0) * radius,
            center_y + sinf(a0) * radius,
            center_x + cosf(a1) * radius,
            center_y + sinf(a1) * radius, thickness,
            verts + quads * 24);
        quads++;
      }
  } else if (custom_hub_settings_popup) {
    // Cup and match settings share one viewport, row geometry, value capsule,
    // arrow pair, and scrollbar. Only their data sources differ.
    const uint32_t item_count = cup_settings_popup
                                    ? competition_frontend_cup_setting_count()
                                : pause_settings_popup
                                    ? pes_controller_pause_settings_count()
                                    : pes_controller_custom_match_settings_count();
    const uint32_t max_visible = 5u;
    const uint32_t visible_count = item_count < max_visible ? item_count : max_visible;
    const uint32_t focus = cup_settings_popup
                               ? competition_frontend_cup_setting_focus()
                           : pause_settings_popup
                               ? pes_controller_pause_settings_focus()
                               : pes_controller_custom_match_settings_focus();
    uint32_t start_index = 0;
    if (focus >= visible_count) {
      start_index = focus - visible_count + 1u;
      if (start_index + visible_count > item_count)
        start_index = item_count - visible_count;
    }
    const uint32_t focus_slot = focus >= start_index ? focus - start_index : 0u;

    const float panel_x = 0.17f * (float)screen_width;
    const float panel_y = 0.080f * (float)screen_height;
    const float panel_w = 0.66f * (float)screen_width;
    const float panel_h = (cup_settings_popup
                               ? 0.115f + 0.030f + 0.108f *
                                     (float)(visible_count - 1u) + 0.082f +
                                     0.032f
                               : 0.770f) * (float)screen_height;
    const float panel_radius = 0.025f * (float)screen_height;
    const float header_h = 0.115f * (float)screen_height;
    const float row_x = panel_x + 0.040f * (float)screen_width;
    const float row_w = panel_w - 0.080f * (float)screen_width;
    const float row_y0 = panel_y + header_h + 0.030f * (float)screen_height;
    const float row_h = 0.082f * (float)screen_height;
    const float row_step = 0.108f * (float)screen_height;
    const float value_w = 0.205f * (float)screen_width;
    const float value_h = 0.058f * (float)screen_height;
    const float value_x = panel_x + panel_w - 0.070f * (float)screen_width - value_w;
    const float button_gh = helper_text_gh;
    const float key_r = (pause_settings_popup ? 0.0225f : 0.021f) * screen_height;
    const float key_gap = 0.017f * screen_height;
    const float action_label_w = measure_efootball_line("CHANGE", 6, button_gh, EFOOTBALL_FONT_BOLD);
    const float back_label_w = measure_efootball_line("BACK", 4, button_gh, EFOOTBALL_FONT_BOLD);
    const float action_key_x = pause_settings_popup
        ? 0.95f * screen_width - action_label_w - key_gap - key_r
        : 0.875f * screen_width;
    const float back_key_x = pause_settings_popup
        ? action_key_x - key_r * 2 - key_gap - back_label_w - 0.035f * screen_height
        : 0.745f * screen_width;
    const float key_y = (pause_settings_popup ? 0.9425f : 0.958f) * screen_height;

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
    if (focus < item_count) {
      custom_selected_quads = emit_round_rect_quad(
          row_x + selector_inset,
          row_y0 + row_step * (float)focus_slot + selector_inset,
          row_w - selector_inset * 2.0f,
          row_h - selector_inset * 2.0f,
          verts + quads * 24);
      quads += custom_selected_quads;
    }

    const float divider_h = fmaxf(1.8f, (float)screen_height / 450.0f);
    for (uint32_t slot = 0; slot + 1 < visible_count; slot++) {
      const float rule_y = floorf(row_y0 + row_step * (float)(slot + 1) -
                           (row_step - row_h) * 0.5f);
      custom_rule_quads += emit_rect(
          row_x, rule_y, row_w, divider_h,
          verts + quads * 24);
      quads++;
    }
    if (item_count > visible_count) {
      const float rail_x = panel_x + panel_w - 0.020f * (float)screen_width;
      const float rail_y = row_y0;
      const float rail_w = fmaxf(2.0f, 0.003f * (float)screen_width);
      const float rail_h = row_step * (float)(visible_count - 1) + row_h;
      custom_rule_quads += emit_rect(rail_x, rail_y, rail_w, rail_h, verts + quads * 24);
      quads++;
      const float thumb_h = rail_h * (float)visible_count / (float)item_count;
      const float thumb_y = rail_y + (rail_h - thumb_h) * (float)start_index / (float)(item_count - visible_count);
      custom_rule_quads += emit_rect(rail_x - 0.001f * (float)screen_width, thumb_y, rail_w + 0.002f * (float)screen_width, thumb_h, verts + quads * 24);
      quads++;
    }
    for (uint32_t slot = 0; slot < visible_count; slot++) {
      const float value_y = row_y0 + row_step * (float)slot +
                            (row_h - value_h) * 0.5f;
      custom_value_plate_style =
          (RoundedRectStyle){value_w, value_h, value_h * 0.5f};
      custom_value_plate_quads += emit_round_rect_quad(
          value_x, value_y, value_w, value_h, verts + quads * 24);
      quads++;
    }
    const float arrow_w = 0.007f * (float)screen_width;
    const float arrow_h = 0.012f * (float)screen_height;
    for (uint32_t slot = 0; slot < visible_count; slot++) {
      const float center_y = row_y0 + row_step * (float)slot + row_h * 0.5f;
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
    if (cup_settings_popup) {
      const float next_w = 0.260f * (float)screen_width;
      const float next_h = 0.070f * (float)screen_height;
      const float next_x = ((float)screen_width - next_w) * 0.5f;
      const float next_y = panel_y + panel_h + 0.035f * (float)screen_height;
      custom_action_button_style = (RoundedRectStyle){
          next_w, next_h, 0.018f * (float)screen_height};
      custom_action_button_quads = emit_round_rect_quad(
          next_x, next_y, next_w, next_h, verts + quads * 24);
      quads += custom_action_button_quads;
    }
    const float key_size = key_r * 2.0f;
    custom_action_key_bg_quads = 1;
    ADD_SWITCH_HELPER("A", action_key_x, key_y, key_size);
    custom_back_key_bg_quads = 1;
    ADD_SWITCH_HELPER("B", back_key_x, key_y, key_size);

    const float title_gh = (float)screen_height / 27.0f;
    const float label_gh = (float)screen_height / 42.0f;
    const float value_gh = (float)screen_height / 43.0f;
    custom_dark_text_first_quad = quads;
    int line_quads = 0;
    custom_focus_text_first_quad = quads;
    if (focus < item_count && focus_slot < visible_count) {
      const char *label = cup_settings_popup
                              ? competition_frontend_item_label(
                                    competition_frontend_cup_setting_row(focus))
                          : pause_settings_popup
                              ? pes_controller_pause_settings_label(focus)
                              : pes_controller_custom_match_settings_label(focus);
      line_quads = emit_efootball_line(
          label, (int)strlen(label), row_x + 0.020f * (float)screen_width,
          row_y0 + row_step * (float)focus_slot +
              (row_h - label_gh) * 0.5f,
          label_gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
      custom_focus_text_quads += line_quads;
      quads += line_quads;
    }
    custom_white_text_first_quad = quads;
    for (uint32_t slot = 0; slot < visible_count; slot++) {
      const uint32_t item = start_index + slot;
      if (item == focus)
        continue;
      const char *label = cup_settings_popup
                              ? competition_frontend_item_label(
                                    competition_frontend_cup_setting_row(item))
                          : pause_settings_popup
                              ? pes_controller_pause_settings_label(item)
                              : pes_controller_custom_match_settings_label(item);
      line_quads = emit_efootball_line(
          label, (int)strlen(label), row_x + 0.020f * (float)screen_width,
          row_y0 + row_step * (float)slot +
              (row_h - label_gh) * 0.5f,
          label_gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
      custom_white_text_quads += line_quads;
      quads += line_quads;
    }
    const char *title = cup_settings_popup
                            ? "CUP SETTINGS"
                        : pause_settings_popup
                            ? pes_controller_pause_settings_title()
                            : "GENERAL SETTINGS";
    const float title_w = measure_efootball_line(
        title, (int)strlen(title), title_gh, EFOOTBALL_FONT_BOLD);
    line_quads = emit_efootball_line(
        title, (int)strlen(title), panel_x + (panel_w - title_w) * 0.5f,
        panel_y + (header_h - title_gh) * 0.5f, title_gh,
        EFOOTBALL_FONT_BOLD, verts + quads * 24);
    custom_white_text_quads += line_quads;
    quads += line_quads;
    for (uint32_t slot = 0; slot < visible_count; slot++) {
      const uint32_t item = start_index + slot;
      const char *value = cup_settings_popup
                              ? competition_frontend_item_value(
                                    competition_frontend_cup_setting_row(item))
                          : pause_settings_popup
                              ? pes_controller_pause_settings_value(item)
                              : pes_controller_custom_match_settings_value(item);
      const float width = measure_efootball_line(
          value, (int)strlen(value), value_gh, EFOOTBALL_FONT_BOLD);
      const float value_y = row_y0 + row_step * (float)slot +
                            (row_h - value_gh) * 0.5f;
      line_quads = emit_efootball_line(
          value, (int)strlen(value), value_x + (value_w - width) * 0.5f,
          value_y, value_gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
      custom_white_text_quads += line_quads;
      quads += line_quads;
    }
    if (cup_settings_popup) {
      const float next_gh = (float)screen_height / 32.0f;
      const char *next = "NEXT";
      const float next_w = measure_efootball_line(
          next, 4, next_gh, EFOOTBALL_FONT_BOLD);
      line_quads = emit_efootball_line(
          next, 4, ((float)screen_width - next_w) * 0.5f,
          panel_y + panel_h + 0.035f * (float)screen_height +
              (0.070f * (float)screen_height - next_gh) * 0.5f,
          next_gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
      custom_white_text_quads += line_quads;
      quads += line_quads;
    }
    line_quads = emit_efootball_line(
        "CHANGE", 6, pause_settings_popup ? action_key_x + key_r + key_gap : 0.900f * screen_width,
        key_y - button_gh * 0.5f, button_gh,
        EFOOTBALL_FONT_BOLD, verts + quads * 24);
    custom_white_text_quads += line_quads;
    quads += line_quads;
    line_quads = emit_efootball_line(
        "BACK", 4, pause_settings_popup ? back_key_x + key_r + key_gap : 0.770f * screen_width,
        key_y - button_gh * 0.5f, button_gh,
        EFOOTBALL_FONT_BOLD, verts + quads * 24);
    custom_white_text_quads += line_quads;
    quads += line_quads;
    if (!pause_settings_popup) {
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
    }
  } else if (custom_hub_choice_page) {
    // Kits and Stadium use the same native-console settings language: one
    // modal card, a dark title band, white focused row, blue value capsule,
    // and arrows that remain completely inside the selected surface.
    const uint32_t row_count = custom_hub_kits_page ? 2u : 6u;
    const uint32_t raw_focus = pes_controller_2p_prematch_hub_page_focus();
    const uint32_t focus = raw_focus < row_count ? raw_focus : row_count - 1u;
    static const char *const stadium_labels[6] = {
        "STADIUM", "MATCH TIME", "WEATHER", "SEASON", "GRASS LENGTH", "PITCH CONDITION"};
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
    const float row_h = (custom_hub_kits_page ? 0.082f : 0.066f) * (float)screen_height;
    const float row_step = (custom_hub_kits_page ? 0.110f : 0.088f) * (float)screen_height;
    const float value_w = 0.205f * (float)screen_width;
    const float value_h = (custom_hub_kits_page ? 0.058f : 0.052f) * (float)screen_height;
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

    const float stadium_divider_h = fmaxf(1.8f, (float)screen_height / 450.0f);
    for (uint32_t row = 1; row < row_count; row++) {
      const float rule_y = floorf(row_y0 + row_step * (float)row - (row_step - row_h) * 0.5f);
      custom_rule_quads += emit_rect(
          row_x, rule_y, row_w, stadium_divider_h, verts + quads * 24);
      quads++;
    }
    for (uint32_t row = 0; row < row_count; row++) {
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
    for (uint32_t row = 0; row < row_count; row++) {
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
    custom_action_key_bg_quads = 1;
    ADD_SWITCH_HELPER("A", action_key_x, key_y, key_r * 2.0f);
    custom_back_key_bg_quads = 1;
    ADD_SWITCH_HELPER("B", back_key_x, key_y, key_r * 2.0f);
    const float title_gh = (float)screen_height / 27.0f;
    const float label_gh = (float)screen_height / 42.0f;
    const float value_gh = (float)screen_height / 43.0f;
    int line_quads = 0;
    custom_dark_text_first_quad = quads;
    custom_focus_text_first_quad = quads;
    const char *focused_label = custom_hub_kits_page
                                    ? (focus ? "AWAY KIT" : "HOME KIT")
                                    : stadium_labels[focus];
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
    for (uint32_t other_row = 0; other_row < row_count; other_row++) {
    if (other_row == focus) continue;
    const char *other_label = custom_hub_kits_page
                                  ? (other_row ? "AWAY KIT" : "HOME KIT")
                                  : stadium_labels[other_row];
    line_quads = emit_efootball_line(
        other_label, (int)strlen(other_label),
        row_x + 0.020f * (float)screen_width,
        row_y0 + row_step * (float)other_row +
            (row_h - label_gh) * 0.5f,
        label_gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
    custom_white_text_quads += line_quads;
    quads += line_quads;
    }
    const char *title = custom_hub_kits_page ? "KITS" : "STADIUM";
    const float title_w = measure_efootball_line(
        title, (int)strlen(title), title_gh, EFOOTBALL_FONT_BOLD);
    line_quads = emit_efootball_line(
        title, (int)strlen(title), panel_x + (panel_w - title_w) * 0.5f,
        panel_y + (header_h - title_gh) * 0.5f, title_gh,
        EFOOTBALL_FONT_BOLD, verts + quads * 24);
    custom_white_text_quads += line_quads;
    quads += line_quads;
    for (uint32_t row = 0; row < row_count; row++) {
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
      } else if (row == 1) {
        value = pes_controller_stadium_is_day() ? "DAY" : "NIGHT";
      } else if (row == 2) {
        static const char *const weather_options[2] = {"FINE", "CLOUDY"};
        value = weather_options[pes_controller_stadium_weather() & 1u];
      } else if (row == 3) {
        value = pes_controller_stadium_season() ? "WINTER" : "SUMMER";
      } else if (row == 4) {
        static const char *const turf_options[3] = {"SHORT", "NORMAL", "LONG"};
        value = turf_options[pes_controller_stadium_turf_length() % 3u];
      } else {
        static const char *const pitch_options[3] = {"DRY", "NORMAL", "WET"};
        value = pitch_options[pes_controller_stadium_pitch_condition() % 3u];
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
    const float button_gh = helper_text_gh;
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
    const uint32_t action_count =
        pes_controller_2p_prematch_hub_button_count();
    const float action_w =
        (0.93f * (float)screen_width -
         (float)(action_count - 1u) * action_gap) / (float)action_count;
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
         action < action_count; action++) {
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
        const char *hint = side == page_side ? "CHANGE KIT"
                                             : "SELECT TEAM";
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
      const char *stadium_hint = "SELECT STADIUM";
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
         action < action_count; action++) {
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
    if (hub_focus < action_count) {
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
    if (!custom_video_settings_popup) {
      custom_rule_quads += emit_rect(
          panel_x + 0.04f * (float)screen_width, footer_y,
          panel_w - 0.08f * (float)screen_width,
          (float)screen_height / 600.0f, verts + quads * 24);
      quads++;
    }
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
    custom_back_key_bg_quads = 1;
    ADD_SWITCH_HELPER("B", back_key_x, back_key_y,
                      back_key_radius * 2.0f);
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
    const float helper_gw =
        helper_text_gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
    custom_white_text_quads = emit_line(
        "BACK", 4, back_key_x + 0.027f * (float)screen_width,
        back_button_y + (back_button_h - helper_text_gh) * 0.5f,
        helper_gw, helper_text_gh,
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
    const float back_key_radius = 0.020f * (float)screen_height;
    const float back_key_gap = 0.010f * (float)screen_width;
    const float back_label_w = measure_efootball_line(
        "BACK", 4, helper_text_gh, EFOOTBALL_FONT_BOLD);
    const float back_key_x = 0.955f * (float)screen_width - back_label_w -
                             back_key_gap - back_key_radius;
    const float back_key_y = 0.9425f * (float)screen_height;

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
    custom_back_key_bg_quads = 1;
    ADD_SWITCH_HELPER("B", back_key_x, back_key_y,
                      back_key_radius * 2.0f);

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

    const float button_gh = helper_text_gh;
    custom_white_text_first_quad = quads;
    custom_white_text_quads = emit_efootball_line(
        "BACK", 4, back_key_x + back_key_radius + back_key_gap,
        back_key_y - button_gh * 0.5f, button_gh,
        EFOOTBALL_FONT_BOLD, verts + quads * 24);
    quads += custom_white_text_quads;
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
    custom_action_key_bg_quads = 1;
    ADD_SWITCH_HELPER("A", action_key_x, key_y, key_radius * 2.0f);
    custom_back_key_bg_quads = 1;
    ADD_SWITCH_HELPER("B", back_key_x, key_y, key_radius * 2.0f);

    custom_dark_text_first_quad = quads;
    const float title_gh = (float)screen_height / 30.0f;
    const float title_gw =
        title_gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
    const float text_gh = (float)screen_height / 38.0f;
    const float text_gw =
        text_gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
    const float helper_gw =
        helper_text_gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
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
        action_button_y + (button_h - helper_text_gh) * 0.5f,
        helper_gw, helper_text_gh,
        verts + quads * 24);
    custom_white_text_quads += line_quads;
    quads += line_quads;
    line_quads = emit_line(
        "BACK", 4, back_key_x + 0.026f * (float)screen_width,
        action_button_y + (button_h - helper_text_gh) * 0.5f,
        helper_gw, helper_text_gh,
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
    const uint32_t item_count = custom_video_settings_popup
                                    ? 2u
                                    : pes_controller_custom_match_settings_count();
    const float panel_x = 0.17f *
                          (float)screen_width;
    const float panel_y = (custom_video_settings_popup ? 0.095f : 0.08f) *
                          (float)screen_height;
    const float panel_w = 0.66f *
                          (float)screen_width;
    const float panel_h = (custom_video_settings_popup ? 0.70f : 0.84f) *
                          (float)screen_height;
    const float panel_radius = 0.025f * (float)screen_height;
    const float header_h = (custom_video_settings_popup ? 0.125f : 0.115f) *
                           (float)screen_height;
    const float footer_y =
        (custom_video_settings_popup ? 0.0f : 0.785f) *
        (float)screen_height;
    const float row_x = panel_x + 0.030f * (float)screen_width;
    const float row_w = panel_w - 0.060f * (float)screen_width;
    const float row_y0 =
        (custom_video_settings_popup ? 0.265f : PES_MATCH_SETTINGS_ROW_Y) *
        (float)screen_height;
    const float row_h =
        (custom_video_settings_popup ? 0.078f : 0.090f) *
        (float)screen_height;
    const float row_step =
        (custom_video_settings_popup ? 0.105f : PES_MATCH_SETTINGS_ROW_STEP) *
        (float)screen_height;
    const float selector_inset = 0.006f * (float)screen_height;
    const float value_w = (custom_video_settings_popup ? 0.205f : 0.200f) *
                          (float)screen_width;
    const float value_h = (custom_video_settings_popup ? 0.058f : 0.065f) *
                          (float)screen_height;
    const float value_x =
        panel_x + panel_w -
        (custom_video_settings_popup ? 0.070f : 0.035f) *
            (float)screen_width - value_w;
    const uint32_t focus = custom_video_settings_popup
                               ? pes_controller_custom_video_settings_focus()
                               : pes_controller_custom_match_settings_focus();
    const float button_margin =
        (custom_video_settings_popup ? 0.025f : 0.035f) *
        (float)screen_width;
    const float action_button_x = panel_x + button_margin;
    const float action_button_y = 0.823f * (float)screen_height;
    const float action_button_w = 0.250f * (float)screen_width;
    const float apply_button_x =
        (float)screen_width * 0.5f - action_button_w * 0.5f;
    const float back_button_x =
        panel_x + panel_w - button_margin - action_button_w;
    const float back_button_w = action_button_w;
    const float button_h = 0.060f * (float)screen_height;
    const float key_radius = (custom_video_settings_popup ? 0.0225f : 0.019f) *
                             (float)screen_height;
    const float key_text_gap = 0.010f * (float)screen_width;
    const float key_group_gap = 0.030f * (float)screen_width;
    const float helper_char_w =
        helper_text_gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
    const float change_label_w = 6.0f * helper_char_w;
    const float apply_label_w = 5.0f * helper_char_w;
    const float back_label_w = 4.0f * helper_char_w;
    const float key_size = key_radius * 2.0f;
    const float video_helper_total = key_size * 3.0f +
        key_text_gap * 3.0f + change_label_w + apply_label_w + back_label_w +
        key_group_gap * 2.0f;
    float video_helper_x = 0.955f * (float)screen_width -
                           video_helper_total;
    const float action_key_x = custom_video_settings_popup
        ? video_helper_x + key_radius
        : action_button_x + 0.030f * (float)screen_width;
    video_helper_x += key_size + key_text_gap + change_label_w +
                      key_group_gap;
    const float apply_key_x = custom_video_settings_popup
        ? video_helper_x + key_radius
        : apply_button_x + 0.030f * (float)screen_width;
    video_helper_x += key_size + key_text_gap + apply_label_w +
                      key_group_gap;
    const float back_key_x = custom_video_settings_popup
        ? video_helper_x + key_radius
        : back_button_x + 0.030f * (float)screen_width;
    const float key_y = custom_video_settings_popup
        ? 0.9425f * (float)screen_height
        : action_button_y + button_h * 0.5f;

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
    if (!custom_video_settings_popup) {
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
    }
    custom_action_key_bg_quads = 1;
    ADD_SWITCH_HELPER("A", action_key_x, key_y, key_radius * 2.0f);
    if (custom_video_settings_popup) {
      custom_action_key_bg_quads++;
      ADD_SWITCH_HELPER("X", apply_key_x, key_y, key_radius * 2.0f);
    }
    custom_back_key_bg_quads = 1;
    ADD_SWITCH_HELPER("B", back_key_x, key_y, key_radius * 2.0f);

    custom_dark_text_first_quad = quads;
    const float title_gh = (float)screen_height / 30.0f;
    const float title_gw =
        title_gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
    const float text_gh = (float)screen_height / 36.0f;
    const float text_gw =
        text_gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
    const float helper_gw =
        helper_text_gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
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
        "CHANGE", 6,
        custom_video_settings_popup
            ? action_key_x + key_radius + key_text_gap
            : action_key_x + 0.026f * (float)screen_width,
        custom_video_settings_popup
            ? key_y - helper_text_gh * 0.5f
            : action_button_y + (button_h - helper_text_gh) * 0.5f,
        helper_gw, helper_text_gh,
        verts + quads * 24);
    custom_white_text_quads += line_quads;
    quads += line_quads;
    if (custom_video_settings_popup) {
      line_quads = emit_line(
          "APPLY", 5, apply_key_x + key_radius + key_text_gap,
          key_y - helper_text_gh * 0.5f,
          helper_gw, helper_text_gh,
          verts + quads * 24);
      custom_white_text_quads += line_quads;
      quads += line_quads;
    }
    line_quads = emit_line(
        "BACK", 4,
        custom_video_settings_popup
            ? back_key_x + key_radius + key_text_gap
            : back_key_x + 0.026f * (float)screen_width,
        custom_video_settings_popup
            ? key_y - helper_text_gh * 0.5f
            : action_button_y + (button_h - helper_text_gh) * 0.5f,
        helper_gw, helper_text_gh,
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
    const char *helper_key = back_only_cursor ? "B" : "A";
    ADD_SWITCH_HELPER(helper_key, helper_x, helper_y,
                      helper_radius * 2.0f);

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

  } else if (tutorial_play_active && !custom_2p_transition &&
             !pause_settings_popup) {
    // The stock tutorial already draws the blue Play footer. Add only its
    // missing controller key; the action itself is dispatched natively on the
    // tutorial UI thread.
    const float helper_x = 0.835f * (float)screen_width;
    const float helper_y = 0.944f * (float)screen_height;
    const float helper_radius = 0.019f * (float)screen_height;
    ADD_SWITCH_HELPER("A", helper_x, helper_y, helper_radius * 2.0f);
  }
  const int text_first_quad = quads;
#if defined(DEBUG_LOG) && DEBUG_LOG
  if (native_lab && !custom_popup) {
    const uint32_t status = native_debug.status;
    char label[192];
    snprintf(label, sizeof(label),
#if PES_EXPERIMENT_INTER_MIAMI
             "NATIVE 2P SETPLAY V8.17.17 IM27 VTOUCH:OFF H:%X P:%X O:%X R:%X U:%X B:%X PR:%X "
#else
             "NATIVE 2P SETPLAY V8.17.17 VTOUCH:OFF H:%X P:%X O:%X R:%X U:%X B:%X PR:%X "
#endif
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
                 "LS=CURL + HEIGHT   RS=CAMERA / AIM");
      else if (native_debug.context == PES_SETPLAY_THROW_IN)
        snprintf(debug_line, sizeof(debug_line), "LS=THROW DIRECTION/AIM");
      else
        snprintf(debug_line, sizeof(debug_line),
                 "LS=CURL + HEIGHT   RS=CAMERA / AIM");
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
#endif
  if (config.show_fps && fps.text[0]) {
    const float gh = (float)screen_height / 30.0f;
    const float gw = gh * (float)FONT_CELL_W / (float)FONT_CELL_H;
    quads += emit_line(fps.text, (int)strlen(fps.text), 10.0f, 8.0f,
                       gw, gh, verts + quads * 24);
  }
  const int generic_text_end_quad = quads;
  if (startup_transition) {
    startup_transition_background_quad = quads;
    quads += emit_image_rect(0, 0, screen_width, screen_height,
                             verts + quads * 24);
    const float center_x = 0.956f * (float)screen_width;
    const float center_y = 0.905f * (float)screen_height;
    const float radius = 0.017f * (float)screen_height;
    const float thickness = 0.004f * (float)screen_height;
    const u64 frequency = armGetSystemTickFreq();
    const float phase = frequency
                            ? (float)(armGetSystemTick() % frequency) /
                                  (float)frequency * 6.2831853f
                            : 0.0f;
    startup_transition_spinner_first_quad = quads;
    for (uint32_t segment = 0; segment < 8; segment++) {
      const float a0 = phase + (float)segment * 0.43f;
      const float a1 = a0 + 0.25f;
      startup_transition_spinner_quads += emit_segment(
          center_x + cosf(a0) * radius,
          center_y + sinf(a0) * radius,
          center_x + cosf(a1) * radius,
          center_y + sinf(a1) * radius, thickness,
          verts + quads * 24);
      quads++;
    }
    const char *loading = "LOADING";
    const float loading_h = (float)screen_height / 42.0f;
    const float loading_w = measure_efootball_line(
        loading, 7, loading_h, EFOOTBALL_FONT_BOLD);
    startup_transition_text_first_quad = quads;
    startup_transition_text_quads = emit_efootball_line(
        loading, 7, 0.932f * (float)screen_width - loading_w,
        center_y - loading_h * 0.5f, loading_h,
        EFOOTBALL_FONT_BOLD, verts + quads * 24);
    quads += startup_transition_text_quads;
  }
  if (start_prompt) {
    title_background_quad = quads;
    quads += emit_image_rect(0, 0, screen_width, screen_height,
                             verts + quads * 24);

    // Reuse the tile menu's proven HD portrait size on the title page's
    // intentionally quiet left side.
    const float portrait_w = 0.425f * (float)screen_width;
    const float portrait_h = 1.010f * (float)screen_height;
    title_portrait_quad = quads;
    quads += emit_image_rect(0.030f * (float)screen_width,
        0.035f * (float)screen_height, portrait_w, portrait_h,
        verts + quads * 24);

    // Treat the logo, prompt and credit as one vertically centered group on
    // the otherwise quiet right side of the title page.
    const float brand_w = 0.350f * (float)screen_width;
    const float brand_h = brand_w * (496.0f / 1310.0f);
    title_brand_quad = quads;
    quads += emit_image_rect(0.715f * (float)screen_width - brand_w * 0.5f,
                             0.360f * (float)screen_height - brand_h * 0.5f,
                             brand_w, brand_h, verts + quads * 24);

    const float prompt_h = (float)screen_height / 36.0f;
    const float prompt_icon = 0.045f * (float)screen_height;
    const float prompt_gap = 0.011f * (float)screen_width;
    const float press_w = measure_efootball_line(
        "PRESS", 5, prompt_h, EFOOTBALL_FONT_BOLD);
    const float start_w = measure_efootball_line(
        "TO START", 8, prompt_h, EFOOTBALL_FONT_BOLD);
    const float prompt_w = press_w + prompt_gap + prompt_icon +
                           prompt_gap + start_w;
    const float prompt_x = 0.715f * (float)screen_width - prompt_w * 0.5f;
    const float prompt_center_y = 0.620f * (float)screen_height;
    title_button_a_quad = quads;
    quads += emit_image_rect(prompt_x + press_w + prompt_gap,
                             prompt_center_y - prompt_icon * 0.5f,
                             prompt_icon, prompt_icon,
                             verts + quads * 24);
    title_prompt_text_first_quad = quads;
    title_prompt_text_quads += emit_efootball_line(
        "PRESS", 5, prompt_x, prompt_center_y - prompt_h * 0.5f,
        prompt_h, EFOOTBALL_FONT_BOLD, verts + quads * 24);
    quads += title_prompt_text_quads;
    const int to_start_quads = emit_efootball_line(
        "TO START", 8,
        prompt_x + press_w + prompt_gap + prompt_icon + prompt_gap,
        prompt_center_y - prompt_h * 0.5f, prompt_h,
        EFOOTBALL_FONT_BOLD, verts + quads * 24);
    quads += to_start_quads;
    title_prompt_text_quads += to_start_quads;

    const char *footer = "ANDROSWITCH PROJECT 2026";
    const int footer_len = (int)strlen(footer);
    const float footer_h = (float)screen_height / 51.0f;
    const float footer_w = measure_efootball_line(
        footer, footer_len, footer_h, EFOOTBALL_FONT_BOLD);
    title_footer_first_quad = quads;
    title_footer_quads = emit_efootball_line(
        footer, footer_len, 0.715f * (float)screen_width - footer_w * 0.5f,
        0.770f * (float)screen_height, footer_h,
        EFOOTBALL_FONT_BOLD, verts + quads * 24);
    quads += title_footer_quads;
  }
  if (cinematic_helper_active) {
    const float helper_radius = 0.022f * (float)screen_height;
    const float skip_y = 0.865f * (float)screen_height;
    const float celebrate_y = 0.945f * (float)screen_height;
    const float generic_y = 0.925f * (float)screen_height;
    const uint32_t profile0 = android_controller_profile(0);
    const uint32_t profile1 = android_controller_profile(1);
    const char *skip_key0 =
        profile0 == PES_CONTROLLER_PROFILE_SINGLE_LEFT
            ? "LEFT"
            : (profile0 == PES_CONTROLLER_PROFILE_SINGLE_RIGHT ? "A" : "B");
    const char *skip_key1 =
        profile1 == PES_CONTROLLER_PROFILE_SINGLE_LEFT
            ? "LEFT"
            : (profile1 == PES_CONTROLLER_PROFILE_SINGLE_RIGHT ? "A" : "B");
    const char *celebrate_key0 =
        profile0 == PES_CONTROLLER_PROFILE_SINGLE_LEFT
            ? "DOWN"
            : (profile0 == PES_CONTROLLER_PROFILE_SINGLE_RIGHT ? "X" : "A");
    const char *celebrate_key1 =
        profile1 == PES_CONTROLLER_PROFILE_SINGLE_LEFT
            ? "DOWN"
            : (profile1 == PES_CONTROLLER_PROFILE_SINGLE_RIGHT ? "X" : "A");
    const int horizontal_dual = cinematic_goal_two_player &&
        (profile0 != PES_CONTROLLER_PROFILE_FULL ||
         profile1 != PES_CONTROLLER_PROFILE_FULL) &&
        (strcmp(skip_key0, skip_key1) ||
         strcmp(celebrate_key0, celebrate_key1));
    const float first_x =
        (horizontal_dual ? 0.785f : 0.825f) * (float)screen_width;
    const float second_x = 0.825f * (float)screen_width;
    ADD_SWITCH_HELPER(skip_key0, first_x,
                      cinematic_goal_actions ? skip_y : generic_y,
                      helper_radius * 2.0f);
    if (horizontal_dual)
      ADD_SWITCH_HELPER(skip_key1, second_x,
                        cinematic_goal_actions ? skip_y : generic_y,
                        helper_radius * 2.0f);
    if (cinematic_goal_actions) {
      ADD_SWITCH_HELPER(celebrate_key0, first_x, celebrate_y,
                        helper_radius * 2.0f);
      if (horizontal_dual)
        ADD_SWITCH_HELPER(celebrate_key1, second_x, celebrate_y,
                          helper_radius * 2.0f);
    }

    const float gh = helper_text_gh;
    cinematic_helper_text_first_quad = quads;
    if (horizontal_dual) {
      const float slash_x = first_x + helper_radius * 1.42f;
      int slash_quads = emit_efootball_line(
          "/", 1, slash_x,
          (cinematic_goal_actions ? skip_y : generic_y) - gh * 0.5f,
          gh, EFOOTBALL_FONT_REGULAR, verts + quads * 24);
      cinematic_helper_text_quads += slash_quads;
      quads += slash_quads;
      if (cinematic_goal_actions) {
        slash_quads = emit_efootball_line(
            "/", 1, slash_x, celebrate_y - gh * 0.5f,
            gh, EFOOTBALL_FONT_REGULAR, verts + quads * 24);
        cinematic_helper_text_quads += slash_quads;
        quads += slash_quads;
      }
    }
    const float label_x = (horizontal_dual ? second_x : first_x) +
                          helper_radius * 1.55f;
    int label_quads = emit_efootball_line(
        "SKIP", 4, label_x,
        (cinematic_goal_actions ? skip_y : generic_y) - gh * 0.5f,
        gh, EFOOTBALL_FONT_REGULAR, verts + quads * 24);
    cinematic_helper_text_quads += label_quads;
    quads += label_quads;
    if (cinematic_goal_actions) {
      const char *celebrate_label = "GOAL CELEBRATION";
      label_quads = emit_efootball_line(
          celebrate_label, (int)strlen(celebrate_label), label_x,
          celebrate_y - gh * 0.5f, gh, EFOOTBALL_FONT_REGULAR,
          verts + quads * 24);
      cinematic_helper_text_quads += label_quads;
      quads += label_quads;
    }
  }
  const char *setplay_keys[5] = {NULL, NULL, NULL, NULL, NULL};
  const char *setplay_labels[5] = {NULL, NULL, NULL, NULL, NULL};
  const char *setplay_camera_key = single_joy_setplay ? "SR+LS" : "RS";
  const char *setplay_camera_label = single_joy_setplay ? "HOLD: CAMERA / AIM" : "CAMERA / AIM";
  unsigned int setplay_helper_count = 0;
  const int offside_free_kick =
      setplay_context == PES_SETPLAY_FREE_KICK &&
      pes_controller_free_kick_offside();
  const int native_far_free_kick =
      native_setplay_debug && setplay_context == PES_SETPLAY_FREE_KICK &&
      (native_debug.stock_mask &
       (PES_NATIVE_LAB_STOCK_FREEKICK_TACTICS |
        PES_NATIVE_LAB_STOCK_FREEKICK_POSITION));
  if (offside_free_kick) {
    // Offside restarts deliberately have no helper. The same free-kick page
    // is reused by the game, but its native FoulKind is authoritative.
    setplay_helper_count = 0;
  } else if (native_setplay_debug &&
      setplay_context == PES_SETPLAY_GOAL_KICK) {
    setplay_keys[0] = "L";
    setplay_labels[0] = "POSITION SHIFT";
    setplay_helper_count = 1;
  } else if (native_setplay_debug &&
             setplay_context == PES_SETPLAY_CORNER) {
    setplay_keys[0] = "L";
    setplay_labels[0] = "SHORT CORNER";
    setplay_keys[1] = setplay_taker_key;
    setplay_labels[1] = "SET PIECE TAKER";
    setplay_keys[2] = "LS";
    setplay_labels[2] = "HEIGHT / CURL";
    setplay_keys[3] = setplay_camera_key;
    setplay_labels[3] = setplay_camera_label;
    setplay_helper_count = 4;
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
    setplay_labels[1] = "HEIGHT / CURL";
    setplay_keys[2] = setplay_camera_key;
    setplay_labels[2] = setplay_camera_label;
    setplay_helper_count = 3;
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
    setplay_keys[0] = setplay_taker_key;
    setplay_labels[0] = "SET PIECE TAKER";
    setplay_keys[1] = "X";
    setplay_labels[1] = "SHORT CORNER";
    setplay_keys[2] = "Y";
    setplay_labels[2] = "SWITCH VIEW";
    setplay_helper_count = 3;
  } else if (!native_setplay_debug && !native_lab &&
             setplay_context == PES_SETPLAY_FREE_KICK) {
    setplay_keys[0] = setplay_taker_key;
    setplay_labels[0] = "SET PIECE TAKER";
    setplay_helper_count = 1;
  } else if (setplay_context == PES_SETPLAY_THROW_IN) {
    setplay_keys[0] = setplay_taker_key;
    setplay_labels[0] = "SET THROWER";
    setplay_helper_count = 1;
  } else if (setplay_options && !native_lab) {
    // Unknown context is not evidence of a goal kick. A raw PositionShift
    // bit also occurs at long free kicks; never invent a Y helper from it.
    if ((setplay_options & PES_SETPLAY_OPTION_KICKER) &&
        setplay_helper_count < 3) {
      setplay_keys[setplay_helper_count] = setplay_taker_key;
      setplay_labels[setplay_helper_count++] = "SET PIECE TAKER";
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
      setplay_keys[setplay_helper_count] = "LS+Y";
      setplay_labels[setplay_helper_count++] = "P1 KICKER";
    } else if (penalty_role_p1 == PES_PENALTY_GOALKEEPER) {
      setplay_keys[setplay_helper_count] = "LS";
      setplay_labels[setplay_helper_count++] = "P1 GOALKEEPER";
    }
    if (penalty_two_player && penalty_role_p2 == PES_PENALTY_KICKER) {
      setplay_keys[setplay_helper_count] = "LS+Y";
      setplay_labels[setplay_helper_count++] = "P2 KICKER";
    } else if (penalty_two_player &&
               penalty_role_p2 == PES_PENALTY_GOALKEEPER) {
      setplay_keys[setplay_helper_count] = "LS";
      setplay_labels[setplay_helper_count++] = "P2 GOALKEEPER";
    }
  }
  // One sprite group plus a measured label per row. Rail-button chords use
  // real SL/SR art, not the old text-only L1/R1 badges.
  if (setplay_helper_count) {
    const float size = screen_height * 0.045f;
    const float gh = helper_text_gh;
    const float gap = screen_height * 0.017f;
    const float step = screen_height * 0.066f;
    int has_chord = 0;
    for (uint32_t i = 0; i < setplay_helper_count; ++i)
      has_chord |= strchr(setplay_keys[i], '+') != NULL;
    const float group_w = size * (has_chord ? 2.65f : 1.0f);
    float label_w = 0;
    for (uint32_t i = 0; i < setplay_helper_count; ++i)
      label_w = fmaxf(label_w, measure_efootball_line(setplay_labels[i],
          (int)strlen(setplay_labels[i]), gh, EFOOTBALL_FONT_BOLD));
    const float x = 0.955f * screen_width - label_w - gap - group_w;
    const float start_y = 0.925f * screen_height -
                          (setplay_helper_count - 1u) * step;
    for (uint32_t i = 0; i < setplay_helper_count; ++i) {
      const int rail = !strcmp(setplay_keys[i], "L1+R1");
      const int kick = !strcmp(setplay_keys[i], "LS+Y");
      const int camera = !strcmp(setplay_keys[i], "SR+LS");
      const char *first = rail ? "SL" : camera ? "SR" : kick ? "LS" : setplay_keys[i];
      switch_helper_quads[switch_helper_count] = quads;
      switch_helper_textures[switch_helper_count++] = switch_button_texture(first);
      quads += emit_image_rect(x, start_y + i * step - size * 0.5f,
                                size, size, verts + quads * 24);
      if (rail || kick || camera) {
        switch_helper_quads[switch_helper_count] = quads;
        switch_helper_textures[switch_helper_count++] =
            switch_button_texture(rail ? "SR" : camera ? "LS" : "Y");
        quads += emit_image_rect(x + group_w - size,
            start_y + i * step - size * 0.5f, size, size, verts + quads * 24);
      }
    }
    setplay_helper_text_first_quad = quads;
    for (uint32_t i = 0; i < setplay_helper_count; ++i) {
      const float y = start_y + i * step - gh * 0.5f;
      if (strchr(setplay_keys[i], '+')) {
        const float plus_w = measure_efootball_line("+", 1, gh, EFOOTBALL_FONT_BOLD);
        int n = emit_efootball_line("+", 1, x + (group_w - plus_w) * 0.5f,
                                    y, gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
        quads += n; setplay_helper_text_quads += n;
      }
      const int n = emit_efootball_line(setplay_labels[i], (int)strlen(setplay_labels[i]),
          x + group_w + gap, y, gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
      quads += n; setplay_helper_text_quads += n;
    }
  }
  const int setplay_gauge_supported =
      (setplay_context == PES_SETPLAY_CORNER ||
       setplay_context == PES_SETPLAY_FREE_KICK ||
       setplay_context == PES_SETPLAY_GOAL_KICK);

  const int match_active =
      !pes_controller_replay_active() &&
      !pes_controller_goal_demo_active() &&
      !pes_controller_cinematic_skip_active() &&
      !pes_controller_fix_demo_skip_active() &&
      !pes_controller_pause_skin_active() &&
      !pes_controller_pause_transition() &&
      !pes_controller_match_result_skin() &&
      !pes_controller_match_result_transition() &&
      pes_controller_virtual_cursor_context() == PES_VIRTUAL_CURSOR_NONE;

  const int gauge_allowed =
      match_active &&
      (pes_controller_match_hud_inplay() || setplay_gauge_supported);

  if (native_lab && !custom_popup && !modal_match_frontend &&
      !tutorial_play_active && !custom_2p_transition &&
      gauge_allowed && (native_debug.gauge_active_mask & 3u)) {
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
          ((native_debug.gauge_anchor_valid_mask & (1u << pad)) != 0) ||
          setplay_gauge_supported;
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
      const int has_anchor =
          (native_debug.gauge_anchor_valid_mask & (1u << pad)) != 0;
      if (has_anchor) {
        bar_x = (float)anchor_x_milli / 1000.0f - bar_w * 0.5f;
        bar_y = (float)anchor_y_milli / 1000.0f +
                0.007f * (float)screen_height;
      } else {
        bar_x = (float)screen_width * 0.5f - bar_w * 0.5f;
        bar_y = (float)screen_height * 0.82f;
      }
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
  if (pause_skin) {
    pause_background = quads;
    quads += emit_image_rect(0, 0, screen_width, screen_height, verts + quads * 24);
    pause_badges = quads;
    const float badge = screen_height * 0.16f;
    for (uint32_t side = 0; side < 2; ++side)
      quads += emit_badge(pes_controller_2p_prematch_hub_badge(side),
          (side ? 0.92f : 0.08f) * screen_width - badge * 0.5f,
          screen_height * 0.065f, badge, badge, verts + quads * 24);
    pause_header = quads;
    const char *heading = "PAUSE MENU";
    float gh = screen_height / 30.0f;
    quads += emit_efootball_line(heading, (int)strlen(heading),
        (screen_width - measure_efootball_line(heading, (int)strlen(heading), gh, EFOOTBALL_FONT_STENCIL)) * 0.5f,
        screen_height * 0.026f, gh, EFOOTBALL_FONT_STENCIL, verts + quads * 24);
    for (uint32_t side = 0; side < 2; ++side) {
      const char *team = pes_controller_2p_prematch_hub_team_name(side);
      gh = screen_height / 34.0f;
      float tw = measure_efootball_line(team, (int)strlen(team), gh, EFOOTBALL_FONT_STENCIL);
      if (tw > screen_width * 0.25f) { gh *= screen_width * 0.25f / tw; tw = screen_width * 0.25f; }
      quads += emit_efootball_line(team, (int)strlen(team),
          (side ? 0.735f : 0.265f) * screen_width - tw * 0.5f,
          screen_height * 0.125f, gh, EFOOTBALL_FONT_STENCIL, verts + quads * 24);
      uint32_t score; char score_text[16];
      if (pes_controller_pause_score(side, &score)) snprintf(score_text, sizeof(score_text), "%u", score);
      else snprintf(score_text, sizeof(score_text), "--");
      gh = screen_height / 12.0f;
      tw = measure_efootball_line(score_text, (int)strlen(score_text), gh, EFOOTBALL_FONT_BOLD);
      quads += emit_efootball_line(score_text, (int)strlen(score_text),
          (side ? 0.55f : 0.45f) * screen_width - tw * 0.5f,
          screen_height * 0.10f, gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
    }
    pause_header_count = quads - pause_header;
    const float w = 0.231f * screen_width, h = 0.105f * screen_height;
    pause_skin_style = (RoundedRectStyle){w, h, 0.018f * screen_height};
    static const char *const labels[] = {
        "GAME PLAN", "GENERAL SETTINGS", "CAMERA SETTINGS", "TOP MENU"};
    for (int i = 0; i < 4; ++i) {
      const float x = (0.020f + i * 0.243f) * screen_width;
      const float y = 0.780f * screen_height;
      if (pes_controller_pause_skin_focus() == (uint32_t)i)
        pause_skin_focus = i;
      else if (gameplan_cursor && gameplan_cursor_x * screen_width >= x &&
          gameplan_cursor_x * screen_width <= x + w &&
          gameplan_cursor_y * screen_height >= y && gameplan_cursor_y * screen_height <= y + h)
        pause_skin_focus = i;
      pause_skin_cards[i] = quads;
      quads += emit_round_rect_quad(x, y, w, h, verts + quads * 24);
    }
    pause_stats_panel = quads;
    quads += emit_round_rect_quad(0.18f * screen_width, 0.265f * screen_height,
        0.64f * screen_width, 0.465f * screen_height, verts + quads * 24);
    pause_skin_text = quads;
    for (int i = 0; i < 4; ++i) {
      const float x = (0.020f + i * 0.243f) * screen_width;
      const float y = 0.780f * screen_height;
      float gh = screen_height / 31.0f;
      const float measured = measure_efootball_line(
          labels[i], (int)strlen(labels[i]), gh, EFOOTBALL_FONT_STENCIL);
      if (measured > w - 0.020f * screen_width)
        gh *= (w - 0.020f * screen_width) / measured;
      const int n = emit_efootball_line(labels[i], (int)strlen(labels[i]),
          x + (w - measure_efootball_line(labels[i], (int)strlen(labels[i]), gh,
                  EFOOTBALL_FONT_STENCIL)) * 0.5f, y + (h - gh) * 0.5f, gh,
          EFOOTBALL_FONT_STENCIL, verts + quads * 24);
      quads += n; pause_skin_text_quads += n;
    }
    pause_stats_text = quads;
    static const char *const stats_labels[8] = {
        "POSSESSION", "SHOTS", "FOULS", "CORNER KICKS",
        "FREE KICKS", "PASSES", "TACKLES", "SAVES"};
    for (int row = -1; row < 8; ++row) {
      const char *label = row < 0 ? "MATCH STATS" : stats_labels[row];
      const float gh = screen_height / (row < 0 ? 27.0f : 33.0f);
      const float y = (row < 0 ? 0.287f : 0.35f + row * 0.044f) * screen_height;
      int n = emit_efootball_line(label, (int)strlen(label),
          (screen_width - measure_efootball_line(label, (int)strlen(label), gh,
              EFOOTBALL_FONT_BOLD)) * 0.5f, y, gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
      quads += n; pause_stats_quads += n;
      if (row < 0) continue;
      for (uint32_t side = 0; side < 2; ++side) {
        uint32_t value;
        char number[24];
        if (pes_controller_pause_stat(side, (uint32_t)row, &value))
          snprintf(number, sizeof(number), row == 0 ? "%u%%" : "%u", value);
        else snprintf(number, sizeof(number), "--");
        n = emit_efootball_line(number, (int)strlen(number),
            (side ? 0.74f : 0.26f) * screen_width -
            measure_efootball_line(number, (int)strlen(number), gh, EFOOTBALL_FONT_BOLD) * 0.5f,
            y, gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
        quads += n; pause_stats_quads += n;
      }
    }
    const float helper_h = helper_text_gh;
    const float helper_y = 0.945f * screen_height;
    const float helper_size = 0.042f * screen_height;
    const float helper_icon_gap = 0.006f * screen_width;
    const float helper_text_gap = 0.010f * screen_width;
    const float helper_group_gap = 0.030f * screen_width;
    const float select_w = measure_efootball_line(
        "SELECT", 6, helper_h, EFOOTBALL_FONT_BOLD);
    const float confirm_w = measure_efootball_line(
        "CONFIRM", 7, helper_h, EFOOTBALL_FONT_BOLD);
    const float resume_w = measure_efootball_line(
        "RESUME MATCH", 12, helper_h, EFOOTBALL_FONT_BOLD);
    const float helper_total = helper_size * 4.0f + helper_icon_gap +
        helper_text_gap * 3.0f + select_w + confirm_w + resume_w +
        helper_group_gap * 2.0f;
    float helper_x = 0.955f * screen_width - helper_total;
    const float select_left_x = helper_x + helper_size * 0.5f;
    helper_x += helper_size + helper_icon_gap;
    const float select_right_x = helper_x + helper_size * 0.5f;
    helper_x += helper_size + helper_text_gap;
    const float select_label_x = helper_x;
    helper_x += select_w + helper_group_gap;
    const float confirm_key_x = helper_x + helper_size * 0.5f;
    helper_x += helper_size + helper_text_gap;
    const float confirm_label_x = helper_x;
    helper_x += confirm_w + helper_group_gap;
    const float resume_key_x = helper_x + helper_size * 0.5f;
    helper_x += helper_size + helper_text_gap;
    const float resume_label_x = helper_x;
    ADD_SWITCH_HELPER("LEFT", select_left_x,
                      helper_y, helper_size);
    ADD_SWITCH_HELPER(">", select_right_x,
                      helper_y, helper_size);
    ADD_SWITCH_HELPER("A", confirm_key_x, helper_y, helper_size);
    ADD_SWITCH_HELPER("B", resume_key_x, helper_y, helper_size);
    pause_helper_text = quads;
    int helper_n = emit_efootball_line(
        "SELECT", 6, select_label_x, helper_y - helper_h * 0.5f,
        helper_h, EFOOTBALL_FONT_BOLD, verts + quads * 24);
    quads += helper_n;
    pause_helper_text_quads += helper_n;
    helper_n = emit_efootball_line(
        "CONFIRM", 7, confirm_label_x, helper_y - helper_h * 0.5f,
        helper_h, EFOOTBALL_FONT_BOLD, verts + quads * 24);
    quads += helper_n;
    pause_helper_text_quads += helper_n;
    helper_n = emit_efootball_line(
        "RESUME MATCH", 12, resume_label_x,
        helper_y - helper_h * 0.5f,
        helper_h, EFOOTBALL_FONT_BOLD, verts + quads * 24);
    quads += helper_n;
    pause_helper_text_quads += helper_n;
  }
  if (result_skin) {
    // Literally the pause layout: same background, badges, header, score,
    // stats panel and helper row. Only the card row is resolved from the
    // match state, and 1-3 cards stay centred on the same baseline.
    result_background = quads;
    quads += emit_image_rect(0, 0, screen_width, screen_height, verts + quads * 24);
    result_badges = quads;
    const float badge = screen_height * 0.16f;
    for (uint32_t side = 0; side < 2; ++side)
      quads += emit_badge(pes_controller_2p_prematch_hub_badge(side),
          (side ? 0.92f : 0.08f) * screen_width - badge * 0.5f,
          screen_height * 0.065f, badge, badge, verts + quads * 24);
    result_header = quads;
    const char *heading = pes_controller_match_result_heading();
    float gh = screen_height / 30.0f;
    quads += emit_efootball_line(heading, (int)strlen(heading),
        (screen_width - measure_efootball_line(heading, (int)strlen(heading), gh, EFOOTBALL_FONT_STENCIL)) * 0.5f,
        screen_height * 0.026f, gh, EFOOTBALL_FONT_STENCIL, verts + quads * 24);
    for (uint32_t side = 0; side < 2; ++side) {
      const char *team = pes_controller_2p_prematch_hub_team_name(side);
      gh = screen_height / 34.0f;
      float tw = measure_efootball_line(team, (int)strlen(team), gh, EFOOTBALL_FONT_STENCIL);
      if (tw > screen_width * 0.25f) { gh *= screen_width * 0.25f / tw; tw = screen_width * 0.25f; }
      quads += emit_efootball_line(team, (int)strlen(team),
          (side ? 0.735f : 0.265f) * screen_width - tw * 0.5f,
          screen_height * 0.125f, gh, EFOOTBALL_FONT_STENCIL, verts + quads * 24);
      uint32_t score; char score_text[16];
      if (pes_controller_pause_score(side, &score)) snprintf(score_text, sizeof(score_text), "%u", score);
      else snprintf(score_text, sizeof(score_text), "--");
      gh = screen_height / 12.0f;
      tw = measure_efootball_line(score_text, (int)strlen(score_text), gh, EFOOTBALL_FONT_BOLD);
      quads += emit_efootball_line(score_text, (int)strlen(score_text),
          (side ? 0.55f : 0.45f) * screen_width - tw * 0.5f,
          screen_height * 0.10f, gh, EFOOTBALL_FONT_BOLD, verts + quads * 24);
    }
    result_header_count = quads - result_header;
    const float w = 0.305f * screen_width, h = 0.105f * screen_height;
    const float gap = 0.0175f * screen_width;
    result_card_style = (RoundedRectStyle){w, h, 0.018f * screen_height};
    uint32_t count = pes_controller_match_result_card_count();
    if (count > 3u) count = 3u;
    result_card_count = (int)count;
    const uint32_t focus = pes_controller_match_result_focus();
    const float total = (float)count * w + (count ? (float)(count - 1u) * gap : 0.0f);
    const float x0 = (screen_width - total) * 0.5f;
    const float card_y = 0.780f * screen_height;
    for (uint32_t i = 0; i < count; ++i) {
      const float x = x0 + (float)i * (w + gap);
      if (focus == i) result_focus = (int)i;
      result_cards[i] = quads;
      quads += emit_round_rect_quad(x, card_y, w, h, verts + quads * 24);
    }
    result_stats_panel = quads;
    quads += emit_round_rect_quad(0.18f * screen_width, 0.265f * screen_height,
        0.64f * screen_width, 0.465f * screen_height, verts + quads * 24);
    result_card_text = quads;
    for (uint32_t i = 0; i < count; ++i) {
      const char *label = pes_controller_match_result_card_label(i);
      const float x = x0 + (float)i * (w + gap);
      const float label_h = screen_height / 29.0f;
      const int n = emit_efootball_line(label, (int)strlen(label),
          x + (w - measure_efootball_line(label, (int)strlen(label), label_h,
                  EFOOTBALL_FONT_STENCIL)) * 0.5f, card_y + (h - label_h) * 0.5f,
          label_h, EFOOTBALL_FONT_STENCIL, verts + quads * 24);
      quads += n; result_card_text_quads += n;
    }
    result_stats_text = quads;
    static const char *const result_stats_labels[8] = {
        "POSSESSION", "SHOTS", "FOULS", "CORNER KICKS",
        "FREE KICKS", "PASSES", "TACKLES", "SAVES"};
    for (int row = -1; row < 8; ++row) {
      const char *label = row < 0 ? "MATCH STATS" : result_stats_labels[row];
      const float row_h = screen_height / (row < 0 ? 27.0f : 33.0f);
      const float y = (row < 0 ? 0.287f : 0.35f + row * 0.044f) * screen_height;
      int n = emit_efootball_line(label, (int)strlen(label),
          (screen_width - measure_efootball_line(label, (int)strlen(label), row_h,
              EFOOTBALL_FONT_BOLD)) * 0.5f, y, row_h, EFOOTBALL_FONT_BOLD, verts + quads * 24);
      quads += n; result_stats_quads += n;
      if (row < 0) continue;
      for (uint32_t side = 0; side < 2; ++side) {
        uint32_t value;
        char number[24];
        if (pes_controller_pause_stat(side, (uint32_t)row, &value))
          snprintf(number, sizeof(number), row == 0 ? "%u%%" : "%u", value);
        else snprintf(number, sizeof(number), "--");
        n = emit_efootball_line(number, (int)strlen(number),
            (side ? 0.74f : 0.26f) * screen_width -
            measure_efootball_line(number, (int)strlen(number), row_h, EFOOTBALL_FONT_BOLD) * 0.5f,
            y, row_h, EFOOTBALL_FONT_BOLD, verts + quads * 24);
        quads += n; result_stats_quads += n;
      }
    }
    // Only advertise B where a Back to Menu card actually exists, so the
    // helper row never promises an action the surface will not take.
    const char *back_label = NULL;
    for (uint32_t i = 0; i < count; ++i) {
      const char *label = pes_controller_match_result_card_label(i);
      if (strcmp(label, "TOP TO MENU") == 0 ||
          strcmp(label, "BACK TO CUP") == 0) {
        back_label = label;
        break;
      }
    }
    const int has_back = back_label != NULL;
    const float helper_h = helper_text_gh;
    const float helper_y = 0.945f * screen_height;
    const float helper_size = 0.042f * screen_height;
    const float helper_icon_gap = 0.006f * screen_width;
    const float helper_text_gap = 0.010f * screen_width;
    const float helper_group_gap = 0.030f * screen_width;
    const float select_w = count > 1u ? measure_efootball_line(
        "SELECT", 6, helper_h, EFOOTBALL_FONT_BOLD) : 0.0f;
    const float confirm_w = measure_efootball_line(
        "CONFIRM", 7, helper_h, EFOOTBALL_FONT_BOLD);
    const float back_w = has_back ? measure_efootball_line(
        back_label, (int)strlen(back_label), helper_h,
        EFOOTBALL_FONT_BOLD) : 0.0f;
    const uint32_t helper_group_count = 1u + (count > 1u ? 1u : 0u) +
                                        (has_back ? 1u : 0u);
    float helper_total = helper_size + helper_text_gap + confirm_w;
    if (count > 1u)
      helper_total += helper_size * 2.0f + helper_icon_gap +
                      helper_text_gap + select_w;
    if (has_back)
      helper_total += helper_size + helper_text_gap + back_w;
    if (helper_group_count > 1u)
      helper_total += (float)(helper_group_count - 1u) * helper_group_gap;
    float helper_x = 0.955f * screen_width - helper_total;
    float select_left_x = 0.0f;
    float select_right_x = 0.0f;
    float select_label_x = 0.0f;
    if (count > 1u) {
      select_left_x = helper_x + helper_size * 0.5f;
      helper_x += helper_size + helper_icon_gap;
      select_right_x = helper_x + helper_size * 0.5f;
      helper_x += helper_size + helper_text_gap;
      select_label_x = helper_x;
      helper_x += select_w + helper_group_gap;
    }
    const float confirm_key_x = helper_x + helper_size * 0.5f;
    helper_x += helper_size + helper_text_gap;
    const float confirm_label_x = helper_x;
    helper_x += confirm_w;
    float back_key_x = 0.0f;
    float back_label_x = 0.0f;
    if (has_back) {
      helper_x += helper_group_gap;
      back_key_x = helper_x + helper_size * 0.5f;
      helper_x += helper_size + helper_text_gap;
      back_label_x = helper_x;
    }
    if (count > 1u) {
      ADD_SWITCH_HELPER("LEFT", select_left_x, helper_y, helper_size);
      ADD_SWITCH_HELPER(">", select_right_x, helper_y, helper_size);
    }
    ADD_SWITCH_HELPER("A", confirm_key_x, helper_y, helper_size);
    if (has_back)
      ADD_SWITCH_HELPER("B", back_key_x, helper_y, helper_size);
    result_helper_text = quads;
    if (count > 1u) {
      int select_n = emit_efootball_line(
          "SELECT", 6, select_label_x, helper_y - helper_h * 0.5f,
          helper_h, EFOOTBALL_FONT_BOLD, verts + quads * 24);
      quads += select_n;
      result_helper_text_quads += select_n;
    }
    int n = emit_efootball_line(
        "CONFIRM", 7, confirm_label_x,
        helper_y - helper_h * 0.5f, helper_h, EFOOTBALL_FONT_BOLD,
        verts + quads * 24);
    quads += n;
    result_helper_text_quads += n;
    if (has_back) {
      n = emit_efootball_line(
          back_label, (int)strlen(back_label), back_label_x,
          helper_y - helper_h * 0.5f, helper_h, EFOOTBALL_FONT_BOLD,
          verts + quads * 24);
      quads += n;
      result_helper_text_quads += n;
    }
  }
  if (result_transition) {
    // Identical treatment to the pause -> Game Plan cover: the custom
    // background is the entire screen and a small console-style spinner sits in
    // the bottom-right corner.
    result_cover_background = quads;
    quads += emit_image_rect(0, 0, screen_width, screen_height, verts + quads * 24);
    const uint64_t freq = armGetSystemTickFreq();
    const float phase = freq ? (float)(armGetSystemTick() % freq) / freq * 6.2831853f : 0;
    const float spinner_x = screen_width * 0.955f;
    const float spinner_y = screen_height * 0.905f;
    const float radius = screen_height * 0.017f;
    result_cover_spinner = quads;
    for (uint32_t i = 0; i < 8; ++i) {
      const float a = phase + i * 0.43f;
      const int n = emit_segment(spinner_x + cosf(a) * radius,
          spinner_y + sinf(a) * radius,
          spinner_x + cosf(a + 0.25f) * radius,
          spinner_y + sinf(a + 0.25f) * radius,
          screen_height * 0.0035f, verts + quads * 24);
      quads += n; result_cover_spinner_count += n;
    }
  }
  if (custom_gameplan) {
    gameplan_locked_rows = quads;
    for (uint32_t side = 0; side < 2; ++side) {
      for (uint32_t slot = 0; slot < prematch_gameplan_bench_visible[side]; ++slot) {
        if (!pes_controller_gameplan_bench_locked(side, prematch_gameplan_bench_start[side] + slot)) continue;
        const float *r = prematch_gameplan_bench_rect[side][slot];
        const int n = emit_rect(r[0], r[1], r[2], r[3], verts + quads * 24);
        quads += n; gameplan_locked_row_count += n;
      }
    }
  }
  if (pause_skin && pause_transition) {
    const uint64_t freq = armGetSystemTickFreq();
    const float phase = freq ? (float)(armGetSystemTick() % freq) / freq * 6.2831853f : 0;
    // Keep transition feedback deliberately quiet: the custom background is
    // the entire cover and only a small console-style spinner remains.
    const float spinner_x = screen_width * 0.955f;
    const float spinner_y = screen_height * 0.905f;
    const float radius = screen_height * 0.017f;
    pause_transition_spinner = quads;
    for (uint32_t i = 0; i < 8; ++i) {
      const float a = phase + i * 0.43f;
      const int n = emit_segment(spinner_x + cosf(a) * radius,
          spinner_y + sinf(a) * radius,
          spinner_x + cosf(a + 0.25f) * radius,
          spinner_y + sinf(a + 0.25f) * radius,
          screen_height * 0.0035f, verts + quads * 24);
      quads += n; pause_transition_spinner_count += n;
    }
  }
  if (pause_skin && pes_controller_pause_top_menu_confirm_active()) {
    const float panel_x = 0.195f * screen_width;
    const float panel_y = 0.235f * screen_height;
    const float panel_w = 0.610f * screen_width;
    const float panel_h = 0.455f * screen_height;
    const float button_w = 0.225f * screen_width;
    const float button_h = 0.090f * screen_height;
    const float button_y = panel_y + 0.305f * screen_height;
    pause_confirm_backdrop = quads;
    quads += emit_rect(0, 0, screen_width, screen_height, verts + quads * 24);
    pause_confirm_panel_style = (RoundedRectStyle){panel_w, panel_h, 0.032f * screen_height};
    pause_confirm_panel = quads;
    quads += emit_round_rect_quad(panel_x, panel_y, panel_w, panel_h, verts + quads * 24);
    pause_confirm_button_style = (RoundedRectStyle){button_w, button_h, 0.020f * screen_height};
    pause_confirm_buttons[0] = quads;
    quads += emit_round_rect_quad(panel_x + 0.060f * screen_width, button_y,
        button_w, button_h, verts + quads * 24);
    pause_confirm_buttons[1] = quads;
    quads += emit_round_rect_quad(panel_x + panel_w - 0.060f * screen_width - button_w,
        button_y, button_w, button_h, verts + quads * 24);
    const float title_h = screen_height / 21.0f;
    const float message_h = screen_height / 32.0f;
    pause_confirm_title = quads;
    pause_confirm_title_quads = emit_efootball_centered_fit_line(
        "RETURN TO TOP MENU?", 19, screen_width * 0.5f,
        panel_y + 0.090f * screen_height, panel_w * 0.88f,
        title_h, title_h, EFOOTBALL_FONT_STENCIL, verts + quads * 24);
    quads += pause_confirm_title_quads;
    pause_confirm_message = quads;
    const char *confirm_message = "LEAVE THE MATCH AND RETURN TO HOME?";
    pause_confirm_message_quads = emit_efootball_centered_fit_line(
        confirm_message, (int)strlen(confirm_message), screen_width * 0.5f,
        panel_y + 0.185f * screen_height, panel_w * 0.90f,
        message_h, message_h, EFOOTBALL_FONT_BOLD, verts + quads * 24);
    quads += pause_confirm_message_quads;
    const char *const confirm_labels[2] = {"CONFIRM", "CANCEL"};
    for (int i = 0; i < 2; ++i) {
      const float bx = i == 0 ? panel_x + 0.060f * screen_width
                              : panel_x + panel_w - 0.060f * screen_width - button_w;
      const float bw = measure_efootball_line(confirm_labels[i],
          (int)strlen(confirm_labels[i]), message_h, EFOOTBALL_FONT_STENCIL);
      pause_confirm_button_text[i] = quads;
      const int n = emit_efootball_line(confirm_labels[i],
          (int)strlen(confirm_labels[i]), bx + (button_w - bw) * 0.5f,
          button_y + (button_h - message_h) * 0.5f, message_h,
          EFOOTBALL_FONT_STENCIL, verts + quads * 24);
      quads += n; pause_confirm_button_text_quads[i] = n;
    }
  }
  if (custom_main_menu) {
    static const char *const labels[4] = {
        "MATCH", "MODES", "SETTINGS", "CREDITS"};
    main_menu_background_quad = quads;
    quads += emit_image_rect(0, 0, screen_width, screen_height,
                             verts + quads * 24);
    main_menu_portrait_quad = quads;
    quads += emit_image_rect(0.540f * screen_width, 0.035f * screen_height,
                             0.425f * screen_width, 1.010f * screen_height,
                             verts + quads * 24);

    main_menu_brand_quad = quads;
    quads += emit_image_rect(0.055f * screen_width, 0.052f * screen_height,
                             0.245f * screen_width,
                             0.245f * screen_width * (496.0f / 1310.0f),
                             verts + quads * 24);

    const float card_x = 0.055f * screen_width;
    const float card_y = 0.315f * screen_height;
    const float card_w = 0.450f * screen_width;
    const float card_h = 0.115f * screen_height;
    const float card_step = 0.135f * screen_height;
    main_menu_card_style = (RoundedRectStyle){
        card_w, card_h, 0.014f * screen_height};
    for (uint32_t row = 0; row < 4; row++) {
      const float focus_amount = main_menu_row_focus_amount(
          row, custom_main_menu_mix);
      const float y = card_y + (float)row * card_step;
      main_menu_card_quads[row] = quads;
      quads += emit_round_rect_quad(card_x, y, card_w, card_h,
                                    verts + quads * 24);
      const float icon_size =
          (0.078f + 0.006f * focus_amount) * screen_height;
      const float icon_x = card_x + card_w - 0.022f * screen_width -
                           icon_size - 0.004f * screen_width * focus_amount;
      const float icon_y = y + (card_h - icon_size) * 0.5f;
      const float u0 = (row & 1u) ? 0.5f : 0.0f;
      const float v0 = (row >= 2u) ? 0.5f : 0.0f;
      main_menu_icon_quads[row] = quads;
      quads += emit_image_rect_uv(icon_x, icon_y, icon_size, icon_size,
                                  u0, v0, u0 + 0.5f, v0 + 0.5f,
                                  verts + quads * 24);
      const float label_h = screen_height / 20.0f;
      main_menu_label_first_quad[row] = quads;
      const int n = emit_efootball_line(
          labels[row], (int)strlen(labels[row]),
          card_x + (0.030f + 0.012f * focus_amount) * screen_width,
          y + (card_h - label_h) * 0.5f, label_h,
          EFOOTBALL_FONT_STENCIL, verts + quads * 24);
      quads += n;
      main_menu_label_quads[row] = n;
    }
    const float helper_h = helper_text_gh;
    main_menu_button_a_quad = quads;
    quads += emit_image_rect(card_x, 0.920f * screen_height,
        0.045f * screen_height, 0.045f * screen_height, verts + quads * 24);
    main_menu_helper_first_quad = quads;
    main_menu_helper_quads = emit_efootball_line(
        "CONFIRM", 7, card_x + 0.035f * screen_width,
        0.930f * screen_height, helper_h,
        EFOOTBALL_FONT_BOLD, verts + quads * 24);
    quads += main_menu_helper_quads;
  }
  if (!quads)
    return;

  GLint prev_fb, prev_prog, prev_active, prev_tex0, prev_sampler = 0;
  GLint prev_array_buf, prev_viewport[4];
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
  // UE4 frequently leaves a sampler object bound to unit zero. A sampler
  // overrides the filtering/wrap state configured on our textures and caused
  // the full-page PNGs to appear as repeated vertical strips. Own unit zero
  // for the complete overlay pass and restore it at the frame boundary.
  if (gl.bind_sampler) {
    glGetIntegerv(GL_SAMPLER_BINDING, &prev_sampler);
    gl.bind_sampler(0, 0);
  }
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
  // The game can render the swap surface through a fixed 1024x576 backbuffer
  // even when pes21_nx.cfg advertises a 1280x720 window. Using the configured
  // dimensions here made the overlay viewport 1.25x larger than the actual
  // target, which clipped the right custom page and enlarged the left one.
  // Keep the native viewport that was active at the frame boundary; our NDC
  // geometry remains resolution-independent and is then composed at the same
  // scale as the scene.
  glViewport(prev_viewport[0], prev_viewport[1], prev_viewport[2],
             prev_viewport[3]);
#if defined(DEBUG_LOG) && DEBUG_LOG
  static int overlay_viewport_logged;
  if (!overlay_viewport_logged &&
      (prev_viewport[2] != screen_width || prev_viewport[3] != screen_height)) {
    debugPrintf("OVERLAY viewport follows native target %d,%d %dx%d (config %dx%d)\n",
                prev_viewport[0], prev_viewport[1], prev_viewport[2],
                prev_viewport[3], screen_width, screen_height);
    overlay_viewport_logged = 1;
  }
#endif
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
  if (stamina_bar_count) {
    // Native scene samplers can require mipmaps absent from HUD textures.
    // Match the Game Plan portrait path and restore the engine sampler.
    GLint hud_previous_sampler = 0;
    if (gl.bind_sampler) {
      glGetIntegerv(GL_SAMPLER_BINDING, &hud_previous_sampler);
      gl.bind_sampler(0, 0);
    }
    glUniform1f(gl.loc_solid, 1.0f);
    glUniform1f(gl.loc_image, 0.0f);
    glUniform2f(gl.loc_off, 0.0f, 0.0f);
    for (uint32_t side = 0; side < PES_STAMINA_BAR_CAPACITY; ++side) {
      if (!stamina_track_quads[side])
        continue;
      const float alpha = stamina_alpha[side];
      use_rounded_rect(&hud_card_style[side]);
      glUniform4f(gl.loc_color, 0.025f, 0.09f, 0.075f, 0.76f * alpha);
      glDrawArrays(GL_TRIANGLES, hud_card_quad[side] * 6, 6);
#ifdef DEBUG_LOG
      ++hud_diag_draws;
#endif
      use_rounded_rect(NULL);
      glUniform1f(gl.loc_solid, 0.0f);
      glUniform1f(gl.loc_image, 1.0f);
      glUniform4f(gl.loc_color, 1, 1, 1, alpha);
      glBindTexture(GL_TEXTURE_2D, gl.badge_tex);
      glDrawArrays(GL_TRIANGLES, hud_badge_quad[side] * 6, 6);
      if (hud_portrait_texture[side]) {
        glBindTexture(GL_TEXTURE_2D, hud_portrait_texture[side]);
        glDrawArrays(GL_TRIANGLES, hud_portrait_quad[side] * 6, 6);
      }
      glUniform1f(gl.loc_image, 0.0f);
      glBindTexture(GL_TEXTURE_2D, gl.efootball_tex);
      glDrawArrays(GL_TRIANGLES, hud_text_quad[side] * 6, hud_text_count[side] * 6);
      glBindTexture(GL_TEXTURE_2D, gl.tex);
      glUniform1f(gl.loc_solid, 1.0f);
      use_rounded_rect(&stamina_shadow_style[side]);
      glUniform4f(gl.loc_color, 0.0f, 0.015f, 0.025f, 0.42f * alpha);
      glDrawArrays(GL_TRIANGLES, stamina_shadow_first_quad[side] * 6,
                   stamina_shadow_quads[side] * 6);
      use_rounded_rect(&stamina_track_style[side]);
      glUniform4f(gl.loc_color, 0.018f, 0.040f, 0.052f, 0.88f * alpha);
      glDrawArrays(GL_TRIANGLES, stamina_track_first_quad[side] * 6,
                   stamina_track_quads[side] * 6);
      if (stamina_fill_quads[side]) {
        use_rounded_rect(&stamina_fill_style[side]);
        glUniform4f(gl.loc_color, stamina_fill_rgb[side][0],
                    stamina_fill_rgb[side][1], stamina_fill_rgb[side][2],
                    0.98f * alpha);
        glDrawArrays(GL_TRIANGLES, stamina_fill_first_quad[side] * 6,
                     stamina_fill_quads[side] * 6);
      }
      if (stamina_highlight_quads[side]) {
        use_rounded_rect(&stamina_highlight_style[side]);
        glUniform4f(gl.loc_color, 0.78f, 1.0f, 0.94f, 0.18f * alpha);
        glDrawArrays(GL_TRIANGLES, stamina_highlight_first_quad[side] * 6,
                     stamina_highlight_quads[side] * 6);
      }
    }
    use_rounded_rect(NULL);
    glUniform1f(gl.loc_solid, 0.0f);
    if (gl.bind_sampler)
      gl.bind_sampler(0, (GLuint)hud_previous_sampler);
  }
  if (start_prompt) {
    use_rounded_rect(NULL);
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform1f(gl.loc_image, 1.0f);
    glUniform2f(gl.loc_off, 0.0f, 0.0f);
    glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, 1.0f);
    glBindTexture(GL_TEXTURE_2D, gl.main_menu_background_tex);
    glDrawArrays(GL_TRIANGLES, title_background_quad * 6, 6);

    if (title_portrait_mix < 1.0f &&
        title_portrait_previous != title_portrait_current) {
      glBindTexture(GL_TEXTURE_2D,
                    gl.main_menu_portrait_tex[title_portrait_previous]);
      glUniform2f(gl.loc_off, -0.24f * title_portrait_mix, 0.0f);
      glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f,
                  1.0f - title_portrait_mix);
      glDrawArrays(GL_TRIANGLES, title_portrait_quad * 6, 6);
    }
    glBindTexture(GL_TEXTURE_2D,
                  gl.main_menu_portrait_tex[title_portrait_current]);
    glUniform2f(gl.loc_off, 0.24f * (1.0f - title_portrait_mix), 0.0f);
    glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, title_portrait_mix);
    glDrawArrays(GL_TRIANGLES, title_portrait_quad * 6, 6);

    glUniform2f(gl.loc_off, 0.0f, 0.0f);
    glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, 1.0f);
    glBindTexture(GL_TEXTURE_2D, gl.main_menu_brand_tex);
    glDrawArrays(GL_TRIANGLES, title_brand_quad * 6, 6);

    const u64 blink_frequency = armGetSystemTickFreq();
    const float blink_phase = blink_frequency
        ? (float)(armGetSystemTick() % blink_frequency) /
              (float)blink_frequency * 6.2831853f
        : 0.0f;
    const float prompt_alpha = 0.58f + 0.42f * (0.5f + 0.5f * sinf(blink_phase));
    glBindTexture(GL_TEXTURE_2D, gl.main_menu_button_a_tex);
    glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, prompt_alpha);
    glDrawArrays(GL_TRIANGLES, title_button_a_quad * 6, 6);

    glBindTexture(GL_TEXTURE_2D, gl.efootball_tex);
    glUniform1f(gl.loc_image, 0.0f);
    glUniform4f(gl.loc_color, 0.96f, 0.98f, 1.0f,
                0.98f * prompt_alpha);
    glDrawArrays(GL_TRIANGLES, title_prompt_text_first_quad * 6,
                 title_prompt_text_quads * 6);
    glUniform4f(gl.loc_color, 0.74f, 0.84f, 1.0f, 0.86f);
    glDrawArrays(GL_TRIANGLES, title_footer_first_quad * 6,
                 title_footer_quads * 6);
    glBindTexture(GL_TEXTURE_2D, gl.tex);
  }
  if (custom_main_menu) {
    use_rounded_rect(NULL);
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform1f(gl.loc_image, 1.0f);
    glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, 1.0f);
    glBindTexture(GL_TEXTURE_2D, gl.main_menu_background_tex);
    glDrawArrays(GL_TRIANGLES, main_menu_background_quad * 6, 6);

    const uint32_t previous = main_menu_portrait_transition.previous;
    const uint32_t current = main_menu_portrait_transition.current;
    if (custom_main_menu_mix < 1.0f && previous < 4u &&
        previous != current) {
      glBindTexture(GL_TEXTURE_2D, gl.main_menu_portrait_tex[previous]);
      glUniform2f(gl.loc_off, 0.24f * custom_main_menu_mix, 0.0f);
      glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f,
                  1.0f - custom_main_menu_mix);
      glDrawArrays(GL_TRIANGLES, main_menu_portrait_quad * 6, 6);
    }
    if (current < 4u) {
      glBindTexture(GL_TEXTURE_2D, gl.main_menu_portrait_tex[current]);
      glUniform2f(gl.loc_off, 0.24f * (1.0f - custom_main_menu_mix), 0.0f);
      glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f,
                  custom_main_menu_mix);
      glDrawArrays(GL_TRIANGLES, main_menu_portrait_quad * 6, 6);
    }

    glBindTexture(GL_TEXTURE_2D, gl.main_menu_brand_tex);
    glUniform2f(gl.loc_off, 0.0f, 0.0f);
    glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, 1.0f);
    glDrawArrays(GL_TRIANGLES, main_menu_brand_quad * 6, 6);
    glBindTexture(GL_TEXTURE_2D, gl.main_menu_button_a_tex);
    glDrawArrays(GL_TRIANGLES, main_menu_button_a_quad * 6, 6);

    glBindTexture(GL_TEXTURE_2D, gl.tex);
    glUniform1f(gl.loc_image, 0.0f);
    glUniform1f(gl.loc_solid, 1.0f);
    use_rounded_rect(&main_menu_card_style);
    glUniform4f(gl.loc_color, 0.006f, 0.025f, 0.105f, 0.88f);
    for (uint32_t row = 0; row < 4; row++)
      glDrawArrays(GL_TRIANGLES, main_menu_card_quads[row] * 6, 6);
    for (uint32_t row = 0; row < 4; row++) {
      const float focus_amount = main_menu_row_focus_amount(
          row, custom_main_menu_mix);
      if (focus_amount <= 0.0f)
        continue;
      glUniform4f(gl.loc_color, 1.0f, 0.91f, 0.02f, focus_amount);
      glDrawArrays(GL_TRIANGLES, main_menu_card_quads[row] * 6, 6);
    }
    use_rounded_rect(NULL);

    glUniform1f(gl.loc_solid, 0.0f);
    glBindTexture(GL_TEXTURE_2D, gl.main_menu_icons_tex);
    for (uint32_t row = 0; row < 4; row++) {
      const float focus_amount = main_menu_row_focus_amount(
          row, custom_main_menu_mix);
      glUniform4f(gl.loc_color,
                  0.72f + (0.02f - 0.72f) * focus_amount,
                  0.80f + (0.10f - 0.80f) * focus_amount,
                  0.96f + (0.34f - 0.96f) * focus_amount,
                  0.94f + 0.06f * focus_amount);
      glDrawArrays(GL_TRIANGLES, main_menu_icon_quads[row] * 6, 6);
    }

    glBindTexture(GL_TEXTURE_2D, gl.efootball_tex);
    for (uint32_t row = 0; row < 4; row++) {
      const float focus_amount = main_menu_row_focus_amount(
          row, custom_main_menu_mix);
      glUniform4f(gl.loc_color,
                  0.95f + (0.015f - 0.95f) * focus_amount,
                  0.97f + (0.075f - 0.97f) * focus_amount,
                  1.00f + (0.29f - 1.00f) * focus_amount,
                  0.95f + 0.05f * focus_amount);
      glDrawArrays(GL_TRIANGLES, main_menu_label_first_quad[row] * 6,
                   main_menu_label_quads[row] * 6);
    }
    glUniform4f(gl.loc_color, 0.88f, 0.93f, 1.0f, 0.92f);
    glDrawArrays(GL_TRIANGLES, main_menu_helper_first_quad * 6,
                 main_menu_helper_quads * 6);
    glBindTexture(GL_TEXTURE_2D, gl.tex);
  }
  if (custom_competition) {
    const int competition_settings_page =
        competition_display_state == COMPETITION_FRONTEND_CUP_SETTINGS ||
        competition_display_state == COMPETITION_FRONTEND_CUP_TEAMS;
    const int bracket_page =
        competition_display_state == COMPETITION_FRONTEND_CUP_BRACKET ||
        competition_display_state == COMPETITION_FRONTEND_CUP_CHECKPOINT;
    const int competition_team_page =
        competition_display_state == COMPETITION_FRONTEND_CUP_TEAMS;
    const int competition_team_picker_page =
        competition_team_page && competition_frontend_cup_team_picker_active();
    /* Dedicated competition surface: opaque background first, then the
     * shared card vocabulary used by the native/custom PES pages. */
    use_rounded_rect(NULL);
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform1f(gl.loc_image, 1.0f);
    glUniform2f(gl.loc_off, 0.0f, 0.0f);
    glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, 1.0f);
    glBindTexture(GL_TEXTURE_2D,
                  (competition_settings_page || bracket_page)
                      ? gl.team_select_bg_tex
                                              : gl.main_menu_background_tex);
    glDrawArrays(GL_TRIANGLES, competition_background_quad * 6, 6);

    if (!competition_settings_page && !bracket_page) {
      glBindTexture(GL_TEXTURE_2D, gl.main_menu_brand_tex);
      glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, 1.0f);
      glDrawArrays(GL_TRIANGLES, competition_brand_quad * 6, 6);
      const uint32_t portrait = main_menu_portrait_transition.current < 4u
                                    ? main_menu_portrait_transition.current
                                    : 0u;
      glBindTexture(GL_TEXTURE_2D, gl.main_menu_portrait_tex[portrait]);
      glDrawArrays(GL_TRIANGLES, competition_portrait_quad * 6, 6);
    }

    glBindTexture(GL_TEXTURE_2D, gl.tex);
    glUniform1f(gl.loc_image, 0.0f);
    glUniform1f(gl.loc_solid, 1.0f);
    if (!competition_settings_page && !bracket_page) {
      use_rounded_rect(&competition_departing_style);
      glUniform4f(gl.loc_color, 0.006f, 0.025f, 0.105f,
                  0.88f * (1.0f - competition_menu_mix));
      for (uint32_t row = 0; row < 4; row++)
        glDrawArrays(GL_TRIANGLES, competition_departing_card_quads[row] * 6,
                     6);
      use_rounded_rect(NULL);
      glUniform1f(gl.loc_solid, 0.0f);
      /* The runtime atlas is a luminance mask.  Use the same mask path as
       * the main menu so transparent/black atlas space never becomes a solid
       * square on the submenu tiles. */
      glUniform1f(gl.loc_image, 0.0f);
      glBindTexture(GL_TEXTURE_2D, gl.main_menu_icons_tex);
      glUniform4f(gl.loc_color, 0.72f, 0.80f, 0.96f,
                  0.94f * (1.0f - competition_menu_mix));
      for (uint32_t row = 0; row < 4; row++)
        glDrawArrays(GL_TRIANGLES, competition_departing_icon_quads[row] * 6,
                     6);
      glUniform1f(gl.loc_image, 0.0f);
      glBindTexture(GL_TEXTURE_2D, gl.efootball_tex);
      glUniform4f(gl.loc_color, 0.95f, 0.97f, 1.0f,
                  0.95f * (1.0f - competition_menu_mix));
      for (uint32_t row = 0; row < 4; row++)
        glDrawArrays(GL_TRIANGLES,
                     competition_departing_label_first_quad[row] * 6,
                     competition_departing_label_quads[row] * 6);
    }

    glBindTexture(GL_TEXTURE_2D, gl.tex);
    glUniform1f(gl.loc_solid, 1.0f);
    if (bracket_page) {
      use_rounded_rect(&cup_shell_style);
      glUniform4f(gl.loc_color, 0.88f, 0.93f, 0.98f, 0.98f);
      glDrawArrays(GL_TRIANGLES, cup_shell_quad * 6, 6);
      use_rounded_rect(&cup_header_style);
      glUniform4f(gl.loc_color, 0.77f, 0.87f, 0.96f, 0.98f);
      glDrawArrays(GL_TRIANGLES, cup_header_quad * 6, 6);
      use_rounded_rect(&cup_left_style);
      glUniform4f(gl.loc_color, 0.97f, 0.98f, 1.0f, 0.99f);
      glDrawArrays(GL_TRIANGLES, cup_left_quad * 6, 6);
      use_rounded_rect(&cup_right_style);
      glDrawArrays(GL_TRIANGLES, cup_right_quad * 6, 6);
      use_rounded_rect(&cup_fixture_style);
      for (uint32_t i = 0; i < 8u; i++) {
        if (!cup_fixture_quads[i]) continue;
        glUniform4f(gl.loc_color,
                    (int)i == cup_focus_fixture ? 0.70f : 0.85f,
                    (int)i == cup_focus_fixture ? 0.88f : 0.93f,
                    (int)i == cup_focus_fixture ? 1.0f : 0.99f, 0.99f);
        glDrawArrays(GL_TRIANGLES, cup_fixture_quads[i] * 6, 6);
        if (cup_fixture_away_quads[i])
          glDrawArrays(GL_TRIANGLES, cup_fixture_away_quads[i] * 6, 6);
      }
      use_rounded_rect(&cup_bye_style);
      glUniform4f(gl.loc_color, 0.85f, 0.93f, 0.99f, 0.99f);
      for (uint32_t i = 0; i < 8u; i++)
        if (cup_bye_quads[i])
          glDrawArrays(GL_TRIANGLES, cup_bye_quads[i] * 6, 6);
      use_rounded_rect(&cup_next_style);
      glUniform4f(gl.loc_color, 0.84f, 0.92f, 0.99f, 0.99f);
      for (uint32_t i = 0; i < 4u; i++) {
        if (cup_next_quads[i])
          glDrawArrays(GL_TRIANGLES, cup_next_quads[i] * 6, 6);
        if (cup_next_away_quads[i])
          glDrawArrays(GL_TRIANGLES, cup_next_away_quads[i] * 6, 6);
      }
      use_rounded_rect(NULL);
      glUniform4f(gl.loc_color, 0.37f, 0.55f, 0.70f, 0.97f);
      glDrawArrays(GL_TRIANGLES, cup_border_first * 6,
                   cup_border_count * 6);
      glUniform4f(gl.loc_color, 0.19f, 0.47f, 0.70f, 0.90f);
      glDrawArrays(GL_TRIANGLES, cup_connector_first * 6,
                   cup_connector_count * 6);
      use_rounded_rect(&cup_history_style);
      for (uint32_t i = 0; i < 5u; i++) {
        if (!cup_history_quads[i]) continue;
        if (!i && competition_frontend_cup_tournament() &&
            competition_frontend_cup_tournament()->champion)
          glUniform4f(gl.loc_color, 0.98f, 0.90f, 0.49f, 0.99f);
        else
          glUniform4f(gl.loc_color, 0.85f, 0.93f, 0.99f, 0.99f);
        glDrawArrays(GL_TRIANGLES, cup_history_quads[i] * 6, 6);
      }
      use_rounded_rect(&cup_action_style);
      for (uint32_t i = 0; i < 2u; i++) {
        const int selected = competition_display_focus == i;
        const int enabled = competition_frontend_item_enabled(i);
        glUniform4f(gl.loc_color,
                    selected && enabled ? 0.99f : enabled ? 0.04f : 0.03f,
                    selected && enabled ? 0.91f : enabled ? 0.43f : 0.17f,
                    selected && enabled ? 0.02f : enabled ? 0.75f : 0.29f,
                    0.98f);
        glDrawArrays(GL_TRIANGLES, cup_action_quads[i] * 6, 6);
      }
      use_rounded_rect(NULL);
      glUniform1f(gl.loc_solid, 0.0f);
      glUniform1f(gl.loc_image, 1.0f);
      glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, 1.0f);
      glBindTexture(GL_TEXTURE_2D, gl.badge_tex);
      glDrawArrays(GL_TRIANGLES, cup_badge_first * 6, cup_badge_count * 6);
      glUniform1f(gl.loc_image, 0.0f);
      glBindTexture(GL_TEXTURE_2D, gl.efootball_tex);
      glUniform4f(gl.loc_color, 0.03f, 0.09f, 0.17f, 1.0f);
      glDrawArrays(GL_TRIANGLES, cup_text_first * 6, cup_text_count * 6);
      for (uint32_t i = 0; i < 2u; i++) {
        const int dark = competition_display_focus == i &&
                         competition_frontend_item_enabled(i);
        glUniform4f(gl.loc_color, dark ? 0.025f : 0.98f,
                    dark ? 0.055f : 0.99f,
                    dark ? 0.095f : 1.0f, 1.0f);
        glDrawArrays(GL_TRIANGLES, cup_action_text_first[i] * 6,
                     cup_action_text_count[i] * 6);
      }
      glBindTexture(GL_TEXTURE_2D, gl.tex);
      glUniform1f(gl.loc_solid, 1.0f);
    } else if (competition_settings_page) {
      use_rounded_rect(&competition_full_panel_style);
      if (competition_team_page)
        glUniform4f(gl.loc_color, 0.91f, 0.95f, 0.99f, 0.99f);
      else
        glUniform4f(gl.loc_color, 0.06f, 0.09f, 0.17f, 0.92f);
      glDrawArrays(GL_TRIANGLES, competition_full_panel_quad * 6, 6);
      use_rounded_rect(&competition_full_header_style);
      if (competition_team_page)
        glUniform4f(gl.loc_color, 0.79f, 0.87f, 0.96f, 0.99f);
      else
        glUniform4f(gl.loc_color, 0.025f, 0.045f, 0.11f, 0.97f);
      glDrawArrays(GL_TRIANGLES, competition_full_header_round_quad * 6, 6);
      use_rounded_rect(NULL);
      glDrawArrays(GL_TRIANGLES, competition_full_header_fill_quad * 6, 6);
      if (!competition_team_page && competition_full_selected_quad) {
        use_rounded_rect(&competition_full_selected_style);
        glUniform4f(gl.loc_color, 0.93f, 0.96f, 1.0f, 0.78f);
        glDrawArrays(GL_TRIANGLES, competition_full_selected_quad * 6, 6);
      }
      if (!competition_team_page) {
        use_rounded_rect(NULL);
        glUniform4f(gl.loc_color, 0.80f, 0.86f, 0.93f, 0.34f);
        glDrawArrays(GL_TRIANGLES, competition_full_rule_first_quad * 6,
                     competition_full_rule_quads * 6);
        use_rounded_rect(&competition_full_value_style);
        glUniform4f(gl.loc_color, 0.04f, 0.43f, 0.76f, 0.96f);
        for (uint32_t index = 0; index < 12u; index++) {
          if (competition_value_plate_quads[index])
            glDrawArrays(GL_TRIANGLES,
                         competition_value_plate_quads[index] * 6, 6);
        }
        use_rounded_rect(NULL);
        glDrawArrays(GL_TRIANGLES, competition_full_arrow_first_quad * 6,
                     competition_full_arrow_quads * 6);
      }
      if (competition_team_page && !competition_team_picker_page) {
        use_rounded_rect(&competition_team_slot_style);
        const uint32_t slot_count = competition_frontend_cup_player_count() > 8u
                                        ? 8u
                                        : competition_frontend_cup_player_count();
        for (uint32_t slot = 0; slot < slot_count; slot++) {
          const int selected = competition_frontend_cup_team_selected(slot);
          glUniform4f(gl.loc_color, selected ? 0.79f : 0.96f,
                      selected ? 0.89f : 0.98f,
                      selected ? 0.98f : 1.0f, 0.99f);
          glDrawArrays(GL_TRIANGLES, competition_team_slot_quads[slot] * 6,
                       6);
        }
        if (competition_display_focus < slot_count) {
          glUniform4f(gl.loc_color, 1.0f, 0.91f, 0.02f, 0.98f);
          glDrawArrays(GL_TRIANGLES,
                       competition_team_slot_quads[competition_display_focus] * 6,
                       6);
        }
        use_rounded_rect(NULL);
        glUniform1f(gl.loc_solid, 0.0f);
        glUniform1f(gl.loc_image, 1.0f);
        glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, 1.0f);
        glBindTexture(GL_TEXTURE_2D, gl.badge_tex);
        for (uint32_t slot = 0; slot < slot_count; slot++)
          if (competition_team_slot_badge_quads[slot])
            glDrawArrays(GL_TRIANGLES,
                         competition_team_slot_badge_quads[slot] * 6, 6);
        glBindTexture(GL_TEXTURE_2D, gl.tex);
        glUniform1f(gl.loc_image, 0.0f);
        glUniform1f(gl.loc_solid, 1.0f);
      } else if (competition_team_picker_page) {
        use_rounded_rect(&competition_team_picker_style);
        glUniform4f(gl.loc_color, 0.96f, 0.98f, 1.0f, 0.99f);
        glDrawArrays(GL_TRIANGLES, competition_team_picker_quad * 6, 6);
        use_rounded_rect(&competition_team_picker_candidate_style);
        glUniform4f(gl.loc_color, 0.04f, 0.43f, 0.76f, 0.98f);
        glDrawArrays(GL_TRIANGLES,
                     competition_team_picker_candidate_quad * 6, 6);
        for (uint32_t item = 0; item < 5u; item++) {
          if (!competition_team_picker_row_quads[item])
            continue;
          use_rounded_rect(&competition_team_picker_candidate_style);
          glUniform4f(gl.loc_color, 0.84f, 0.91f, 0.98f, 0.98f);
          glDrawArrays(GL_TRIANGLES,
                       competition_team_picker_row_quads[item] * 6, 6);
        }
      }
      if (!competition_team_picker_page)
        use_rounded_rect(&competition_full_action_style);
      const uint32_t action_focus =
          competition_display_state == COMPETITION_FRONTEND_CUP_SETTINGS
              ? 8u
              : competition_frontend_cup_player_count();
      const int action_enabled =
          competition_display_state == COMPETITION_FRONTEND_CUP_SETTINGS
              ? 1
              : competition_frontend_cup_teams_ready();
      const int action_selected = competition_display_focus == action_focus;
      glUniform4f(gl.loc_color,
                  action_selected && action_enabled ? 0.98f
                                                     : action_enabled ? 0.04f
                                                                       : 0.04f,
                  action_selected && action_enabled ? 0.91f
                                                     : action_enabled ? 0.42f
                                                                       : 0.20f,
                  action_selected && action_enabled ? 0.02f
                                                     : action_enabled ? 0.72f
                                                                       : 0.28f,
                  0.96f);
      if (!competition_team_picker_page)
        glDrawArrays(GL_TRIANGLES, competition_full_action_button_quad * 6, 6);
    } else {
      use_rounded_rect(&competition_row_style);
      glUniform4f(gl.loc_color, 0.006f, 0.025f, 0.105f,
                  0.88f * competition_menu_mix);
      for (uint32_t index = 0; index < competition_display_item_count &&
                               index < 12u; index++) {
        if (competition_row_quads[index])
          glDrawArrays(GL_TRIANGLES, competition_row_quads[index] * 6, 6);
      }
      if (competition_focus_quad >= 0) {
        use_rounded_rect(&competition_row_style);
        glUniform4f(gl.loc_color, 1.0f, 0.91f, 0.02f,
                    0.98f * competition_menu_mix);
        glDrawArrays(GL_TRIANGLES, competition_focus_quad * 6, 6);
      }
      use_rounded_rect(&competition_value_style);
      glUniform4f(gl.loc_color, 0.055f, 0.16f, 0.30f,
                  0.98f * competition_menu_mix);
      for (uint32_t index = 0; index < 12u; index++) {
        if (competition_value_plate_quads[index])
          glDrawArrays(GL_TRIANGLES, competition_value_plate_quads[index] * 6,
                       6);
      }
    }
    if (competition_display_state == COMPETITION_FRONTEND_CUP_BRACKET ||
        competition_display_state == COMPETITION_FRONTEND_CUP_CHECKPOINT) {
      use_rounded_rect(&competition_row_style);
      glUniform4f(gl.loc_color, 0.025f, 0.095f, 0.18f, 0.98f);
      for (uint32_t index = 0; index < 8u; index++) {
        if (competition_bracket_card_quads[index])
          glDrawArrays(GL_TRIANGLES, competition_bracket_card_quads[index] * 6,
                       6);
      }
    }
    if (!competition_settings_page && !bracket_page) {
      use_rounded_rect(NULL);
      glUniform1f(gl.loc_solid, 0.0f);
      /* main_menu_icons_tex is an RGBA copy of a luminance mask.  Sampling
       * it through the font-mask path preserves transparent atlas space on
       * all Switch GPU drivers and matches the main menu exactly. */
      glUniform1f(gl.loc_image, 0.0f);
      glBindTexture(GL_TEXTURE_2D, gl.main_menu_icons_tex);
      for (uint32_t index = 0; index < 12u; index++) {
        if (!competition_icon_quads[index])
          continue;
        const float focused = index == competition_display_focus ? 1.0f : 0.0f;
        glUniform4f(gl.loc_color,
                    0.72f + (0.02f - 0.72f) * focused,
                    0.80f + (0.10f - 0.80f) * focused,
                    0.96f + (0.34f - 0.96f) * focused,
                    competition_menu_mix * (0.94f + 0.06f * focused));
        glDrawArrays(GL_TRIANGLES, competition_icon_quads[index] * 6, 6);
      }
      glUniform1f(gl.loc_image, 0.0f);
    }
    use_rounded_rect(NULL);
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform1f(gl.loc_image, 0.0f);
    glBindTexture(GL_TEXTURE_2D, gl.efootball_tex);
    if (competition_team_page)
      glUniform4f(gl.loc_color, 0.03f, 0.09f, 0.17f, 1.0f);
    else
      glUniform4f(gl.loc_color, 0.96f, 0.98f, 1.0f,
                  competition_settings_page ? 1.0f : competition_menu_mix);
    glDrawArrays(GL_TRIANGLES, competition_title_first_quad * 6,
                 competition_title_quads * 6);
    if (!competition_team_page) {
      for (uint32_t index = 0; index < 12u; index++) {
        if (!competition_label_quads[index])
          continue;
        const float focused =
            !competition_settings_page && index == competition_display_focus
                ? 1.0f
                : 0.0f;
        const int item_enabled = competition_frontend_item_enabled(index);
        glUniform4f(
            gl.loc_color,
            competition_settings_page
                ? (item_enabled ? 0.98f : 0.52f)
                : 0.95f + (0.015f - 0.95f) * focused,
            competition_settings_page
                ? (item_enabled ? 0.99f : 0.56f)
                : 0.97f + (0.075f - 0.97f) * focused,
            competition_settings_page
                ? (item_enabled ? 1.0f : 0.64f)
                : 1.00f + (0.29f - 1.00f) * focused,
            competition_settings_page ? 1.0f
                                       : competition_menu_mix *
                                             (0.95f + 0.05f * focused));
        glDrawArrays(GL_TRIANGLES, competition_label_first_quad[index] * 6,
                     competition_label_quads[index] * 6);
        if (competition_value_quads[index]) {
          glUniform4f(gl.loc_color, item_enabled ? 0.98f : 0.58f,
                      item_enabled ? 0.99f : 0.62f,
                      item_enabled ? 1.0f : 0.70f, competition_menu_mix);
          glDrawArrays(GL_TRIANGLES, competition_value_first_quad[index] * 6,
                       competition_value_quads[index] * 6);
        }
      }
    }
    if (competition_team_page && !competition_team_picker_page) {
      const uint32_t slot_count = competition_frontend_cup_player_count() > 8u
                                      ? 8u
                                      : competition_frontend_cup_player_count();
      for (uint32_t index = 0; index < slot_count; index++) {
        glUniform4f(gl.loc_color, 0.03f, 0.09f, 0.17f, 1.0f);
        glDrawArrays(GL_TRIANGLES, competition_label_first_quad[index] * 6,
                     competition_label_quads[index] * 6);
        glDrawArrays(GL_TRIANGLES, competition_value_first_quad[index] * 6,
                     competition_value_quads[index] * 6);
      }
    }
    if (competition_team_picker_page) {
      if (competition_team_picker_title_quads) {
        glUniform4f(gl.loc_color, 0.03f, 0.09f, 0.17f, 1.0f);
        glDrawArrays(GL_TRIANGLES,
                     competition_team_picker_title_first_quad * 6,
                     competition_team_picker_title_quads * 6);
        glUniform4f(gl.loc_color, 0.98f, 0.99f, 1.0f, 1.0f);
        glDrawArrays(GL_TRIANGLES,
                     competition_team_picker_value_first_quad * 6,
                     competition_team_picker_value_quads * 6);
      }
      glUniform4f(gl.loc_color, 0.03f, 0.09f, 0.17f, 0.96f);
      for (uint32_t item = 0; item < 5u; item++) {
        if (competition_team_picker_row_text_quads[item])
          glDrawArrays(GL_TRIANGLES,
                       competition_team_picker_row_text_first_quad[item] * 6,
                       competition_team_picker_row_text_quads[item] * 6);
      }
    }
    if (!competition_team_page && competition_settings_page &&
        competition_display_focus < 12u &&
        competition_label_quads[competition_display_focus]) {
      /* The Hub settings renderer repaints the focused label dark over the
       * light row, leaving every other label white. */
      glUniform4f(gl.loc_color, 0.025f, 0.055f, 0.095f, 1.0f);
      glDrawArrays(GL_TRIANGLES,
                   competition_label_first_quad[competition_display_focus] * 6,
                   competition_label_quads[competition_display_focus] * 6);
    }
    if (competition_settings_page && !competition_team_picker_page) {
      const uint32_t action_focus =
          competition_team_page ? competition_frontend_cup_player_count()
                                : 8u;
      const int invert = competition_display_focus == action_focus &&
                         competition_frontend_item_enabled(action_focus);
      glUniform4f(gl.loc_color, invert ? 0.03f : 0.98f,
                  invert ? 0.09f : 0.99f,
                  invert ? 0.17f : 1.0f, 1.0f);
      glDrawArrays(GL_TRIANGLES, competition_full_action_text_first_quad * 6,
                   competition_full_action_text_quads * 6);
    }
    glUniform4f(gl.loc_color, 0.98f, 0.99f, 1.0f, competition_menu_mix);
    for (uint32_t index = 0; index < 8u; index++) {
      if (competition_bracket_text_quads[index])
        glDrawArrays(GL_TRIANGLES,
                     competition_bracket_text_first_quad[index] * 6,
                     competition_bracket_text_quads[index] * 6);
    }
    if (competition_status_quads)
      glDrawArrays(GL_TRIANGLES, competition_status_first_quad * 6,
                   competition_status_quads * 6);
    glUniform4f(gl.loc_color, 0.78f, 0.88f, 1.0f, 0.95f * competition_menu_mix);
    if (competition_helper_quads)
      glDrawArrays(GL_TRIANGLES, competition_helper_first_quad * 6,
                   competition_helper_quads * 6);
    glBindTexture(GL_TEXTURE_2D, gl.tex);
  }
  if (custom_gameplan) {
    static const float side_accent[2][3] = {
        {0.08f, 0.72f, 0.96f},
        {0.96f, 0.18f, 0.34f},
    };

    use_rounded_rect(NULL);
    glBindTexture(GL_TEXTURE_2D, gl.team_select_bg_tex);
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform1f(gl.loc_image, 1.0f);
    glUniform4f(gl.loc_color, 0.38f, 0.46f, 0.60f, 1.0f);
    glDrawArrays(GL_TRIANGLES,
                 prematch_gameplan_backdrop_first_quad * 6,
                 prematch_gameplan_backdrop_quads * 6);

    glBindTexture(GL_TEXTURE_2D, gl.tex);
    glUniform1f(gl.loc_image, 0.0f);
    glUniform1f(gl.loc_solid, 1.0f);
    use_rounded_rect(&prematch_gameplan_panel_style);
    glUniform4f(gl.loc_color, 0.96f, 0.98f, 1.0f, 0.74f);
    glDrawArrays(GL_TRIANGLES, prematch_gameplan_panel_first_quad * 6,
                 prematch_gameplan_panel_quads * 6);
    use_rounded_rect(NULL);

    for (uint32_t side = 0; side < 2; side++) {
      glUniform4f(gl.loc_color, side_accent[side][0] * 0.16f,
                  side_accent[side][1] * 0.16f,
                  side_accent[side][2] * 0.16f, 0.98f);
      glDrawArrays(GL_TRIANGLES,
                   prematch_gameplan_header_first_quad[side] * 6,
                   prematch_gameplan_header_quads[side] * 6);
    }

    glUniform4f(gl.loc_color, 0.020f, 0.235f, 0.145f, 0.98f);
    for (uint32_t side = 0; side < 2; side++)
      glDrawArrays(GL_TRIANGLES,
                   prematch_gameplan_pitch_first_quad[side] * 6,
                   prematch_gameplan_pitch_quads[side] * 6);
    glUniform4f(gl.loc_color, 0.035f, 0.315f, 0.190f, 0.78f);
    for (uint32_t side = 0; side < 2; side++)
      glDrawArrays(GL_TRIANGLES,
                   prematch_gameplan_stripe_first_quad[side] * 6,
                   prematch_gameplan_stripe_quads[side] * 6);
    glUniform4f(gl.loc_color, 0.86f, 0.94f, 0.93f, 0.72f);
    for (uint32_t side = 0; side < 2; side++)
      glDrawArrays(GL_TRIANGLES,
                   prematch_gameplan_line_first_quad[side] * 6,
                   prematch_gameplan_line_quads[side] * 6);

    glUniform4f(gl.loc_color, 0.96f, 0.98f, 1.0f, 0.88f);
    for (uint32_t side = 0; side < 2; side++) {
      use_rounded_rect(&prematch_gameplan_modal_style[side]);
      glDrawArrays(GL_TRIANGLES,
                   prematch_gameplan_modal_first_quad[side] * 6,
                   prematch_gameplan_modal_quads[side] * 6);
    }
    use_rounded_rect(NULL);
    glUniform4f(gl.loc_color, 0.94f, 0.97f, 1.0f, 0.76f);
    for (uint32_t side = 0; side < 2; side++)
      glDrawArrays(GL_TRIANGLES,
                   prematch_gameplan_neutral_first_quad[side] * 6,
                   prematch_gameplan_neutral_quads[side] * 6);

    use_rounded_rect(&prematch_gameplan_waiting_style);
    glUniform4f(gl.loc_color, 0.98f, 0.99f, 1.0f, 0.92f);
    for (uint32_t side = 0; side < 2; side++)
      glDrawArrays(GL_TRIANGLES,
                   prematch_gameplan_waiting_first_quad[side] * 6,
                   prematch_gameplan_waiting_quads[side] * 6);
    use_rounded_rect(NULL);

    for (uint32_t side = 0; side < 2; side++) {
      glUniform4f(gl.loc_color, side_accent[side][0],
                  side_accent[side][1], side_accent[side][2], 0.80f);
      glDrawArrays(GL_TRIANGLES,
                   prematch_gameplan_accent_first_quad[side] * 6,
                   prematch_gameplan_accent_quads[side] * 6);
    }

    // The four actions are detached from the content panel, with rounded
    // white buttons and a side-colored active button.
    use_rounded_rect(&prematch_gameplan_action_style);
    glUniform4f(gl.loc_color, 0.96f, 0.98f, 1.0f, 0.80f);
    for (uint32_t side = 0; side < 2; side++) {
      if (custom_gameplan_exhibition && side == 1)
        continue;
      glDrawArrays(GL_TRIANGLES,
                   prematch_gameplan_action_first_quad[side] * 6,
                   prematch_gameplan_action_quads[side] * 6);
    }
    for (uint32_t side = 0; side < 2; side++) {
      if (custom_gameplan_exhibition && side == 1)
        continue;
      glUniform4f(gl.loc_color, side_accent[side][0],
                  side_accent[side][1], side_accent[side][2], 0.92f);
      glDrawArrays(GL_TRIANGLES,
                   prematch_gameplan_action_selected_first_quad[side] * 6,
                   prematch_gameplan_action_selected_quads[side] * 6);
    }
    use_rounded_rect(NULL);

    // Portraits are uploaded lazily from the native common/player archive.
    // Draw each quad with its own cached texture; the surrounding card and
    // text remain in the normal solid/font batches above and below it.
    {
      GLint previous_sampler = 0;
      if (gl.bind_sampler) {
        glGetIntegerv(GL_SAMPLER_BINDING, &previous_sampler);
        gl.bind_sampler(0, 0);
      }
      glUniform1f(gl.loc_solid, 0.0f);
      glUniform1f(gl.loc_image, 1.0f);
      glUniform1f(gl.loc_image_curve, 0.0f);
      glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, 1.0f);
      for (uint32_t side = 0; side < 2; side++) {
        const uint32_t page =
            pes_controller_custom_prematch_gameplan_page(side);
        if (page != PES_PREMATCH_GAMEPLAN_PAGE_ROOT &&
            page != PES_PREMATCH_GAMEPLAN_PAGE_SUBSTITUTE)
          continue;
        const uint32_t count =
            pes_controller_custom_prematch_gameplan_field_count(side);
        for (uint32_t index = 0; index < count && index < 40; index++) {
          const int quad = prematch_gameplan_portrait_quad[side][0][index];
          if (quad < 0)
            continue;
          const uint32_t portrait_id =
              pes_controller_custom_prematch_gameplan_player_portrait_id(
                  side, 1u, index);
          const GLuint texture = gameplan_portrait_texture(portrait_id);
          if (!texture)
            continue;
          glBindTexture(GL_TEXTURE_2D, texture);
          glDrawArrays(GL_TRIANGLES, quad * 6, 6);
        }
      }
      if (gl.bind_sampler)
        gl.bind_sampler(0, (GLuint)previous_sampler);
      glBindTexture(GL_TEXTURE_2D, gl.tex);
      glUniform1f(gl.loc_image, 0.0f);
      glUniform1f(gl.loc_solid, 1.0f);
    }

    glUniform4f(gl.loc_color, 0.012f, 0.018f, 0.024f, 0.95f);
    use_rounded_rect(&prematch_gameplan_field_plate_style);
    for (uint32_t side = 0; side < 2; side++)
      glDrawArrays(GL_TRIANGLES,
                   prematch_gameplan_field_plate_first_quad[side] * 6,
                   prematch_gameplan_field_plate_quads[side] * 6);
    use_rounded_rect(NULL);

    static const float gameplan_role_colors[4][3] = {
        {0.96f, 0.55f, 0.10f}, // goalkeeper
        {0.08f, 0.45f, 0.88f}, // defenders
        {0.05f, 0.68f, 0.36f}, // midfielders
        {0.88f, 0.18f, 0.20f}, // forwards
    };
    glUniform1f(gl.loc_solid, 1.0f);
    glUniform1f(gl.loc_image, 0.0f);
    use_rounded_rect(NULL);
    for (uint32_t role_band = 0; role_band < 4; role_band++) {
      if (!prematch_gameplan_role_plate_quads[role_band])
        continue;
      glUniform4f(gl.loc_color, gameplan_role_colors[role_band][0],
                  gameplan_role_colors[role_band][1],
                  gameplan_role_colors[role_band][2], 0.92f);
      glDrawArrays(GL_TRIANGLES,
                   prematch_gameplan_role_plate_first_quad[role_band] * 6,
                   prematch_gameplan_role_plate_quads[role_band] * 6);
    }

    glUniform1f(gl.loc_circle, 1.0f);
    glUniform1f(gl.loc_circle_feather, 0.020f);
    glUniform4f(gl.loc_color, 0.82f, 0.86f, 0.90f, 0.96f);
    for (uint32_t side = 0; side < 2; side++)
      glDrawArrays(GL_TRIANGLES,
                   prematch_gameplan_picker_foot_first_quad[side] * 6,
                   prematch_gameplan_picker_foot_quads[side] * 6);
    glUniform1f(gl.loc_circle, 0.0f);

    for (uint32_t side = 0; side < 2; side++) {
      glUniform4f(gl.loc_color, 0.04f, 0.58f, 1.0f, 1.0f);
      glDrawArrays(GL_TRIANGLES,
                   prematch_gameplan_selected_outline_first_quad[side] * 6,
                   prematch_gameplan_selected_outline_quads[side] * 6);
    }

    glUniform1f(gl.loc_solid, 1.0f);
    glUniform4f(gl.loc_color, 0.01f, 0.02f, 0.035f, 0.92f);
    use_rounded_rect(&prematch_gameplan_context_plate_style);
    for (uint32_t side = 0; side < 2; side++)
      glDrawArrays(GL_TRIANGLES,
                   prematch_gameplan_context_plate_first_quad[side] * 6,
                   prematch_gameplan_context_plate_quads[side] * 6);
    use_rounded_rect(NULL);

    // Focus is a pointer, while a committed player selection is the blue
    // corner-only frame above. This mirrors the console distinction between
    // navigation and an actual pending swap.
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform1f(gl.loc_cursor, 1.0f);
    for (uint32_t side = 0; side < 2; side++) {
      if (!prematch_gameplan_focus_outline_quads[side])
        continue;
      glUniform1f(gl.loc_cursor_border, 2.2f);
      glUniform4f(gl.loc_color, 0.01f, 0.03f, 0.04f, 0.90f);
      glDrawArrays(GL_TRIANGLES,
                   prematch_gameplan_focus_outline_first_quad[side] * 6,
                   prematch_gameplan_focus_outline_quads[side] * 6);
      glUniform1f(gl.loc_cursor_border, 0.0f);
      glUniform4f(gl.loc_color, 0.98f, 0.99f, 1.0f, 1.0f);
      glDrawArrays(GL_TRIANGLES,
                   prematch_gameplan_focus_outline_first_quad[side] * 6,
                   prematch_gameplan_focus_outline_quads[side] * 6);
    }
    glUniform1f(gl.loc_cursor, 0.0f);
    glUniform1f(gl.loc_solid, 1.0f);

    glBindTexture(GL_TEXTURE_2D, gl.badge_tex);
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform1f(gl.loc_image, 1.0f);
    glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, 1.0f);
    for (uint32_t side = 0; side < 2; side++)
      glDrawArrays(GL_TRIANGLES,
                   prematch_gameplan_badge_first_quad[side] * 6,
                   prematch_gameplan_badge_quads[side] * 6);

    glBindTexture(GL_TEXTURE_2D, gl.efootball_tex);
    glUniform1f(gl.loc_image, 0.0f);
    glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, 1.0f);
    glDrawArrays(GL_TRIANGLES,
                 prematch_gameplan_white_text_first_quad * 6,
                 prematch_gameplan_white_text_quads * 6);
    // Body copy sits on translucent white surfaces, while the header keeps
    // the native white-on-color treatment. Repaint only body/action ranges.
    glUniform4f(gl.loc_color, 0.025f, 0.055f, 0.095f, 1.0f);
    for (uint32_t side = 0; side < 2; side++) {
      glDrawArrays(GL_TRIANGLES,
                   prematch_gameplan_body_text_first_quad[side] * 6,
                   prematch_gameplan_body_text_quads[side] * 6);
      if (!custom_gameplan_exhibition || side == 0)
        glDrawArrays(GL_TRIANGLES,
                     prematch_gameplan_action_text_first_quad[side] * 6,
                     prematch_gameplan_action_text_quads[side] * 6);
      glDrawArrays(GL_TRIANGLES,
                   prematch_gameplan_waiting_text_first_quad[side] * 6,
                   prematch_gameplan_waiting_text_quads[side] * 6);
    }
    glUniform4f(gl.loc_color, 0.05f, 0.68f, 0.30f, 1.0f);
    for (uint32_t side = 0; side < 2; side++) {
      for (uint32_t metric = 0; metric < 2; metric++) {
        if (prematch_gameplan_auto_gain_first[side][metric] < 0 ||
            !prematch_gameplan_auto_gain_quads[side][metric])
          continue;
        glDrawArrays(GL_TRIANGLES,
                     prematch_gameplan_auto_gain_first[side][metric] * 6,
                     prematch_gameplan_auto_gain_quads[side][metric] * 6);
      }
    }
    glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, 1.0f);
    for (uint32_t side = 0; side < 2; side++) {
      glDrawArrays(GL_TRIANGLES,
                   prematch_gameplan_header_text_first_quad[side] * 6,
                   prematch_gameplan_header_text_quads[side] * 6);
      glDrawArrays(GL_TRIANGLES,
                   prematch_gameplan_focus_text_first_quad[side] * 6,
                   prematch_gameplan_focus_text_quads[side] * 6);
      glDrawArrays(GL_TRIANGLES,
                   prematch_gameplan_field_text_first_quad[side] * 6,
                   prematch_gameplan_field_text_quads[side] * 6);
    }
    // Field role abbreviations use the native GK/DF/MF/FW color language;
    // names remain white and OVR keeps its independent value spectrum.
    for (uint32_t side = 0; side < 2; side++) {
      for (uint32_t index = 0; index < PREMATCH_GAMEPLAN_FIELD_SLOTS;
           index++) {
        if (prematch_gameplan_field_role_first[side][index] < 0 ||
            !prematch_gameplan_field_role_quads[side][index])
          continue;
        const uint32_t role_band =
            prematch_gameplan_field_role_band[side][index];
        glUniform4f(gl.loc_color, gameplan_role_colors[role_band][0],
                    gameplan_role_colors[role_band][1],
                    gameplan_role_colors[role_band][2], 1.0f);
        glDrawArrays(GL_TRIANGLES,
                     prematch_gameplan_field_role_first[side][index] * 6,
                     prematch_gameplan_field_role_quads[side][index] * 6);
      }
    }
    glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, 1.0f);
    glDrawArrays(GL_TRIANGLES,
                 prematch_gameplan_role_text_first_quad * 6,
                 prematch_gameplan_role_text_quads * 6);
    glUniform4f(gl.loc_color, 0.96f, 0.98f, 1.0f, 1.0f);
    glDrawArrays(GL_TRIANGLES,
                 prematch_gameplan_muted_text_first_quad * 6,
                 prematch_gameplan_muted_text_quads * 6);
    for (uint32_t side = 0; side < 2; side++) {
      for (uint32_t index = 0; index < PREMATCH_GAMEPLAN_FIELD_SLOTS;
           index++) {
        if (prematch_gameplan_field_metric_first[side][index] < 0 ||
            !prematch_gameplan_field_metric_quads[side][index])
          continue;
        glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, 1.0f);
        glDrawArrays(GL_TRIANGLES,
                     prematch_gameplan_field_metric_first[side][index] * 6,
                     prematch_gameplan_field_metric_quads[side][index] * 6);
      }
      for (uint32_t slot = 0; slot < PREMATCH_GAMEPLAN_VISIBLE_BENCH;
           slot++) {
        if (prematch_gameplan_bench_metric_first[side][slot] < 0 ||
            !prematch_gameplan_bench_metric_quads[side][slot])
          continue;
        glUniform4f(gl.loc_color, 0.015f, 0.025f, 0.035f, 1.0f);
        glDrawArrays(GL_TRIANGLES,
                     prematch_gameplan_bench_metric_first[side][slot] * 6,
                     prematch_gameplan_bench_metric_quads[side][slot] * 6);
      }
      for (uint32_t slot = 0; slot < PREMATCH_GAMEPLAN_VISIBLE_PICKER;
           slot++) {
        if (prematch_gameplan_picker_metric_first[side][slot] < 0 ||
            !prematch_gameplan_picker_metric_quads[side][slot])
          continue;
        glUniform4f(gl.loc_color, 0.015f, 0.025f, 0.035f, 1.0f);
        glDrawArrays(GL_TRIANGLES,
                     prematch_gameplan_picker_metric_first[side][slot] * 6,
                     prematch_gameplan_picker_metric_quads[side][slot] * 6);
      }
    }
    // A blue player name is a quieter active-assignment cue than an extra
    // checkmark and leaves the compact POS / NAME / FOOT / PWR row untouched.
    glUniform4f(gl.loc_color, 0.04f, 0.46f, 0.96f, 1.0f);
    for (uint32_t side = 0; side < 2; side++) {
      for (uint32_t slot = 0; slot < PREMATCH_GAMEPLAN_VISIBLE_PICKER;
           slot++) {
        if (prematch_gameplan_picker_active_text_first[side][slot] < 0 ||
            !prematch_gameplan_picker_active_text_quads[side][slot])
          continue;
        glDrawArrays(
            GL_TRIANGLES,
            prematch_gameplan_picker_active_text_first[side][slot] * 6,
            prematch_gameplan_picker_active_text_quads[side][slot] * 6);
      }
    }
    for (uint32_t side = 0; side < 2; side++) {
      glUniform4f(gl.loc_color, side_accent[side][0],
                  side_accent[side][1], side_accent[side][2], 1.0f);
      glDrawArrays(GL_TRIANGLES,
                   prematch_gameplan_accent_text_first_quad[side] * 6,
                   prematch_gameplan_accent_text_quads[side] * 6);
    }
    glBindTexture(GL_TEXTURE_2D, gl.tex);
    glUniform1f(gl.loc_solid, 0.0f);
  } else if (custom_popup) {
    int custom_offset = 0;
    if (pause_settings_popup || cup_settings_popup ||
        custom_2p_team_selector || custom_2p_prematch_hub_raw ||
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
      if (custom_loading_spinner_quads) {
        glUniform4f(gl.loc_color, 0.96f, 0.98f, 1.0f, 0.94f);
        glDrawArrays(GL_TRIANGLES, custom_loading_spinner_first_quad * 6,
                     custom_loading_spinner_quads * 6);
      }
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
    else if (custom_hub_settings_popup || custom_hub_choice_page ||
             custom_main_menu_dark_popup)
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
    else if (custom_hub_settings_popup || custom_hub_choice_page ||
             custom_main_menu_dark_popup)
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
    else if (custom_main_menu_dark_popup)
      glUniform4f(gl.loc_color, 0.08f, 0.30f, 0.50f, 0.82f);
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
    else if (custom_hub_settings_popup || custom_hub_choice_page ||
             custom_main_menu_dark_popup)
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
    if (custom_hub_settings_popup || custom_hub_choice_page ||
        custom_main_menu_dark_popup)
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
    else if (cup_settings_popup &&
             competition_frontend_cup_setting_focus() ==
                 competition_frontend_cup_setting_count())
      glUniform4f(gl.loc_color, 0.08f, 0.57f, 0.91f, 1.0f);
    else if (custom_hub_settings_popup || custom_hub_choice_page ||
             custom_main_menu_dark_popup)
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
    // Button art is rendered by the unified Switch helper pass. Preserve the
    // category offsets here without repainting the same quads as circles.
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform4f(gl.loc_color, 0.98f, 0.99f, 1.0f, 1.0f);
    custom_offset += custom_action_key_bg_quads;
    custom_offset += custom_back_key_bg_quads;
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
  if (cinematic_helper_text_quads) {
    glBindTexture(GL_TEXTURE_2D, gl.efootball_tex);
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform2f(gl.loc_off, 0.0f, 0.0f);
    glUniform4f(gl.loc_color, 0.95f, 0.97f, 1.0f, 1.0f);
    glDrawArrays(GL_TRIANGLES, cinematic_helper_text_first_quad * 6,
                 cinematic_helper_text_quads * 6);
    glBindTexture(GL_TEXTURE_2D, gl.tex);
  }
  if (pause_skin) {
    glUniform2f(gl.loc_off, 0.0f, 0.0f);
    use_rounded_rect(NULL);
    glUniform1f(gl.loc_circle, 0.0f);
    glUniform1f(gl.loc_cursor, 0.0f);
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform1f(gl.loc_image, 1.0f);
    glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, 1.0f);
    glBindTexture(GL_TEXTURE_2D, gl.team_select_bg_tex);
    glDrawArrays(GL_TRIANGLES, pause_background * 6, 6);
    glBindTexture(GL_TEXTURE_2D, gl.badge_tex);
    glDrawArrays(GL_TRIANGLES, pause_badges * 6, 12);
    glUniform1f(gl.loc_image, 0.0f);
    glBindTexture(GL_TEXTURE_2D, gl.efootball_tex);
    glDrawArrays(GL_TRIANGLES, pause_header * 6, pause_header_count * 6);
    glUniform1f(gl.loc_image, 0.0f);
    glUniform1f(gl.loc_solid, 1.0f);
    glUniform1f(gl.loc_circle, 0.0f);
    glUniform1f(gl.loc_cursor, 0.0f);
    use_rounded_rect(&pause_skin_style);
    for (int i = 0; i < 4; ++i) {
      if (i == pause_skin_focus) glUniform4f(gl.loc_color, 0.12f, 0.75f, 0.93f, 1.0f);
      else glUniform4f(gl.loc_color, 0.93f, 0.95f, 0.99f, 0.98f);
      glDrawArrays(GL_TRIANGLES, pause_skin_cards[i] * 6, 6);
    }
    use_rounded_rect(NULL);
    const RoundedRectStyle stats_style = {0.64f * screen_width, 0.465f * screen_height,
                                          0.024f * screen_height};
    use_rounded_rect(&stats_style);
    glUniform4f(gl.loc_color, 0.02f, 0.06f, 0.10f, 0.76f);
    glDrawArrays(GL_TRIANGLES, pause_stats_panel * 6, 6);
    use_rounded_rect(NULL);
    glUniform1f(gl.loc_solid, 0.0f);
    glBindTexture(GL_TEXTURE_2D, gl.efootball_tex);
    glUniform4f(gl.loc_color, 0.02f, 0.05f, 0.14f, 1.0f);
    glDrawArrays(GL_TRIANGLES, pause_skin_text * 6, pause_skin_text_quads * 6);
    glUniform4f(gl.loc_color, 0.95f, 0.97f, 1.0f, 1.0f);
    glDrawArrays(GL_TRIANGLES, pause_stats_text * 6, pause_stats_quads * 6);
    glDrawArrays(GL_TRIANGLES, pause_helper_text * 6,
                 pause_helper_text_quads * 6);
    glBindTexture(GL_TEXTURE_2D, gl.tex);
  }
  if (result_skin) {
    // Same draw order, textures and colours as the pause skin above.
    use_rounded_rect(NULL);
    glUniform1f(gl.loc_circle, 0.0f);
    glUniform1f(gl.loc_cursor, 0.0f);
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform1f(gl.loc_image, 1.0f);
    glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, 1.0f);
    glBindTexture(GL_TEXTURE_2D, gl.team_select_bg_tex);
    glDrawArrays(GL_TRIANGLES, result_background * 6, 6);
    glBindTexture(GL_TEXTURE_2D, gl.badge_tex);
    glDrawArrays(GL_TRIANGLES, result_badges * 6, 12);
    glUniform1f(gl.loc_image, 0.0f);
    glBindTexture(GL_TEXTURE_2D, gl.efootball_tex);
    glDrawArrays(GL_TRIANGLES, result_header * 6, result_header_count * 6);
    glUniform1f(gl.loc_solid, 1.0f);
    use_rounded_rect(&result_card_style);
    for (int i = 0; i < result_card_count; ++i) {
      if (i == result_focus) glUniform4f(gl.loc_color, 0.12f, 0.75f, 0.93f, 1.0f);
      else glUniform4f(gl.loc_color, 0.93f, 0.95f, 0.99f, 0.98f);
      glDrawArrays(GL_TRIANGLES, result_cards[i] * 6, 6);
    }
    use_rounded_rect(NULL);
    const RoundedRectStyle result_stats_style = {0.64f * screen_width,
                                                 0.465f * screen_height,
                                                 0.024f * screen_height};
    use_rounded_rect(&result_stats_style);
    glUniform4f(gl.loc_color, 0.02f, 0.06f, 0.10f, 0.76f);
    glDrawArrays(GL_TRIANGLES, result_stats_panel * 6, 6);
    use_rounded_rect(NULL);
    glUniform1f(gl.loc_solid, 0.0f);
    glBindTexture(GL_TEXTURE_2D, gl.efootball_tex);
    glUniform4f(gl.loc_color, 0.02f, 0.05f, 0.14f, 1.0f);
    glDrawArrays(GL_TRIANGLES, result_card_text * 6, result_card_text_quads * 6);
    glUniform4f(gl.loc_color, 0.95f, 0.97f, 1.0f, 1.0f);
    glDrawArrays(GL_TRIANGLES, result_stats_text * 6, result_stats_quads * 6);
    glDrawArrays(GL_TRIANGLES, result_helper_text * 6,
                 result_helper_text_quads * 6);
    glBindTexture(GL_TEXTURE_2D, gl.tex);
  }
  // Draw all helper glyphs after custom full-page backgrounds and text, but
  // before transition covers/confirmation modals that intentionally hide
  // their underlying controls.
  if (switch_helper_count) {
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform1f(gl.loc_image, 1.0f);
    glUniform1f(gl.loc_round_rect, 0.0f);
    glUniform1f(gl.loc_cursor, 0.0f);
    glUniform1f(gl.loc_circle, 0.0f);
    glUniform2f(gl.loc_off, 0.0f, 0.0f);
    glUniform4f(gl.loc_color, 1, 1, 1, 1);
    for (int i = 0; i < switch_helper_count; ++i) {
      glBindTexture(GL_TEXTURE_2D, switch_helper_textures[i]);
      glDrawArrays(GL_TRIANGLES, switch_helper_quads[i] * 6, 6);
    }
    glUniform1f(gl.loc_image, 0.0f);
    glBindTexture(GL_TEXTURE_2D, gl.tex);
  }
  if (result_transition) {
    // Drawn last so it covers the custom result skin as well as the native
    // page underneath it.
    use_rounded_rect(NULL);
    glUniform1f(gl.loc_circle, 0.0f);
    glUniform1f(gl.loc_cursor, 0.0f);
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform1f(gl.loc_image, 1.0f);
    glUniform4f(gl.loc_color, 1, 1, 1, 1);
    glBindTexture(GL_TEXTURE_2D, gl.team_select_bg_tex);
    glDrawArrays(GL_TRIANGLES, result_cover_background * 6, 6);
    glUniform1f(gl.loc_image, 0.0f);
    glUniform1f(gl.loc_solid, 1.0f);
    glUniform4f(gl.loc_color, 0.92f, 0.96f, 1.0f, 0.94f);
    glDrawArrays(GL_TRIANGLES, result_cover_spinner * 6,
                 result_cover_spinner_count * 6);
    glUniform1f(gl.loc_solid, 0.0f);
    glBindTexture(GL_TEXTURE_2D, gl.tex);
  }
  if (gameplan_locked_row_count) {
    use_rounded_rect(NULL);
    glUniform1f(gl.loc_image, 0.0f);
    glUniform1f(gl.loc_solid, 1.0f);
    glUniform4f(gl.loc_color, 0.43f, 0.46f, 0.51f, 0.68f);
    glDrawArrays(GL_TRIANGLES, gameplan_locked_rows * 6, gameplan_locked_row_count * 6);
    glUniform1f(gl.loc_solid, 0.0f);
  }
  if (pause_skin && pause_transition) {
    use_rounded_rect(NULL);
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform1f(gl.loc_image, 1.0f);
    glUniform4f(gl.loc_color, 1, 1, 1, 1);
    glBindTexture(GL_TEXTURE_2D, gl.team_select_bg_tex);
    glDrawArrays(GL_TRIANGLES, pause_background * 6, 6);
    glUniform1f(gl.loc_image, 0.0f);
    glUniform1f(gl.loc_solid, 1.0f);
    glUniform4f(gl.loc_color, 0.92f, 0.96f, 1.0f, 0.94f);
    glDrawArrays(GL_TRIANGLES, pause_transition_spinner * 6, pause_transition_spinner_count * 6);
    glUniform1f(gl.loc_solid, 0.0f);
    glBindTexture(GL_TEXTURE_2D, gl.tex);
  }
  if (pause_skin && pes_controller_pause_top_menu_confirm_active()) {
    use_rounded_rect(NULL);
    glUniform1f(gl.loc_image, 0.0f);
    glUniform1f(gl.loc_solid, 1.0f);
    glUniform4f(gl.loc_color, 0.0f, 0.0f, 0.0f, 0.56f);
    glDrawArrays(GL_TRIANGLES, pause_confirm_backdrop * 6, 6);
    use_rounded_rect(&pause_confirm_panel_style);
    glUniform4f(gl.loc_color, 0.97f, 0.98f, 1.0f, 0.99f);
    glDrawArrays(GL_TRIANGLES, pause_confirm_panel * 6, 6);
    use_rounded_rect(&pause_confirm_button_style);
    const uint32_t confirm_focus = pes_controller_pause_top_menu_confirm_focus();
    for (int i = 0; i < 2; ++i) {
      if ((uint32_t)i == confirm_focus)
        glUniform4f(gl.loc_color, 0.10f, 0.70f, 0.92f, 1.0f);
      else
        glUniform4f(gl.loc_color, 0.89f, 0.92f, 0.97f, 1.0f);
      glDrawArrays(GL_TRIANGLES, pause_confirm_buttons[i] * 6, 6);
    }
    use_rounded_rect(NULL);
    glBindTexture(GL_TEXTURE_2D, gl.efootball_tex);
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform4f(gl.loc_color, 0.025f, 0.065f, 0.12f, 1.0f);
    glDrawArrays(GL_TRIANGLES, pause_confirm_title * 6, pause_confirm_title_quads * 6);
    glDrawArrays(GL_TRIANGLES, pause_confirm_message * 6, pause_confirm_message_quads * 6);
    for (int i = 0; i < 2; ++i) {
      if ((uint32_t)i == confirm_focus)
        glUniform4f(gl.loc_color, 0.98f, 0.99f, 1.0f, 1.0f);
      else
        glUniform4f(gl.loc_color, 0.025f, 0.065f, 0.12f, 1.0f);
      glDrawArrays(GL_TRIANGLES, pause_confirm_button_text[i] * 6,
                   pause_confirm_button_text_quads[i] * 6);
    }
    glBindTexture(GL_TEXTURE_2D, gl.tex);
  }
  if (gameplan_cursor_quads && !pause_transition) {
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
  if (set_piece_selector || cup_settings_popup || custom_2p_team_selector ||
      custom_2p_prematch_hub_raw || custom_2p_transition)
    glBindTexture(GL_TEXTURE_2D, gl.efootball_tex);
  if (custom_dark_text_quads) {
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform2f(gl.loc_off, 0.0f, 0.0f);
    if (custom_main_menu_dark_popup)
      glUniform4f(gl.loc_color, 0.94f, 0.97f, 1.0f, 1.0f);
    else
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
    if (pause_settings_popup || cup_settings_popup)
      glBindTexture(GL_TEXTURE_2D, gl.efootball_tex);
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
  if (set_piece_selector || cup_settings_popup || custom_2p_team_selector ||
      custom_2p_prematch_hub_raw || custom_2p_transition)
    glBindTexture(GL_TEXTURE_2D, gl.tex);
  if (custom_white_text_quads) {
    if (pause_settings_popup || cup_settings_popup ||
        custom_2p_team_selector || custom_2p_prematch_hub_raw ||
        custom_2p_transition)
      glBindTexture(GL_TEXTURE_2D, gl.efootball_tex);
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform2f(gl.loc_off, 0.0f, 0.0f);
    glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, 1.0f);
    glDrawArrays(GL_TRIANGLES, custom_white_text_first_quad * 6,
                 custom_white_text_quads * 6);
    if (cup_settings_popup || custom_2p_team_selector ||
        custom_2p_prematch_hub_raw ||
        custom_2p_transition)
      glBindTexture(GL_TEXTURE_2D, gl.tex);
  }
  if (custom_key_text_quads && !custom_popup) {
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
    glBindTexture(GL_TEXTURE_2D, gl.tex);
  }

  if (startup_transition) {
    // This cover is deliberately last: no native title/loading geometry may
    // bleed through between PreTitle and the custom title PostInit callback.
    use_rounded_rect(NULL);
    glUniform1f(gl.loc_solid, 0.0f);
    glUniform1f(gl.loc_image, 1.0f);
    glUniform2f(gl.loc_off, 0.0f, 0.0f);
    glUniform4f(gl.loc_color, 1.0f, 1.0f, 1.0f, 1.0f);
    glBindTexture(GL_TEXTURE_2D, gl.team_select_bg_tex);
    glDrawArrays(GL_TRIANGLES, startup_transition_background_quad * 6, 6);
    glBindTexture(GL_TEXTURE_2D, gl.tex);
    glUniform1f(gl.loc_image, 0.0f);
    glUniform1f(gl.loc_solid, 1.0f);
    glUniform4f(gl.loc_color, 0.96f, 0.98f, 1.0f, 0.94f);
    glDrawArrays(GL_TRIANGLES, startup_transition_spinner_first_quad * 6,
                 startup_transition_spinner_quads * 6);
    glUniform1f(gl.loc_solid, 0.0f);
    glBindTexture(GL_TEXTURE_2D, gl.efootball_tex);
    glDrawArrays(GL_TRIANGLES, startup_transition_text_first_quad * 6,
                 startup_transition_text_quads * 6);
    glBindTexture(GL_TEXTURE_2D, gl.tex);
  }

#undef ADD_SWITCH_HELPER

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
  if (gl.bind_sampler)
    gl.bind_sampler(0, (GLuint)prev_sampler);
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
