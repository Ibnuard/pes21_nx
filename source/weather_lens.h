#ifndef PESNX_WEATHER_LENS_H
#define PESNX_WEATHER_LENS_H
#include <stdint.h>
#include <math.h>
#define WEATHER_LENS_W 256
#define WEATHER_LENS_H 144
/* One cached luminance alpha mask per season, sampled once per screen pixel.
 * Marks are attached to the lens: never falling particles or world geometry. */
static inline float weather_lens_smooth(float a,float b,float x) {
  float t=fminf(1.0f,fmaxf(0.0f,(x-a)/(b-a)));
  return t*t*(3.0f-2.0f*t);
}
static inline uint32_t weather_lens_hash(uint32_t v) {
  v^=v>>16;v*=0x7feb352du;v^=v>>15;v*=0x846ca68bu;return v^(v>>16);
}
static inline float weather_lens_alpha(float u,float v,int winter) {
  float rim=weather_lens_smooth(.46f,1.0f,fmaxf(fabsf(u-.5f)*2,fabsf(v-.5f)*2));
  float alpha=(winter?.075f:.045f)+(winter?.10f:.065f)*rim;
  for(uint32_t i=0;i<24;i++) {
    uint32_t h=weather_lens_hash(i+37u);
    float x=(h&65535u)/65535.f,y=(h>>16)/65535.f;
    /* Keep sharply visible beads away from the central action area. */
    if(x>.22f && x<.78f && y>.20f && y<.80f)continue;
    float radius=(winter?.007f:.011f)+(h%11u)*.00065f;
    float dx=(u-x)/radius,dy=(v-y)/(radius*(winter?1.6f:2.5f));
    float d=dx*dx+dy*dy;
    float bead=1-weather_lens_smooth(.10f,1.0f,d);
    float ring=weather_lens_smooth(.20f,.45f,d)*(1-weather_lens_smooth(.55f,1.25f,d));
    alpha+=(winter?.15f:.045f)*bead+(winter?.02f:.075f)*ring;
  }
  /* Leave native scoreboard and bottom name bars legible, with soft edges. */
  float top=1-weather_lens_smooth(.10f,.17f,v);
  float left=1-weather_lens_smooth(.34f,.42f,u);
  float bottom=weather_lens_smooth(.88f,.96f,v);
  alpha*=1-.80f*fmaxf(top*left,bottom);
  return fminf(alpha,.30f);
}
static inline void weather_lens_mask(uint8_t *pixels,int winter) {
  for(int y=0;y<WEATHER_LENS_H;y++)for(int x=0;x<WEATHER_LENS_W;x++)
    pixels[y*WEATHER_LENS_W+x]=(uint8_t)(255*weather_lens_alpha(
        (x+.5f)/WEATHER_LENS_W,(y+.5f)/WEATHER_LENS_H,winter)+.5f);
}
#endif
