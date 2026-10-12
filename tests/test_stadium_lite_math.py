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
    def test_camp_nou_single_roof_keeps_midfield_clear_in_both_seasons(self):
        cc=shutil.which('g++')
        if not cc:self.skipTest('Host C++ compiler unavailable')
        profiles=(ROOT/'source/stadium_roof_profiles.h').read_text()
        build_and_run(cc,host_math()+profiles+r'''
int main(){
 float values[16];stadium_roof_uniform(13,values);nxStadiumProfile=13;
 for(int i=0;i<4;i++)nxShellRoof[i]=vec4(values[i*4],values[i*4+1],values[i*4+2],values[i*4+3]);
 assert(values[10]==0 && values[12]==0 && values[13]==0 && values[14]==0 && values[15]==1);
 assert(nxImportedRoofProxy(vec2(0,7000),8)==0);
 assert(nxImportedRoofProxy(vec2(0,-7000),8)==1);
 assert(nxImportedRoofProxy(vec2(7000,0),8)==1);
 assert(nxImportedRoofProxy(vec2(-7000,0),8)==1);
 for(int weather=0;weather<3;weather++)for(int winter=0;winter<2;winter++) {
  nxStadiumClimate=vec4(weather,winter,0,0);unsigned total=0,shade=0;
  for(int y=-3400;y<=3400;y+=50)for(int x=-5250;x<=5250;x+=50) {
   float ground=nxRoofVisibility(vec3(x,y,0));
   vec2 head=vec2(x,y)+nxSun.xy*((1+.45f*winter)*185/nxSun.z);
   assert(fabsf(ground-nxRoofVisibility(vec3(head.x,head.y,185)))<.002f);
   if(abs(x)<2500 && abs(y)<1500)assert(ground==1);
   total++;shade+=ground<.99f;
  }
  assert(shade>total*.01f && shade<total*.20f);
 }
}
''')

    def test_tall_roofs_use_overhead_sun_and_shade_ten_to_twenty_percent(self):
        cc=shutil.which('g++')
        if not cc:self.skipTest('Host C++ compiler unavailable')
        profiles=(ROOT/'source/stadium_roof_profiles.h').read_text()
        build_and_run(cc,host_math()+profiles+r'''
int main(){
 for(int id=6;id<=7;id++) {
  float values[16];stadium_roof_uniform(id,values);nxStadiumProfile=id;
  for(int i=0;i<4;i++)nxShellRoof[i]=vec4(values[4*i],values[4*i+1],values[4*i+2],values[4*i+3]);
  unsigned total=0,shade=0;
  for(int weather=0;weather<3;weather++)for(int winter=0;winter<2;winter++) {
   nxStadiumClimate=vec4(weather,winter,0,0);
   for(int direction=0;direction<3;direction++) {
    MobileDirectionalLight_DirectionalLightDirectionAndShadowTransition.xyz=vec3(.3f*direction-.3f,.6f-.5f*direction,.25f+.2f*direction);
    for(int y=-3400;y<=3400;y+=50)for(int x=-5250;x<=5250;x+=50) {
     float ground=nxRoofVisibility(vec3(x,y,0));
     assert(fabsf(ground-nxRoofVisibility(vec3(x,y,185)))<.00001f);
     // Deeper left/lower shade must not spill into central play.
     if(abs(x)<=4200 && abs(y)<=2000)assert(ground==1);
     if(weather==0 && winter==0 && direction==0){total++;shade+=ground<.99f;}
     float expected=mix(nxImportedRoofProxy(vec2(x-values[8],y-values[9]),8+50*min(weather,1)),1,.65f*min(weather,1));
     assert(fabsf(ground-expected)<.0001f);
    }
   }
  }
  assert(shade>=total*.10f && shade<=total*.20f);
  nxStadiumClimate=vec4(0,0,0,0);
  assert(nxRoofVisibility(vec3(0,-3375,0))==0); // lower touchline shaded
  assert(nxRoofVisibility(vec3(0,3375,0))==1); // upper touchline stays lit
  assert(nxRoofVisibility(vec3(5200,0,0))==1); // right goal stays lit
  assert(nxRoofVisibility(vec3(-5000,0,0))==0); // 2.5 m inside left goal line
  assert(nxRoofVisibility(vec3(0,-3000,0))==0); // 4 m inside lower touchline
  assert(nxRoofVisibility(vec3(-4400,0,0))==1); // leave the inner field lit
  assert(nxRoofVisibility(vec3(0,-2500,0))==1);
  assert(nxRoofVisibility(vec3(0,-4000,0))==0); // apron still receives the roof
  printf("overhead roof %d: shaded %u/%u ground samples\n",id,shade,total);
 }
}
''')

    def test_imported_roof_is_shared_by_pitch_and_moving_players(self):
        cc=shutil.which('g++')
        if not cc:self.skipTest('Host C++ compiler unavailable')
        profiles=(ROOT/'source/stadium_roof_profiles.h').read_text()
        build_and_run(cc,host_math()+profiles+r'''
int main(){
 for(int id=2;id<12;id++) {
  float values[16];stadium_roof_uniform(id,values);nxStadiumProfile=id;
  for(int i=0;i<4;i++)nxShellRoof[i]=vec4(values[4*i],values[4*i+1],values[4*i+2],values[4*i+3]);
  assert(nxImportedRoofProxy(vec2(0,0),8)==1);
  assert(nxImportedRoofProxy(vec2(40000,0),8)==1);
  assert(nxImportedRoofProxy(vec2((values[0]+values[4])*.5f,0),8)==0);
  for(int weather=0;weather<3;weather++)for(int winter=0;winter<2;winter++) {
   nxStadiumClimate=vec4(weather,winter,0,0);
   float season=1+.45f*winter;
   for(int y=-3400;y<=3400;y+=100)for(int x=-5250;x<=5250;x+=100) {
    float ground=nxRoofVisibility(vec3(x,y,0));
    vec2 shifted=(id==6 || id==7)?vec2(x,y):vec2(x,y)+nxSun.xy*(season*170/nxSun.z);
    float head=nxRoofVisibility(vec3(shifted.x,shifted.y,170));
    assert(ground>=0 && ground<=1 && head>=0 && head<=1);
    assert(fabsf(ground-head)<.002);
   }
  }
 }
}
''')

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
