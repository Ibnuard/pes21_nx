/* Project-authored 5x7 bitmap font used by the Switch HUD overlay. */

#ifndef PES21_FONT_ATLAS_H
#define PES21_FONT_ATLAS_H

#include <stdint.h>

#define FONT_CELL_W 5
#define FONT_CELL_H 7
#define FONT_GLYPHS "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-+:"
#define FONT_COUNT ((int)(sizeof(FONT_GLYPHS) - 1))
#define FONT_COLS FONT_COUNT
#define FONT_ATLAS_W (FONT_CELL_W * FONT_COLS)
#define FONT_ATLAS_H FONT_CELL_H

/* One five-bit row per scanline, most-significant visible bit first. */
static const uint8_t font_glyph_rows[FONT_COUNT][FONT_CELL_H] = {
  {14,17,19,21,25,17,14}, {4,12,4,4,4,4,14},
  {14,17,1,2,4,8,31},    {30,1,1,14,1,1,30},
  {2,6,10,18,31,2,2},    {31,16,16,30,1,1,30},
  {6,8,16,30,17,17,14},  {31,1,2,4,8,8,8},
  {14,17,17,14,17,17,14},{14,17,17,15,1,2,12},
  /* A-Z */
  {14,17,17,31,17,17,17},{30,17,17,30,17,17,30},
  {14,17,16,16,16,17,14},{30,17,17,17,17,17,30},
  {31,16,16,30,16,16,31},{31,16,16,30,16,16,16},
  {14,17,16,23,17,17,15},{17,17,17,31,17,17,17},
  {14,4,4,4,4,4,14},     {7,2,2,2,2,18,12},
  {17,18,20,24,20,18,17},{16,16,16,16,16,16,31},
  {17,27,21,21,17,17,17},{17,25,21,19,17,17,17},
  {14,17,17,17,17,17,14},{30,17,17,30,16,16,16},
  {14,17,17,17,21,18,13},{30,17,17,30,20,18,17},
  {15,16,16,14,1,1,30},  {31,4,4,4,4,4,4},
  {17,17,17,17,17,17,14},{17,17,17,17,17,10,4},
  {17,17,17,21,21,21,10},{17,17,10,4,10,17,17},
  {17,17,10,4,4,4,4},    {31,1,2,4,8,16,31},
  /* - + : */
  {0,0,0,31,0,0,0},      {0,4,4,31,4,4,0},
  {0,4,4,0,4,4,0},
};

static int font_glyph_index(char c) {
  for (int i = 0; i < FONT_COUNT; i++)
    if (FONT_GLYPHS[i] == c)
      return i;
  return -1;
}

#endif
