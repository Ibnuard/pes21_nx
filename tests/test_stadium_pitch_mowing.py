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
    def test_owned_old_trafford_edges_are_inside_retained_white_paint(self):
        import json
        path=ROOT/'local-debug/day-roof-grass-v1/pitch-mesh/Assets/bg_lighting_AM1/Meshes/st029_pitch_2.gltf'
        textures=ROOT/'local-debug/pitch-recreate/verify-final/PesMobile/Content/Assets/bg_lighting_AM1/Textures'
        if not path.is_file() or not all((textures/('pitch_'+side+'_bsm_alp.uexp')).is_file() for side in ('l','r')):
            self.skipTest('Optional retained native pitch mesh/paint fixtures unavailable')
        import numpy as np
        from audit_stadium_optimization import accessor
        from cooked_texture import Texture
        document=json.loads(path.read_text())
        blob=(path.parent/document['buffers'][0]['uri']).read_bytes()
        # These slots are independently established by the native StaticMaterials
        # audit; no proprietary mesh/paint is copied into the repository.
        for slot,side,sign,ranges in ((3,'l',-1,((240,270),(320,345),(485,505))),
                                    (4,'r', 1,((755,785),(680,710),(520,545)))):
            primitive=next(p for p in document['meshes'][0]['primitives'] if p['material']==slot)
            positions=accessor(document,blob,primitive['attributes']['POSITION'])
            uv=accessor(document,blob,primitive['attributes']['TEXCOORD_0'])
            triangles=accessor(document,blob,primitive['indices']).reshape(-1,3)
            pixels=np.asarray(Texture(textures/('pitch_'+side+'_bsm_alp.uexp')).decode())[...,:3]
            height,width=pixels.shape[:2]
            paint=(pixels.min(2)>=78)&(pixels.max(2)-pixels.min(2)<=48)

            def world_x(u,v):
                for triangle in triangles:
                    matrix=np.vstack((uv[triangle].T,np.ones(3)))
                    if abs(np.linalg.det(matrix))<1e-10:continue
                    bary=np.linalg.solve(matrix,[u,v,1])
                    if min(bary)>-.000001:return float(bary@positions[triangle,0])
                self.fail('Paint sample is not covered by the retained native mesh')

            samples=((.08,.5,.92),(.4,.5,.6),(.26,.5,.74))
            for (lo,hi),anchor,vs in zip(ranges,(52.552,47.257,36.22),samples):
                strength=paint[int(height*.44):int(height*.56),lo:hi].mean(0)
                columns=np.flatnonzero(strength>.8)+lo
                self.assertGreaterEqual(len(columns),2)
                for v in vs:
                    bounds=sorted((world_x(columns[0]/width,v),world_x((columns[-1]+1)/width,v)))
                    self.assertLess(bounds[0],sign*anchor)
                    self.assertGreater(bounds[1],sign*anchor)

    def test_old_trafford_goal_area_edges_have_no_thin_end_strip(self):
        cc = shutil.which('g++')
        if not cc:
            self.skipTest('Host C++ compiler unavailable')
        build_and_run(cc, host_math() + r'''
int main() {
 nxStadiumProfile=12;
 const vec3 grass(.033,.09,.009);
 // Native mesh + retained paint UV mapping, not hypothetical regulation boxes.
 // Seven central strips meet two box strips and one complete goal-side strip.
 const float edges[]={0,3622.f/7,3622.f*2/7,3622.f*3/7,3622.f*4/7,
  3622.f*5/7,3622.f*6/7,3622,4173.85f,4725.7f,5255.2f};
 float narrowest=10000,widest=0;
 for(int i=0;i<11;i++) {
  float x=edges[i];
  for(int side=-1;side<=1;side+=2) {
   float a=nxPitchMowing(grass,vec3(side*x-3,1700,0)).g;
   float b=nxPitchMowing(grass,vec3(side*x+3,1700,0)).g;
   assert(fabsf(a-b)>.024f); // actual profile branch crosses the marking
  }
  if(i) {float w=x-edges[i-1];narrowest=min(narrowest,w);widest=max(widest,w);}
 }
 assert(widest/narrowest<1.067f); // no oversized/undersized isolated end stripe
 // Centers/widths measured by barycentric UV mapping of the retained paint.
 // The authored edge must lie inside BOTH native white strips on each half.
 const float painted[2][3]={{-3620.2603f,-4728.2362f,-5254.6663f},
                           { 3623.6580f, 4723.1087f, 5255.7618f}};
 const float authored[]={3622,4725.7f,5255.2f};
 for(int side=0;side<2;side++)for(int k=0;k<3;k++)
  assert(fabsf((side?1.f:-1.f)*authored[k]-painted[side][k])<3.f);
 // Every strip has a full flat interior on both halves.
 for(int i=1;i<11;i++)for(int side=-1;side<=1;side+=2) {
  float middle=side*(edges[i-1]+edges[i])*.5f;
  float a=nxPitchMowing(grass,vec3(middle-100,1700,0)).g;
  float b=nxPitchMowing(grass,vec3(middle+100,1700,0)).g;
  assert(fabsf(a-b)<.0109f); // wear only, never another mowing transition
 }
}
''')

    def test_stadium_stripes_align_with_field_markings_and_keep_distinct_widths(self):
        cc=shutil.which('g++')
        if not cc:self.skipTest('Host C++ compiler unavailable')
        build_and_run(cc,host_math()+r'''
int main() {
 const vec3 grass(.03,.09,.01);const int ids[]={0,1,8,9,12};
 const int expected[]={18,20,12,22,20};
 for(int i=0;i<5;i++) {
  nxStadiumProfile=ids[i];int edges=0;float last=0;
  for(int x=-5249;x<5250;x+=2) {
   // Remove shared wear by reading the authored band field independently.
    float mid=ids[i]==9?8:ids[i]==1?7:6,box=2;
   float band=ids[i]==8?nxMowingBand(x/1750.f+.25f):ids[i]==12?nxMowingOldTrafford(x):nxMowingAligned(x,mid,box);
   if(last*band<0)edges++;if(fabsf(band)>.01f)last=band;
  }
  assert(edges==expected[i]-1);
  if(ids[i]==8) {
   const float width=875.f;float last_edge=-5250;
   for(float x=-5250+width;x<=5251;x+=width) {
    float period=width*2;
    assert(fabsf(nxMowingBand(x/period+.25f))<.0001f);
    assert(fabsf(x-last_edge-width)<.001f);last_edge=x;
   }
   continue;
  }
  if(ids[i]==12)continue; // measured native paint bounds checked above
  float mid=ids[i]==9?8:ids[i]==1?7:6,box=2;
  const float anchors[]={-5250,-4700,-3600,0,3600,4700,5250};
  for(float x:anchors)assert(fabsf(nxMowingAligned(x,mid,box))<.0001f);
  assert(nxMowingAligned(-10,mid,box)>.9f && nxMowingAligned(10,mid,box)<-.9f);
  // The pattern is antisymmetric about the halfway line, not the same shade
  // on both sides. Shared wear is fixed to the field, never the camera.
  for(int x=100;x<5200;x+=101)assert(fabsf(nxMowingAligned(x,mid,box)+nxMowingAligned(-x,mid,box))<.001f);
 }
}
''')

    def test_shared_grass_palette_and_wear_preserve_distinct_ring_and_checker_patterns(self):
        cc=shutil.which('g++')
        if not cc:self.skipTest('Host C++ compiler unavailable')
        build_and_run(cc,host_math()+r'''
int main() {
 const vec3 grass(.03,.09,.01);const int ids[]={0,1,2,8,9,12,13};
 int patches=0,total=0;
 for(int id:ids) {
  nxStadiumProfile=id;
  for(int x=-5000;x<=5000;x+=123)for(int y=-3200;y<=3200;y+=131) {
   float band=id==9?nxMowingAligned(x,8,2):id==8?nxMowingBand(x/1750.f+.25f):id==12?nxMowingOldTrafford(x):id==2?(nxMowingAligned(x,3,1)+nxMowingBand(y/1700.f))*.5f:id==13?nxMowingBand(length(vec2(x,y))/1700.f):id==1?nxMowingAligned(x,7,2):nxMowingAligned(x,6,2);
   const vec3 p(x,y,0),g=nxPitchMowing(grass,p);float clean=.09f*(1+.15f*band);
   assert(clean-g.g>=-.000001f && clean-g.g<=.010801f);
   assert(fabsf(g.r/g.g-.033f/.09f)<.000001f && fabsf(g.b/g.g-.009f/.09f)<.000001f);
   patches+=clean-g.g>.003f;total++;
   nxCloudMotion=vec2(200,1);assert(nxPitchMowing(grass,p).g==g.g);
  }
 }
 assert(patches>total*.25 && patches<total*.75);
 // Ring geometry stays circular; patch modulation does not redefine its path.
 for(int radius=100;radius<5000;radius+=100)for(int angle=0;angle<360;angle+=15) {
  float a=angle*3.14159265f/180;
  assert(fabsf(nxMowingBand(length(vec2(cosf(a)*radius,sinf(a)*radius))/1700.f)-nxMowingBand(radius/1700.f))<.0001f);
 }
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

    def test_etihad_has_three_broad_base_green_levels(self):
        cc=shutil.which('g++')
        if not cc:self.skipTest('Host C++ compiler unavailable')
        build_and_run(cc,host_math()+r'''
int main() {
 nxStadiumProfile=2;int dark=0,middle=0,light=0,total=0;
 for(int x=-5190;x<5190;x+=43)for(int y=-3330;y<3330;y+=43) {
  float g=nxPitchMowing(vec3(.033,.09,.009),vec3(x,y,0)).g;
  dark+=g<.078f;middle+=g>=.078f && g<.0915f;light+=g>=.0915f;total++;
 }
 assert(dark>total*.18f && light>total*.18f);
 assert(middle>total*.4f && middle<total*.6f);
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
   // Offset the broad grid from exact paint/band boundaries; anchor neutrality
   // is checked separately and must not bias the light/dark coverage count.
   vec3 pos(x+17,y+13,0);vec3 a=nxPitchMowing(dark,pos),b=nxPitchMowing(light,pos);
   const float lower=.73f,upper=1.15f;
   assert(a.g>=.09f*lower-.000001f && a.g<=.09f*upper+.000001f);
   assert(fabsf(a.g-b.g)<.000001f); // baked green bands replaced, not overlaid
   assert(fabsf(a.r/a.g-.033f/.09f)<.000001f); // shared Stamford palette
   high+=a.g>.095;low+=a.g<.085;
   patterns[i][n++]=a.g;
   for(int day=0;day<2;day++)for(int weather=0;weather<3;weather++) {
    nxDayStadium=day;nxStadiumClimate=vec4(weather,1,0,1);
    same(nxPitchMowing(dark,pos),a); // weather/light remains downstream
   }
   for(int p=0;p<=100;p++)same(nxPitchMowing(vec3(p*.01f),pos),vec3(p*.01f));
  }
  assert(n==1025 && high>n*(ids[i]==2 ? .15f : .30f) && low>n*(ids[i]==2 ? .15f : .30f));
  for(int j=0;j<i;j++) {
   int different=0;
   for(int k=0;k<n;k++)different+=fabsf(patterns[i][k]-patterns[j][k])>.004;
   // Old Trafford shares Anfield's 20-strip count because native goal-area
   // alignment takes priority; its measured paint anchors differ slightly.
   assert(different>n*((ids[i]==12 && ids[j]==1) ? .01f : .30f));
  }
  same(nxPitchMowing(dark,vec3(5401,0,0)),dark);
  same(nxPitchMowing(dark,vec3(0,3551,0)),dark);
  same(nxPitchMowing(dark,vec3(0,0,101)),dark);
 }
 for(int id=-1;id<18;id++) {
  bool supported=false;for(int i=0;i<6;i++)supported|=id==ids[i];
  if(supported || id==0)continue;
  nxStadiumProfile=id;
  same(nxPitchMowing(dark,vec3(300,400,0)),dark);
  same(nxPitchMowing(light,vec3(-500,700,0)),light);
 }
 // Return to Konami, then another imported shell: no old pattern survives.
 for(int repeat=0;repeat<100;repeat++) {
  nxStadiumProfile=1;vec3 first=nxPitchMowing(dark,vec3(300,400,0));
  nxStadiumProfile=0;vec3 konami=nxPitchMowing(dark,vec3(300,400,0));assert(konami.g!=dark.g);
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
