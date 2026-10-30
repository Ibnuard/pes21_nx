"""Optional real MP3 -> production ownership adapter -> stereo PCM integration."""
import ctypes
import os
import shutil
import subprocess

import pytest

import test_custom_playlist_v120 as playlist


def test_real_mp3_uses_premute_gain_and_restores_native_music(tmp_path):
    try:
        ctypes.CDLL("libmpg123.so.0")
    except OSError:
        pytest.skip("host libmpg123.so.0 required for real adapter/PCM integration")
    ffmpeg = os.environ.get("FFMPEG_BINARY") or shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg with MP3 encoding required; FFMPEG_BINARY can select it")
    directory = tmp_path / "playlist"
    directory.mkdir()
    # stdout also permits a Windows ffmpeg invoked by WSL: no host path is
    # passed across the OS boundary. This is generated test audio only.
    generated = subprocess.run(
        [ffmpeg, "-nostdin", "-v", "error", "-threads", "1", "-filter_threads", "1",
         "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100:duration=5",
         "-ac", "1", "-codec:a", "libmp3lame", "-b:a", "192k", "-f", "mp3", "pipe:1"],
        capture_output=True, timeout=30)
    error = generated.stderr.decode(errors="replace")
    if generated.returncode and "Unknown encoder 'libmp3lame'" in error:
        pytest.skip("ffmpeg libmp3lame encoder required for generated MP3 integration")
    assert generated.returncode == 0, error
    (directory / "tone.mp3").write_bytes(generated.stdout)
    adapter = (playlist.ROOT / "source/custom_playlist_native.inc").read_text().split(
        "static void custom_playlist_native_install")[0]
    playlist.compile_run(tmp_path, r'''
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include "custom_playlist.c"
static unsigned mute_calls, volume_calls, notes;
static int muted;
static int native_registered(int notify) { assert(!notify);return 1; }
static void native_mute(const char *name,int value) {
 assert(!strcmp(name,"OptVol_Menu_Music"));muted=value;++mute_calls;
}
static int native_is_muted(const char *name) {
 assert(!strcmp(name,"OptVol_Menu_Music"));return muted;
}
static float native_volume(const char *name) {
 ++volume_calls;
 if(!strcmp(name,"OptVol_Menu_Music"))return muted?0.000015259f:0.5f;
 assert(!strcmp(name,"DefVol_Menu_Music"));return 0.8f;
}
static void scene_runtime_note(const char *tag,const char *reason) {
 assert(tag&&reason);++notes;
}
''' + adapter + r'''
static uint64_t monotonic_ns(void) {
 struct timespec now;assert(!clock_gettime(CLOCK_MONOTONIC,&now));
 return (uint64_t)now.tv_sec*1000000000u+(uint64_t)now.tv_nsec;
}
static void wait_until(uint64_t deadline) {
 struct timespec when={(time_t)(deadline/1000000000u),(long)(deadline%1000000000u)};
 assert(!clock_nanosleep(CLOCK_MONOTONIC,TIMER_ABSTIME,&when,NULL));
}
static void await_audible(void) {
 for(unsigned i=0;i<400&&!__atomic_load_n(&cp.audible,__ATOMIC_ACQUIRE);++i) {
  custom_playlist_native_tick(1,cp_now_ms());cp_wait(5);
 }
 assert(__atomic_load_n(&cp.audible,__ATOMIC_ACQUIRE)&&muted);
 assert(fabsf(playlist_native_gain-.4f)<.0001f);
}
int main(void) {
 playlist_native_acf_registered=native_registered;
 playlist_native_mute=native_mute;
 playlist_native_is_muted=native_is_muted;
 playlist_native_volume=native_volume;
 assert(custom_playlist_init("playlist",1));await_audible();
 uint64_t deadline=monotonic_ns();unsigned nonzero=0,peak=0,empty_blocks=0;
 for(unsigned block=0;block<96;++block) {
  int16_t output[1024*2]={0};uint64_t now=cp_now_ms();
  for(unsigned pad=0;pad<8;++pad)custom_playlist_native_tick(1,now);
  custom_playlist_mix_pcm(output,1024,now);
  unsigned block_nonzero=0;
  for(unsigned frame=0;frame<1024;++frame) {
   assert(output[frame*2]==output[frame*2+1]);
   int value=output[frame*2];unsigned magnitude=(unsigned)(value<0?-value:value);
   if(magnitude){++nonzero;++block_nonzero;}
   if(magnitude>peak)peak=magnitude;
  }
  if(!block_nonzero)++empty_blocks;
  deadline+=1024u*UINT64_C(1000000000)/CP_RATE;wait_until(deadline);
 }
 /* Muted GetVolume is about -96 dB. Using it would make all PCM effectively
  * zero, while the actual captured .5 * .8 gain leaves a clear tone. */
 assert(nonzero>90000&&peak>1000&&peak<2100&&!empty_blocks);
 assert(muted&&mute_calls==1&&volume_calls==2&&!notes);
 custom_playlist_native_tick(0,cp_now_ms());
 assert(!muted&&!cp.audible&&mute_calls==2);
 cp_wait(60);unsigned paused=__atomic_load_n(&cp.buffered_frames,__ATOMIC_ACQUIRE);
 int16_t sentinel[1024*2];for(unsigned i=0;i<2048;++i)sentinel[i]=777;
 custom_playlist_mix_pcm(sentinel,1024,cp_now_ms());
 for(unsigned i=0;i<2048;++i)assert(sentinel[i]==777);
 cp_wait(60);assert(paused==__atomic_load_n(&cp.buffered_frames,__ATOMIC_ACQUIRE));
 await_audible();assert(mute_calls==3&&volume_calls==4);
 uint32_t revision=custom_playlist_revision();
 custom_playlist_enable(0);custom_playlist_native_tick(1,cp_now_ms());
 assert(!custom_playlist_enabled()&&custom_playlist_revision()!=revision);
 assert(!muted&&!cp.audible&&mute_calls==4);
 custom_playlist_mix_pcm(sentinel,1024,cp_now_ms());
 for(unsigned i=0;i<2048;++i)assert(sentinel[i]==777);
 custom_playlist_enable(1);assert(!custom_playlist_ready());await_audible();
 assert(mute_calls==5&&volume_calls==6&&!notes);
 custom_playlist_native_tick(0,cp_now_ms());custom_playlist_shutdown();
 assert(!muted&&!custom_playlist_enabled()&&mute_calls==6);
 printf("real_adapter_pcm peak=%u nonzero=%u empty_blocks=%u native_mute_calls=%u\n",
        peak,nonzero,empty_blocks,mute_calls);
 return 0;
}
''', real=True)
