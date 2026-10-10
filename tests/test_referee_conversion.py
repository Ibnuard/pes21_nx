"""Retargeting and native playback contracts; no proprietary fixture required."""
from pathlib import Path
import math
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib

from tools.convert_ef_referee import (read_skeleton, retarget, unpack_wesys, write_bank,
                                     render_rotations, render_rotation, rotate)

ROOT = Path(__file__).resolve().parents[1]


def skeleton(version, bones):
    start, stride = (8, 44) if version == 1 else (16, 28)
    data = bytearray(start + stride * len(bones))
    struct.pack_into('<II', data, 0, version, len(bones))
    for i, (name, parent, pos) in enumerate(bones):
        at = start + i * stride
        struct.pack_into('<IIi3f', data, at, 0, len(data)-at-4, parent, *pos)
        data += name.encode() + b'\0'
    return bytes(data)


class RefereeConversionTests(unittest.TestCase):
    def test_render_bind_rotations_and_skinning_space(self):
        bones = [('hip', -1, (0, 1, 0)), ('hand', 0, (.4, 0, 0))]
        data = bytearray(skeleton(1, bones))
        bind = (math.sqrt(.5), 0, 0, math.sqrt(.5))
        for i in range(2):
            struct.pack_into('<4f', data, 8+i*44+28, *bind)
        target = read_skeleton(data)
        conversions = render_rotations(data, target)
        world = (0, math.sqrt(.5), 0, math.sqrt(.5))
        # A vertex authored in the render bone's basis must first enter the
        # animation basis, then receive animation's world rotation.
        vertex = (.1, .2, .3)
        expected = rotate(world, rotate(bind, vertex))
        actual = rotate(render_rotation(world, conversions[1]), vertex)
        for a, b in zip(actual, expected):
            self.assertAlmostEqual(a, b, places=6)
        self.assertGreater(math.dist(rotate(world, vertex), expected), .1)
        # v2 stores the same conversions in an aligned separate table.
        header = bytearray(16+28*2)
        struct.pack_into('<II', header, 0, 2, 2)
        header += bytes((-len(header))%16) + struct.pack('<4f', *bind)*2
        for i, (name, parent, pos) in enumerate(bones):
            at = 16+i*28
            struct.pack_into('<IIi3f', header, at, 0, len(header)-at-4, parent, *pos)
            header += name.encode()+b'\0'
        self.assertEqual(render_rotations(header, target), conversions)
        with self.assertRaises(ValueError):
            render_rotations(data, list(reversed(target)))
        struct.pack_into('<4f', data, 36, 0, 0, 0, 0)
        with self.assertRaises(ValueError):
            render_rotations(data, target)

    def test_both_skeleton_layouts_and_invalid_hierarchy(self):
        bones = [('hip', -1, (0, 1, 0)), ('knee', 0, (0, -0.45, 0))]
        old = read_skeleton(skeleton(1, bones))
        self.assertEqual(read_skeleton(skeleton(2, bones)), old)
        for version in (1, 2):
            with self.assertRaises(ValueError):
                read_skeleton(skeleton(version, [bones[0], ('knee', 1, (0, 0, 0))]))
            with self.assertRaises(ValueError):
                read_skeleton(skeleton(version, [bones[0], bones[0]]))
            with self.assertRaises(ValueError):
                read_skeleton(skeleton(version, bones)[:20])

    def test_wrapped_bounds(self):
        data = skeleton(2, [('hip', -1, (0, 1, 0))])
        packed = zlib.compress(data)
        blob = b'\0\0\0WESYS' + struct.pack('<II', len(packed), len(data)) + packed
        self.assertEqual(unpack_wesys(blob), data)
        wrong = bytearray(blob)
        struct.pack_into('<I', wrong, 12, 1)
        with self.assertRaises(ValueError):
            unpack_wesys(wrong)
        with self.assertRaises(ValueError):
            unpack_wesys(blob[:-1])

    def test_world_rotations_survive_removed_spine_and_lengths_stay_native(self):
        source = read_skeleton(skeleton(2, [
            ('hip', -1, (0, 1, 0)), ('sk_spine_01', 0, (0, .1, 0)),
            ('sk_spine_02', 1, (0, .1, 0)), ('sk_spine_03', 2, (0, .1, 0)),
            ('hand', 3, (0, .2, 0))]))
        target = read_skeleton(skeleton(1, [
            ('hip', -1, (0, .9, 0)), ('sk_belly', 0, (0, .15, 0)),
            ('sk_chest', 1, (0, .2, 0)), ('hand', 2, (0, .3, 0))]))
        q = [(0, 0, math.sin(a/2), math.cos(a/2)) for a in (0, .2, .3, .4, .6)]
        p = [(100, 1.1, 300)] * 5  # World translation must not drive the referee.
        rotations, positions = retarget(source, target, q, p)
        self.assertEqual(rotations[2], q[3])  # Global chest rotation includes extra spine.
        self.assertEqual(rotations[3], q[4])
        self.assertAlmostEqual(positions[0][1], .99, places=6)
        self.assertEqual((positions[0][0], positions[0][2]), (0, 0))
        for i in range(1, len(target)):
            parent = target[i]['parent']
            self.assertAlmostEqual(math.dist(positions[i], positions[parent]),
                                   math.sqrt(sum(v*v for v in target[i]['pos'])), places=6)

    def test_writer_rejects_invalid_bank_without_overwriting(self):
        identity = ((0, 0, 0, 1), (0, 1, 0))
        clips = [[[identity] * 19] * 3] * 4
        with tempfile.TemporaryDirectory(prefix='pesnx-ref-write-') as temp:
            out = Path(temp) / 'referee.nxra'
            write_bank(clips, out)
            baseline = out.read_bytes()
            for invalid in (clips[:3], [[[identity] * 19]],
                            [[[(0, 0, 0, 0), (0, 1, 0)]] * 4]):
                with self.assertRaises(ValueError):
                    write_bank(invalid, out)
                self.assertEqual(out.read_bytes(), baseline)

    def test_python_bank_plays_in_production_c_sampler(self):
        cc = shutil.which('gcc') or shutil.which('clang')
        if not cc:
            self.skipTest('host C compiler unavailable')
        with tempfile.TemporaryDirectory(prefix='pesnx-ref-format-') as temp:
            folder = Path(temp)
            out = folder / 'referee.nxra'
            clips = []
            for clip in range(4):
                frames = []
                for i in range(21+clip):
                    angle = .3*math.sin(2*math.pi*i/(21+clip))
                    bone = ((0, math.sin(angle/2), 0, math.cos(angle/2)), (0, 1, 0))
                    frames.append([bone] * 19)
                clips.append(frames)
            write_bank(clips, out)
            source, exe = folder / 'sample.c', folder / 'sample.exe'
            source.write_text('''#include "referee_animation.h"
#include <assert.h>
int main(int argc,char **argv) {
  assert(argc==2);FILE *f=fopen(argv[1],"rb");assert(f);
  fseek(f,0,SEEK_END);size_t n=ftell(f);rewind(f);
  void *data=malloc(n);assert(fread(data,1,n,f)==n);fclose(f);
  RefereeAnimationBank bank;assert(referee_animation_bind(&bank,data,n));
  RefereeAnimationClock clock={0};RefereeBonePose pose[19];
  for(unsigned i=0;i<1800;++i) {
    assert(referee_animation_step(&bank,&clock,(i%180)*5.8f/180,1.0f/30,pose));
    assert(isfinite(pose[0].rotation[3]) && fabsf(pose[0].position[1]-1)<.00001f);
  }
  free(data);return 0;
}
''')
            build = subprocess.run([cc, '-std=c11', '-Wall', '-Wextra', '-Werror',
                '-I', (ROOT / 'source').as_posix(), source.as_posix(), '-lm', '-o', exe.as_posix()],
                capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(exe), str(out)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
