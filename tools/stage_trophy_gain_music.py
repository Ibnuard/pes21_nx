"""Stage the reviewed trophy song 3 dB above v99, with unchanged native routing.

Encode once from the exact original decoded PCM, rather than amplifying or
transcoding an earlier lossy HCA. Only a new ignored local-debug folder is
written. This tool does not install a bank or alter global mixer settings.
"""
from pathlib import Path
import argparse
from dataclasses import dataclass
import json
import subprocess
import wave

import numpy as np

from stage_indonesia_commentary import Utf, fnv64, memory_awb
from stage_manager_league_audio import awb_recording
from stage_player_commentary import rebuild_utf
from stage_trophy_hca_music import digest, hca_info, ENCODER_SHA, MAX_BANK
from stage_trophy_music import ROOT, row_copy
from stage_trophy_pcm_music import routing

@dataclass(frozen=True)
class Revision:
    version: int
    gain_db: int
    base_version: int
    base_bank_sha: str
    increase_db: int
    maximum_peak: float

    @property
    def asset(self):
        return f"Audio/trophy-user-hca-v{self.version}.acb"

    @property
    def cue(self):
        return f"FNX_TROPHY_USER_HCA_V{self.version}"

    @property
    def gain(self):
        return 10 ** (self.gain_db / 20)


# Historical recipes remain reproducible; current production selects v100.
V97 = Revision(97, -6, 94,
    "5a5a06c711b27940f8109b43cfb32c422b0b4fa5231579c10984ca09b891a506", 6, .50)
V99 = Revision(99, -3, 97,
    "634355f8955691730f5e0955f93f19f6ed1da3a7ba6adae654d80f5b056112bd", 3, .70)
V100 = Revision(100, 0, 99,
    "f83690edd7c5d2c124277051f0cdaf69a28516e2f6639557abf64fecdb429ec8", 3, .96)
CURRENT = V100
ASSET, CUE, GAIN_DB, GAIN, BASE_BANK_SHA = (
    CURRENT.asset, CURRENT.cue, CURRENT.gain_db, CURRENT.gain, CURRENT.base_bank_sha)
SOURCE_SHA = "3655a2a1fbb297efb34d4629547e3943326c5ed5e1ee23ab8f88cbb02d6603ff"
SOURCE_PCM_SHA = "2c5ed50a75c451a87a3589df05ee50ecfb55a30d2acf30adef003cccc595aed3"
NATIVE_GRAPH_FIELDS = ("CueTable", "SequenceTable", "TrackTable", "SynthTable",
                       "TrackEventTable", "SeqCommandTable", "StringValueTable",
                       "AcfMd5Hash", "WaveformTable")


def gained_pcm(original: bytes, revision: Revision = CURRENT) -> bytes:
    if len(original) != 688128 * 2 * 2:
        raise ValueError("full stereo PCM frame count differs")
    samples = np.frombuffer(original, "<i2").astype(np.float64)
    gained = np.rint(samples * revision.gain)
    if np.any(np.abs(gained) >= 32768):
        raise ValueError("cue gain clips PCM")
    return gained.astype("<i2").tobytes()


def build_bank(sealed: bytes, audio: bytes, revision: Revision = CURRENT) -> bytes:
    if digest(sealed) != revision.base_bank_sha:
        raise ValueError(f"sealed v{revision.base_version} source bank differs")
    hca_info(audio)
    native = Utf(sealed)
    top = row_copy(native, 0)
    top.update(Name=revision.cue, AcbGuid=bytes.fromhex(digest(revision.cue.encode() + audio))[:16],
               AwbFile=memory_awb([(0, audio)]),
               CueNameTable=rebuild_utf(native.child("CueNameTable"),
                   [{"CueName": revision.cue, "CueIndex": 0}], compact_blobs=True))
    bank = rebuild_utf(native, [top], compact_blobs=True)
    after = Utf(bank)
    if len(bank) > MAX_BANK or awb_recording(after.blob(0, "AwbFile"), 0) != audio:
        raise ValueError("bank bounds/recording roundtrip differs")
    for field in NATIVE_GRAPH_FIELDS:
        if native.blob(0, field) != after.blob(0, field):
            raise ValueError("native graph or routing changed: " + field)
    routing(after)
    return bank


