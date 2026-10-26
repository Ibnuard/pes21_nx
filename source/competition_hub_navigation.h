#ifndef PESNX_COMPETITION_HUB_NAVIGATION_H
#define PESNX_COMPETITION_HUB_NAVIGATION_H
#include <stdint.h>
/* Production Master League layout: two feature containers above three panels.
 * Crossing a row edge moves the carousel; shoulder paging clamps at its ends. */
static inline void fnx_hub_navigate_count(uint32_t key,uint32_t *section,uint32_t *focus,uint32_t count) {
  if(count<1u || count>4u)return;
  const int bottom=*focus>=2u;
  if(key&(1u<<10))*focus=*focus==4u || *focus==3u ? 1u : 0u;
  else if(key&(1u<<11))*focus=*focus==1u ? 4u : *focus<2u ? 2u : *focus;
  else if(key&((1u<<4)|(1u<<7))) {
    if((key&(1u<<4)) && *section)(*section)--;
    if((key&(1u<<7)) && *section+1u<count)(*section)++;
    *focus=bottom ? 2u : 0u;
  } else if(key&(1u<<12)) {
    if(*focus==1u || *focus>2u)(*focus)--;
    else if(*section){(*section)--;*focus=bottom ? 4u : 1u;}
  } else if(key&(1u<<13)) {
    if(*focus==0u || (*focus>=2u && *focus<4u))(*focus)++;
    else if(*section+1u<count){(*section)++;*focus=bottom ? 2u : 0u;}
  }
}
static inline void fnx_hub_navigate(uint32_t key,uint32_t *section,uint32_t *focus) {
  fnx_hub_navigate_count(key,section,focus,4u);
}
#endif
