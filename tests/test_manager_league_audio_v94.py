"""Owned event timing, native ABI/mount lifetime, and exact generic recordings."""
from pathlib import Path
import hashlib
import json
import os
import re
import struct
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tests")]
import stage_manager_league_audio as audio
from stage_indonesia_commentary import Utf, fnv64
from test_trophy_audio_v88 import compile_run

FOLDER = ROOT / "local-debug/manager-league-v94/audio/stage-02"
LIBRARY_SHA = "a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187"
CHECKS = [(0x77e4c90, 0x10, 0x9bdd49ca07a9b0c3),
          (0x6cfff3c, 0x88, 0x1754719cc571d7a7),
          (0x6d003e8, 0x1c, 0xf6ff621af0d3a391),
          (0x6d004ec, 0x44, 0xaf5dcafef3170be3),
          (0x6d00480, 0x20, 0x8b2db63ac314e144),
          (0x77e4b48, 0x14, 0xc9d04bf96671de06)]


def local_bank():
    path = FOLDER / audio.ASSET
    if not path.exists():
        pytest.skip("ignored staged own-source Manager League HCA bank required")
    return path.read_bytes(), json.loads((FOLDER / "AUDIO-REPORT.json").read_text())


HARNESS = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "manager_league_audio_policy.h"
static unsigned plays[MLA_CLIP_COUNT],stops,fail_play,fail_stop,publish_failed_handle;
static uint64_t serial;
static int play(void *ctx,uint32_t clip,uint64_t *out) {
 (void)ctx;assert(clip<MLA_CLIP_COUNT);++plays[clip];
 *out=fail_play&&!publish_failed_handle?0:++serial;return fail_play?-7:0;
}
static int stop(void *ctx,uint64_t handle,uint32_t fade) {
 (void)ctx;assert(handle&&fade==100);++stops;return fail_stop?-9:0;
}
static uint32_t duration(void *ctx,uint32_t clip) {
 (void)ctx;if(clip==MLA_SPEECH_HALF_TIME||clip==MLA_SPEECH_FULL_TIME||clip==MLA_SPEECH_KICKOFF)return 0;
 return clip==MLA_BED?21000:1000;
}
static ManagerLeagueAudioPolicy p;
static ManagerLeagueAudioFrame f;
static void reset(void) {
 memset(&p,0,sizeof(p));memset(&f,0,sizeof(f));memset(plays,0,sizeof(plays));
 stops=fail_play=fail_stop=publish_failed_handle=0;serial=0;
 p.ops=(ManagerLeagueAudioOps){play,stop,duration,0};
 f=(ManagerLeagueAudioFrame){.fixture_token=11,.visible_watch=1,.monotonic_ms=10000};
 manager_league_audio_step(&p,&f);assert(plays[MLA_BED]==1);
}
static void event(uint32_t kind,uint32_t serial,uint32_t at) {
 f.monotonic_ms=10000+at;f.position_ms=at;f.event_at_ms=at;
 f.event_serial=serial;f.event_kind=kind;manager_league_audio_step(&p,&f);
}
'''


def test_live_events_are_coherent_once_only_and_goal_interrupts(tmp_path):
    compile_run(tmp_path, HARNESS + r'''
int main(void){reset();event(MLA_SHOT,1,500);
 assert(plays[MLA_BALL_SHOT]==1&&plays[MLA_SPEECH_SHOT]==1);
 event(MLA_SHOT,1,600);assert(plays[MLA_SPEECH_SHOT]==1);
 event(MLA_FOUL,2,800);assert(!plays[MLA_SPEECH_FOUL]&&p.dropped_speech==1);
 event(MLA_GOAL,3,1100);assert(plays[MLA_CROWD_GOAL]==1&&plays[MLA_SPEECH_GOAL]==1);
 assert(stops==2); /* previous effect and obsolete shot speech */
 for(unsigned i=0;i<10;++i)manager_league_audio_step(&p,&f);
 assert(plays[MLA_SPEECH_GOAL]==1);
 event(MLA_HALF_TIME,4,1400);assert(!plays[MLA_SPEECH_HALF_TIME]);
 return 0;}
