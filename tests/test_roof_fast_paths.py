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

    def test_imported_curves_preserve_v25_shade_with_roots_only_at_soft_edges(self):
        profiles = (ROOT / 'source/stadium_roof_profiles.h').read_text()
        build_and_run(self.compiler, counted_math() + profiles + r'''
static float v25Imported(vec2 p,float edge){
 vec2 extent(nxShellRoof[0].x,nxShellRoof[0].y);
 float inner=nxRoofDistance(p,extent,nxShellRoof[0].z);
 if(inner<=-edge)return 1;
 vec2 side=abs(p)-extent;
 float panel=side.x>side.y?(p.x<0?nxShellRoof[3].x:nxShellRoof[3].y):(p.y<0?nxShellRoof[3].z:nxShellRoof[3].w);
 if(panel<.5)return 1;
 float outer=nxRoofDistance(p,vec2(nxShellRoof[1].x,nxShellRoof[1].y),nxShellRoof[1].z);
 if(outer>=edge)return 1;
 float roof=1;
 if(inner<edge)roof=smoothstep(-edge,edge,inner);
 if(outer>-edge)roof*=1-smoothstep(-edge,edge,outer);
 return 1-roof;
}
static unsigned oldRoots,newRoots,samples;
static void compareImported(vec2 p,float edge){
 float inner=referenceDistance(p,vec2(nxShellRoof[0].x,nxShellRoof[0].y),nxShellRoof[0].z);
 float outer=referenceDistance(p,vec2(nxShellRoof[1].x,nxShellRoof[1].y),nxShellRoof[1].z);
 roots=blends=0;float old=v25Imported(p,edge);oldRoots+=roots;
 roots=blends=0;float current=nxImportedRoofProxy(p,edge);newRoots+=roots;
 assert(fabsf(old-current)<.0002f);
 assert(current>=0 && current<=1);
 // Fully lit/shaded curved regions do not need any square root or smoothing.
 if(inner < -edge-.1f || (inner > edge+.1f && (outer < -edge-.1f || outer > edge+.1f)))assert(roots==0);
 ++samples;
}
int main(){
 const float edges[]={8,24,70,120};
 for(int id=2;id<12;id++){
  float values[16];stadium_roof_uniform(id,values);
  for(int i=0;i<4;i++)nxShellRoof[i]=vec4(values[4*i],values[4*i+1],values[4*i+2],values[4*i+3]);
  for(float edge:edges){
   for(int y=-18000;y<=18000;y+=113)for(int x=-18000;x<=18000;x+=127)
    compareImported(vec2(x,y),edge);
   // Sweep both rounded contours, all signs, including exactly +/-edge.
   for(int which=0;which<2;which++)for(int angle=1;angle<90;angle+=3)
    for(int offset=-20;offset<=20;offset++)for(int sx=-1;sx<=1;sx+=2)for(int sy=-1;sy<=1;sy+=2){
     vec4 b=nxShellRoof[which];float r=b.z+edge*offset/20;
     compareImported(vec2(sx*(b.x-b.z+cosf(angle*.0174532925f)*r),
                          sy*(b.y-b.z+sinf(angle*.0174532925f)*r)),edge);
    }
  }
  // Future partial roofs still respect their four directional panel gates.
  nxShellRoof[2].z=0;nxShellRoof[3].y=0;
  for(int x=-16000;x<16000;x+=100)compareImported(vec2(x,100),8);
 }
 assert(oldRoots>100000 && newRoots<oldRoots/8);
 printf("Imported roof: %u samples, square-root calls %u -> %u\n",samples,oldRoots,newRoots);
}
''')

    def test_old_trafford_asymmetric_outer_roof_retains_soft_edges(self):
        profiles = (ROOT / 'source/stadium_roof_profiles.h').read_text()
        build_and_run(self.compiler, counted_math() + profiles + r'''
int main(){
 float values[16];stadium_roof_uniform(12,values);
 for(int i=0;i<4;i++)nxShellRoof[i]=vec4(values[4*i],values[4*i+1],values[4*i+2],values[4*i+3]);
 assert(values[7]==-50 && values[11]==-1850 && values[10]==1);
 const float edges[]={8,24,70,120};
 unsigned lit=0,shaded=0,soft=0;
 for(float edge:edges)for(int y=-17000;y<17000;y+=71)for(int x=-17000;x<17000;x+=89){
  vec2 p(x,y),outerPoint=p-vec2(values[7],values[11]);
  float inner=referenceDistance(p,vec2(values[0],values[1]),values[2]);
  float outer=referenceDistance(outerPoint,vec2(values[4],values[5]),values[6]);
  float expected=1-smoothstep(-edge,edge,inner)*(1-smoothstep(-edge,edge,outer));
  float actual=nxImportedRoofProxy(p,edge);
  assert(actual>=0 && actual<=1 && fabsf(actual-expected)<.0002f);
  lit+=actual==1;shaded+=actual==0;soft+=actual>0 && actual<1;
 }
 assert(lit>10000 && shaded>10000 && soft>1000);
}
''')

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
