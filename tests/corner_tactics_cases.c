#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "corner_tactics.h"
static uint64_t now=1000;
static uint32_t step(unsigned pad,unsigned buttons) {
  return fnx_corner_input(pad,now,1,1,buttons,!buttons);
}
static void publish(unsigned pad,unsigned mode,uint64_t epoch) {
  fnx_corner_publish(pad,epoch,mode,1,8,4,0,now);
}
static void open_menu(unsigned pad) {
  step(pad,0);
  assert(step(pad,FNX_CORNER_LEFT)&FNX_CORNER_CAPTURE);
  FnxCornerView v;fnx_corner_view(pad,now,&v);assert(v.open);
  assert(step(pad,FNX_CORNER_LEFT)&FNX_CORNER_CAPTURE);
  step(pad,0);
}
static void choice(unsigned mode,unsigned direction) {
  unsigned native_mode=mode==FNX_CORNER_SHORT ? FNX_CORNER_ATTACK : mode;
  publish(0,native_mode,42);open_menu(0);
  if(mode==FNX_CORNER_SHORT) {step(0,FNX_CORNER_PAGE);step(0,0);}
  uint32_t command=0;uint8_t option=0;
  unsigned key=1u<<direction;
  assert(step(0,key)&FNX_CORNER_CAPTURE);
  int expected=!(mode==FNX_CORNER_DEFENCE && direction==2);
  assert(fnx_corner_take(0,42,now,&command,&option)==expected);
  if(expected) {
    static const uint8_t def[4]={2,3,0,1};
    assert(option==(mode==FNX_CORNER_DEFENCE ? def[direction] : direction+1));
    assert(command==(mode==FNX_CORNER_SHORT ? 0x71u : mode==FNX_CORNER_DEFENCE ? 0x6fu : 0x6eu));
    assert(!fnx_corner_take(0,42,now,&command,&option));
    assert(step(0,key)&FNX_CORNER_CAPTURE); /* Closing press cannot kick/taker. */
    step(0,0);
    FnxCornerView view;fnx_corner_view(0,now,&view);
    assert(!view.open && view.current==(mode==FNX_CORNER_DEFENCE ? 3u : UINT32_MAX)); /* No optimistic highlight. */
    fnx_corner_publish(0,42,native_mode,1,7,0,2,now);
    fnx_corner_view(0,now,&view);assert(view.current==0);
  }
}
static void lifecycle(const char *test) {
  publish(0,FNX_CORNER_ATTACK,42);open_menu(0);
  uint32_t command=0;uint8_t option=0;
  if(!strcmp(test,"cancel")) {
    step(0,FNX_CORNER_BACK);assert(!fnx_corner_take(0,42,now,&command,&option));
    assert(step(0,FNX_CORNER_BACK)&FNX_CORNER_CAPTURE);
    step(0,0);assert(!(step(0,FNX_CORNER_RIGHT)&FNX_CORNER_CAPTURE));
  } else if(!strcmp(test,"stale")) {
    step(0,FNX_CORNER_UP);now+=251;
    assert(!fnx_corner_take(0,42,now,&command,&option));
    FnxCornerView v;fnx_corner_view(0,now,&v);assert(!v.available && !v.open);
  } else if(!strcmp(test,"epoch")) {
    step(0,FNX_CORNER_UP);publish(0,FNX_CORNER_ATTACK,43);
    assert(!fnx_corner_take(0,43,now,&command,&option));
  } else if(!strcmp(test,"pause")) {
    step(0,FNX_CORNER_UP);
    fnx_corner_input(0,now,0,1,FNX_CORNER_UP,0);
    assert(!fnx_corner_take(0,42,now,&command,&option));
  } else if(!strcmp(test,"disconnect")) {
    fnx_corner_input(0,now,1,0,FNX_CORNER_LEFT,0);
    FnxCornerView v;fnx_corner_view(0,now,&v);assert(!v.open);
    assert(step(0,FNX_CORNER_LEFT)&FNX_CORNER_CAPTURE);
  } else if(!strcmp(test,"two-pads")) {
    publish(1,FNX_CORNER_DEFENCE,77);open_menu(1);
    step(0,FNX_CORNER_RIGHT);step(1,FNX_CORNER_LEFT);
    assert(!fnx_corner_take(1,42,now,&command,&option));
    assert(fnx_corner_take(0,42,now,&command,&option));assert(option==2 && command==0x6e);
    step(1,0);open_menu(1);step(1,FNX_CORNER_LEFT);
    assert(fnx_corner_take(1,77,now,&command,&option));assert(option==1 && command==0x6f);
  } else if(!strcmp(test,"diagonal")) {
    step(0,FNX_CORNER_UP|FNX_CORNER_RIGHT);
    assert(!fnx_corner_take(0,42,now,&command,&option));
    FnxCornerView v;fnx_corner_view(0,now,&v);assert(v.open);
  } else if(!strcmp(test,"restart-ended")) {
    step(0,FNX_CORNER_RIGHT);publish(0,FNX_CORNER_NONE,43);
    assert(!fnx_corner_take(0,42,now,&command,&option));
    assert(step(0,FNX_CORNER_RIGHT)&FNX_CORNER_CAPTURE);
  } else if(!strcmp(test,"reset")) {
    step(0,FNX_CORNER_UP);fnx_corner_reset();
    assert(!fnx_corner_take(0,42,now,&command,&option));
  } else abort();
}
int main(int argc,char **argv) {
  assert(argc>=2);fnx_corner_reset();
  if(!strcmp(argv[1],"first-ready")) {
    publish(0,FNX_CORNER_ATTACK,42);
    /* Availability alone is not a modal action. Right taker and aiming must
     * work on the very first ready frame, including a held movement stick. */
    assert(!(step(0,FNX_CORNER_RIGHT)&FNX_CORNER_CAPTURE));
    assert(!(fnx_corner_input(0,now,1,1,FNX_CORNER_OTHER,0)&FNX_CORNER_CAPTURE));
    step(0,0);open_menu(0);
  }
  else if(!strcmp(argv[1],"ordinary-play")) {
    /* ThinkUnitList publishes unavailable context on every ordinary frame.
     * It must never continuously re-arm modal release and eat gameplay. */
    for(unsigned frame=0;frame<20;frame++) {
      fnx_corner_publish(0,1,FNX_CORNER_NONE,0,0,0,0,now++);
      assert(!(fnx_corner_input(0,now,1,1,FNX_CORNER_OTHER,0)&FNX_CORNER_CAPTURE));
    }
    publish(0,FNX_CORNER_ATTACK,2);step(0,0);
    fnx_corner_publish(0,3,FNX_CORNER_NONE,0,0,0,0,now);
    assert(!(step(0,FNX_CORNER_OTHER)&FNX_CORNER_CAPTURE));
  }
  else if(!strcmp(argv[1],"choice")){assert(argc==4);choice(atoi(argv[2]),atoi(argv[3]));}
  else lifecycle(argv[1]);
  puts("corner ownership/input/lifetime passed");return 0;
}
