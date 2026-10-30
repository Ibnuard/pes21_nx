#ifndef PESNX_MENU_AXIS_NAVIGATION_H
#define PESNX_MENU_AXIS_NAVIGATION_H
#include <stdint.h>
typedef struct {uint32_t direction;uint64_t next_ms;} NxMenuAxisRepeat;
/* Screen axes are signed, with negative Y pointing up. Face buttons never
 * repeat. A new direction fires immediately, then after 350 ms / each 110 ms. */
static inline uint32_t nx_menu_axis_buttons(uint32_t buttons,int32_t x,int32_t y) {
  const int32_t ax=x<0 ? -x : x,ay=y<0 ? -y : y;
  if(buttons&0x3c00u)return buttons;
  if(ax<16000 && ay<16000)return buttons;
  return buttons | (ax>ay ? (x<0 ? 1u<<12 : 1u<<13) : (y<0 ? 1u<<10 : 1u<<11));
}
static inline uint32_t nx_menu_axis_repeat(NxMenuAxisRepeat *s,uint32_t buttons,uint64_t now) {
  uint32_t d=buttons&0x3c00u;
  if(d!=s->direction){s->direction=d;s->next_ms=now+350u;return 0;}
  if(!d || now<s->next_ms)return 0;
  s->next_ms=now+110u;return d;
}
#endif
