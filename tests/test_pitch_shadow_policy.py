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
                    self.assertEqual(result, body.replace(key+b';', key+b' * 0.85;'))
                    self.assertIsNone(transform(body+b'//unknown variant'))
                    changed += 1
                else:
                    self.assertIsNone(result)
            self.assertGreater(changed, 0)
            for name in ('M_Pitch_Default_night', 'M_Pitch_Default_night_Low'):
                for body in bodies(native/(name+'.uexp')):
                    self.assertIsNone(transform(body))
