"""Pure mocks preserve child ownership across attach and cancellation failures."""
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


class FakeDirectory:
    name = 'unused-mock-worker'
    def __init__(self):
        self.cleaned = False
    def cleanup(self):
        self.cleaned = True


class FakeResources:
    def __init__(self):
        self.closed = False
    def close(self):
        self.closed = True


def install_task(runner, process, monkeypatch):
    # No subprocess, temp directory or cancel marker is created by these tests.
    monkeypatch.setattr(ai_async.Path, 'touch', lambda *a, **k: None)
    directory, resources = FakeDirectory(), FakeResources()
    runner.task = ai_async._Task(process, directory, 'token', (), 0, 0,
                                 resources=resources)
    return directory, resources


@pytest.mark.parametrize('terminate_error', [False, True])
def test_cancel_escalates_live_worker_without_waiting(monkeypatch, terminate_error):
    process = FakeProcess(terminate_error=terminate_error)
    waits = []
    original_wait = process.wait
    def wait(timeout=None):
        waits.append(timeout)
        assert process.poll() is not None, 'cancel must never wait for a live worker'
        return original_wait(timeout)
    monkeypatch.setattr(process, 'wait', wait)
    runner = ai_async.AsyncAI()
    directory, resources = install_task(runner, process, monkeypatch)
    try:
        runner.cancel()
        assert process.terminated and process.killed
        assert not runner.busy and not runner.retired
        assert waits == [0]
        assert directory.cleaned and resources.closed
    finally:
        runner.close()


def test_failed_kill_stays_owned_and_is_retried_by_reap(monkeypatch):
    process = FakeProcess(terminate_error=True)
    kills = []
    def kill():
        kills.append(1)
        if len(kills) == 1:
            raise OSError('temporary kill failure')
        process.returncode = -1
    monkeypatch.setattr(process, 'kill', kill)
    runner = ai_async.AsyncAI()
    directory, resources = install_task(runner, process, monkeypatch)
    try:
        runner.cancel()
        assert not runner.busy and len(runner.retired) == 1
        assert process.poll() is None
        assert not directory.cleaned and not resources.closed
        runner.reap()
        assert len(kills) == 2 and not runner.retired
        assert directory.cleaned and resources.closed
    finally:
        runner.close()
