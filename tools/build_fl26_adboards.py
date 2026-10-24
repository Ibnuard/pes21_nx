"""Bake four owned FL26 generic adboard frames into Mobile's native LED atlas.

Only same-sized Texture2D mip payloads change. The mesh, UVs, material shader,
native five/ten-second atlas animation and package metadata remain game-owned.
Source movie data is streamed from its CPK range; no CPK/OBB/movie is copied.
All generated payloads and previews must stay in ignored local output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from PIL import Image, ImageOps

from cooked_texture import Texture
from prepare_loose_cpk import cpk_layout, member_name


MEMBER = Path('PesMobile/Content/Assets/bg_lighting_AM1/Billboard/bill_myclub')
SOURCE_MEMBER = 'common/bg/model/bg/bill/p_global/movie/bill_p_global.usm'
NATIVE_HASHES = {
    '.uasset': '855a1eefc86f17d07c32f8f3c00a245627fd9bf807e468764dacb616ed82dbd5',
    '.uexp': 'fb95f3a7e46772a5361795c502e8cb9b6c0a5bcd26e39ea76c7d201281adca3d',
    '.ubulk': '0e1b874fc51649676c3cf175c3b48a2f688ec9357f90f4da4cc73bce18d695e0',
}
# The two PC video rows are different strips, not an alpha plane. Select one
# complete sponsor crop per native slot and preserve its physical proportions.
# Frame indices are in the observed 30fps first video stream, without seeking.
SAMPLES = (
    dict(slot=0, label='FL26', frame=225, crop=(160, 72, 608, 144)),
    dict(slot=1, label='Copilot', frame=495, crop=(160, 0, 608, 72)),
    dict(slot=2, label='Hisense', frame=1305, crop=(128, 0, 640, 72)),
    dict(slot=3, label='Qatar Airways', frame=1845, crop=(0, 72, 768, 144)),
)
PAK_NAME = 'PesMobile-FL26-Adboards-v76-Android_ETC1_P.pak'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def checked_source(cpk, expected):
    """Bind a single uncompressed CPK member to an explicit content hash."""
    if len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
        raise ValueError('An explicit lowercase source SHA256 is required')
    _, rows, base = cpk_layout(cpk)
    matches = [r for r in rows if member_name(r) == SOURCE_MEMBER]
    if len(matches) != 1:
        raise ValueError('Expected exactly one generic source movie')
    row = matches[0]
    size, start = int(row['FileSize']), base + int(row['FileOffset'])
    if (size != int(row['ExtractSize']) or size <= 0 or start < 0 or
            start + size > cpk.stat().st_size):
        raise ValueError('Invalid or compressed source movie range')
    digest = hashlib.sha256()
    with cpk.open('rb') as stream:
        stream.seek(start)
        remaining = size
        while remaining:
            block = stream.read(min(1024 * 1024, remaining))
            if not block:
                raise ValueError('Source movie range truncated')
            digest.update(block)
            remaining -= len(block)
    if digest.hexdigest() != expected:
        raise ValueError('Source movie fingerprint mismatch')
    return dict(member=SOURCE_MEMBER, offset=start, bytes=size, sha256=expected)


def extract_frames(cpk, binding, ffmpeg, output):
    output.mkdir()
    selected = '+'.join('eq(n,%d)' % s['frame'] for s in SAMPLES)
    command = [str(ffmpeg), '-hide_banner', '-loglevel', 'info', '-i', 'pipe:0',
               '-map', '0:v:0', '-vf', "select='%s',showinfo" % selected,
               '-fps_mode', 'vfr', '-frames:v', str(len(SAMPLES)),
               str(output / 'frame-%02d.png')]
    fed = 0
    with (output / 'ffmpeg.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen(command, stdin=subprocess.PIPE,
                                   stdout=log, stderr=log)
        try:
            with cpk.open('rb') as stream:
                stream.seek(binding['offset'])
                remaining = binding['bytes']
                while remaining:
                    block = stream.read(min(1024 * 1024, remaining))
                    if not block:
                        raise ValueError('Source movie stream truncated')
                    remaining -= len(block)
                    process.stdin.write(block)
                    fed += len(block)
        except BrokenPipeError:
            # ffmpeg stops after the requested fourth frame. It need not read
            # the remainder of the full source movie, which was hashed above.
            pass
        finally:
            try:
                process.stdin.close()
            except BrokenPipeError:
                pass
            code = process.wait()
    if code != 0:
        raise ValueError('Frame extraction failed; see ffmpeg.log')
    paths = sorted(output.glob('frame-*.png'))
    if len(paths) != len(SAMPLES):
        raise ValueError('The four selected source frames were not decoded')
    images = []
    for path in paths:
        with Image.open(path) as image:
            if image.size != (1536, 144):
                raise ValueError('Source video dimensions changed')
            images.append(image.convert('RGB'))
    return images, fed


def compose_atlas(images):
    """Pre-compensate the native 2:1 texel panel for its 5.3036:1 geometry."""
    if len(images) != 4 or any(im.size != (1536, 144) for im in images):
        raise ValueError('Four decoded 1536x144 source frames are required')
    atlas = Image.new('RGB', (512, 256))
    physical = []
    for spec, image in zip(SAMPLES, images):
        crop = image.crop(spec['crop'])
        # A 509x96 board approximates the measured native aspect 5.303624.
        # Source logo aspect is preserved here; raster distortion is undone by
        # the existing native billboard rectangle when the atlas is sampled.
        panel = Image.new('RGB', (509, 96), crop.getpixel((0, 0)))
        contained = ImageOps.contain(crop, (489, 86), Image.Resampling.LANCZOS)
        panel.paste(contained, ((509-contained.width)//2, (96-contained.height)//2))
        physical.append(panel)
        slot = spec['slot']
        atlas.paste(panel.resize((256, 128), Image.Resampling.LANCZOS),
                    ((slot % 2) * 256, (slot // 2) * 128))
    return atlas, physical


def assert_payload_only(before, after, mips):
    """All serialized metadata/offsets/padding outside mip ranges are exact."""
    if set(before) != set(after):
        raise ValueError('Texture split set changed')
    for suffix, raw in after.items():
        if len(raw) != len(before[suffix]):
            raise ValueError('Texture split size changed')
        restored = bytearray(raw)
        for mip in mips:
            if mip.file == suffix:
                restored[mip.offset:mip.offset+mip.size] = before[suffix][mip.offset:mip.offset+mip.size]
        if bytes(restored) != before[suffix]:
            raise ValueError('Texture metadata or padding changed')


def healthy_test_log(text, pak, expected):
    """UE4.22 reports 'Pak file <path> healthy', without the word 'is'."""
    summary = 'Pak file "%s" healthy, %d files checked.' % (pak, len(expected))
    checked = re.findall(r'LogPakFile: Display: "([^"\r\n]+)" OK\. \[Zlib\]', text)
    return summary in text and len(checked) == len(expected) and set(checked) == set(expected)


def build(native, cpk, source_sha256, ffmpeg, encoder, repak, unrealpak, umodel, output):
    if output.exists():
        raise ValueError('Output must be a new ignored local directory')
    source = native / MEMBER
    inputs = {ext: source.with_suffix(ext).read_bytes() for ext in NATIVE_HASHES}
    if {ext: sha(raw) for ext, raw in inputs.items()} != NATIVE_HASHES:
        raise ValueError('Native billboard revision fingerprint mismatch')
    texture = Texture(source.with_suffix('.uexp'))
    if (texture.format != 'PF_ETC1' or (texture.width, texture.height) != (512, 256) or
            len(texture.mips) != 10 or sum(m.size for m in texture.mips) != 87400):
        raise ValueError('Native billboard mip contract changed')
    binding = checked_source(cpk, source_sha256)
    output.mkdir(parents=True)
    images, fed = extract_frames(cpk, binding, ffmpeg, output / 'frames')
    atlas, physical = compose_atlas(images)
    atlas.save(output / 'atlas-source.png')
    contact = Image.new('RGB', (509, 4*96))
    for spec, panel in zip(SAMPLES, physical):
        contact.paste(panel, (0, spec['slot']*96))
    contact.save(output / 'panels-physical-aspect.png')
    stage = output / 'stage'
    dest = stage / MEMBER
    dest.parent.mkdir(parents=True)
    encoded = output / 'encoded'
    encoded.mkdir()
    payloads = []
    for index, mip in enumerate(texture.mips):
        image = atlas.resize((mip.width, mip.height), Image.Resampling.LANCZOS)
        png, payload = encoded / ('mip-%02d.png'%index), encoded / ('mip-%02d.etc1'%index)
        image.save(png)
        subprocess.run([str(encoder), str(png), '--encodeNoHeader', '-o', str(payload)],
                       check=True, capture_output=True)
        raw = payload.read_bytes()
        if len(raw) != mip.size:
            raise ValueError('ETC1 mip payload size differs')
        payloads.append(raw)
    originals = texture.files
    changed = texture.replace(payloads)
    assert_payload_only(originals, changed, texture.mips)
    for suffix, raw in changed.items():
        dest.with_suffix('.'+suffix).write_bytes(raw)
    dest.with_suffix('.uasset').write_bytes(inputs['.uasset'])
    after = Texture(dest.with_suffix('.uexp'))
    if any(after.payload(i) != payload for i, payload in enumerate(payloads)):
        raise ValueError('Cooked texture reread differs')
    after.decode().save(output / 'atlas-etc1-roundtrip.png')

    # Independent game-asset reader/exporter, without starting the UE editor.
    independent = output / 'independent-export'
    command = [str(umodel), '-export', '-game=ue4.22', '-path='+str(stage),
               '-out='+str(independent), 'bill_myclub.uasset']
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    (output / 'umodel-export.log').write_text(result.stdout+result.stderr, encoding='utf-8')
    tgas = list(independent.rglob('bill_myclub.tga'))
    if len(tgas) != 1:
        raise ValueError('Independent native Texture2D export unavailable')
    if Image.open(tgas[0]).convert('RGBA').tobytes() != after.decode().tobytes():
        raise ValueError('Independent decoder disagrees with the patched texture')

    pak = output / PAK_NAME
    subprocess.run([str(repak), 'pack', '--version', 'V8A', '--compression', 'Zlib',
                    str(stage), str(pak)], check=True, capture_output=True)
    expected = {MEMBER.with_suffix(ext).as_posix(): sha((stage/MEMBER).with_suffix(ext).read_bytes())
                for ext in NATIVE_HASHES}
    names = subprocess.check_output([str(repak), 'list', str(pak)], text=True).splitlines()
    if set(names) != set(expected) or len(names) != 3:
        raise ValueError('Adboard PAK allowlist differs')
    test = subprocess.run([str(unrealpak), str(pak), '-Test'], capture_output=True,
                          text=True, check=True)
    test_log = test.stdout+test.stderr
    (output / 'unrealpak-test.log').write_text(test_log, encoding='utf-8')
    if not healthy_test_log(test_log, pak, expected):
        raise ValueError('UnrealPak did not confirm a healthy archive')
    restored = output / 'independent-unpack'
    subprocess.run([str(repak), 'unpack', '-q', '-o', str(restored), str(pak)], check=True)
    unpacked = {p.relative_to(restored).as_posix(): sha(p.read_bytes())
                for p in restored.rglob('*') if p.is_file()}
    if unpacked != expected:
        raise ValueError('Independent PAK unpack hashes differ')
    if {ext: sha(source.with_suffix(ext).read_bytes()) for ext in NATIVE_HASHES} != NATIVE_HASHES:
        raise ValueError('Native source changed')
    report = dict(schema=1, state='verified_optional_adboard_candidate',
                  source_cpk=str(cpk), source=binding, source_stream_bytes_read=fed,
                  samples=SAMPLES, native_hashes=NATIVE_HASHES,
                  native_texture=dict(width=512, height=256, format='PF_ETC1',
                                      mip_count=10, retained_mip_payload_bytes=87400,
                                      additional_gpu_texture_bytes=0),
                  target_member=MEMBER.as_posix(), members=expected,
                  pak=str(pak), pak_bytes=pak.stat().st_size, pak_sha256=sha(pak.read_bytes()),
                  metadata_exact=True, native_source_untouched=True,
                  independent_decode_exact=True, unrealpak_test_healthy=True,
                  independent_unpack_hashes_exact=True,
                  native_mesh_material_uv_animation_unchanged=True,
                  added_per_frame_cpu_work=False, pc_video_playback_ported=False,
                  automatic_league_selection=False, hardware_tested=False)
    (output / 'VERIFICATION.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('native', 'source-cpk', 'ffmpeg', 'etc1tool', 'repak', 'unrealpak', 'umodel', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--source-sha256', required=True)
    a = parser.parse_args()
    report = build(a.native.resolve(), a.source_cpk.resolve(), a.source_sha256,
                   a.ffmpeg.resolve(), a.etc1tool.resolve(), a.repak.resolve(),
                   a.unrealpak.resolve(), a.umodel.resolve(), a.output.resolve())
    print(json.dumps(dict(state=report['state'], pak=report['pak'], bytes=report['pak_bytes'])))


if __name__ == '__main__':
    main()