def catalog(bank: bytes, audio: bytes, revision: Revision = CURRENT) -> str:
    info = hca_info(audio)
    return f'''/* Generated metadata only; the user recording remains ignored. */
#ifndef PESNX_TROPHY_AUDIO_CATALOG_H
#define PESNX_TROPHY_AUDIO_CATALOG_H
#define TROPHY_AUDIO_ASSET "{revision.asset}"
#define TROPHY_AUDIO_CUE "{revision.cue}"
#define TROPHY_AUDIO_ENCODE_TYPE 2u
#define TROPHY_AUDIO_MAX_BANK_BYTES {MAX_BANK}u
#define TROPHY_AUDIO_GAIN_DB_X100 ({revision.gain_db * 100})
#define TROPHY_AUDIO_BYTES {len(bank)}u
#define TROPHY_AUDIO_FNV UINT64_C(0x{fnv64(bank):016x})
#define TROPHY_AUDIO_HEADER_BYTES {info['header_bytes']}u
#define TROPHY_AUDIO_HEADER_FNV UINT64_C(0x{fnv64(audio[:info['header_bytes']]):016x})
#endif
'''


def stage(source: Path, sealed_path: Path, encoder: Path, ffmpeg: Path,
          output: Path, revision: Revision = CURRENT) -> dict:
    output = output.resolve()
    if not output.is_relative_to(ROOT / "local-debug") or output.exists():
        raise ValueError("use a new ignored local-debug directory")
    sealed, supplied = sealed_path.read_bytes(), source.read_bytes()
    if digest(sealed) != revision.base_bank_sha or digest(supplied) != SOURCE_SHA:
        raise ValueError(f"reviewed source song or sealed v{revision.base_version} bank differs")
    if digest(encoder.read_bytes()) != ENCODER_SHA:
        raise ValueError("reviewed encoder differs")
    original = subprocess.run([str(ffmpeg), "-nostdin", "-v", "error", "-xerror",
        "-i", str(source), "-map", "0:a:0", "-vn", "-f", "s16le", "-"],
        check=True, capture_output=True, timeout=60).stdout
    if digest(original) != SOURCE_PCM_SHA:
        raise ValueError("original decoded PCM differs from reviewed v90 source")
    pcm = gained_pcm(original, revision)
    output.mkdir(parents=True)
    wave_path = output / f"source-minus{-revision.gain_db}db.wav"
    with wave.open(str(wave_path), "wb") as writer:
        writer.setnchannels(2)
        writer.setsampwidth(2)
        writer.setframerate(44100)
        writer.writeframes(pcm)
    hca_path = output / "trophy-user.hca"
    subprocess.run([str(encoder), "-i", str(wave_path), "-o", str(hca_path),
        "--hcaquality", "highest", "--no-loop"], check=True,
        capture_output=True, timeout=60)
    audio = hca_path.read_bytes()
    info = hca_info(audio)
    decoded = subprocess.run([str(ffmpeg), "-nostdin", "-v", "error", "-xerror",
        "-i", str(hca_path), "-f", "f32le", "-"], check=True,
        capture_output=True, timeout=60).stdout
    samples = np.frombuffer(decoded, "<f4").reshape(-1, 2)
    if len(samples) == info["frames"] * 1024:
        samples = samples[info["encoder_delay"]:info["encoder_delay"] + info["samples"]]
    if len(samples) != info["samples"] or not np.all(np.isfinite(samples)):
        raise ValueError("full independent decoded sample count/finite check failed")
    reference = np.frombuffer(pcm, "<i2").reshape(-1, 2).astype(np.float64) / 32768
    polarity = -1 if np.sum(reference * samples) < 0 else 1
    snr = float(10 * np.log10(np.sum(reference ** 2) /
                            np.sum((reference - samples * polarity) ** 2)))
    peak = float(np.max(np.abs(samples)))
    if snr < 37 or peak > revision.maximum_peak or np.any(np.abs(samples) >= 1):
        raise ValueError(f"HCA quality/headroom check failed: snr={snr}, peak={peak}")
    # Independently compare to the earlier bank, without using its lossy audio
    # as encoder input. All source samples still come from the original MP3.
    previous_hca = output / f"sealed-v{revision.base_version}.hca"
    previous_hca.write_bytes(awb_recording(Utf(sealed).blob(0, "AwbFile"), 0))
    previous_decoded = subprocess.run([str(ffmpeg), "-nostdin", "-v", "error", "-xerror",
        "-i", str(previous_hca), "-f", "f32le", "-"], check=True,
        capture_output=True, timeout=60).stdout
    previous = np.frombuffer(previous_decoded, "<f4").reshape(-1, 2)
    if len(previous) == info["frames"] * 1024:
        previous = previous[info["encoder_delay"]:info["encoder_delay"] + info["samples"]]
    if previous.shape != samples.shape or not np.all(np.isfinite(previous)):
        raise ValueError("previous independent decode sample count/finite check failed")
    rms_dbfs = float(20 * np.log10(np.sqrt(np.mean(samples ** 2))))
    previous_rms_dbfs = float(20 * np.log10(np.sqrt(np.mean(previous ** 2))))
    increase = rms_dbfs - previous_rms_dbfs
    if abs(increase - revision.increase_db) > .02:
        raise ValueError(f"relative decoded level differs: {increase}")
    bank = build_bank(sealed, audio, revision)
    target = output / revision.asset
    target.parent.mkdir()
    target.write_bytes(bank)
    (output / "trophy_audio_catalog.h").write_text(catalog(bank, audio, revision),
        encoding="ascii", newline="\n")
    if source.read_bytes() != supplied or sealed_path.read_bytes() != sealed:
        raise ValueError("sealed source mutated during staging")
    report = dict(status="detached_host_verified_not_installed", source_sha256=SOURCE_SHA,
        source_pcm_sha256=SOURCE_PCM_SHA,
        **{f"sealed_v{revision.base_version}_sha256": revision.base_bank_sha},
        source_mutated=False, previous_bank_mutated=False,
        bank_sha256=digest(bank), bank_bytes=len(bank), bank_fnv64=f"{fnv64(bank):016x}",
        runtime_asset=revision.asset, runtime_cue=revision.cue, hca_sha256=digest(audio), codec_info=info,
        codec="HCA highest", gain_db=revision.gain_db,
        **{f"increase_vs_v{revision.base_version}_db": revision.increase_db},
        measured_increase_db=increase, previous_decoded_rms_dbfs=previous_rms_dbfs,
        original_pcm_encoded_once=True, normalization_or_compression=False,
        resampling_or_downmixing=False, trimmed_frames=0,
        independent_decoded_samples=len(samples), snr_db=snr,
        comparison_global_polarity=polarity, decoded_peak=peak,
        decoded_rms_dbfs=float(20 * np.log10(np.sqrt(np.mean(samples ** 2)))),
        decoded_peak_headroom_db=float(-20 * np.log10(peak)),
        clipped_samples=int(np.count_nonzero(np.abs(samples) >= 1)),
        native_route=routing(Utf(bank)), encoder_sha256=ENCODER_SHA,
        global_gain_or_commentary_changed=False, creates_new_voice_pool=False,
        device_accepted=False)
    (output / "AUDIO-REPORT.json").write_text(json.dumps(report, indent=2) + "\n",
        encoding="utf8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("source", "sealed-bank", "encoder", "ffmpeg", "output"):
        parser.add_argument("--" + arg, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.source, args.sealed_bank, args.encoder,
                           args.ffmpeg, args.output,V100), indent=2))
