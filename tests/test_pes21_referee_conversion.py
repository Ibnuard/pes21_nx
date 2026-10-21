"""Native pose/bind-space and runtime-bank contracts without game fixtures."""
from pathlib import Path
import math
import shutil
import struct
import subprocess

import pytest

from tools.audit_fl26_referee import CLIP_KEYS
from tools.convert_ef_referee import SPEEDS, render_rotation, rotate, write_bank
from tools.convert_pes21_referee import (bake_motion, convert, encode_bank,
                                         native_pose, root_motion_metrics,
                                         select_motions, whistle_contact)

ROOT = Path(__file__).resolve().parents[1]
IDENTITY = (0, 0, 0, 1)


def gani():
    data = bytearray(176)
    struct.pack_into("<III", data, 0, 201106130, 32, len(data))
    struct.pack_into("<Ib", data, 156, 3, 10)
    return bytes(data)


def mtar(entries):
    data = bytearray(32 + len(entries) * 16)
    struct.pack_into("<II", data, 0, 0x0BFFA89C, len(entries))
    for i, (key, payload) in enumerate(entries):
        struct.pack_into("<QII", data, 32 + i * 16, key, len(data), len(payload))
        data += payload
    return data


def pose_fixture():
    # Native IK may include small solved offsets. Preserve them rather than
    # reconstructing all positions from their neutral rest hierarchy.
    bones = [{"name": "pelvis", "parent": -1, "pos": (0, 1, 0)},
             {"name": "hand", "parent": 0, "pos": (.3, 0, 0)}]
    rotations = [IDENTITY, IDENTITY]
    positions = [(1, 1.1, .5), (1.3, 1.101, .5)]
    return bones, rotations, positions


def test_full_identity_extraction_and_duplicate_rejection():
    key = CLIP_KEYS["referee_stand_0"]
    data = mtar([(key | 0x1000000000000, gani()), (key, gani())])
    assert select_motions(data) == {"referee_stand_0": gani()}
    with pytest.raises(ValueError, match="duplicate"):
        select_motions(mtar([(key, gani()), (key, gani())]))
    data = mtar([(key, gani())])
    struct.pack_into("<I", data, 40, 1)
    with pytest.raises(ValueError, match="bounds"):
        select_motions(data)


def test_direct_native_positions_and_bind_rotations_survive_slot_reordering():
    bones, q, p = pose_fixture()
    world = (0, math.sqrt(.5), 0, math.sqrt(.5))
    bind = (math.sqrt(.5), 0, 0, math.sqrt(.5))
    q[1] = world
    pose, metrics = native_pose(bones, ["hand", "pelvis"], [IDENTITY, bind], q, p)
    assert pose[0][1] == pytest.approx((.3, 1.101, 0))
    assert pose[1][1] == pytest.approx((0, 1.1, 0))
    assert pose[0][0] == pytest.approx(render_rotation(world, bind))
    vertex = (.1, .2, .3)
    assert rotate(pose[0][0], vertex) == pytest.approx(rotate(world, rotate(bind, vertex)))
    assert metrics["max_fk_residual_m"] == pytest.approx(.001)
    assert metrics["max_bone_length_error_m"] < .0001


@pytest.mark.parametrize("mutation", ["detached", "nan", "rotation", "duplicate_slot", "missing_slot"])
def test_native_pose_rejects_corruption_instead_of_repairing(mutation):
    bones, q, p = pose_fixture()
    slots = ["pelvis", "hand"]
    if mutation == "detached":
        p[1] = (1.5, 1.1, .5)
    elif mutation == "nan":
        p[1] = (math.nan, 1.1, .5)
    elif mutation == "rotation":
        q[0] = (0, 0, 0, 0)
    elif mutation == "duplicate_slot":
        slots = ["hand", "hand"]
    else:
        slots = ["missing"]
    with pytest.raises(ValueError):
        native_pose(bones, slots, [IDENTITY] * 2, q, p)


def test_locomotion_phase_is_aligned_but_gesture_order_remains_original():
    bones = [{"name": "pelvis", "parent": -1, "pos": (0, 1, 0)},
             {"name": "sk_foot_l", "parent": 0, "pos": (.1, -.9, 0)},
             {"name": "sk_foot_r", "parent": 0, "pos": (-.1, -.9, 0)}]
    samples = []
    for offset in (0, .001, -.001):
        samples.append(([IDENTITY] * 3, [(0, 1, 0), (.1, .1, offset), (-.1, .1, -offset)]))
    slots = [bone["name"] for bone in bones]
    gesture, gesture_metrics = bake_motion(samples, bones, slots, [IDENTITY] * 3, False)
    loop, loop_metrics = bake_motion(samples, bones, slots, [IDENTITY] * 3, True)
    assert gesture_metrics["phase_shift"] == 0
    assert loop_metrics["phase_shift"] == 1
    assert loop == gesture[1:] + gesture[:1]


