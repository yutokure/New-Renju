# Independent review: native worker memory limits and adapter integration

Date: 2026-11-08 (Asia/Tokyo). Scope is deliberately narrow: [worker_limits.py](<../worker_limits.py>), the `ProcessBudget` integration in [ai_async.py](<../ai_async.py>), [mock tests](<../tests/test_worker_limits.py>) and [resource-limit documentation](<worker-resource-limits.md>). This reviewer did not edit production sources or tests, change Git state, launch workers, or run performance/stress tests. Serial match measurements were left undisturbed.

## Disposition

| Component / evidence | Status | Meaning |
| --- | --- | --- |
| `ProcessBudget` API and native-cap source design | **PASS** | No blocking ABI, process-targeting, flag, ownership or normal native-error-cleanup error found in the inspected source. This is a source/API review, not proof of operational enforcement. |
| `AsyncAI` attachment-failure lifecycle | **PASS** (source + narrow mock) | Initial WLR-01 was corrected during review: expected termination/timeout failures retain ownership and preserve the assignment error. Native failure-path behavior remains an operational check. |
| Resource-status/configuration integration | **PASS** (source) | Initial WLR-02 and WLR-03 were corrected during review, including the native-pointer-width upper bound. See the remaining snapshot-status note below. |
| Windows memory-limit operational evidence | **PASS** (limited parent-reported checks; artifacts inspected) | A 512 MiB VH worker completed and a controlled 64 MiB child rejected a 192 MiB allocation; this reviewer did not execute or witness those checks. |
| Parent-death enforcement | **PASS** (limited parent-reported check; artifact inspected) | A supervised controller exited and its child was recorded signaled afterward, while the outer parent survived. This reviewer did not execute the native test. |
| Frozen worker/adapter with explicit workspace request root | **PASS** (bounded parent-reported checks; artifacts and probe source inspected) | All four workers and real adapter move requests, deferred validation and cancellation passed using the explicitly configured root and frozen 1024 MiB cap. This is not default-TEMP or packaged-GUI approval. |
| Frozen packaged GUI/default-TEMP readiness | **CHANGES REQUESTED** | The default request directory behavior was not changed and remains unapproved in this environment; explicit-root success does not close that release gate. |
| Native adapter failure cleanup | **PASS** (limited parent-reported check; artifact inspected) | A memory-failure child exited 77; the adapter returned a safe error, closed resources, removed its temporary directory and left no retired children. |
| Overall narrow review | **CHANGES REQUESTED** | Native and explicit-root frozen components pass within their evidence bounds; packaged-GUI/default-TEMP readiness remains unapproved. |

## Initial findings and resolution

The findings below describe the initial snapshot. The parent corrected them while this review was in progress, and this reviewer re-read the updated source and repeated the narrow cleanup probe. The source is not immutable during the review; line links below identify the current relevant area, while the quoted old control flow remains a historical finding.

### WLR-01 — attachment failure can lose child ownership (high priority; resolved)

