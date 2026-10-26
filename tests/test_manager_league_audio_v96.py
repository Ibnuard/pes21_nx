"""PCM provenance, native decoder/format masks, bounded6voice owner lifetime."""
from pathlib import Path
import hashlib
import io
import json
import os
import struct
import subprocess
import sys
import wave

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tests")]
import stage_manager_pcm_audio as pcm_stage
from stage_indonesia_commentary import Utf, fnv64
from stage_manager_league_audio import awb_recording, GAINS
from test_trophy_audio_v88 import compile_run

FOLDER = ROOT / "local-debug/manager-review-v96/audio/pcm-01"


def staged():
    path = FOLDER / pcm_stage.ASSET
    if not path.exists():
        pytest.skip("ignored individually reviewed Manager PCM stage required")
    return path.read_bytes(), json.loads((FOLDER / "AUDIO-REPORT.json").read_text())


def test_pcm_bank_binds_individual_semantics_and_has_no_double_gain():
    bank, report = staged()
    assert len(bank) == report["bank_bytes"] < 16 * 1024 * 1024
    assert hashlib.sha256(bank).hexdigest() == report["bank_sha256"]
    assert report["semantic_review_sha256"] == pcm_stage.REVIEW_SHA
    assert not report["device_audibility_verified"]
    assert report["no_resampling"] and report["cue_gain_baked_once"]
    top = Utf(bank)
    source_path = ROOT / "local-debug/manager-league-v94/audio/stage-02/Audio/manager-league-v94.acb"
    source = Utf(source_path.read_bytes())
    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == pcm_stage.SOURCE_SHA
    for field in ("SequenceTable", "TrackTable", "SynthTable", "TrackEventTable", "AcfMd5Hash"):
        assert top.blob(0, field) == source.blob(0, field)
    assert (FOLDER / "manager_league_audio_catalog.h").read_bytes() == (ROOT / "source/manager_league_audio_catalog.h").read_bytes()
    for i, clip in enumerate(report["clips"]):
        data = awb_recording(top.blob(0, "AwbFile"), i)
        assert hashlib.sha256(data).hexdigest() == clip["wave_sha256"]
        assert clip["gain_baked"] == GAINS.get(clip["role"], .65)
        assert clip["pcm_peak"] < .68 and clip["pcm_quantization_error_max_lsb"] <= .5
        with wave.open(io.BytesIO(data), "rb") as recording:
            assert recording.getnchannels() == 2 and recording.getsampwidth() == 2
            assert recording.getframerate() == 48000 and recording.getnframes() == clip["samples"]
            assert hashlib.sha256(recording.readframes(clip["samples"])).hexdigest() == clip["pcm_sha256"]
        fmt = top.child("WaveformTable").rows[i]
        assert fmt["EncodeType"] == 20 and fmt["NumChannels"] == 2 and fmt["SamplingRate"] == 48000
        assert fmt["NumSamples"] == clip["samples"] and fmt["LoopFlag"] == 1 and fmt["ExtensionData"] == 65535
        assert top.child("SeqCommandTable").blob(i, "Command") == struct.pack(">HBfHBHHHBHH", 0x44, 4, 1., 0x6f, 4, 1, 0, 0x6f, 4, 2, 10000)
    assert len(report["clips"]) == 13


POOL_HARNESS = r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
typedef struct {uint8_t *load_base;} so_module;
static uintptr_t so_try_find_addr_rx(so_module *m,const char *n){(void)m;(void)n;return 0;}
static uintptr_t so_find_addr(so_module *m,const char *n){(void)m;(void)n;return 0;}
static void scene_runtime_note(const char *a,const char *b){(void)a;(void)b;}
static void *nx_asset_read(const char *n,uint32_t max,size_t *size){(void)n;(void)max;(void)size;return NULL;}
#include "manager_league_audio_runtime.inc"
static unsigned size_calls, allocations, fail_allocate;
static int32_t required=4096;
static int32_t size_stub(const MlaWavePoolConfig *c){
 assert(sizeof(*c)==28&&!c->identifier&&c->voices==6&&c->channels==2&&c->rate==48000);
 assert(!c->streaming&&c->renderer==2&&!c->latency);++size_calls;return required;}
static void *allocate_stub(const MlaWavePoolConfig *c,void *work,int32_t size){
 assert(c->voices==6&&work&&size==required);++allocations;return fail_allocate?NULL:(void*)77;}
'''


def test_pool_is_cached_allocation_failure_is_terminal_and_worksize_bounded(tmp_path):
    compile_run(tmp_path, POOL_HARNESS + r'''
