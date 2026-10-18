"""Execute the motion-only C policy and native-boundary adapters."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from test_result_flow import function

ROOT=Path(__file__).resolve().parents[1]
HOOKS=(ROOT/'source/ue4_hooks.c').read_text()


class StadiumV2Tests(unittest.TestCase):
    def run_c(self, body):
        cc=shutil.which('gcc') or shutil.which('clang')
        if not cc:
            self.skipTest('host C compiler unavailable')
        prelude='''#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include "stadium_v2_camera.h"
#define PESNX_STADIUM_V2_ENABLED 1 /* exercise retained adapter in isolation */
'''
        with tempfile.TemporaryDirectory(prefix='stadium-v2-') as tmp:
            source=Path(tmp)/'case.c'; exe=Path(tmp)/'case.exe'
            source.write_text(prelude+body)
            compiled=subprocess.run([cc,'-std=c11','-Wall','-Wextra','-Werror','-I',str(ROOT/'source'),
                                     str(source),'-o',str(exe),'-lm'],capture_output=True,text=True)
            self.assertEqual(compiled.returncode,0,compiled.stdout+compiled.stderr)
            result=subprocess.run([str(exe)],capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_stationary_target_is_native_and_no_authored_lens(self):
        policy=(ROOT/'source/stadium_v2_camera.h').read_text()
        for removed in ('STADIUM_V2_WIDE','STADIUM_V2_HEIGHT','STADIUM_V2_RAIL',
                        'atan2f','atanf','radius=55'):
            self.assertNotIn(removed,policy)
        self.run_c(r'''
int main(void) {
  for(int x=-40;x<=40;x+=20)for(int z=-25;z<=25;z+=10) {
    StadiumV2Camera s={0};
    for(unsigned i=0;i<300;++i) {
      float target[]={(float)x,.5f,(float)z};
      assert(stadium_v2_step(&s,target,45,-30,30,1000000000ULL+i*16666667ULL));
      assert(target[0]==x && target[1]==.5f && target[2]==z);
    }
  }
  float ball[]={-48,1.7f,7};
  assert(stadium_v2_valid_ball(ball));
  ball[0]=NAN;assert(!stadium_v2_valid_ball(ball));
  ball[0]=66;assert(!stadium_v2_valid_ball(ball));
  assert(!stadium_v2_valid_ball(NULL));
}
''')

    def test_visible_short_passes_hold_pose_and_long_passes_reframe(self):
        self.run_c(r'''
static void view(StadiumV2Camera *s,float x,float z,uint64_t ns,float *p) {
  float target[]={x,.5f,z};
  assert(stadium_v2_step(s,target,50,-32,32,ns));
  memcpy(p,target,12);p[3]=target[0]*.39f;p[4]=21;p[5]=70;
  p[13]=.302f;stadium_v2_finish(s,p,p[13]);
}
int main(void) {
  for(unsigned hz=30;hz<=120;hz*=2) {
    StadiumV2Camera s={0};float p[24]={0};
    view(&s,0,0,1000000000ULL,p);
    // Short passes across midfield must not move a held camera at all.
    for(unsigned i=1;i<=hz*3;++i) {
      view(&s,7.f*sinf(i*.21f),4.f*cosf(i*.17f),1000000000ULL+(uint64_t)i*1000000000/hz,p);
      assert(p[0]==0 && p[1]==.5f && p[2]==0 && p[3]==0 && p[13]==.302f);
    }
    // A 40 m/s pass traverses the shot. It must initiate smooth panning,
    // keep room for play and settle with the ball off-centre, not chase it.
    float largest=0,previous=0;
    for(unsigned i=1;i<=hz;++i) {
      float ball[]={40.f*i/hz,.5f,0},screen[2];
      view(&s,ball[0],0,4000000000ULL+(uint64_t)i*1000000000/hz,p);
      assert(p[0]>=previous && p[0]<=ball[0]);previous=p[0];
      assert(stadium_v2_screen(p,p[13],ball,screen));
      if(fabsf(screen[0])>largest)largest=fabsf(screen[0]);
    }
    printf("%u Hz max normalized screen x %.4f\n",hz,largest);
    assert(largest<.97f);
    for(unsigned i=1;i<=hz*4;++i)
      view(&s,40,0,5000000000ULL+(uint64_t)i*1000000000/hz,p);
    assert(p[0]>20 && p[0]<39); // deliberately not centred
    float held=p[0];
    for(unsigned i=1;i<=hz;++i)
      view(&s,40,0,9000000000ULL+(uint64_t)i*1000000000/hz,p);
    assert(fabsf(p[0]-held)<.03f);
    float lens=p[13];assert(lens>=.302f && lens<.306f);
  }
}
''')

    def test_projection_and_zoom_are_finite_smooth_and_bounded(self):
        self.run_c(r'''
int main(void) {
  StadiumV2Camera s={0};float p[24]={0},target[]={0,.5f,0},screen[2];
  stadium_v2_step(&s,target,50,-32,32,1000000000ULL);
  p[1]=.5f;p[4]=21;p[5]=70;p[13]=.3f;stadium_v2_finish(&s,p,p[13]);
  assert(stadium_v2_screen(p,p[13],target,screen) && fabsf(screen[0])+fabsf(screen[1])<.0001f);
  float bad[6]={0};assert(!stadium_v2_screen(bad,.3f,target,screen));
  assert(!stadium_v2_screen(p,NAN,target,screen));
  for(unsigned i=1;i<=120;++i) {
    float old=s.lens;target[0]=0;target[1]=.5f;target[2]=0;
    stadium_v2_step(&s,target,50,-32,32,1000000000ULL+i*16666667ULL);
    p[13]=i<=60?.4f:.25f;stadium_v2_finish(&s,p,p[13]);
    assert(fabsf(p[13]-old)<.007f && p[13]>=.25f && p[13]<=.4f);
    assert(p[0]==0 && p[1]==.5f && p[4]==21 && p[5]==70);
  }
  assert(s.lens>.25f && s.lens<.31f);
}
''')

    def test_dt_duplicate_pause_invalid_and_native_bounds(self):
        self.run_c(r'''
static float step_at(unsigned hz) {
  StadiumV2Camera s={0};float p[]={0,.5f,0};
  stadium_v2_step(&s,p,50,-30,30,1000000000ULL);
  for(unsigned i=1;i<=hz/2;++i) {
    p[0]=20;p[1]=.5f;p[2]=10;
    stadium_v2_step(&s,p,50,-30,30,1000000000ULL+(uint64_t)i*1000000000/hz);
  }
  return s.target[0];
}
int main(void) {
  assert(fabsf(step_at(30)-step_at(120))<.00005f);
  assert(fabsf(step_at(60)-step_at(120))<.00005f);
  StadiumV2Camera s={0};float p[]={70,.5f,45};
  stadium_v2_step(&s,p,40,-20,25,1000000000ULL);
  assert(p[0]==40 && p[2]==25);
  StadiumV2Camera before=s;
  p[0]=-30;p[2]=-15;stadium_v2_step(&s,p,40,-20,25,s.stamp);
  assert(!memcmp(&before,&s,sizeof(s)) && p[0]==40);
  p[0]=-30;p[2]=-15;stadium_v2_step(&s,p,40,-20,25,2000000000ULL);
  assert(p[0]==-30 && p[2]==-15); // no pause time integrated
  stadium_v2_suspend(&s);p[0]=10;stadium_v2_step(&s,p,40,-20,25,1);
  assert(p[0]==10);
  float saved[3];p[0]=NAN;memcpy(saved,p,sizeof(p));
  assert(!stadium_v2_step(&s,p,40,-20,25,2) && !memcmp(p,saved,sizeof(p)));
  p[0]=1;memcpy(saved,p,sizeof(p));
  assert(!stadium_v2_step(&s,p,-1,-20,25,2) && !memcmp(p,saved,sizeof(p)));
  assert(!stadium_v2_step(&s,p,40,20,-25,2));
  p[0]=30;p[2]=20;stadium_v2_step(&s,p,4,-2,2,3);
  assert(fabsf(p[0])<=4 && fabsf(p[2])<=2); // shrinking lens bounds
}
''')

    def test_production_scope_native_lens_geometry_and_lifecycle(self):
        scope=HOOKS[HOOKS.index('typedef struct {\n  StadiumV2Camera motion;'):
                    HOOKS.index('static void pes_inplay_camera_update(')]
        stubs=r'''
static uint32_t pause_camera_stadium_v2=1,pause_camera_revision,session=1,live=1;
static uint32_t pause_camera_dynamic_wide_custom;
static uint8_t camera_type=12;static unsigned available=1;
static uint64_t clock_ns=1000000000ULL;
static unsigned pes_controller_match_hud_session(void){return session;}
static int pes_controller_match_hud_inplay(void){return live;}
static unsigned char *pause_settings_tmpdb_camera(uint8_t *t){*t=camera_type;return available?&camera_type:NULL;}
static uint64_t armGetSystemTick(void){return clock_ns;}
static uint64_t armTicksToNs(uint64_t t){return t;}
'''
        self.run_c(stubs+scope+r'''
static unsigned trace_calls,interpolate_calls,native_calls;
static float actual_ball[]={20,.1f,-8},raw_target[]={45,8,22};
static float trace_state[3],velocity[3],accel[3],old[3];
static void native_trace(void *c,const void *t,float *p,float *a,float *b,float *o,
    float *d,const float *r,float x,float z0,float z1,float rate,bool first,
    const void *snap,const void *move,const void *touch,const void *kind) {
  (void)c;(void)t;(void)p;(void)a;(void)b;(void)o;(void)d;(void)r;
  assert(x==40 && z0==-20 && z1==25 && rate==1 && !first);
  assert(snap==(void*)1 && move==(void*)2 && touch==(void*)3 && kind==(void*)4);
  ++trace_calls;
}
static void native_interpolate(void *c,void *parameter) {
  (void)c;++interpolate_calls;float *p=parameter;
  for(unsigned i=0;i<6;++i)p[i]*=.5f;
  p[13]=.287f; // native optical transition must remain, not custom FOV
}
static void native_update(void *camera,void *parameter) {
  ++native_calls;if(!camera || !parameter)return;
  float *p=parameter,target[3];memcpy(target,raw_target,sizeof(target));
  pes_stadium_v2_target(camera,target,actual_ball);
  // Stand-in for native ground-height shaping at the tested call boundary.
  target[1]=.5f;
  pes_stadium_v2_trace(camera,NULL,target,trace_state,velocity,old,accel,NULL,
      40,-20,25,1,false,(void*)1,(void*)2,(void*)3,(void*)4);
  for(unsigned i=0;i<24;++i)p[i]=100.f+i;
  memcpy(p,target,sizeof(target));
  // Native final eye formula; the optional owned ELF test executes its bytes.
  p[3]=target[0]*.39f;p[4]=21;p[5]=70;p[13]=.3f;p[18]=0;
  pes_stadium_v2_interpolate(camera,p);
}
static void (*match_inplay_camera_update_original)(void*,void*)=native_update;
static unsigned footballnx_tribune_view(float *p){p[13]=.77f;return 1;}
''' + function(HOOKS,'pes_inplay_camera_update') + r'''
int main(void) {
  stadium_v2_trace_original=native_trace;
  stadium_v2_interpolate_original=native_interpolate;
  unsigned char camera[32]={0};float p[24]={0};uint32_t id=6;memcpy(camera+8,&id,4);
  pes_inplay_camera_update(camera,p);
  assert(!trace_calls && interpolate_calls==1 && native_calls==1);
  assert(p[0]==20 && p[1]==.5f && p[2]==-8 && fabsf(p[3]-7.8f)<.00001f);
  assert(p[4]==21 && p[5]==70 && p[13]==.3f);
  for(unsigned i=6;i<24;++i)if(i!=13 && i!=18)assert(p[i]==100.f+i);
  assert(!memcmp(old,trace_state,12));
  assert(velocity[0]==0 && accel[2]==0 && !stadium_v2_scope.active);
  // No target override can leak outside the native Update call.
  float target[]={1,2,3};pes_stadium_v2_target(camera,target,actual_ball);
  assert(target[0]==1);
  // A held ball stays aimed even when the native receiver/group prediction
  // changes. There is no extra ball accessor or future-vector sampling here.
  for(unsigned i=0;i<180;++i) {
    raw_target[0]=40.f*sinf((float)i);raw_target[2]=24.f*cosf((float)i);
    clock_ns+=16666667;pes_inplay_camera_update(camera,p);
    assert(p[0]==20 && p[2]==-8 && p[13]==.3f);
  }
  raw_target[0]=45;raw_target[2]=22;
  // Every unrelated preset and every unavailable scope keeps original tracing.
  for(unsigned selected=0;selected<2;++selected)for(id=0;id<14;++id) {
    memcpy(camera+8,&id,4);pause_camera_stadium_v2=selected;
    unsigned before=trace_calls;clock_ns+=16666667;pes_inplay_camera_update(camera,p);
    assert(trace_calls==before+!(selected && id==6));
    if(!(selected && id==6))assert(p[0]==22.5f && p[4]==10.5f && p[5]==35);
    assert(p[13]==((selected && id==6)?.3f:.287f) && !stadium_v2_scope.active);
  }
  id=6;memcpy(camera+8,&id,4);pause_camera_stadium_v2=1;
  for(unsigned off=0;off<4;++off) {
    live=off!=0;available=off!=1;camera_type=off==2?3:12;p[18]=off==3?1:0;
    unsigned before=trace_calls;pes_inplay_camera_update(camera,p);
    assert(trace_calls==before+1 && p[4]==10.5f);
  }
  live=available=1;camera_type=12;p[18]=0;
  actual_ball[0]=-30;++session;pes_inplay_camera_update(camera,p);assert(p[0]==-30);
  actual_ball[0]=30;++pause_camera_revision;pes_inplay_camera_update(camera,p);assert(p[0]==30);
  actual_ball[0]=NAN;unsigned before=trace_calls;pes_inplay_camera_update(camera,p);
  assert(trace_calls==before+1 && p[0]==22.5f && !stadium_v2_scope.active);
  pes_inplay_camera_update(NULL,p);pes_inplay_camera_update(camera,NULL);
  pause_camera_stadium_v2=0;pause_camera_dynamic_wide_custom=1;
  id=5;memcpy(camera+8,&id,4);pes_inplay_camera_update(camera,p);assert(p[13]==.77f);
}
''')

    def test_installer_boundaries_are_scoped_and_checked(self):
        self.assertIn('stadium_target_words[4]',HOOKS)
        self.assertIn('stadium_trace_words[4]',HOOKS)
        self.assertIn('stadium_interpolate_words[4]',HOOKS)
        update=function(HOOKS,'pes_inplay_camera_update')
        self.assertLess(update.index('stadium_v2_begin'),update.index('match_inplay_camera_update_original(camera'))
        self.assertLess(update.index('match_inplay_camera_update_original(camera'),update.index('stadium_v2_end'))
        self.assertNotIn('stadium_v2_compose',HOOKS)
        interpolate=function(HOOKS,'pes_stadium_v2_interpolate')
        self.assertIn('float native_pose[6]',interpolate)
        self.assertIn('stadium_v2_finish',interpolate)
        target=function(HOOKS,'pes_stadium_v2_target')
        self.assertNotIn('match_ball_info_get_trans',target)
        self.assertNotIn('future',target.lower())


if __name__=='__main__': unittest.main()
