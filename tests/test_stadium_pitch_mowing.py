"""Shipped mowing math, real shader edits and reuse of the loaded-shell key."""
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from test_night_lighting_policy import shader_sources
from test_result_flow import build_and_run

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from stadium_lite_preview import host_math


class StadiumPitchMowingTests(unittest.TestCase):
    def test_camp_nou_rings_and_old_trafford_straight_bands(self):
        cc = shutil.which('g++')
        if not cc:
            self.skipTest('Host C++ compiler unavailable')
        build_and_run(cc, host_math() + r'''
int main() {
 const vec3 grass(.03,.09,.01);
 nxStadiumProfile=13;
 // Points at the same Euclidean radius have the same shade, including
 // rotations/reflections away from the centre: actual circles, not diamonds.
 for(int radius=100;radius<=5000;radius+=100) {
  const float expected=nxPitchMowing(grass,vec3(radius,0,0)).g;
  for(int angle=0;angle<360;angle+=15) {
   const float a=angle*3.141592653589793f/180;
   const float x=cosf(a)*radius,y=sinf(a)*radius;
   if(fabsf(y)>3500)continue;
   assert(fabsf(nxPitchMowing(grass,vec3(x,y,0)).g-expected)<.00001f);
  }
 }
 assert(nxPitchMowing(grass,vec3(0,0,0)).g>.095f);
 assert(nxPitchMowing(grass,vec3(850,0,0)).g<.085f);
 assert(nxPitchMowing(grass,vec3(1700,0,0)).g>.095f);
 nxStadiumProfile=12;
 for(int x=-5000;x<=5000;x+=100) {
  const float expected=nxPitchMowing(grass,vec3(x,0,0)).g;
  for(int y=-3400;y<=3400;y+=100)
   assert(nxPitchMowing(grass,vec3(x,y,0)).g==expected);
 }
 assert(nxPitchMowing(grass,vec3(0,0,0)).g>.095f);
 assert(nxPitchMowing(grass,vec3(1050,0,0)).g<.085f);
 assert(nxPitchMowing(grass,vec3(2100,0,0)).g>.095f);
}
''')

    def test_owned_accepted_paint_pixels_are_unchanged(self):
        cc = shutil.which('g++')
        if not cc:
            self.skipTest('Host C++ compiler unavailable')
        native = ROOT / 'local-debug/pitch-recreate/verify-final/PesMobile/Content/Assets/bg_lighting_AM1/Textures'
        paths = [native / (n + '.uexp') for n in
                 ('pitch_l_bsm_alp', 'pitch_r_bsm_alp', 'pitch_n_bsm_alp')]
        if not all(p.is_file() for p in paths):
            self.skipTest('Optional accepted local pitch texture fixtures unavailable')
        import numpy as np
        from cooked_texture import Texture
        colors = set()
        for path in paths:
            pixels = np.array(Texture(path).decode())[..., :3]
            # Same native paint criterion used by the accepted texture builder.
            paint = (pixels.min(2) >= 78) & (pixels.max(2) - pixels.min(2) <= 48)
            colors.update(map(tuple, pixels[paint]))
        self.assertGreater(len(colors), 100)
        srgb = np.array(sorted(colors)) / 255.0
        linear = np.where(srgb <= .04045, srgb / 12.92,
                          ((srgb + .055) / 1.055) ** 2.4)
        samples = ',\n'.join('vec3(%.9f,%.9f,%.9f)' % tuple(c) for c in linear)
        build_and_run(cc, host_math() + '\nstatic const vec3 paint[]={' + samples + r'''};
int main() {
 const int ids[]={1,2,8,9,12,13};
 for(int i=0;i<6;i++) {
  nxStadiumProfile=ids[i];
  for(unsigned c=0;c<sizeof(paint)/sizeof(paint[0]);c++) {
   const vec3 a=paint[c];vec3 b=nxPitchMowing(a,vec3(300,400,0));
   assert(a.r==b.r && a.g==b.g && a.b==b.b);
  }
 }
}
''')

    def test_minified_bands_fade_to_the_same_mean(self):
        cc = shutil.which('g++')
        if not cc:
            self.skipTest('Host C++ compiler unavailable')
        code = host_math().replace('fwidth(float v){(void)v;return 0;}',
                                   'fwidth(float v){(void)v;return 1;}')
        build_and_run(cc, code + r'''
int main() {
 const int ids[]={1,2,8,9,12,13};
 for(int i=0;i<6;i++) {
  nxStadiumProfile=ids[i];
  for(int y=-3400;y<3400;y+=400)for(int x=-5200;x<5200;x+=400)
   assert(fabsf(nxPitchMowing(vec3(.03,.09,.01),vec3(x,y,0)).g-.09f)<.000001f);
 }
}
''')

    def test_loaded_stadiums_are_distinct_stable_bounded_and_preserve_paint(self):
        cc = shutil.which('g++')
        if not cc:
            self.skipTest('Host C++ compiler unavailable')
        build_and_run(cc, host_math() + r'''
static void same(vec3 a,vec3 b) {
 assert(fabsf(a.r-b.r)<.000001f && fabsf(a.g-b.g)<.000001f && fabsf(a.b-b.b)<.000001f);
}
int main() {
 const int ids[]={1,2,8,9,12,13};
 const vec3 dark(.0284,.0802,.008),light(.0382,.1070,.0123);
 float patterns[6][1025];
 for(int i=0;i<6;i++) {
  nxStadiumProfile=ids[i];int n=0,high=0,low=0;
  for(int y=-3000;y<=3000;y+=250)for(int x=-5000;x<=5000;x+=250) {
   vec3 pos(x,y,0);vec3 a=nxPitchMowing(dark,pos),b=nxPitchMowing(light,pos);
   assert(a.g>=.09f*.915f-.000001f && a.g<=.09f*1.085f+.000001f);
   assert(fabsf(a.g-b.g)<.000001f); // baked green bands replaced, not overlaid
   assert(fabsf(a.r/a.g-dark.r/dark.g)<.000001f); // hue survives
   high+=a.g>.095;low+=a.g<.085;
   patterns[i][n++]=a.g;
   for(int day=0;day<2;day++)for(int weather=0;weather<3;weather++) {
    nxDayStadium=day;nxStadiumClimate=vec4(weather,1,0,1);
    same(nxPitchMowing(dark,pos),a); // weather/light remains downstream
   }
   for(int p=0;p<=100;p++)same(nxPitchMowing(vec3(p*.01f),pos),vec3(p*.01f));
  }
  assert(n==1025 && high>n*.30 && low>n*.30);
  for(int j=0;j<i;j++) {
   int different=0;
   for(int k=0;k<n;k++)different+=fabsf(patterns[i][k]-patterns[j][k])>.004;
   assert(different>n*.30); // whole-field distinction, not one chosen sample
  }
  same(nxPitchMowing(dark,vec3(5401,0,0)),dark);
  same(nxPitchMowing(dark,vec3(0,3551,0)),dark);
  same(nxPitchMowing(dark,vec3(0,0,101)),dark);
 }
 for(int id=-1;id<18;id++) {
  bool supported=false;for(int i=0;i<6;i++)supported|=id==ids[i];
  if(supported)continue;
  nxStadiumProfile=id;
  same(nxPitchMowing(dark,vec3(300,400,0)),dark);
  same(nxPitchMowing(light,vec3(-500,700,0)),light);
 }
 // Return to Konami, then another imported shell: no old pattern survives.
 for(int repeat=0;repeat<100;repeat++) {
  nxStadiumProfile=1;vec3 first=nxPitchMowing(dark,vec3(300,400,0));
  nxStadiumProfile=0;same(nxPitchMowing(dark,vec3(300,400,0)),dark);
  nxStadiumProfile=1;same(nxPitchMowing(dark,vec3(300,400,0)),first);
 }
}
''')

    def test_owned_day_and_night_variants_keep_texture_operations_and_alpha(self):
        cc = shutil.which('gcc')
        if not cc:
            self.skipTest('Host C compiler unavailable')
        native = ROOT / 'local-debug/pitch-recreate/native/PesMobile/Content/Assets/bg_lighting_AM1/Materials'
        paths = [native / (n + '.uexp') for n in
                 ('M_Pitch_Default', 'M_Pitch_Default_night', 'M_Pitch_Default_night_Low')]
        if not all(p.is_file() for p in paths):
            self.skipTest('Optional legally supplied native pitch shader fixtures unavailable')
        with tempfile.TemporaryDirectory(prefix='pesnx-mowing-') as temp:
            source = Path(temp) / 'policy.c'
            exe = source.with_suffix('.exe')
            source.write_text('#include "stadium_lighting_policy.h"\n'
                'int main(void){(void)night_lighting_source;char s[262144];'
                'size_t n=fread(s,1,sizeof(s)-1,stdin);s[n]=0;'
                'char*p=stadium_lighting_source(s);if(!p)return 2;'
                'fputs(p,stdout);free(p);return 0;}')
            subprocess.run([cc, '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-I', str(ROOT / 'source'), str(source), '-o', str(exe)],
                           check=True, capture_output=True)
            counts = []
            for path in paths:
                changed = 0
                for original in shader_sources(path):
                    result = subprocess.run([str(exe)], input=original, capture_output=True)
                    self.assertIn(result.returncode, (0, 2), result.stderr)
                    if result.returncode == 2:
                        self.assertNotIn(b'View_BufferSizeAndInvSize', original)
                        continue
                    patched = result.stdout.replace(b'\r\n', b'\n')
                    original = original.replace(b'\r\n', b'\n')
                    body = patched.split(b'void main()', 1)[1]
                    before = original.split(b'void main()', 1)[1]
                    self.assertEqual(body.count(b'nxPitchMowing('), 1)
                    # Every native texture read, its UV and its LOD/bias survives.
                    texture_ops = lambda s: re.findall(rb'texture(?:Lod)?\([^;\n]*?\)', s)
                    self.assertEqual(texture_ops(body), texture_ops(before))
                    alpha = lambda s: re.findall(rb'[^\n]*(?:out_Target0\.xyzw|v\d+\.w =|discard;)[^\n]*', s)
                    self.assertEqual(alpha(body), alpha(before))
                    # Retain original detail mix and apply surface weather last.
                    self.assertIn(b'nxPitchWeather', body)
                    self.assertLess(body.index(b'nxPitchMowing'), body.index(b'nxPitchWeather'))
                    if path.stem.endswith('_Low'):
                        self.assertRegex(body, rb'v\d+\.xyzw = texture\(ps2,[^;]+;\n\tv\d+\.xyz = nxPitchMowing')
                    else:
                        self.assertIn(b'nxPitchMowing(texture(ps0,in_TEXCOORD0.xy).xyz,', body)
                    self.assertEqual(subprocess.run([str(exe)], input=patched,
                                                   capture_output=True).returncode, 2)
                    self.assertEqual(subprocess.run([str(exe)], input=original+b'//unknown',
                                                   capture_output=True).returncode, 2)
                    changed += 1
                counts.append(changed)
            self.assertEqual(counts, [20, 20, 18])

    def test_active_shell_profile_is_cached_and_no_extra_texture_or_frame_path(self):
        source = (ROOT / 'source/imports.c').read_text()
        self.assertIn('"nxStadiumProfile"', source)
        self.assertIn('const int profile = (int)pes_controller_stadium_canary_active();', source)
        self.assertIn('profile != roof_uniforms[index].profile_value', source)
        header = (ROOT / 'source/stadium_lite_glsl.h').read_text()
        helper = header.split('"highp float nxMowingBand', 1)[1].split('"highp vec3 nxPitchGrain', 1)[0]
        for forbidden in ('texture(', 'sin(', 'cos(', 'sqrt(', 'time', 'Frame'):
            self.assertNotIn(forbidden, helper)
        # One distance operation is confined to Camp Nou's uniform branch.
        self.assertEqual(helper.count('length('), 1)
        self.assertIn('else band=nxMowingBand(length(world.xy)/1700.0)', helper)
        self.assertIn('fwidth(coordinate)', helper)


if __name__ == '__main__':
    unittest.main()
