"""Custom recording integrity, original native ADX decode, and mixer ownership."""
from pathlib import Path
import hashlib
import json
import os
import struct
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tests")]
import stage_custom_trophy_music as music
from stage_indonesia_commentary import Utf
from test_trophy_audio_v88 import compile_run

LIBRARY_SHA = "a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187"


def local_audio():
    folder = ROOT / "local-debug/trophy-presentation-v89/music-02"
    bank = folder / music.ASSET
    if not bank.is_file():
        pytest.skip("ignored staged user trophy recording required")
    blob = bank.read_bytes()
    awb = Utf(blob).blob(0, "AwbFile")
    start, end = struct.unpack_from("<II", awb, 18)
    return folder, blob, awb[(start + 31) & ~31:end]


def native_pcm(audio, sample_limit=46080):
    """Run original native codec functions; no stub decoder or audio device."""
    np = pytest.importorskip("numpy")
    pytest.importorskip("unicorn")
    from native_hca_probe import NativeHcaProbe
    library = ROOT / "dist/pes21_nx/libUE4.so"
    if not library.is_file():
        pytest.skip("compatible ignored Mobile ELF required")
    with library.open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == LIBRARY_SHA
    info = music.adx_info(audio)
    probe = NativeHcaProbe(library)
    try:
        data = probe.alloc(len(audio), audio)
        header = probe.alloc(256)
        assert probe.call(0x74BAE28, data, len(audio), header) == info["header_bytes"]
        fmt, error = probe.alloc(256), probe.alloc(8)
        assert probe.call(0x7DF829C, data, len(audio), 0, 0, fmt, error) == 0
        fields = struct.unpack("<17I", probe.uc.mem_read(fmt, 68))
        assert fields[:5] == (1, info["channels"], info["sample_rate"],
                              info["samples"], info["header_bytes"])
        work, handle_ptr = probe.alloc(4096), probe.alloc(8)
        assert probe.call(0x7DF8420, fmt, work, 4096, handle_ptr) == 0
        handle = probe.pointer(handle_ptr)
        left, right = probe.alloc(4096), probe.alloc(4096)
        output = probe.alloc(16, struct.pack("<QQ", left, right))
        consumed, samples = probe.alloc(8), probe.alloc(8)
        target = min(sample_limit, info["samples"]) if sample_limit else info["samples"]
        position, count, chunks = 0, 0, []
        while count < target:
            # The ninth AArch64 argument lives on the caller stack, not X8.
            probe.write(0x1000FF000, struct.pack("<Q", samples))
            probe.write(consumed, bytes(8))
            probe.write(samples, bytes(8))
            request = min(1024, target - count)
            assert probe.call(0x7DF84AC, handle, data + position, len(audio) - position,
                              0, 0, output, request, consumed) == 0
            used = struct.unpack("<I", probe.uc.mem_read(consumed, 4))[0]
            number = struct.unpack("<I", probe.uc.mem_read(samples, 4))[0]
            assert used or number
            position += used
            if number:
                assert number <= request
                chunks.append(np.column_stack([
                    np.frombuffer(probe.uc.mem_read(left, number * 4), "<f4"),
                    np.frombuffer(probe.uc.mem_read(right, number * 4), "<f4")]))
                count += number
        result = np.concatenate(chunks)
        assert np.all(np.isfinite(result))
        assert float(np.max(np.abs(result))) > 0.1
        assert float(np.sqrt(np.mean(result * result))) > 0.01
        return result, fields
    finally:
        probe.close()


