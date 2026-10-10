"""Scoped light/roof rewrites preserve character albedo and texture sampling."""
import ast
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from test_night_lighting_policy import shader_sources
from test_result_flow import build_and_run

ROOT = Path(__file__).resolve().parents[1]


class StadiumLightingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cc = shutil.which('gcc')
        if not cls.cc:
            raise unittest.SkipTest('Host C compiler unavailable')
        cls.temp = tempfile.TemporaryDirectory(prefix='pesnx-stadium-light-')
        cls.addClassCleanup(cls.temp.cleanup)
        c = Path(cls.temp.name)/'policy.c'
        cls.exe = c.with_suffix('.exe')
        c.write_text('#include "stadium_lighting_policy.h"\n'
            'int main(void){(void)night_lighting_source;char s[262144];size_t n=fread(s,1,sizeof(s)-1,stdin);'
            's[n]=0;char*p=stadium_lighting_source(s);if(!p)return 2;'
            'fputs(p,stdout);free(p);return 0;}')
        subprocess.run([cls.cc, '-std=c11', '-Wall', '-Wextra', '-Werror',
            '-I', str(ROOT/'source'), str(c), '-o', str(cls.exe)],
            check=True, capture_output=True)

    def transform(self, source):
        r = subprocess.run([str(self.exe)], input=source, capture_output=True)
        self.assertIn(r.returncode, (0, 2), r.stderr)
        return r.stdout.replace(b'\r\n', b'\n') if r.returncode == 0 else None

    def test_unknown_sources_are_refused(self):
        for source in (b'', b'void main(){}',
                       b'void main(){v0.xyz=View_SkyLightColor.xyz;}'):
            self.assertIsNone(self.transform(source))

    def test_owned_variants_change_only_decoded_light(self):
        stadium = ROOT/'local-debug/pitch-recreate/native/PesMobile/Content/Assets/bg_lighting_AM1/Materials'
        players = ROOT/'local-debug/night-lighting-audit/PesMobile/Content/Assets/character'
        extra = ROOT/'local-debug/stadium-review-v2/audit'
        paths = [stadium/(n+'.uexp') for n in ('M_field_ed', 'M_PitchSide')]
        paths += list(players.rglob('*.uexp'))
        paths += [extra/(n+'.uexp') for n in ('M_SpikeBase', 'M_test_hair_parts', 'M_test_spike_c_L')]
        runtime = ROOT/'local-debug/stadium-lite-v5/audit'
        paths += [runtime/(n+'.uexp') for n in ('body_base','body_base_low',
                     'face_tablet_phone','hair_parts_tablet_ss')]
        if len(paths) != 13 or not all(p.is_file() for p in paths):
            self.skipTest('Owned player/perimeter shader fixtures unavailable')
        changed = depth_only = 0
        for path in paths:
            for source in shader_sources(path):
                source = source.replace(b'\r\n', b'\n')
                result = self.transform(source)
                body = source.split(b'void main()', 1)[1]
                if (b'discard;' in body and (b'out_Target0.xyzw = vec4(0.000000e+00,' in body
                        or b'out_Target0.xyzw = pu_h[0].xxxx;' in body)
                        and b'MobileDirectionalLight' not in body):
                    self.assertIsNone(result)
                    depth_only += 1
                    continue
                with self.subTest(material=path.stem, variant=changed):
                    self.assertIsNotNone(result)
                    changed += 1
                    self.assertIsNone(self.transform(result))
                    self.assertIsNone(self.transform(source+b'//unknown'))
                    prefix, body = result.split(b'void main()', 1)
                    native_prefix, native_body = source.split(b'void main()', 1)
                    self.assertTrue(prefix.startswith(native_prefix))
                    self.assertIn(b'nxDayStadium', result)
                    self.assertNotIn(b'nxNightFloor', result)
                    # Undo ONLY the allowed light terms and injected assignment.
                    # Any albedo, depth, geometry, alpha or output change fails.
                    body, inserts = re.subn(
                        rb'\n\t(v\d+)\.xyz = nx(?:NeutralLight\(\1\.xyz|AmbientLight\(\1\.xyz,nxRoofLight)\);', b'', body)
                    self.assertGreater(inserts, 0)
                    for color,helper in ((b'MobileDirectionalLight_DirectionalLightColor.xyz',b'nxDirectLight'),
                                  (b'View_SkyLightColor.xyz',b'nxNeutralLight'),
                                  (b'View_IndirectLightingColorScale',b'nxAmbientLight')):
                        args=b'' if helper==b'nxNeutralLight' else b',nxRoofLight'
                        body = body.replace(helper+b'('+color+args+b')', color)
                    body=body.replace(b'\n\thighp float nxRoofLight=1.0;\n'
                        b'\tif(nxDayStadium>0.5) nxRoofLight=nxRoofVisibility(in_TEXCOORD8.xyz-View_PreViewTranslation);\n',b'')
                    for coord in (b'v2',b'v3'):
                        body=body.replace(b'if (nxDayStadium<0.5 && ('+coord+b'.z>0.000000e+00))',
                                          b'if (('+coord+b'.z>0.000000e+00))')
                    body=re.sub(rb'\n\thighp vec3 nxWeatherWorld=[^\n]+;\n(?:\tout_Target0.xyz=[^\n]+;\n)+',b'',body)
                    self.assertEqual(body, native_body)
                    # All texture reads, including encoded RGBM, remain original.
                    reads = lambda s: re.findall(rb'[^\n]*= (?:texture|clamp\(texture)[^\n]*', s)
                    self.assertEqual(reads(result), reads(source))
        self.assertEqual(changed, 628)
        self.assertEqual(depth_only, 18)

    def test_actual_helper_preserves_disabled_mode_and_neutral_light_luminance(self):
        cpp = shutil.which('g++')
        if not cpp:
            self.skipTest('Host C++ compiler unavailable')
        import sys
        sys.path.insert(0,str(ROOT/'tools'))
        from stadium_lite_preview import host_math
        build_and_run(cpp, host_math()+r'''
int main(){
  for(int enabled=0;enabled<2;enabled++) {
    nxNightIndirect=enabled;
    for(int r=0;r<18;r++)for(int g=0;g<18;g++)for(int b=0;b<18;b++) {
      vec3 v(r/4.f,g/4.f,b/4.f), out=nxNeutralLight(v);
      if(!enabled) {
        assert(out.r==v.r && out.g==v.g && out.b==v.b);
      } else {
        float y=dot(v,vec3(.2126f,.7152f,.0722f));
        assert(out.r==out.g && out.g==out.b && fabs(out.r-y)<.000001f);
      }
    }
  }
}
''')


if __name__ == '__main__':
    unittest.main()