def bank_fixture():
    clips = []
    for i in range(8):
        frames = []
        for frame in range(3 + i):
            angle = .05 * math.sin(frame)
            q = (0, math.sin(angle / 2), 0, math.cos(angle / 2))
            frames.append([(q, (.01 * i, 1, .001 * bone)) for bone in range(19)])
        clips.append(frames)
    return clips


def test_bank_is_byte_compatible_with_existing_runtime_format(tmp_path):
    clips = bank_fixture()
    output = tmp_path / "reference.nxra"
    write_bank(clips, output)
    encoded = encode_bank(clips, SPEEDS, (0, 0))
    assert encoded[32:] == output.read_bytes()[32:]
    assert struct.unpack_from("<I", encoded, 8)[0] == 4
    assert encode_bank(clips, SPEEDS, (0, 0)) == encoded
    with_contact = encode_bank(clips, SPEEDS, (.01, .02))
    assert struct.unpack_from("<ff", with_contact, 32 + 4 * 32 + 16) == pytest.approx((.01, .02))
    with pytest.raises(ValueError):
        encode_bank(clips[:4], SPEEDS, (0, 0))
    clips[0][0][0] = (IDENTITY, (0, math.nan, 0))
    with pytest.raises(ValueError):
        encode_bank(clips, SPEEDS, (0, 0))


@pytest.mark.parametrize("contact", [(-1, 0), (.02, .01), (0, 100), (0, math.nan)])
def test_native_contact_range_validation(contact):
    with pytest.raises(ValueError, match="contact"):
        encode_bank(bank_fixture(), SPEEDS, contact)


def test_root_travel_speed_and_contiguous_whistle_plateau():
    samples = [([IDENTITY] * 3, [(frame / 30, 1, 0), (0, 1, distance), (0, 1, 0)])
               for frame, distance in enumerate((.5, .4, .1, .105, .2, .5))]
    bones = [{"name": "pelvis"}, {"name": "sk_hand_l"}, {"name": "sk_head"}]
    metrics = root_motion_metrics(samples)
    assert metrics["root_net_speed_mps"] == pytest.approx(1)
    assert metrics["root_horizontal_path_m"] == metrics["root_horizontal_net_m"]
    contact = whistle_contact(samples, bones)
    assert contact["nearest_frame"] == 2
    assert contact["contact_begin_s"] == pytest.approx(2 / 30)
    assert contact["contact_end_s"] == pytest.approx(3 / 30)


def test_unsupported_decoder_rejected_before_output_mutation(tmp_path):
    library = tmp_path / "unknown.so"
    library.write_bytes(b"synthetic unsupported library")
    output = tmp_path / "referee.nxra"
    output.write_bytes(b"previous known working output")
    with pytest.raises(ValueError, match="decoder ELF identity"):
        convert(tmp_path / "absent.cpk", library, output)
    assert output.read_bytes() == b"previous known working output"


def test_all_eight_native_slots_play_in_production_c_sampler(tmp_path):
    compiler = shutil.which("gcc") or shutil.which("clang")
    if not compiler:
        pytest.skip("host C compiler unavailable")
    bank = tmp_path / "referee.nxra"
    bank.write_bytes(encode_bank(bank_fixture(), SPEEDS, (.01, .02)))
    source, executable = tmp_path / "bank.c", tmp_path / "bank.exe"
    source.write_text('''#include "referee_animation.h"
#include <assert.h>
int main(int argc,char **argv) {
  assert(argc==2);FILE *f=fopen(argv[1],"rb");assert(f);
  fseek(f,0,SEEK_END);size_t size=ftell(f);rewind(f);
  void *data=malloc(size);assert(fread(data,1,size,f)==size);fclose(f);
  RefereeAnimationBank bank;assert(referee_animation_bind(&bank,data,size));
  assert(bank.count==8);RefereeBonePose pose[19];RefereeAnimationClock clock={0};
  for(unsigned i=0;i<1800;++i) {
    assert(referee_animation_step(&bank,&clock,(i%180)*5.8f/180,1.0f/30,pose));
    for(unsigned j=0;j<19;++j) assert(isfinite(pose[j].position[1]));
  }
  for(unsigned clip=4;clip<8;++clip) {
    RefereeGesture gesture={.clip=clip};
    assert(referee_gesture_apply(&bank,&gesture,1.0f/30,pose));
  }
  ((unsigned char *)data)[size-1]^=1;
  assert(!referee_animation_bind(&bank,data,size));free(data);return 0;
}
''', encoding="utf-8")
    command = [compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", "-I",
               (ROOT / "source").as_posix(), source.as_posix(), "-lm", "-o", executable.as_posix()]
    build = subprocess.run(command, capture_output=True, text=True)
    assert build.returncode == 0, build.stdout + build.stderr
    run = subprocess.run([str(executable), str(bank)], capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr
