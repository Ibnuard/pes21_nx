"""Finish an already-running local league conversion and its TEST bundle.

This is a local foreground/background process, not a scheduler. It observes
only the explicitly supplied conversion/cook process IDs and this run's files.
If a worker command exits early, at most two resumable restarts are attempted.
Progress/errors remain in PIPELINE-STATUS.json. No release is approved/installed.
"""
import argparse
import ctypes
import os
from pathlib import Path
import subprocess
import sys
import time

from realface_batch_inventory import read, write
from realface_native_hair_candidate import package
from realface_native_hair_queue import pending, queue
from realface_native_hair_recover import recover
from realface_native_hair_trial import HERE


def running(pid):
    if not pid: return False
    if os.name == 'nt':
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle: return False
        try:
            code = wintypes.DWORD()
            return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
        finally: kernel.CloseHandle(handle)
    try: os.kill(pid, 0); return True
    except ProcessLookupError: return False


def finish(config_path, work, prepare_pid, cook_pid):
    config = read(config_path); work = Path(work).resolve()
    if not work.is_relative_to(HERE.parent / 'local-debug') or work == HERE.parent / 'local-debug':
        raise ValueError('Finishing requires a dedicated ignored league directory')
    restarts = 0; child = None
    try:
        while True:
            faces = read(work / 'chosen-faces.json')
            expected = sum(not r.get('reuse_cooked') and r.get('status') in ('prepared', 'prepared_cached') for r in faces)
            rows = read(work / 'trial-report.json')
            verified = read(work / 'verify-report.json') if (work / 'verify-report.json').exists() else []
            checked = {r['base_id']: r for r in verified}
            write(work / 'PIPELINE-STATUS.json', dict(phase='converting' if len(rows) < expected else 'cooking',
                  attempted=len(rows), target=expected, cook_results=len(verified),
                  cooked_passes=sum(r['status'].startswith('validated') for r in verified),
                  remaining_cooks=len(pending(rows, checked)), prepare_pid=prepare_pid,
                  cook_pid=cook_pid, restarts=restarts, approved=False))
            if len(rows) == expected:
                break
            if not running(prepare_pid):
                if restarts >= 2: raise RuntimeError('Conversion exited before all identities; restart limit reached')
                saved = read(work / 'run-config.json')
                args = [sys.executable, '-u', str(HERE / 'realface_native_hair_leagues.py'),
                        '--config', str(Path(config_path).resolve()), '--coverage', str(work / 'input-coverage.json'),
                        '--work-dir', str(work), '--workers', str(saved['workers'])]
                for base, report in saved['alternatives']: args += ['--face-choice', str(base) + '=' + report]
                with (work / 'automatic-resume.log').open('a', encoding='utf-8') as log:
                    child = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT)
                prepare_pid = child.pid; restarts += 1
            time.sleep(10)
        # An optional early worker owns these leaf caches until its active job
        # finishes. It stops taking work once the primary run reaches its target.
        precompute_state = work / 'PRECOMPUTE-STATUS.json'
        while precompute_state.exists():
            early = read(precompute_state)
            if early.get('phase') != 'running' or not running(early.get('pid')): break
            write(work / 'PIPELINE-STATUS.json', dict(phase='waiting_for_recovery_cache', approved=False,
                  active_base_id=early.get('active_base_id'), precomputed=early.get('completed')))
            time.sleep(10)
        write(work / 'PIPELINE-STATUS.json', dict(phase='recovering_held_heads',
              attempted=expected, target=expected, approved=False))
        recovered_config, recovered_work = recover(config, work)
        # Geometry recovery owns separate inputs/leaf directories, so it can
        # overlap the last original cook. Join that queue before taking its
        # final verified snapshot; only unchanged candidate keys may carry over.
        while running(cook_pid):
            write(work / 'PIPELINE-STATUS.json', dict(phase='waiting_for_primary_cook', approved=False))
            time.sleep(10)
        queue(config, work, follow=False, workers=2)
        merge_primary_verification(work, recovered_work)
        write(work / 'PIPELINE-STATUS.json', dict(phase='verifying_recovered_heads', approved=False))
        queue(recovered_config, recovered_work, follow=False, workers=1)
        write(work / 'PIPELINE-STATUS.json', dict(phase='packaging_test_candidate', approved=False))
        release = package(recovered_config, recovered_work)
        write(work / 'latest-test.json', read(recovered_work / 'latest-test.json'))
        write(work / 'PIPELINE-STATUS.json', dict(phase='test_candidate_complete', release=str(release),
              approved=False, installed=False, coverage=read(release / 'VERIFICATION.json')['counts']))
    except Exception as error:
        write(work / 'PIPELINE-STATUS.json', dict(phase='failed', reason=str(error), approved=False))
        raise


def merge_primary_verification(original, recovered):
    source = original / 'verify-report.json'
    if not source.exists(): return
    current = {r['base_id']: r for r in read(recovered / 'trial-report.json')}
    destination = recovered / 'verify-report.json'
    saved = {r['base_id']: r for r in read(destination)} if destination.exists() else {}
    for row in read(source):
        if current.get(row['base_id'], {}).get('cache_key') == row['cache_key']:
            saved[row['base_id']] = row
    write(destination, sorted(saved.values(), key=lambda r: r['base_id']))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True); p.add_argument('--work-dir', required=True)
    p.add_argument('--prepare-pid', required=True, type=int); p.add_argument('--cook-pid', required=True, type=int)
    a = p.parse_args(); finish(a.config, a.work_dir, a.prepare_pid, a.cook_pid)
