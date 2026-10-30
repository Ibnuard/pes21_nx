"""User MP3 worker ownership and actual final-buffer mixing, without game data."""
from pathlib import Path
import ctypes
import os
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Deterministic decoder transport for concurrency/failure tests. The production
# worker, directory scan, generation gates, ring and mixer are compiled intact.
MPG_STUB = r'''
#ifndef TEST_MPG123_H
#define TEST_MPG123_H
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
enum {MPG123_OK=0, MPG123_ERR=-1, MPG123_NEW_FORMAT=-11, MPG123_DONE=-12,
 MPG123_ADD_FLAGS=2, MPG123_FORCE_RATE=3, MPG123_INDEX_SIZE=15,
 MPG123_RESYNC_LIMIT=14, MPG123_FORCE_STEREO=8, MPG123_QUIET=32,
 MPG123_SKIP_ID3V2=8192, MPG123_NO_PEEK_END=131072,
 MPG123_STEREO=2, MPG123_ENC_SIGNED_16=208};
typedef struct {unsigned at; int format, invalid_format;} mpg123_handle;
static unsigned fake_opens, fake_reads, fake_live;
static int mpg123_init(void) {return 0;}
static mpg123_handle *mpg123_new(const char *d,int *e) {
 (void)d; (void)e; mpg123_handle *h=calloc(1,sizeof(*h));
 if(h)__atomic_add_fetch(&fake_live,1u,__ATOMIC_RELAXED);
 return h;
}
static void mpg123_delete(mpg123_handle *h) {
 if(h){__atomic_sub_fetch(&fake_live,1u,__ATOMIC_RELAXED);free(h);}
}
static int mpg123_param(mpg123_handle *h,int p,long v,double f) {
 (void)h;(void)p;(void)v;(void)f;return 0;
}
static int mpg123_format_none(mpg123_handle *h) {(void)h;return 0;}
static int mpg123_format(mpg123_handle *h,long r,int c,int e) {
 (void)h;return r==48000&&c==2&&e==208?0:-1;
}
static int mpg123_open(mpg123_handle *h,const char *path) {
 __atomic_add_fetch(&fake_opens,1u,__ATOMIC_RELAXED);
 const char *name=strrchr(path,'/');name=name?name+1:path;
 h->invalid_format=strstr(name,"wrong")!=NULL;
 return strstr(name,"bad") ? MPG123_ERR : MPG123_OK;
}
static int mpg123_getformat(mpg123_handle *h,long *r,int *c,int *e) {
 *r=h->invalid_format?44100:48000;*c=2;*e=208;return 0;
}
static int mpg123_read(mpg123_handle *h,unsigned char *out,size_t capacity,size_t *done) {
 __atomic_add_fetch(&fake_reads,1u,__ATOMIC_RELAXED);*done=0;
 if(!h->format){h->format=1;return MPG123_NEW_FORMAT;}
 unsigned count=(unsigned)(capacity/4u);
 if(count>12000-h->at)count=12000-h->at;
 for(unsigned i=0;i<count;++i){((int16_t*)out)[i*2]=1000;((int16_t*)out)[i*2+1]=-1000;}
 *done=count*4u;h->at+=count;return h->at==12000?MPG123_DONE:MPG123_OK;
}
#endif
'''

PREFIX = r'''
#include <assert.h>
#include "custom_playlist.c"
static void prime(void) {
 cp.started=1;cp.enabled=1;cp.generation=1;
 assert(cp_reset_ring(1));custom_playlist_publish(1,100);
 static int16_t samples[CP_PREFILL_FRAMES*2];
 for(unsigned i=0;i<CP_PREFILL_FRAMES;++i){samples[i*2]=20000;samples[i*2+1]=-20000;}
 assert(cp_push(samples,CP_PREFILL_FRAMES,1)==CP_PREFILL_FRAMES);
 assert(custom_playlist_ready());
}
'''


