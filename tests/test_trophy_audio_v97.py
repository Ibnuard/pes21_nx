"""A louder isolated ceremony cue, exact recording and unchanged native routing."""
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
from test_trophy_audio_v89 import LIBRARY_SHA

FOLDER = ROOT / "local-debug/manager-review-v97/trophy-audio/stage-01"


def local_bank():
    path = FOLDER / music.V97.asset
    if not path.is_file():
        pytest.skip("optional ignored v97 custom trophy bank required")
    bank = path.read_bytes()
    audio = awb_recording(Utf(bank).blob(0, "AwbFile"), 0)
    return bank, audio, json.loads((FOLDER / "AUDIO-REPORT.json").read_text())


def test_full_original_recording_is_louder_without_changing_native_route():
    bank, audio, report = local_bank()
    sealed_path = ROOT / "local-debug/match-review-v94/audio/stage-02/Audio/trophy-user-hca-v94.acb"
    if not sealed_path.is_file():
        pytest.skip("optional sealed v94 trophy bank required")
    assert bank == music.build_bank(sealed_path.read_bytes(), audio, music.V97)
    # Current production is v99; preserve the sealed v97 metadata check.
    assert (FOLDER / "trophy_audio_catalog.h").read_text() == music.catalog(bank, audio, music.V97)
    assert hashlib.sha256(bank).hexdigest() == report["bank_sha256"]
    assert report["gain_db"] == -6 and report["increase_vs_v94_db"] == 6
    assert report["original_pcm_encoded_once"] and not report["source_mutated"]
    assert not report["previous_bank_mutated"] and not report["global_gain_or_commentary_changed"]
    assert report["independent_decoded_samples"] == 688128 and report["snr_db"] > 37
    assert .46 < report["decoded_peak"] < .50 and not report["clipped_samples"]
    assert -19.8 < report["decoded_rms_dbfs"] < -19.7
    assert not report["creates_new_voice_pool"] and not report["device_accepted"]
    assert not report["resampling_or_downmixing"] and report["trimmed_frames"] == 0
    assert music.hca_info(audio)["cipher"] == 0
    assert Utf(bank).child("WaveformTable").rows[0]["EncodeType"] == 2
    assert [(row["bus_name"], row["gain"]) for row in report["native_route"]["bus_sends"]] == [
        ("MasterOut", 0), ("BUS8", 1)]
    runtime = (ROOT / "source/fixdemo_trophy_audio.inc").read_text()
    assert "TROPHY_AUDIO_GAIN_DB_X100" in runtime and "baked-once" in runtime
    assert "SetCategoryVolume" not in runtime and "SetGameOptionVolume" not in runtime
    with pytest.raises(ValueError, match="sealed v94"):
        music.build_bank(sealed_path.read_bytes() + b"x", audio, music.V97)


def test_pcm_gain_rounding_headroom_and_channel_frame_count():
    np = pytest.importorskip("numpy")
    reference = np.resize(np.array([-32768, 32767, -1, 0, 1, 12345], "<i2"), 688128 * 2)
    transformed = music.gained_pcm(reference.tobytes(), music.V97)
    result = np.frombuffer(transformed, "<i2")
    assert len(transformed) == len(reference) * 2
    assert np.max(np.abs(result.astype(float) - reference.astype(float) * music.V97.gain)) <= .5
    assert np.max(np.abs(result.astype(float))) < 16424
    with pytest.raises(ValueError, match="frame count"):
        music.gained_pcm(bytes(3))


def native_headers_and_packets(bank_reader=local_bank):
    """Execute original HCA header/packet readers, not a substitute decoder."""
    from native_hca_probe import NativeHcaProbe
    bank, audio, _ = bank_reader()
    library = ROOT / "dist/pes21_nx/libUE4.so"
    with library.open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == LIBRARY_SHA
    probe = NativeHcaProbe(library)
    try:
        work, out = probe.alloc(0x10000), probe.alloc(8)
        assert probe.call(0x74bf6a8, 2, 1, work, 0x10000, out) == 0
        decoder = probe.pointer(out)
        data = probe.alloc(len(audio), audio)
        assert probe.call(0x74bf97c, decoder, data, 96, 0, 0, out) == 0
        assert probe.call(0x74bf970, decoder, 0, 0) == 0
        info = music.hca_info(audio)
        for frame in range(info["frames"]):
            offset = 96 + frame * info["frame_bytes"]
            assert probe.call(0x74c0140, decoder, data + offset,
                              info["frame_bytes"], 0, 0, out) == 0
            packet = probe.pointer(decoder + 0xe8)
            assert bytes(probe.uc.mem_read(packet, info["frame_bytes"])) == audio[
                offset:offset + info["frame_bytes"]]
        return dict(native_library_sha256=LIBRARY_SHA,
            bank_sha256=hashlib.sha256(bank).hexdigest(), native_header_accepted=True,
            unaltered_packets=info["frames"],
            native_pcm_synthesis_executed=False, mixer_or_audio_device_executed=False)
    finally:
        probe.close()


def test_original_native_accepts_header_and_all_plaintext_packets():
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
    (FOLDER / "NATIVE-PROOF.json").write_text(json.dumps(proof, indent=2) + "\n")


if __name__ == "__main__":
    assert sys.argv[1:] == ["--native"]
    print(json.dumps(native_headers_and_packets()))
