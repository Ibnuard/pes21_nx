"""A measured +3 dB trophy recording, with sealed routes and native admission."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tests")]
import stage_trophy_gain_music as music
from stage_indonesia_commentary import Utf
from stage_manager_league_audio import awb_recording

FOLDER = ROOT / "local-debug/manager-review-v99/trophy-audio/stage-01"
SEALED = ROOT / "local-debug/manager-review-v97/trophy-audio/stage-01"


def local_bank():
    path = FOLDER / music.V99.asset
    if not path.is_file():
        pytest.skip("optional ignored v99 trophy bank required")
    bank = path.read_bytes()
    audio = awb_recording(Utf(bank).blob(0, "AwbFile"), 0)
    return bank, audio, json.loads((FOLDER / "AUDIO-REPORT.json").read_text())


def test_louder_cue_preserves_recording_native_graph_and_runtime_admission():
    bank, audio, report = local_bank()
    old = (SEALED / music.V97.asset).read_bytes()
    assert hashlib.sha256(old).hexdigest() == music.V99.base_bank_sha
    assert bank == music.build_bank(old, audio, music.V99)
    assert (FOLDER / "trophy_audio_catalog.h").read_text() == music.catalog(bank, audio, music.V99)
    assert hashlib.sha256(bank).hexdigest() == report["bank_sha256"]
    assert report["gain_db"] == -3 and report["increase_vs_v97_db"] == 3
    assert abs(report["measured_increase_db"] - 3) < .02
    assert report["original_pcm_encoded_once"] and not report["source_mutated"]
    assert not report["previous_bank_mutated"] and not report["global_gain_or_commentary_changed"]
    assert not report["creates_new_voice_pool"] and not report["device_accepted"]
    assert not report["resampling_or_downmixing"] and report["trimmed_frames"] == 0
    assert report["independent_decoded_samples"] == 688128 and report["snr_db"] > 37
    assert .65 < report["decoded_peak"] < .70 and report["decoded_peak_headroom_db"] > 3
    assert -16.8 < report["decoded_rms_dbfs"] < -16.7 and report["clipped_samples"] == 0
    assert music.hca_info(audio) == music.hca_info(awb_recording(Utf(old).blob(0, "AwbFile"), 0))
    assert [(row["bus_name"], row["gain"]) for row in report["native_route"]["bus_sends"]] == [
        ("MasterOut", 0), ("BUS8", 1)]
    runtime = (ROOT / "source/fixdemo_trophy_audio.inc").read_text()
    assert "exact-user-HCA-v100" in runtime and "TROPHY_AUDIO_GAIN_DB_X100" in runtime
    assert "SetCategoryVolume" not in runtime and "SetGameOptionVolume" not in runtime
    with pytest.raises(ValueError, match="sealed v97"):
        music.build_bank(old + b"x", audio, music.V99)


def test_full_s16_gain_rounding_preserves_channels_and_peak_headroom():
    np = pytest.importorskip("numpy")
    reference = np.resize(np.array([-32768, 32767, -1, 0, 1, 12345], "<i2"), 688128 * 2)
    result = np.frombuffer(music.gained_pcm(reference.tobytes(), music.V99), "<i2")
    assert result.shape == reference.shape
    assert np.max(np.abs(result.astype(float) - reference.astype(float) * music.V99.gain)) <= .5
    assert 23100 < np.max(np.abs(result.astype(float))) < 23200
    with pytest.raises(ValueError, match="frame count"):
        music.gained_pcm(bytes(3))


def test_independent_decode_rechecks_full_recording_and_measured_level(tmp_path):
    np = pytest.importorskip("numpy")
    imageio_ffmpeg = pytest.importorskip("imageio_ffmpeg")
    bank, audio, report = local_bank()
    previous = awb_recording(Utf((SEALED / music.V97.asset).read_bytes()).blob(0, "AwbFile"), 0)
    decoded = []
    for name, recording in (("current", audio), ("previous", previous)):
        path = tmp_path / (name + ".hca")
        path.write_bytes(recording)
        result = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-nostdin", "-v", "error",
            "-xerror", "-i", str(path), "-f", "f32le", "-"],
            check=True, capture_output=True, timeout=60)
        info = music.hca_info(recording)
        samples = np.frombuffer(result.stdout, "<f4").reshape(-1, 2)
        if len(samples) == info["frames"] * 1024:
            samples = samples[info["encoder_delay"]:info["encoder_delay"] + info["samples"]]
        assert samples.shape == (688128, 2) and np.all(np.isfinite(samples))
        assert not np.count_nonzero(np.abs(samples) >= 1)
        decoded.append(samples)
    actual_increase = 10 * np.log10(np.mean(decoded[0] ** 2) / np.mean(decoded[1] ** 2))
    assert actual_increase == pytest.approx(3, abs=.02)
    assert float(np.max(np.abs(decoded[0]))) == pytest.approx(report["decoded_peak"], abs=1e-7)
    assert hashlib.sha256(bank).hexdigest() == report["bank_sha256"]


def test_original_native_accepts_header_and_every_plaintext_packet():
    local_bank()
    for module in ("unicorn", "elftools.elf.elffile"):
        pytest.importorskip(module)
    if not (ROOT / "dist/pes21_nx/libUE4.so").is_file():
        pytest.skip("optional exact Mobile library required")
    env = dict(os.environ)
    env.pop("PYTHONFAULTHANDLER", None)
    result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--native"],
        check=True, capture_output=True, text=True, timeout=60, env=env)
    proof = json.loads(result.stdout)
    assert proof["native_header_accepted"] and proof["unaltered_packets"] == 673
    assert not proof["native_pcm_synthesis_executed"] and not proof["mixer_or_audio_device_executed"]
    (FOLDER / "NATIVE-PROOF.json").write_text(json.dumps(proof, indent=2) + "\n")


if __name__ == "__main__":
    assert sys.argv[1:] == ["--native"]
    from test_trophy_audio_v97 import native_headers_and_packets
    print(json.dumps(native_headers_and_packets(local_bank)))
