"""Pure mocked native-API/validation tests: no workers or memory stress."""
import ctypes
import json
import os
import subprocess
from types import SimpleNamespace

import pytest

import worker_limits as limits


class FakePopen(subprocess.Popen):
    """Type-correct stand-in; never invokes subprocess.Popen.__init__."""
    def __init__(self, pid=None, handle=1234, returncode=None):
        pid = pid if pid is not None else 424242
        while pid in (os.getpid(), os.getppid()):
            pid += 1
        self.pid = pid
        self._handle = handle
        self.returncode = returncode

    def poll(self):
        return self.returncode

    def __del__(self):
        pass


class FakeKernel32:
    def __init__(self, pid, fail=None):
        self.pid = pid
        self.fail = fail
        self.calls = []
        self.closed = []
        self.job_handle = 5678
        self.info = None

    def GetProcessId(self, handle):
        self.calls.append(('GetProcessId', handle.value))
        return 0 if self.fail == 'GetProcessId' else self.pid

    def CreateJobObjectW(self, security, name):
        self.calls.append(('CreateJobObjectW', security, name))
        return 0 if self.fail == 'CreateJobObjectW' else self.job_handle

    def SetInformationJobObject(self, job, kind, pointer, size):
        self.calls.append(('SetInformationJobObject', job, kind, size))
        self.info = limits._JOBOBJECT_EXTENDED_LIMIT_INFORMATION.from_buffer_copy(
            ctypes.string_at(pointer, size))
        return int(self.fail != 'SetInformationJobObject')

    def AssignProcessToJobObject(self, job, process):
        self.calls.append(('AssignProcessToJobObject', job, process.value))
        return int(self.fail != 'AssignProcessToJobObject')

    def CloseHandle(self, job):
        self.calls.append(('CloseHandle', job))
        if self.fail == 'CloseHandle':
            return 0
        self.closed.append(job)
        return 1


@pytest.fixture
def windows_api(monkeypatch):
    process = FakePopen()
    kernel = FakeKernel32(process.pid)
    monkeypatch.setattr(limits, '_IS_WINDOWS', True)
    monkeypatch.setattr(limits, '_load_kernel32', lambda: kernel)
    monkeypatch.setattr(limits, '_native_error', lambda op: OSError(5, op + ' failed'))
    return process, kernel


@pytest.mark.parametrize('value', [None, object(), 1, {'pid': 1234}])
def test_requires_popen_child(value):
    with pytest.raises(TypeError, match='Popen'):
        limits.ProcessBudget(value)


@pytest.mark.parametrize('value', [True, False, 512.0, '512', None])
def test_memory_limit_requires_integer_mib(value):
    with pytest.raises(TypeError, match='positive integer'):
        limits.ProcessBudget(FakePopen(), value)


@pytest.mark.parametrize('value', [0, -1, -512, 1 << (ctypes.sizeof(ctypes.c_size_t) * 8)])
def test_memory_limit_requires_positive_native_size(value):
    with pytest.raises(ValueError, match='SIZE_T'):
        limits.ProcessBudget(FakePopen(), value)


@pytest.mark.parametrize('pid', [None, True, False, 0, -1, 2**32, '42', 42.0])
def test_invalid_pid_never_loads_native_api(monkeypatch, pid):
    process = FakePopen()
    process.pid = pid
    monkeypatch.setattr(limits, '_load_kernel32', lambda: pytest.fail('invalid process reached API'))
    with pytest.raises(ValueError, match='pid'):
        limits.ProcessBudget(process)


@pytest.mark.parametrize('pid', [os.getpid(), os.getppid()])
def test_never_limits_current_application_or_parent(monkeypatch, pid):
    process = FakePopen()
    process.pid = pid
    monkeypatch.setattr(limits, '_load_kernel32', lambda: pytest.fail('parent reached API'))
    with pytest.raises(ValueError, match='current application'):
        limits.ProcessBudget(process)


def test_already_exited_child_rejected_before_native_api(monkeypatch):
    process = FakePopen(returncode=0)
    monkeypatch.setattr(limits, '_load_kernel32', lambda: pytest.fail('exited child reached API'))
    with pytest.raises(ValueError, match='still be running'):
        limits.ProcessBudget(process)


@pytest.mark.parametrize('handle', [None, True, 0, -1, -2, '1234', object(),
                                  (1 << (ctypes.sizeof(ctypes.c_size_t) * 8)) - 1])
def test_invalid_or_pseudo_native_handle_rejected(windows_api, handle):
    process, kernel = windows_api
    process._handle = handle
    with pytest.raises(ValueError, match='handle'):
        limits.ProcessBudget(process)
    assert not kernel.calls


@pytest.mark.parametrize('pid', [os.getpid(), os.getppid(), 1234567])
def test_handle_pid_must_match_validated_child(windows_api, pid):
    process, kernel = windows_api
    kernel.pid = pid
    with pytest.raises(ValueError, match='does not identify'):
        limits.ProcessBudget(process)
    assert [item[0] for item in kernel.calls] == ['GetProcessId']


def test_non_windows_explicitly_not_enforced(monkeypatch):
    monkeypatch.setattr(limits, '_IS_WINDOWS', False)
    monkeypatch.setattr(limits, '_load_kernel32', lambda: pytest.fail('unsupported native API loaded'))
    process = FakePopen()
    budget = limits.ProcessBudget(process)
    assert budget.supported is False
    assert budget.platform_supported() is False
    assert budget.enforced is False
    assert budget.memory_limit_mb == 512
    assert budget.memory_limit_bytes == 512 * 1024 * 1024
    assert 'no cap enforced' in budget.diagnostic
    metadata = budget.metadata
    assert json.loads(json.dumps(metadata)) == metadata
    metadata['enforced'] = True
    assert budget.metadata['enforced'] is False
    # No job exists, so closing an unsupported budget cannot kill a live child.
    budget.close()
    budget.close()
    assert budget.closed is True and budget.enforced is False


