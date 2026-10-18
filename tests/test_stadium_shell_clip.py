"""Camera/alpha rejection precedes authored RGB fetch without losing gradients."""
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[1]
SOURCE='''#version 310 es
uniform highp vec3 View_WorldCameraOrigin;
uniform sampler2D ps0;
in highp vec4 in_COLOR0;
in highp vec4 in_TEXCOORD0;
out vec4 out_Target0;
void main()
{
 vec3 v1;
 vec2 uv=in_TEXCOORD0.xy;
 v1.xyz = (textureGrad(ps0,uv,dFdx(uv),(-dFdy(uv))).xyz*in_COLOR0.xxx);
 vec3 lo=vec3(-5.800000e+03,-4.000000e+03,-5.000000e+01);
 vec3 hi=vec3(5.800000e+03,4.000000e+03,2.600000e+02);
 if (View_WorldCameraOrigin.z<lo.z || uv.x>hi.x) discard;
 out_Target0=vec4(v1,1.0);
}
'''


@pytest.fixture(scope='module')
def transform(tmp_path_factory):
    gcc=shutil.which('gcc')
    if not gcc: pytest.skip('Host C compiler unavailable')
    folder=tmp_path_factory.mktemp('shell-clip');driver=folder/'driver.c';exe=folder/'driver.exe'
    driver.write_text('''#include "stadium_shell_clip.h"
int main(int argc,char**argv){(void)argv;char s[262144];size_t n=fread(s,1,sizeof(s)-1,stdin);s[n]=0;
char*p=argc>1?stadium_shell_clip_transform(s):stadium_shell_clip_source(s);
if(!p) {return 2;}
fputs(p,stdout);free(p);return 0;}
''')
    subprocess.run([gcc,'-std=c11','-Wall','-Wextra','-Werror','-I',str(ROOT/'source'),str(driver),'-o',str(exe)],check=True)
    def apply(source,known=False):
        args=[str(exe)]+([] if known else ['unchecked-test-fixture'])
        result=subprocess.run(args,input=source.encode(),capture_output=True)
        assert result.returncode in (0,2),result.stderr
        return result.stdout.decode() if result.returncode==0 else None
    return apply


def test_rgb_is_deferred_but_derivatives_and_colour_factor_are_preserved(transform):
    changed=transform(SOURCE)
    discard=changed.index('discard;');fetch=changed.index('textureGrad(')
    assert changed.index('nxShellColorDx=dFdx(uv)')<discard<fetch
    assert changed.index('nxShellColorDy=(-dFdy(uv))')<discard
    assert 'textureGrad(ps0,uv,nxShellColorDx,nxShellColorDy).xyz*in_COLOR0.xxx' in changed
    assert 'if (View_WorldCameraOrigin.z<lo.z || uv.x>hi.x) discard;' in changed
    assert 'out_Target0=vec4(v1,1.0);' in changed


def test_implicit_crowd_filtering_uses_gradients_from_before_discard(transform):
    changed=transform(SOURCE.replace('textureGrad(ps0,uv,dFdx(uv),(-dFdy(uv)))','texture(ps0,uv)'))
    assert 'nxShellColorDx=dFdx(uv)' in changed and 'nxShellColorDy=dFdy(uv)' in changed
    assert changed.index('discard;')<changed.index('textureGrad(')


def test_unknown_native_or_similar_body_is_not_authorized(transform):
    assert transform(SOURCE,known=True) is None
    assert transform(SOURCE.replace('View_WorldCameraOrigin','otherCamera')) is None
    assert transform(SOURCE.replace('-5.800000e+03','-5.700000e+03')) is None


def test_legacy_es2_and_repeat_application_are_unchanged(transform):
    assert transform(SOURCE.replace('#version 310 es','#version 100')) is None
    assert transform(transform(SOURCE)) is None


def test_colour_dependency_in_coverage_refuses_reordering(transform):
    source=SOURCE.replace(' vec3 lo=',' float usesColour=v1.x;\n vec3 lo=')
    assert transform(source) is None


def test_header_and_unknown_source_prefix_survive_transform(transform):
    source=SOURCE.replace('uniform sampler2D','// keep exact compile header\nuniform sampler2D')
    assert transform(source).startswith(source[:source.index('void main()')])
