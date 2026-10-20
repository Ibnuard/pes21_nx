"""One bounded Blender process for serial preview requests with exact receipts."""
import json
import os
from pathlib import Path
import subprocess
import uuid

from realface_pipeline import sha

HERE=Path(__file__).resolve().parent
PREFIX='PESNX_PREVIEW_COMPLETE '


class PreviewProcess:
    def __init__(self,blender):
        self.blender=blender;self.process=None;self.jobs=0;self.closing=False
        self.renderer_sha=sha(HERE/'blender_preview_realface.py')

    def __enter__(self):
        return self

    def __exit__(self,*args):
        self.close()

    def __call__(self,targets,log):
        if sha(HERE/'blender_preview_realface.py')!=self.renderer_sha:
            raise ValueError('Preview renderer changed during the batch')
        if self.closing or self.process is None or self.process.poll() is not None or self.jobs>=8:
            self.close()
            self.process=subprocess.Popen([self.blender,'--background','--threads','2',
                '--python-exit-code','1','--python',str(HERE/'blender_realface_preview_worker.py')],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                text=True,encoding='utf-8',errors='replace',bufsize=1,
                creationflags=0x08000000 if os.name=='nt' else 0)
            self.jobs=0
        token=uuid.uuid4().hex
        self.process.stdin.write(json.dumps(dict(token=token,targets=str(targets),renderer_sha256=self.renderer_sha))+'\n')
        self.process.stdin.flush();self.jobs+=1
        with Path(log).open('w',encoding='utf-8') as stream:
            for line in self.process.stdout:
                stream.write(line)
                if not line.startswith(PREFIX):
                    continue
                receipt=json.loads(line[len(PREFIX):])
                if receipt.get('token')!=token:
                    raise ValueError('Mismatched preview receipt')
                if not receipt.get('ok'):
                    raise RuntimeError(receipt.get('reason','Preview failed'))
                if sha(HERE/'blender_preview_realface.py')!=self.renderer_sha:
                    raise ValueError('Preview renderer changed while rendering')
                return
        raise RuntimeError('Blender exited without preview completion')

    def close(self):
        process=self.process
        if process is None:
            return
        self.closing=True
        try:
            # Blender can still write shutdown output after the last receipt.
            # communicate closes stdin and drains that output while waiting;
            # wait alone can deadlock against a full stdout pipe.
            for action,timeout in ((None,20),('terminate',10),('kill',30)):
                if action and process.poll() is None:
                    getattr(process,action)()
                try:
                    process.communicate(timeout=timeout)
                except subprocess.TimeoutExpired:
                    if action=='kill':
                        raise
                else:
                    break
        finally:
            # Keep ownership if shutdown failed: a new request must not start
            # another worker while the previous process is still alive.
            if process.poll() is not None:
                self.process=None;self.closing=False
                if process.stdin is not None:
                    process.stdin.close()
                process.stdout.close()
