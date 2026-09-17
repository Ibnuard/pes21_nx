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
    def test_grade_luminance_and_neutral_mask(self):
        weights = (0.2126, 0.7152, 0.0722)
        def grade(rgb):
            r, g, b = rgb
            t = min(1, max(0, ((g-max(r,b))/max(g,0.0001)-0.05)/0.13))
            mask = t*t*(3-2*t)
            tinted = [x*s for x,s in zip(rgb, (0.82,1,1.12))]
            luminance = sum(x*w for x,w in zip(rgb, weights))
            scale = luminance/max(sum(x*w for x,w in zip(tinted, weights)),0.0001)
            return tuple(x*(1-mask)+y*scale*mask for x,y in zip(rgb,tinted))
        for rgb in ((0.30,0.42,0.08), (0.06,0.09,0.02), (0.8,0.8,0.8), (0,0,0)):
            out = grade(rgb)
            self.assertAlmostEqual(sum(x*w for x,w in zip(rgb,weights)), sum(x*w for x,w in zip(out,weights)))
        self.assertEqual(grade((0.8,0.8,0.8)), (0.8,0.8,0.8))
        self.assertLess(grade((0.30,0.42,0.08))[0]/grade((0.30,0.42,0.08))[1], 0.30/0.42)

    def test_native_allowlist_and_night_exclusion(self):
        gcc = shutil.which('gcc')
        if not gcc:
            self.skipTest('gcc unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            c = Path(tmp)/'policy.c'
            c.write_text('#include "pitch_shadow_policy.h"\n#include <stdio.h>\n'
                         'int main(void) {char s[131072]; size_t n=fread(s,1,sizeof(s)-1,stdin);'
                         's[n]=0; char *p=pitch_shadow_source(s); if(!p)return 2;'
                         'fputs(p,stdout); free(p);return 0;}\n')
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
                if key+b';' in body:
                    old_tint = b'vec3(8.755540e-01,1.000000e+00,0.000000e+00)'
                    new_tint = b'vec3(6.000000e-01,1.000000e+00,2.900000e-01)'
                    self.assertEqual(len(old_tint), len(new_tint))
                    self.assertEqual(body.count(old_tint), 1)
                    self.assertEqual(result.count(b'// NX pitch hue begin'), 1)
                    self.assertIn(b'out_Target0.xyz = mix(v1.xyz,nxTint,nxMask);', result)
                    ungraded = re.sub(rb'\n// NX pitch hue begin\n.*?// NX pitch hue end\n', b'', result, flags=re.S)
                    self.assertEqual(ungraded, body.replace(key+b';', key+b' * 0.85;').replace(old_tint, new_tint))
                    self.assertIsNone(transform(result))
                    self.assertIsNone(transform(body+b'//unknown variant'))
                    changed += 1
                else:
                    self.assertIsNone(result)
            self.assertGreater(changed, 0)
            for name in ('M_Pitch_Default_night', 'M_Pitch_Default_night_Low'):
                for body in bodies(native/(name+'.uexp')):
                    self.assertIsNone(transform(body))
