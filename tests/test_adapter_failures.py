"""Pure mocks preserve child ownership across native attach failures."""
import subprocess
import pytest
import ai_async
import worker_limits
from board import Board, BLACK


class FakeProcess:
    def __init__(self, terminate_error=False, wait_timeout=False):
        self.returncode=None
        self.terminate_error=terminate_error
        self.wait_timeout=wait_timeout
        self.terminated=self.killed=False
    def poll(self):
        return self.returncode
    def terminate(self):
        self.terminated=True
        if self.terminate_error:
            raise OSError('terminate failed')
    def kill(self):
        self.killed=True
        self.returncode=-1
    def wait(self,timeout=None):
        if self.wait_timeout and self.returncode is None:
            raise subprocess.TimeoutExpired('fake',timeout)
        if self.returncode is None:
            self.returncode=-1
        return self.returncode


@pytest.mark.parametrize('terminate_error,wait_timeout',[(False,True),(True,False),(False,False)])
def test_attach_failure_kills_reaps_preserves_error(monkeypatch,terminate_error,wait_timeout):
    process=FakeProcess(terminate_error,wait_timeout)
    monkeypatch.setattr(ai_async.subprocess,'Popen',lambda *a,**k:process)
    def fail(*args,**kwargs):
        raise OSError('native attach denied')
    monkeypatch.setattr(worker_limits,'ProcessBudget',fail)
    runner=ai_async.AsyncAI()
    try:
        with pytest.raises(OSError,match='native attach denied'):
            runner.start(Board(),BLACK,0,'hard')
        assert process.terminated
        assert process.poll() is not None or runner.retired
        if terminate_error or wait_timeout:
            assert process.killed
        assert not runner.busy
    finally:
        runner.close()
    assert not runner.retired


@pytest.mark.parametrize('limit',[0,-1,True,512.0,'512',10**100])
def test_bad_memory_config_never_spawns(monkeypatch,limit):
    monkeypatch.setattr(ai_async.subprocess,'Popen',lambda *a,**k:pytest.fail('must validate before spawn'))
    with pytest.raises(ValueError):
        ai_async.AsyncAI(memory_limit_mb=limit)
