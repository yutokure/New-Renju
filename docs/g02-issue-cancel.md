# G02 issue draft: cancelled worker can remain live indefinitely

## Scope and baseline

- Audited main revision: `37a027eda2f6b9e33a9ebbde4e6a40884d00049e`.
- Area: UI/adapter worker lifecycle, not AI search, rule adjudication, engine tuning, worker temporary-directory policy, or frozen packaging.
- Severity: P2 robustness/resource-lifecycle issue. Trigger requires `terminate()` to fail or leave a still-running child; the ordinary Windows termination path usually succeeds.

## Root cause and impact

[`AsyncAI._retire`](../ai_async.py) signals cancellation, attempts `process.terminate()`, swallows `OSError`, and moves the task out of the active slot into `retired`. At the audited baseline, `reap()` only retained live retired tasks; it never escalated to `kill()` or retried termination. A cancelled or watchdog-expired child could therefore continue searching indefinitely while later `start()` calls launched replacement workers. Position/token guards prevent applying the stale result, but do not prevent the stale computation/resource leak. Menu/reset/save/history cancellation must stop the work as well as discard the result.

The native process-budget attach-failure path already had a kill fallback; normal cancellation and timeout retirement did not. The main loop repeatedly calls `reap()`, so a nonblocking escalation there closes the lifecycle hole without changing any engine.

## Minimal reproduction (memory-only mocks)

1. Install an `_Task` whose fake process always reports `poll() is None`, and whose `terminate()` raises `OSError`.
2. Stub `Path.touch` so no cancellation marker is written.
3. Call `cancel()`, then `reap()` repeatedly.
4. Baseline observed: active task absent, one live retired task, one terminate call, zero kill calls after five reaps. No subprocess or file was used.

## Minimal fix

In `reap()`, attempt `kill()` for each still-live retired task before checking exit and cleanup. Do not wait for a live child. Swallow transient `OSError` only while retaining the exact task/resources for the next reap. Continue closing budget handles and deleting the owned temporary directory only once `poll()` confirms child exit. Keep final `close()` safety and the attach-failure path intact.

## Regression coverage

[`tests/test_adapter_failures.py`](../tests/test_adapter_failures.py) adds pure-mock cases for:

- `terminate()` raises: cancellation escalates, exited child is reaped, resources close.
- `terminate()` returns but process remains live: cancellation still escalates.
- `kill()` transiently fails: task and resources remain owned, next `reap()` retries and cleans up.
- No blocking `wait()` on a live fake process; only exited-child `wait(timeout=0)` is allowed.

The existing tests remain responsible for native process-budget attach failure. This fix does not alter move selection, validation packets, UI input semantics, temporary-root selection, or packaging.
