"""Identity isolation, bounded audio deltas, and native mount ownership."""
from pathlib import Path
import re
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from stage_indonesia_commentary import (HEADER, Utf, build_patch, cpk_member,
                                       fnv64, index_cpk, make_delta, memory_awb,
                                       mobile_index, read_awb_wave)
from pack_runtime_assets import pack

HOOKS = (ROOT / "source/ue4_hooks.c").read_text(encoding="utf-8")
HEADER_PATH = (ROOT / "source/team_commentary_policy.h").as_posix()


def c_array(name, data):
    return f'unsigned char {name}[]={{' + ','.join(str(b) for b in data) + '};\n'


BASE = b"@UTF" + struct.pack(">I", 56) + bytes(56)
TARGET = b"@UTF" + struct.pack(">I", 64) + bytes(16) + b"IDNO" + bytes(36) + b"audio123"
PATCH = make_delta(BASE, TARGET, [(4, 8), (24, 28), (64, 72)])


class CommentaryPolicyTests(unittest.TestCase):
    def run_c(self, body, wrappers=False, archived=False):
        compiler = shutil.which("gcc")
        if not compiler:
            self.skipTest("gcc unavailable")
        source = f'#include <assert.h>\n#include "{HEADER_PATH}"\n'
        source += c_array("base", BASE) + c_array("patch", PATCH) + c_array("target", TARGET)
        if wrappers:
            start = HOOKS.index("static uint32_t team_commentary_indonesia_slot;")
            end = HOOKS.index("\n#ifdef DEBUG_LOG\nstatic int32_t (*sound_cinf_play_original)", start)
            source += HOOKS[start:end]
        source += body
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "Commentary").mkdir()
            (folder / "Commentary/indonesia.nxcp").write_bytes(PATCH)
            if archived:
                pack(folder, folder / 'FootballNX.assets')
                (folder / 'Commentary/indonesia.nxcp').unlink()
                (folder / 'Commentary').rmdir()
            (folder / "test.c").write_text(source)
            subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                            str(folder / "test.c"), "-o", str(folder / "test.exe")], check=True)
            subprocess.run([str(folder / "test.exe")], cwd=folder, check=True)

    def test_archive_only_commentary_reconstructs_identical_bank(self):
        self.run_c(r'''
int main(void) {
  uint32_t n=0;
  void *result=team_commentary_load_delta(base,sizeof(base),"Commentary/indonesia.nxcp",&n);
  assert(result && n==sizeof(target) && !memcmp(result,target,n));free(result);
  base[24]=1;
  assert(!team_commentary_load_delta(base,sizeof(base),"Commentary/indonesia.nxcp",&n));
  assert(n==0);return 0;
}
''', archived=True)

    def test_delta_and_identity_scope(self):
        self.run_c(r'''
int main(void) {
  assert(team_commentary_is_team_bank("00_TEAM.awb"));
  assert(team_commentary_is_team_bank("sound/awb/00_TEAM.awb"));
  assert(!team_commentary_is_team_bank("eng/sound/awb/00_TEAM.awb.bak"));
  assert(!team_commentary_is_team_bank("eng/sound/awb/not00_TEAM.awb"));
  assert(!team_commentary_is_team_bank(NULL));
  for (uint32_t id=0; id<16384; ++id) {
    assert(team_commentary_name_id(id,0,0)==id);
    assert(team_commentary_name_id(id,1,1)==id);
    assert(team_commentary_name_id(id,1,0)==(id==1164?5750:id));
  }
  uint32_t n=777;
  void *result=team_commentary_apply_delta(base,sizeof(base),patch,sizeof(patch),&n);
  assert(result && n==sizeof(target) && !memcmp(result,target,n)); free(result);
  assert(base[24]==0 && sizeof(base)==64);
  result=team_commentary_load_delta(base,sizeof(base),"Commentary/indonesia.nxcp",&n);
  assert(result && !memcmp(result,target,n)); free(result);
  assert(!team_commentary_load_delta(base,sizeof(base),"missing.nxcp",&n) && n==0);
  return 0;
}
''')

    def test_rejects_truncation_corruption_overlap_and_bounds(self):
        self.run_c(r'''
static void reject(unsigned char *p, uint32_t size) {
  uint32_t n=1; assert(!team_commentary_apply_delta(base,sizeof(base),p,size,&n));
  assert(n==0);
}
int main(void) {
  unsigned char bad[sizeof(patch)+1];
  for (unsigned i=0;i<sizeof(patch);++i) reject(patch,i);
  // Magic, source identity, result identity, format/count/reserved fields.
  const unsigned offsets[]={0,8,12,16,24,32,36,40,44,52};
  for(unsigned i=0;i<sizeof(offsets)/sizeof(*offsets);++i) {
    memcpy(bad,patch,sizeof(patch)); bad[offsets[i]]^=0xff; reject(bad,sizeof(patch));
  }
  memcpy(bad,patch,sizeof(patch)); bad[sizeof(patch)]=0; reject(bad,sizeof(bad));
  memcpy(bad,patch,sizeof(patch)); memset(bad+40,0xff,4); reject(bad,sizeof(patch));
  memcpy(bad,patch,sizeof(patch)); memset(bad+44,0xff,4); reject(bad,sizeof(patch));
  memcpy(bad,patch,sizeof(patch)); memset(bad+52,0,4); reject(bad,sizeof(patch));
  base[31]=1; reject(patch,sizeof(patch));
  return 0;
}
''')

    def test_mount_lifetime_failure_fallback_and_repeat_matches(self):
        self.run_c(r'''
static int calls, rejected_patch, fail_unmount, reuse_on_unmount;
static int16_t reused_id;
static int16_t next_id=1;
static void *observed;
static uint32_t label_id;
static void label_stub(const void *c,char *l,const uint32_t *cap,const uint32_t *side,
    const uint32_t *id,uint32_t licensed,uint32_t edited,const uint32_t *type,
    const uint32_t *variation) {
  assert(c==(void*)4 && l==(char*)5 && *cap==256 && *side==1 && licensed==1);
  assert(edited<=1 && *type==2 && *variation==1); label_id=*id;
}
static int32_t mount_stub(void *data,uint32_t size,void *binder,const char *path,
    uint16_t flags,uint16_t search,int16_t *id) {
  assert(binder==(void*)3 && path && flags==65535 && search==0); ++calls;
  observed=data;
  if(data!=base) {
    assert(size==sizeof(target) && !memcmp(data,target,size));
    if(rejected_patch) return -2;
    // CRI is allowed to mutate its mounted work areas.
    ((unsigned char*)data)[31]=17;
  } else assert(size==sizeof(base));
  if(id) *id=next_id++;
  return 0;
}
static int32_t unmount_stub(int16_t id) {
  assert(id>0);
  if(reuse_on_unmount) {
    reuse_on_unmount=0; next_id=id;
    assert(!pes_sound_mount_data(base,sizeof(base),(void*)3,
        "sound/awb/00_TEAM.awb",65535,0,&reused_id));
    assert(observed!=base && reused_id==id);
  }
  return fail_unmount?-3:0;
}
int main(void) {
  (void)pes_sound_decode_hca_header;
  sound_team_name_label_original=label_stub;
  sound_mount_data_original=mount_stub;
  sound_unmount_data_original=unmount_stub;
  uint32_t cap=256,side=1,id=1164,type=2,variation=1;
  team_commentary_indonesia_slot=1;
  pes_sound_team_name_label((void*)4,(char*)5,&cap,&side,&id,1,0,&type,&variation);
  assert(label_id==5750 && id==1164);
  pes_sound_team_name_label((void*)4,(char*)5,&cap,&side,&id,1,1,&type,&variation);
  assert(label_id==1164);
  const char *path="cpk_snd/eng/sound/awb/00_TEAM.awb";
  int16_t mounted[5];
  for(unsigned i=0;i<5;++i) {
    assert(!pes_sound_mount_data(base,sizeof(base),(void*)3,path,65535,0,&mounted[i]));
    assert((observed==base)==(i==4));
  }
  fail_unmount=1; assert(pes_sound_unmount_data(mounted[0])==-3);
  assert(team_commentary_mounts[0].state==2 && team_commentary_mounts[0].data);
  fail_unmount=0;
  for(unsigned i=0;i<5;++i) assert(!pes_sound_unmount_data(mounted[i]));
  for(unsigned i=0;i<4;++i) assert(!team_commentary_mounts[i].state && !team_commentary_mounts[i].data);
  // Each rematch rebuilds from pristine source, with no stale CRI bytes.
  for(unsigned i=0;i<12;++i) {
    assert(!pes_sound_mount_data(base,sizeof(base),(void*)3,path,65535,0,&mounted[0]));
    assert(observed!=base); assert(!pes_sound_unmount_data(mounted[0]));
  }
  assert(!pes_sound_mount_data(base,sizeof(base),(void*)3,path,65535,0,&mounted[0]));
  reuse_on_unmount=1;
  assert(!pes_sound_unmount_data(mounted[0]));
  assert(team_commentary_mounts[1].state==2 && team_commentary_mounts[1].id==reused_id);
  assert(!pes_sound_unmount_data(reused_id));
  rejected_patch=1; int before=calls;
  assert(!pes_sound_mount_data(base,sizeof(base),(void*)3,path,65535,0,&mounted[0]));
  assert(calls==before+2 && observed==base && !team_commentary_mounts[0].state);
  rejected_patch=0; team_commentary_indonesia_slot=0;
  assert(!pes_sound_mount_data(base,sizeof(base),(void*)3,path,65535,0,&mounted[0]));
  assert(observed==base);
  team_commentary_indonesia_slot=1;
  assert(!pes_sound_mount_data(base,sizeof(base),(void*)3,"eng/sound/awb/10_PLAYER.awb",65535,0,&mounted[0]));
  assert(observed==base);
  return 0;
}
''', wrappers=True)

    def test_catalog_gate_and_native_hook_guards(self):
        self.assertIn("indonesia->physical_team_id == 1164u", HOOKS)
        self.assertIn("exhibition_team_catalog_logical(1164u) == 5750u", HOOKS)
        for name in ("team_name_label", "mount_data", "unmount_data", "hca_decode_header"):
            self.assertRegex(HOOKS, rf"!memcmp\(\(void \*\){name}_plt, expected_{name}_plt, 16\)")
        self.assertEqual(HOOKS.count("(uintptr_t)&pes_sound_mount_data)"), 1)

    def test_unknown_or_incomplete_hca_headers_are_not_reclassified(self):
        self.run_c(r'''
int main(void) {
  unsigned char data[128]={0};
  memcpy(data,"HCA\0\2\0\0\x60",8);
  assert(!team_commentary_plain_hca_header(NULL,0,NULL,0));
  assert(!team_commentary_plain_hca_header(data,-1,NULL,0));
  assert(!team_commentary_plain_hca_header(data,96,data,-1));
  for(int n=0;n<128;++n) {
    assert(!team_commentary_plain_hca_header(data,n,NULL,0));
    assert(!team_commentary_plain_hca_header(NULL,0,data,n));
    if(n<=96) assert(!team_commentary_plain_hca_header(data,n,data+n,96-n));
  }
}
''')


