"""Scoped Night/High decoded-light compensation; owned shader fixtures optional."""
from pathlib import Path
import ast
import os
import re
import shutil
import subprocess
import tempfile
import unittest
import zlib

from test_result_flow import build_and_run, function

ROOT = Path(__file__).resolve().parents[1]


def shader_sources(path):
    data = path.read_bytes()
    for match in re.finditer(b'\x78[\x01\x5e\x9c\xda]', data):
        try:
            raw = zlib.decompress(data[match.start():])
        except zlib.error:
            continue
        if not raw.startswith(b'LSLGSP'):
            continue
        start = raw.find(b'#version')
        end = raw.find(b'\0', start)
        if start >= 0 and end > start and b'out_Target0' in raw[start:end]:
            yield raw[start:end]


class NightLightingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compiler = shutil.which('gcc') or shutil.which('clang')
        if not cls.compiler:
            raise unittest.SkipTest('Host C compiler unavailable')
        cls.temp = tempfile.TemporaryDirectory(prefix='pesnx-night-lighting-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.exe = Path(cls.temp.name)/'policy.exe'
        path = Path(cls.temp.name)/'policy.c'
        path.write_text('#include "night_lighting_policy.h"\n'
                        'int main(void) {char s[262144];size_t n=fread(s,1,sizeof(s)-1,stdin);'
                        's[n]=0;char *p=night_lighting_source(s);if(!p)return 2;'
                        'fputs(p,stdout);free(p);return 0;}\n')
        subprocess.run([cls.compiler,'-std=c11','-Wall','-Wextra','-Werror','-I',
                        str(ROOT/'source'),str(path),'-o',str(cls.exe)],check=True,
                       capture_output=True)

    def transform(self, source):
        result = subprocess.run([str(self.exe)], input=source, capture_output=True, timeout=5)
        if result.returncode == 2:
            return None
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.replace(b'\r\n', b'\n')

    def test_unknown_and_similarly_named_shaders_are_unchanged(self):
        for source in (b'', b'void main() { }',
                       b'void main() { vec3 v0=texture(ps1,uv).rgb; }',
                       b'void main() { v0.z = dot(View_SkyIrradianceEnvironmentMap[2],v1); }'):
            self.assertIsNone(self.transform(source))

    def test_quality_and_time_gate(self):
        source = (ROOT/'source/ue4_hooks.c').read_text()
        build_and_run(self.compiler, '#include <stdint.h>\n#include <assert.h>\n'
                      'static uint32_t main_menu_video_graphics,exhibition_settings_time_zone;\n' +
                      function(source,'pes_controller_stadium_is_day') +
                      function(source,'pes_controller_night_lighting_balance_enabled') + r'''
int main(void) {
  for(unsigned q=0;q<4;q++)for(unsigned night=0;night<2;night++) {
    main_menu_video_graphics=q;exhibition_settings_time_zone=night;
    assert(pes_controller_night_lighting_balance_enabled()==(q==2 && night==1));
  }
}
''')

    def test_helper_bounds_and_disabled_identity(self):
        header=(ROOT/'source/night_lighting_policy.h').read_text()
        strings=header.split('static const char helper[]=',1)[1].split('const size_t n=',1)[0]
        helper=''.join(ast.literal_eval(s) for s in re.findall(r'"(?:\\.|[^"\\])*"',strings))
        helper=helper.replace('uniform ','').replace('highp ','')
        # This helper uses only scalar operations shared by GLSL and C. Run
        # the actual generated helper, not a duplicate correction formula.
        build_and_run(self.compiler, r'''
#include <assert.h>
typedef struct { float r,g,b; } vec3;
#define min(a,b) ((a)<(b)?(a):(b))
#define max(a,b) ((a)>(b)?(a):(b))
''' + helper + r'''
int main(void) {
  for(int enabled=0;enabled<2;++enabled) {
    nxNightIndirect=(float)enabled;
    for(int r=-2;r<22;++r)for(int g=-2;g<22;++g)for(int b=-2;b<22;++b) {
      vec3 light={r/4.0f,g/4.0f,b/4.0f},result=nxNightLight(light);
      assert(result.r==light.r && result.b==light.b);
      assert(result.g<=light.g);
      if(!enabled)assert(result.g==light.g);
      else {
        float limit=(float)(max(0.0,max(light.r,light.b))*1.05);
        assert(result.g<=limit+0.00001f);
        if(light.g<=limit)assert(result.g==light.g);
      }
    }
    vec3 neutral={4.0f,4.0f,4.0f};
    assert(nxNightLight(neutral).g==4.0f);
  }
}
''')

    def test_owned_shader_sites_and_byte_preservation(self):
        stadium=ROOT/'local-debug/pitch-recreate/native/PesMobile/Content/Assets/bg_lighting_AM1/Materials'
        players=ROOT/'local-debug/night-lighting-audit/PesMobile/Content/Assets/character'
        paths=[stadium/(name+'.uexp') for name in ('M_field_ed','M_PitchSide')]
        paths+=list(players.rglob('*.uexp'))
        if not all(p.is_file() for p in paths[:2]) or len(paths)!=6:
            self.skipTest('optional owned perimeter/player material fixtures unavailable')
        altered=reflection_only=lightmapped=0
        validator=os.environ.get('PESNX_GLSLANG')
        for path in paths:
            for source in shader_sources(path):
                source=source.replace(b'\r\n',b'\n')
                body=source[source.index(b'void main()'):]
                eligible=b'texture(' in body and b'samplerCube ' in source
                result=self.transform(source)
                with self.subTest(material=path.stem, variant=altered):
                    if not eligible:
                        self.assertIsNone(result)
                        continue
                    self.assertIsNotNone(result)
                    altered+=1
                    if (b'IndirectLightingSHCoefficients2.z;' not in body and
                            b'View_SkyIrradianceEnvironmentMap[2]' not in body):
                        reflection_only+=1
                    if b'PrecomputedLightingBuffer_LightMapAdd[1]' in body:
                        lightmapped+=1
                    self.assertIsNone(self.transform(result))
                    self.assertIsNone(self.transform(source+b'//unrecognized'))
                    prefix,patched_body=result.split(b'void main()',1)
                    before_prefix=source.split(b'void main()',1)[0]
                    self.assertTrue(prefix.startswith(before_prefix))
                    self.assertIn(b'if (nxNightIndirect > 0.5)',prefix)
                    self.assertIn(b'light.g = min(light.g, max(0.0, max(light.r, light.b)) * 1.05);',prefix)
                    insertions=list(re.finditer(rb'\n\t(v\d+)\.xyz = nxNightLight\(\1\.xyz\);',patched_body))
                    self.assertGreaterEqual(len(insertions),1)
                    self.assertLessEqual(len(insertions),3)
                    for edit in insertions:
                        preceding=patched_body[:edit.start()].split(b'\n')[-1]
                        # Every insertion follows reconstructed irradiance or
                        # decoded radiance, never diffuse, final RGB or alpha.
                        self.assertTrue(any(token in preceding for token in (
                            b'= max(vec3(0.000000e+00,0.000000e+00,0.000000e+00),',
                            b'.z = dot(View_SkyIrradianceEnvironmentMap[2],',
                            b'*vec3((', b'}')),preceding)
                    cube=re.search(rb'samplerCube (ps\d+);',source).group(1)
                    fetched=re.search(rb'(v\d+)\.xyzw = textureLod\('+cube+rb',',body).group(1)
                    # Encoded RGBM/alpha is never modified; a single correction
                    # follows the shared destination's sky and RGBM branches.
                    self.assertNotIn(b'\n\t'+fetched+b'.xyz = nxNightLight(',result)
                    decoded=[e for e in insertions if patched_body[:e.start()].rstrip().endswith(b'}')]
                    self.assertEqual(len(decoded),1)
                    target=decoded[0].group(1)
                    branch_start=patched_body.rfind(b'if (bool(',0,decoded[0].start())
                    branch=patched_body[branch_start:decoded[0].start()]
                    self.assertEqual(branch.count(target+b'.xyz = '),2)
                    self.assertIn(b'View_SkyLightColor.xyz',branch)
                    if b'PrecomputedLightingBuffer_LightMapAdd[1]' in body:
                        baked=[e for e in insertions if b'*vec3((' in patched_body[:e.start()].split(b'\n')[-1]]
                        self.assertEqual(len(baked),1)
                        self.assertGreater(baked[0].start(),patched_body.index(b'PrecomputedLightingBuffer_LightMapAdd[1]'))
                        self.assertLess(baked[0].end(),patched_body.index(b'View_IndirectLightingColorScale'))
                    restored=re.sub(rb'\n\t(v\d+)\.xyz = nxNightLight\(\1\.xyz\);',b'',patched_body)
                    self.assertEqual(before_prefix+b'void main()'+restored,source)
                    if validator:
                        frag=Path(self.temp.name)/'variant.frag'
                        # Cooked sources omit two macros supplied by the RHI.
                        # Compile both clip-space branches, before and after
                        # rewriting, instead of depending on undefined macros.
                        for candidate in (source,result):
                            version,remaining=candidate.split(b'\n',1)
                            for clip_space in (b'0',b'1'):
                                prologue=(b'\n#define HLSLCC_DX11ClipSpace '+clip_space+
                                          b'\n#define INTERFACE_LOCATION(x) layout(location=x)\n')
                                frag.write_bytes(version+prologue+remaining)
                                run=subprocess.run([validator,str(frag)],capture_output=True,timeout=15)
                                self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        self.assertEqual(altered,250)
        self.assertEqual(reflection_only,57)
        self.assertEqual(lightmapped,12)

    def test_day_pitch_and_night_pitch_are_unchanged(self):
        root=ROOT/'local-debug/pitch-recreate/native/PesMobile/Content/Assets/bg_lighting_AM1/Materials'
        if not root.exists():
            self.skipTest('optional owned pitch fixtures unavailable')
        for name in ('M_Pitch_Default','M_Pitch_Default_night','M_Pitch_Default_night_Low'):
            for source in shader_sources(root/(name+'.uexp')):
                self.assertIsNone(self.transform(source))

    def test_both_shader_routes_use_the_guarded_hook(self):
        imports=(ROOT/'source/imports.c').read_text()
        self.assertIn('night_lighting_source(copy)',function(imports,'glShaderSource_pitch'))
        self.assertIn('night_lighting ? NULL : pitch_roof_source(patched)',imports)
        self.assertIn('{ "glShaderSource", (uintptr_t)&glShaderSource_pitch }',imports)
        self.assertIn('&glShaderSource_pitch',function(imports,'eglGetProcAddress_diag'))


if __name__=='__main__':
    unittest.main()
