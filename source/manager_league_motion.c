#include "manager_league_dummy.h"
#include <math.h>
#include <string.h>

/* A broadcast is sampled from one football action tape, never from viewing
 * time. Each endpoint inherits the prior endpoint, including dead balls,
 * possession changes, substitutes and the half-time change of ends. */
static float blend(float a,float b,float t) { return a+(b-a)*t; }
static float bound(float v,float lo,float hi) { return fmaxf(lo,fminf(hi,v)); }
static uint32_t actor_for(const MdDot p[23],uint32_t side,uint32_t number) {
  for(uint32_t n=0;n<11;n++)if(p[side*11+n].number==number)return side*11+n;
  return side*11+9;
}
static uint32_t nearest(const MdDot p[23],uint32_t side,float x,float y) {
  uint32_t best=side*11+1;float distance=100.f;
  for(uint32_t n=1;n<11;n++) {
    uint32_t i=side*11+n;float dx=(p[i].x-x)*1.54f,dy=p[i].y-y,d=dx*dx+dy*dy;
    if(d<distance){distance=d;best=i;}
  }
  return best;
}
static void shape(MdDot p[23],uint32_t half,uint32_t possession,float ball_x,float ball_y) {
  static const float xs[11]={.045f,.24f,.20f,.20f,.24f,.42f,.39f,.46f,.66f,.69f,.66f};
  static const float ys[11]={.5f,.13f,.38f,.62f,.87f,.22f,.51f,.76f,.15f,.50f,.85f};
  for(uint32_t side=0;side<2;side++) {
    const int flip=side^half;const float progress=flip ? 1-ball_x : ball_x;
    for(uint32_t n=0;n<11;n++) {
      float x=xs[n],y=ys[n];
      if(n) {
        x+=(progress-.5f)*.29f+(possession==side ? .025f : -.035f);
        y+=(ball_y-.5f)*.18f;
        /* Staggered lanes keep a midfield triangle, rather than three dots
         * sharing the same X and hiding behind their opponents. */
        x+=.012f*sinf((float)(p[side*11+n].number*3u+side));
      }
      p[side*11+n].x=flip ? 1-bound(x,.035f,.88f) : bound(x,.035f,.88f);
      p[side*11+n].y=bound(y,.06f,.94f);
    }
  }
}
static void kickoff(MdDot p[23],uint32_t half,uint32_t side) {
  shape(p,half,side,.5f,.5f);
  for(uint32_t s=0;s<2;s++)for(uint32_t n=1;n<11;n++) {
    uint32_t i=s*11+n;int flip=s^half;
    float x=flip ? 1-p[i].x : p[i].x;
    p[i].x=flip ? 1-fminf(x,.405f) : fminf(x,.405f);
  }
  const uint32_t taker=side*11+9,partner=side*11+7;
  p[taker].x=(side^half) ? .507f : .493f;p[taker].y=.5f;
  p[partner].x=(side^half) ? .57f : .43f;p[partner].y=.58f;
  p[22].x=.5f;p[22].y=.5f;
}
static int step(MdDot out[23],MdDot from[23],const MdDot to[23],uint32_t *at,
                uint32_t end,uint32_t elapsed) {
  if(end<*at)end=*at;
  if(elapsed<=end) {
    float t=end>*at ? (float)(elapsed-*at)/(end-*at) : 1.f;
    for(uint32_t i=0;i<23;i++) {
      if(t>=1.f){out[i]=to[i];continue;}
      float u=i==22 ? t : t*t*(3-2*t);
      out[i]=from[i];out[i].x=blend(from[i].x,to[i].x,u);out[i].y=blend(from[i].y,to[i].y,u);
    }
    return 1;
  }
  memcpy(from,to,23*sizeof(*to));*at=end;return 0;
}
static void ball_to(MdDot p[23],uint32_t player) {
  p[22].x=p[player].x;p[22].y=p[player].y;
}
void manager_dummy_sample(const MdFixture *f,uint32_t elapsed,MdDot out[23]) {
  MdDot p[23]={0},target[23];uint32_t at=0,half=0,owner=7;
  if(elapsed>MD_DURATION)elapsed=MD_DURATION;
  for(uint32_t s=0;s<2;s++)for(uint32_t n=0;n<11;n++)p[s*11+n]=(MdDot){0,0,s,n+1};
  p[22].side=2;kickoff(p,0,0);memcpy(target,p,sizeof(p));
  if(step(out,p,target,&at,700,elapsed))return;
  /* Kickoff is a visible backward pass. Everyone begins in their own half. */
  ball_to(target,owner);
  if(step(out,p,target,&at,1400,elapsed))return;
  for(uint32_t i=0;i<MD_EVENTS;i++) {
    const MdEvent *e=&f->events[i];const uint32_t hash=f->seed^(0x9e3779b9u*(i+1));
    const uint32_t side=e->side,actor=actor_for(p,side,e->player),flip=side^half;
    const float dir=flip ? -1.f : 1.f;
    const int shot=e->kind==MD_GOAL || e->kind==MD_SHOT || e->kind==MD_SAVE;
    memcpy(target,p,sizeof(p));
    if(e->kind==MD_HALF || e->kind==MD_SUB) {
      if(e->kind==MD_HALF) {
        shape(target,half,owner/11,p[22].x,p[22].y);
        const float direction=(owner/11)^half ? -1.f : 1.f;
        target[owner].x=bound(p[owner].x+direction*.04f,.04f,.96f);
        target[owner].y=p[owner].y;ball_to(target,owner);
        if(step(out,p,target,&at,e->at_ms-400u,elapsed))return;
        memcpy(target,p,sizeof(p));
      }
      /* The ball stays with its carrier until the whistle; the departing
       * player walks to the near touchline, rather than vanishing in place. */
      if(e->kind==MD_SUB) {
        target[actor].y=target[actor].y<.5f ? .025f : .975f;
        target[actor].number=e->other;
      }
      if(step(out,p,target,&at,e->at_ms,elapsed))return;
      if(e->kind==MD_SUB) {
        p[actor].number=e->other;
        if(owner==actor)owner=nearest(p,side,p[22].x,p[22].y);
      } else {
        memcpy(target,p,sizeof(p));
        if(step(out,p,target,&at,e->at_ms+700,elapsed))return;
        half=1;kickoff(target,half,1);owner=18;
        if(step(out,p,target,&at,e->at_ms+3300,elapsed))return;
        ball_to(target,owner);
        if(step(out,p,target,&at,e->at_ms+3900,elapsed))return;
      }
      continue;
    }
    /* Build towards the event: keep the present carrier, spread into support
     * lanes, then deliver a distinct pass to the named player. No new ball
     * coordinate is introduced at an event boundary. */
    float progress=shot ? .76f : e->kind==MD_CORNER ? .90f : .43f+(hash%18)*.012f;
    float x=flip ? 1-progress : progress,y=.28f+((hash>>8)%45)*.01f;
    uint32_t carrier=owner;
    if(carrier/11!=side) {
      /* A visible contested pass/interception hands over possession. */
      carrier=nearest(p,side,p[22].x,p[22].y);
      memcpy(target,p,sizeof(p));ball_to(target,carrier);
      if(step(out,p,target,&at,at+350,elapsed))return;
    }
    memcpy(target,p,sizeof(p));shape(target,half,side,x,y);
    target[actor].x=x-dir*.045f;target[actor].y=y;
    ball_to(target,carrier);
    /* Restarts consume part of the next six-second action. Allocate every
     * lead-in from the remaining interval, never clamp an already-past key
     * time to 'now' (which would introduce a zero-duration position jump). */
    const uint32_t begin=at,remaining=e->at_ms-begin;
    const uint32_t contact=remaining>=1750u ? 600u : remaining/3u;
    const uint32_t runway=remaining-contact;
    const uint32_t delivery=runway*40u/100u>900u ? 900u : runway*40u/100u;
    const uint32_t carry=runway*16u/100u>650u ? 650u : runway*16u/100u;
    const uint32_t ready=begin+runway-delivery-carry;
    if(step(out,p,target,&at,ready,elapsed))return;
    memcpy(target,p,sizeof(p));ball_to(target,actor);
    if(step(out,p,target,&at,ready+delivery,elapsed))return;
    owner=actor;
    memcpy(target,p,sizeof(p));target[actor].x=x;target[actor].y=y;ball_to(target,actor);
    if(step(out,p,target,&at,e->at_ms-contact,elapsed))return;
    memcpy(target,p,sizeof(p));
    if(e->kind==MD_PASS) {
      uint32_t receiver=nearest(p,side,bound(x+dir*.17f,.08f,.92f),1-y);
      if(receiver==actor)receiver=side*11+5+(hash%3);
      ball_to(target,receiver);owner=receiver;
    } else if(shot) {
      target[22].x=flip ? .008f : .992f;
      target[22].y=e->kind==MD_SHOT ? ((hash&1) ? .31f : .69f) : .48f+(hash%5)*.01f;
      if(e->kind==MD_SAVE) {
        owner=(1-side)*11;target[22].x=flip ? .075f : .925f;
        target[owner].x=target[22].x;target[owner].y=target[22].y;
      }
    } else if(e->kind==MD_CORNER) {
      /* A corner is awarded when the deflected ball crosses the byline; the
       * named attacker does not sprint/teleport to the flag with the ball. */
      target[22].x=flip ? .012f : .988f;target[22].y=(hash&1) ? .025f : .975f;
    } else if(e->kind==MD_FOUL || e->kind==MD_YELLOW) {
      owner=nearest(p,1-side,p[22].x,p[22].y);
      target[owner].x=p[22].x;target[owner].y=p[22].y;
      target[actor].x=p[22].x-dir*.018f;target[actor].y=p[22].y+.018f;
    }
    if(step(out,p,target,&at,e->at_ms,elapsed))return;
    /* Observable dead-ball phases. A goal always returns to kickoff before
     * open play; a save remains in the keeper's hands before distribution. */
    memcpy(target,p,sizeof(p));
    if(e->kind==MD_GOAL) {
      if(step(out,p,target,&at,e->at_ms+900,elapsed))return;
      kickoff(target,half,1-side);owner=(1-side)*11+7;
      if(step(out,p,target,&at,e->at_ms+3000,elapsed))return;
      if(step(out,p,target,&at,e->at_ms+3300,elapsed))return;
      ball_to(target,owner);
      if(step(out,p,target,&at,e->at_ms+3900,elapsed))return;
    } else if(e->kind==MD_SHOT || e->kind==MD_OFFSIDE) {
      if(step(out,p,target,&at,e->at_ms+700,elapsed))return;
      owner=(1-side)*11;ball_to(target,owner);
      if(step(out,p,target,&at,e->at_ms+1500,elapsed))return;
    } else if(e->kind==MD_FOUL || e->kind==MD_YELLOW || e->kind==MD_SAVE) {
      if(step(out,p,target,&at,e->at_ms+1000,elapsed))return;
    }
  }
  memcpy(out,p,sizeof(p));
}
