#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "corner_tactics.h"
typedef struct {void *load_base,*load_virtbase;size_t load_size;} so_module;
static uintptr_t so_try_find_addr_rx(so_module *m,const char *name){(void)m;(void)name;return 0;}
static uintptr_t *find_vtable_method_slot(so_module *m,const char *n,uintptr_t p,uint32_t c){(void)m;(void)n;(void)p;(void)c;return NULL;}
static uint64_t clock_ms=1000;
static uint64_t scene_runtime_ms(void){return clock_ms;}
static void scene_runtime_note(const char *a,const char *b){(void)a;(void)b;}
static uint8_t registry[0x500],info[0x1700],ai[2][0xb8b4],anime[8];
static uint8_t lists[2][0x4000],units[2][0x48],inputs[2][0x30];
static uint32_t match_hud_session_serial=1;
static int two_player=1,ready=1,native_calls;
static int pes_controller_native_pad_lab_active(void){return 1;}
static int pes_controller_native_pad_lab_two_player(void){return two_player;}
static void *get_registry(void){return registry;}
static const void *get_ai(const void *r,uint32_t side){assert(r==registry && side<2);return ai[side];}
static const void *get_anime(const void *r,uint32_t player){assert(r==registry && player<=21);return anime;}
static uint32_t is_ready(uint32_t action){assert(action==0x33);return ready;}
static void *(*match_global_registry_get_instance)(void)=get_registry;
static const void *(*match_global_registry_get_team_ai_info)(const void *,uint32_t)=get_ai;
#include "corner_tactics_native.inc"
static uint32_t original(void *unit,const void *input,uint32_t kind) {
  (void)input;(void)kind;native_calls++;
  /* Model native Init/menu work; the adapter must retain it, then clear only
   * the hidden-menu bytes before returning the custom native command. */
  ((uint8_t *)unit)[0x38]=1;((uint8_t *)unit)[0x39]=1;
  ((uint8_t *)unit)[0x22]=0xab;return 0x6e;
}
static void u32(void *base,size_t off,uint32_t n){memcpy((char *)base+off,&n,4);}
static void ptr(void *base,size_t off,const void *p){memcpy((char *)base+off,&p,sizeof(p));}
static void init(void) {
  fnx_corner_reset();corner_native_enabled=1;corner_get_anime=get_anime;
  corner_is_setplay_anime=is_ready;anime[1]=0x33;
  corner_native_vptr[0]=0x1000;corner_native_vptr[1]=0x2000;
  ptr(registry,0x4f0,info);u32(info,0x116c,3);u32(info,0x1514,4);u32(info,0x16fc,2);
  for(unsigned p=0;p<2;p++) {
    u32(inputs[p],0x24,p ? 13 : 2);
    u32(ai[p],0xb8a8,8);u32(ai[p],0xb8ac,4);u32(ai[p],0xb8b0,0);
    uintptr_t vp=corner_native_vptr[p];memcpy(units[p],&vp,sizeof(vp));
    ptr(lists[p],0x3bf8+(70+p)*sizeof(uintptr_t),units[p]);
    assert(corner_native_observe(lists[p],inputs[p],p)==70+p);
  }
}
static void select_up(unsigned pad) {
  fnx_corner_input(pad,clock_ms,1,1,0,1);
  fnx_corner_input(pad,clock_ms,1,1,FNX_CORNER_LEFT,0);
  fnx_corner_input(pad,clock_ms,1,1,0,1);
  fnx_corner_input(pad,clock_ms,1,1,FNX_CORNER_UP,0);
}
int main(int argc,char **argv) {
  assert(argc==2);init();
  if(!strcmp(argv[1],"commands")) {
    select_up(0);select_up(1);
    assert(corner_native_main(units[0],inputs[0],70,original)==0x6e);
    assert(units[0][0x19]==1 && units[0][0x22]==0xab);
    assert(!units[0][0x38] && !units[0][0x39]);
    assert(corner_native_main(units[1],inputs[1],71,original)==0x6f);
    assert(units[1][0x19]==2 && native_calls==2);
    assert(corner_native_main(units[0],inputs[0],70,original)==0);
    uint32_t value;memcpy(&value,ai[0]+0xb8a8,4);assert(value==8); /* No direct AI patch. */
  } else if(!strcmp(argv[1],"role-switch")) {
    select_up(0);u32(info,0x16fc,13);
    assert(!corner_native_observe(lists[0],inputs[0],0)); /* Wrong dormant vptr. */
    assert(!corner_native_units[0]);FnxCornerView v;fnx_corner_view(0,clock_ms,&v);assert(!v.available);
  } else if(!strcmp(argv[1],"not-ready")) {
    select_up(0);ready=0;assert(!corner_native_observe(lists[0],inputs[0],0));
    FnxCornerView v;fnx_corner_view(0,clock_ms,&v);assert(!v.available);
  } else if(!strcmp(argv[1],"match-generation")) {
    select_up(0);match_hud_session_serial++;
    assert(corner_native_observe(lists[0],inputs[0],0)==70);
    assert(!corner_native_main(units[0],inputs[0],70,original));
  } else if(!strcmp(argv[1],"single-player")) {
    two_player=0;assert(!corner_native_observe(lists[1],inputs[1],1));
    assert(corner_native_observe(lists[0],inputs[0],0)==70);
  } else if(!strcmp(argv[1],"abi-fallback")) {
    corner_native_enabled=0;install_corner_tactics(NULL);assert(!corner_native_enabled);
    assert(corner_native_main(units[0],inputs[0],70,original)==0x6e);
  } else if(!strcmp(argv[1],"out-of-play")) {
    select_up(0);u32(info,0x116c,2);assert(!corner_native_observe(lists[0],inputs[0],0));
    FnxCornerView v;fnx_corner_view(0,clock_ms,&v);assert(!v.available);
  } else abort();
  puts("actual native adapter command/owner/lifecycle passed");return 0;
}
