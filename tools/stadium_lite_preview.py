"""Inspect the authored roof geometry using the exact emitted shader math.

This is a mathematical preview, not a game render or performance measurement.
No game assets are read. Requires a host C++ compiler, numpy and matplotlib.
"""
import argparse
import ast
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def shader_math():
    text = (ROOT/'source/stadium_lite_glsl.h').read_text()
    strings = re.findall(r'"(?:\\.|[^"\\])*"', text)
    return ''.join(ast.literal_eval(s) for s in strings)


def host_math():
    """Small vector adapter; the geometry/lighting functions are not duplicated."""
    return r'''
#include <cmath>
#include <cstdio>
#include <cassert>
using std::abs;
static float min(float a,float b){return a<b?a:b;}
static float max(float a,float b){return a>b?a:b;}
static float clamp(float v,float lo,float hi){return min(hi,max(lo,v));}
static float mix(float a,float b,float t){return a+(b-a)*t;}
static float fract(float x){return x-floorf(x);}
static float smoothstep(float a,float b,float v){float t=clamp((v-a)/(b-a),0,1);return t*t*(3-2*t);}
static float fwidth(float v){(void)v;return 0;}
struct vec2 {
 float x,y; vec2(float v):x(v),y(v){} vec2(float a,float b):x(a),y(b){}
 vec2 operator+(vec2 b)const{return vec2(x+b.x,y+b.y);}
 vec2 operator-(vec2 b)const{return vec2(x-b.x,y-b.y);}
 vec2 operator*(vec2 b)const{return vec2(x*b.x,y*b.y);}
 vec2 operator*(float s)const{return vec2(x*s,y*s);}
};
static vec2 fract(vec2 v){return vec2(fract(v.x),fract(v.y));}
static vec2 floor(vec2 v){return vec2(floorf(v.x),floorf(v.y));}
static float dot(vec2 a,vec2 b){return a.x*b.x+a.y*b.y;}
static vec2 abs(vec2 v){return vec2(fabsf(v.x),fabsf(v.y));}
static vec2 max(vec2 a,vec2 b){return vec2(max(a.x,b.x),max(a.y,b.y));}
static float length(vec2 v){return sqrtf(v.x*v.x+v.y*v.y);}
struct vec3 {
 union {struct {float x,y,z;};struct {float r,g,b;};}; vec2 xy;
 vec3(float v):x(v),y(v),z(v),xy(v){}
 vec3(float a,float b,float c):x(a),y(b),z(c),xy(a,b){}
 vec3 operator+(vec3 b)const{return vec3(x+b.x,y+b.y,z+b.z);}
 vec3 operator*(float s)const{return vec3(x*s,y*s,z*s);}
 vec3 operator*(vec3 b)const{return vec3(x*b.x,y*b.y,z*b.z);}
};
static vec3 mix(vec3 a,vec3 b,float t){return vec3(mix(a.x,b.x,t),mix(a.y,b.y,t),mix(a.z,b.z,t));}
static vec3 max(vec3 a,vec3 b){return vec3(max(a.x,b.x),max(a.y,b.y),max(a.z,b.z));}
static float dot(vec3 a,vec3 b){return a.x*b.x+a.y*b.y+a.z*b.z;}
struct vec4 {
 float x,y,z,w;
 vec4(float a=0,float b=0,float c=0,float d=0):x(a),y(b),z(c),w(d){}
};
static vec3 nxSun(.4013,.4488,.798);
static struct {vec3 xyz;} MobileDirectionalLight_DirectionalLightDirectionAndShadowTransition={nxSun};
''' + shader_math().replace('highp ', '').replace('uniform ', '')


def preview(output):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    compiler = shutil.which('g++')
    if not compiler:
        raise RuntimeError('Host g++ compiler unavailable')
    with tempfile.TemporaryDirectory(prefix='pesnx-roof-preview-') as directory:
        source = Path(directory)/'roof.cpp'
        binary = source.with_suffix('.exe')
        source.write_text(host_math()+r'''
int main(){
 for(int y=0;y<361;y++)for(int x=0;x<521;x++) {
  float wx=-6500+x*25,wy=-4500+y*25;
  printf("%.6f %.6f %.6f\n",nxRoofProxy(vec2(wx,wy),8),
    nxRoofVisibility(vec3(wx,wy,0)),nxRoofVisibility(vec3(wx,wy,170)));
 }
}
''')
        subprocess.run([compiler,'-std=c++17','-O2',str(source),'-o',str(binary)],check=True,capture_output=True)
        values = subprocess.check_output([str(binary)])
        from io import BytesIO
        arrays = np.loadtxt(BytesIO(values)).reshape(361,521,3)
    fig, axes = plt.subplots(1,3,figsize=(15,5),layout='constrained')
    titles = ['Bukaan atap: tampak atas', 'Penerima di tanah (0 m)', 'Penerima di kepala (1,7 m)']
    for i,ax in enumerate(axes):
        ax.imshow(arrays[:,:,i],origin='lower',extent=(-65,65,-45,45),vmin=0,vmax=1,cmap='Greens_r')
        ax.plot([-52.5,52.5,52.5,-52.5,-52.5],[-34,-34,34,34,-34],color='white',lw=1)
        ax.plot([0,0],[-34,34],color='white',lw=1)
        ax.set(title=titles[i],xlabel='Panjang lapangan (m)',ylabel='Lebar lapangan (m)')
    fig.suptitle('Stadium Lite — proyeksi geometri matematis, bukan screenshot game',fontsize=14)
    output.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(output,dpi=140)
    plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    preview(parser.parse_args().output)
