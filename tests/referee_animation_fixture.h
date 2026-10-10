#ifndef PESNX_REFEREE_ANIMATION_FIXTURE_H
#define PESNX_REFEREE_ANIMATION_FIXTURE_H
#include "../source/referee_animation.h"
/* Synthetic poses only. No copyrighted animation fixture is committed. */
static inline void fixture_word(unsigned char *p,uint32_t n) {memcpy(p,&n,4);}
static inline unsigned char *referee_animation_fixture_count(size_t *size,unsigned count) {
  const size_t header=32+32*count;
  *size=header+count*4*19*sizeof(RefereeBonePose);
  unsigned char *p=calloc(1,*size);if(!p)return NULL;
  memcpy(p,"NXREF01\0",8);fixture_word(p+8,count==8?3:2);fixture_word(p+12,count);
  fixture_word(p+16,19);fixture_word(p+20,32);
  const float speeds[]={0,1.4f,3.2f,5.8f},rate=30;
  for(unsigned c=0;c<count;++c) {
    const size_t at=header+c*4*19*sizeof(RefereeBonePose);
    unsigned char *row=p+32+c*32;
    fixture_word(row,4);fixture_word(row+4,(uint32_t)at);
    memcpy(row+8,&rate,4);if(c<4)memcpy(row+12,&speeds[c],4);
    RefereeBonePose *poses=(RefereeBonePose *)(p+at);
    for(unsigned f=0;f<4;++f)for(unsigned b=0;b<19;++b) {
      const float angle=(float)c*0.1f+(float)(f%2)*0.2f;
      RefereeBonePose *v=&poses[f*19+b];
      v->rotation[0]=sinf(angle);v->rotation[3]=cosf(angle);
      v->position[0]=(float)b*0.01f;
      v->position[1]=1.0f+(float)c*0.03f+(float)(f%2)*0.02f;v->position[3]=1;
    }
  }
  uint64_t sum=nx_asset_hash(p+32,*size-32);memcpy(p+24,&sum,8);return p;
}
static inline unsigned char *referee_animation_fixture(size_t *size) {
  return referee_animation_fixture_count(size,4);
}
#endif