def test_custom_graph_catalog_and_full_supplied_recording():
    folder, blob, audio = local_audio()
    report = json.loads((folder / "AUDIO-REPORT.json").read_text())
    music.verify_bank(blob, audio)
    assert len(blob) == 779816
    assert hashlib.sha256(blob).hexdigest() == report["bank_sha256"]
    assert report["source_sha256"] == "3655a2a1fbb297efb34d4629547e3943326c5ed5e1ee23ab8f88cbb02d6603ff"
    assert report["codec_info"]["samples"] == 688128
    assert report["codec_info"]["channels"] == 2
    assert report["codec_info"]["sample_rate"] == 44100
    assert report["pcm_s16le_bytes"] == 688128 * 2 * 2
    assert report["removed_audio_frames"] == 0 and not report["loop"]
    assert report["source_pcm_s16le_bytes"] == report["pcm_s16le_bytes"]
    assert report["native_music_routing_preserved"]
    assert Utf(blob).child("SequenceTable").rows[0]["CommandIndex"] == 5
    assert hashlib.sha256(Utf(blob).child("SeqCommandTable").blob(5, "Command")).hexdigest() == music.NATIVE_COMMAND_SHA
    original = Path(report["source_path"])
    if original.exists():
        assert hashlib.sha256(original.read_bytes()).hexdigest() == report["source_sha256"]
    assert (folder / "trophy_audio_catalog.h").read_text() == music.catalog(blob, audio)
    assert music.adx_info(audio)["cipher"] == 0
    with pytest.raises(ValueError, match="declared frames"):
        music.adx_info(audio + bytes(18))
    body, footer = music.remove_partial_footer(audio + bytes.fromhex(report["removed_terminal_footer_hex"]))
    assert body == audio and len(footer) == 18
    with pytest.raises(ValueError, match="terminal"):
        music.remove_partial_footer(audio + bytes(18))
    # Reproduce the v88 routing defect without changing the sealed fixture.
    top = Utf(blob)
    row = music.row_copy(top, 0)
    sequence = top.child("SequenceTable")
    seq = music.row_copy(sequence, 0)
    seq["CommandIndex"] = 65535
    row["SequenceTable"] = music.rebuild_utf(sequence, [seq], compact_blobs=True)
    damaged = music.rebuild_utf(top, [row], compact_blobs=True)
    with pytest.raises(ValueError, match="discarded native music routing"):
        music.verify_bank(damaged, audio)


def isolated_probe(mode):
    pytest.importorskip("unicorn")
    pytest.importorskip("elftools.elf.elffile")
    if not (ROOT / "dist/pes21_nx/libUE4.so").is_file():
        pytest.skip("compatible ignored Mobile ELF required")
    environment = os.environ.copy()
    environment.pop("PYTHONFAULTHANDLER", None)
    result = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), mode],
                            cwd=ROOT, env=environment, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_original_native_adx_synthesizes_finite_non_silent_pcm():
    local_audio()
    report = isolated_probe("--native-pcm")
    assert report["native_format"][0] == 1 and report["decoded_samples_per_channel"] == 46080


def native_retired():
    from native_hca_probe import NativeHcaProbe
    library = ROOT / "dist/pes21_nx/libUE4.so"
    if not library.is_file():
        pytest.skip("compatible ignored Mobile ELF required")
    probe = NativeHcaProbe(library)
    try:
        registry = probe.alloc(32, b"\xff\xff" + bytes(30))
        probe.write(0x95A2910, struct.pack("<Q", registry))
        # Original CheckRequire on the tagged handle seen in the v88 device log.
        assert probe.call(0x77F22FC, 0, 0x1000001F30000, 0) == 0x80000010
    finally:
        probe.close()


def test_original_native_missing_handle_result_is_not_boolean_failure():
    assert isolated_probe("--native-retired") == {"tagged_missing_handle_result": "80000010"}


RUNTIME = r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include "trophy_audio_policy.h"
typedef struct { void *load_base; } so_module;
static TrophyAudioState fixdemo_trophy_audio;
static int fixdemo_trophy_result_prepared;
static const char *fixdemo_trophy_verified_elf_sha256="";
static uintptr_t so_try_find_addr_rx(so_module *m,const char *s){(void)m;(void)s;return 0;}
static uintptr_t so_find_addr(so_module *m,const char *s){(void)m;(void)s;return 0;}
static unsigned notes,status_calls,position_calls,gain_calls;
static void fixdemo_trophy_note(const char *s){assert(s && *s);++notes;}
static void *nx_asset_read_production(const char *p,size_t limit,size_t *bytes){(void)p;(void)limit;*bytes=0;return NULL;}
#include "fixdemo_trophy_audio.inc"
static int32_t status_result,stop_result;
static int32_t status(uint64_t handle,uint32_t *flags){assert(handle);++status_calls;*flags=1u<<20;return status_result;}
static int32_t stop(uint64_t handle,int32_t fade,int32_t mode){assert(handle && fade==250 && !mode);return stop_result;}
static int32_t position(uint64_t handle,int64_t *time){assert(handle);++position_calls;*time=1234;return 0;}
static float gain(const char *name){assert(!strcmp(name,"DefVol_Menu_Music"));++gain_calls;return 1.0f;}
static void setup(void){
  fixdemo_trophy_audio_install(NULL);
  fixdemo_audio_status=status;fixdemo_audio_stop=stop;
  fixdemo_audio_position=position;fixdemo_audio_category_volume=gain;
}
'''


def test_poll_is_bounded_and_retired_stop_releases_only_confirmed_owner(tmp_path):
    compile_run(tmp_path, RUNTIME + r'''
