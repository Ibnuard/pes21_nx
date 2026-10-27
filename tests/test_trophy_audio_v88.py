"""Bounded native music ownership and exact locally supplied FL26 provenance."""
from pathlib import Path
import hashlib
import importlib.util
import re
import shutil
import struct
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from stage_indonesia_commentary import Utf
import stage_trophy_music as music


def compile_run(tmp_path, body):
    compiler = shutil.which("gcc") or shutil.which("clang")
    if not compiler:
        pytest.skip("host C compiler required")
    source, exe = tmp_path / "audio.c", tmp_path / "audio.exe"
    source.write_text(body, encoding="utf-8")
    built = subprocess.run([compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                            "-I", (ROOT / "source").as_posix(),
                            "-I", (ROOT / "tests").as_posix(), source.as_posix(),
                            "-o", exe.as_posix()], capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=20, cwd=tmp_path)
    assert ran.returncode == 0, ran.stdout + ran.stderr


def test_music_is_owned_by_native_start_and_all_teardown_paths(tmp_path):
    compile_run(tmp_path, r'''
#define main original_trophy_test_main
#include "test_fixdemo_trophy_result.c"
#undef main
static unsigned audio_plays, audio_stops;
static uint64_t audio_serial;
static int audio_play(void *ctx, uint64_t *handle) {
  (void)ctx; assert(starts && fixdemo_trophy_started && !fixdemo_trophy_abort);
  assert(fixdemo_trophy_input_state()==2);
  ++audio_plays; *handle=++audio_serial; return 0;
}
static int audio_stop(void *ctx, uint64_t handle, uint32_t fade) {
  (void)ctx; assert(handle && fade==250); ++audio_stops; return 0;
}
static void start_audio_case(void) {
  reset_case(); arm_listener(); run_listener();
  unsigned before=audio_plays;
  for (int i=0;i<10;++i) run_listener();
  assert(audio_plays==before); /* No music while assets load. */
  props_state=FIXDEMO_TROPHY_PROPS_READY; run_listener();
  assert(audio_plays==before+1 && fixdemo_trophy_audio.handle);
  for (int i=0;i<10;++i) run_listener();
  assert(audio_plays==before+1);
}
int main(void) {
  configure();
  fixdemo_trophy_audio.ops=(TrophyAudioOps){audio_play,audio_stop,NULL,NULL};
  start_audio_case(); unsigned stops=audio_stops;
  fixdemo_trophy_request_skip(); assert(audio_stops==stops); /* UI only publishes. */
  run_listener(); assert(audio_stops==stops+1 && !fixdemo_trophy_audio.handle);
  run_listener(); assert(audio_stops==stops+1);
  start_audio_case(); stops=audio_stops;
  fixdemo_trophy_end(candidate_memory); assert(audio_stops==stops+1);
  run_listener(); assert(audio_stops==stops+1); /* Forget is idempotent. */
  start_audio_case(); stops=audio_stops;
  props_state=FIXDEMO_TROPHY_PROPS_FAILED; run_listener();
  assert(audio_stops==stops+1 && !fixdemo_trophy_audio.handle);
  start_audio_case(); stops=audio_stops;
  pointer(listener_memory,0x19018,ordinary); run_listener();
  assert(audio_stops==stops+1);
  start_audio_case(); stops=audio_stops;
  fixdemo_trophy_end_match(); assert(audio_stops==stops+1);
  fixdemo_trophy_end_match(); assert(audio_stops==stops+1);
  reset_case(); arm_listener(); run_listener();
  props_state=FIXDEMO_TROPHY_PROPS_FAILED;
  unsigned before=audio_plays; run_listener(); assert(audio_plays==before);
  return 0;
}
''')


def test_policy_failures_do_not_duplicate_or_leak_unowned_handles(tmp_path):
    compile_run(tmp_path, r'''
#include <assert.h>
#include "trophy_audio_policy.h"
static unsigned plays,stops,play_fail,stop_fail,publish_failed_handle;
static int play(void *c,uint64_t *h) {
  (void)c; ++plays; *h=play_fail ? publish_failed_handle : plays; return play_fail;
}
static int stop(void *c,uint64_t h,uint32_t fade) {
  (void)c; assert(h && fade==250); ++stops; return stop_fail;
}
int main(void) {
  TrophyAudioState s={0};
  assert(!trophy_audio_start(&s,0) && !trophy_audio_start(&s,1));
  s.ops=(TrophyAudioOps){play,stop,0,0};
  assert(trophy_audio_start(&s,1));
  for(int i=0;i<100;++i)assert(!trophy_audio_start(&s,1));
  assert(plays==1 && !stops);
  assert(trophy_audio_stop(&s) && trophy_audio_stop(&s) && stops==1);
  assert(!trophy_audio_start(&s,1)); /* Same-token End cannot restart. */
  play_fail=1; assert(!trophy_audio_start(&s,2));
  assert(!trophy_audio_start(&s,2) && plays==2 && stops==1);
  publish_failed_handle=77;assert(!trophy_audio_start(&s,3));assert(stops==2 && !s.handle);
  play_fail=0;assert(trophy_audio_start(&s,4));stop_fail=1;
  assert(!trophy_audio_stop(&s));assert(s.handle && s.failed_stop);
  assert(!trophy_audio_start(&s,5) && plays==4 && stops==3);
  assert(!trophy_audio_stop(&s) && stops==3); /* Deterministic stop failure is terminal. */
  return 0;
}
''')


