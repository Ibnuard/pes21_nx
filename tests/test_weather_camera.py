"""Removed camera weather path and buffered presentation timing."""
from pathlib import Path
import shutil
import unittest
from test_result_flow import build_and_run, function

ROOT=Path(__file__).resolve().parents[1]


class WeatherCameraTests(unittest.TestCase):
    def test_break_log_keeps_live_time_stadium_and_cascade_observation(self):
        cc=shutil.which('gcc')
        if not cc:self.skipTest('Host C compiler unavailable')
        overlay=(ROOT/'source/overlay.c').read_text()
        render=function(overlay,'overlay_render')
        # Compile the production timing block without the unrelated UI renderer.
        timing=render[:render.index('  if (config.show_fps)')]+'}\n'
        build_and_run(cc,'#include "'+(ROOT/'source/frame_pacing_sample.h').as_posix()+'"\n'+r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
static unsigned live=1,day=1,stadium=1,day_lite=1,notes;
static int cascades;
static uint64_t now=1;
static char logged[320];
static unsigned pes_controller_match_hud_inplay(void){return live;}
static unsigned pes_controller_stadium_weather(void){return 0;}
static unsigned pes_controller_stadium_season(void){return 0;}
static unsigned pes_controller_match_hud_session(void){return 1;}
static unsigned pes_controller_stadium_is_day(void){return day;}
static unsigned pes_controller_stadium_canary_active(void){return stadium;}
static unsigned pes_controller_day_stadium_lite_enabled(void){return day_lite;}
static int pes_controller_stadium_shadow_cascades(void){return cascades;}
static uint64_t armGetSystemTick(void){return now;}
static uint64_t armTicksToNs(uint64_t value){return value;}
static const char *nx_weather_label(unsigned value){(void)value;return "FINE";}
static void pes_controller_referee_performance_note(void){}
static void scene_runtime_note(const char *area,const char *message){
 assert(!live && !strcmp(area,"frame pacing"));++notes;
 snprintf(logged,sizeof(logged),"%s",message);
}
''' + timing + r'''
int main(){
 for(unsigned i=0;i<181;i++){overlay_render();now+=16666667;}
 assert(!notes); // no filesystem output during the sampled live segment
 live=0;day=0;stadium=0;day_lite=0;cascades=4;overlay_render();
 assert(notes==1 && strstr(logged,"time=DAY stadium=1 day_lite=1 csm=0"));
 assert(strstr(logged,"frames=180 avg_us=16666") && strstr(logged,"over20ms=0"));
 now+=60000000000ull;live=1;
 for(unsigned i=0;i<181;i++){overlay_render();now+=20000001;}
 live=0;overlay_render();
 assert(notes==2 && strstr(logged,"time=NIGHT stadium=0 day_lite=0 csm=4"));
 assert(strstr(logged,"frames=180 avg_us=20000") && strstr(logged,"over20ms=180"));
 // Time changes inside the same session also start a new sample.
 live=1;for(unsigned i=0;i<20;i++){overlay_render();now+=16666667;}
 day=1;day_lite=1;cascades=-2;
 for(unsigned i=0;i<121;i++){overlay_render();now+=16666667;}
 live=0;overlay_render();assert(notes==3);
 assert(strstr(logged,"time=DAY") && strstr(logged,"csm=-2") && strstr(logged,"frames=120"));
}
''')

    def test_timing_accumulator_counts_stalls_without_mixing_sessions(self):
        cc=shutil.which('gcc')
        if not cc:self.skipTest('Host C compiler unavailable')
        build_and_run(cc,'#include "'+(ROOT/'source/frame_pacing_sample.h').as_posix()+'"\n'+r'''
#include <assert.h>
int main(){
 NxFramePacingSample s={0};uint64_t now=1;
 nx_frame_pacing_add(&s,now);
 for(int i=0;i<600;i++){now+=16666667;nx_frame_pacing_add(&s,now);}
 assert(s.frames==600 && s.over20==0 && s.over30==0);
 now+=33333334;nx_frame_pacing_add(&s,now);
 assert(s.over20==1 && s.over30==1 && s.worst==33333334);
 s.previous=0;now+=60000000000ull;nx_frame_pacing_add(&s,now);
 assert(s.frames==601); // paused time is not a rendered frame
 s=(NxFramePacingSample){0};nx_frame_pacing_add(&s,now);
 assert(!s.frames && !s.over20 && !s.total);
}
''')

    def test_camera_weather_removed_but_timing_retained(self):
        overlay=(ROOT/'source/overlay.c').read_text()
        self.assertNotIn('weather_lens',overlay)
        render=function(overlay,'overlay_render')
        self.assertIn('else if(pacing.previous)',render)
        self.assertIn('nx_frame_pacing_add',render)
        policy=(ROOT/'source/stadium_lighting_policy.h').read_text()
        self.assertNotIn('nxWeatherHaze',policy)
        self.assertNotIn('nxLensMist',policy)
        self.assertIn('if((scope&24u) && output',policy)
