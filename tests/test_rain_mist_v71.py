"""Execute the actual emitted mist math; Fine/Cloudy must remain exact."""
from pathlib import Path
import shutil
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from stadium_lite_preview import host_math
from test_result_flow import build_and_run


def test_actual_rain_mist_math_is_bounded_and_weather_owned():
    compiler=shutil.which('g++')
    if not compiler: pytest.skip('Host C++ compiler unavailable')
    build_and_run(compiler,host_math()+r'''
int main(){
 vec3 color(.2,.4,.1),origin(0,0,0);
 for(int weather=0;weather<2;weather++){
  nxStadiumClimate=vec4(weather,0,0,0);
  vec3 value=nxRainMist(color,origin,vec3(8000,3000,2000));
  assert(value.x==color.x && value.y==color.y && value.z==color.z);
 }
 nxStadiumClimate=vec4(2,0,0,0);nxDayStadium=1;
 vec3 near=nxRainMist(color,origin,origin);
 assert(near.x==color.x && near.y==color.y && near.z==color.z);
 float previous=0;
 for(int distance=1;distance<100000;distance+=317){
  vec3 value=nxRainMist(color,origin,vec3(distance,0,0));
  float amount=(value.z-color.z)/(.40-.1);
  assert(amount>=previous-.000001f && amount<=.420001f);
  previous=amount;
 }
 vec3 above(0,10000,3000),top=nxRainMist(color,above,vec3(0,-5000,1800));
 assert(top.z>color.z+.07f); // Raised audience is inside the atmosphere too.
 // The reported Day/High wide camera must produce an appreciable, bounded
 // colour separation, not merely a compile-time presence of the helper.
 vec3 camera(0,-5000,1800),visible=nxRainMist(color,origin,camera);
 float amount=(visible.z-color.z)/(.4-.1);
 assert(amount>.18f && amount<.23f);
 assert(visible.z-color.z>.05f);
 // Foreground stays clear, and a reversed ray integrates the same air.
 vec3 close=nxRainMist(color,vec3(0,100,170),vec3(0,0,170));
 assert(close.z-color.z<.002f);
 vec3 reversed=nxRainMist(color,camera,origin);
 assert(fabs(visible.z-reversed.z)<.000001f);
 // Night is a bounded darker atmosphere, with the same weather ownership.
 nxDayStadium=0;
 vec3 night=nxRainMist(color,origin,camera);
 assert(night.x<color.x && night.y<color.y && night.z>color.z);
 float n=(night.z-color.z)/(.12f-.1f);assert(n>0 && n<=.32f);
}
''')
