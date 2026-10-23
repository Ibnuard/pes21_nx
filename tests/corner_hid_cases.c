#include <assert.h>
#include <stdint.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "corner_tactics.h"
typedef uint64_t u64;
enum {PES_CONTROLLER_PROFILE_FULL=0};
enum {HidNpadButton_A=1,HidNpadButton_B=2,HidNpadButton_X=4,
  HidNpadButton_Up=8,HidNpadButton_Right=16,HidNpadButton_Down=32,
  HidNpadButton_Left=64,HidNpadButton_StickL=128,HidNpadButton_StickR=256,
  HidNpadButton_Plus=512,HidNpadButton_Minus=1024,
  HidNpadButton_AnySL=2048,HidNpadButton_AnySR=4096};
#include "corner_tactics_hid.inc"
static unsigned hid(unsigned pad,unsigned profile,u64 buttons,u64 menu,float x,float y) {
  return corner_tactics_hid(pad,1000,1,1,profile,buttons,menu,x,y,0,0);
}
int main(int argc,char **argv) {
  assert(argc==2);fnx_corner_reset();
  fnx_corner_publish(0,42,FNX_CORNER_ATTACK,1,8,4,0,1000);
  uint32_t command=0;uint8_t option=0;
  if(!strcmp(argv[1],"full-right")) {
    hid(0,0,0,0,0,0);
    assert(!(hid(0,0,HidNpadButton_Right,0,0,0)&FNX_CORNER_CAPTURE));
    hid(0,0,0,0,0,0);assert(hid(0,0,HidNpadButton_Left,0,0,0)&FNX_CORNER_CAPTURE);
    assert(hid(0,0,HidNpadButton_Right,0,0,0)&FNX_CORNER_CAPTURE);
    assert(!fnx_corner_take(0,42,1000,&command,&option)); /* Opening still held. */
    hid(0,0,0,0,0,0);hid(0,0,HidNpadButton_Right,0,0,0);
    assert(fnx_corner_take(0,42,1000,&command,&option) && option==2);
  } else if(!strcmp(argv[1],"single-stick")) {
    hid(0,1,0,0,0,0);hid(0,1,HidNpadButton_StickL,0,0,0);
    hid(0,1,0,0,0,0);assert(hid(0,1,0,0,1,0)&FNX_CORNER_CAPTURE);
    assert(fnx_corner_take(0,42,1000,&command,&option) && option==2);
    assert(hid(0,1,0,0,1,0)&FNX_CORNER_CAPTURE);
    hid(0,1,0,0,0,0);assert(!(hid(0,1,0,0,1,0)&FNX_CORNER_CAPTURE));
  } else if(!strcmp(argv[1],"cancel")) {
    hid(0,0,0,0,0,0);hid(0,0,HidNpadButton_Left,0,0,0);hid(0,0,0,0,0,0);
    assert(hid(0,0,HidNpadButton_B,HidNpadButton_B,0,0)&FNX_CORNER_CAPTURE);
    assert(!fnx_corner_take(0,42,1000,&command,&option));
  } else if(!strcmp(argv[1],"short-page")) {
    hid(0,0,0,0,0,0);hid(0,0,HidNpadButton_Left,0,0,0);hid(0,0,0,0,0,0);
    assert(hid(0,0,HidNpadButton_X,HidNpadButton_X,0,0)&FNX_CORNER_CAPTURE);
    hid(0,0,0,0,0,0);hid(0,0,HidNpadButton_Down,0,0,0);
    assert(fnx_corner_take(0,42,1000,&command,&option) && command==0x71 && option==3);
  } else return 2;
  puts("actual HID adapter routing passed");return 0;
}
