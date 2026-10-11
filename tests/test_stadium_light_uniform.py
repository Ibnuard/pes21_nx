"""Compare cached CPU factors with the previous fragment lighting equations."""
from pathlib import Path
import shutil
import sys
import unittest

from test_result_flow import build_and_run

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from stadium_lite_preview import host_math


class StadiumLightUniformTests(unittest.TestCase):
    def test_all_climates_keep_previous_light_and_surface_response(self):
        compiler = shutil.which('g++')
        if not compiler:
            self.skipTest('Host C++ compiler unavailable')
        build_and_run(compiler, host_math() + r'''
static void same(vec3 a,vec3 b){
 assert(fabsf(a.r-b.r)<.000002f && fabsf(a.g-b.g)<.000002f && fabsf(a.b-b.b)<.000002f);
}
int main(){
 for(int day=0;day<2;day++)for(int weather=0;weather<3;weather++)
 for(int season=0;season<2;season++)for(int turf=-1;turf<2;turf++)
 for(int wet=-1;wet<2;wet++) {
  nxDayStadium=day;nxNightIndirect=!day;
  nxStadiumClimate=vec4(weather,season,turf,wet);nxUpdateLightUniforms();
  const float winter=day?season:0;
  vec3 seasonal(1-.07f*winter,1-.025f*winter,1+.05f*winter);
  vec3 rain(1);
  if(weather==2)rain=mix(vec3(.84f),day?vec3(1):vec3(.97f,1.02f,1.07f),(float)season);
  float cloud=day?min((float)weather,1):0;
  if(weather==2)cloud*=1-.92f*season;
  same(nxRainLightScale(),rain);
  for(int light=0;light<7;light++)for(int visibility=0;visibility<=10;visibility++){
   vec3 lamp(.2f*light,.1f*light,.3f*light);float v=visibility*.1f;
   vec3 neutral=nxNeutralLight(lamp);
   same(nxDirectLight(lamp,v),neutral*seasonal*rain*mix(1,.62f,cloud)*mix(.12f,1,v));
   same(nxAmbientLight(lamp,v),neutral*seasonal*rain*mix(1,1.10f,cloud)*mix(.56f,1,v));
   same(nxPitchSheen(lamp,v),day?neutral*((.025f+wet*(wet<0?.015f:.065f))*v):lamp);
  }
  for(int grain=0;grain<=10;grain++) {
   vec3 grass(.0284f,.0802f,.008f);float g=grain*.1f;
   float contrast=clamp(1+(grass.g-.09f)*5,.85f,1.16f);
   float detail=.16f+.055f*turf,damp=1-wet*(wet<0?.025f:.08f);
   same(nxPitchGrain(grass,g),day?grass*vec3(.58f,1.12f,.46f)*(contrast*damp*mix(1-detail,1+detail,g)):grass);
  }
 }
}
''')


if __name__ == '__main__':
    unittest.main()
