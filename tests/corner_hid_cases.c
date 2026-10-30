#include <assert.h>
#include <stdint.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "corner_tactics.h"
typedef uint64_t u64;
enum {PES_CONTROLLER_PROFILE_FULL=0};
static int nameplates_ready;
static int pes_controller_nameplate_ready(void){return nameplates_ready;}
enum {HidNpadButton_A=1,HidNpadButton_B=2,HidNpadButton_X=4,
  HidNpadButton_Up=8,HidNpadButton_Right=16,HidNpadButton_Down=32,
  HidNpadButton_Left=64,HidNpadButton_StickL=128,HidNpadButton_StickR=256,
  HidNpadButton_Plus=512,HidNpadButton_Minus=1024,
  HidNpadButton_AnySL=2048,HidNpadButton_AnySR=4096,HidNpadButton_Y=8192,
  HidNpadButton_L=16384,HidNpadButton_R=32768};
#include "corner_tactics_hid.inc"
static unsigned hid(unsigned pad,unsigned profile,u64 buttons,u64 menu,float x,float y) {
  (void)menu;menu=controller_profile_map_buttons(buttons,(ControllerProfile)profile);
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
  } else if(!strcmp(argv[1],"single-hold")) {
    FnxCornerView v;
    hid(0,1,0,0,0,0);
    assert(!(hid(0,1,HidNpadButton_StickL,0,0,0)&FNX_CORNER_CAPTURE));
    hid(0,1,0,0,0,0);
    assert(hid(0,1,HidNpadButton_AnySL,0,0,0)&FNX_CORNER_CAPTURE);
    fnx_corner_view(0,1000,&v);assert(v.open && v.layout==1);
    hid(0,1,HidNpadButton_AnySL|HidNpadButton_Down,HidNpadButton_A,0,0);
    assert(fnx_corner_take(0,42,1000,&command,&option) && command==0x6e && option==2);
    assert(hid(0,1,HidNpadButton_Down,HidNpadButton_A,0,0)&FNX_CORNER_CAPTURE);
    assert(hid(0,1,HidNpadButton_Down,HidNpadButton_A,0,0)&FNX_CORNER_CAPTURE);
    fnx_corner_view(0,1000,&v);assert(!v.open);
    hid(0,1,0,0,0,0);
    assert(!(hid(0,1,HidNpadButton_Down,HidNpadButton_A,0,0)&FNX_CORNER_CAPTURE));
  } else if(!strcmp(argv[1],"single-short-two-pads")) {
    FnxCornerView v;
    fnx_corner_publish(1,43,FNX_CORNER_DEFENCE,0,8,4,0,1000);
    hid(0,1,0,0,0,0);hid(1,2,0,0,0,0);
    hid(0,1,HidNpadButton_AnySL|HidNpadButton_AnySR,0,0,0);
    fnx_corner_view(0,1000,&v);assert(v.mode==FNX_CORNER_SHORT && v.open);
    hid(0,1,HidNpadButton_AnySL|HidNpadButton_AnySR,0,0,0);
    fnx_corner_view(0,1000,&v);assert(v.mode==FNX_CORNER_SHORT); // Edge only.
    hid(1,2,HidNpadButton_L|HidNpadButton_A,HidNpadButton_B,0,0);
    assert(!fnx_corner_take(1,43,1000,&command,&option)); // Defence down is empty.
    hid(1,2,HidNpadButton_L,0,0,0);
    hid(1,2,HidNpadButton_L|HidNpadButton_B,HidNpadButton_Y,0,0);
    assert(fnx_corner_take(1,43,1000,&command,&option) && command==0x6f && option==1);
    hid(0,1,HidNpadButton_AnySL,0,0,0);
    hid(0,1,HidNpadButton_AnySL|HidNpadButton_Left,HidNpadButton_B,0,0);
    assert(fnx_corner_take(0,42,1000,&command,&option) && command==0x71 && option==3);
    hid(0,1,HidNpadButton_AnySL,0,0,0);
    corner_tactics_hid(0,1001,0,1,1,HidNpadButton_AnySL,0,0,0,0,0);
    fnx_corner_view(0,1000,&v);assert(!v.open);
    assert(hid(0,1,HidNpadButton_AnySL,0,0,0)&FNX_CORNER_CAPTURE);
    fnx_corner_view(0,1000,&v);assert(!v.open); // Resume needs shoulder release.
    hid(0,1,0,0,0,0);hid(0,1,HidNpadButton_AnySL,0,0,0);
    fnx_corner_view(0,1000,&v);assert(v.open && v.mode==FNX_CORNER_ATTACK);
  } else if(!strcmp(argv[1],"single-mapping")) {
    const u64 raw[2][4]={{HidNpadButton_Right,HidNpadButton_Down,HidNpadButton_Left,HidNpadButton_Up},
      {HidNpadButton_Y,HidNpadButton_X,HidNpadButton_A,HidNpadButton_B}};
    for(unsigned side=0;side<2;side++)for(unsigned d=0;d<4;d++) {
      fnx_corner_reset();fnx_corner_publish(side,42,FNX_CORNER_ATTACK,1,8,4,0,1000);
      hid(side,side+1,0,0,0,0);hid(side,side+1,HidNpadButton_AnySL,0,0,0);
      assert(hid(side,side+1,HidNpadButton_AnySL|raw[side][d],0,0,0)&FNX_CORNER_CAPTURE);
      assert(fnx_corner_take(side,42,1000,&command,&option) && command==0x6e && option==d+1);
      hid(side,side+1,HidNpadButton_AnySL|raw[side][d],0,0,0);
      assert(!fnx_corner_take(side,42,1000,&command,&option)); // No held-button repeats.
    }
  } else if(!strcmp(argv[1],"cancel")) {
    hid(0,0,0,0,0,0);hid(0,0,HidNpadButton_Left,0,0,0);hid(0,0,0,0,0,0);
    assert(hid(0,0,HidNpadButton_B,HidNpadButton_B,0,0)&FNX_CORNER_CAPTURE);
    assert(!fnx_corner_take(0,42,1000,&command,&option));
  } else if(!strcmp(argv[1],"nameplate-start")) {
    for(unsigned profile=0;profile<3;profile++) {
      nameplates_ready=0;fnx_corner_reset();
      fnx_corner_publish(0,42,FNX_CORNER_ATTACK,1,8,4,0,1000);
      hid(0,profile,0,0,0,0);
      u64 opener=profile ? HidNpadButton_AnySL : HidNpadButton_Left;
      assert(hid(0,profile,opener,0,0,0)&FNX_CORNER_CAPTURE);
      nameplates_ready=1;
      /* No release latch swallowing movement while COM already kicks. */
      assert(!hid(0,profile,opener|HidNpadButton_B,0,1,1));
      FnxCornerView v;fnx_corner_view(0,1000,&v);assert(!v.available && !v.open);
      assert(!fnx_corner_take(0,42,1000,&command,&option));
      nameplates_ready=0;
      assert(!hid(0,profile,opener,0,0,0));
      fnx_corner_view(0,1000,&v);assert(!v.available);
      fnx_corner_publish(0,43,FNX_CORNER_ATTACK,1,8,4,0,1000);
      hid(0,profile,0,0,0,0);
      assert(hid(0,profile,opener,0,0,0)&FNX_CORNER_CAPTURE);
    }
  } else if(!strcmp(argv[1],"short-page")) {
    hid(0,0,0,0,0,0);hid(0,0,HidNpadButton_Left,0,0,0);hid(0,0,0,0,0,0);
    assert(hid(0,0,HidNpadButton_X,HidNpadButton_X,0,0)&FNX_CORNER_CAPTURE);
    hid(0,0,0,0,0,0);hid(0,0,HidNpadButton_Down,0,0,0);
    assert(fnx_corner_take(0,42,1000,&command,&option) && command==0x71 && option==3);
  } else return 2;
  puts("actual HID adapter routing passed");return 0;
}