int main(void){
 (void)manager_league_audio_native_install;(void)manager_league_audio_native_pump;
 (void)manager_league_audio_plain_hca_header;
 mla_wave_pool_size=size_stub;mla_wave_pool_allocate=allocate_stub;
 assert(mla_ensure_wave_pool()&&mla_wave_pool==(void*)77&&mla_wave_pool_work);
 for(unsigned i=0;i<10000;++i)assert(mla_ensure_wave_pool());
 assert(size_calls==1&&allocations==1);free(mla_wave_pool_work);
 mla_wave_pool=mla_wave_pool_work=NULL;mla_wave_pool_attempted=0;fail_allocate=1;
 assert(!mla_ensure_wave_pool()&&!mla_wave_pool_work);
 for(unsigned i=0;i<10000;++i)assert(!mla_ensure_wave_pool());
 assert(size_calls==2&&allocations==2);
 mla_wave_pool_attempted=0;required=2*1024*1024+1;assert(!mla_ensure_wave_pool());
 mla_wave_pool_attempted=0;required=-1;assert(!mla_ensure_wave_pool());
 assert(size_calls==4&&allocations==2);return 0;}
''')


def test_observation_covers_short_contact_before_expected_end_and_finite_bed_cycle(tmp_path):
    compile_run(tmp_path, POOL_HARNESS + r'''
static uint64_t serial;
static unsigned plays[MLA_CLIP_COUNT],status_reads;
static int play(void *c,uint32_t clip,uint64_t *h){(void)c;++plays[clip];*h=++serial;return 0;}
static int stop(void *c,uint64_t h,uint32_t f){(void)c;assert(h&&f==100);return 0;}
static int32_t status(uint64_t h,uint32_t *s){assert(h);*s=1u<<20;++status_reads;return 0;}
static int32_t position(uint64_t h,int64_t *p){assert(h);*p=20;return 0;}
int main(void){
 (void)manager_league_audio_native_install;(void)manager_league_audio_plain_hca_header;
 (void)size_stub;(void)allocate_stub;
 mla_ready=1;mla_native_status=status;mla_native_position=position;
 mla_policy.ops=(ManagerLeagueAudioOps){play,stop,mla_clip_duration,NULL};
 ManagerLeagueAudioFrame f={.fixture_token=7,.visible_watch=1,.monotonic_ms=1000};
 manager_league_audio_publish(&f);manager_league_audio_native_pump(1000);
 assert(mla_policy.bed.until_ms==22000&&plays[MLA_BED]==1);
 /* Continuous ticks preserve a finite21sec bed instead of silently ending. */
 for(unsigned t=2000;t<=22000;t+=1000){f.monotonic_ms=t;f.position_ms=t-1000;
 manager_league_audio_publish(&f);manager_league_audio_native_pump(t);}
 assert(plays[MLA_BED]==2&&mla_policy.bed.until_ms==43000);
 mla_watch[2].handle=99;mla_watch[2].started=22000;mla_watch[2].clip=MLA_BALL_PASS;mla_watch[2].samples=0;
 manager_league_audio_native_pump(22000);assert(status_reads==1);
 manager_league_audio_native_pump(22019);assert(status_reads==1);
 manager_league_audio_native_pump(22020);assert(status_reads==2);
 manager_league_audio_native_pump(22100);assert(status_reads==3);
 manager_league_audio_native_pump(23000);assert(status_reads==3);
 return 0;}
