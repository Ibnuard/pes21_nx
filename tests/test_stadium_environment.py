"""Day presets affect receivers and turf while the accepted defaults stay put."""
from pathlib import Path
import shutil
import sys
import unittest
from test_result_flow import build_and_run

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from stadium_lite_preview import host_math


class StadiumEnvironmentTests(unittest.TestCase):
    def test_rain_light_is_darker_in_summer_bright_and_cool_in_winter(self):
        cc = shutil.which('g++')
        if not cc:
            self.skipTest('host C++ compiler unavailable')
        build_and_run(cc, host_math() + r'''
static float lum(vec3 v){return dot(v,vec3(.2126,.7152,.0722));}
int main(){
 nxDayStadium=1;nxNightIndirect=0;
 const vec3 lamp(1.0);
 nxStadiumClimate=vec4(0,0,0,0);
 vec3 fine=nxDirectLight(lamp,1)*.65+nxAmbientLight(lamp,1)*.35;
 nxStadiumClimate.x=1;
 vec3 cloud=nxDirectLight(lamp,1)*.65+nxAmbientLight(lamp,1)*.35;
 for(int repeat=0;repeat<100;repeat++){
  nxStadiumClimate=vec4(2,0,0,1);
  vec3 rain=nxDirectLight(lamp,1)*.65+nxAmbientLight(lamp,1)*.35;
  assert(lum(rain)<lum(cloud)*.9);
  nxStadiumClimate.y=1;
  vec3 snow=nxDirectLight(lamp,1)*.65+nxAmbientLight(lamp,1)*.35;
  assert(lum(snow)>lum(fine)*.90 && lum(snow)<lum(fine)*1.05);
  assert(snow.b>snow.g && snow.g>snow.r);
  nxStadiumClimate=vec4(0,0,0,0);
  assert(nxDirectLight(lamp,1).g==1.0);
 }
 nxDayStadium=0;nxNightIndirect=1;
 nxStadiumClimate=vec4(2,0,0,1);assert(nxRainLightScale().g<1);
 nxStadiumClimate.y=1;vec3 night=nxRainLightScale();
 assert(night.b>night.g && night.g>night.r);
 for(int w=0;w<2;w++)for(int season=0;season<2;season++){
  nxStadiumClimate=vec4(w,season,0,0);
  vec3 scale=nxRainLightScale();assert(scale.r==1 && scale.g==1 && scale.b==1);
 }
}
''')

    def test_settings_drive_distinct_presets_and_preserve_default_and_night(self):
        cc = shutil.which('g++')
        if not cc:
            self.skipTest('host C++ compiler unavailable')
        code = host_math() + '\n#include "' + (ROOT/'source/stadium_environment.h').as_posix() + '"\n'
        build_and_run(cc, code + r'''
static void set(unsigned w,unsigned s,unsigned t,unsigned p){
 float v[4];stadium_environment_uniform(stadium_environment_key(w,s,t,p),v);
 nxStadiumClimate=vec4(v[0],v[1],v[2],v[3]);
}
static float luminance(vec3 v){return dot(v,vec3(.2126,.7152,.0722));}
int main(){
 set(0,0,1,1);nxDayStadium=1;nxNightIndirect=0;
 const vec3 grass(.0284,.0802,.008),lamp(.6,.9,.3);
 vec3 turf=nxPitchGrain(grass,.5),sun=nxDirectLight(lamp,1),sky=nxAmbientLight(lamp,1);
 float sheen=nxPitchSheen(lamp,1).g;
 assert(fabsf(sheen-luminance(lamp)*.025)<.000001f);
 assert(fabsf(sun.g-luminance(lamp))<.000001f);
 assert(fabsf(sky.g-luminance(lamp))<.000001f);
 float minRoof=1;vec3 shade(0);
 for(int y=-5500;y<=5500;y+=500)for(int x=-7500;x<=7500;x+=500){
  vec3 p(x,y,0);float roof=nxRoofVisibility(p);
  if(roof<minRoof){minRoof=roof;shade=p;}
 }
 assert(minRoof<.01);
 set(1,0,1,1);
 assert(luminance(nxDirectLight(lamp,1))<luminance(sun)*.7);
 assert(luminance(nxAmbientLight(lamp,1))>luminance(sky));
 assert(nxRoofVisibility(shade)>.6); // diffused daylight weakens roof contrast
 set(0,1,1,1);vec3 winter=nxDirectLight(lamp,1);
 assert(winter.b>winter.r && winter.r<sun.r);
 int changed=0;
 for(int y=-4500;y<=4500;y+=200)for(int x=-6500;x<=6500;x+=200){
  vec3 p(x,y,170);set(0,0,1,1);float a=nxRoofVisibility(p);
  set(0,1,1,1);changed+=fabsf(nxRoofVisibility(p)-a)>.1;
 }
 assert(changed>20); // lower winter sun moves ground and elevated receivers
 set(0,0,0,1);float shortDetail=nxPitchGrain(grass,1).g-nxPitchGrain(grass,0).g;
 set(0,0,2,1);float longDetail=nxPitchGrain(grass,1).g-nxPitchGrain(grass,0).g;
 assert(longDetail>shortDetail*1.5);
 set(0,0,1,2);
 assert(nxPitchGrain(grass,.5).g<turf.g);
 assert(nxPitchSheen(lamp,1).g>sheen*3);
 set(0,0,1,0);
 assert(nxPitchGrain(grass,.5).g>turf.g);
 assert(nxPitchSheen(lamp,1).g<sheen);
 set(99,99,99,99);assert(nxPitchGrain(grass,.5).g==turf.g);
 nxDayStadium=0;nxNightIndirect=1;
 for(unsigned w=0;w<2;w++)for(unsigned s=0;s<2;s++)
 for(unsigned t=0;t<3;t++)for(unsigned p=0;p<3;p++){
  set(w,s,t,p);
  assert(nxPitchGrain(grass,.5).g==grass.g);
  assert(nxPitchSheen(lamp,.7).g==lamp.g);
  vec3 light=nxDirectLight(lamp,1);
  assert(light.r==sun.r && light.g==sun.g && light.b==sun.b);
 }
}
''')
