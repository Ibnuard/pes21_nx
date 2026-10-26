#ifndef PESNX_MAIN_MENU_LAYOUT_H
#define PESNX_MAIN_MENU_LAYOUT_H
#include <stdint.h>
enum { NX_MAIN_MENU_COUNT=5, NX_MAIN_MENU_ONLINE_NATIVE=4 };
/* Native four tile IDs remain stable; virtual tile 4 never indexes native arrays. */
static inline uint32_t nx_menu_visual(uint32_t native) {
  static const uint8_t rows[5]={0,4,1,3,2};
  return native<5 ? rows[native] : 0;
}
static inline uint32_t nx_menu_native(uint32_t visual) {
  static const uint8_t rows[5]={0,2,4,3,1};
  return visual<5 ? rows[visual] : 0;
}
static inline uint32_t nx_menu_portrait(uint32_t visual) {
  static const uint8_t images[5]={0,1,1,2,3};
  return images[visual<5 ? visual : 0];
}
static inline uint32_t nx_menu_hit_row(float normalized_y,uint32_t focus) {
  float top=.327f;
  for(uint32_t i=0;i<NX_MAIN_MENU_COUNT;i++) {
    const float height=.075f+(i==focus ? .08775f : 0.f);
    if(normalized_y<top+height+.0085f)return i;
    top+=height+.017f;
  }
  return NX_MAIN_MENU_COUNT-1;
}
#endif
