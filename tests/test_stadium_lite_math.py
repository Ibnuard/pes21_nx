"""Run the actual emitted geometry/lighting functions on the host."""
import shutil
import sys
from pathlib import Path
import unittest
from test_result_flow import build_and_run, function

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from stadium_lite_preview import host_math


class StadiumLiteMathTests(unittest.TestCase):
    def test_roof_holes_projection_skin_response_and_neutral_lighting(self):
        cc=shutil.which('g++')
        if not cc:self.skipTest('Host C++ compiler unavailable')
        build_and_run(cc,host_math()+r'''
int main(){
 assert(nxRoofProxy(vec2(0,0),8)==1); // centre opening
 assert(nxRoofProxy(vec2(9000,0),8)==1); // outside roof
 assert(nxRoofProxy(vec2(200,3800),8)==0); // solid near edge
 assert(nxRoofProxy(vec2(200,4140),8)==1); // first skylight
 assert(nxRoofProxy(vec2(0,4140),8)==0); // beam within skylight
 assert(nxRoofProxy(vec2(200,4900),8)==1); // second skylight
 int dark=0,lit=0,changed=0;
 for(int y=-3400;y<=3400;y+=50)for(int x=-5250;x<=5250;x+=50){
  vec3 ground(x,y,0), head(x,y,170);
  float a=nxRoofVisibility(ground),b=nxRoofVisibility(head);
  assert(a>=0 && a<=1 && b>=0 && b<=1);
  dark+=a<.1;lit+=a>.9;changed+=fabsf(a-b)>.5;
  // Same light ray hits the same roof point at every receiver height.
  vec2 shifted=vec2(x,y)+nxSun.xy*(170/nxSun.z);
  float same=nxRoofVisibility(vec3(shifted.x,shifted.y,170));
  assert(fabsf(a-same)<.0002);
 }
 assert(dark>1000 && lit>1000 && changed>100);
 for(int day=0;day<2;day++)for(int night=0;night<2;night++){
  nxDayStadium=day;nxNightIndirect=night;
  for(int r=0;r<12;r++)for(int g=0;g<12;g++)for(int b=0;b<12;b++){
   vec3 c(r/4.f,g/4.f,b/4.f),n=nxNeutralLight(c);
   if(day || night){float y=dot(c,vec3(.2126,.7152,.0722));
    assert(n.r==n.g && n.g==n.b && fabsf(n.r-y)<.00001);
   }else assert(n.r==c.r && n.g==c.g && n.b==c.b);
  }
 }
 nxDayStadium=1;nxNightIndirect=0;
 // Darkening acts on lighting before skin/kit albedo and preserves its hue.
 vec3 skin(.48,.24,.12),sun(1,1,1);
 vec3 litLight=nxDirectLight(sun,1),shadeLight=nxDirectLight(sun,0);
 assert(shadeLight.r<litLight.r*.2 && nxAmbientLight(sun,0).r>.5);
 assert(fabsf((skin.r*shadeLight.r)/(skin.g*shadeLight.g)-2)<.00001);
 // Day-only green recovery after neutral light; white paint stays untouched.
 vec3 white(.8,.8,.8),grass(.03,.07,.006);
 assert(nxPitchGrain(white,0).r==white.r);
 vec3 middle=nxPitchGrain(grass,.5);
 assert(middle.g/middle.r > grass.g/grass.r*1.4);
 assert(middle.g/middle.b > grass.g/grass.b*1.5);
 float oldY=dot(grass,vec3(.2126,.7152,.0722));
 float newY=dot(middle,vec3(.2126,.7152,.0722));
 assert(newY>oldY*.8 && newY<oldY*1.15);
 assert(fabsf((nxPitchGrain(grass,0).g+nxPitchGrain(grass,1).g)*.5-middle.g)<.00001);
 assert(nxPitchSheen(vec3(.875,1,0),1).r<.025);
 nxDayStadium=0;
 assert(nxPitchGrain(grass,0).g==grass.g);
 assert(nxPitchGrain(grass,1).r==grass.r);
 assert(nxPitchSheen(vec3(.875,1,0),1).g==1);
}
''')

    def test_day_grass_has_stronger_green_and_stripe_contrast_without_night_changes(self):
        cc=shutil.which('g++')
        if not cc:self.skipTest('Host C++ compiler unavailable')
        build_and_run(cc,host_math()+r'''
int main(){
 nxDayStadium=1;
 // Representative decoded dark/light stripes from the installed turf.
 vec3 dark(.0284,.0802,.0080),light(.0382,.1070,.0123);
 vec3 d=nxPitchGrain(dark,.5),l=nxPitchGrain(light,.5);
 assert(l.g/d.g > light.g/dark.g*1.12); // contrast, not uniform brightening
 vec3 v5=dark*vec3(.82,1.18,.74);
 assert(d.g/d.r>v5.g/v5.r*1.3 && d.g/d.b>v5.g/v5.b*1.4);
 assert(dot(d,vec3(.2126,.7152,.0722)) < dot(v5,vec3(.2126,.7152,.0722)));
 for(int i=0;i<=100;i++){
  vec3 paint(i/100.f); // marking/neutral pixels must not receive the turf grade
  vec3 out=nxPitchGrain(paint,.2);
  assert(out.r==paint.r && out.g==paint.g && out.b==paint.b);
 }
 nxDayStadium=0;
 for(int night=0;night<2;night++){
  nxNightIndirect=night;
  for(int r=0;r<10;r++)for(int g=0;g<10;g++)for(int b=0;b<10;b++){
   vec3 rgb(r/10.f,g/10.f,b/10.f);
   for(int detail=0;detail<3;detail++){
    vec3 out=nxPitchGrain(rgb,detail*.5f),sheen=nxPitchSheen(rgb,.3);
    assert(out.r==rgb.r && out.g==rgb.g && out.b==rgb.b);
    assert(sheen.r==rgb.r && sheen.g==rgb.g && sheen.b==rgb.b);
   }
  }
 }
}
''')

    def test_saved_quality_gates_cascade_replacement(self):
        cc=shutil.which('gcc')
        if not cc:self.skipTest('Host C compiler unavailable')
        source=(ROOT/'source/ue4_hooks.c').read_text()
        build_and_run(cc,'#include <stdint.h>\n#include <assert.h>\n'
            'static uint32_t main_menu_video_graphics,exhibition_settings_time_zone;\n'
            +function(source,'pes_controller_stadium_is_day')
            +function(source,'pes_controller_roof_shadow_enabled')
            +function(source,'pes_controller_day_stadium_lite_enabled')+r'''
int main(){for(unsigned q=0;q<4;q++)for(unsigned t=0;t<2;t++){
 main_menu_video_graphics=q;exhibition_settings_time_zone=t;
 assert(pes_controller_day_stadium_lite_enabled()==(q==2 && t==0));
}}
''')
        entry=function(source,'pes_exhibition_match_setup_data_entry')
        self.assertIn('pes_controller_day_stadium_lite_enabled() ? 1u : 2u',entry)


if __name__=='__main__':unittest.main()
