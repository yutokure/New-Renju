# Worker resource limits

[worker_limits.py](<../worker_limits.py>) provides an operating-system memory budget for a **single supplied subprocess**, independently of AI difficulty, search algorithm, wall-clock deadline, or the UI. The adapter owns process lifecycle and integrates this budget immediately after spawning the worker.

## API

```python
from worker_limits import ProcessBudget

process = subprocess.Popen(command, ...)  # Adapter starts its own child.
try:
    resources = ProcessBudget(process, memory_limit_mb=512)
except (OSError, ValueError, TypeError):
    # Fail closed: caller must terminate/kill and wait for its child.
    ...

# Polling must remain nonblocking on the UI thread.
info = resources.metadata
# After process termination and wait()/poll() establishes exit:
resources.close()
```

- `ProcessBudget(process, memory_limit_mb=512)` requires a `subprocess.Popen` object that is still running. Its PID must be a positive 32-bit integer and must not identify the current application or its parent.
- `memory_limit_mb` is a positive **integer MiB count**, not decimal megabytes. `512` means 536,870,912 bytes. Booleans, floats, strings, zero, negative values, and values that cannot fit native `SIZE_T` are rejected rather than coerced.
- `ProcessBudget.platform_supported()` is a platform-support query. Instance `supported` indicates native support; `enforced` indicates ownership of an attached Windows job; `closed` indicates cleanup completion.
- `pid`, `memory_limit_mb`, `memory_limit_bytes`, and `diagnostic` are available as attributes. `metadata` returns a fresh JSON-serializable dictionary with these fields plus `platform`, `supported`, `enforced`, and `closed`. It does not expose raw handles or the process object.
- `close()` is idempotent. On Windows it **refuses a still-live child with `RuntimeError`**: wait for the process to exit before closing its job. A failed native handle close raises `OSError` while retaining ownership for a possible retry. The budget never closes the process handle owned by `Popen` and does not reap the process.
- There is deliberately no destructor/context-manager that might silently kill a live worker during routine object cleanup. The adapter explicitly closes every retired worker's job after exit.

## Windows implementation and safety

Windows uses `ctypes.WinDLL('kernel32', use_last_error=True)` with explicit argument/result types. The native structures use 32-bit `DWORD`, 64-bit counters, and pointer-sized `SIZE_T`; they use normal ABI alignment, not packed layout. This avoids handle truncation and incorrect structure offsets on 64-bit Python.

Before creating or assigning any job, `GetProcessId(Popen._handle)` must match the validated child PID. Null/pseudo handles and mismatched handles are rejected. The module does **not** call `GetCurrentProcess`, assign the application to a job, or configure system-wide memory policy. It affects only the supplied child handle, although normal Windows job membership also applies to descendants the worker may create.

The module creates an **unnamed, non-inheritable Job Object**, sets `JOBOBJECT_EXTENDED_LIMIT_INFORMATION` (information class 9), then assigns the child. The flags are:

- `JOB_OBJECT_LIMIT_PROCESS_MEMORY` (`0x00000100`), with `ProcessMemoryLimit = memory_limit_mb * 1024 * 1024`.
- `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` (`0x00002000`). If the application exits and Windows closes its last job handle, workers still in that job are terminated instead of surviving as orphans.

The cap is **per-process committed memory**, not a reservation, working-set/RSS limit, total-system RAM limit, or a hard limit on combined memory of every descendant. Exceeding the process commit limit causes allocations to fail. An unhandled Python `MemoryError` or native allocator failure commonly ends the worker, but the process-memory flag alone does **not** promise immediate termination of a worker that catches failures and loops. The adapter's independent wall-clock watchdog and cancellation/termination policy remain necessary. A memory-related worker exit must not crash or block the application; the adapter can use its last verified result or report failure.

A child is already running briefly before attachment. This avoids changing the parent's spawn implementation, but is not a security sandbox or a guarantee that no startup allocation occurred before attachment. If the child exits before attachment, the caller can reap the finished process. Existing host jobs can prohibit nesting/assignment. Native setup errors (including nesting restrictions and invalid handles) raise `OSError`, with the original Windows error code preserved; the constructor closes any created job handle on the failure path. It does not secretly fall back to an unenforced Windows budget. The adapter must terminate and reap a still-running child after an attachment failure.

## Non-Windows behavior

Other platforms explicitly return `supported=False`, `enforced=False`, and a diagnostic that no OS cap is enforced. There is no imitation portable cap, `resource` wrapper, or claim of native protection. Input/process validation still applies. Since an unsupported budget owns no job handle, closing it is harmless even while the child is alive. Wall-clock/cancellation policies are separate from native memory support.

## Validation and operational testing boundary

[Mocked tests](<../tests/test_worker_limits.py>) exercise argument and PID/handle validation; prevention of current/parent process targeting; Windows function signatures and structure offsets; exact process-memory/kill-on-close flags and byte count; use of only the supplied child handle; native-error cleanup; guarded/idempotent close; retry after close failure; serializable metadata; and explicit non-Windows behavior.

```text
python -B -m pytest tests/test_worker_limits.py -q
```

These tests do not spawn a process or allocate stress memory, so they do not compete with serial AI performance measurements. They establish API/structure correctness, **not measured real-world cap enforcement**. A native Windows smoke test and a controlled allocation-limit test must run separately after benchmark measurements, targeting only a disposable child and verifying the application remains responsive. The parent owns those operational tests and the adapter integration.