def compile_run(tmp_path, body, *, real=False):
    compiler = shutil.which("gcc") or shutil.which("clang")
    if not compiler:
        pytest.skip("host C compiler required")
    source, executable = tmp_path / "playlist.c", tmp_path / "playlist-test.exe"
    source.write_text(body, encoding="utf-8")
    command = [compiler, "-std=c11", "-D_POSIX_C_SOURCE=200809L", "-O2",
               "-Wall", "-Wextra", "-Werror", "-pthread",
               "-I", str(ROOT / "source")]
    if real:
        header = Path(os.environ.get("MPG123_INCLUDE_DIR", "/usr/include"))
        if not (header / "mpg123.h").exists():
            pytest.skip("host libmpg123 and headers required for real MP3 integration")
        try:
            ctypes.CDLL("libmpg123.so.0")
        except OSError:
            pytest.skip("host libmpg123.so.0 required for real MP3 integration")
        command += ["-I", str(header), str(source), "-l:libmpg123.so.0"]
    else:
        (tmp_path / "mpg123.h").write_text(MPG_STUB, encoding="utf-8")
        command += ["-I", str(tmp_path), str(source)]
    command += ["-o", str(executable)]
    built = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([str(executable)], cwd=tmp_path,
                         capture_output=True, text=True, timeout=12)
    assert ran.returncode == 0, ran.stdout + ran.stderr


def test_native_buffer_and_position_stay_unchanged_until_owner_mutes_bgm(tmp_path):
    compile_run(tmp_path, PREFIX + r'''
int main(void) {
 prime();int16_t output[4]={123,-456,321,-654}, original[4];
 memcpy(original,output,sizeof output);unsigned count=cp.count;
 custom_playlist_mix_pcm(output,2,100);
 assert(!memcmp(output,original,sizeof output)&&cp.count==count);
 custom_playlist_set_audible(1,1.0f);
 custom_playlist_mix_pcm(output,2,99); /* Regressing clock is not fresh. */
 custom_playlist_mix_pcm(output,2,1101); /* No stale menu music. */
 assert(!memcmp(output,original,sizeof output)&&cp.count==count);
 cp.pcm_lock=1;custom_playlist_mix_pcm(output,2,100);cp.pcm_lock=0;
 assert(!memcmp(output,original,sizeof output)&&cp.count==count);
 custom_playlist_publish(0,101);custom_playlist_mix_pcm(output,2,101);
 assert(!memcmp(output,original,sizeof output)&&cp.count==count);
 custom_playlist_publish(1,102);custom_playlist_set_audible(1,1.0f);
 custom_playlist_mix_pcm(output,2,102);
 assert(cp.count==count-2&&memcmp(output,original,sizeof output));
 assert(!fake_opens&&!fake_reads);return 0;
}
''')


def test_pcm_attack_gain_saturation_wrap_and_underflow(tmp_path):
    compile_run(tmp_path, PREFIX + r'''
int main(void) {
 prime();custom_playlist_set_audible(1,0.5f);
 int16_t output[CP_ATTACK_FRAMES*2]={0};
 custom_playlist_mix_pcm(output,CP_ATTACK_FRAMES,100);
 for(unsigned i=0;i<CP_ATTACK_FRAMES;++i) {
  int gain=(int)(16384u*(i+1)/CP_ATTACK_FRAMES);
  assert(output[i*2]==20000*gain/32768&&output[i*2+1]==-20000*gain/32768);
 }
 custom_playlist_set_audible(1,1.0f);
 int16_t clipping[2]={30000,-30000};custom_playlist_mix_pcm(clipping,1,100);
 assert(clipping[0]==32767&&clipping[1]==-32768);
 cp.read_at=cp.write_at=CP_RING_FRAMES-1;cp.count=0;
 const int16_t pair[4]={1234,-1234,4321,-4321};
 assert(cp_push(pair,2,1)==2);int16_t wrapped[6]={0,0,0,0,88,-88};
 custom_playlist_mix_pcm(wrapped,3,100);
 assert(!memcmp(wrapped,pair,sizeof pair)&&wrapped[4]==88&&wrapped[5]==-88);
 assert(cp.read_at==1&&cp.count==0);return 0;
}
''')


