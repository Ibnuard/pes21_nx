from pathlib import Path
import sys
import zipfile
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import package_pacing_runtime_candidate as M


@pytest.mark.parametrize('version',[44,45,46,47,48])
def test_pair_is_verified_before_writes_and_ordinary_build_is_primary(tmp_path,monkeypatch,version):
    monkeypatch.setattr(M,'ROOT',tmp_path)
    calls=[]
    def inspect(folder,diagnostic,pair):
        calls.append((folder.name,diagnostic,pair));return {'near_camera_trace':diagnostic}
    monkeypatch.setattr(M,'inspect_build',inspect)
    build=tmp_path/'build'
    marker=f'FootballNX scene v{version} session\0'.encode()+M.CANDIDATES[version][1]
    for kind in ('production','diagnostic'):
        (build/kind).mkdir(parents=True)
        (build/kind/'pes21_nx.nro').write_bytes(marker+kind.encode())
    (build/'diagnostic/pes21_nx.nro').write_bytes(b'wrong version')
    output=tmp_path/'local-debug/package'
    with pytest.raises(ValueError,match=f'v{version}'):M.package(build,output,'pair',version)
    assert not output.exists()
    (build/'diagnostic/pes21_nx.nro').write_bytes(marker+b'diagnostic')
    proof=M.package(build,output,'pair',version)
    assert calls[-2:]==[('production',False,'pair'),('diagnostic',True,'pair')]
    assert (output/'update/pes21_nx.nro').read_bytes()==marker+b'production'
    assert (output/'diagnostic/pes21_nx.nro').read_bytes()==marker+b'diagnostic'
    assert proof['verification']['face_quality_changed'] is (None if version>=47 else False)
    assert proof['verification']['face_assets_changed'] is False
    assert proof['verification']['native_high_player_class_changed'] == (version>=47)
    assert proof['verification']['compositor_diagnostic_probes_removed'] == (version>=48)
    assert proof['verification']['previous_session_journal_preserved'] == (version>=48)
    assert proof['verification']['diagnostic_native_player_class_control'] == (version>=48)
    if version>=48:
        assert (output/'controls/native-player-class/render-control.txt').read_bytes()==b'PESNX_NATIVE_PLAYER_CLASS_V1\n'
    assert proof['verification']['device_stadium_visibility_verified'] is False
    assert proof['verification']['device_blinking_resolved'] is False
    if version>=47:
        assert proof['verification']['model_quality_policy']=={
            'low':['low','low'],'standard':['standard','standard'],
            'high':['standard','high']}
    assert proof['verification']['stable_60_fps_verified'] is False
    assert not (output/'update/render-control.txt').exists()
    with zipfile.ZipFile(proof['zip']) as z:assert z.testzip() is None
    assert f'v{version}' in (output/'INSTALL.txt').read_text()
    with pytest.raises(ValueError,match='fresh'):M.package(build,output,'pair',version)
