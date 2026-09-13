#pragma once
#include <stdint.h>
#define SWITCH_BUTTON_ASSETS(X) \
  X(x, "X") X(y, "Y") X(l, "L") X(zl, "ZL") X(zr, "ZR") \
  X(sl, "SL") X(sr, "SR") X(ls, "LS") X(rs, "RS") X(right, ">") \
  X(up, "UP") X(down, "DOWN") X(left, "LEFT")
#define SWITCH_DECLARE(name, key) \
  extern const uint8_t switch_button_##name##_bin[]; \
  extern const uint8_t switch_button_##name##_bin_end[];
SWITCH_BUTTON_ASSETS(SWITCH_DECLARE)
#undef SWITCH_DECLARE
enum {
#define SWITCH_ENUM(name, key) SWITCH_BUTTON_##name,
  SWITCH_BUTTON_ASSETS(SWITCH_ENUM)
#undef SWITCH_ENUM
  SWITCH_BUTTON_COUNT
};