int main(void){
  setup();fixdemo_audio_watch_handle=17;
  unsigned times[]={1000,1099,1100,1999,2000,4999,5000,10999,11000,16999,17000};
  for(unsigned i=0;i<sizeof(times)/sizeof(times[0]);++i)fixdemo_trophy_audio_observe(times[i]);
  assert(status_calls==6 && position_calls==6 && gain_calls==6 && notes==6);
  for(unsigned i=0;i<10000;++i)fixdemo_trophy_audio_observe(17001+i);
  assert(status_calls==6 && position_calls==6 && gain_calls==6 && notes==6);
  fixdemo_trophy_audio.ops=(TrophyAudioOps){fixdemo_audio_native_play,fixdemo_audio_native_stop,fixdemo_audio_note,NULL};
  fixdemo_trophy_audio.handle=17;fixdemo_trophy_audio.playing_token=9;
  stop_result=status_result=(int32_t)FIXDEMO_AUDIO_RETIRED;
  assert(trophy_audio_stop(&fixdemo_trophy_audio));
  assert(!fixdemo_trophy_audio.handle && !fixdemo_trophy_audio.playing_token && !fixdemo_trophy_audio.failed_stop);
  fixdemo_trophy_audio.handle=18;status_result=0;
  assert(!trophy_audio_stop(&fixdemo_trophy_audio)); /* A non-retired status is not normalized. */
  assert(fixdemo_trophy_audio.handle==18 && fixdemo_trophy_audio.failed_stop);
  return 0;
}
''')


def test_observation_is_serialized_before_skip_and_never_changes_global_mix():
    owner = (ROOT / "source/fixdemo_trophy_result.inc").read_text()
    audio = (ROOT / "source/fixdemo_trophy_audio.inc").read_text()
    assert "PESNX_TROPHY_AUDIO_OBSERVE_RUNTIME" in owner
    assert "fixdemo_trophy_audio_observe(" in owner
    for forbidden in ("SetGameOptionVolume", "SetCategoryVolume", "MusicManager10SetEventId", "StopAll"):
        assert forbidden not in audio
    assert "music-native-stop result=%08x status=%08x" in audio
    assert "audible-unverified" in (ROOT / "source/trophy_audio_policy.h").read_text()


if __name__ == "__main__":
    if sys.argv[1:] == ["--native-retired"]:
        native_retired()
        print(json.dumps({"tagged_missing_handle_result": "80000010"}))
    else:
        assert sys.argv[1:] in (["--native-pcm"], ["--native-full"])
        import numpy as np
        folder, blob, audio = local_audio()
        decoded, fields = native_pcm(audio, 0 if sys.argv[1] == "--native-full" else 46080)
        ffmpeg = Path("C:/Users/Administrator/AppData/Local/Programs/Python/Python312/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe")
        result = subprocess.run([str(ffmpeg), "-v", "error", "-xerror", "-i",
                                 str(folder / "encoded.adx"), "-f", "f32le", "-"],
                                capture_output=True, timeout=30)
        assert not result.returncode
        reference = np.frombuffer(result.stdout, "<f4").reshape(-1, 2)[:len(decoded)]
        correlation = float(np.corrcoef(decoded.ravel(), reference.ravel())[0, 1])
        assert correlation > 0.999
        report = {"schema": "PESNX_TROPHY_NATIVE_ADX_V89", "status": "native_pcm_verified",
                  "native_library_sha256": LIBRARY_SHA,
                  "runtime_bank_sha256": hashlib.sha256(blob).hexdigest(),
                  "encoded_sha256": hashlib.sha256(audio).hexdigest(),
                  "native_format": fields,
                  "decoded_samples_per_channel": len(decoded), "channels": 2,
                  "native_float_pcm_sha256": hashlib.sha256(decoded.astype("<f4").tobytes()).hexdigest(),
                  "native_peak": float(np.max(np.abs(decoded))),
                  "native_rms": float(np.sqrt(np.mean(decoded * decoded))),
                  "reference_decoder_correlation": correlation,
                  "reference_max_sample_error": float(np.max(np.abs(decoded - reference))),
                  "native_methods": ["criAdxDec_DecodeHeader", "criadxcodec_AnalyzeStreamFormat",
                                     "criadxcodec_DecoderCreate", "criadxcodec_DecodeStream"],
                  "no_stub_decoder": True, "gain_changed": False,
                  "audio_device_executed": False, "device_audio_accepted": False}
        print(json.dumps(report, indent=2))
