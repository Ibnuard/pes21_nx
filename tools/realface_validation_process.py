"""One lazily started, reusable Blender validator for one worker thread."""
import json
from pathlib import Path
import subprocess
import uuid

from blender_realface_validate_worker import PREFIX


class ValidationProcess:
    def __init__(self, blender):
        self.blender = blender
        self.process = None

    def __call__(self, profile, log):
        if self.process is None or self.process.poll() is not None:
            self.close()
            self.process = subprocess.Popen([
                str(self.blender), '--background', '--threads', '2', '--python-exit-code', '1',
                '--python', str(Path(__file__).with_name('blender_realface_validate_worker.py'))],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding='utf-8', errors='replace', bufsize=1)
        token = uuid.uuid4().hex
        self.process.stdin.write(json.dumps(dict(token=token, profile=str(profile))) + '\n')
        self.process.stdin.flush()
        with Path(log).open('w', encoding='utf-8') as stream:
            for line in self.process.stdout:
                stream.write(line)
                if line.startswith(PREFIX):
                    result = json.loads(line[len(PREFIX):])
                    if result.get('token') != token:
                        raise ValueError('Validator response belongs to another player')
                    if not result.get('ok'):
                        raise ValueError(result.get('reason', 'Cook validation failed'))
                    return
        raise RuntimeError('Blender validator exited before returning a result')

    def close(self):
        process, self.process = self.process, None
        if process is None:
            return
        try:
            if process.poll() is None:
                process.stdin.close()
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    process.wait(timeout=10)
        finally:
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
            if process.stdout:
                process.stdout.close()
