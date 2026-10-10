"""Removed camera weather path and buffered presentation timing."""
from pathlib import Path
import shutil
import unittest
from test_result_flow import build_and_run, function

ROOT=Path(__file__).resolve().parents[1]


class WeatherCameraTests(unittest.TestCase):
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
