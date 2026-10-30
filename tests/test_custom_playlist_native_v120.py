"""Execute the production menu-music adapter and persisted setting."""
from pathlib import Path
import shutil
import subprocess

import pytest
from test_gameplan_editor import function

ROOT = Path(__file__).resolve().parents[1]


def run_c(tmp_path, body, extra=()):
    cc = shutil.which('gcc')
    if not cc:
        pytest.skip('host C compiler required')
    source, exe = tmp_path / 'test.c', tmp_path / 'test.exe'
    source.write_text(body)
    result = subprocess.run([cc, '-std=c11', '-Wall', '-Wextra', '-Werror',
                             '-I', str(ROOT / 'source'), str(source), *map(str, extra),
                             '-lm', '-o', str(exe)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    result = subprocess.run([str(exe)], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_native_music_mute_ownership_volume_and_fallback(tmp_path):
    from test_custom_playlist_native_v121 import run_adapter
    run_adapter(tmp_path, r'''
 custom_playlist_native_tick(1,1000);assert(!muted && !audible && !acf_calls);
 ready=1;custom_playlist_native_tick(1,1001);
 assert(muted && audible && fabsf(gain-.4f)<.0001f);
 /* The real getter returns ~-96 dB after mute, but PCM keeps its captured gain. */
 custom_playlist_native_tick(1,2000);assert(fabsf(gain-.4f)<.0001f);
 custom_playlist_native_tick(0,2001);assert(!muted && !audible && !playlist_native_owned);
 level=0;custom_playlist_native_tick(1,2002);assert(audible && gain==0);
 custom_playlist_native_tick(0,2003);assert(!muted);
 level=.5f;muted=1;custom_playlist_native_tick(1,2004);assert(audible && gain==0);
 custom_playlist_native_tick(0,2005);assert(muted); /* Preserve pre-existing mute. */
 muted=0;level=NAN;custom_playlist_native_tick(1,2006);assert(audible && gain==0);
 custom_playlist_native_tick(0,2007);assert(!muted && !notes);
''')


def test_playlist_setting_defaults_off_and_survives_restart(tmp_path):
    run_c(tmp_path, r'''
#include <assert.h>
#include "config.h"
int main(void){
 assert(read_config("missing.cfg")<0 && config.custom_playlist==0);
 config.custom_playlist=1;assert(!write_config("settings.cfg"));
 config.custom_playlist=0;assert(!read_config("settings.cfg") && config.custom_playlist==1);
 config.custom_playlist=0;assert(!write_config("settings.cfg"));
 config.custom_playlist=1;assert(!read_config("settings.cfg") && config.custom_playlist==0);
 return 0;
}
''', [ROOT / 'source/config.c'])


def test_settings_third_row_changes_playlist_without_changing_fps(tmp_path):
    hooks = (ROOT / 'source/ue4_hooks.c').read_text()
    functions = '\n'.join(function(hooks, name) for name in (
        'pes_controller_custom_video_settings_focus', 'pes_controller_custom_video_settings_count',
        'pes_controller_custom_video_settings_label', 'pes_controller_custom_video_settings_value',
        'main_menu_video_adjust'))
    run_c(tmp_path, r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "config.h"
Config config;
static uint32_t main_menu_video_settings_open=1,main_menu_video_focus_index=2;
static uint32_t main_menu_video_graphics=1,main_menu_video_frame_rate=1;
static void main_menu_video_apply(uint32_t row,uint32_t value){assert(row==2);config.custom_playlist=value;}
''' + functions + r'''
int main(void){
 assert(pes_controller_custom_video_settings_count()==3 && pes_controller_custom_video_settings_focus()==2);
 assert(!strcmp(pes_controller_custom_video_settings_label(2),"CUSTOM PLAYLIST"));
 main_menu_video_adjust(1);assert(config.custom_playlist==1 && !strcmp(pes_controller_custom_video_settings_value(2),"ON"));
 main_menu_video_adjust(-1);assert(config.custom_playlist==0);
 main_menu_video_adjust(2);assert(config.custom_playlist==1 && main_menu_video_frame_rate==1);
 main_menu_video_settings_open=0;main_menu_video_adjust(2);assert(config.custom_playlist==1);
 return 0;
}
''')
