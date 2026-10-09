"""Compile the policy and check all available owned day/night shader variants."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]


def bodies(path):
    data = path.read_bytes()
    for m in re.finditer(b'\x78[\x01\x5e\x9c\xda]', data):
        try:
            raw = zlib.decompress(data[m.start():])
        except zlib.error:
            continue
        if not raw.startswith(b'LSLGSP'):
            continue
        start = raw.find(b'void main()')
        end = raw.find(b'\0', start)
        if start >= 0 and end > start:
            yield raw[start:end]


class PitchShadowTests(unittest.TestCase):
    def test_native_allowlist_and_night_exclusion(self):
        gcc = shutil.which('gcc')
        if not gcc:
            self.skipTest('gcc unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            c = Path(tmp)/'policy.c'
            c.write_text('#include "pitch_shadow_policy.h"\n#include <stdio.h>\n'
                         'int main(void) {char s[131072]; size_t n=fread(s,1,sizeof(s)-1,stdin);'
                         's[n]=0; char *p=pitch_shadow_source(s); if(!p)return 2;'
                         'char *r=pitch_roof_source(p); if(!r){free(p);return 3;}'
                         'fputs(r,stdout); free(r); free(p);return 0;}\n')
            exe = Path(tmp)/'policy.exe'
            subprocess.run([gcc, '-I', str(ROOT/'source'), str(c), '-o', str(exe)], check=True)
            def transform(body):
                result = subprocess.run([str(exe)], input=body, capture_output=True)
                if result.returncode == 2:
                    return None
                self.assertEqual(result.returncode, 0, result.stderr)
                return result.stdout.replace(b'\r\n', b'\n')
            self.assertIsNone(transform(b'void main() { }'))
            self.assertIsNone(transform(b'void main() { float x=MobileDirectionalLight_DirectionalLightDirectionAndShadowTransition.w; }'))
            native = ROOT/'local-debug/pitch-recreate/native/PesMobile/Content/Assets/bg_lighting_AM1/Materials'
            if not native.exists():
                self.skipTest('owned native shader fixtures unavailable; synthetic refusal checked')
            changed = 0
            key = b'MobileDirectionalLight_DirectionalLightDirectionAndShadowTransition.w'
            for body in bodies(native/'M_Pitch_Default.uexp'):
                result = transform(body)
                if b'texture(ps1,in_TEXCOORD0.zw)' in body:
                    old_tint = b'vec3(8.755540e-01,1.000000e+00,0.000000e+00)'
                    new_tint = b'vec3(0.000000e+00,0.000000e+00,0.000000e+00)'
                    self.assertEqual(len(old_tint), len(new_tint))
                    self.assertEqual(body.count(old_tint), 1)
                    is_v1 = key+b';' in body
                    self.assertNotIn(b'nxGrass', result)
                    self.assertEqual(result.count(b'uniform highp float nxRoofDisabled;'), 1)
                    self.assertEqual(result.count(b'(nxRoofDisabled > 0.5 ? vec4(1.0) : texture(ps1,in_TEXCOORD0.zw))'), 1)
                    restored = result.replace(b'uniform highp float nxRoofDisabled;\n', b'').replace(
                        b'(nxRoofDisabled > 0.5 ? vec4(1.0) : texture(ps1,in_TEXCOORD0.zw))',
                        b'texture(ps1,in_TEXCOORD0.zw)')
                    expected = body.replace(old_tint, new_tint)
                    if is_v1:
                        expected = expected.replace(key+b';', key+b' * 0.85;')
                    color = re.compile(rb'(v\d+)\.xyz = clamp\(\(\((v\d+)\+\(Material_VectorExpressions\[1\]\.xyz\*(v\d+)\.xxx\)\).*?;')
                    matches = list(color.finditer(expected))
                    self.assertEqual(len(matches), 1)
                    dest, base, mask = matches[0].groups()
                    albedo = (dest+b'.xyz = (clamp(('+base+b'+Material_VectorExpressions[1].xyz),vec3(0.0),'
                              b'vec3(1.0))*mix(0.65,1.0,clamp('+mask+b'.x,0.0,1.0)));')
                    expected = color.sub(lambda m: albedo, expected)
                    self.assertEqual(restored, expected)
                    # Evaluate the emitted expression against many RGB inputs.
                    # Shadow must reduce all channels equally, leave sunlight
                    # intact, and never add the old fixed green shadow colour.
                    import numpy as np
                    expression = albedo.split(b' = ', 1)[1].rstrip(b';').decode()
                    expression = expression.replace((base+b'').decode(), 'grass')
                    expression = expression.replace('Material_VectorExpressions[1].xyz', 'light')
                    expression = expression.replace((mask+b'.x').decode(), 'coverage')
                    def evaluate(grass, light, coverage):
                        return eval(expression, {'__builtins__': {}}, dict(
                            grass=np.array(grass), light=np.array(light), coverage=coverage,
                            vec3=lambda x: np.full(3, x), clamp=np.clip,
                            mix=lambda a,b,t: a*(1-t)+b*t))
                    for grass in ((.025,.075,.011),(.08,.14,.034),(.8,.8,.8),(0,0,0),(2,.3,.7)):
                        light=(.005208,.002781,0.)
                        sun=evaluate(grass,light,1.)
                        np.testing.assert_allclose(sun,np.clip(np.array(grass)+light,0,1),atol=1e-12)
                        previous=evaluate(grass,light,0.)
                        np.testing.assert_allclose(previous,sun*.65,atol=1e-12)
                        for coverage in (.1,.3,.6,1.):
                            shade=evaluate(grass,light,coverage)
                            self.assertTrue(np.all(shade>=previous) and np.all(shade<=sun))
                            np.testing.assert_allclose(np.cross(sun,shade),0.,atol=1e-12)
                            previous=shade
                    self.assertIsNone(transform(result))
                    self.assertIsNone(transform(body+b'//unknown variant'))
                    changed += 1
                else:
                    self.assertIsNone(result)
            self.assertEqual(changed, 20)
            # The old hue patch must never leak into Night, perimeter turf or
            # the pitch-side people material. Hash refusal is checked on every
            # available cooked variant, not inferred from a filename alone.
            for name in ('M_Pitch_Default_night', 'M_Pitch_Default_night_Low',
                         'M_field_ed', 'M_PitchSide'):
                for body in bodies(native/(name+'.uexp')):
                    self.assertIsNone(transform(body))
