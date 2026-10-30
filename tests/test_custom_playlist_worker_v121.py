"""Bounded decoder scheduling under cold prefill and a missing output owner."""
import pytest
import test_custom_playlist_v120 as playlist


def test_worker_prefill_yields_and_full_ring_stops_decoder(tmp_path, monkeypatch):
    directory = tmp_path / "playlist"
    directory.mkdir()
    (directory / "tone.mp3").write_bytes(b"project-authored decoder transport")
    monkeypatch.setattr(playlist, "MPG_STUB", playlist.MPG_STUB.replace(
        "__atomic_add_fetch(&fake_reads,1u,__ATOMIC_RELAXED);*done=0;",
        "observe_decode();__atomic_add_fetch(&fake_reads,1u,__ATOMIC_RELAXED);*done=0;"))
    playlist.compile_run(tmp_path, r'''
#include <assert.h>
#include <stdio.h>
#include <time.h>
static unsigned current_burst, maximum_burst, sleeps;
static void observe_decode(void) {
 unsigned burst=__atomic_add_fetch(&current_burst,1u,__ATOMIC_RELAXED);
 if(burst>__atomic_load_n(&maximum_burst,__ATOMIC_RELAXED))
  __atomic_store_n(&maximum_burst,burst,__ATOMIC_RELAXED);
}
static int observed_sleep(const struct timespec *request,struct timespec *remaining) {
 __atomic_store_n(&current_burst,0u,__ATOMIC_RELAXED);
 __atomic_add_fetch(&sleeps,1u,__ATOMIC_RELAXED);
 return nanosleep(request,remaining);
}
#define nanosleep observed_sleep
#include "custom_playlist.c"
#undef nanosleep
static void wait_test(void) {struct timespec delay={0,5000000};nanosleep(&delay,NULL);}
int main(void) {
 assert(custom_playlist_init("playlist",1));
 for(unsigned i=0;i<400;++i) {
  custom_playlist_publish(1,100);
  if(__atomic_load_n(&cp.buffered_frames,__ATOMIC_ACQUIRE)>=CP_RING_FRAMES-CP_CHUNK_FRAMES)break;
  wait_test();
 }
 assert(custom_playlist_ready());
 assert(__atomic_load_n(&cp.buffered_frames,__ATOMIC_ACQUIRE)>=CP_RING_FRAMES-CP_CHUNK_FRAMES);
 unsigned before=__atomic_load_n(&fake_reads,__ATOMIC_RELAXED);
 unsigned before_sleeps=__atomic_load_n(&sleeps,__ATOMIC_RELAXED);
 uint64_t started_wait=cp_now_ms();
 for(unsigned i=0;i<20;++i)wait_test();
 assert(__atomic_load_n(&fake_reads,__ATOMIC_RELAXED)==before);
 unsigned waits=__atomic_load_n(&sleeps,__ATOMIC_RELAXED)-before_sleeps;
 assert(waits>0&&waits<=(cp_now_ms()-started_wait)/5u+5u); /* Full ring waits, never busy-spins. */
 custom_playlist_shutdown();
 fprintf(stderr,"decode_burst=%u full_ring_waits=%u reads=%u\n",maximum_burst,waits,before);
 assert(maximum_burst<=2); /* Do not decode two seconds in one CPU burst. */
 assert(!fake_live);return 0;
}
''')


@pytest.mark.parametrize("result,read_limit", [("MPG123_NEW_FORMAT", 9), ("MPG123_OK", 9), ("-10", 1)])
def test_zero_progress_decoder_responses_stop_without_retry_loop(tmp_path, monkeypatch, result, read_limit):
    directory = tmp_path / "playlist"
    directory.mkdir()
    (directory / "tone.mp3").write_bytes(b"project-authored no-progress transport")
    monkeypatch.setattr(playlist, "MPG_STUB", playlist.MPG_STUB.replace(
        "__atomic_add_fetch(&fake_reads,1u,__ATOMIC_RELAXED);*done=0;",
        "__atomic_add_fetch(&fake_reads,1u,__ATOMIC_RELAXED);*done=0;return " + result + ";"))
    playlist.compile_run(tmp_path, "#define EXPECTED_READS " + str(read_limit) + r'''
#include <assert.h>
#include "custom_playlist.c"
int main(void) {
 assert(custom_playlist_init("playlist",1));custom_playlist_publish(1,100);
 for(unsigned i=0;i<200&&__atomic_load_n(&fake_reads,__ATOMIC_RELAXED)<EXPECTED_READS;++i)cp_wait(5);
 cp_wait(60);assert(!custom_playlist_ready());
 assert(__atomic_load_n(&fake_reads,__ATOMIC_RELAXED)==EXPECTED_READS);
 assert(__atomic_load_n(&fake_opens,__ATOMIC_RELAXED)==1);
 cp_wait(100);
 assert(__atomic_load_n(&fake_reads,__ATOMIC_RELAXED)==EXPECTED_READS);
 assert(__atomic_load_n(&fake_opens,__ATOMIC_RELAXED)==1);
 custom_playlist_shutdown();assert(!fake_live);return 0;
}
''')
