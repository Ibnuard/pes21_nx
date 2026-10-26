"""Stage the quiet full user recording on the existing native HCA voice pool.

The sealed v90 PCM bank supplies the reviewed recording and native routing.
Only detached outputs are written. No global audio setting or pool is changed.
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import subprocess
import wave
import io

import numpy as np

from stage_indonesia_commentary import Utf, fnv64, memory_awb
from stage_player_commentary import rebuild_utf
from stage_trophy_music import row_copy
from stage_trophy_pcm_music import routing
from stage_manager_league_audio import awb_recording

ASSET = 'Audio/trophy-user-hca-v94.acb'
CUE = 'FNX_TROPHY_USER_HCA_V94'
PCM_BANK_SHA = '2d7512a25c6c2289db0f2005771a9fd7fbbf319701a52d2686c84d734600f837'
QUIET_WAVE_SHA = '2cb6488ac182b614bb5d82b8873d387f667b6dd43a73e4350e6e3b187e5bdc97'
ENCODER_SHA = '0f3bda1bf2dc2421756a16c05769430e4881876deb4eab40ca47b31009173e2b'
MAX_BANK = 2*1024*1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def hca_info(audio):
    if audio[:12] != b'HCA\0\x02\0\0\x60fmt\0' or audio[24:28] != b'comp':
        raise ValueError('unreviewed HCA format/header')
    if audio[40:46] != b'ciph\0\0' or b'loop' in audio[:96]:
        raise ValueError('requires plaintext, non-looping HCA')
    channels, rate, frames = audio[12], int.from_bytes(audio[13:16],'big'), int.from_bytes(audio[16:20],'big')
    delay, padding = struct.unpack_from('>HH',audio,20)
    frame_bytes = struct.unpack_from('>H',audio,28)[0]
    samples = frames*1024-delay-padding
    if (channels,rate,samples,frame_bytes)!=(2,44100,688128,1024) or len(audio)!=96+frames*frame_bytes:
        raise ValueError('full recording/channel/frame bounds differ')
    return dict(channels=channels,sample_rate=rate,samples=samples,frames=frames,
                frame_bytes=frame_bytes,header_bytes=96,encoder_delay=delay,padding=padding,cipher=0)


def build_bank(sealed,audio):
    if digest(sealed)!=PCM_BANK_SHA:
        raise ValueError('requires the sealed quiet PCM bank')
    hca_info(audio)
    native=Utf(sealed);top=row_copy(native,0)
    waveform=row_copy(native.child('WaveformTable'),0)
    waveform['EncodeType']=2
    top.update(Name=CUE,AcbGuid=hashlib.sha256(CUE.encode()+audio).digest()[:16],
               AwbFile=memory_awb([(0,audio)]),
               CueNameTable=rebuild_utf(native.child('CueNameTable'),[{'CueName':CUE,'CueIndex':0}],compact_blobs=True),
               WaveformTable=rebuild_utf(native.child('WaveformTable'),[waveform],compact_blobs=True))
    bank=rebuild_utf(native,[top],compact_blobs=True)
    if len(bank)>MAX_BANK or awb_recording(Utf(bank).blob(0,'AwbFile'),0)!=audio:
        raise ValueError('bank bound/recording roundtrip differs')
    after=Utf(bank)
    for field in ('CueTable','SequenceTable','TrackTable','SynthTable','TrackEventTable',
                  'SeqCommandTable','StringValueTable','AcfMd5Hash'):
        if native.blob(0,field)!=after.blob(0,field):
            raise ValueError('native graph or routing changed: '+field)
    routing(after)
    return bank


def catalog(bank,audio):
    info=hca_info(audio)
    return f'''/* Generated metadata only; the user recording remains ignored. */
#ifndef PESNX_TROPHY_AUDIO_CATALOG_H
#define PESNX_TROPHY_AUDIO_CATALOG_H
#define TROPHY_AUDIO_ASSET "{ASSET}"
#define TROPHY_AUDIO_CUE "{CUE}"
#define TROPHY_AUDIO_ENCODE_TYPE 2u
#define TROPHY_AUDIO_MAX_BANK_BYTES {MAX_BANK}u
#define TROPHY_AUDIO_GAIN_DB_X100 (-1200)
#define TROPHY_AUDIO_BYTES {len(bank)}u
#define TROPHY_AUDIO_FNV UINT64_C(0x{fnv64(bank):016x})
#define TROPHY_AUDIO_HEADER_BYTES {info['header_bytes']}u
#define TROPHY_AUDIO_HEADER_FNV UINT64_C(0x{fnv64(audio[:info['header_bytes']]):016x})
#endif
'''


def stage(pcm_bank,encoder,ffmpeg,output):
    sealed=pcm_bank.read_bytes()
    if digest(sealed)!=PCM_BANK_SHA or digest(encoder.read_bytes())!=ENCODER_SHA:
        raise ValueError('sealed source or reviewed encoder differs')
    recording=awb_recording(Utf(sealed).blob(0,'AwbFile'),0)
    if digest(recording)!=QUIET_WAVE_SHA:
        raise ValueError('quiet full recording differs')
    output.mkdir(parents=True,exist_ok=False)
    source=output/'quiet-source.wav';source.write_bytes(recording)
    hca=output/'trophy-user.hca'
    command=[str(encoder),'-i',str(source),'-o',str(hca),'--hcaquality','highest','--no-loop']
    subprocess.run(command,check=True,capture_output=True,timeout=60)
    audio=hca.read_bytes();info=hca_info(audio)
    decoded=subprocess.run([str(ffmpeg),'-v','error','-xerror','-i',str(hca),'-f','f32le','-'],
                           check=True,capture_output=True,timeout=60)
    pcm=np.frombuffer(decoded.stdout,'<f4').reshape(-1,2)
    if len(pcm)==info['frames']*1024:
        pcm=pcm[info['encoder_delay']:info['encoder_delay']+info['samples']]
    if len(pcm)!=info['samples'] or not np.all(np.isfinite(pcm)):
        raise ValueError('independent full HCA decode/frame count failed')
    with wave.open(io.BytesIO(recording),'rb') as reader:
        reference=np.frombuffer(reader.readframes(reader.getnframes()),'<i2').reshape(-1,2).astype(float)/32768
    # VGAudio and FFmpeg use opposite global HCA polarity. Account for that
    # convention only in the comparison; never modify the encoded recording.
    polarity=-1 if np.sum(reference*pcm)<0 else 1
    snr=float(10*np.log10(np.sum(reference**2)/np.sum((reference-pcm*polarity)**2)))
    peak=float(np.max(np.abs(pcm)))
    if snr<37 or peak>.26 or np.any(np.abs(pcm)>=1):
        raise ValueError(f'HCA quality/headroom check failed: snr={snr}, peak={peak}')
    bank=build_bank(sealed,audio)
    target=output/ASSET;target.parent.mkdir();target.write_bytes(bank)
    (output/'trophy_audio_catalog.h').write_text(catalog(bank,audio),encoding='ascii',newline='\n')
    report=dict(status='detached_host_verified_not_installed',source_pcm_bank_sha256=PCM_BANK_SHA,
                source_quiet_wave_sha256=QUIET_WAVE_SHA,source_clip_sha256='3655a2a1fbb297efb34d4629547e3943326c5ed5e1ee23ab8f88cbb02d6603ff',
                bank_sha256=digest(bank),bank_bytes=len(bank),hca_sha256=digest(audio),codec_info=info,
                codec='HCA highest',gain_db=-12,independent_decoded_samples=len(pcm),snr_db=snr,
                comparison_global_polarity=polarity,
                decoded_peak=peak,decoded_rms_dbfs=float(20*np.log10(np.sqrt(np.mean(pcm**2)))),
                clipped_samples=int(np.count_nonzero(np.abs(pcm)>=1)),
                native_route=routing(Utf(bank)),encoder_sha256=ENCODER_SHA,
                encoder_source='https://github.com/Thealexbarney/VGAudio/releases/tag/v2.2.1',
                creates_new_voice_pool=False,device_accepted=False)
    (output/'AUDIO-REPORT.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ('pcm-bank','encoder','ffmpeg','output'):
        parser.add_argument('--'+arg,type=Path,required=True)
    a=parser.parse_args()
    print(json.dumps(stage(a.pcm_bank,a.encoder,a.ffmpeg,a.output),indent=2))
