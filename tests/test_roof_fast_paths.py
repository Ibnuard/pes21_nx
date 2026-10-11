"""Compare emitted roof math to the accepted shadow, including its boundaries.

Operation counters exercise the actual helper branches on the host. They are
not GPU instruction counts or a device frame-rate benchmark.
"""
from pathlib import Path
import shutil
import sys
import unittest

from test_result_flow import build_and_run

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from stadium_lite_preview import host_math


# Frozen pre-v20 equations: keep this independent of the optimized helpers.
REFERENCE = r'''
static float referenceDistance(vec2 p,vec2 extent,float radius){
 vec2 q=abs(p)-extent+vec2(radius);
 return length(max(q,vec2(0)))+min(max(q.x,q.y),0)-radius;
}
static float referenceRoof(vec2 p,float edge,int anfield){
 if(anfield){
  float inner=referenceDistance(p,vec2(5650,4200),150);
  float outer=referenceDistance(p,vec2(11000,8500),250);
  return 1-smoothstep(-edge,edge,inner)*(1-smoothstep(-edge,edge,outer));
 }
 float inner=referenceDistance(p,vec2(5700,3700),1400);
 float outer=referenceDistance(p,vec2(7800,5800),2000);
 float roof=smoothstep(-edge,edge,inner)*(1-smoothstep(-edge,edge,outer));
 float slot1=smoothstep(260-edge,260+edge,inner)*(1-smoothstep(620-edge,620+edge,inner));
 float slot2=smoothstep(1050-edge,1050+edge,inner)*(1-smoothstep(1360-edge,1360+edge,inner));
 vec2 side=abs(p)-vec2(4300,2300);
 float along=side.x>side.y?p.y:p.x;
 float beam=abs(fract(along/650+.5)-.5)*650;
 float opening=max(slot1,slot2)*smoothstep(24-edge,24+edge,beam);
 return 1-roof*(1-opening);
}
static float referenceVisibility(vec3 world){
 vec3 sun=MobileDirectionalLight_DirectionalLightDirectionAndShadowTransition.xyz;
 float season=1+.45*nxStadiumClimate.y;
 vec3 light(sun.x*season,sun.y*season,sun.z);
 vec2 p=world.xy+light.xy*((3600-world.z)/max(light.z,.2));
 float edge=clamp(max(fwidth(p.x),fwidth(p.y))*.75,8,70)+50*min(nxStadiumClimate.x,1);
 if(nxStadiumProfile>.5)
  p=world.xy+light.xy*((3000-world.z)/max(light.z,.2));
 return mix(referenceRoof(p,edge,nxStadiumProfile>.5),1,.65*min(nxStadiumClimate.x,1));
}
static float candidateRoof(vec2 p,float edge,int anfield){
 return anfield?nxAnfieldRoofProxy(p,edge):nxRoofProxy(p,edge);
}
'''


def counted_math():
    code = host_math()
    code = code.replace('using std::abs;', 'using std::abs;\n'
        'static unsigned roots, blends, derivatives;\nstatic float footprint;')
    code = code.replace('return sqrtf(v.x*v.x+v.y*v.y);',
                        '++roots;return sqrtf(v.x*v.x+v.y*v.y);')
    code = code.replace('float t=clamp((v-a)/(b-a),0,1);',
                        '++blends;float t=clamp((v-a)/(b-a),0,1);')
    code = code.replace('(void)v;return 0;', '(void)v;++derivatives;return footprint;')
    return code + REFERENCE


