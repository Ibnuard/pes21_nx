"""Full quiet PCM recording, native WAVE decoding, and unchanged mixer route."""
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import wave

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tests")]
import stage_trophy_pcm_music as music
from stage_indonesia_commentary import Utf
from test_trophy_audio_v89 import LIBRARY_SHA
from test_trophy_audio_v89 import RUNTIME
from test_trophy_audio_v88 import compile_run


def staged():
    folder = ROOT / "local-debug/presentation-v90/music-01"
    path = folder / music.ASSET
    if not path.exists():
        pytest.skip("ignored staged v90 user PCM music required")
    blob = path.read_bytes()
    awb = Utf(blob).blob(0, "AwbFile")
    start, end = struct.unpack_from("<II", awb, 18)
    audio = awb[(start + 31) & ~31:end]
    with wave.open(io.BytesIO(audio), "rb") as recording:
        pcm = recording.readframes(recording.getnframes())
    return folder, blob, audio, pcm


def native_decode(audio):
    """All original WAVE codec bodies, no replacement codec or audio device."""
    import numpy as np
    from native_hca_probe import NativeHcaProbe
    library = ROOT / "dist/pes21_nx/libUE4.so"
    with library.open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == LIBRARY_SHA
    info = music.pcm_wave_info(audio)
    probe = NativeHcaProbe(library)
    try:
        source = probe.alloc(len(audio), audio)
        fmt, error = probe.alloc(256), probe.alloc(8)
        assert probe.call(0x7E248B0, source, len(audio), 0, 0, fmt, error) == 0
        fields = struct.unpack("<17I", probe.uc.mem_read(fmt, 68))
        assert fields[:5] == (5, 2, 44100, info["samples"], 44)
        work, pointer = probe.alloc(4096), probe.alloc(8)
        assert probe.call(0x7E249D8, fmt, work, 4096, pointer) == 0
        handle = probe.pointer(pointer)
        left, right = probe.alloc(4096), probe.alloc(4096)
        output = probe.alloc(16, struct.pack("<QQ", left, right))
        consumed, samples = probe.alloc(8), probe.alloc(8)
        count, position, chunks = 0, 0, []
        while count < info["samples"]:
            probe.write(0x1000FF000, struct.pack("<Q", samples))
            probe.write(consumed, bytes(8))
            probe.write(samples, bytes(8))
            number = min(1024, info["samples"] - count)
            assert probe.call(0x7E24A18, handle, source + position, len(audio) - position,
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
        assert position == len(audio) and len(decoded) == info["samples"]
        assert np.all(np.isfinite(decoded))
        return decoded, fields
    finally:
        probe.close()


def native_pool_selection():
    """Execute original selector against disjoint registered native pool masks."""
    from native_hca_probe import NativeHcaProbe
    import unicorn.arm64_const as regs
    probe = NativeHcaProbe(ROOT / "dist/pes21_nx/libUE4.so")
    try:
        word = (2 << 24) | 44100 | (2 << 20)
        config_input = probe.alloc(20, struct.pack("<5I", 2, 44100, 0, 2, 0))
        parsed, parsed_channels = probe.alloc(4), probe.alloc(4)
        probe.call(0x7DFDE40, config_input, parsed, parsed_channels)
        assert struct.unpack("<I", probe.uc.mem_read(parsed, 4))[0] == word
        assert struct.unpack("<I", probe.uc.mem_read(parsed_channels, 4))[0] == 2
        nodes, records = [], []
        for mask in (0x0A, 0x20):
            pool, node = probe.alloc(80), probe.alloc(16)
            player, record = probe.alloc(0x300), probe.alloc(56)
            probe.write(pool + 0x14, struct.pack("<HH", 1, 0))
            probe.write(pool + 0x18, struct.pack("<II", 0, mask))
            probe.write(pool + 0x20, struct.pack("<I", word))
            probe.write(pool + 0x28, struct.pack("<Q", record))
            probe.write(record + 8, struct.pack("<Q", player))
            probe.write(node, struct.pack("<Q", pool))
            nodes.append(node)
            records.append(record)
        probe.write(nodes[0] + 8, struct.pack("<Q", nodes[1]))
        head = probe.alloc(8, struct.pack("<Q", nodes[0]))
        probe.write(0x9565668, struct.pack("<Q", head))
        config = probe.alloc(4, struct.pack("<I", word))
        matches = {}
        for mask in (2, 8, 32):
            probe.call(0x7533B40, 0, mask, config)
            result = probe.uc.reg_read(regs.UC_ARM64_REG_X0)
            expected = records[1] if mask == 32 else records[0]
            assert result == expected
            matches[str(mask)] = "WAVE" if result == records[1] else "existing_ADX_HCA"
        return {"native_selector": "criatomplayerpool_search_free_player",
                "native_config_parser": "criAtomPlayer_ParseWavePlayerConfig",
                "parsed_native_configuration_word": f"{word:08x}",
                "identifier": 0, "request_format_mask_selection": matches,
                "existing_adx_hca_pool_unchanged": True,
                "actual_platform_voice_allocated": False}
    finally:
        probe.close()


def test_full_pcm_bank_is_quiet_before_playback_and_has_no_adx_loss():
    folder, blob, audio, pcm = staged()
    report = json.loads((folder / "AUDIO-REPORT.json").read_text())
    music.verify_bank(blob, audio)
    assert len(blob) == 2758200 < music.MAX_BANK == 4 * 1024 * 1024
    assert hashlib.sha256(blob).hexdigest() == report["bank_sha256"]
    # The historical PCM bank stays sealed after the v94 HCA runtime repair.
    assert (folder / "trophy_audio_catalog.h").read_text() == music.catalog(blob, audio)
    assert report["cue_gain_db"] == -12 and report["gain_applied_before_playback"]
    assert report["codec"] == "WAVE_PCM16" and not report["lossy_transcode"]
    assert report["codec_info"]["samples"] == 688128
    assert report["codec_info"]["channels"] == 2 and report["codec_info"]["sample_rate"] == 44100
    assert report["source_pcm_bytes"] == len(pcm) == 688128 * 4
    assert report["staged_pcm_peak"] < 0.24 and report["staged_pcm_clipped_samples"] == 0
    assert report["independent_full_pcm_roundtrip_exact"] and not report["trimmed_frames"]
    assert not report["global_gain_or_playlist_changed"] and report["mobile_acf_preserved"]
    assert Utf(blob).child("WaveformTable").rows[0]["EncodeType"] == 20


def test_quantization_is_bounded_and_never_clips_or_changes_frame_count():
    original = struct.pack("<8h", -32768, 32767, -30000, 30000, -1, 1, 0, 12345)
    transformed = music.attenuate_pcm(original)
    assert len(transformed) == len(original)
    for source, target in zip(struct.unpack("<8h", original), struct.unpack("<8h", transformed)):
        assert abs(target - source * music.GAIN) <= 0.5
        assert -32768 < target < 32767
    with pytest.raises(ValueError, match="frames"):
        music.attenuate_pcm(bytes(3))


def test_exact_audible_native_route_has_no_double_full_volume_bus_send():
    _, blob, _, _ = staged()
    result = music.routing(Utf(blob))
    assert result["category_ids"] == [355, 20]
    assert [(row["bus_name"], row["gain"]) for row in result["bus_sends"]] == [("MasterOut", 0), ("BUS8", 1)]
    assert not result["parallel_full_volume_master_and_bus8_sends"]
    audio = (ROOT / "source/fixdemo_trophy_audio.inc").read_text()
    assert "TROPHY_AUDIO_MAX_BANK_BYTES" in audio and "TROPHY_AUDIO_GAIN_DB_X100" in audio
    assert "SetCategoryVolume" not in audio and "SetGameOptionVolume" not in audio


def test_one_native_wave_pool_is_cached_and_allocation_failure_is_terminal(tmp_path):
    compile_run(tmp_path, RUNTIME + r'''
static unsigned size_calls, allocations;
static int32_t required=4096;
static unsigned fail_allocate;
static int32_t pool_size(const FixdemoWavePoolConfig *config){
  assert(sizeof(*config)==28 && !config->identifier && config->voices==1 && config->channels==2);
  assert(config->rate==44100 && !config->streaming && config->renderer==2 && !config->latency);
  ++size_calls;return required;
}
static void *pool_allocate(const FixdemoWavePoolConfig *config,void *work,int32_t bytes){
  assert(config->voices==1 && work && bytes==4096);++allocations;
  return fail_allocate ? NULL : (void*)77;
}
int main(void){
  setup();fixdemo_trophy_audio_observe(1000);
  fixdemo_audio_wave_pool_size=pool_size;fixdemo_audio_wave_pool_allocate=pool_allocate;
  assert(fixdemo_audio_ensure_wave_pool());
  assert(fixdemo_audio_wave_pool==(void*)77 && fixdemo_audio_wave_pool_work);
  for(unsigned i=0;i<10000;++i)assert(fixdemo_audio_ensure_wave_pool());
  assert(size_calls==1 && allocations==1);
  void *cached=fixdemo_audio_wave_pool_work;
  fixdemo_trophy_audio.ops=(TrophyAudioOps){fixdemo_audio_native_play,fixdemo_audio_native_stop,fixdemo_audio_note,NULL};
  assert(trophy_audio_stop(&fixdemo_trophy_audio));
  assert(fixdemo_audio_wave_pool==(void*)77 && fixdemo_audio_wave_pool_work==cached);
  /* This isolated fake pool has no native references; production never frees a registered pool. */
  free(cached);fixdemo_audio_wave_pool=fixdemo_audio_wave_pool_work=NULL;
  fixdemo_audio_wave_pool_attempted=0;fail_allocate=1;
  assert(!fixdemo_audio_ensure_wave_pool());
  for(unsigned i=0;i<1000;++i)assert(!fixdemo_audio_ensure_wave_pool());
  assert(size_calls==2 && allocations==2 && !fixdemo_audio_wave_pool_work);
  fixdemo_audio_wave_pool_attempted=0;required=1024*1024+1;
  assert(!fixdemo_audio_ensure_wave_pool());
  assert(size_calls==3 && allocations==2);
  fixdemo_audio_wave_pool_attempted=0;required=-1;
  assert(!fixdemo_audio_ensure_wave_pool());
  assert(size_calls==4 && allocations==2);
  return 0;
}
''')


def test_original_native_wave_codec_reproduces_all_pcm_samples_and_channel_order():
    staged()
    for dependency in ("unicorn", "numpy", "elftools.elf.elffile"):
        pytest.importorskip(dependency)
    if not (ROOT / "dist/pes21_nx/libUE4.so").is_file():
        pytest.skip("compatible ignored Mobile ELF required")
    env = os.environ.copy()
    env.pop("PYTHONFAULTHANDLER", None)
    result = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "--native-full"],
                            cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    proof = json.loads(result.stdout)
    assert proof["decoded_samples_per_channel"] == 688128
    assert proof["native_format"][0] == 5 and proof["pcm16_roundtrip_exact"]
    assert proof["native_max_sample_error"] == 0 and proof["native_clipped_samples"] == 0
    assert proof["native_pool_selection"]["existing_adx_hca_pool_unchanged"]