def test_disable_and_new_generation_reject_previous_pcm(tmp_path):
    compile_run(tmp_path, PREFIX + r'''
int main(void) {
 assert(!custom_playlist_enabled());prime();custom_playlist_set_audible(1,1.0f);
 unsigned generation=custom_playlist_revision();assert(custom_playlist_enabled());
 custom_playlist_enable(1);assert(custom_playlist_revision()==generation);
 custom_playlist_enable(0);assert(!custom_playlist_ready()&&!cp.audible);
 assert(!custom_playlist_enabled()&&custom_playlist_revision()!=generation);
 custom_playlist_enable(1);assert(!custom_playlist_ready()&&custom_playlist_enabled());
 int16_t sample[2]={77,-88},old[2]={1000,-1000};
 custom_playlist_set_audible(1,1.0f);custom_playlist_mix_pcm(sample,1,100);
 assert(sample[0]==77&&sample[1]==-88);
 assert(cp_push(old,1,generation)==0);
 assert(cp_reset_ring(cp.generation));assert(!cp.count&&!custom_playlist_ready());
 assert(cp_push(old,1,cp.generation)==1);assert(!custom_playlist_ready());
 return 0;
}
''')


def test_directory_scan_is_top_level_sorted_case_insensitive_and_bounded(tmp_path):
    playlist = tmp_path / "playlist"
    playlist.mkdir()
    for number in reversed(range(140)):
        (playlist / f"{number:03d}.MP3").write_bytes(b"synthetic test transport")
    (playlist / "000.wav").write_bytes(b"not MP3")
    (playlist / ".hidden.mp3").write_bytes(b"not shown")
    (playlist / "000-empty.mp3").touch()
    (playlist / "000-directory.mp3").mkdir()
    compile_run(tmp_path, r'''
#include <assert.h>
#include "custom_playlist.c"
int main(void) {
 strcpy(cp.directory,"playlist");char names[CP_MAX_TRACKS][CP_NAME_BYTES];
 assert(cp_scan(names)==128);
 for(unsigned i=0;i<128;++i){char expected[32];snprintf(expected,sizeof expected,"%03u.MP3",i);assert(!strcmp(names[i],expected));}
 assert(!cp_mp3_name("mp3")&&!cp_mp3_name("a.mp3.bak")&&cp_mp3_name("A.mP3"));
 return 0;
}
''')


def test_worker_invalid_formats_empty_directory_and_all_bad_stop_retrying(tmp_path):
    (tmp_path / "bad").mkdir()
    (tmp_path / "bad/01-bad.mp3").write_bytes(b"invalid MP3")
    (tmp_path / "bad/02-wrong.mp3").write_bytes(b"decoder format rejected")
    compile_run(tmp_path, r'''
#include <assert.h>
#include "custom_playlist.c"
int main(void) {
 assert(custom_playlist_init("does-not-exist",1));custom_playlist_publish(1,100);
 cp_wait(100);assert(!custom_playlist_ready());custom_playlist_shutdown();
 assert(custom_playlist_init("bad",1));custom_playlist_publish(1,100);
 for(unsigned i=0;i<100&&__atomic_load_n(&fake_opens,__ATOMIC_RELAXED)<2;++i)cp_wait(5);
 cp_wait(60);assert(!custom_playlist_ready());
 unsigned opens=__atomic_load_n(&fake_opens,__ATOMIC_RELAXED);assert(opens==2);
 custom_playlist_publish(1,200);cp_wait(150);
 assert(__atomic_load_n(&fake_opens,__ATOMIC_RELAXED)==opens);
 int16_t output[2]={700,-800};custom_playlist_set_audible(1,1.0f);
 custom_playlist_mix_pcm(output,1,200);assert(output[0]==700&&output[1]==-800);
 custom_playlist_shutdown();assert(!fake_live);return 0;
}
''')