def test_windows_job_flags_and_only_supplied_child_handle(windows_api):
    process, kernel = windows_api
    budget = limits.ProcessBudget(process)
    assert budget.supported and budget.enforced and not budget.closed
    assert budget.pid == process.pid
    assert kernel.info.BasicLimitInformation.LimitFlags == 0x2100
    assert kernel.info.ProcessMemoryLimit == 512 * 1024 * 1024
    assert kernel.info.JobMemoryLimit == 0
    assert kernel.calls == [
        ('GetProcessId', process._handle),
        ('CreateJobObjectW', None, None),
        ('SetInformationJobObject', kernel.job_handle, 9,
         ctypes.sizeof(limits._JOBOBJECT_EXTENDED_LIMIT_INFORMATION)),
        ('AssignProcessToJobObject', kernel.job_handle, process._handle),
    ]
    assert not kernel.closed
    assert json.loads(json.dumps(budget.metadata))['enforced'] is True


def test_custom_mib_limit_is_used(windows_api):
    process, kernel = windows_api
    budget = limits.ProcessBudget(process, memory_limit_mb=64)
    assert kernel.info.ProcessMemoryLimit == 64 * 1024 * 1024
    assert budget.memory_limit_mb == 64


@pytest.mark.parametrize('failed', ['GetProcessId', 'CreateJobObjectW',
                                    'SetInformationJobObject', 'AssignProcessToJobObject'])
def test_native_failure_cleans_up_job_without_terminating_process(windows_api, failed):
    process, kernel = windows_api
    kernel.fail = failed
    with pytest.raises(OSError, match=failed):
        limits.ProcessBudget(process)
    should_close = failed in ('SetInformationJobObject', 'AssignProcessToJobObject')
    assert kernel.closed == ([kernel.job_handle] if should_close else [])
    assert process.returncode is None
    if failed != 'AssignProcessToJobObject':
        assert not any(item[0] == 'AssignProcessToJobObject' for item in kernel.calls)


def test_failed_cleanup_preserves_original_attachment_error(windows_api, monkeypatch):
    process, kernel = windows_api
    kernel.fail = 'AssignProcessToJobObject'
    monkeypatch.setattr(kernel, 'CloseHandle', lambda job: 0)
    with pytest.raises(OSError, match='AssignProcessToJobObject') as error:
        limits.ProcessBudget(process)
    assert 'Closing the unconfigured job handle also failed' in error.value.__notes__


def test_close_refuses_live_child_then_closes_once_after_exit(windows_api):
    process, kernel = windows_api
    budget = limits.ProcessBudget(process)
    with pytest.raises(RuntimeError, match='wait for the child'):
        budget.close()
    assert budget.enforced and not budget.closed and not kernel.closed
    process.returncode = 0
    budget.close()
    budget.close()
    assert kernel.closed == [kernel.job_handle]
    assert budget.closed and not budget.enforced
    assert process._handle == 1234  # Budget never owns Popen's process handle.


def test_close_handle_failure_remains_owned_for_retry(windows_api):
    process, kernel = windows_api
    budget = limits.ProcessBudget(process)
    process.returncode = 1
    kernel.fail = 'CloseHandle'
    with pytest.raises(OSError, match='CloseHandle'):
        budget.close()
    assert not budget.closed and budget.enforced
    kernel.fail = None
    budget.close()
    assert kernel.closed == [kernel.job_handle]
    assert budget.closed and not budget.enforced


def test_windows_struct_layout_uses_fixed_width_dword_and_pointer_size():
    pointer_size = ctypes.sizeof(ctypes.c_void_p)
    assert ctypes.sizeof(limits._DWORD) == 4
    assert ctypes.sizeof(limits._SIZE_T) == pointer_size
    assert ctypes.sizeof(limits._IO_COUNTERS) == 48
    # Both layouts are the native Windows ABI, not a packed byte structure.
    assert ctypes.sizeof(limits._JOBOBJECT_BASIC_LIMIT_INFORMATION) == (64 if pointer_size == 8 else 48)
    assert ctypes.sizeof(limits._JOBOBJECT_EXTENDED_LIMIT_INFORMATION) == (144 if pointer_size == 8 else 112)
    assert limits._JOBOBJECT_EXTENDED_LIMIT_INFORMATION.ProcessMemoryLimit.offset == (112 if pointer_size == 8 else 96)


def test_native_function_prototypes(monkeypatch):
    class Function:
        pass
    names = ('CreateJobObjectW', 'SetInformationJobObject',
             'AssignProcessToJobObject', 'GetProcessId', 'CloseHandle')
    kernel = SimpleNamespace(**{name: Function() for name in names})
    calls = []
    def load(name, **kwargs):
        calls.append((name, kwargs))
        return kernel
    monkeypatch.setattr(ctypes, 'WinDLL', load, raising=False)
    assert limits._load_kernel32() is kernel
    assert calls == [('kernel32', {'use_last_error': True})]
    assert kernel.CreateJobObjectW.restype is ctypes.c_void_p
    assert kernel.GetProcessId.restype is ctypes.c_uint32
    assert kernel.AssignProcessToJobObject.argtypes == [ctypes.c_void_p, ctypes.c_void_p]
    assert kernel.SetInformationJobObject.argtypes[-1] is ctypes.c_uint32
