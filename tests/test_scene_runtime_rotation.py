"""Preserve one real prior boot log, with bounded storage and no game edits."""
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_reopening_keeps_exactly_one_bounded_prior_session(tmp_path):
    cc = shutil.which('gcc')
    if not cc:
        pytest.skip('gcc required for journal replay')
    source = tmp_path / 'journal.c'
    source.write_text('''#include <stdint.h>
static uint64_t armGetSystemTick(void) { return 0; }
static uint64_t armTicksToNs(uint64_t n) { return n; }
''' + f'#include "{(ROOT / "source/scene_runtime_log.h").as_posix()}"\n' + '''
int main(void) { scene_runtime_begin(); scene_runtime_note("test","boot complete"); }
''')
    exe = tmp_path / 'journal.exe'
    subprocess.run([cc, str(source), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], cwd=tmp_path, check=True)
    current, previous = tmp_path / 'scene-runtime.log', tmp_path / 'scene-runtime.previous.log'
    assert current.read_bytes().startswith(b'FootballNX scene v65 session')
    assert not previous.exists()
    cold = b'cold start: geometry missing\n'
    current.write_bytes(cold)
    subprocess.run([str(exe)], cwd=tmp_path, check=True)
    assert previous.read_bytes() == cold
    warm = b'warm start: recovered\n'
    current.write_bytes(warm)
    subprocess.run([str(exe)], cwd=tmp_path, check=True)
    assert previous.read_bytes() == warm
    assert len(list(tmp_path.glob('*.log'))) == 2
    # An oversized unmanaged input is not duplicated into another large file.
    current.write_bytes(b'x' * 65537)
    subprocess.run([str(exe)], cwd=tmp_path, check=True)
    assert previous.read_bytes() == warm
    assert current.stat().st_size < 65536
