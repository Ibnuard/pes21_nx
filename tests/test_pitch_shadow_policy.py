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
    def test_day_edits_are_scoped_and_night_pitch_reaches_gl_byte_exact(self):
        # Exercise the production hook, not just a duplicate/no-op policy.
        from test_result_flow import function
        from test_night_lighting_policy import shader_sources
        gcc=shutil.which('gcc')
        if not gcc:self.skipTest('Host compiler unavailable')
        native=ROOT/'local-debug/pitch-recreate/native/PesMobile/Content/Assets/bg_lighting_AM1/Materials'
        paths=[native/(n+'.uexp') for n in ('M_Pitch_Default','M_Pitch_Default_night','M_Pitch_Default_night_Low')]
        if not all(p.exists() for p in paths):self.skipTest('Owned native pitch material fixtures unavailable')
        hook=function((ROOT/'source/imports.c').read_text(),'glShaderSource_pitch')
        with tempfile.TemporaryDirectory(prefix='pesnx-native-pitch-') as temp:
            c=Path(temp)/'check.c';exe=Path(temp)/'check.exe'
            c.write_text('#include "stadium_lighting_policy.h"\n'
                'typedef unsigned GLuint;typedef int GLsizei;typedef int GLint;typedef char GLchar;\n'
                '#define debugPrintf(...) ((void)0)\n'
                'static void glShaderSource(GLuint s,GLsizei n,const GLchar*const*t,const GLint*l) {'
                '(void)s;for(int i=0;i<n;i++)fwrite(t[i],1,l&&l[i]>=0?(size_t)l[i]:strlen(t[i]),stdout); }\n'
                +hook+'\nint main(int argc,char**argv){(void)argv;char s[262144];'
                'size_t n=fread(s,1,sizeof(s)-1,stdin);s[n]=0;const char*p[2]={s,s+n/2};'
                'int l[2]={(int)(n/2),(int)(n-n/2)};'
                'if(argc>1)glShaderSource_pitch(1,2,p,l);'
                'else {l[0]=(int)n;glShaderSource_pitch(1,1,p,l);}return 0;}')
            subprocess.run([gcc,'-std=c11','-Wall','-Wextra','-Werror','-I',str(ROOT/'source'),str(c),'-o',str(exe)],check=True,capture_output=True)
            total=0
            for path in paths:
                for source in shader_sources(path):
                    total+=1
                    for args in ([],['segmented']):
                        result=subprocess.run([str(exe),*args],input=source,capture_output=True,check=True)
                        result=result.stdout.replace(b'\r\n',b'\n')
                        original=source.replace(b'\r\n',b'\n')
                        if args or path.stem!='M_Pitch_Default':
                            self.assertEqual(result,original)
                            continue
                        prefix,body=result.split(b'void main()',1)
                        native_prefix,native_body=original.split(b'void main()',1)
                        self.assertTrue(prefix.startswith(native_prefix))
                        self.assertIn(b'nxPitchGrain',body)
                        self.assertIn(b'nxPitchSheen',body)
                        self.assertIn(b'nxRoofVisibility(in_TEXCOORD8.xyz-View_PreViewTranslation)',body)
                        body=body.replace(b'\n\thighp float nxRoofLight=1.0;\n'
                            b'\tif(nxDayStadium>0.5) nxRoofLight=nxRoofVisibility(in_TEXCOORD8.xyz-View_PreViewTranslation);\n',b'')
                        body=re.sub(rb'\n\t(v\d+)\.xyz = nx(?:NeutralLight\(\1\.xyz|AmbientLight\(\1\.xyz,nxRoofLight|PitchSheen\(\1\.xyz,nxRoofLight|PitchGrain\(\1\.xyz,v\d+\.w)\);',b'',body)
                        body=re.sub(rb'\n\tif\(nxDayStadium>0.5\) v\d+\.xyzw=vec4\(1.0\);',b'',body)
                        body=re.sub(rb'\n\tif\(nxDayStadium>0.5\) v\d+\.xyz=clamp\(v\d+,vec3\(0.0\),vec3\(1.0\)\);',b'',body)
                        for color,helper in ((b'MobileDirectionalLight_DirectionalLightColor.xyz',b'nxDirectLight'),
                                  (b'View_SkyLightColor.xyz',b'nxNeutralLight'),
                                  (b'View_IndirectLightingColorScale',b'nxAmbientLight')):
                            body=body.replace(helper+b'('+color+(b'' if helper==b'nxNeutralLight' else b',nxRoofLight')+b')',color)
                        body=body.replace(b'if (nxDayStadium<0.5 && (v2.z>0.000000e+00))',b'if ((v2.z>0.000000e+00))')
                        self.assertEqual(body,native_body)
            self.assertGreaterEqual(total,20)


if __name__=='__main__':unittest.main()
