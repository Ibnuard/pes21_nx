"""Real reviewed PCM -> bounded blend -> existing AudioOut submission path."""
from pathlib import Path
import hashlib
import json
import re
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tests")]
import index_manager_pcm_audio as index
from stage_indonesia_commentary import Utf
from stage_manager_league_audio import awb_recording, ROLES
from test_trophy_audio_v88 import compile_run

BANK = ROOT / "local-debug/manager-review-v96/audio/pcm-01/Audio/manager-league-pcm-v96.acb"


def bank_data():
    if not BANK.exists():
        pytest.skip("ignored individually reviewed v96 PCM bank required")
    data = BANK.read_bytes()
    assert hashlib.sha256(data).hexdigest() == index.BANK_SHA
    return data


def test_index_uses_native_cue_indices_and_exact_reviewed_waveforms():
    data = bank_data()
    assert index.catalog(data) == (ROOT / "source/manager_league_pcm_catalog.h").read_text()
    entries = re.findall(r"\{(\d+)u, (\d+)u\}", index.catalog(data))
    report = json.loads((BANK.parents[1] / "AUDIO-REPORT.json").read_text())
    by_role = {c["role"]: c for c in report["clips"]}
    for role, (offset, frames) in zip(ROLES, entries, strict=True):
        offset, frames = int(offset), int(frames)
        if role not in by_role:
            assert offset == frames == 0
            continue
        reviewed = by_role[role]
        assert frames == reviewed["samples"]
        raw = data[offset + 44:offset + 44 + frames * 4]
        assert hashlib.sha256(raw).hexdigest() == reviewed["pcm_sha256"]
    with pytest.raises(ValueError, match="exact individually"):
        index.catalog(bytes([data[0] ^ 1]) + data[1:])


PREFIX = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "manager_league_audio.h"
#include "manager_league_audio_catalog.h"
#include "manager_league_pcm_mixer.h"
static unsigned reads, bad_bank;
static void *read_bank(size_t *bytes) {
 FILE *f=fopen(BANK_PATH,"rb");assert(f);fseek(f,0,SEEK_END);*bytes=(size_t)ftell(f);rewind(f);
 unsigned char *data=malloc(*bytes);assert(data);assert(fread(data,1,*bytes,f)==*bytes);fclose(f);
 if(bad_bank)data[*bytes-1]^=1;
 ++reads;return data;
}
'''


def compile_case(tmp_path, code):
    bank_data()
    compile_run(tmp_path, '#define BANK_PATH ' + json.dumps(BANK.as_posix()) + '\n' + PREFIX + code)


def test_every_recording_is_sample_exact_in_real_pcm_output(tmp_path):
    compile_case(tmp_path, r'''
int main(void) {
 size_t bytes;unsigned char *data=read_bank(&bytes);int16_t output[8192*2];
 for(unsigned clip=0;clip<MLA_CLIP_COUNT;++clip) {
  if(!mla_pcm_clips[clip].frames)continue;
  MlaPcmMixer mixer={0};assert(mla_pcm_bind(&mixer,data,(uint32_t)bytes));
  uint64_t handle=0;assert(!mla_pcm_start(&mixer,clip,&handle)&&handle);
  mixer.voices[0].attack=0; /* Identity proof before the separately tested envelope. */
  char name[40];snprintf(name,sizeof(name),"clip-%u.raw",clip);FILE *f=fopen(name,"wb");assert(f);
  unsigned remaining=mla_pcm_clips[clip].frames;
  while(remaining) {
   unsigned frames=remaining>8192?8192:remaining;memset(output,0,sizeof(output));
   mla_pcm_mix(&mixer,output,frames,1);assert(fwrite(output,4,frames,f)==frames);remaining-=frames;
  }
  fclose(f);assert(mixer.source_frames[clip]==mla_pcm_clips[clip].frames);
 }
 free(data);return 0;
}
''')
    top = Utf(bank_data())
    report = json.loads((BANK.parents[1] / "AUDIO-REPORT.json").read_text())
    specs = {c["role"]: c for c in report["clips"]}
    proof = []
    for clip, role in enumerate(ROLES):
        if role not in specs:
            continue
        raw = (tmp_path / f"clip-{clip}.raw").read_bytes()
        assert hashlib.sha256(raw).hexdigest() == specs[role]["pcm_sha256"]
        cue_index = next(c["CueIndex"] for c in top.child("CueNameTable").rows
                         if c["CueName"] == "FNX_ML96_" + role.upper())
        assert raw == awb_recording(top.blob(0, "AwbFile"), cue_index)[44:]
        proof.append({"role": role, "frames": len(raw) // 4,
                      "pcm_sha256": hashlib.sha256(raw).hexdigest(), "sample_exact": True})
    output = ROOT / "local-debug/manager-review-v99/audio"
    output.mkdir(parents=True, exist_ok=True)
    (output / "PCM-OUTPUT-PROOF.json").write_text(json.dumps({
        "bank_sha256": index.BANK_SHA, "source": "exact individually reviewed v96 PCM",
        "destination": "production PCM blend, zero native input, envelope bypassed for identity proof",
        "clips": proof, "audio_device_executed": False, "device_listening_verified": False}, indent=2) + "\n")


def test_normal_attack_envelope_matches_independent_sample_math(tmp_path):
    compile_case(tmp_path, r'''
