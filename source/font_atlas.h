/* Project-authored 5x7 bitmap digits used by the optional FPS overlay. */

#ifndef PES21_FONT_ATLAS_H
#define PES21_FONT_ATLAS_H

#include <stdint.h>

#define FONT_CELL_W 5
#define FONT_CELL_H 7
#define FONT_COLS 10
#define FONT_FIRST '0'
#define FONT_COUNT 10
#define FONT_ATLAS_W (FONT_CELL_W * FONT_COLS)
#define FONT_ATLAS_H FONT_CELL_H

#define O 0x00
#define X 0xff

static const uint8_t font_atlas[FONT_ATLAS_W * FONT_ATLAS_H] = {
  /* 0     1     2     3     4     5     6     7     8     9 */
  O,X,X,X,O, O,O,X,O,O, O,X,X,X,O, X,X,X,X,O, O,O,O,X,O,
  X,X,X,X,X, O,X,X,X,O, X,X,X,X,X, O,X,X,X,O, O,X,X,X,O,

  X,O,O,O,X, O,X,X,O,O, X,O,O,O,X, O,O,O,O,X, O,O,X,X,O,
  X,O,O,O,O, X,O,O,O,O, O,O,O,O,X, X,O,O,O,X, X,O,O,O,X,

  X,O,O,X,X, O,O,X,O,O, O,O,O,O,X, O,O,O,O,X, O,X,O,X,O,
  X,O,O,O,O, X,O,O,O,O, O,O,O,X,O, X,O,O,O,X, X,O,O,O,X,

  X,O,X,O,X, O,O,X,O,O, O,O,O,X,O, O,X,X,X,O, X,O,O,X,O,
  X,X,X,X,O, X,X,X,X,O, O,O,X,O,O, O,X,X,X,O, O,X,X,X,X,

  X,X,O,O,X, O,O,X,O,O, O,O,X,O,O, O,O,O,O,X, X,X,X,X,X,
  O,O,O,O,X, X,O,O,O,X, O,X,O,O,O, X,O,O,O,X, O,O,O,O,X,

  X,O,O,O,X, O,O,X,O,O, O,X,O,O,O, O,O,O,O,X, O,O,O,X,O,
  O,O,O,O,X, X,O,O,O,X, O,X,O,O,O, X,O,O,O,X, O,O,O,O,X,

  O,X,X,X,O, O,X,X,X,O, X,X,X,X,X, X,X,X,X,O, O,O,O,X,O,
  X,X,X,X,O, O,X,X,X,O, O,X,O,O,O, O,X,X,X,O, O,X,X,X,O,
};

#undef X
#undef O

#endif