def test_runtime_absent_or_corrupt_bank_never_calls_native_mount(tmp_path):
    compile_run(tmp_path, r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include "trophy_audio_policy.h"
typedef struct { void *load_base; } so_module;
static TrophyAudioState fixdemo_trophy_audio;
static int fixdemo_trophy_result_prepared;
static const char *fixdemo_trophy_verified_elf_sha256="";
static unsigned reads,mounts,plays,corrupt;
static uintptr_t so_try_find_addr_rx(so_module *m,const char *s) {(void)m;(void)s;return 0;}
static uintptr_t so_find_addr(so_module *m,const char *s) {(void)m;(void)s;return 0;}
static void fixdemo_trophy_note(const char *s) {assert(s && *s);}
static void *nx_asset_read_production(const char *p,size_t limit,size_t *bytes) {
  assert(!strcmp(p,TROPHY_AUDIO_ASSET) && limit==TROPHY_AUDIO_MAX_BANK_BYTES);++reads;
  *bytes=0;if(!corrupt)return NULL;
  *bytes=TROPHY_AUDIO_BYTES;return calloc(1,*bytes);
}
#include "fixdemo_trophy_audio.inc"
static int32_t mount(void *b,uint32_t n,void *binder,const char *awb,int16_t *id) {
  (void)b;(void)n;(void)binder;(void)awb;(void)id;++mounts;return 0;
}
static int32_t play(const char *n,uint64_t *h,int32_t f,int32_t a) {
  (void)n;(void)h;(void)f;(void)a;++plays;return 0;
}
static int32_t exists(const char *n) {(void)n;return 1;}
int main(void) {
  fixdemo_trophy_audio_install(NULL);
  fixdemo_trophy_audio_observe(1000);
  fixdemo_audio_mount=mount;fixdemo_audio_play=play;fixdemo_audio_existing=exists;
  fixdemo_trophy_audio.ops=(TrophyAudioOps){fixdemo_audio_native_play,
      fixdemo_audio_native_stop,fixdemo_audio_note,NULL};
  assert(!trophy_audio_start(&fixdemo_trophy_audio,1));
  assert(reads==1 && !mounts && !plays && !fixdemo_trophy_audio.handle);
  assert(!trophy_audio_start(&fixdemo_trophy_audio,1) && reads==1);
  assert(trophy_audio_stop(&fixdemo_trophy_audio)); /* Ordinary ceremony can finish. */
  corrupt=1;fixdemo_audio_attempted_mount=0;
  assert(!trophy_audio_start(&fixdemo_trophy_audio,2));
  assert(reads==2 && !mounts && !plays && !fixdemo_audio_bank);
  assert(!__atomic_load_n(&trophy_audio_bank_mounted,__ATOMIC_ACQUIRE));
  assert(trophy_audio_stop(&fixdemo_trophy_audio));
  return 0;
}
''')


def local_bank():
    path = ROOT / "local-debug/trophy-material-v88/music-01/Audio/trophy-fl26-v88.acb"
    if not path.is_file():
        pytest.skip("ignored staged FL26 trophy music bank required")
    blob = path.read_bytes()
    awb = Utf(blob).blob(0, "AwbFile")
    start, end = struct.unpack_from("<II", awb, 18)
    return blob, awb[(start + 31) & ~31:end]


def test_staged_bank_graph_exact_payload_loop_and_catalog():
    blob, audio = local_bank()
    music.verify_bank(blob, audio)
    assert len(blob) == 1588072
    assert hashlib.sha256(blob).hexdigest() == "a1901ec2bea1878751d21eaceaf4b4136f2ecbd0f3974f7b73ff3728a0976403"
    assert hashlib.sha256(audio).hexdigest() == music.WAVE_SHA
    # The historical FL bank stays sealed after the user chose a custom v89 cue.
    sealed = ROOT / "local-debug/trophy-material-v88/music-01/trophy_audio_catalog.h"
    assert sealed.read_text() == music.catalog(blob, audio)


def owned_hca_header():
    from stage_manager_league_audio import awb_recording
    path = ROOT / 'local-debug/match-review-v94/audio/stage-02/Audio/trophy-user-hca-v94.acb'
    if not path.is_file():
        pytest.skip('ignored staged current user HCA bank required')
    audio = awb_recording(Utf(path.read_bytes()).blob(0, 'AwbFile'), 0)
    return audio[:int.from_bytes(audio[6:8], 'big')]


def test_plaintext_decoder_admission_is_full_header_exact_and_owned(tmp_path):
    header = ",".join(str(b) for b in owned_hca_header())
    compile_run(tmp_path, r'''
#include <assert.h>
#include "trophy_audio_policy.h"
int main(void) {
  unsigned char h[TROPHY_AUDIO_HEADER_BYTES]={''' + header + r'''};
  assert(!trophy_audio_plain_hca_header(h,sizeof(h),NULL,0));
  __atomic_store_n(&trophy_audio_bank_mounted,1,__ATOMIC_RELEASE);
  for(unsigned split=0;split<=sizeof(h);++split)
#if TROPHY_AUDIO_ENCODE_TYPE == 2u
    assert(trophy_audio_plain_hca_header(h,split,h+split,sizeof(h)-split));
#else
    assert(!trophy_audio_plain_hca_header(h,split,h+split,sizeof(h)-split));
#endif
  assert(!trophy_audio_plain_hca_header(NULL,260,NULL,0));
  assert(!trophy_audio_plain_hca_header(h,-1,h,260));
  assert(!trophy_audio_plain_hca_header(h,sizeof(h)-1,NULL,0));
  for(unsigned i=0;i<sizeof(h);++i) {
    h[i]^=1;assert(!trophy_audio_plain_hca_header(h,sizeof(h),NULL,0));h[i]^=1;
  }
  __atomic_store_n(&trophy_audio_bank_mounted,0,__ATOMIC_RELEASE);
  assert(!trophy_audio_plain_hca_header(h,sizeof(h),NULL,0));
  return 0;
}
''')


def test_actual_decoder_wrapper_preserves_other_voices(tmp_path):
    from test_player_commentary_runtime import compile_run as run_wrapper
    header = ','.join(str(b) for b in owned_hca_header())
    run_wrapper(tmp_path, r'''
static unsigned calls, clears;
static int32_t decode(void *decoder,const void *a,int64_t n,const void *b,
    int64_t m,int64_t *used) {
  (void)decoder;(void)a;(void)n;(void)b;(void)m;++calls;*used=17;return 23;
}
static int32_t clear(void *d,const void *table,int64_t n) {
  assert(d==(void*)1 && !table && !n);++clears;return 0;
}
int main(void) {
  (void)pes_sound_team_name_label;(void)pes_sound_mount_data;(void)pes_sound_unmount_data;
  unsigned char h[TROPHY_AUDIO_HEADER_BYTES]={''' + header + r'''};
  sound_hca_decode_header_original=decode;sound_hca_set_decryption_table=clear;
  int64_t used=0;
  assert(pes_sound_decode_hca_header((void*)1,h,sizeof(h),NULL,0,&used)==23);
  assert(calls==1 && !clears && used==17); /* Bank not owned. */
  __atomic_store_n(&trophy_audio_bank_mounted,1,__ATOMIC_RELEASE);
  for(unsigned split=0;split<=sizeof(h);++split) {
    unsigned before=calls;
    assert(pes_sound_decode_hca_header((void*)1,h,split,h+split,sizeof(h)-split,&used)==23);
#if TROPHY_AUDIO_ENCODE_TYPE == 2u
    assert(calls==before+1 && clears==split+1 && used==17);
#else
    assert(calls==before+1 && !clears && used==17);
#endif
  }
  unsigned before=clears;
  h[sizeof(h)-1]^=1;
  assert(pes_sound_decode_hca_header((void*)1,h,sizeof(h),NULL,0,&used)==23);
  assert(clears==before); /* Different voice retains native cipher. */
  return 0;
}
''', wrappers=True)


def test_original_native_audio_abi_and_no_global_playlist_writes():
    path = ROOT / "dist/pes21_nx/libUE4.so"
    if not path.is_file():
        pytest.skip("compatible ignored Mobile ELF required")
    ELFFile = pytest.importorskip("elftools.elf.elffile").ELFFile
    text = (ROOT / "source/fixdemo_trophy_audio.inc").read_text()
    checks = re.findall(r'\{"([^\"]+)", (0x[0-9a-f]+), (0x[0-9a-f]+), UINT64_C\((0x[0-9a-f]+)\)\}', text)
    assert len(checks) == 9
    with path.open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == "a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187"
        stream.seek(0)
        elf = ELFFile(stream)
        table = elf.get_section_by_name(".dynsym")
        strings = table.stringtable.data()
        symbols = {}
        for row in struct.iter_unpack("<IBBHQQ", table.data()):
            name = strings[row[0]:strings.find(b"\0", row[0])].decode(errors="replace")
            if row[3] and row[4]:
                symbols[name] = row[4:6]
        for name, address, size, expected in checks:
            address, size = int(address, 16), int(size, 16)
            assert symbols[name] == (address, size)
            stream.seek(next(elf.address_offsets(address, size)))
            data = stream.read(size)
            from stage_indonesia_commentary import fnv64
            assert fnv64(data) == int(expected, 16)
    assert "MusicManager10SetEventId" not in text
    assert "SetCategoryVolume" not in text and "StopAll" not in text
    assert "so_try_find_addr_rx" in text and "module->load_base" in text
