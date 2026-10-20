import io
import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import realface_preview_process as preview


class Process:
    def __init__(self,mode='ok'):
        self.stdin=self;self.stdout=io.StringIO();self.code=None;self.mode=mode
    def poll(self):return self.code
    def write(self,line):
        request=json.loads(line)
        token='wrong' if self.mode=='wrong' else request['token']
        self.stdout=io.StringIO('render detail\n'+preview.PREFIX+json.dumps(dict(
            token=token,ok=self.mode=='ok',reason='render failed'))+'\n')
    def flush(self):pass
    def close(self):self.code=0
    def wait(self,timeout):self.code=0
    def terminate(self):self.code=-1
    def kill(self):self.code=-9
    def communicate(self,timeout):
        self.close();return self.stdout.read(),None


def test_preview_worker_reuses_one_process_and_bounds_its_lifetime(tmp_path,monkeypatch):
    calls=[]
    def launch(*args,**kwargs):
        calls.append(args[0]);return Process()
    monkeypatch.setattr(preview.subprocess,'Popen',launch)
    with preview.PreviewProcess('blender') as worker:
        for i in range(9):
            worker(tmp_path/'targets.json',tmp_path/(str(i)+'.log'))
        assert len(calls)==2 and worker.jobs==1
        assert 'blender_realface_preview_worker.py' in calls[0][-1]
    assert worker.process is None


@pytest.mark.parametrize('mode,message',[('wrong','Mismatched'),('failed','render failed')])
def test_failed_or_wrong_receipt_cannot_complete_preview(tmp_path,monkeypatch,mode,message):
    monkeypatch.setattr(preview.subprocess,'Popen',lambda *a,**k:Process(mode))
    with preview.PreviewProcess('blender') as worker:
        with pytest.raises((RuntimeError,ValueError),match=message):
            worker(tmp_path/'targets.json',tmp_path/'render.log')


def test_renderer_edit_rejects_reusing_worker(tmp_path,monkeypatch):
    worker=preview.PreviewProcess('blender')
    monkeypatch.setattr(preview,'sha',lambda p:'changed')
    with pytest.raises(ValueError,match='renderer changed'):
        worker(tmp_path/'targets.json',tmp_path/'render.log')


def test_shutdown_drains_output_larger_than_the_pipe_without_terminating():
    # This child writes only after stdin EOF, just like Blender teardown.
    # Waiting without draining stdout blocks and eventually terminates it.
    process=preview.subprocess.Popen([sys.executable,'-u','-c',
        "import sys; sys.stdin.read(); sys.stdout.write('shutdown\\n'*200000); sys.stdout.flush()"],
        stdin=preview.subprocess.PIPE,stdout=preview.subprocess.PIPE,
        stderr=preview.subprocess.STDOUT,text=True)
    worker=preview.PreviewProcess('unused');worker.process=process
    try:
        worker.close()
        assert process.returncode==0
        assert worker.process is None and process.stdout.closed
    finally:
        if process.poll() is None:
            process.kill();process.communicate(timeout=10)


@pytest.mark.parametrize('timeouts',[1,2,3])
def test_slow_shutdown_escalates_and_keeps_ownership_until_reaped(tmp_path,monkeypatch,timeouts):
    class SlowProcess(Process):
        def __init__(self):
            super().__init__();self.calls=[];self.attempts=0
        def communicate(self,timeout):
            self.attempts+=1
            if timeouts==3 or self.attempts<=timeouts:
                raise preview.subprocess.TimeoutExpired('blender',timeout)
            self.code=0;return '',None
        def terminate(self):self.calls.append('terminate')
        def kill(self):self.calls.append('kill')
    process=SlowProcess();worker=preview.PreviewProcess('unused');worker.process=process
    monkeypatch.setattr(preview.subprocess,'Popen',lambda *a,**k:pytest.fail('Duplicate worker started'))
    if timeouts==3:
        with pytest.raises(preview.subprocess.TimeoutExpired):
            worker.close()
        assert worker.process is process and process.poll() is None
        assert not process.stdout.closed
        assert worker.closing
        monkeypatch.setattr(process,'write',lambda *a:pytest.fail('Reused a closing worker'))
        with pytest.raises(preview.subprocess.TimeoutExpired):
            worker(tmp_path/'unused-targets.json',tmp_path/'unused-render.log')
        assert not (tmp_path/'unused-render.log').exists()
    else:
        worker.close()
        assert worker.process is None and process.stdout.closed
    assert process.calls[:2]==(['terminate'] if timeouts==1 else ['terminate','kill'])