''')


def test_replay_only_crowd_ball_and_exit_stops_all(tmp_path):
    compile_run(tmp_path, HARNESS + r'''
int main(void){reset();event(MLA_CORNER,1,500);assert(plays[MLA_SPEECH_CORNER]==1);
 f.replay=1;f.timeline_serial++;manager_league_audio_step(&p,&f);
 assert(!p.speech.handle);event(MLA_GOAL,2,900);
 assert(plays[MLA_CROWD_GOAL]==1&&!plays[MLA_SPEECH_GOAL]);
 event(MLA_PASS,3,1300);assert(plays[MLA_BALL_PASS]==1);
 f.visible_watch=0;manager_league_audio_step(&p,&f);
 assert(!p.bed.handle&&!p.effect.handle&&!p.speech.handle);
 unsigned n=stops;manager_league_audio_step(&p,&f);assert(stops==n);
 return 0;}
''')


def test_late_seek_pause_backwards_and_new_fixture_drop_history(tmp_path):
    compile_run(tmp_path, HARNESS + r'''
int main(void){reset();event(MLA_GOAL,1,500);assert(plays[MLA_SPEECH_GOAL]==1);
 f.timeline_serial++;f.position_ms=30000;f.event_at_ms=10000;f.event_serial=10;
 f.monotonic_ms+=500;manager_league_audio_step(&p,&f);
 assert(!p.speech.handle&&plays[MLA_SPEECH_GOAL]==1);
 f.event_serial++;manager_league_audio_step(&p,&f);assert(p.stale_events==1);
 f.paused=1;manager_league_audio_step(&p,&f);assert(!p.bed.handle);
 f.paused=0;f.event_kind=MLA_GOAL;f.event_at_ms=f.position_ms;
 manager_league_audio_step(&p,&f);assert(plays[MLA_SPEECH_GOAL]==1);
 f.fixture_token++;manager_league_audio_step(&p,&f);assert(!p.speech.handle);
 f.monotonic_ms--;manager_league_audio_step(&p,&f);assert(!p.speech.handle);
 return 0;}
''')


def test_stop_failure_retains_handles_and_failed_start_never_leaks(tmp_path):
    compile_run(tmp_path, HARNESS + r'''
int main(void){reset();event(MLA_SHOT,1,500);uint64_t old=p.speech.handle;
 fail_stop=1;f.visible_watch=0;manager_league_audio_step(&p,&f);
 assert(p.stop_failed&&p.speech.handle==old);unsigned n=serial;
 fail_stop=0;f.visible_watch=1;event(MLA_GOAL,2,900);assert(serial==n);
 reset();fail_play=1;publish_failed_handle=1;event(MLA_SHOT,1,500);
 assert(!p.speech.handle&&!p.effect.handle&&stops==2);
 reset();fail_play=1;event(MLA_SHOT,1,500);assert(stops==0);
 return 0;}
''')


def test_original_looped_bed_has_no_timer_restart_and_flood_is_bounded(tmp_path):
    compile_run(tmp_path, HARNESS + r'''
int main(void){reset();for(unsigned at=1000;at<=30000;at+=1000){
 f.monotonic_ms=10000+at;f.position_ms=at;manager_league_audio_step(&p,&f);}
 assert(plays[MLA_BED]==1&&p.bed.until_ms==UINT64_MAX);
 event(MLA_GOAL,1,30100);event(MLA_GOAL,2,30101);event(MLA_GOAL,3,30102);
 assert(plays[MLA_SPEECH_GOAL]==1&&p.stale_events==2);
 return 0;}
