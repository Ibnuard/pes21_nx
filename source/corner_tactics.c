#include "corner_tactics.h"
#include <pthread.h>
#include <string.h>

typedef struct {
  uint64_t epoch, seen, queued_at;
  uint32_t mode, short_allowed, values[3], previous;
  uint32_t open, page, release, pending, pending_mode;
  uint32_t submitted, consumed;
} CornerPad;
static CornerPad pads[2];
static pthread_mutex_t corner_mutex=PTHREAD_MUTEX_INITIALIZER;
static int fresh(const CornerPad *p,uint64_t now) {
  return p->mode && now>=p->seen && now-p->seen<=250;
}
/* Directions are UP, RIGHT, DOWN, LEFT. These are native command options,
 * not physical PadId values (which change with native camera orientation). */
static uint8_t option_for(uint32_t mode,uint32_t direction) {
  static const uint8_t attack[4]={1,2,3,4};
  static const uint8_t short_corner[4]={1,2,3,4};
  static const uint8_t defence[4]={2,3,0,1};
  if(direction>=4)return 0;
  return mode==FNX_CORNER_ATTACK ? attack[direction] :
         mode==FNX_CORNER_SHORT ? short_corner[direction] :
         mode==FNX_CORNER_DEFENCE ? defence[direction] : 0;
}
static uint32_t current(const CornerPad *p) {
  static const uint32_t normal[4]={7,6,5,2};
  static const uint32_t defence[4]={2,1,UINT32_MAX,0};
  uint32_t mode=p->page ? FNX_CORNER_SHORT : p->mode;
  uint32_t value=p->values[mode==FNX_CORNER_SHORT ? 1 :
                           mode==FNX_CORNER_DEFENCE ? 2 : 0];
  for(uint32_t d=0;d<4;d++)
    if((mode==FNX_CORNER_SHORT ? d :
        mode==FNX_CORNER_DEFENCE ? defence[d] : normal[d])==value)
      return d;
  return UINT32_MAX;
}
void fnx_corner_reset(void) {
  pthread_mutex_lock(&corner_mutex);
  memset(pads,0,sizeof(pads));
  pthread_mutex_unlock(&corner_mutex);
}
void fnx_corner_publish(uint32_t pad,uint64_t epoch,uint32_t mode,
    int short_allowed,uint32_t normal,uint32_t short_choice,
    uint32_t defence,uint64_t now) {
  if(pad>1)return;
  if(mode!=FNX_CORNER_ATTACK && mode!=FNX_CORNER_DEFENCE)mode=0;
  pthread_mutex_lock(&corner_mutex);
  CornerPad *p=&pads[pad];
  if(p->epoch!=epoch || p->mode!=mode || (mode && !fresh(p,now))) {
    /* Repeated unavailable heartbeats must not isolate ordinary gameplay.
     * Retain a release latch only for an actual open/closing modal action. */
    p->release=p->open || p->pending || p->release;
    p->open=p->page=p->pending=0;
  }
  p->epoch=epoch;p->mode=mode;p->seen=now;
  p->short_allowed=mode==FNX_CORNER_ATTACK && short_allowed;
  if(!p->short_allowed)p->page=0;
  p->values[0]=normal;p->values[1]=short_choice;p->values[2]=defence;
  pthread_mutex_unlock(&corner_mutex);
}
uint32_t fnx_corner_input(uint32_t pad,uint64_t now,int allowed,
    int connected,uint32_t buttons,int axes_neutral) {
  if(pad>1)return 0;
  pthread_mutex_lock(&corner_mutex);
  CornerPad *p=&pads[pad];
  uint32_t pressed=buttons & ~p->previous;
  p->previous=buttons;
  int valid=allowed && connected && fresh(p,now);
  uint32_t result=valid ? FNX_CORNER_AVAILABLE : 0;
  if(!valid) {
    if(p->open || p->pending)p->release=1;
    p->open=p->pending=0;
  }
  if(p->release) {
    /* Eat the closing press even if the native restart ended in that frame. */
    if(connected && allowed)result|=FNX_CORNER_CAPTURE;
    if(!buttons && axes_neutral)p->release=0;
  } else if(valid && p->open) {
    result|=FNX_CORNER_CAPTURE;
    if(pressed & (FNX_CORNER_BACK|FNX_CORNER_OTHER)) {
      p->open=0;p->release=1;
    } else if((pressed & FNX_CORNER_PAGE) && p->short_allowed) {
      p->page=!p->page;p->release=1;
    } else {
      uint32_t directions=pressed & 15u;
      /* A diagonal press is ambiguous; require a single direction. */
      if(directions && !(directions & (directions-1))) {
        uint32_t d=directions==1 ? 0 : directions==2 ? 1 :
                   directions==4 ? 2 : 3;
        uint32_t mode=p->page ? FNX_CORNER_SHORT : p->mode;
        if(option_for(mode,d)) {
          p->pending=d+1;p->pending_mode=mode;p->queued_at=now;
          p->submitted++;p->open=0;p->release=1;
        }
      }
    }
  } else if(valid && (pressed & FNX_CORNER_LEFT) &&
            !(buttons & ~FNX_CORNER_LEFT)) {
    p->open=1;p->page=0;p->release=1;
    result|=FNX_CORNER_CAPTURE;
  }
  pthread_mutex_unlock(&corner_mutex);
  return result;
}
int fnx_corner_take(uint32_t pad,uint64_t epoch,uint64_t now,
                    uint32_t *command,uint8_t *option) {
  if(pad>1 || !command || !option)return 0;
  pthread_mutex_lock(&corner_mutex);
  CornerPad *p=&pads[pad];int ok=0;
  if(p->pending && p->epoch==epoch && fresh(p,now) &&
      now>=p->queued_at && now-p->queued_at<=250 &&
      (p->pending_mode==p->mode ||
       (p->mode==FNX_CORNER_ATTACK && p->short_allowed &&
        p->pending_mode==FNX_CORNER_SHORT))) {
    *option=option_for(p->pending_mode,p->pending-1);
    *command=p->pending_mode==FNX_CORNER_DEFENCE ? 0x6f :
             p->pending_mode==FNX_CORNER_SHORT ? 0x71 : 0x6e;
    p->consumed++;ok=1;
  }
  p->pending=0;
  pthread_mutex_unlock(&corner_mutex);
  return ok;
}
void fnx_corner_view(uint32_t pad,uint64_t now,FnxCornerView *out) {
  memset(out,0,sizeof(*out));
  if(pad>1)return;
  pthread_mutex_lock(&corner_mutex);
  const CornerPad *p=&pads[pad];
  out->available=fresh(p,now);out->open=out->available && p->open;
  out->mode=p->page ? FNX_CORNER_SHORT : p->mode;
  out->short_allowed=p->short_allowed;out->current=current(p);
  out->submitted=p->submitted;out->consumed=p->consumed;
  pthread_mutex_unlock(&corner_mutex);
}
const char *fnx_corner_label(uint32_t mode,uint32_t direction) {
  static const char *labels[3][4]={
    {"DASH","FAR POST","6-YARD BOX","TRAIN"},
    {"TOUCHLINE","DIAGONAL RUN","RUN FROM DEEP","TWO OPTIONS"},
    {"MIXED","ZONAL","","MAN-TO-MAN"}};
  return mode>=1 && mode<=3 && direction<4 ? labels[mode-1][direction] : "";
}
