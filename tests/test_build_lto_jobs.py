"""Exercise the real generated shell argument construction without a title build."""
from pathlib import Path
import os
import re
import shutil
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('workers',[None,'1','4'])
def test_lto_worker_limit_is_one_make_argument_and_default_stays_auto(workers):
    bash=shutil.which('bash')
    if not bash:pytest.skip('host Bash required for generated build command contract')
    source=(ROOT/'build-wsl.ps1').read_text()
    body=source.split("$buildScript = @'",1)[1].split("'@",1)[0]
    select=re.search(r'^lto_jobs=.*$',body,re.M)[0]
    command=body[body.index('make -j"$jobs"'):body.index('\n\ncp pes21_nx.nro')]
    script='set -eu\njobs=1\n'+select+'\nlink_build_id=test\nmake(){ printf "%s\\n" "$@"; }\n'+command
    env=os.environ.copy();env.pop('PES21_NX_LTO_JOBS',None)
    if workers is not None:env['PES21_NX_LTO_JOBS']=workers
    run=subprocess.run([bash,'-c',script],env=env,capture_output=True,text=True,check=True)
    options=run.stdout.splitlines()
    lto=[s for s in options if s.startswith('LTOFLAGS=')]
    assert lto==['LTOFLAGS=-flto='+('auto' if workers is None else workers)+' -fuse-linker-plugin']
    assert options[0]=='-j1' and 'LINK_BUILD_ID=test' in options
    assert '"LTO_JOBS=$lto_jobs"' in body
    assert '[ValidateRange(0,64)][int]$LtoJobs = 0' in source
    assert '$env:PES21_NX_LTO_JOBS = $oldLtoJobs' in source