''')


def test_current_live_kickoff_speech_is_once_only_and_replay_never_announces(tmp_path):
    audible=HARNESS.replace('||clip==MLA_SPEECH_KICKOFF','')
    compile_run(tmp_path,audible+r'''
int main(void){(void)event;reset();assert(plays[MLA_SPEECH_KICKOFF]==1);
 f.paused=1;manager_league_audio_step(&p,&f);f.paused=0;
 f.position_ms=500;f.monotonic_ms+=500;manager_league_audio_step(&p,&f);
 assert(plays[MLA_SPEECH_KICKOFF]==1);
 f.fixture_token++;f.replay=1;f.timeline_serial++;f.position_ms=0;
 manager_league_audio_step(&p,&f);assert(plays[MLA_SPEECH_KICKOFF]==1);
 f.fixture_token++;f.replay=0;f.position_ms=5000;
 manager_league_audio_step(&p,&f);assert(plays[MLA_SPEECH_KICKOFF]==1);
 f.position_ms=0;f.timeline_serial++;manager_league_audio_step(&p,&f);
 assert(plays[MLA_SPEECH_KICKOFF]==1);return 0;}
''')


def native_bodies():
    library = ROOT / "dist/pes21_nx/libUE4.so"
    if not library.exists():
        pytest.skip("ignored pinned native library required")
    with library.open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == LIBRARY_SHA
        from elftools.elf.elffile import ELFFile
        elf = ELFFile(stream)
        segments = [s for s in elf.iter_segments() if s["p_type"] == "PT_LOAD"]
        bodies = []
        for rva, size, expected in CHECKS:
            segment = next(s for s in segments if s["p_vaddr"] <= rva < s["p_vaddr"]+s["p_filesz"])
            stream.seek(segment["p_offset"]+rva-segment["p_vaddr"])
            body = stream.read(size)
            assert fnv64(body) == expected
            bodies.append(body)
        return bodies


def test_actual_native_full_body_guards_and_unchanged_trophy_route():
    native_bodies()
    text = (ROOT / "source/manager_league_audio_runtime.inc").read_text()
    assert "PlayBgm" not in text and "SetCategoryVolume" not in text
    assert "AllocateWaveVoicePool" not in text and "SetGameOptionVolume" not in text
    assert "mla_native_play(mla_clips[clip].cue, handle, 0, 0, 0)" in text
    assert "__atomic_store_n(&mla_mounted, 1u, __ATOMIC_RELEASE)" in text


def test_bank_graph_exact_original_payloads_review_binding_and_decode(tmp_path):
    bank, report = local_bank()
    assert hashlib.sha256(bank).hexdigest() == report["bank_sha256"]
    assert audio.catalog(bank, [{"spec": s, "duration_ms": s["duration_ms"],
        "audio": audio.awb_recording(Utf(bank).blob(0, "AwbFile"), i)}
        for i,s in enumerate(report["clips"])]) == (FOLDER / "manager_league_audio_catalog.h").read_text()
    review_path = FOLDER.parent / "RECORDING-REVIEW.json"
    assert hashlib.sha256(review_path.read_bytes()).hexdigest() == report["review_sha256"]
    originals = []
    sources = {}
    for spec in report["clips"]:
        if spec["cpk"] not in sources:
            sources[spec["cpk"]] = audio.Cpk(Path("D:/Games/SP Football Life 2026/Data")/spec["cpk"])
        originals.append(audio.source_clip(sources[spec["cpk"]],spec))
    audio.verify_bank(bank, originals)
    import imageio_ffmpeg
    import numpy as np
    decoded = []
    for clip in originals:
        path = tmp_path / (clip["spec"]["role"] + ".hca")
        path.write_bytes(clip["audio"])
        ran = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-nostdin", "-v", "error", "-xerror",
            "-i", str(path), "-f", "f32le", "-"], capture_output=True, timeout=40)
        assert ran.returncode == 0, ran.stderr
        pcm = np.frombuffer(ran.stdout,"<f4")
        assert len(pcm) and np.all(np.isfinite(pcm))
        count = len(pcm)//clip["wave"]["NumChannels"]
        frames = struct.unpack_from(">I", clip["audio"], 16)[0]
        # FFmpeg emits all HCA blocks, including original encoder padding and
        # the tail beyond a looping bed's native loop endpoint. Keep both exact.
        assert count == frames * 1024
        assert count >= clip["wave"]["NumSamples"]
        decoded.append({"role": clip["spec"]["role"], "samples_per_channel": count,
            "source_peak": float(np.max(np.abs(pcm))), "gain": audio.GAINS.get(clip["spec"]["role"],.65),
            "pcm_sha256": hashlib.sha256(ran.stdout).hexdigest()})
    assert report["unavailable_roles"] == ["half_time", "full_time"]
    (FOLDER / "DECODE-PROOF.json").write_text(json.dumps({"decoded": decoded,
        "recordings_reencoded": False, "audio_device_executed": False},indent=2)+"\n")


def test_native_runtime_owner_mount_lifetime_split_headers_and_stale_timeout(tmp_path):
    bank = (ROOT / "local-debug/manager-review-v95/audio/stage-01/Audio/manager-league-v95.acb").read_bytes()
    bodies = native_bodies()
    top = Utf(bank)
    header = audio.awb_recording(top.blob(0,"AwbFile"),0)[:96]
    arrays = "\n".join("static const uint8_t body%d[]={%s};" % (i, ",".join(map(str,b)))
                       for i,b in enumerate(bodies))
    copies = "\n".join(f"memcpy(backing+{rva}u,body{i},sizeof(body{i}));" for i,(rva,_,_) in enumerate(CHECKS))
    code = r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
typedef struct {uint8_t *load_base;} so_module;
static unsigned mounts,plays,stops,reads;
static uint64_t next_handle=10;
static int bad_bank,stop_result,status_result;
static uint32_t guard_index;
static const uint32_t rvas[]={0x77e4c90,0x6cfff3c,0x6d003e8,0x6d004ec,0x6d00480,0x77e4b48};
static uintptr_t so_try_find_addr_rx(so_module *m,const char *n) {
 (void)m;(void)n;return UINT64_C(0x80000000)+rvas[guard_index];}
static uintptr_t so_find_addr(so_module *m,const char *n) {
 (void)n;return (uintptr_t)m->load_base+rvas[guard_index++];}
static void scene_runtime_note(const char *a,const char *b){(void)a;(void)b;}
static void *nx_asset_read(const char *n,uint32_t max,size_t *size) {
 assert(!strcmp(n,"Audio/manager-league-v95.acb")&&max==4194304);++reads;
 FILE *f=fopen(BANK_PATH,"rb");assert(f);fseek(f,0,SEEK_END);*size=ftell(f);rewind(f);
 uint8_t *b=malloc(*size);assert(fread(b,1,*size,f)==*size);fclose(f);if(bad_bank)b[0]^=1;return b;
}
#include "manager_league_audio_runtime.inc"
static int32_t mount_stub(void *p,uint32_t n,void *w,const char *s,int16_t *id){
 assert(p&&n==MLA_BANK_BYTES&&!w&&!s);++mounts;*id=9;return 0;}
static int32_t play_stub(const char *n,uint64_t *h,int32_t a,int32_t b,uint32_t c){
 assert(n&&h&&!a&&!b&&!c);++plays;*h=++next_handle;return 0;}
static int32_t stop_stub(uint64_t h,int32_t f,int32_t z){assert(h&&f==100&&!z);++stops;return stop_result;}
static int32_t existing_stub(const char *n){assert(n);return 1;}
static int32_t status_stub(uint64_t h,uint32_t *s){assert(h&&s);*s=0;return status_result;}
static int32_t position_stub(uint64_t h,int64_t *p){assert(h&&p);*p=100;return status_result;}
int main(void){
 uint8_t *backing=calloc(1,0x7800000u);assert(backing);so_module m={backing};BODY_COPIES
 manager_league_audio_native_install(&m,"wrong");assert(!mla_ready&&!mounts);
 manager_league_audio_native_install(&m,"a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187");
 assert(mla_ready&&!mounts&&!reads&&(uintptr_t)mla_native_play==UINT64_C(0x86cfff3c));
 mla_native_mount=mount_stub;mla_native_play=play_stub;mla_native_stop=stop_stub;
 mla_native_existing=existing_stub;mla_native_status=status_stub;mla_native_position=position_stub;
 uint8_t hca[96]={HEADER_BYTES};
 assert(!manager_league_audio_plain_hca_header(hca,96,NULL,0));
 ManagerLeagueAudioFrame f={.fixture_token=9,.visible_watch=1,.monotonic_ms=10000};
 manager_league_audio_publish(&f);assert(!mounts&&!plays);manager_league_audio_native_pump(10000);
 assert(mounts==1&&reads==1&&plays==2);
 assert(manager_league_audio_plain_hca_header(hca,96,NULL,0));
 for(unsigned i=0;i<=96;++i)assert(manager_league_audio_plain_hca_header(hca,i,hca+i,96-i));
 for(unsigned i=0;i<96;++i){hca[i]^=1;assert(!manager_league_audio_plain_hca_header(hca,96,NULL,0));hca[i]^=1;}
 assert(!manager_league_audio_plain_hca_header(hca,95,NULL,0));
 f.monotonic_ms=10500;f.position_ms=f.event_at_ms=500;f.event_serial=1;f.event_kind=MLA_SHOT;
 manager_league_audio_publish(&f);manager_league_audio_native_pump(10500);assert(plays==3&&mounts==1);
 manager_league_audio_native_pump(13000);assert(!mla_policy.speech.handle&&!mla_policy.bed.handle);
 stop_result=status_result=(int32_t)0x80000010u;assert(!mla_stop(NULL,123,100));
 status_result=-7;assert(mla_stop(NULL,123,100));
 manager_league_audio_publish(NULL);manager_league_audio_native_pump(14000);
 assert(mla_bank&&mla_mounted);
 /* Independent fresh optional-bank failure: no native mount, no repeated IO. */
 void *accepted=mla_bank;mla_bank=NULL;mla_attempted=mla_mounted=0;bad_bank=1;
 unsigned previous=mounts;uint64_t failed=77;
 assert(mla_play(NULL,MLA_BED,&failed)&&!failed&&mounts==previous&&reads==2);
 assert(mla_play(NULL,MLA_BED,&failed)&&reads==2&&!mla_mounted);
 free(accepted);free(backing);return 0;}
'''
    code = '#include <stdint.h>\n#define BANK_PATH '+json.dumps((ROOT/"local-debug/manager-review-v95/audio/stage-01/Audio/manager-league-v95.acb").as_posix())+'\n'+arrays+'\n'+code
    code = code.replace("BODY_COPIES",copies).replace("HEADER_BYTES", ",".join(map(str,header)))
    compile_run(tmp_path,code)


