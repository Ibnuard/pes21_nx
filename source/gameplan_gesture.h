#pragma once
#include <stdint.h>
/* Exhibition and online plans share role zones and the hold/drag geometry. */
#define FNX_GAMEPLAN_HOLD_MS 220u
static inline uint32_t fnx_gameplan_zone_role(uint32_t current, uint32_t x,
                                           uint32_t y, uint32_t cycle) {
  if (current == 0) return 0; // Never turn a keeper into an outfield player.
  uint32_t options[4], count = 0;
  if (y <= 17) {
    options[count++] = 1;
    if (x < 30) options[count++] = 2;
    else if (x > 75) options[count++] = 3;
  } else if (y <= 35) {
    options[count++] = 4; options[count++] = 5; options[count++] = 8;
    if (x < 30) options[count++] = 6;
    else if (x > 75) options[count++] = 7;
  } else {
    options[count++] = 11; options[count++] = 12;
    if (x < 30) options[count++] = 9;
    else if (x > 75) options[count++] = 10;
  }
  for (uint32_t i = 0; i < count; i++)
    if (options[i] == current) return options[(i + (cycle != 0)) % count];
  if (y <= 17) return x < 30 ? 2 : x > 75 ? 3 : 1;
  if (y <= 35) return x < 30 ? 6 : x > 75 ? 7 : y <= 23 ? 4 : y <= 29 ? 5 : 8;
  return x < 30 ? 9 : x > 75 ? 10 : y <= 40 ? 11 : 12;
}

static inline void fnx_gameplan_drag(float *x,float *y,int keeper,float dx,float dy,uint64_t elapsed_ms){
  float seconds=(float)(elapsed_ms>50?50:elapsed_ms)/1000.f;
  *x+=dx*96.f*seconds;*y+=dy*96.f*seconds;
  if(*x<0)*x=0;
  if(*x>255)*x=255;
  if(*y<0)*y=0;
  if(*y>255)*y=255;
  if(keeper&&*y<165)*y=165;
}
