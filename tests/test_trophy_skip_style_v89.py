"""Run Cup Skip through the actual production set-play helper renderer."""
from pathlib import Path
import re
import shutil
import subprocess

import pytest
from test_gameplan_editor import function

ROOT = Path(__file__).resolve().parents[1]


def block(source, marker):
    start = source.index(marker)
    opening = source.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def harness(source):
    key_start = re.search(r'(?m)^static const char \*overlay_cinematic_skip_key', source)
    assert key_start
    key = function(source[key_start.start():], 'overlay_cinematic_skip_key')
    selection = block(source, 'if (cinematic_helper_active && ceremony_phase == PES_CEREMONY_INPUT_PLAYING)')
    rows = block(source, 'if (setplay_helper_count || corner_entry_count)')
    draw = block(source, 'if (setplay_helper_text_quads)')
    return r'''
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <assert.h>
#include <math.h>
enum { PES_CONTROLLER_PROFILE_FULL, PES_CONTROLLER_PROFILE_SINGLE_LEFT,
       PES_CONTROLLER_PROFILE_SINGLE_RIGHT };
enum { PES_CEREMONY_INPUT_NONE, PES_CEREMONY_INPUT_LOADING, PES_CEREMONY_INPUT_PLAYING };
enum { EFOOTBALL_FONT_REGULAR, EFOOTBALL_FONT_BOLD, FNX_CORNER_DEFENCE=2 };
enum { GL_TEXTURE_2D, GL_TRIANGLES };
typedef unsigned GLuint;
typedef float GLfloat;
typedef struct { float x,y,w,h; } Image;
typedef struct { char label[64]; float x,y,h; int font; } Text;
static Image images[16]; static Text texts[16];
static unsigned image_count,text_count,color_count,offset_count,draw_count;
static float colors[4][4],offsets[4][2];
static int screen_width=1280,screen_height=720;
static float helper_text_gh=17.0f;
static GLuint switch_helper_textures[48];
static int switch_helper_quads[48],switch_helper_count,quads;
static GLfloat verts[4096*24];
static int setplay_helper_text_first_quad,setplay_helper_text_quads;
static const char *setplay_keys[7],*setplay_alternate_keys[7],*setplay_labels[7];
static const char *corner_entry_keys[2],*corner_entry_labels[2];
static unsigned setplay_helper_count,corner_entry_count,corner_available_count;
static int single_joy_setplay;
static struct { int mode; } corner_views[2];
static uint32_t ceremony_phase,profiles[2];
static int cinematic_helper_active,cinematic_goal_two_player;
static struct { int loc_solid,loc_off,loc_color; GLuint efootball_tex,tex; } gl;
static uint32_t android_controller_profile(uint32_t pad) { assert(pad<2); return profiles[pad]; }
static GLuint switch_button_texture(const char *key) {
  if (!strcmp(key,"B")) return 1;
  if (!strcmp(key,"LEFT")) return 2;
  if (!strcmp(key,"A")) return 3;
  if (!strcmp(key,"SL")) return 4;
  if (!strcmp(key,"SR")) return 5;
  assert(0); return 0;
}
static int emit_image_rect(float x,float y,float w,float h,GLfloat *v) {
  (void)v; assert(image_count<16); images[image_count++]=(Image){x,y,w,h}; return 1;
}
static float measure_efootball_line(const char *s,int len,float h,int font) {
  assert((int)strlen(s)==len && font==EFOOTBALL_FONT_BOLD); return len*h*.5f;
}
static int emit_efootball_line(const char *s,int len,float x,float y,float h,
                                int font,GLfloat *v) {
  (void)v; assert(len<64 && text_count<16); Text *text=&texts[text_count++];
  memcpy(text->label,s,len); text->label[len]=0;
  text->x=x; text->y=y; text->h=h; text->font=font; return len;
}
#define ADD_SWITCH_HELPER(KEY,X,Y,SIZE) do { assert(0); } while (0)
static void glBindTexture(int target,GLuint texture) { (void)target; (void)texture; }
static void glUniform1f(int loc,float value) { (void)loc; (void)value; }
static void glUniform2f(int loc,float x,float y) {
  (void)loc; assert(offset_count<4); offsets[offset_count][0]=x; offsets[offset_count++][1]=y;
}
static void glUniform4f(int loc,float r,float g,float b,float a) {
  (void)loc; assert(color_count<4); float *c=colors[color_count++]; c[0]=r;c[1]=g;c[2]=b;c[3]=a;
}
static void glDrawArrays(int mode,int first,int count) {
  assert(mode==GL_TRIANGLES && first==setplay_helper_text_first_quad*6 &&
         count==setplay_helper_text_quads*6); ++draw_count;
}
''' + key + '\nstatic void select_cup(void) {\n' + selection + '\n}\n' + \
        '\nstatic void emit_rows(void) {\n' + rows + '\n}\n' + \
        '\nstatic void draw_text(void) {\n' + draw + '\n}\n' + r'''
static int near(float a,float b) { return fabsf(a-b)<0.0001f; }
static void reset(void) {
  memset(images,0,sizeof(images)); memset(texts,0,sizeof(texts));
  memset(setplay_keys,0,sizeof(setplay_keys));
  memset(setplay_alternate_keys,0,sizeof(setplay_alternate_keys));
  memset(setplay_labels,0,sizeof(setplay_labels));
  image_count=text_count=color_count=offset_count=draw_count=0;
  switch_helper_count=quads=setplay_helper_text_first_quad=setplay_helper_text_quads=0;
  setplay_helper_count=corner_entry_count=corner_available_count=0;
}
int main(void) {
  /* Reference row is emitted by the same unchanged production set-play block. */
  reset(); setplay_keys[0]="B"; setplay_labels[0]="SKIP";setplay_helper_count=1;
  emit_rows(); assert(image_count==1 && text_count==1);
  Image reference_image=images[0]; Text reference_text=texts[0];
  for (unsigned two=0;two<2;++two) for (unsigned p0=0;p0<3;++p0)
    for (unsigned p1=0;p1<3;++p1) {
      reset(); profiles[0]=p0; profiles[1]=p1;
      ceremony_phase=PES_CEREMONY_INPUT_PLAYING; cinematic_helper_active=1;
      cinematic_goal_two_player=two;
      select_cup(); assert(setplay_helper_count==1 && !strcmp(setplay_labels[0],"SKIP"));
      emit_rows();
      unsigned count=two && p0!=p1 ? 2 : 1;
      assert(image_count==count && (unsigned)switch_helper_count==count);
      assert(text_count==1 && !strcmp(texts[0].label,"SKIP")); /* No '+' chord. */
      assert(texts[0].font==EFOOTBALL_FONT_BOLD && texts[0].h==helper_text_gh);
      assert(switch_helper_textures[0]==p0+1);
      if (count==2) assert(switch_helper_textures[1]==p1+1);
      float size=screen_height*.045f,gap=screen_height*.017f;
      float group=size*(count==2?2.65f:1);
      assert(near(images[0].w,size) && near(images[0].h,size));
      assert(near(images[0].y,.925f*screen_height-size*.5f));
      assert(near(texts[0].x,images[0].x+group+gap));
      assert(near(texts[0].x+4*helper_text_gh*.5f,.955f*screen_width));
      if (count==1) {
        assert(!memcmp(&images[0],&reference_image,sizeof(Image)));
        assert(!memcmp(&texts[0],&reference_text,sizeof(Text)));
      } else assert(near(images[1].x,images[0].x+group-size));
      draw_text(); assert(draw_count==2 && color_count==2 && offset_count==2);
      assert(colors[0][0]==0 && colors[0][1]==0 && colors[0][2]==0 && near(colors[0][3],.85f));
      assert(colors[1][0]==1 && colors[1][1]==1 && colors[1][2]==1 && colors[1][3]==1);
      assert(near(offsets[0][0],2.0f/screen_width) && near(offsets[0][1],-2.0f/screen_height));
      assert(offsets[1][0]==0 && offsets[1][1]==0);
    }
  /* Existing set-play rail chords keep their two sprites and '+' marker. */
  reset();setplay_keys[0]="L1+R1";setplay_labels[0]="SET PIECE TAKER";setplay_helper_count=1;
  emit_rows(); assert(image_count==2 && switch_helper_textures[0]==4 && switch_helper_textures[1]==5);
  assert(text_count==2 && !strcmp(texts[0].label,"+") && !strcmp(texts[1].label,"SET PIECE TAKER"));
  /* Hidden/loading ceremonies cannot replace another surface's rows. */
  for (unsigned phase=0;phase<3;++phase) {
    reset();setplay_keys[0]="B";setplay_labels[0]="ORIGINAL";setplay_helper_count=1;
    ceremony_phase=phase;cinematic_helper_active=0;select_cup();
    assert(!strcmp(setplay_labels[0],"ORIGINAL"));
  }
  return 0;
}
'''


def test_skip_uses_identical_production_setplay_style(tmp_path):
    compiler = shutil.which('gcc') or shutil.which('clang')
    if not compiler:
        pytest.skip('host C compiler required')
    source = (ROOT / 'source/overlay.c').read_text(encoding='utf-8')
    path, exe = tmp_path / 'skip-style.c', tmp_path / 'skip-style.exe'
    path.write_text(harness(source), encoding='utf-8')
    built = subprocess.run([compiler, '-std=c11', '-Wall', '-Wextra', '-Werror',
                            str(path), '-lm', '-o', str(exe)],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stdout + ran.stderr


def test_legacy_goal_demo_row_is_not_used_for_cup():
    source = (ROOT / 'source/overlay.c').read_text(encoding='utf-8')
    legacy = block(source, 'if (cinematic_helper_active && ceremony_phase != PES_CEREMONY_INPUT_PLAYING)')
    assert 'EFOOTBALL_FONT_REGULAR' in legacy
    assert 'GOAL CELEBRATION' in legacy
    assert 'setplay_helper_text_quads' not in legacy