def native_request_and_hca_headers():
    """Execute native wrappers/packet decoder. Only final queue admission is stubbed.

    This records argument and plaintext packet semantics; it cannot prove mixer
    playback or device audibility. The existing HCA pool is not reconfigured.
    """
    from native_hca_probe import NativeHcaProbe
    import unicorn.arm64_const as regs
    from unicorn import UC_HOOK_CODE
    bank, report = local_bank()
    native_bodies()
    probe = NativeHcaProbe(ROOT / "dist/pes21_nx/libUE4.so")
    try:
        gate = probe.alloc(8, bytes([1])+bytes(7))
        probe.write(0x9597cb8,struct.pack("<Q",gate))
        seen = []
        def queue(uc,address,size,context):
            info,out = uc.reg_read(regs.UC_ARM64_REG_X0),uc.reg_read(regs.UC_ARM64_REG_X1)
            raw = bytes(uc.mem_read(info,0x38))
            seen.append(raw)
            uc.mem_write(out,struct.pack("<Q",123))
            uc.reg_write(regs.UC_ARM64_REG_W0,0)
            uc.reg_write(regs.UC_ARM64_REG_PC,uc.reg_read(regs.UC_ARM64_REG_LR))
        hook = probe.uc.hook_add(UC_HOOK_CODE,queue,begin=0x77e4668,end=0x77e4668)
        cue = probe.alloc(32,b"FNX_ML94_SHOT\0")
        handle = probe.alloc(8)
        assert probe.call(0x6cfff3c,cue,handle,0,0,0)==0
        assert probe.pointer(handle)==123 and len(seen)==1
        info = seen[0]
        assert struct.unpack_from("<Q",info,0)[0]==cue
        assert info[0x18:0x24]==bytes(12)
        assert struct.unpack_from("<H",info,0x2e)[0]==0xfff8
        assert struct.unpack_from("<I",info,0x30)[0]==0
        probe.uc.hook_del(hook)
        # Original KS HCA create/header/table/packet methods, all thirteen exact
        # source recordings. No replacement decoder or proprietary cipher key.
        work,out=probe.alloc(0x10000),probe.alloc(8)
        assert probe.call(0x74bf6a8,2,1,work,0x10000,out)==0
        decoder=probe.pointer(out)
        top=Utf(bank)
        records=[]
        for i,clip in enumerate(report["clips"]):
            hca=audio.awb_recording(top.blob(0,"AwbFile"),i)
            data=probe.alloc(len(hca),hca)
            header_bytes=struct.unpack_from(">H",hca,6)[0]
            result=probe.call(0x74bf97c,decoder,data,header_bytes,0,0,out)
            assert result==0,(clip["role"],hex(result),header_bytes)
            assert probe.call(0x74bf970,decoder,0,0)==0
            frame_bytes=struct.unpack_from(">H",hca,0x1c)[0]
            for frame in range(3):
                offset=header_bytes+frame*frame_bytes
                assert probe.call(0x74c0140,decoder,data+offset,frame_bytes,0,0,out)==0
                packet=probe.pointer(decoder+0xe8)
                assert bytes(probe.uc.mem_read(packet,frame_bytes))==hca[offset:offset+frame_bytes]
            records.append({"role":clip["role"],"header_bytes":header_bytes,
                "source_sha256":clip["audio_sha256"],"native_header_accepted":True,
                "native_original_packet_bytes":True,"packets_checked":3})
        return {"native_library_sha256":LIBRARY_SHA,"bank_sha256":report["bank_sha256"],
            "original_interface_play_executed":True,"play_parameters":[0,0,0],
            "native_play_info_flags_2e":"fff8","numeric_cue_selector_30":0,
            "final_queue_stubbed":True,"audio_device_executed":False,
            "native_original_hca_headers_and_packets":records}
    finally:
        probe.close()


def test_original_native_request_defaults_and_all_plain_hca_headers():
    local_bank()
    env=dict(os.environ)
    env.pop("PYTHONFAULTHANDLER",None)
    child=subprocess.run([sys.executable,str(Path(__file__).resolve()),"--native"],
        capture_output=True,text=True,timeout=90,env=env)
    assert child.returncode==0,child.stdout+child.stderr
    proof=json.loads(child.stdout)
    assert proof["original_interface_play_executed"]
    assert len(proof["native_original_hca_headers_and_packets"])==13
    (FOLDER/"NATIVE-PROOF.json").write_text(json.dumps(proof,indent=2)+"\n")


if __name__=="__main__":
    assert sys.argv[1:]==["--native"]
    print(json.dumps(native_request_and_hca_headers(),indent=2))
