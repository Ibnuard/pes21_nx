"""Misnamed containers cannot reach MP3 decoding or native mute ownership."""
import pytest

import test_custom_playlist_v120 as playlist
from test_custom_playlist_native_v121 import run_adapter


@pytest.mark.parametrize("header", [
    b"\x00\x00\x00\x1cftypdash\x00\x00\x00\x00iso6mp41",  # AAC in MP4, named .mp3
    b"\x00\x00\x00\x1cstypiso6",
    b"\x00\x00\x00\x1cmoofdata",
    b"\x00\x00\x00\x1cmdatdata",
    b"OggS\x00\x02payload", b"fLaCpayload", b"RIFF1234WAVE",
    b"FORM1234AIFF", b"caffpayload", b"\xff\xf1\x50\x80ADTS AAC",
    b"\xff\xf9\x50\x80ADTS MPEG2 AAC",
])
def test_misnamed_container_never_decodes_or_replaces_native_pcm(tmp_path, header):
    directory = tmp_path / "playlist"
    directory.mkdir()
    (directory / "song.mp3").write_bytes(header)
    playlist.compile_run(tmp_path, r'''
#include <assert.h>
#include "custom_playlist.c"
int main(void) {
 assert(custom_playlist_init("playlist",1));custom_playlist_publish(1,100);
 for(unsigned i=0;i<100&&!custom_playlist_input_warnings();++i)cp_wait(5);
 assert(custom_playlist_input_warnings()==CUSTOM_PLAYLIST_INPUT_FORMAT);
 assert(!fake_opens&&!fake_reads&&!fake_live&&!custom_playlist_ready());
 int16_t original[4]={700,-800,123,-456},output[4];memcpy(output,original,sizeof output);
 custom_playlist_set_audible(1,1.f);custom_playlist_mix_pcm(output,2,100);
 assert(!memcmp(output,original,sizeof output));
 cp_wait(100);assert(!fake_opens&&!fake_reads);
 custom_playlist_enable(0);assert(!custom_playlist_input_warnings());
 custom_playlist_shutdown();return 0;
}
''')


def test_bad_container_is_skipped_but_real_mp3_headers_and_id3_are_admitted(tmp_path):
    directory = tmp_path / "playlist"
    directory.mkdir()
    (directory / "00-aac.mp3").write_bytes(b"\0\0\0\x18ftypdash")
    for name, data in [
        ("01-mpeg1", b"\xff\xfb\x90\x00"), ("02-mpeg2", b"\xff\xf3\x90\x00"),
        ("03-mpeg25", b"\xff\xe3\x90\x00"), ("04-id3", b"ID3\x04\x00\x00\0\0\0\0")
    ]:
        (directory / (name + ".mp3")).write_bytes(data)
    playlist.compile_run(tmp_path, r'''
#include <assert.h>
#include "custom_playlist.c"
int main(void) {
 assert(cp_input_allowed("playlist/01-mpeg1.mp3"));
 assert(cp_input_allowed("playlist/02-mpeg2.mp3"));
 assert(cp_input_allowed("playlist/03-mpeg25.mp3"));
 assert(cp_input_allowed("playlist/04-id3.mp3"));
 assert(custom_playlist_init("playlist",1));custom_playlist_publish(1,100);
 for(unsigned i=0;i<200&&!custom_playlist_ready();++i)cp_wait(5);
 assert(custom_playlist_ready()&&fake_reads&&fake_opens);
 assert(custom_playlist_input_warnings()==CUSTOM_PLAYLIST_INPUT_FORMAT);
 custom_playlist_set_audible(1,1.f);int16_t output[2048]={0};
 for(unsigned i=0;i<100&&!output[2046];++i){custom_playlist_mix_pcm(output,1024,100);cp_wait(1);}
 assert(output[2046]==1000&&output[2047]==-1000);
 custom_playlist_shutdown();assert(!fake_live);return 0;
}
''')


@pytest.mark.parametrize("with_good_track", [False, True])
def test_partial_output_before_decoder_error_does_not_retry_bad_track(tmp_path, monkeypatch, with_good_track):
    directory = tmp_path / "playlist"
    directory.mkdir()
    (directory / "00-partial.mp3").write_bytes(b"synthetic partial stream")
    if with_good_track:
        (directory / "01-good.mp3").write_bytes(b"synthetic healthy stream")
    transport = playlist.MPG_STUB.replace(
        "int format, invalid_format;", "int format, invalid_format, partial;").replace(
        "static unsigned fake_opens, fake_reads, fake_live;",
        "static unsigned fake_opens, fake_reads, fake_live, partial_opens;").replace(
        'h->invalid_format=strstr(name,"wrong")!=NULL;',
        'h->partial=strstr(name,"partial")!=NULL;if(h->partial)++partial_opens;'
        'h->invalid_format=strstr(name,"wrong")!=NULL;').replace(
        "h->at==12000?MPG123_DONE:MPG123_OK;",
        "h->at==12000?(h->partial?MPG123_ERR:MPG123_DONE):MPG123_OK;")
    monkeypatch.setattr(playlist, "MPG_STUB", transport)
    playlist.compile_run(tmp_path, "#define WITH_GOOD_TRACK " + str(int(with_good_track)) + r'''
#include <assert.h>
#include "custom_playlist.c"
int main(void) {
 assert(custom_playlist_init("playlist",1));
 unsigned mixed=0;
 for(unsigned i=0;i<200;++i) {
  custom_playlist_publish(1,100);
  if(custom_playlist_ready()) {
   custom_playlist_set_audible(1,1.f);int16_t output[4096]={0};
   custom_playlist_mix_pcm(output,2048,100);++mixed;
  }
  cp_wait(5);
 }
 custom_playlist_shutdown();assert(!fake_live&&partial_opens==1);
 assert(custom_playlist_input_warnings()&CUSTOM_PLAYLIST_INPUT_DECODE);
 if(WITH_GOOD_TRACK)assert(mixed>30&&fake_opens>5);
 else assert(fake_opens==1);
 return 0;
}
''')


def test_input_notices_do_not_mute_native_or_spam_every_pad_tick(tmp_path):
    run_adapter(tmp_path, r'''
 input_warnings=CUSTOM_PLAYLIST_INPUT_FORMAT;
 for(uint64_t t=1000;t<9000;++t)custom_playlist_native_tick(1,t);
 assert(notes==1&&!mute_calls&&!audible&&!playlist_native_failed);
 /* A good track in the same folder can play normally. */
 ready=1;custom_playlist_native_tick(1,9000);assert(audible&&muted&&notes==1);
 input_warnings|=CUSTOM_PLAYLIST_INPUT_DECODE;
 custom_playlist_native_tick(1,9001);assert(notes==2&&audible);
 for(uint64_t t=9002;t<10000;++t)custom_playlist_native_tick(1,t);
 assert(notes==2&&mute_calls==1);
 custom_playlist_native_tick(0,10000);assert(!audible&&!muted);
 ++revision;ready=0;custom_playlist_native_tick(1,10001);assert(notes==4&&!muted);
''')
