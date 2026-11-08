"""Native per-child memory budget, independent of search and UI policy.

Windows uses a Job Object with PROCESS_MEMORY and KILL_ON_JOB_CLOSE. Other
platforms explicitly report that no OS memory limit is enforced. This module
never assigns the calling application (or its parent) to a job, starts a
process, or terminates/reaps the supplied child on an attachment failure.
"""
import ctypes
import os
import subprocess
import sys


DEFAULT_MEMORY_LIMIT_MB = 512
_MIB = 1024 * 1024
_IS_WINDOWS = sys.platform == 'win32'
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9
_JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_SIZE_T = ctypes.c_size_t
_DWORD = ctypes.c_uint32  # Windows DWORD stays 32 bits on a 64-bit interpreter.
_HANDLE = ctypes.c_void_p


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('PerProcessUserTimeLimit', ctypes.c_int64),
        ('PerJobUserTimeLimit', ctypes.c_int64),
        ('LimitFlags', _DWORD),
        ('MinimumWorkingSetSize', _SIZE_T),
        ('MaximumWorkingSetSize', _SIZE_T),
        ('ActiveProcessLimit', _DWORD),
        ('Affinity', _SIZE_T),
        ('PriorityClass', _DWORD),
        ('SchedulingClass', _DWORD),
    ]


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ('ReadOperationCount', ctypes.c_uint64),
        ('WriteOperationCount', ctypes.c_uint64),
        ('OtherOperationCount', ctypes.c_uint64),
        ('ReadTransferCount', ctypes.c_uint64),
        ('WriteTransferCount', ctypes.c_uint64),
        ('OtherTransferCount', ctypes.c_uint64),
    ]


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('BasicLimitInformation', _JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ('IoInfo', _IO_COUNTERS),
        ('ProcessMemoryLimit', _SIZE_T),
        ('JobMemoryLimit', _SIZE_T),
        ('PeakProcessMemoryUsed', _SIZE_T),
        ('PeakJobMemoryUsed', _SIZE_T),
    ]


def _load_kernel32():
    """Load Windows APIs lazily; importing on other platforms is harmless."""
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.CreateJobObjectW.argtypes = [_HANDLE, ctypes.c_wchar_p]
    kernel32.CreateJobObjectW.restype = _HANDLE
    kernel32.SetInformationJobObject.argtypes = [_HANDLE, ctypes.c_int,
                                               ctypes.c_void_p, _DWORD]
    kernel32.SetInformationJobObject.restype = ctypes.c_int32
    kernel32.AssignProcessToJobObject.argtypes = [_HANDLE, _HANDLE]
    kernel32.AssignProcessToJobObject.restype = ctypes.c_int32
    kernel32.GetProcessId.argtypes = [_HANDLE]
    kernel32.GetProcessId.restype = _DWORD
    kernel32.CloseHandle.argtypes = [_HANDLE]
    kernel32.CloseHandle.restype = ctypes.c_int32
    return kernel32


def _native_error(operation):
    # Called only after a failed Windows API; use_last_error preserves the code.
    code = ctypes.get_last_error()
    return ctypes.WinError(code, operation + ' failed')


