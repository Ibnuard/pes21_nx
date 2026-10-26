"""Quiet custom HCA recording, existing-pool playback and original native reader."""
from pathlib import Path
import hashlib
import json
import os
import struct
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests')]
import stage_trophy_hca_music as music
from stage_indonesia_commentary import Utf
from stage_manager_league_audio import awb_recording
from test_trophy_audio_v89 import RUNTIME,LIBRARY_SHA
from test_trophy_audio_v88 import compile_run

FOLDER=ROOT/'local-debug/match-review-v94/audio/stage-02'


def local_bank():
    path=FOLDER/music.ASSET
    if not path.is_file():
        pytest.skip('optional detached custom HCA bank required')
    bank=path.read_bytes();audio=awb_recording(Utf(bank).blob(0,'AwbFile'),0)
    return bank,audio,json.loads((FOLDER/'AUDIO-REPORT.json').read_text())


def test_quiet_full_recording_and_native_music_routing():
    bank,audio,report=local_bank()
    sealed=ROOT/'local-debug/presentation-v90/music-01/Audio/trophy-user-pcm-v90.acb'
    assert bank==music.build_bank(sealed.read_bytes(),audio)
    assert (ROOT/'source/trophy_audio_catalog.h').read_text()==music.catalog(bank,audio)
    assert hashlib.sha256(bank).hexdigest()==report['bank_sha256']
    assert report['independent_decoded_samples']==688128 and report['gain_db']==-12
    assert report['snr_db']>37 and report['decoded_peak']<.26 and not report['clipped_samples']
    assert report['comparison_global_polarity']==-1
    assert not report['creates_new_voice_pool'] and not report['device_accepted']
    assert music.hca_info(audio)['cipher']==0
    assert Utf(bank).child('WaveformTable').rows[0]['EncodeType']==2
    assert [(r['bus_name'],r['gain']) for r in report['native_route']['bus_sends']]==[('MasterOut',0),('BUS8',1)]


def test_playback_succeeds_without_allocating_a_wave_pool(tmp_path):
    bank,_,_=local_bank()
    old='static void *nx_asset_read(const char *p,size_t limit,size_t *bytes){(void)p;(void)limit;*bytes=0;return NULL;}'
    replacement=r'''static unsigned reads;
static void *nx_asset_read(const char *p,size_t limit,size_t *bytes){
 assert(!strcmp(p,TROPHY_AUDIO_ASSET) && limit==TROPHY_AUDIO_MAX_BANK_BYTES);++reads;
 FILE *f=fopen(BANK_PATH,"rb");assert(f);fseek(f,0,SEEK_END);*bytes=ftell(f);rewind(f);
 void *data=malloc(*bytes);assert(data && fread(data,1,*bytes,f)==*bytes);fclose(f);return data;}
'''
    assert old in RUNTIME
    code=RUNTIME.replace(old,replacement)+r'''
static unsigned mounts,plays,pool_calls;
static int32_t pool_size(const FixdemoWavePoolConfig *c){(void)c;++pool_calls;return -1;}
static void *pool_allocate(const FixdemoWavePoolConfig *c,void *w,int32_t n){
 (void)c;(void)w;(void)n;++pool_calls;return NULL;}
static int32_t mount_bank(void *b,uint32_t n,void *w,const char *s,int16_t *id){
 assert(b&&n==TROPHY_AUDIO_BYTES&&!w&&!s);++mounts;*id=7;return 0;}
static int32_t exists(const char *name){assert(!strcmp(name,TROPHY_AUDIO_CUE));return 1;}
static int32_t play(const char *name,uint64_t *h,int32_t a,int32_t b){
 assert(!strcmp(name,TROPHY_AUDIO_CUE)&&!a&&!b);*h=100+ ++plays;return 0;}
int main(void){
 setup();fixdemo_trophy_audio_observe(1000);
 fixdemo_audio_wave_pool_size=pool_size;fixdemo_audio_wave_pool_allocate=pool_allocate;
 fixdemo_audio_mount=mount_bank;fixdemo_audio_existing=exists;fixdemo_audio_play=play;
 fixdemo_trophy_audio.ops=(TrophyAudioOps){fixdemo_audio_native_play,fixdemo_audio_native_stop,fixdemo_audio_note,NULL};
 assert(trophy_audio_start(&fixdemo_trophy_audio,1));
 assert(reads==1&&mounts==1&&plays==1&&!pool_calls&&!fixdemo_audio_wave_pool_attempted);
 assert(__atomic_load_n(&trophy_audio_bank_mounted,__ATOMIC_ACQUIRE));
 assert(trophy_audio_stop(&fixdemo_trophy_audio));
 assert(trophy_audio_start(&fixdemo_trophy_audio,2));
 assert(reads==1&&mounts==1&&plays==2&&!pool_calls);
 assert(trophy_audio_stop(&fixdemo_trophy_audio));free(fixdemo_audio_bank);return 0;}
'''
    compile_run(tmp_path,'#define BANK_PATH '+json.dumps((FOLDER/music.ASSET).as_posix())+'\n'+code)


def native_headers_and_packets():
    from native_hca_probe import NativeHcaProbe
    bank,audio,_=local_bank();library=ROOT/'dist/pes21_nx/libUE4.so'
    with library.open('rb') as f:
        assert hashlib.file_digest(f,'sha256').hexdigest()==LIBRARY_SHA
    probe=NativeHcaProbe(library)
    try:
        work,out=probe.alloc(0x10000),probe.alloc(8)
        assert probe.call(0x74bf6a8,2,1,work,0x10000,out)==0
        decoder=probe.pointer(out);data=probe.alloc(len(audio),audio)
        assert probe.call(0x74bf97c,decoder,data,96,0,0,out)==0
        assert probe.call(0x74bf970,decoder,0,0)==0
        info=music.hca_info(audio)
        for frame in range(info['frames']):
            at=96+frame*info['frame_bytes']
            assert probe.call(0x74c0140,decoder,data+at,info['frame_bytes'],0,0,out)==0
            packet=probe.pointer(decoder+0xe8)
            assert bytes(probe.uc.mem_read(packet,info['frame_bytes']))==audio[at:at+info['frame_bytes']]
        return {'native_library_sha256':LIBRARY_SHA,'bank_sha256':hashlib.sha256(bank).hexdigest(),
                'native_header_accepted':True,'unaltered_packets':info['frames'],
                'mixer_or_audio_device_executed':False}
    finally:
        probe.close()


def test_original_native_accepts_header_and_every_plaintext_packet():
    local_bank()
    for module in ('unicorn','elftools.elf.elffile'):
        pytest.importorskip(module)
    if not (ROOT/'dist/pes21_nx/libUE4.so').is_file():
        pytest.skip('optional exact Mobile library required')
    env=dict(os.environ);env.pop('PYTHONFAULTHANDLER',None)
    result=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--native'],
                          check=True,capture_output=True,text=True,timeout=60,env=env)
    proof=json.loads(result.stdout)
    assert proof['native_header_accepted'] and proof['unaltered_packets']==673
    (FOLDER/'NATIVE-PROOF.json').write_text(json.dumps(proof,indent=2)+'\n')


if __name__=='__main__':
    assert sys.argv[1:]==['--native']
    print(json.dumps(native_headers_and_packets()))