class CommentaryLocalAssetTests(unittest.TestCase):
    def recordings(self):
        path = Path(os.environ.get("PESNX_FL26_COMMENTARY_CPK",
                    "D:/Games/SP Football Life 2026/Data/dt41_eng_all.cpk"))
        if not path.is_file():
            self.skipTest("owned FL26 English commentary CPK unavailable")
        index, offset = index_cpk(path)
        return [read_awb_wave(path, index["eng/sound/awb/00_TEAM.awb"], offset, ident)
                for ident in (497, 1997)]

    def test_plaintext_correction_is_per_decoder_and_per_recording(self):
        a, b = self.recordings()
        body = c_array("a", a[:96]) + c_array("b", b[:96]) + r'''
static int clears, calls;
static void *expected_decoder;
static const void *expected_first, *expected_second;
static int64_t expected_n, expected_m;
static int32_t set_table(void *decoder,const void *table,int64_t size) {
  assert(decoder==expected_decoder && table==NULL && size==0); ++clears; return 0;
}
static int32_t decode(void *decoder,const void *first,int64_t n,
    const void *second,int64_t m,int64_t *consumed) {
  assert(decoder==expected_decoder && first==expected_first && second==expected_second);
  assert(n==expected_n && m==expected_m); ++calls; *consumed=123; return 9;
}
static void invoke(void *decoder,const void *first,int64_t n,
    const void *second,int64_t m,int expected_clears) {
  expected_decoder=decoder; expected_first=first; expected_second=second;
  expected_n=n; expected_m=m;
  int64_t consumed=0; int before=calls; clears=0;
  assert(pes_sound_decode_hca_header(decoder,first,n,second,m,&consumed)==9);
  assert(clears==expected_clears && calls==before+1 && consumed==123);
}
int main(void) {
  (void)pes_sound_team_name_label; (void)pes_sound_mount_data;
  (void)pes_sound_unmount_data;
  sound_hca_decode_header_original=decode; sound_hca_set_decryption_table=set_table;
  team_commentary_indonesia_slot=1;
  for(int i=0;i<4;++i) {
    team_commentary_mounts[i].state=2;
    for(int who=0;who<2;++who) {
      unsigned char *header=who?b:a;
      for(int split=0;split<=96;++split) {
        assert(team_commentary_plain_hca_header(header,split,header+split,96-split));
        invoke((void*)1,header,split,header+split,96-split,1);
      }
      invoke((void*)2,NULL,0,header,96,1);
      // Every truncation and any change (including cipher type) is refused.
      for(int n=0;n<96;++n) {
        invoke((void*)1,header,n,NULL,0,0);
        unsigned char old=header[n];header[n]^=1;
        invoke((void*)1,header,96,NULL,0,0);header[n]=old;
      }
    }
    team_commentary_mounts[i].state=0;
  }
  for(int state=0;state<2;++state) {
    team_commentary_mounts[0].state=state; invoke((void*)1,a,96,NULL,0,0);
  }
  team_commentary_mounts[0].state=2; team_commentary_indonesia_slot=0;
  invoke((void*)1,a,96,NULL,0,0);
  team_commentary_indonesia_slot=1; invoke(NULL,a,96,NULL,0,0);
}
'''
        CommentaryPolicyTests.run_c(self, body, wrappers=True)

    def test_native_hca_packet_reader_reproduces_and_fixes_plaintext_corruption(self):
        library = ROOT / "dist/pes21_nx/libUE4.so"
        if not library.is_file():
            self.skipTest("owned v5.3.0 library unavailable")
        try:
            from native_hca_probe import NativeHcaProbe
        except ImportError:
            self.skipTest("optional pyelftools/unicorn unavailable")
        # Isolate the optional native JIT from pytest's Windows exception
        # observer. A probe failure remains a failing child exit, and cannot
        # take down unrelated tests in the main process.
        if os.environ.get("PESNX_NATIVE_HCA_CHILD") != "1":
            environment = dict(os.environ, PESNX_NATIVE_HCA_CHILD="1")
            result = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                "CommentaryLocalAssetTests.test_native_hca_packet_reader_reproduces_and_fixes_plaintext_corruption",
                "-q"], env=environment, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("OK", result.stderr)
            return
        recordings = self.recordings()
        native = NativeHcaProbe(library)
        self.addCleanup(native.close)
        # Synthetic nonidentity permutation: no game cipher key is needed.
        cipher = native.alloc(256, bytes([0] + [255-x for x in range(1,255)] + [255]))
        work, out = native.alloc(0x10000), native.alloc(8)
        self.assertEqual(native.call(0x74bf6a8, 1, 1, work, 0x10000, out), 0)
        decoder = native.pointer(out)
        for hca in recordings:
            data = native.alloc(len(hca), hca)
            self.assertEqual(native.call(0x74bf970, decoder, cipher, 256), 0)
            self.assertEqual(native.call(0x74bf97c, decoder, data, 96, 0, 0, out), 0)
            self.assertEqual(native.pointer(decoder+0x108), cipher)
            frame_size = struct.unpack_from('>H',hca,0x1c)[0]
            self.assertEqual(native.call(0x74c0140,decoder,data+96,frame_size,0,0,out),0)
            packet = native.pointer(decoder+0xe8)
            self.assertNotEqual(bytes(native.uc.mem_read(packet,frame_size)),hca[96:96+frame_size])
            self.assertEqual(native.call(0x74bf970,decoder,0,0),0)
            frames = struct.unpack_from('>I',hca,0x10)[0]
            for i in range(frames):
                offset = 96+i*frame_size
                self.assertEqual(native.call(0x74c0140,decoder,data+offset,frame_size,0,0,out),0)
                self.assertEqual(bytes(native.uc.mem_read(packet,frame_size)),hca[offset:offset+frame_size])

    def test_local_candidate_preserves_other_cues_and_audio(self):
        mobile_path = ROOT / "dist/pes21_nx/Download/dt510_mobile_eng_all.cpk"
        fl26_path = Path(os.environ.get("PESNX_FL26_COMMENTARY_CPK",
                         "D:/Games/SP Football Life 2026/Data/dt41_eng_all.cpk"))
        patch_path = ROOT / "local-debug/indonesia-commentary-v7/Commentary/indonesia.nxcp"
        if not all(p.exists() for p in (mobile_path, fl26_path, patch_path)):
            self.skipTest("owned mobile/FL26 CPKs or staged local commentary delta unavailable")
        mobile, mb = mobile_index(mobile_path)
        fl26, fb = index_cpk(fl26_path)
        base = cpk_member(mobile_path, mobile, mb, "eng/sound/acb/00_TEAM.acb")
        source = cpk_member(fl26_path, fl26, fb, "eng/sound/acb/00_TEAM.acb")
        def wave_reader(ident):
            return read_awb_wave(fl26_path, fl26["eng/sound/awb/00_TEAM.awb"], fb, ident)
        patch = patch_path.read_bytes()
        rebuilt, report = build_patch(base, source, wave_reader)
        self.assertEqual(rebuilt, patch)
        def unknown_header(ident):
            payload = bytearray(wave_reader(ident))
            payload[16] ^= 1
            return bytes(payload)
        with self.assertRaisesRegex(ValueError, "unrecognized A1 HCA header"):
            build_patch(base, source, unknown_header)
        self.assertEqual(report["other_cues_preserved"], 45448)
        magic, size, output_size, base_hash, result_hash, count, reserved = HEADER.unpack_from(patch)
        self.assertEqual(size, len(base)); self.assertEqual(base_hash, fnv64(base))
        result = bytearray(base + bytes(output_size - size)); cursor = HEADER.size
        for _ in range(count):
            offset, length = struct.unpack_from("<II", patch, cursor); cursor += 8
            result[offset:offset + length] = patch[cursor:cursor + length]; cursor += length
        self.assertEqual(cursor, len(patch)); self.assertEqual(result_hash, fnv64(result))
        old, new = Utf(base), Utf(bytes(result))
        changed = (804, 4282)
        for name in ("SynthTable", "CommandTable", "TrackTable", "SequenceTable"):
            self.assertEqual(old.child(name).data, new.child(name).data)
        for field, value in old.rows[0].items():
            if field not in ("WaveformTable", "AwbFile"):
                self.assertEqual(new.rows[0][field], value, field)
        for i, (a, b) in enumerate(zip(old.child("CueTable").rows, new.child("CueTable").rows)):
            self.assertEqual(a if i not in changed else {**a, "Length": (890 if i==804 else 669)}, b)
        before_waves = old.child("WaveformTable").rows
        after_waves = new.child("WaveformTable").rows
        self.assertEqual(len(before_waves),len(after_waves))
        for i, (a, b) in enumerate(zip(before_waves, after_waves)):
            if i not in changed:
                self.assertEqual(a,b)
            else:
                self.assertEqual(b["Streaming"],0)
                self.assertEqual(b["NumSamples"],42711 if i==804 else 32128)
        names = new.child("CueNameTable").rows
        self.assertEqual([r["CueName"] for r in names], sorted(r["CueName"] for r in names))
        expected = {r["CueName"]:r["CueIndex"] for r in old.child("CueNameTable").rows}
        for speaker in ("A1","B1"):
            expected[f"EN_{speaker}_T0_R5750"] = expected.pop(f"EN_{speaker}_T0_R1164")
        self.assertEqual({r["CueName"]:r["CueIndex"] for r in names}, expected)
        awb = new.blob(0,"AwbFile")
        self.assertEqual(awb, memory_awb([(804,wave_reader(497)), (4282,wave_reader(1997))]))

    def test_supported_elf_plt_fingerprints(self):
        binary = ROOT / "dist/pes21_nx/libUE4.so"
        if not binary.exists():
            self.skipTest("ignored user-owned libUE4.so unavailable")
        try:
            from elftools.elf.elffile import ELFFile
        except ImportError:
            self.skipTest("optional pyelftools unavailable")
        with binary.open('rb') as stream:
            elf = ELFFile(stream)
            for name in ("team_name_label", "mount_data", "unmount_data", "hca_decode_header"):
                address = int(re.search(rf"const uintptr_t {name}_plt = .*?\+ (0x[0-9a-f]+);",HOOKS)[1],16)
                words = re.search(rf"expected_{name}_plt\[4\] = \{{(.*?)\}};",HOOKS,re.S)[1]
                expected = struct.pack('<4I',*(int(s,16) for s in re.findall(r'0x[0-9a-f]+',words)))
                stream.seek(next(elf.address_offsets(address)))
                self.assertEqual(stream.read(16),expected,name)


if __name__ == "__main__":
    unittest.main()