if __name__ == "__main__":
    assert sys.argv[1:] == ["--native-full"]
    import numpy as np
    folder, blob, audio, pcm = staged()
    decoded, fields = native_decode(audio)
    integers = np.frombuffer(pcm, "<i2").reshape(-1, 2)
    expected = integers.astype(np.float32) / 32768.0
    recovered = np.rint(decoded * 32768).astype("<i2").tobytes()
    assert recovered == pcm and np.array_equal(decoded, expected)
    proof = {"schema": "PESNX_TROPHY_NATIVE_WAVE_V90", "status": "native_full_pcm_exact",
             "native_library_sha256": LIBRARY_SHA, "bank_sha256": hashlib.sha256(blob).hexdigest(),
             "wave_sha256": hashlib.sha256(audio).hexdigest(), "pcm16_sha256": hashlib.sha256(pcm).hexdigest(),
             "decoded_samples_per_channel": len(decoded), "channels": 2, "sample_rate": 44100,
             "native_format": fields, "native_float_pcm_sha256": hashlib.sha256(decoded.astype("<f4").tobytes()).hexdigest(),
             "native_peak": float(np.max(np.abs(decoded))), "native_rms": float(np.sqrt(np.mean(decoded * decoded))),
             "native_rms_dbfs": float(20 * np.log10(np.sqrt(np.mean(decoded * decoded)))),
             "native_clipped_samples": int(np.count_nonzero(np.abs(decoded) >= 1)),
             "native_non_finite_samples": int(np.count_nonzero(~np.isfinite(decoded))),
             "native_max_sample_error": float(np.max(np.abs(decoded - expected))),
             "pcm16_roundtrip_exact": True, "channel_order_exact": True,
             "native_methods": ["criwavecodec_AnalyzeStreamFormat", "criwavecodec_DecoderCreate", "criwavecodec_DecodeStream"],
             "no_stub_decoder": True, "gain_db_applied_to_this_cue_only": -12,
             "native_pool_selection": native_pool_selection(),
             "global_gain_changed": False, "audio_device_executed": False, "device_v90_accepted": False}
    print(json.dumps(proof, indent=2))