int main(void) {
 size_t bytes;unsigned char *data=read_bank(&bytes);MlaPcmMixer m={0};int16_t out[4096*2];
 assert(mla_pcm_bind(&m,data,(uint32_t)bytes));uint64_t handle;
 assert(!mla_pcm_start(&m,MLA_BALL_SHOT,&handle));memset(out,0,sizeof(out));
 mla_pcm_mix(&m,out,4096,1);FILE *f=fopen("attack.raw","wb");assert(f);
 assert(fwrite(out,4,4096,f)==4096);fclose(f);free(data);return 0;
}
''')
    import numpy as np
    raw = awb_recording(Utf(bank_data()).blob(0, "AwbFile"), 2)[44:44 + 4096 * 4]
    source = np.frombuffer(raw, "<i2").reshape(-1, 2).astype(np.int64)
    gain = np.minimum(np.arange(4096), 480) * 32768 // 480
    expected = np.trunc(source * gain[:, None] / 32768).astype("<i2").tobytes()
    assert (tmp_path / "attack.raw").read_bytes() == expected


def test_envelopes_capacity_saturation_bounds_and_complete_native_restore(tmp_path):
    compile_case(tmp_path, r'''
int main(void) {
 size_t bytes;unsigned char *data=read_bank(&bytes);MlaPcmMixer m={0};int16_t out[8192*2];
 assert(!mla_pcm_bind(&m,data,100));assert(!m.bank);
 unsigned header=mla_pcm_clips[MLA_BED].wave_offset;
 data[header+22]^=1;assert(!mla_pcm_bind(&m,data,(uint32_t)bytes));data[header+22]^=1;
 assert(mla_pcm_bind(&m,data,(uint32_t)bytes));assert(!mla_pcm_bind(&m,data,(uint32_t)bytes));
 for(unsigned i=0;i<8192*2;++i)out[i]=(i&1)?-23456:12345;
 int16_t original[8192*2];memcpy(original,out,sizeof(out));
 mla_pcm_mix(&m,out,8192,0);assert(!memcmp(out,original,sizeof(out)));
 uint64_t handles[6],extra=123;
 for(unsigned i=0;i<6;++i)assert(!mla_pcm_start(&m,MLA_CROWD_GOAL,&handles[i]));
 assert(mla_pcm_start(&m,MLA_CROWD_GOAL,&extra)&&!extra&&mla_pcm_active(&m)==6);
 /* Controlled +/-30000 source tests clipping independently of recordings. */
 unsigned char *pcm=data+mla_pcm_clips[MLA_CROWD_GOAL].wave_offset+44;
 for(unsigned i=0;i<8192;++i){pcm[i*4]=0x30;pcm[i*4+1]=0x75;pcm[i*4+2]=0xd0;pcm[i*4+3]=0x8a;}
 memset(out,0,sizeof(out));mla_pcm_mix(&m,out,8192,1);
 assert(out[16000]==32767&&out[16001]==-32768);
 assert(m.native_gain==MLA_PCM_WATCH_NATIVE_GAIN);
 assert(!mla_pcm_stop(&m,999999,100)&&mla_pcm_active(&m)==6);
 for(unsigned i=0;i<8192*2;++i)out[i]=original[i];
 mla_pcm_mix(&m,out,8192,0);assert(!mla_pcm_active(&m)&&m.native_gain==MLA_PCM_UNITY);
 assert(!memcmp(out+4800*2,original+4800*2,(8192-4800)*4));
 memcpy(out,original,sizeof(out));mla_pcm_mix(&m,out,8192,0);assert(!memcmp(out,original,sizeof(out)));
 /* Invalid frame count is not read or written. */
 mla_pcm_mix(&m,out,8193,1);assert(!memcmp(out,original,sizeof(out)));
 free(data);return 0;
}
''')


RUNTIME = r'''
typedef struct {int dummy;} so_module;
static void scene_runtime_note(const char *a,const char *b){(void)a;(void)b;}
static void *nx_asset_read_production(const char *name,uint32_t maximum,size_t *bytes) {
 assert(!strcmp(name,MLA_ASSET)&&maximum==MLA_BANK_MAX_BYTES);return read_bank(bytes);
}
#include "manager_league_audio_runtime.inc"
static void arm(void) {
 so_module module={0};
 manager_league_audio_native_install(&module,"wrong");assert(!mla_ready);
 manager_league_audio_native_install(&module,"a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187");
 assert(mla_ready&&!reads);assert(!manager_league_audio_plain_hca_header(NULL,0,NULL,0));
}
static ManagerLeagueAudioFrame frame={.fixture_token=9,.monotonic_ms=1000,.visible_watch=1};
static void tick(unsigned now,unsigned position,unsigned kind,unsigned serial) {
 frame.monotonic_ms=now;frame.position_ms=frame.event_at_ms=position;frame.event_kind=kind;frame.event_serial=serial;
 manager_league_audio_publish(&frame);manager_league_audio_native_pump(now);
}
'''


def test_live_policy_to_callback_goals_once_pause_exit_and_stale_restart(tmp_path):
    compile_case(tmp_path, RUNTIME + r'''
