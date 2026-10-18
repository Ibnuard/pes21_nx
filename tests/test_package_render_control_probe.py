from pathlib import Path
import sys
import zipfile
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import package_render_control_probe as M


def test_only_verified_v43_nro_is_packaged_and_modes_share_one_binary(tmp_path,monkeypatch):
    monkeypatch.setattr(M,'ROOT',tmp_path)
    build=tmp_path/'build';build.mkdir()
    nro=build/'pes21_nx.nro'
    calls=[]
    def inspect(folder,diagnostic,pair):
        calls.append((folder,diagnostic,pair));return dict(elf_load_segments_match=True)
    monkeypatch.setattr(M,'inspect_build',inspect)
    nro.write_bytes(b'incomplete candidate')
    out=tmp_path/'local-debug/package'
    with pytest.raises(ValueError,match='v43'):M.package(build,out,'synthetic-pair')
    assert not out.exists()
    nro.write_bytes(b'FootballNX scene v43 session\0PESNX_GL_CACHE_BYPASS_V1\0'
                    b'map_failures=\0unmap_failures=\0render control: state_cache=')
    result=M.package(build,out,'synthetic-pair')
    assert calls[-1]==(build,True,'synthetic-pair')
    assert (out/'update/pes21_nx.nro').read_bytes()==nro.read_bytes()
    assert len(list(out.rglob('*.nro')))==1
    assert (out/'update/render-control.txt').read_bytes()==b'PESNX_GL_CACHE_DEFAULT_V1\n'
    assert (out/'test-2-bypass/render-control.txt').read_bytes()==b'PESNX_GL_CACHE_BYPASS_V1\n'
    assert result['verification']['whole_player_blink_fixed'] is False
    with zipfile.ZipFile(result['zip']) as archive:assert archive.testzip() is None
    with pytest.raises(ValueError,match='fresh'):M.package(build,out,'synthetic-pair')
    with pytest.raises(ValueError,match='fresh'):M.package(build,tmp_path/'public','synthetic-pair')
