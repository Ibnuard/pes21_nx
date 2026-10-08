"""Preview Cup news screens using production C geometry and synthetic saves.

No game runtime is loaded. The frontend runs in a temporary directory; its
existing OpenGL draw calls are recorded and rasterized with the public assets.
Uses generated Cup artwork and the shared Master League UI components.
Requires a host C compiler and Pillow. Outputs are for review, not device captures.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from test_gameplan_editor import function, struct


def between(text, start, end):
    return text.split(start, 1)[1].split(end, 1)[0]


C_PREFIX = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <assert.h>
#include "competition_frontend.h"
#include "master_league_frontend.h"
#include "exhibition_team_catalog.h"
#include "fl26_cup_catalog_generated.h"
#include "fl26_league_catalog_generated.h"
#include "efootball_font_atlas.h"
#include "badge_atlas.h"
#include "switch_button_assets.h"
#include "ue4_hooks.h"
typedef float GLfloat;
typedef unsigned int GLuint;
typedef int GLint;
typedef uint64_t u64;
typedef void (*OverlayBindSamplerProc)(GLuint, GLuint);
#define GL_TRIANGLES 1
#define GL_TEXTURE_2D 2
#define GL_SAMPLER_BINDING 3
static int screen_width=1280, screen_height=720;
static uint64_t preview_ticks=10000000000ull;
static uint64_t armGetSystemTick(void) { return preview_ticks; }
static uint64_t armTicksToNs(uint64_t t) { return t; }
uint32_t pes_controller_native_hid_connected_mask(void) { return 3u; }
static struct { uint32_t current; } main_menu_portrait_transition={2};
enum { FNX_BUTTON_FRAME, FNX_BUTTON_FILL, FNX_BUTTON_GLOSS, FNX_BUTTON_TEXT };
static FILE *frame;
static GLfloat *active_vertices;
static int active_quads, draw_count;
static float uniforms[64][4];
static GLuint bound_texture;
static void glUniform1f(int loc,float a) { uniforms[loc][0]=a; }
static void glUniform2f(int loc,float a,float b) { uniforms[loc][0]=a; uniforms[loc][1]=b; }
static void glUniform4f(int loc,float a,float b,float c,float d) {
  uniforms[loc][0]=a; uniforms[loc][1]=b; uniforms[loc][2]=c; uniforms[loc][3]=d;
}
static void glBindTexture(int target,GLuint texture) { (void)target;bound_texture=texture; }
static void glGetIntegerv(int key,GLint *out) { (void)key;*out=0; }
static void prepare_league_logo_index(uint32_t index) { (void)index; }
static GLuint gameplan_portrait_texture(uint32_t id) { (void)id;return 0; }
static GLuint current_league_logo_texture(void) { return 0; }
'''

C_RECORD = r'''
static void glDrawArrays(int mode,int first,int count) {
  (void)mode;
  if(!count || uniforms[gl.loc_color][3]<=0.f)return;
  assert(first>=0 && count>=0 && first%6==0 && count%6==0 && first+count<=active_quads*6);
  int kind=uniforms[gl.loc_solid][0]>.5f ? 0 : uniforms[gl.loc_image][0]>.5f ? 2 : 1;
  fprintf(frame,"%s{\"kind\":%d,\"texture\":%u,\"radius\":%g,\"color\":[%g,%g,%g,%g],\"vertices\":[",
      draw_count++ ? "," : "",kind,bound_texture,uniforms[gl.loc_round_rect][0]>.5f ? uniforms[gl.loc_round_radius][0] : 0.f,
      uniforms[gl.loc_color][0],uniforms[gl.loc_color][1],uniforms[gl.loc_color][2],uniforms[gl.loc_color][3]);
  for(int i=0;i<count*4;i++) {
    float f=active_vertices[first*4+i];
    if(i%4<2)f+=uniforms[gl.loc_off][i%4];
    fprintf(frame,"%s%.8g",i ? "," : "",f);
  }
  fprintf(frame,"]}");
}
static GLuint switch_button_texture(const char *key) {
  if(!strcmp(key,"A"))return 20;
  if(!strcmp(key,"B"))return 21;
#define KEY_TEXTURE(name,value) if(!strcmp(key,value))return 22+SWITCH_BUTTON_##name;
  SWITCH_BUTTON_ASSETS(KEY_TEXTURE)
#undef KEY_TEXTURE
  assert(!"Unknown helper key");return 0;
}
'''

C_DRIVER = r'''
enum {B=1u<<0,A=1u<<1,Y=1u<<2,X=1u<<3,L=1u<<4,R=1u<<7,
      UP=1u<<10,DOWN=1u<<11,LEFT=1u<<12,RIGHT=1u<<13};
static void press(uint32_t key) {
  competition_frontend_pad_event(0,0);competition_frontend_pad_event(key,0);competition_frontend_pad_event(0,0);
}
static void enter_cup(void) {
  competition_frontend_close();competition_frontend_finish_close();
  competition_frontend_open_modes();competition_frontend_pad_event(0,0);press(A);
  assert(competition_frontend_state()==COMPETITION_FRONTEND_CUP_LANDING);
}
static void assert_toast_visible(int visible) {
  static GLfloat verts[16000*24];int quads=0,foreground=0;MasterLeagueRender ui;
  cup_news_emit(&ui,competition_frontend_state(),verts,&quads);
  for(uint32_t i=0;i<ui.draw_count;i++)if(ui.draws[i].layer==1)foreground++;
  assert(visible ? foreground==3 : foreground==0);
}
int main(void) {
  initialize_gl();
  FILE *font=fopen("font.pgm","wb");assert(font);
  fprintf(font,"P5\n%d %d\n255\n",EFOOTBALL_FONT_ATLAS_W,EFOOTBALL_FONT_ATLAS_H);
  fwrite(efootball_font_atlas_alpha,1,sizeof(efootball_font_atlas_alpha),font);fclose(font);
  enter_cup();capture("01-new-continue");
  press(DOWN);press(A);assert(competition_frontend_state()==COMPETITION_FRONTEND_CUP_SLOTS);
  capture("02-load-empty");press(B);press(A);
  assert(competition_frontend_state()==COMPETITION_FRONTEND_CUP_SETTINGS);
  press(DOWN);press(RIGHT);assert(competition_frontend_cup_player_count()==2u);
  capture("03-cup-settings");
  for(uint32_t i=0;i<3;i++)press(DOWN);
  press(RIGHT);press(DOWN);
  capture("04-cup-settings-create");press(A);
  assert(competition_frontend_state()==COMPETITION_FRONTEND_CUP_BRACKET);
  assert(!competition_frontend_item_enabled(1));capture("05-cup-hub-empty");
  press(A);assert(competition_frontend_cup_bracket_editing());
  press(A);assert(competition_frontend_cup_team_picker_active());
  competition_frontend_cup_team_picker_result(101u);
  press(DOWN);press(A);competition_frontend_cup_team_picker_result(102u);
  press(X);assert(competition_draft_ready(competition_frontend_cup_draft()));
  capture("06-participants");
  const uint32_t moved_team=competition_frontend_cup_draft()->teams[1];
  const uint32_t replaced_team=competition_frontend_cup_draft()->teams[2];
  char slot_code[16];
  assert(cup_ui_slot_code(competition_frontend_cup_draft(),1,slot_code,sizeof(slot_code))==0u && !strcmp(slot_code,"01B"));
  press(Y);press(DOWN);capture("33-participants-move-target");assert_toast_visible(1);
  preview_ticks+=3100000000ull;capture("38-participants-move-persistent");assert_toast_visible(1);press(A);
  assert(competition_frontend_cup_draft()->teams[2]==moved_team && competition_frontend_cup_draft()->owners[2]==2u);
  assert(competition_frontend_cup_draft()->teams[1]==replaced_team && competition_frontend_cup_draft()->owners[1]==0u);
  assert(cup_ui_slot_code(competition_frontend_cup_draft(),1,slot_code,sizeof(slot_code))==0u && !strcmp(slot_code,"01B"));
  assert(cup_ui_slot_code(competition_frontend_cup_draft(),2,slot_code,sizeof(slot_code))==1u && !strcmp(slot_code,"02A"));
  capture("34-participants-slots-swapped");assert_toast_visible(1);
  preview_ticks+=3100000000ull;capture("37-participants-toast-dismissed");assert_toast_visible(0);
  press(Y);press(UP);press(A);press(B);
  press(UP);press(RIGHT);assert(competition_frontend_focus()==1u);
  assert(competition_frontend_item_enabled(1));capture("07-cup-hub-ready");
  CupTournament unchanged=*competition_frontend_cup_tournament();
  for(uint64_t ms=100u;ms<=6500u;ms+=100u)competition_frontend_tick(ms);
  assert(competition_frontend_cup_news_index()==1u);
  assert(!memcmp(&unchanged,competition_frontend_cup_tournament(),sizeof(unchanged)));
  capture("08-news-next-match");
  press(DOWN);assert(competition_frontend_focus()==2u);press(A);
  assert(competition_frontend_cup_general_open());capture("09-general-settings");
  for(uint32_t i=0;i<5;i++)press(DOWN);capture("10-general-settings-page2");
  press(B);press(RIGHT);press(A);assert(competition_frontend_state()==COMPETITION_FRONTEND_CUP_SLOTS);
  capture("11-save-slots");press(A);assert(competition_frontend_state()==COMPETITION_FRONTEND_CUP_BRACKET);
  const uint32_t saved_team=competition_frontend_cup_draft()->teams[0];
  press(LEFT);press(LEFT);assert(competition_frontend_focus()==4u);press(A);
  assert(competition_frontend_cup_page()==CUP_PAGE_BRACKET);capture("12-bracket");
  press(Y);capture("13-bracket-next-page");press(R);capture("14-bracket-next-round");
  press(B);press(UP);assert(competition_frontend_focus()==5u);press(A);
  assert(competition_frontend_cup_page()==CUP_PAGE_MATCHES);capture("15-match-centre");press(B);
  enter_cup();press(DOWN);capture("16-continue-selected");press(A);
  assert(competition_frontend_item_enabled(0));capture("17-load-populated");press(A);
  assert(competition_frontend_cup_draft()->teams[0]==saved_team);capture("18-cup-hub-loaded");
  press(UP);press(RIGHT);press(A);assert(competition_frontend_take_action()==COMPETITION_ACTION_CUP_FIXTURE);
  competition_frontend_cup_handoff_result(1);competition_frontend_cup_match_result(2,0);
  competition_frontend_cup_restore_after_match();competition_frontend_pad_event(0,0);
  capture("19-result-news");
  for(uint32_t played=0;played<32u && !competition_frontend_cup_tournament()->champion;played++) {
    press(A);assert(competition_frontend_take_action()==COMPETITION_ACTION_CUP_FIXTURE);
    competition_frontend_cup_handoff_result(1);competition_frontend_cup_match_result(2,0);
    competition_frontend_cup_restore_after_match();competition_frontend_pad_event(0,0);
  }
  assert(competition_frontend_cup_tournament()->champion);capture("20-champion-news");
  press(DOWN);press(LEFT);press(A);capture("21-final-and-third-place");
  enter_cup();press(A);for(uint32_t i=0;i<5u;i++)press(RIGHT);
  press(DOWN);for(uint32_t i=0;i<7u;i++)press(RIGHT);
  assert(competition_frontend_cup_player_count()==8u && competition_frontend_cup_team_count()==32u);
  capture("22-eight-player-settings");
  while(competition_frontend_focus()!=5u)press(DOWN);
  press(A);press(A);press(X);
  for(uint32_t i=0;i<7u;i++)press(DOWN);capture("23-eight-players");
  press(DOWN);capture("24-participants-next-page");press(B);
  press(RIGHT);press(A);for(uint32_t i=0;i<7u;i++)press(Y);capture("25-32-team-bracket-page8");
  assert(competition_frontend_cup_view_page_index()==7u);
  enter_cup();press(A);
  static const char *types[]={"26-settings-fa-cup","27-settings-copa-del-rey","28-settings-coppa-italia",
      "29-settings-afc-cup","30-settings-euro","31-settings-world-cup","32-settings-footballnx-cup"};
  for(uint32_t i=0;i<FL26_CUP_CATALOG_COUNT;i++) {
    assert(competition_frontend_cup_catalog_index()==i);
    capture(types[i]);press(RIGHT);
  }
  for(uint32_t i=0;i<6u;i++)press(RIGHT);
  press(DOWN);press(DOWN);
  for(uint32_t i=0;i<32u && competition_frontend_cup_team_count()!=20u;i++)press(RIGHT);
  assert(competition_frontend_cup_team_count()==20u);
  while(competition_frontend_focus()!=5u)press(DOWN);
  press(A);press(A);press(X);
  for(uint32_t i=0;i<8u;i++)press(DOWN);
  assert(cup_ui_slot_code(competition_frontend_cup_draft(),8,slot_code,sizeof(slot_code))==4u && !strcmp(slot_code,"05A"));
  assert(cup_ui_slot_code(competition_frontend_cup_draft(),9,slot_code,sizeof(slot_code))==5u && !strcmp(slot_code,"06A"));
  capture("35-participants-bye-slots");press(B);press(RIGHT);press(A);
  press(Y);press(Y);capture("36-bracket-bye-slots");
  return 0;
}
'''


def build_driver(source, logos=()):
    shared = (ROOT / "source/master_league_overlay.inc").read_text()
    renderer = (ROOT / "source/cup_overlay.inc").read_text()
    gl_struct = "static struct {" + between(source, "// text-overlay GL objects, created lazily on first draw\nstatic struct {", "} gl;") + "} gl;"
    helpers = ["efootball_raster_level", "efootball_raster_height", "efootball_raster_width",
        "efootball_raster_advances", "measure_efootball_line_mode", "emit_efootball_line_mode",
        "emit_badge", "emit_image_rect_uv", "emit_image_rect", "emit_round_rect_quad",
        "use_rounded_rect", "fnx_button_color"]
    ui_helpers = ["ml_ui_draw", "ml_ui_rect", "ml_ui_text", "ml_ui_image", "ml_ui_button",
        "ml_ui_center_text", "ml_ui_unread", "ml_ui_art", "ml_ui_icon", "ml_ui_frame",
        "ml_ui_emblem", "ml_ui_header_icon", "ml_ui_panel", "ml_ui_row", "ml_ui_pills", "ml_ui_toast_card",
        "master_league_draw_layer", "master_league_draw"]
    uniforms = sorted(set(re.findall(r"gl\.(loc_\w+)", source)))
    fields = {"tex": 1, "efootball_tex": 2, "badge_tex": 3,
        "master_league_cards_tex": 50, "master_league_icons_tex": 51,
        "master_league_headers_tex": 52, "master_league_emblems_tex": 53,
        "cup_pearl_tex": 54, "cup_news_tex": 55, "main_menu_brand_tex": 56}
    initialize = "static void initialize_gl(void) {\n" + "\n".join(
        [f"gl.{name}={i};" for i, name in enumerate(uniforms, 1)] +
        [f"gl.{name}={value};" for name, value in fields.items()] +
        [f"gl.cup_logo_tex[{logo['index']}]={80+logo['index']};gl.cup_logo_uploaded[{logo['index']}]=1;gl.cup_logo_aspect[{logo['index']}]={logo['width']/logo['height']:.9f}f;" for logo in logos]) + "\n}"
    capture = r'''
static void capture(const char *name) {
  static GLfloat verts[16000*24];int quads=0;MasterLeagueRender ui;
  const CupTournament *live=competition_frontend_cup_tournament();CupTournament before={0};
  if(live)before=*live;
  cup_news_emit(&ui,competition_frontend_state(),verts,&quads);
  preview_ticks+=200000000ull;quads=0;
  cup_news_emit(&ui,competition_frontend_state(),verts,&quads);
  assert(quads<4096 && ui.draw_count<380);
  if(live)assert(!memcmp(live,&before,sizeof(before)));
  for(uint32_t i=0;i<ui.view.helper_count;i++)
    ml_ui_image(&ui,switch_button_texture(ui.view.helper_key[i]),0,
      ui.helper_centers[i]-.0444f*.5625f*.5f,.9625f-.0222f,.0444f*.5625f,.0444f,verts,&quads);
  char filename[128];snprintf(filename,sizeof(filename),"%s.json",name);
  frame=fopen(filename,"w");assert(frame);fprintf(frame,"[");draw_count=0;
  memset(uniforms,0,sizeof(uniforms));bound_texture=0;
  active_quads=quads;active_vertices=verts;
  master_league_draw(&ui);master_league_draw_layer(&ui,1);
  fprintf(frame,"]");fclose(frame);
  printf("%s: %d quads, %d draws\n",name,quads,draw_count);
}
'''
    return "\n".join([C_PREFIX, struct(source, "RoundedRectStyle"), gl_struct, C_RECORD,
        function(source,"current_cup_logo_texture"),
        *[function(source, name) for name in helpers], struct(shared,"MlDraw"),struct(shared,"MasterLeagueRender"),
        *[function(shared, name) for name in ui_helpers], renderer, initialize, capture, C_DRIVER])


def textures(folder, logos=()):
    data = ROOT / "data"
    result = {2: Image.open(folder / "font.pgm").convert("RGB")}
    names = {20: "main_menu_button_a", 21: "main_menu_button_b",
        50: "master_league_cards_v2", 51: "master_league_icons_v4", 52: "master_league_headers_v8",
        53: "master_league_emblems_v7", 54: "cup_pearl_v1", 55: "cup_news_v1", 56: "main_menu_brand"}
    header = (ROOT / "source/switch_button_assets.h").read_text()
    for i, (name, _) in enumerate(re.findall(r'X\((\w+), "([^"]+)"\)', header)):
        names[22+i] = "switch_button_" + name
    for key, name in names.items():
        result[key] = Image.open(data / f"{name}.bin").convert("RGBA")
    badge = (ROOT / "source/badge_atlas.h").read_text()
    def define(name):
        return int(re.search(r"#define " + name + r" (\d+)", badge)[1])
    cell = define("BADGE_CELL_SIZE")
    result[3] = Image.frombytes("RGBA", (cell*define("BADGE_ATLAS_COLS"),
        cell*define("BADGE_ATLAS_ROWS")), (data / "badge_atlas.bin").read_bytes())
    for logo in logos:
        result[80+logo["index"]] = Image.open(logo["path"]).convert("RGBA")
    return result


def rasterize(draws, assets):
    canvas = Image.new("RGBA", (1280, 720), (0, 0, 0, 255))
    for draw in draws:
        color = tuple(max(0, min(255, round(c*255))) for c in draw["color"])
        for start in range(0, len(draw["vertices"]), 24):
            v = draw["vertices"][start:start+24]
            points = [(round((v[i]+1)*640), round((1-v[i+1])*360)) for i in range(0, 24, 4)]
            x0, y0 = min(x for x,y in points), min(y for x,y in points)
            x1, y1 = max(x for x,y in points), max(y for x,y in points)
            w, h = x1-x0, y1-y0
            if w <= 0 or h <= 0:
                continue
            if draw["kind"] == 0:
                tile = Image.new("RGBA", (w,h), color)
                mask = Image.new("L", (w*4,h*4))
                painter = ImageDraw.Draw(mask)
                if len(set(points)) == 3:
                    painter.polygon([((x-x0)*4,(y-y0)*4) for x,y in points[:3]], fill=color[3])
                else:
                    painter.rounded_rectangle((0,0,w*4-1,h*4-1), radius=draw["radius"]*4, fill=color[3])
                tile.putalpha(mask.resize((w,h), Image.Resampling.LANCZOS))
            else:
                texture = assets[draw["texture"]]
                box = (v[2]*texture.width,v[3]*texture.height,v[18]*texture.width,v[19]*texture.height)
                sample = texture.transform((w,h), Image.Transform.EXTENT, box, resample=Image.Resampling.BILINEAR)
                if draw["kind"] == 1:
                    tile = Image.new("RGBA", (w,h), color)
                    tile.putalpha(sample.getchannel("R").point(lambda a: round(a*color[3]/255)))
                else:
                    tile = sample.convert("RGBA")
                    tile.putalpha(tile.getchannel("A").point(lambda a: round(a*color[3]/255)))
                    if draw["radius"]:
                        mask = Image.new("L", (w*4,h*4))
                        ImageDraw.Draw(mask).rounded_rectangle((0,0,w*4-1,h*4-1), radius=draw["radius"]*4, fill=255)
                        tile.putalpha(ImageChops.multiply(tile.getchannel("A"),mask.resize((w,h),Image.Resampling.LANCZOS)))
            canvas.alpha_composite(tile, (x0,y0))
    return canvas.convert("RGB")



def write_gallery(output, frames):
    labels = [p.stem.split("-", 1)[1].replace("-", " ").title() for p in frames]
    names = [p.with_suffix(".png").name for p in frames]
    html = """<!doctype html>
