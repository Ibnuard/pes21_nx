#ifndef PESNX_MANAGER_DEV_SHORTCUT_H
#define PESNX_MANAGER_DEV_SHORTCUT_H
#include <stdint.h>
typedef struct {uint64_t began;unsigned held,fired;} NxManagerDevShortcut;
/* Cobra bits: ZL=5, ZR=6, Y=2. 1 consumes hold; 2 opens once. */
static inline int nx_manager_dev_shortcut(NxManagerDevShortcut *s,uint32_t buttons,int eligible,uint64_t ms){
  const uint32_t combo=(1u<<5)|(1u<<6)|(1u<<2);
  if(!eligible||buttons!=combo){s->held=s->fired=0;s->began=0;return 0;}
  if(!s->held||ms<s->began){s->began=ms;s->held=1;s->fired=0;}
  if(!s->fired&&ms-s->began>=2000){s->fired=1;return 2;}return 1;
}
#endif