''')


def native_full_proof():
    """Run all original native WAVE decoders, not a host substitute or device."""
    import numpy as np
    from native_hca_probe import NativeHcaProbe
    from test_manager_league_audio_v94 import LIBRARY_SHA
    import unicorn.arm64_const as regs
    bank, report = staged()
    library = ROOT / "dist/pes21_nx/libUE4.so"
    with library.open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == LIBRARY_SHA

    class WaveProbe(NativeHcaProbe):
        def alloc(self, length, data=None):
            address = self.heap
            self.heap += (length + 31) & ~31
            assert self.heap < 0x101400000
            if data:
                self.uc.mem_write(address, data)
            return address

    decoded_clips = []
    top = Utf(bank)
    for i, clip in enumerate(report["clips"]):
        audio = awb_recording(top.blob(0, "AwbFile"), i)
        probe = WaveProbe(library)
        probe.uc.mem_map(0x100400000, 0x1000000)
        try:
            source = probe.alloc(len(audio), audio)
            fmt, error = probe.alloc(256), probe.alloc(8)
            assert probe.call(0x7e248b0, source, len(audio), 0, 0, fmt, error) == 0
            fields = struct.unpack("<17I", probe.uc.mem_read(fmt, 68))
            assert fields[:5] == (5, 2, 48000, clip["samples"], 44)
            work, pointer = probe.alloc(4096), probe.alloc(8)
            assert probe.call(0x7e249d8, fmt, work, 4096, pointer) == 0
            handle = probe.pointer(pointer)
            left, right = probe.alloc(4096), probe.alloc(4096)
            output = probe.alloc(16, struct.pack("<QQ", left, right))
            consumed, samples = probe.alloc(8), probe.alloc(8)
            count = position = 0
            chunks = []
            while count < clip["samples"]:
                probe.write(0x1000ff000, struct.pack("<Q", samples))
                probe.write(consumed, bytes(8)); probe.write(samples, bytes(8))
                number = min(1024, clip["samples"] - count)
                assert probe.call(0x7e24a18, handle, source + position, len(audio) - position,
                                  0, 0, output, number, consumed) == 0
                used = struct.unpack("<I", probe.uc.mem_read(consumed, 4))[0]
                number = struct.unpack("<I", probe.uc.mem_read(samples, 4))[0]
                assert used or number
                position += used
                if number:
                    chunks.append(np.column_stack([
                        np.frombuffer(probe.uc.mem_read(left, number * 4), "<f4"),
                        np.frombuffer(probe.uc.mem_read(right, number * 4), "<f4")]))
                    count += number
            decoded = np.concatenate(chunks)
            original = audio[44:]
            assert position == len(audio) and count == clip["samples"]
            recovered = np.rint(decoded * 32768).astype("<i2").tobytes()
            assert recovered == original
            decoded_clips.append({"role": clip["role"], "samples": count,
                "native_full_pcm_sha256": hashlib.sha256(recovered).hexdigest(),
                "pcm16_roundtrip_exact": True, "channels_exact": True})
        finally:
            probe.close()
    probe = NativeHcaProbe(library)
    try:
        word = (2 << 24) | 48000 | (2 << 20)
        inp = probe.alloc(20, struct.pack("<5I", 2, 48000, 0, 2, 0))
        parsed, channels = probe.alloc(4), probe.alloc(4)
        probe.call(0x7dfde40, inp, parsed, channels)
        assert struct.unpack("<I", probe.uc.mem_read(parsed, 4))[0] == word
        assert struct.unpack("<I", probe.uc.mem_read(channels, 4))[0] == 2
        nodes, records = [], []
        for mask in (0x0a, 0x20):
            pool, node = probe.alloc(80), probe.alloc(16)
            player, record = probe.alloc(0x300), probe.alloc(56)
            probe.write(pool + 0x14, struct.pack("<HH", 1, 0))
            probe.write(pool + 0x18, struct.pack("<II", 0, mask))
            probe.write(pool + 0x20, struct.pack("<I", word))
            probe.write(pool + 0x28, struct.pack("<Q", record))
            probe.write(record + 8, struct.pack("<Q", player))
            probe.write(node, struct.pack("<Q", pool)); nodes.append(node); records.append(record)
        probe.write(nodes[0] + 8, struct.pack("<Q", nodes[1]))
        head = probe.alloc(8, struct.pack("<Q", nodes[0]))
        probe.write(0x9565668, struct.pack("<Q", head))
        config = probe.alloc(4, struct.pack("<I", word))
        for mask in (2, 8, 32):
            probe.call(0x7533b40, 0, mask, config)
            assert probe.uc.reg_read(regs.UC_ARM64_REG_X0) == records[1 if mask == 32 else 0]
    finally:
        probe.close()
    return {"native_library_sha256": LIBRARY_SHA, "bank_sha256": report["bank_sha256"],
        "decoded_clips": decoded_clips, "native_wav_format": 5, "rate": 48000,
        "native_wave_parser_and_disjoint_pool_selector_executed": True,
        "native_voice_allocation_or_audio_device_executed": False,
        "device_audibility_verified": False}


def test_full_original_native_pcm_decode_and_disjoint_pool_selection():
    staged()
    for dependency in ("unicorn", "numpy", "elftools.elf.elffile"):
        pytest.importorskip(dependency)
    if not (ROOT / "dist/pes21_nx/libUE4.so").exists():
        pytest.skip("compatible ignored native ELF required")
    env = dict(os.environ)
    env.pop("PYTHONFAULTHANDLER", None)
    ran = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "--native"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=90)
    assert not ran.returncode, ran.stdout + ran.stderr
    proof = json.loads(ran.stdout)
    assert len(proof["decoded_clips"]) == 13
    (FOLDER / "NATIVE-PCM-PROOF.json").write_text(json.dumps(proof, indent=2) + "\n")


if __name__ == "__main__":
    assert sys.argv[1:] == ["--native"]
    print(json.dumps(native_full_proof(), indent=2))
