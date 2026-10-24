"""Execute production cloud/haze math, including periodic motion and ownership."""
from pathlib import Path
import shutil
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from stadium_lite_preview import host_math
from test_result_flow import build_and_run


def test_cloud_shadows_are_bounded_pitch_only_and_continuous():
    compiler=shutil.which('g++')
    if not compiler:pytest.skip('Host C++ compiler unavailable')
    build_and_run(compiler,host_math()+r'''
int main(){
 vec3 color(.09,.18,.045),pos(0,0,0);
 nxCloudMotion=vec2(.125,1);
 for(int weather=0;weather<3;weather+=2){
  nxStadiumClimate=vec4(weather,0,0,0);
  vec3 v=nxPitchCloud(color,pos);assert(v.x==color.x&&v.y==color.y&&v.z==color.z);
 }
 nxStadiumClimate=vec4(1,0,0,0);nxCloudMotion.y=0;
 assert(nxPitchCloud(color,pos).y==color.y);
 nxCloudMotion.y=1;
 assert(nxPitchCloud(color,vec3(0,0,170)).y==color.y);
 assert(nxPitchCloud(color,vec3(6000,0,0)).y==color.y);
 float motion=0,min_factor=1,max_factor=0;
 for(int y=-3300;y<=3300;y+=300)for(int x=-5100;x<=5100;x+=300){
  pos=vec3(x,y,0);nxCloudMotion.x=0;float a=nxPitchCloud(color,pos).y;
  nxCloudMotion.x=.125;float b=nxPitchCloud(color,pos).y;
  min_factor=min(min_factor,a/color.y);max_factor=max(max_factor,a/color.y);
  motion+=fabs(a-b);
  nxCloudMotion.x=.999999f;float before=nxPitchCloud(color,pos).y;
  nxCloudMotion.x=0;float after=nxPitchCloud(color,pos).y;
  assert(fabs(before-after)<.00001f); // 240-second phase wrap has no jump.
 }
 assert(min_factor>=.89999f && min_factor<.94f && max_factor>.99f);
 assert(motion>1.f); // Slow motion must change the actual receiver, not only a clock.
 // Mowing normalization must not erase the shadow on authored stadiums.
 nxStadiumProfile=13;pos=vec3(0,0,0);nxCloudMotion=vec2(0,0);
 vec3 base=nxPitchMowing(color,pos);nxCloudMotion.y=1;
 vec3 shaded=nxPitchMowing(color,pos);assert(shaded.y<=base.y&&shaded.y>=base.y*.89999f);
}
''')


def test_winter_haze_is_thinner_than_rain_with_exact_other_weather():
    compiler=shutil.which('g++')
    if not compiler:pytest.skip('Host C++ compiler unavailable')
    build_and_run(compiler,host_math()+r'''
int main(){
 vec3 black(0),pos(0),camera(0,-5000,1800);
 nxDayStadium=1;nxStadiumClimate=vec4(2,0,0,0);
 float rain=nxRainMist(black,pos,camera).z/.40f;
 nxStadiumClimate.y=1;
 float snow=nxRainMist(black,pos,camera).z/.53f;
 assert(snow>0 && snow<rain*.5f);
 assert(nxRainMist(black,pos,vec3(0,-100000,1000)).z<=.53f*.18001f);
 for(int weather=0;weather<2;weather++){
  nxStadiumClimate.x=weather;assert(nxRainMist(black,pos,camera).z==0);
 }
}
''')