<html lang="id"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FootballNX · Cup UI review</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#e9eff6;color:#102747;font:15px system-ui,sans-serif}
header{padding:20px 28px;background:#102747;color:white;display:flex;justify-content:space-between;align-items:center;gap:16px}
h1{font-size:20px;margin:0 0 5px}header p{font-size:13px;opacity:.7;margin:0}main{max-width:1500px;margin:auto;padding:20px}
nav{display:flex;gap:8px;overflow:auto;padding:0 0 16px}button,select{font:inherit;border:1px solid #c2d0e1;border-radius:8px;padding:10px 14px;background:white;color:#102747;cursor:pointer;white-space:nowrap}button:focus-visible,select:focus-visible{outline:3px solid #00a5d2;outline-offset:2px}button[aria-pressed=true]{background:#075ca9;border-color:#075ca9;color:white}
figure{margin:0;background:#132c4c;border-radius:12px;overflow:hidden;box-shadow:0 8px 28px #1e35551a}img{display:block;width:100%;aspect-ratio:16/9;object-fit:contain}figcaption{display:flex;align-items:center;justify-content:space-between;gap:12px;background:white;padding:14px 18px}.meta{font-size:13px;color:#566c84}footer{display:flex;gap:10px;align-items:center;justify-content:center;padding:18px}
@media(max-width:700px){header{display:block;padding:16px}header div+div{margin-top:12px}main{padding:10px}figcaption{display:block}.meta{margin-top:6px}select{max-width:220px}}
</style>
<header><div><h1>Cup · News carousel direction</h1><p>Preview renderer C produksi · data sintetis · 1280 × 720 · bukan capture Switch</p></div><div>FootballNX / Design review 06</div></header>
<main><nav aria-label="Flow utama"><button data-frame="0">New / Continue</button><button data-frame="2">Cup Settings</button><button data-frame="6">Cup Hub</button><button data-frame="5">Participants</button><button data-frame="32">Move Slot</button><button data-frame="16">Load</button><button data-frame="11">Bracket</button><button data-frame="14">Match Centre</button></nav>
<figure><img id="shot" alt=""><figcaption><strong id="label"></strong><span class="meta" id="position"></span></figcaption></figure>
<footer><button id="previous" aria-label="Preview sebelumnya">←</button><select id="pages" aria-label="Pilih preview"></select><button id="next" aria-label="Preview berikutnya">→</button></footer>
<p class="meta">Gunakan tombol panah atau pilih halaman. Gambar berasal dari implementasi UI; kontrol di dalam gambar merupakan tampilan statis untuk review.</p></main>
<script>
const files=FILES, labels=LABELS;let index=0;
const image=document.querySelector('#shot'),select=document.querySelector('#pages');
labels.forEach((label,i)=>{const o=document.createElement('option');o.value=i;o.textContent=String(i+1).padStart(2,'0')+' · '+label;select.appendChild(o)});
function show(i){index=(i+files.length)%files.length;image.src=files[index];image.alt=labels[index];select.value=index;document.querySelector('#label').textContent=labels[index];document.querySelector('#position').textContent=(index+1)+' / '+files.length;document.querySelectorAll('[data-frame]').forEach(b=>b.setAttribute('aria-pressed',Number(b.dataset.frame)===index));}
document.querySelectorAll('[data-frame]').forEach(b=>b.onclick=()=>show(Number(b.dataset.frame)));
select.onchange=()=>show(Number(select.value));document.querySelector('#previous').onclick=()=>show(index-1);document.querySelector('#next').onclick=()=>show(index+1);
document.addEventListener('keydown',e=>{if(e.target.tagName==='SELECT')return;if(e.key==='ArrowRight'){e.preventDefault();show(index+1)}if(e.key==='ArrowLeft'){e.preventDefault();show(index-1)}});show(0);
</script></html>"""
    (output / "index.html").write_text(html.replace("FILES", json.dumps(names)).replace("LABELS", json.dumps(labels)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path, default=ROOT/"local-debug/cup-news-preview")
    parser.add_argument("--cup-logos", type=Path, help="Optional runtime CupLogos folder; filenames follow the source catalog")
    args = parser.parse_args()
    logo_dir = args.cup_logos.resolve() if args.cup_logos else ROOT / "CupLogos"
    if args.cup_logos and not logo_dir.is_dir():
        parser.error(f"CupLogos folder not found: {logo_dir}")
    logos = []
    catalog = json.loads((ROOT / "data/fl26_cup_catalog.json").read_text())["cups"]
    for index, cup in enumerate(catalog):
        name = cup["logo_file"]
        if not name or not (logo_dir / name).is_file():
            continue
        path = logo_dir / name
        with Image.open(path) as logo:
            logos.append({"index": index, "file": name, "path": str(path),
                "width": logo.width, "height": logo.height,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    source = (ROOT / "source/overlay.c").read_text()
    with tempfile.TemporaryDirectory(prefix="pes-cup-preview-") as temporary:
        temp = Path(temporary)
        (temp / "preview.c").write_text(build_driver(source, logos))
        # Only the native hook type dependency is replaced for this host harness.
        # Frontend and tournament/save implementation bytes are otherwise unchanged.
        (temp / "ue4_hooks.h").write_text((ROOT / "source/ue4_hooks.h").read_text().replace(
            '#include "so_util.h"', 'typedef struct so_module so_module;'))
        shutil.copy2(ROOT / "source/competition_frontend.c", temp / "competition_frontend.c")
        core = ["competition_entry_draft.c", "cup_tournament.c", "cup_save.c",
            "league_tournament.c", "league_save.c", "master_league.c", "master_league_save.c",
            "master_league_frontend.c", "master_league_catalog.c", "gameplan_preset.c"]
        command = [shutil.which("cc") or shutil.which("gcc"), "-std=c11", "-Wno-constant-logical-operand",
            "-I", str(temp), "-I", str(ROOT / "source"), str(temp / "preview.c"),
            str(temp / "competition_frontend.c"), *[str(ROOT / "source" / name) for name in core],
            "-lm", "-o", str(temp / "preview")]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            print(result.stderr, file=sys.stderr)
            raise SystemExit(result.returncode)
        subprocess.run([str(temp / "preview")], cwd=temp, check=True)
        assets = textures(temp, logos)
        frames = sorted(temp.glob("*.json"))
        for frame in frames:
            draws = json.loads(frame.read_text())
            rasterize(draws, assets).save(output / frame.with_suffix(".png").name)
        write_gallery(output, frames)
        (output / "provenance.json").write_text(json.dumps({
            "description": "Production Cup news renderer, synthetic competition and temporary save; not Switch screenshots",
            "source_sha256": {name: hashlib.sha256((ROOT / "source" / name).read_bytes()).hexdigest() for name in ["overlay.c", "cup_overlay.inc", "master_league_overlay.inc", "competition_frontend.c"]},
            "assets": "generated Cup artwork, shared Master League controls and public badge catalog",
            "cup_logos": [{k:v for k,v in logo.items() if k != "path"} for logo in logos],
            "missing_cup_logos": "Runtime FootballNX fallback used wherever the mapped PNG is unavailable",
            "size": [1280,720], "frames": [p.with_suffix(".png").name for p in frames],
        }, indent=2) + "\n")
    print(output)


if __name__ == "__main__":
    main()
