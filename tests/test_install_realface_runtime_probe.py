"""Use synthetic bytes only; preserve unrelated cinematic/runtime changes."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT=Path(__file__).resolve().parents[1]
SHELL=shutil.which('pwsh') or shutil.which('powershell')
pytestmark=pytest.mark.skipif(not SHELL,reason='PowerShell unavailable')


def digest(data):return hashlib.sha256(data).hexdigest()


def setup(tmp):
    package,runtime,backup=(tmp/n for n in ('package','runtime','backup'))
    for root in (package/'update',package/'diagnostic',package/'entrance-baseline/LooseCpk',runtime/'LooseCpk'):
        root.mkdir(parents=True)
    native=b'cinematic native';canary=b'entrance-only candidate';other=b'unrelated new team data'
    header='PESNX_LOOSE_CPK_V2 0123456789abcdef 53248 '+'0'*64+'\n'
    reference=header+f'dt200_mobile_all.cpk 3 {digest(b"old")}\ndt220_mobile_all.cpk {len(native)} {digest(native)}\n'
    installed=header+f'dt200_mobile_all.cpk {len(other)} {digest(other)}\ndt220_mobile_all.cpk {len(canary)} {digest(canary)}\n'
    (package/'update/pes21_nx.nro').write_bytes(b'production')
    (package/'diagnostic/pes21_nx.nro').write_bytes(b'diagnostic')
    (package/'entrance-baseline/LooseCpk/dt220_mobile_all.cpk').write_bytes(native)
    (package/'entrance-baseline/LooseCpk/manifest.txt').write_text(reference,encoding='ascii')
    (runtime/'pes21_nx.nro').write_bytes(b'previous')
    (runtime/'LooseCpk/dt200_mobile_all.cpk').write_bytes(other)
    (runtime/'LooseCpk/dt220_mobile_all.cpk').write_bytes(canary)
    (runtime/'LooseCpk/manifest.txt').write_text(installed,encoding='ascii')
    (runtime/'cinematic-trace.txt').write_bytes(b'PESNX_CINEMATIC_TRACE_V1\n')
    proof=dict(candidate='Face runtime isolation v42',runtime_pair='0123456789abcdef',expected_patch_obb_bytes=53248,
               builds={k:dict(sha256=digest(k.encode())) for k in ('production','diagnostic')},
               baseline_cinematics=dict(dt220_sha256=digest(native),manifest_sha256=digest((package/'entrance-baseline/LooseCpk/manifest.txt').read_bytes()),
                                        allowed_installed_dt220_sha256=[digest(native),digest(canary)]))
    (package/'VERIFICATION.json').write_text(json.dumps(proof))
    return package,runtime,backup,other,canary


def run(package,runtime,backup,*args):
    return subprocess.run([SHELL,'-NoProfile','-NonInteractive','-File',str(ROOT/'tools/install_realface_runtime_probe.ps1'),
                           '-RuntimeRoot',str(runtime),'-PackageRoot',str(package),'-BackupRoot',str(backup),*args],
                          capture_output=True,text=True,timeout=30)


def test_preflight_then_install_preserves_other_rows_and_backs_up(tmp_path):
    package,runtime,backup,other,canary=setup(tmp_path)
    old=(runtime/'LooseCpk/manifest.txt').read_text().splitlines()
    result=run(package,runtime,backup,'-CheckOnly')
    assert result.returncode==0,result.stderr
    assert not backup.exists() and (runtime/'pes21_nx.nro').read_bytes()==b'previous'
    result=run(package,runtime,backup,'-Mode','diagnostic')
    assert result.returncode==0,result.stderr
    assert (runtime/'pes21_nx.nro').read_bytes()==b'diagnostic'
    assert (runtime/'LooseCpk/dt200_mobile_all.cpk').read_bytes()==other
    new=(runtime/'LooseCpk/manifest.txt').read_text().splitlines()
    assert new[:2]==old[:2] and new[2]!=old[2]
    saved=list(backup.iterdir());assert len(saved)==1
    assert (saved[0]/'LooseCpk/dt220_mobile_all.cpk').read_bytes()==canary
    assert (saved[0]/'pes21_nx.nro').read_bytes()==b'previous'
    assert (saved[0]/'cinematic-trace.txt').exists() and not (runtime/'cinematic-trace.txt').exists()


def test_package_tamper_and_unknown_cinematics_fail_before_any_write(tmp_path):
    package,runtime,backup,other,canary=setup(tmp_path)
    (package/'update/pes21_nx.nro').write_bytes(b'tampered')
    result=run(package,runtime,backup)
    assert result.returncode!=0 and not backup.exists()
    assert (runtime/'pes21_nx.nro').read_bytes()==b'previous'
    (package/'update/pes21_nx.nro').write_bytes(b'production')
    (runtime/'LooseCpk/dt220_mobile_all.cpk').write_bytes(b'X'*len(canary))
    result=run(package,runtime,backup)
    assert result.returncode!=0 and 'unreviewed' in result.stderr
    assert not backup.exists() and (runtime/'pes21_nx.nro').read_bytes()==b'previous'
