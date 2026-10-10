"""Execute the shipped GLSL math: local weather patches, no particle lifecycle."""
from pathlib import Path
import shutil
import sys
import unittest
from test_result_flow import build_and_run

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from stadium_lite_preview import host_math


class PitchWeatherSurfaceTests(unittest.TestCase):
    def test_surface_coverage_baselines_paint_and_camera_veil(self):
        cc = shutil.which('g++')
        if not cc:
            self.skipTest('Host C++ compiler unavailable')
        build_and_run(cc, host_math() + r'''
int main(){
 const vec3 grass(.12,.30,.065), paint(.7,.7,.7);
 for(int day=0;day<2;day++)for(int w=0;w<2;w++)for(int winter=0;winter<2;winter++){
  nxDayStadium=day;nxStadiumClimate=vec4(w,winter,0,1);
  assert(nxPitchWeather(grass,vec3(10,20,0)).g==grass.g);
 }
 nxDayStadium=1;nxStadiumClimate=vec4(2,0,0,1);
 int count=0,wetCount=0,snowCount=0;float lo=1,hi=0;
 for(int y=-3300;y<=3300;y+=60)for(int x=-5200;x<=5200;x+=60){
  vec3 pos(x,y,0);vec2 coverage=nxWeatherCoverage(pos);
  assert(coverage.x>=0 && coverage.x<=1 && coverage.y>=0 && coverage.y<=1);
  ++count;wetCount+=coverage.x>.4;snowCount+=coverage.y>.12;
  nxStadiumClimate.y=0;vec3 wet=nxPitchWeather(grass,pos);
  assert(wet.g>=grass.g*.50 && wet.g<=grass.g*.92);
  lo=min(lo,wet.g);hi=max(hi,wet.g);
  assert(nxPitchWeather(grass,pos).g==wet.g); // no frame/time/camera dependency
  nxStadiumClimate.y=1;vec3 snow=nxPitchWeather(grass,pos);
  assert(snow.b>=wet.b && snow.g<.66);
  assert(nxPitchWeather(paint,pos).r==paint.r); // preserve painted lines
 }
 assert(hi-lo>.075); // real spatial texture, not a uniform tint
 assert(wetCount>count*.10 && wetCount<count*.70);
 assert(snowCount>count*.025 && snowCount<count*.35); // thin, broken coverage
 assert(nxPitchWeather(grass,vec3(6000,0,0)).g==grass.g);
 assert(nxPitchWeather(grass,vec3(0,0,170)).g==grass.g);
}
''')

    def test_particle_hooks_are_not_installed(self):
        source = (ROOT / 'source/ue4_hooks.c').read_text()
        self.assertNotIn('#include "weather_scene.inc"', source)
        self.assertNotIn('install_weather_scene(module);', source)
        self.assertIn('install_native_weather(module);', source)
        self.assertNotIn('NX_WEATHER_SNOW', (ROOT/'source/match_environment.h').read_text())