At the inspected [adapter attachment failure path:93–100](<../ai_async.py#L93-L100>), a running child is handled by `terminate(); wait(timeout=1.0); directory.cleanup(); raise`. None of these operations has a cleanup `finally`, a kill fallback, or a retained task. The active task is not installed until after this block.

If `terminate()` raises `OSError`, or `wait()` raises `subprocess.TimeoutExpired`, control leaves before directory cleanup and before the process is registered in `task`/`retired`. The original assignment error is also replaced by the cleanup error. A worker that never received a native cap can therefore be left unowned, while the UI receives an unexpected exception. The wait also runs synchronously in `start()` on this error path.

**Independent reproduction (mocks only):** replaced `Popen` with a no-process fake; replaced `ProcessBudget` with an `OSError`; made fake `wait()` raise `TimeoutExpired`. Observed:

```text
raised=TimeoutExpired
terminated=True
kill_fallback=False
directory_cleaned=False
task=None
retired=0
```

**Requested correction:** establish adapter ownership immediately after spawning, before attempting attachment; preserve it through every failure path. Request termination and retain/reap the failed child nonblockingly, with a hard-stop fallback if needed, then clean the temporary directory only after child exit. Preserve/report the original assignment error and any cleanup failure. Add mock integration cases for terminate failure, wait timeout, and native assignment failure followed by successful retirement. Do not silently proceed with an uncapped *live* Windows worker.

**Resolution verified:** the updated [failure path:95–119](<../ai_async.py#L95-L119>) registers a retired task before termination, catches termination `OSError` with a kill attempt, waits at most 0.1 seconds, attempts kill on `TimeoutExpired`, and reaps while retaining a still-live task. The same independent fake-wait-timeout probe now observes the original `OSError`, `terminated=True`, `kill_fallback=True`, `task=None`, `retired=1`, and `owns_child=True`. This addresses the concrete ownership-loss reproduction. The error path is bounded rather than strictly nonblocking (up to 0.1 seconds); no native worker failure was exercised by this reviewer.

### WLR-02 — progress metadata loses the cap status (medium priority; resolved for attached tasks)

Initial `last_info` contains `resource_limits`, and final `poll()` results add it, but [progress reading:136–137](<../ai_async.py#L136-L137>) replaces `last_info` directly with the worker packet. Normal worker packets do not own or know the parent-held Job Object. During the actual thinking interval the cap status disappears from public adapter progress.

Keep resource metadata authoritative in the parent, and merge the current metadata into every public progress snapshot. A child-supplied field should never supersede parent resource status. Distinguish native support, successful attachment, exited-before-attachment, and cleanup completion rather than implying that a missing field means enforcement.

**Resolution verified:** [progress:155–158](<../ai_async.py#L155-L158>) now merges `task.resources.metadata` into accepted worker progress before publishing it. Parent-held status is authoritative for attached tasks. Minor residual: the `resources=None` fast-exited-child route still has only terminal/initial parent diagnostics, and terminal status is a snapshot taken before asynchronous reap; callers should not interpret its `closed=False` as permanent handle leakage.

### WLR-03 — invalid configuration is checked after spawn and can be swallowed (medium priority; resolved on current x64/default path)

`AsyncAI.__init__` stores `memory_limit_mb` without validating it. In `start()`, `ProcessBudget` may reject a boolean, float, zero, negative or overflowing limit, but the adapter catches that `TypeError`/`ValueError` together with native attachment errors. If the child has already exited by the next `poll()`, the adapter accepts the fast-exit path and returns normally, concealing the invalid caller configuration.

Validate the limit before spawning (using the same positive-integer/SIZE_T contract), and reserve the fast-exit exception for a genuinely completed child. A promptly exited worker needs no subsequent memory cap, but does not make an invalid API configuration valid. No real child was launched to reproduce this race; the finding follows directly from the inspected control flow.

**Resolution verified:** [constructor:44–51](<../ai_async.py#L44-L51>) now rejects non-integer, boolean, nonpositive, and overly large limits before spawning. Construction-only probes independently confirmed pre-spawn rejection of `False`, `0`, `-1`, `512.0`, and `'512'`. The parent subsequently changed the upper bound to the minimum of the application ceiling and the native pointer-width `SIZE_T` maximum using `struct.calcsize('P')`; this reviewer re-read and confirmed that source correction. The earlier 32-bit upper-bound concern is resolved in source, but no 32-bit interpreter was executed.

## Native/API checks that passed source review

- `DWORD` is fixed-width 32-bit; `SIZE_T` and handles are pointer-sized; counters and time fields are 64-bit. Structures use native alignment rather than packed layout.
- `CreateJobObjectW`, `SetInformationJobObject`, `AssignProcessToJobObject`, `GetProcessId`, and `CloseHandle` have explicit argument/result prototypes. `use_last_error=True` preserves the failing API's Windows error code.
- The supplied object must be a running `Popen`, with a valid positive PID. Current application and parent PIDs are rejected. Native `GetProcessId(Popen._handle)` must match the supplied PID before a job is created. Null, pseudo and mismatched handles are rejected. No current-process pseudo-handle is used for assignment.
- `CreateJobObjectW(None, None)` creates an unnamed Job Object with a non-inheritable returned handle. The worker is not given a duplicate/inherited job handle. `KILL_ON_JOB_CLOSE` consequently supports killing assigned workers when the parent dies and Windows closes its last owning handle, subject to the standard Job Object handle/membership semantics.
- Flags are exactly `PROCESS_MEMORY | KILL_ON_JOB_CLOSE` (`0x2100`), with 512 MiB = 536,870,912 bytes by default. This limits per-process **committed memory**, not RSS, aggregate descendant memory, or total-system RAM.
- `PROCESS_MEMORY` causes allocations beyond the limit to fail; it is **not** an immediate-kill guarantee. Deadline/cancellation/termination remains independently necessary.
- Native set/assign failures close the newly created job and preserve the original native exception. A failed cleanup adds context. Normal assignment failure does not assign the calling application or close the `Popen`-owned process handle.
- Explicit `close()` refuses a live attached child, closes after confirmed exit, is idempotent, and retains handle ownership on a failed native close for retry. No garbage-collection destructor silently kills a live child.
- Non-Windows reports unsupported/unenforced explicitly. This review makes **no Linux native-cap claim**.
- A child can run briefly before attachment, and existing host Job Objects can reject nesting/assignment. Both are documented. The implementation is not a security sandbox or a pre-spawn zero-allocation guarantee.

## Independent execution evidence

Only no-worker construction/ABI/mock checks were run:

```text
python -B -m pytest tests/test_worker_limits.py -q
47 passed in 0.08s
```

A runtime ctypes layout/prototype probe on the current Windows x64 Python reported pointer size 8, basic-limit structure size 64, extended-limit structure size 144, and `ProcessMemoryLimit` offset 112. `kernel32` prototypes loaded successfully. The probe did **not** create a job, assign any process, or exercise allocation enforcement.

The 47 tests meaningfully cover the module's validation, structure/prototype definitions, flags and byte count, supplied-handle targeting, native error cleanup, metadata, non-Windows behavior, and guarded/idempotent close. They do not cover the adapter's failing cleanup route identified above, real Windows Job Object nesting/assignment, committed-memory exhaustion, or parent-death kill behavior.

## Parent-reported native follow-up (artifacts inspected, not independently executed)

After the serial match batch ended, the parent reported native Windows tests and supplied these artifacts. This reviewer read the JSON files but did not launch, reproduce, or directly observe the tests, and therefore keeps this evidence separate from independent execution above.

- [VH native single-thread resource sample](<../benchmarks/results/vh-resource-native-single-thread.json>): configured budget 5.0 seconds; observed wall time 5.3173 seconds; 497 native memory samples; peak RSS 38,993,920 bytes and peak committed memory 28,094,464 bytes. The result completed depth 4, returned a move with `proof_status=UNKNOWN`, and reported a successfully attached Windows per-process 512 MiB cap (`536,870,912` bytes), without watchdog timeout. This is one quiet 15×15 position, not a memory maximum over every game or a test that exceeds the 512 MiB default.
- [Controlled native memory-limit result](<../benchmarks/results/native-memory-limit-test.json>): disposable child limited to 64 MiB attempted a 192 MiB allocation; recorded `MemoryError_as_expected`, exit code 0, and `parent_survived=true`. This is useful operational evidence that committed-memory enforcement causes allocation failure rather than promising immediate termination. It does not prove every native allocator's behavior or parent-death cleanup.
- The parent reported that initial BLAS pool reservation had produced a peak commit of 533,024,768 bytes, near the 512 MiB cap. That earlier measurement was not independently inspected in an artifact here. The current [adapter worker environment:84–89](<../ai_async.py#L84-L89>) explicitly sets `OPENBLAS_NUM_THREADS`, `OMP_NUM_THREADS`, and `MKL_NUM_THREADS` to `1` before launching the worker. This reviewer confirmed that source mitigation; the single-thread sample above is the inspected post-change evidence.
- [Native parent-death result](<../benchmarks/results/native-parent-death-test.json>): records `controller_exit=0`, `child_signaled_after_parent_exit=true`, and `parent_survived=true`. This supports the parent's supervised `KILL_ON_JOB_CLOSE` operational check for the tested disposable tree. It does not by itself record all handle ownership, timing, or every ancestor-death variant. This reviewer read the artifact but did not execute the native test.
- The parent additionally reports 9 passing adapter-failure mock tests and a 467-test full suite. This reviewer did not rerun or independently verify those additional executions; they are not included in the independently executed 47-test count above.
- [Native adapter memory-failure result](<../benchmarks/results/native-adapter-memory-failure.json>): a disposable child under a 64 MiB enforced cap exited 77. The adapter returned `move=null` and `error="Worker ended without a result"`, without a watchdog timeout. The artifact separately records `resources_closed=true`, `temporary_directory_removed=true`, `no_retired_children=true`, and `parent_survived=true`. The parent identifies the trigger as actual over-allocation; the result artifact does not itself record the requested allocation size. This supports safe error propagation and post-failure cleanup for the tested disposable-child path. This reviewer read the artifact but did not run the test.
- `closed=false` in earlier result metadata is a snapshot taken before asynchronous reap, not proof of permanent leakage. The separate post-reap flags in the native adapter failure artifact above supply the previously missing final-cleanup evidence for that tested case.

The limited memory-enforcement, parent-death and native adapter failure-cleanup operational checks are **PASS on the supplied parent-reported, artifact-inspected evidence**, not independently reproduced native PASS results.

### Frozen executable boundary

The current [adapter constructor:74–87](<../ai_async.py#L74-L87>) selects 512 MiB by default for unfrozen Python and 1024 MiB when `sys.frozen` is true; explicit caller configuration remains available and native-width validated. The module-level `ProcessBudget` default remains 512 MiB. `worker_directory` is explicit caller configuration, used by [request-directory construction:117](<../ai_async.py#L117>); its default stays `None`, meaning the ordinary system temporary directory. No silent fallback after a denied TEMP access is introduced. This reviewer confirmed these source distinctions.

The parent initially reported startup failures under a 512 MiB frozen cap and pre-worker request-access problems even with 1 GiB. The parent identifies an environment-specific temporary-request permissions issue. No ACL modification was made and default-TEMP investigation was stopped in this environment. The source baseline `fa5f188` was parent-attributed; this reviewer did not use Git to verify it.

The parent subsequently reports a source rebuild and successful **explicit workspace request-root** component tests. This reviewer inspected the supplied artifacts and [probe source](<../benchmarks/frozen_adapter_probe.py>), but did not rebuild or execute them:

- [Frozen direct worker smoke](<../benchmarks/results/frozen-worker-smoke-explicit-root.json>): Easy, Normal, Hard and Very Hard all exited 0 and returned the center `(7,7)` on an empty board. Observed wall times ranged from approximately 0.299 to 0.971 seconds. Hard completed depth 2; Very Hard reported `UNKNOWN`, not a fabricated proof. These are worker-dispatch smoke checks, not playing-strength or full-GUI checks.
- [Frozen real-adapter results](<../benchmarks/results/frozen-adapter-explicit-root.json>): four nonempty-board move requests completed without errors or watchdog timeouts, each reporting an enforced 1024 MiB cap. Hard completed depth 2 and Very Hard depth 3; observed move-request wall times ranged from approximately 0.289 to 1.264 seconds. The inspected probe creates an actual `AsyncAI(worker_directory=root)`, routes its executable/frozen fields to the supplied exe, checks each returned move with `board.is_valid_move`, and asserts closed resources, removed directories and empty retired lists after close.
- The same real-adapter artifact records completed deferred validation for the center on an empty board with `adjudication=legal`, full validation context and `validation_complete=true`. Its cancellation check records approximately 0.000508 seconds for cancel, child exit, closed resources, removed directory and no retired children. The probe source asserts these postconditions.
- The parent additionally reports a final local suite of 495 passing tests in 9.12 seconds and a successful rerun of native adapter-failure cleanup. These execution counts were not independently rerun by this reviewer.

The bounded frozen **worker/adapter explicit-root component** is therefore **PASS on parent-reported, artifact/probe-inspected evidence**, not an independently executed test. This does not establish that the packaged GUI's default-TEMP path works: it uses explicit caller configuration rather than the GUI's normal default, and the probe does not exercise all GUI initialization/transitions. Default-TEMP packaged-GUI readiness remains **CHANGES REQUESTED**. The successful unfrozen 512 MiB sample also remains separate from the frozen 1024 MiB evidence.

## Remaining operational evidence

The parent should run disposable-child checks separately, never concurrently with performance/match measurements:

1. Verify the packaged GUI with its normal default-TEMP request path in an authorized, suitable environment. The explicit-root worker/adapter tests now establish bounded component behavior, but do not certify this GUI/release path. No further ACL repair or build investigation is requested by this review in the current environment.
2. Verify any remaining cancellation/watchdog cleanup scenarios, and report host-job assignment restrictions honestly; do not mark unenforced Windows fallback as PASS. The supplied native memory-failure artifact now establishes final resource/directory/retired-child cleanup for its tested case.

**Final conclusion after follow-up:** native cap source/API design **PASS** and corrected adapter lifecycle **PASS** within the stated source/mock scope. Limited Windows unfrozen cap/controlled-allocation, supervised parent-death, native adapter failure-cleanup and frozen explicit-root worker/adapter component checks are **PASS on parent-reported, artifact/probe-inspected evidence**, not independently reproduced. The packaged GUI's default-TEMP release path remains unapproved, so the overall operational gate remains **CHANGES REQUESTED** for that readiness check. No `REJECTED` architectural finding. The earlier 32-bit configuration bound concern is resolved in source. No Linux-cap, immediate-termination, or full packaged-GUI claim is made.