def test_worker_prefills_without_consuming_and_stops_in_match(tmp_path):
    (tmp_path / "playlist").mkdir()
    (tmp_path / "playlist/song.MP3").write_bytes(b"synthetic decoder transport")
    compile_run(tmp_path, r'''
#include <assert.h>
#include "custom_playlist.c"
int main(void) {
 assert(custom_playlist_init("playlist",1));custom_playlist_publish(1,100);
 for(unsigned i=0;i<100&&!custom_playlist_ready();++i)cp_wait(5);
 assert(custom_playlist_ready());custom_playlist_set_audible(1,1.0f);
 int16_t output[CP_ATTACK_FRAMES*2]={0};
 /* The callback may leave a block untouched on decoder lock contention. */
 for(unsigned i=0;i<100&&!output[CP_ATTACK_FRAMES*2-2];++i) {
  custom_playlist_mix_pcm(output,CP_ATTACK_FRAMES,100);cp_wait(1);
 }
 assert(output[CP_ATTACK_FRAMES*2-2]==1000&&output[CP_ATTACK_FRAMES*2-1]==-1000);
 custom_playlist_publish(0,101);cp_wait(60);
 unsigned reads=__atomic_load_n(&fake_reads,__ATOMIC_RELAXED);cp_wait(100);
 assert(__atomic_load_n(&fake_reads,__ATOMIC_RELAXED)==reads);
 unsigned count=__atomic_load_n(&cp.buffered_frames,__ATOMIC_ACQUIRE);
 memset(output,0,sizeof output);custom_playlist_mix_pcm(output,CP_ATTACK_FRAMES,101);
 for(unsigned i=0;i<CP_ATTACK_FRAMES*2;++i)assert(output[i]==0);
 assert(__atomic_load_n(&cp.buffered_frames,__ATOMIC_ACQUIRE)==count);
 custom_playlist_publish(1,102);assert(custom_playlist_ready());
 custom_playlist_set_audible(1,1.0f);
 for(unsigned i=0;i<100&&!output[CP_ATTACK_FRAMES*2-2];++i) {
  custom_playlist_mix_pcm(output,CP_ATTACK_FRAMES,102);cp_wait(1);
 }
 assert(output[CP_ATTACK_FRAMES*2-2]==1000);
 custom_playlist_shutdown();assert(!fake_live);return 0;
}
''')


def test_real_mp3_mono_resampling_uses_existing_stereo_output(tmp_path):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg and host libmpg123 required for generated-tone integration")
    directory = tmp_path / "playlist"
    directory.mkdir()
    generated = subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-threads", "1",
                               "-filter_threads", "1", "-f", "lavfi", "-i",
                               "sine=frequency=440:sample_rate=44100:duration=0.7",
                               "-ac", "1", "-codec:a", "libmp3lame",
                               str(directory / "tone.MP3")],
                              capture_output=True, text=True, timeout=60)
    assert generated.returncode == 0, generated.stderr
    compile_run(tmp_path, r'''
#include <assert.h>
#include "custom_playlist.c"
int main(void) {
 assert(custom_playlist_init("playlist",1));custom_playlist_publish(1,100);
 for(unsigned i=0;i<400&&!custom_playlist_ready();++i){custom_playlist_publish(1,100);cp_wait(5);}
 assert(custom_playlist_ready());custom_playlist_set_audible(1,1.0f);
 int16_t output[4800*2]={0};custom_playlist_mix_pcm(output,4800,100);
 unsigned nonzero=0;for(unsigned i=0;i<4800;++i){
  assert(output[i*2]==output[i*2+1]);if(output[i*2])++nonzero;
 }
 assert(nonzero>4000);assert(cp.count<=CP_RING_FRAMES);
 custom_playlist_publish(0,101);memset(output,0,sizeof output);
 custom_playlist_mix_pcm(output,4800,101);
 for(unsigned i=0;i<9600;++i)assert(!output[i]);
 custom_playlist_shutdown();return 0;
}
''', real=True)
