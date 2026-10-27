"""Current production trophy bank: full decode, native admission and cue binding."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests')]
import stage_trophy_gain_music as music
from stage_indonesia_commentary import Utf
from stage_manager_league_audio import awb_recording
FOLDER=ROOT/'local-debug/manager-review-v100/trophy-audio/stage-01'
def local_bank():
    path=FOLDER/music.V100.asset
    if not path.is_file():pytest.skip('ignored current v100 trophy bank required')
    bank=path.read_bytes();return bank,awb_recording(Utf(bank).blob(0,'AwbFile'),0),json.loads((FOLDER/'AUDIO-REPORT.json').read_text())
def test_current_bank_preserves_native_graph_and_exact_runtime_fingerprint():
    bank,audio,report=local_bank();old=(ROOT/'local-debug/manager-review-v99/trophy-audio/stage-01'/music.V99.asset).read_bytes()
    assert bank==music.build_bank(old,audio,music.V100)
    assert (ROOT/'source/trophy_audio_catalog.h').read_text()==music.catalog(bank,audio,music.V100)
    assert hashlib.sha256(bank).hexdigest()==report['bank_sha256']
    assert report['gain_db']==0 and abs(report['measured_increase_db']-3)<.02
    assert not report['source_mutated'] and not report['previous_bank_mutated']
    assert report['clipped_samples']==0 and report['decoded_peak']<.96
    assert report['original_pcm_encoded_once'] and not report['global_gain_or_commentary_changed']
def test_original_native_accepts_current_header_and_all_packets():
    local_bank()
    for module in ('unicorn','elftools.elf.elffile'):pytest.importorskip(module)
    if not (ROOT/'dist/pes21_nx/libUE4.so').exists():pytest.skip('exact local Mobile ELF required')
    env=dict(os.environ);env.pop('PYTHONFAULTHANDLER',None)
    ran=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--native'],check=True,capture_output=True,text=True,timeout=60,env=env)
    proof=json.loads(ran.stdout)
    assert proof['native_header_accepted'] and proof['unaltered_packets']==673
    assert not proof['mixer_or_audio_device_executed']
    (FOLDER/'NATIVE-PROOF.json').write_text(json.dumps(proof,indent=2)+'\n')
if __name__=='__main__':
    assert sys.argv[1:]==['--native']
    from test_trophy_audio_v97 import native_headers_and_packets
    print(json.dumps(native_headers_and_packets(local_bank)))