int main(void) {
 arm();tick(1000,0,0,0);assert(reads==1&&mla_policy.bed.handle&&mla_policy.speech.handle);
 int16_t out[1024*2];memset(out,0,sizeof(out));manager_league_audio_mix_pcm(out,1024,1000);
 assert(mla_pcm.source_frames[MLA_BED]==1024&&mla_pcm.source_frames[MLA_SPEECH_KICKOFF]==1024);
 uint64_t serial=mla_pcm.serial;tick(1010,10,0,0);assert(mla_pcm.serial==serial);
 tick(1500,500,MLA_SHOT,1);assert(mla_policy.effect.handle);
 tick(2000,1000,MLA_GOAL,2);assert(mla_policy.played_events==2);
 assert(mla_watch[1].clip==MLA_SPEECH_GOAL&&mla_watch[2].clip==MLA_CROWD_GOAL);
 serial=mla_pcm.serial;tick(2010,1010,MLA_GOAL,2);assert(mla_pcm.serial==serial);
 /* No callback waits for the owner; source positions do not change on contention. */
 mla_pcm_lock=1;memset(out,0x11,sizeof(out));int16_t before[2048];memcpy(before,out,sizeof(out));
 uint64_t mixed=mla_pcm.mixed_frames;manager_league_audio_mix_pcm(out,1024,2010);
 assert(!memcmp(before,out,sizeof(out))&&mla_pcm.mixed_frames==mixed);mla_pcm_lock=0;
 for(unsigned i=0;i<10;++i){memset(out,0,sizeof(out));manager_league_audio_mix_pcm(out,1024,2010+i*21);}
 assert(mla_pcm.nonzero_samples&&mla_pcm.source_frames[MLA_SPEECH_GOAL]);
 /* Lost publication fades sounds and fully restores the native buffer in <=100ms. */
 for(unsigned i=0;i<6;++i){for(unsigned j=0;j<2048;++j)out[j]=12345;
 manager_league_audio_mix_pcm(out,1024,5000+i*21);}
 assert(mla_output_stale&&!mla_pcm_active(&mla_pcm)&&mla_pcm.native_gain==MLA_PCM_UNITY);
 for(unsigned j=0;j<2048;++j)assert(out[j]==12345);
 tick(5200,1200,MLA_GOAL,2);assert(!mla_output_stale&&mla_policy.bed.handle&&mla_pcm_active(&mla_pcm)==1);
 assert(mla_policy.played_events==2); /* Current event was anchored, not replayed. */
 frame.paused=1;tick(5300,1300,MLA_GOAL,2);assert(!mla_policy.bed.handle&&!mla_watch_active);
 frame.visible_watch=0;tick(5400,1400,MLA_GOAL,2);
 for(unsigned i=0;i<6;++i){for(unsigned j=0;j<2048;++j)out[j]=-12345;
 manager_league_audio_mix_pcm(out,1024,5400+i*21);}
 assert(!mla_pcm_active(&mla_pcm)&&mla_pcm.native_gain==MLA_PCM_UNITY);
 for(unsigned j=0;j<2048;++j)assert(out[j]==-12345);
 assert(reads==1&&mla_pcm.bank);return 0;
}
''')


def test_bad_bank_never_ducks_native_audio_and_is_not_retried(tmp_path):
    compile_case(tmp_path, RUNTIME + r'''
