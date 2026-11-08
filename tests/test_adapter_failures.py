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


def append_exited_task(runner):
    """Only fake resources; no child, temporary directory or disk operation."""
    process = FakeProcess()
    process.returncode = 0
    directory, resources = FakeDirectory(), FakeResources()
    task = ai_async._Task(process, directory, 'retired-token', (), 0, 0,
                          resources=resources)
    runner.retired.append(task)
    return task


@pytest.mark.parametrize('operation', ['reap', 'close'])
@pytest.mark.parametrize('stage', ['resources', 'directory'])
def test_cleanup_failure_keeps_failed_task_attempts_sibling_and_retries(monkeypatch, operation, stage):
    runner = ai_async.AsyncAI()
    first = append_exited_task(runner)
    second = append_exited_task(runner)
    owner = getattr(first, stage)
    method = 'close' if stage == 'resources' else 'cleanup'
    original = getattr(owner, method)
    attempts = []
    def fail_once():
        attempts.append(stage)
        if len(attempts) == 1:
            raise OSError('transient ' + stage + ' cleanup failure')
        original()
    monkeypatch.setattr(owner, method, fail_once)

    if operation == 'close':
        with pytest.raises(OSError, match='Worker cleanup incomplete') as caught:
            runner.close()
        assert 'transient ' + stage in str(caught.value.__cause__)
        assert any(stage in note for note in caught.value.__notes__)
    else:
        runner.reap()
    assert runner.retired == [first]
    assert not runner.busy
    assert not first.directory.cleaned
    assert first.resources.closed is (stage == 'directory')
    assert second.directory.cleaned and second.resources.closed
    assert attempts == [stage]

    getattr(runner, operation)()
    assert not runner.retired
    assert first.directory.cleaned and first.resources.closed
    assert attempts == [stage, stage]
    runner.close()  # Idempotent; successful siblings are never retried.
    assert attempts == [stage, stage]


@pytest.mark.parametrize('operation', ['reap', 'close'])
@pytest.mark.parametrize('failure', ['oserror', 'timeout'])
def test_wait_failure_preserves_task_and_does_not_skip_sibling(monkeypatch, operation, failure):
    runner = ai_async.AsyncAI()
    first = append_exited_task(runner)
    second = append_exited_task(runner)
    original_wait = first.process.wait
    waits = []
    def wait(timeout=None):
        waits.append(timeout)
        if len(waits) == 1:
            if failure == 'timeout':
                raise subprocess.TimeoutExpired('fake', timeout)
            raise OSError('transient wait failure')
        return original_wait(timeout)
    monkeypatch.setattr(first.process, 'wait', wait)

    if operation == 'close':
        with pytest.raises(OSError, match='Worker cleanup incomplete'):
            runner.close()
    else:
        runner.reap()
    assert runner.retired == [first]
    assert not first.resources.closed and not first.directory.cleaned
    assert second.resources.closed and second.directory.cleaned
    getattr(runner, operation)()
    assert waits == ([0, 0] if operation == 'reap' else [1.0, 1.0])
    assert first.resources.closed and first.directory.cleaned
    assert not runner.retired
    runner.close()


@pytest.mark.parametrize('operation', ['reap', 'close'])
def test_live_worker_kill_failure_retains_ownership_and_attempts_sibling(monkeypatch, operation):
    runner = ai_async.AsyncAI()
    first = append_exited_task(runner)
    first.process.returncode = None
    second = append_exited_task(runner)
    original_kill = first.process.kill
    kills = []
    def kill():
        kills.append(1)
        if len(kills) == 1:
            raise OSError('transient kill failure')
        original_kill()
    def wait(timeout=None):
        assert first.process.poll() is not None, 'never wait after a failed live-child kill'
        return first.process.returncode
    monkeypatch.setattr(first.process, 'kill', kill)
    monkeypatch.setattr(first.process, 'wait', wait)

    if operation == 'close':
        with pytest.raises(OSError, match='Worker cleanup incomplete'):
            runner.close()
    else:
        runner.reap()
    assert runner.retired == [first]
    assert first.process.poll() is None
    assert not first.resources.closed and not first.directory.cleaned
    assert second.resources.closed and second.directory.cleaned
    getattr(runner, operation)()
    assert len(kills) == 2 and not runner.retired
    assert first.resources.closed and first.directory.cleaned
    runner.close()


def test_reap_never_waits_or_cleans_before_worker_reports_exit(monkeypatch):
    runner = ai_async.AsyncAI()
    task = append_exited_task(runner)
    task.process.returncode = None
    monkeypatch.setattr(task.process, 'kill', lambda: None)
    def must_not_wait(timeout=None):
        pytest.fail('nonblocking reap must not wait for a live worker')
    monkeypatch.setattr(task.process, 'wait', must_not_wait)
    runner.reap()
    assert runner.retired == [task]
    assert not task.resources.closed and not task.directory.cleaned
    task.process.returncode = 0
    monkeypatch.setattr(task.process, 'wait', lambda timeout=None: 0)
    runner.close()
    assert not runner.retired and task.resources.closed and task.directory.cleaned


def test_close_retains_active_task_on_failure_without_duplicate_retirement(monkeypatch):
    runner = ai_async.AsyncAI()
    task = append_exited_task(runner)
    runner.retired.clear()
    runner.task = task
    original = task.resources.close
    attempts = []
    def close_once():
        attempts.append(1)
        if len(attempts) == 1:
            raise OSError('transient job close failure')
        original()
    monkeypatch.setattr(task.resources, 'close', close_once)
    with pytest.raises(OSError, match='Worker cleanup incomplete'):
        runner.close()
    assert not runner.busy and runner.retired == [task]
    assert not task.resources.closed and not task.directory.cleaned
    runner.close()
    assert len(attempts) == 2 and not runner.retired
    assert task.resources.closed and task.directory.cleaned
