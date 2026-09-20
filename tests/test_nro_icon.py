"""Synthetic launcher metadata tests; no proprietary runtime fixtures needed."""
import hashlib
import io
import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from prepare_runtime import APK_ICON_PATH, prepare_nro


def make_nro(icon):
    executable = bytearray(0x100)
    executable[0x10:0x14] = b"NRO0"
    struct.pack_into("<I", executable, 0x18, len(executable))
    header = bytearray(0x38)
    header[:4] = b"ASET"
    payload = bytearray()
    for pair, asset in ((8, icon), (0x18, b"synthetic nacp"), (0x28, b"synthetic romfs")):
        struct.pack_into("<QQ", header, pair, 0x38 + len(payload), len(asset))
        payload.extend(asset)
    return bytes(executable + header + payload)


def asset(data, pair):
    offset = struct.unpack_from("<I", data, 0x18)[0]
    relative, size = struct.unpack_from("<QQ", data, offset + pair)
    return data[offset + relative:offset + relative + size]


def test_canonical_icon():
    path = ROOT / "icon.jpg"
    assert path.read_bytes() == (ROOT / "art/nro/fnx-ronaldo-v1-256.jpg").read_bytes()
    with Image.open(path) as image:
        image.load()
        assert (image.format, image.size, image.mode) == ("JPEG", (256, 256), "RGB")
        assert not image.info.get("progressive")
        assert not image.getexif()


def test_preparer_preserves_entire_release_without_opening_apk(tmp_path):
    icon = (ROOT / "icon.jpg").read_bytes()
    original = make_nro(icon)
    source, output = tmp_path / "input.nro", tmp_path / "staging/out.nro"
    source.write_bytes(original)
    report = prepare_nro(tmp_path / "missing.apk", source, output)
    assert output.read_bytes() == original
    assert report["preserved"] is True
    assert report["source"] == "release-nro"
    assert report["sha256"] == hashlib.sha256(icon).hexdigest()


def test_legacy_apk_icon_remains_explicit_opt_in(tmp_path):
    original = make_nro((ROOT / "icon.jpg").read_bytes())
    source, output, apk = tmp_path / "input.nro", tmp_path / "out.nro", tmp_path / "test.apk"
    source.write_bytes(original)
    png = io.BytesIO()
    Image.new("RGB", (64, 64), (30, 50, 70)).save(png, "PNG")
    with zipfile.ZipFile(apk, "w") as archive:
        archive.writestr(APK_ICON_PATH, png.getvalue())
    report = prepare_nro(apk, source, output, apk_icon=True)
    result = output.read_bytes()
    assert result[:0x100] == original[:0x100]
    assert asset(result, 0x18) == asset(original, 0x18)
    assert asset(result, 0x28) == asset(original, 0x28)
    assert asset(result, 8) != asset(original, 8)
    assert report["source"] == APK_ICON_PATH


@pytest.mark.parametrize("kind", ["header", "aset", "range", "dimensions"])
def test_invalid_release_fails_without_output(tmp_path, kind):
    data = bytearray(make_nro((ROOT / "icon.jpg").read_bytes()))
    if kind == "header":
        data[0x10:0x14] = b"FAIL"
    elif kind == "aset":
        struct.pack_into("<I", data, 0x18, 0xFFFFFFFF)
    elif kind == "range":
        struct.pack_into("<Q", data, 0x108, 0xFFFFFFFFFFFFFFFF)
    else:
        small = io.BytesIO()
        Image.new("RGB", (8, 8)).save(small, "JPEG")
        data = make_nro(small.getvalue())
    source, output = tmp_path / "invalid.nro", tmp_path / "out.nro"
    source.write_bytes(data)
    with pytest.raises(RuntimeError):
        prepare_nro(tmp_path / "missing.apk", source, output)
    assert not output.exists()


@pytest.mark.parametrize("kind", ["valid", "different", "range", "missing"])
def test_build_checker(tmp_path, kind):
    if sys.platform != "win32":
        pytest.skip("build-wsl.ps1's System.Drawing check runs on Windows")
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        pytest.skip("PowerShell unavailable")
    icon = (ROOT / "icon.jpg").read_bytes()
    data = bytearray(make_nro(icon))
    if kind == "different":
        data[0x138 + 100] ^= 1
    elif kind == "range":
        struct.pack_into("<Q", data, 0x108, 0xFFFFFFFFFFFFFFFF)
    elif kind == "missing":
        struct.pack_into("<Q", data, 0x110, 0)
    nro = tmp_path / "space in filename.nro"
    nro.write_bytes(data)
    result = subprocess.run([shell, "-NoProfile", "-File", str(ROOT / "scripts/check-nro-icon.ps1"),
                             "-IconPath", str(ROOT / "icon.jpg"), "-NroPath", str(nro)],
                            capture_output=True, text=True)
    assert (result.returncode == 0) == (kind == "valid"), result.stdout + result.stderr