int main(void) {
 arm();bad_bank=1;tick(1000,0,0,0);assert(reads==1&&!mla_pcm.bank&&!mla_watch_active);
 tick(1100,100,MLA_GOAL,1);assert(reads==1&&!mla_policy.bed.handle);
 int16_t out[2048];for(unsigned i=0;i<2048;++i)out[i]=23456;
 manager_league_audio_mix_pcm(out,1024,1100);for(unsigned i=0;i<2048;++i)assert(out[i]==23456);
 return 0;
}
''')


def test_owner_and_output_threads_are_bounded_and_restore_after_contention(tmp_path):
    compile_case(tmp_path, RUNTIME + r'''
#include <pthread.h>
static uint64_t clock_now=1000;
static void *owner_thread(void *unused) {
 (void)unused;
 for(unsigned i=0;i<3000;++i) {
  unsigned now=(unsigned)__atomic_load_n(&clock_now,__ATOMIC_ACQUIRE);
  tick(now,now-1000,MLA_PASS,i+1);
 }
 return NULL;
}
static void *output_thread(void *unused) {
 (void)unused;int16_t out[2048];
 for(unsigned i=0;i<3000;++i) {
  memset(out,0,sizeof(out));uint64_t now=__atomic_fetch_add(&clock_now,21,__ATOMIC_ACQ_REL);
  manager_league_audio_mix_pcm(out,1024,now);
 }
 return NULL;
}
int main(void) {
 arm();tick(1000,0,0,0);pthread_t owner,output;
 assert(!pthread_create(&owner,NULL,owner_thread,NULL));
 assert(!pthread_create(&output,NULL,output_thread,NULL));
 assert(!pthread_join(owner,NULL));assert(!pthread_join(output,NULL));
 assert(reads==1&&mla_pcm_active(&mla_pcm)<=6);
 unsigned now=(unsigned)__atomic_load_n(&clock_now,__ATOMIC_ACQUIRE);frame.visible_watch=0;
 tick(now,now-1000,MLA_PASS,3001);int16_t out[2048];
 for(unsigned i=0;i<6;++i){for(unsigned j=0;j<2048;++j)out[j]=23456;
  manager_league_audio_mix_pcm(out,1024,now+i*21);}
 assert(!mla_pcm_active(&mla_pcm)&&mla_pcm.native_gain==MLA_PCM_UNITY);
 for(unsigned j=0;j<2048;++j)assert(out[j]==23456);
 return 0;
}
''')


def test_actual_aaudio_submission_blends_after_resample_before_existing_append(tmp_path):
    text = (ROOT / "source/aaudio_shim.c").read_text()
    function = text[text.index("static int aaudio_fill_output_buffer("):text.index("static void aaudio_stop_and_flush(")]
    compile_case(tmp_path, RUNTIME + r'''
typedef struct {void *buffer;unsigned data_size;} AudioOutBuffer;
typedef struct {AudioOutBuffer nx;uint64_t source_frames;} AAudioOutputBuffer;
typedef struct {int xrun_count;} AAudioStream;
typedef int Result;
#define AAUDIO_AUDOUT_BUFFER_FRAMES 1024
#define AAUDIO_AUDOUT_CHANNEL_COUNT 2
#define AAUDIO_ERROR_INTERNAL -896
#define R_FAILED(r) ((r)<0)
#define debugPrintf(...) ((void)0)
static unsigned appended,nonzero,failed_render,errors;
static uint64_t clock_ms=1000;
static uint64_t armGetSystemTick(void){return clock_ms*1000000u;}
static uint64_t armTicksToNs(uint64_t tick){return tick;}
static int aaudio_render_output(AAudioStream *s,int16_t *out,uint64_t *source){
 (void)s;if(failed_render)return 0;memset(out,0,4096);*source=1024;return 1;}
static void aaudio_report_error(AAudioStream *s,int error){(void)s;(void)error;++errors;}
static Result audoutAppendAudioOutBuffer(AudioOutBuffer *buffer) {
 assert(buffer->data_size==4096);const int16_t *pcm=buffer->buffer;
 for(unsigned i=0;i<2048;++i)nonzero+=!!pcm[i];
 ++appended;return 0;
}
''' + function + r'''
int main(void) {
 arm();tick(1000,0,0,0);AAudioStream stream={0};int16_t pcm[2048];
 AAudioOutputBuffer buffer={.nx={.buffer=pcm}};
 for(unsigned i=0;i<48;++i){clock_ms=1000+i*21;assert(aaudio_fill_output_buffer(&stream,&buffer));}
 assert(appended==48&&nonzero>10000&&mla_pcm.source_frames[MLA_BED]==49152&&buffer.source_frames==1024);
 uint64_t frames=mla_pcm.mixed_frames;failed_render=1;assert(!aaudio_fill_output_buffer(&stream,&buffer));
 assert(appended==48&&mla_pcm.mixed_frames==frames&&!errors);return 0;
}
''')
