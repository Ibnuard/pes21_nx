"""Optional local-only regression using the reported mislabeled audio and its MP3 conversion.

Set PESNX_PLAYLIST_WRONG_INPUT and PESNX_PLAYLIST_MP3_INPUT to local files.
No recording or copyrighted fixture belongs in this repository.
"""
from pathlib import Path
import os
import shutil

import pytest
import test_custom_playlist_v120 as playlist


def test_reported_input_is_rejected_and_converted_mp3_plays(tmp_path):
    paths = [Path(os.environ.get(key, "")) for key in
             ("PESNX_PLAYLIST_WRONG_INPUT", "PESNX_PLAYLIST_MP3_INPUT")]
    if not all(path.is_file() for path in paths):
        pytest.skip("local reported input and converted MP3 required via PESNX_PLAYLIST_*_INPUT")
    for name, path in zip(("wrong", "correct"), paths):
        directory = tmp_path / name
        directory.mkdir()
        shutil.copyfile(path, directory / "track.mp3")
    adapter = (playlist.ROOT / "source/custom_playlist_native.inc").read_text().split(
        "static void custom_playlist_native_install")[0]
    playlist.compile_run(tmp_path, r'''
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <mpg123.h>
static unsigned decoder_opens, decoder_reads;
static int observe_open(mpg123_handle *h,const char *path) {
 __atomic_add_fetch(&decoder_opens,1u,__ATOMIC_RELAXED);return mpg123_open(h,path);
}
static int observe_read(mpg123_handle *h,unsigned char *p,size_t n,size_t *done) {
 __atomic_add_fetch(&decoder_reads,1u,__ATOMIC_RELAXED);return mpg123_read(h,p,n,done);
}
#define mpg123_open observe_open
#define mpg123_read observe_read
#include "custom_playlist.c"
#undef mpg123_open
#undef mpg123_read
static unsigned mute_calls, input_notes, fallback_notes;
static int muted;
static int registered(int notify){assert(!notify);return 1;}
static void native_mute(const char *name,int value){(void)name;muted=value;++mute_calls;}
static int native_muted(const char *name){(void)name;return muted;}
static float native_volume(const char *name){(void)name;return muted?.00001525f:.8f;}
static void scene_runtime_note(const char *tag,const char *reason) {
 assert(reason&&*reason);
 if(!strcmp(tag,"custom playlist input"))++input_notes;
 else {assert(!strcmp(tag,"custom playlist fallback"));++fallback_notes;}
}
''' + adapter + r'''
int main(void) {
 playlist_native_acf_registered=registered;playlist_native_mute=native_mute;
 playlist_native_is_muted=native_muted;playlist_native_volume=native_volume;
 assert(custom_playlist_init("wrong",1));
 for(unsigned i=0;i<100;++i){custom_playlist_native_tick(1,cp_now_ms());cp_wait(5);}
 assert(!custom_playlist_ready()&&!cp.audible&&!muted&&!mute_calls);
 assert(!decoder_opens&&!decoder_reads&&input_notes==1&&!fallback_notes);
 custom_playlist_shutdown();
 assert(custom_playlist_init("correct",1));
 for(unsigned i=0;i<400;++i){
  custom_playlist_native_tick(1,cp_now_ms());
  if(cp.audible&&__atomic_load_n(&cp.buffered_frames,__ATOMIC_ACQUIRE)>=CP_RING_FRAMES-CP_CHUNK_FRAMES)break;
  cp_wait(5);
 }
 assert(cp.audible&&muted&&!custom_playlist_input_warnings());
 unsigned short_blocks=0,nonzero=0;
 struct timespec deadline;assert(!clock_gettime(CLOCK_MONOTONIC,&deadline));
 uint64_t ns=(uint64_t)deadline.tv_sec*1000000000u+deadline.tv_nsec;
 for(unsigned block=0;block<188;++block){
  uint64_t now=cp_now_ms();custom_playlist_native_tick(1,now);
  int16_t output[2048]={0};unsigned before=cp.read_at;
  custom_playlist_mix_pcm(output,1024,now);
  if(cp.read_at!=(before+1024)%CP_RING_FRAMES)++short_blocks;
  for(unsigned i=0;i<2048;++i)if(output[i])++nonzero;
  ns+=1024u*UINT64_C(1000000000)/CP_RATE;
  deadline.tv_sec=(time_t)(ns/1000000000u);deadline.tv_nsec=(long)(ns%1000000000u);
  assert(!clock_nanosleep(CLOCK_MONOTONIC,TIMER_ABSTIME,&deadline,NULL));
 }
 assert(!short_blocks&&nonzero>100000&&!fallback_notes&&input_notes==1&&mute_calls==1);
 custom_playlist_native_tick(0,cp_now_ms());assert(!muted&&!cp.audible&&mute_calls==2);
 custom_playlist_shutdown();
 printf("reported_input: decoder_reads=0 mute_calls=0; converted_mp3: blocks=188 short_blocks=%u nonzero=%u fallback=%u\n",
        short_blocks,nonzero,fallback_notes);
 return 0;
}
''', real=True)
