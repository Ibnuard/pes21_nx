"""Player-bank ownership and plaintext playback policy, using production code."""
from pathlib import Path
import json
import os
import shutil
import struct
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from stage_indonesia_commentary import Utf, mobile_index, cpk_member


def compile_run(tmp_path, body, *, wrappers=False):
    compiler = shutil.which("gcc") or shutil.which("clang")
    if not compiler:
        pytest.skip("host C compiler required")
    header = (ROOT / "source/player_commentary_policy.h").as_posix()
    source = f'#include <assert.h>\n#include "{header}"\n'
    source += '#define scene_runtime_note(a,b) ((void)0)\n'
    if wrappers:
        source += f'#include "{(ROOT / "source/trophy_audio_policy.h").as_posix()}"\n'
        hooks = (ROOT / "source/ue4_hooks.c").read_text(encoding="utf8")
        first = hooks.index("static uint32_t team_commentary_indonesia_slot;")
        last = hooks.index("\n#ifdef DEBUG_LOG\nstatic int32_t (*sound_cinf_play_original)", first)
        source += hooks[first:last]
    path, executable = tmp_path / "player.c", tmp_path / "player.exe"
    path.write_text(source + body, encoding="utf8")
    built = subprocess.run([compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                            str(path), "-o", str(executable)], capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([str(executable)], cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert ran.returncode == 0, ran.stdout + ran.stderr


@pytest.fixture(scope="module")
def owned_bank():
    folder = Path(os.environ.get("PESNX_PLAYER_COMMENTARY_CANDIDATE",
                                ROOT / "local-debug/player-commentary-v53/staged-final"))
    patch = folder / "Commentary/players-yamal-raphinha.nxcp"
    mobile = ROOT / "dist/pes21_nx/Download/dt510_mobile_eng_all.cpk"
    if not patch.is_file() or not mobile.is_file():
        pytest.skip("owned Mobile bank and staged player-commentary candidate required")
    index, offset = mobile_index(mobile)
    base = cpk_member(mobile, index, offset, "eng/sound/acb/10_PLAYER.acb")
    delta = patch.read_bytes()
    assert delta[:8] == b"NXCMT01\0" and struct.unpack_from("<II", delta, 40) == (0, len(delta) - 48)
    result = Utf(delta[48:])
    awb = result.blob(0, "AwbFile")
    width, id_width = awb[5:7]
    count, align = struct.unpack_from("<IH", awb, 8)
    ids = [int.from_bytes(awb[16+i*id_width:16+(i+1)*id_width], "little") for i in range(count)]
    start = 16 + count * id_width
    offsets = [int.from_bytes(awb[start+i*width:start+(i+1)*width], "little") for i in range(count+1)]
    recordings = {ident: awb[(offsets[i]+align-1)//align*align:offsets[i+1]] for i, ident in enumerate(ids)}
    assert len(recordings) == 27
    return base, delta, list(recordings.values())


def test_large_player_limit_does_not_relax_team_policy(tmp_path):
    compile_run(tmp_path, r'''
static void u32(unsigned char *p,uint32_t v) { for(int i=0;i<4;i++)p[i]=v>>(i*8); }
static void u64(unsigned char *p,uint64_t v) { for(int i=0;i<8;i++)p[i]=v>>(i*8); }
int main(void) {
  assert(player_commentary_catalog_active(PLAYER_COMMENTARY_RUNTIME_PAIR));
  assert(!player_commentary_catalog_active("unknown") && !player_commentary_catalog_active(NULL));
  assert(player_commentary_is_bank("eng/sound/awb/10_PLAYER.awb"));
  assert(!player_commentary_is_bank("10_PLAYER.awb.bak") && !player_commentary_is_bank(NULL));
  assert(!player_commentary_is_bank("00_TEAM.awb"));
  unsigned char base[64]={0}; memcpy(base,"@UTF",4);base[7]=56;
  const uint32_t size=2u*1024u*1024u;
  unsigned char *delta=calloc(1,size+48); assert(delta);
  memcpy(delta,"NXCMT01\0",8);u32(delta+8,64);u32(delta+12,size);
  u64(delta+16,team_commentary_hash(base,64));u32(delta+32,1);u32(delta+44,size);
  memcpy(delta+48,base,64);delta[52]=(size-8)>>24;delta[53]=(size-8)>>16;
  delta[54]=(unsigned char)((size-8)>>8);delta[55]=(unsigned char)(size-8);
  u64(delta+24,team_commentary_hash(delta+48,size));
  uint32_t n=123;
  assert(!team_commentary_apply_delta(base,64,delta,size+48,&n) && !n);
  void *result=commentary_apply_delta_bounded(base,64,delta,size+48,PLAYER_COMMENTARY_MAX_PATCH,&n);
  assert(result && n==size);free(result);
  /* Even a valid synthetic delta cannot claim the pinned player catalog. */
  assert(!player_commentary_apply_delta(base,64,delta,size+48,&n) && !n);
  delta[48+60]^=1;
  assert(!commentary_apply_delta_bounded(base,64,delta,size+48,PLAYER_COMMENTARY_MAX_PATCH,&n) && !n);
  free(delta);return 0;
}
''')


def test_owned_player_mount_rematches_failures_and_slot_limit(tmp_path, owned_bank):
    base, delta, _ = owned_bank
    (tmp_path / "base.acb").write_bytes(base)
    (tmp_path / "Commentary").mkdir()
    (tmp_path / "Commentary/players-v53.nxcp").write_bytes(delta)
    compile_run(tmp_path, r'''
static void *base; static uint32_t base_size;
static int next_id,fail_mount,fail_unmount,patch_calls,base_calls,unmounts;
static int32_t mount(void *data,uint32_t size,void *binder,const char *path,
    uint16_t flags,uint16_t search,int16_t *id) {
  assert(binder==(void*)9 && flags==3 && search==4 && path);
  if(data==base) { assert(size==base_size);++base_calls; }
  else { assert(size==PLAYER_COMMENTARY_RESULT_BYTES);++patch_calls;if(fail_mount)return -2; }
  *id=next_id++;return 0;
}
static int32_t unmount(int16_t id) { (void)id;++unmounts;return fail_unmount?-3:0; }
static int load(const char *path) {
  int16_t id=-1;assert(!pes_sound_mount_data(base,base_size,(void*)9,path,3,4,&id));return id;
}
int main(void) {
  (void)pes_sound_team_name_label;(void)pes_sound_decode_hca_header;
  FILE *f=fopen("base.acb","rb");assert(f);base_size=PLAYER_COMMENTARY_BASE_BYTES;
  base=malloc(base_size);assert(base && fread(base,1,base_size,f)==base_size);fclose(f);
  sound_mount_data_original=mount;sound_unmount_data_original=unmount;
  int id=load("10_PLAYER.awb");assert(base_calls==1 && !patch_calls);pes_sound_unmount_data(id);
  player_commentary_enabled=1;
  id=load("10_PLAYER.awb");assert(patch_calls==1 && player_commentary_mounts[0].state==2);
  fail_unmount=1;assert(pes_sound_unmount_data(id)==-3 && player_commentary_mounts[0].state==2);
  fail_unmount=0;assert(!pes_sound_unmount_data(id) && !player_commentary_mounts[0].state);
  fail_mount=1;id=load("10_PLAYER.awb");assert(base_calls==2 && patch_calls==2);
  assert(!player_commentary_mounts[0].state);pes_sound_unmount_data(id);fail_mount=0;
  int ids[5];for(int i=0;i<5;i++)ids[i]=load("eng/sound/awb/10_PLAYER.awb");
  assert(base_calls==3 && patch_calls==6);
  for(int i=0;i<4;i++)assert(player_commentary_mounts[i].state==2 && !team_commentary_mounts[i].state);
  for(int i=0;i<5;i++)assert(!pes_sound_unmount_data(ids[i]));
  for(int i=0;i<8;i++) { id=load("10_PLAYER.awb");assert(!pes_sound_unmount_data(id)); }
  base_calls=patch_calls=0;
  id=load("other/10_PLAYER.awb.bak");assert(base_calls==1 && !patch_calls);pes_sound_unmount_data(id);
  assert(!rename("Commentary/players-v53.nxcp","Commentary/held"));
  id=load("10_PLAYER.awb");assert(base_calls==2 && !patch_calls);pes_sound_unmount_data(id);
  assert(!rename("Commentary/held","Commentary/players-v53.nxcp"));
  ((unsigned char*)base)[40]^=1;
  id=load("10_PLAYER.awb");assert(base_calls==3 && !patch_calls);pes_sound_unmount_data(id);
  free(base);return 0;
}
''', wrappers=True)


def test_owned_plaintext_policy_all_splits_corruption_and_mount_isolation(tmp_path, owned_bank):
    _, _, recordings = owned_bank
    values = ",".join("{" + ",".join(str(x) for x in recording[:96]) + "}" for recording in recordings)
    code = 'static unsigned char headers[27][96]={' + values + '};\n' + r'''
static int clears,calls;static void *who;
static int32_t clear(void *decoder,const void *table,int64_t size) {
  assert(decoder==who && !table && !size);++clears;return 0;
}
static int32_t decode(void *decoder,const void *a,int64_t n,const void *b,int64_t m,int64_t *used) {
  (void)a;(void)n;(void)b;(void)m;assert(decoder==who);++calls;*used=123;return 7;
}
static void invoke(void *decoder,unsigned char *h,int split,int expect) {
  who=decoder;int before=clears;int64_t used=0;
  assert(pes_sound_decode_hca_header(decoder,h,split,h+split,96-split,&used)==7);
  assert(clears==before+expect && used==123);
}
int main(void) {
  (void)pes_sound_team_name_label;(void)pes_sound_mount_data;(void)pes_sound_unmount_data;
  sound_hca_decode_header_original=decode;sound_hca_set_decryption_table=clear;
  player_commentary_enabled=1;
  for(int slot=0;slot<4;slot++) {
    player_commentary_mounts[slot].state=2;
    for(int i=0;i<27;i++) {
      for(int split=0;split<=96;split++)invoke((void*)1,headers[i],split,1);
      for(int byte=0;byte<96;byte++) {
        assert(!player_commentary_plain_hca_header(headers[i],byte,NULL,0));
        headers[i][byte]^=1;invoke((void*)1,headers[i],96,0);headers[i][byte]^=1;
      }
    }
    player_commentary_mounts[slot].state=0;
  }
  team_commentary_indonesia_slot=1;team_commentary_mounts[0].state=2;
  invoke((void*)1,headers[0],96,0); /* Team mounts never approve player audio. */
  player_commentary_mounts[0].state=1;invoke((void*)1,headers[0],96,0);
  player_commentary_mounts[0].state=2;player_commentary_enabled=0;invoke((void*)1,headers[0],96,0);
  player_commentary_enabled=1;invoke(NULL,headers[0],96,0);return 0;
}
'''
    compile_run(tmp_path, code, wrappers=True)


def test_owned_native_packets_and_player_id_path(owned_bank):
    # Run the native JIT in a child, outside pytest's Windows fault observer.
    env = os.environ.copy()
    env.pop("PYTHONFAULTHANDLER", None)
    ran = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "--native"],
                         env=env, capture_output=True, text=True, timeout=90)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert "27 plaintext recordings and native player IDs: pass" in ran.stdout


def test_selected_mount_clone_report_header_scope_and_reused_id(tmp_path):
    compile_run(tmp_path, r'''
static unsigned char header[96];
static int clears, mounts, reports, releases, outcome, fail_selected, fail_unmount;
static const void *original;
static int32_t mount(void *data,uint32_t bytes,void *binder,const char *path,
    uint16_t flags,uint16_t search,int16_t *id) {
  (void)binder;(void)path;(void)flags;(void)search;assert(bytes==64);++mounts;
  if(data!=original && fail_selected)return -1;
  *id=7;return 0;
}
static int32_t unmount(int16_t id) { assert(id==7);return fail_unmount?-1:0; }
static int32_t clear(void *d,const void *t,int64_t n) {
  assert(d && !t && !n);++clears;return 0;
}
static int32_t decode(void *d,const void *a,int64_t n,const void *b,int64_t m,int64_t *used) {
  (void)d;(void)a;(void)n;(void)b;(void)m;*used=96;return 0;
}
static void *clone(const void *base,uint32_t size,PlayerCommentaryMountedPolicy *p,
                    uint32_t *bytes,void **lease) {
  assert(base==original && size==64);
  void *copy=malloc(64);assert(copy);memcpy(copy,base,64);*bytes=64;*lease=malloc(1);
  p->generation=123;p->bank.data=copy;p->bank.size=64;p->bank.header_count=1;
  p->bank.headers[0]=team_commentary_hash(header,96);return copy;
}
static void observe(void *lease,int16_t id,unsigned variant) {
  assert(lease && id==7);++reports;outcome=(int)variant;free(lease);++releases;
}
static void invoke(int expected) {
  int before=clears;int64_t used=0;
  assert(!pes_sound_decode_hca_header((void*)1,header,35,header+35,61,&used));
  assert(clears==before+expected && used==96);
}
int main(void) {
  (void)pes_sound_team_name_label;
  unsigned char base[64]={0};memcpy(base,"@UTF",4);original=base;
  for(unsigned i=0;i<96;i++)header[i]=(unsigned char)(i+11);
  sound_mount_data_original=mount;sound_unmount_data_original=unmount;
  sound_hca_decode_header_original=decode;sound_hca_set_decryption_table=clear;
  player_commentary_roster_clone_for_mount=clone;
  player_commentary_roster_mount_observe=observe;player_commentary_enabled=1;
  int16_t id=-1;invoke(0);
  assert(!pes_sound_mount_data(base,64,NULL,"10_PLAYER.awb",0,0,&id));
  assert(id==7 && reports==1 && releases==1 && outcome==0 && mounts==1);
  TeamCommentaryMount *slot=player_commentary_mounts;
  assert(slot->state==2 && slot->roster.lookup.accepted==PC_LOOKUP_ACCEPTED);
  for(unsigned split=0;split<=96;split++)
    assert(player_commentary_roster_header_mounted(header,split,header+split,96-split));
  header[40]^=1;invoke(0);header[40]^=1;invoke(1);
  assert(!player_commentary_roster_header_mounted(header,-1,NULL,0));
  assert(!player_commentary_roster_header_mounted(header,95,NULL,0));
  fail_unmount=1;assert(pes_sound_unmount_data(7)==-1);invoke(1);
  fail_unmount=0;assert(!pes_sound_unmount_data(7));invoke(0);
  assert(!slot->roster.generation && !slot->data && !slot->state);
  /* A reused native ID must carry a fresh slot and independent buffer. */
  assert(!pes_sound_mount_data(base,64,NULL,"10_PLAYER.awb",0,0,&id));
  assert(reports==2 && outcome==0);assert(!pes_sound_unmount_data(id));
  /* A failed replacement retries unchanged native arguments and retires policy. */
  fail_selected=1;
  assert(!pes_sound_mount_data(base,64,NULL,"10_PLAYER.awb",0,0,&id));
  assert(reports==3 && releases==3 && outcome==2 && mounts==4);
  invoke(0);assert(!slot->state && !slot->roster.generation);return 0;
}
''', wrappers=True)


if __name__ == "__main__":
    assert sys.argv[1:] == ["--native"]
    from native_hca_probe import NativeHcaProbe
    from unicorn.arm64_const import UC_ARM64_REG_X0
    _, _, recordings = owned_bank.__wrapped__()
    native = NativeHcaProbe(ROOT / "dist/pes21_nx/libUE4.so")
    try:
        cipher = native.alloc(256, bytes([0] + [255-x for x in range(1,255)] + [255]))
        work, out = native.alloc(0x10000), native.alloc(8)
        assert native.call(0x74bf6a8, 1, 1, work, 0x10000, out) == 0
        decoder = native.pointer(out)
        for hca in recordings:
            data = native.alloc(len(hca), hca)
            assert native.call(0x74bf970, decoder, cipher, 256) == 0
            assert native.call(0x74bf97c, decoder, data, 96, 0, 0, out) == 0
            frame_size, frames = struct.unpack_from('>H', hca, 0x1c)[0], struct.unpack_from('>I', hca, 0x10)[0]
            assert native.call(0x74bf970, decoder, 0, 0) == 0
            for frame in (0, frames//2, frames-1):
                offset = 96 + frame * frame_size
                assert native.call(0x74c0140, decoder, data+offset, frame_size, 0, 0, out) == 0
                packet = native.pointer(decoder+0xe8)
                assert bytes(native.uc.mem_read(packet, frame_size)) == hca[offset:offset+frame_size]
        for player in (110644, 162114, 8957, 12345):
            raw = player << 32 | 0x1234
            native.call(0x6cfb944, raw)
            assert native.uc.reg_read(UC_ARM64_REG_X0) >> 32 == player
            assert native.call(0x6cfb968, player) == player
        print("27 plaintext recordings and native player IDs: pass")
    finally:
        native.close()