class ProcessBudget:
    """Attach a native memory cap to one already-running Popen child.

    ``memory_limit_mb`` is a positive integer number of MiB (default 512).
    On Windows successful construction means the supplied child is assigned to
    an owned Job Object. Native setup failures raise OSError after job cleanup;
    the caller must terminate/wait its child if it cannot safely proceed.

    ``supported`` describes platform support; ``enforced`` is True only while
    an attached Windows job handle is owned. Non-Windows construction is an
    explicit unsupported result, never a claim of a portable OS memory cap.

    Call ``close()`` only after poll()/wait() confirms the child exited. It is
    idempotent, does not close Popen's process handle, and refuses to close a
    live attached job because KILL_ON_JOB_CLOSE would terminate that child.
    The OS also closes this non-inheritable handle if the parent application
    exits, killing workers left in the job. Do not use as a live-task context
    manager and do not depend on Python garbage-collection finalizers.
    """
    def __init__(self, process, memory_limit_mb=DEFAULT_MEMORY_LIMIT_MB):
        if not isinstance(process, subprocess.Popen):
            raise TypeError('process must be a subprocess.Popen child')
        if type(memory_limit_mb) is not int:
            raise TypeError('memory_limit_mb must be a positive integer MiB count')
        max_bytes = (1 << (ctypes.sizeof(_SIZE_T) * 8)) - 1
        if not 0 < memory_limit_mb <= max_bytes // _MIB:
            raise ValueError('memory_limit_mb must be positive and fit native SIZE_T')
        pid = getattr(process, 'pid', None)
        if type(pid) is not int or not 0 < pid <= 0xFFFFFFFF:
            raise ValueError('process must have a valid positive Windows-compatible pid')
        if pid in (os.getpid(), os.getppid()):
            raise ValueError('refusing to limit the current application or its parent')
        if process.poll() is not None:
            raise ValueError('process must still be running when its budget is attached')

        self._process = process
        self.pid = pid
        self.memory_limit_mb = memory_limit_mb
        self.memory_limit_bytes = memory_limit_mb * _MIB
        self.supported = self.platform_supported()
        self.enforced = False
        self.closed = False
        self._kernel32 = None
        self._job_handle = None
        self.diagnostic = 'OS memory limits are unsupported on this platform; no cap enforced'
        if not self.supported:
            return

        raw_handle = getattr(process, '_handle', None)
        # subprocess.Handle is an int subclass on CPython/Windows. Reject bool,
        # pseudo handles (-1/-2), null handles and arbitrary coercible objects.
        if not isinstance(raw_handle, int) or isinstance(raw_handle, bool):
            raise ValueError('Windows Popen child must expose a valid native process handle')
        if not 0 < raw_handle < max_bytes:
            raise ValueError('Windows child handle must not be null or a pseudo handle')
        kernel32 = _load_kernel32()
        handle_pid = kernel32.GetProcessId(_HANDLE(raw_handle))
        if not handle_pid:
            raise _native_error('GetProcessId')
        if handle_pid != self.pid or handle_pid in (os.getpid(), os.getppid()):
            raise ValueError('native process handle does not identify the supplied child')

        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            raise _native_error('CreateJobObjectW')
        try:
            info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            info.BasicLimitInformation.LimitFlags = (
                _JOB_OBJECT_LIMIT_PROCESS_MEMORY | _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)
            info.ProcessMemoryLimit = self.memory_limit_bytes
            if not kernel32.SetInformationJobObject(
                    job, _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
                    ctypes.byref(info), ctypes.sizeof(info)):
                raise _native_error('SetInformationJobObject')
            if not kernel32.AssignProcessToJobObject(job, _HANDLE(raw_handle)):
                raise _native_error('AssignProcessToJobObject')
        except BaseException as error:
            # Nothing is assigned on normal API failure, so this does not kill
            # the caller or leave an unowned job handle behind. Preserve the
            # original native error; surface cleanup failure as extra context.
            if not kernel32.CloseHandle(job):
                error.add_note('Closing the unconfigured job handle also failed')
            raise
        self._kernel32 = kernel32
        self._job_handle = job
        self.enforced = True
        self.diagnostic = 'Windows Job Object per-process committed-memory cap active'

    @staticmethod
    def platform_supported():
        """Whether this module implements a native cap on this platform."""
        return _IS_WINDOWS

    @property
    def metadata(self):
        """Small JSON-serializable status; no raw handles or process objects."""
        return {'platform': sys.platform, 'supported': self.supported,
                'enforced': self.enforced, 'closed': self.closed,
                'pid': self.pid, 'memory_limit_mb': self.memory_limit_mb,
                'memory_limit_bytes': self.memory_limit_bytes,
                'diagnostic': self.diagnostic}

    def close(self):
        """Release an exited child's job; refuse accidental live-child kills."""
        if self.closed:
            return
        if self._job_handle is not None:
            if self._process.poll() is None:
                raise RuntimeError('wait for the child to exit before closing its process budget')
            if not self._kernel32.CloseHandle(self._job_handle):
                # Keep ownership so callers can retry; do not claim cleanup.
                raise _native_error('CloseHandle')
            self._job_handle = None
        self.closed = True
        self.enforced = False
        self.diagnostic = ('Windows job handle closed after child exit' if self.supported
                           else 'Closed unsupported budget; no OS cap was enforced')