class RoofFastPathTests(unittest.TestCase):
    def setUp(self):
        self.compiler = shutil.which('g++')
        if not self.compiler:
            self.skipTest('Host C++ compiler unavailable')

    def test_both_roofs_match_interior_corners_skylights_and_soft_edges(self):
        build_and_run(self.compiler, counted_math() + r'''
static void compare(vec2 p,float edge,int profile){
 float a=referenceRoof(p,edge,profile),b=candidateRoof(p,edge,profile);
 assert(b>=0 && b<=1 && fabsf(a-b)<.0002);
}
int main(){
 const float edges[]={8,12.5,32,70,90,120};
 unsigned seed=71;
 for(int profile=0;profile<2;profile++)for(float edge:edges){
  // Includes off-pitch geometry visible during close-ups and celebrations.
  for(int y=-10000;y<=10000;y+=100)for(int x=-13000;x<=13000;x+=100)
   compare(vec2(x,y),edge,profile);
  for(int i=0;i<40000;i++){
   seed=seed*1664525u+1013904223u;float x=(seed&0xffffff)/16777215.f*26000-13000;
   seed=seed*1664525u+1013904223u;float y=(seed&0xffffff)/16777215.f*20000-10000;
   compare(vec2(x,y),edge,profile);
  }
  // Sweep both sides of each exact fast-path/slot threshold in sub-centimetres.
  const float distances[]={-edge,edge,260-edge,260+edge,620-edge,620+edge,
                          1050-edge,1050+edge,1360-edge,1360+edge};
  for(float d:distances)for(int n=-16;n<=16;n++)for(int sign=-1;sign<=1;sign+=2)
   for(int along=-750;along<=750;along+=13){
    float offset=d+n*.0625f;
    compare(vec2(along,sign*((profile?4200:3700)+offset)),edge,profile);
    compare(vec2(sign*((profile?5650:5700)+offset),along),edge,profile);
   }
 }
}
''')

    def test_moving_players_keep_height_season_and_weather_response(self):
        build_and_run(self.compiler, counted_math() + r'''
int main(){
 const float heights[]={0,80,170,215};
 const float widths[]={0,32,160};
 int transitions[2]={0,0};
 for(int profile=0;profile<2;profile++)for(int weather=0;weather<3;weather++)
 for(int season=0;season<2;season++)for(float width:widths){
  nxStadiumProfile=profile;nxStadiumClimate=vec4(weather,season,0,0);footprint=width;
  for(int y=-3400;y<=3400;y+=80)for(int x=-5250;x<=5250;x+=80){
   for(float height:heights){
    vec3 world(x,y,height);
    float expected=referenceVisibility(world);
    derivatives=0;
    float actual=nxRoofVisibility(world);
    assert(derivatives==2); // before every spatial exit, even in flat regions
    assert(fabsf(expected-actual)<.0002);
   }
   float ground=nxRoofVisibility(vec3(x,y,0)),head=nxRoofVisibility(vec3(x,y,170));
   transitions[profile]+=fabsf(ground-head)>.3;
  }
 }
 assert(transitions[0]>100 && transitions[1]>100);
 nxDayStadium=1;nxNightIndirect=0;nxStadiumClimate=vec4(0,0,0,0);nxUpdateLightUniforms();
 assert(fabsf(nxDirectLight(vec3(1),0).r-.12)<.00001);
 assert(fabsf(nxAmbientLight(vec3(1),0).r-.56)<.00001);
}
''')

    def test_flat_shade_skips_roots_and_edge_blends(self):
        build_and_run(self.compiler, counted_math() + r'''
int main(){
 for(int profile=0;profile<2;profile++){
  vec2 shade=profile?vec2(6200,100):vec2(200,3900);
  roots=blends=0;
  assert(referenceRoof(shade,8,profile)==0);
  unsigned oldRoots=roots,oldBlends=blends;
  roots=blends=0;
  assert(candidateRoof(shade,8,profile)==0);
  assert(oldRoots==2 && oldBlends==(profile?2u:7u));
  assert(roots==0 && blends==0);
  roots=blends=0;
  assert(candidateRoof(vec2(0,0),8,profile)==1);
  assert(roots==0 && blends==0);
 }
 // Soft borders and rounded corners must still do the work they require.
 roots=blends=0;float border=nxAnfieldRoofProxy(vec2(5650,0),8);
 assert(border>0 && border<1 && blends==1);
 roots=blends=0;
 nxRoofProxy(vec2(5500,3700),8);
 assert(roots>0);
}
''')


if __name__ == '__main__':
    unittest.main()
