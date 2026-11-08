# Independent review: deferred single-move adjudication

Date: 2026-11-08 (Asia/Tokyo). This is a bounded review of the deferred legality patch, not a new rules-engine or playing-strength certification. The reviewer did not implement or edit production code, edit tests, change Git state, run matches, or build an executable. The only authored deliverable is this review.

## Disposition

| Area | Status | Evidence boundary |
| --- | --- | --- |
| Exact-position legal-only Board handoff | **PASS** | Source inspection plus focused cache regressions. |
| Worker task/candidate/context binding | **PASS** | Source inspection and malformed/stale-result regressions. The protocol is an integrity boundary between application tasks, not protection against a malicious local process with access to the request directory. |
| Human/AI timeout → pending → resolved/UNKNOWN behavior | **PASS** | Focused headless integration tests; a real unfrozen single-candidate worker was exercised. |
| Cancellation/resource ownership | **PASS** (bounded scope) | Deferred tasks use the existing owned `AsyncAI` lifecycle and native-cap integration; no separate unowned child path was added. Existing native resource evidence is not rerun here. |
| Overall deferred-adjudication patch | **PASS** | No unresolved blocking finding in this narrow review. No claim about full-suite completion, frozen executable readiness, exhaustive Renju correctness, or Very Hard strength follows from this status. |

## Reviewed implementation

- [Board handoff:100–131](<../board.py#L100-L131>): `accept_checked_move` is legal-only, rejects bool/non-integer coordinates, player and move count, and delegates bounds, vacancy, nonnegative count, exact current grid bytes, ruleset and opening geometry checks. Opening policy is additionally matched. It does not directly place a stone. The helper is intentionally **not** an authentication API; only the authenticated Game pipeline may treat a detached verdict as trusted.
- [Board legality cache:260–288](<../board.py#L260-L288>): the installed value is an intrinsic black-foul result for the exact grid/size/target, not a cached general permission to move. Count/turn need not be in this cache key because player, vacancy and opening are rechecked by the complete move path. Direct legacy grid changes invalidate the cache through the byte key. A timed-out query raises before assigning a cache value.
- [Validation context and strict candidate shape:36–59](<../ai_async.py#L36-L59>): task kind/protocol/candidate/size/target/player/count/ruleset/opening are bound to a digest of the detached snapshot and last move. Each request also receives a fresh task token. Coordinates require exact Python integer types, not merely equality-compatible values.
- [Validation packet acceptance:184–217](<../ai_async.py#L184-L217>) and [result ingestion:219–258](<../ai_async.py#L219-L258>): only a matching token and validation task with `done is True`, a strict matching candidate, exact serialized context and a consistent complete verdict may be accepted. UNKNOWN requires `validation_complete is False` and no verdict. Legal/win/reason fields have strict types and compatible meanings. Analysis/overlay/progress packets cannot become a complete validation verdict.
- [Current-context recheck and pending move:261–309](<../ai_async.py#L261-L309>): changed position or semantic context cancels the task before applying its result. An AI move whose short UI validation times out is preserved separately as `validation_pending_move`; it is not classified as illegal and is not applied. Polling a validation task does not recursively validate again on the main thread.
- [Dedicated worker:61–94](<../ai_worker.py#L61-L94>): validation calls `Rules.classify_grid` independently of AI search/evaluation, with cancellation and a 5-second configurable request budget. It starts with UNKNOWN and publishes a complete legal/illegal result only after classification returns. Interruption remains UNKNOWN. Normal error packets fail the validation schema and become a safe unresolved outcome rather than permission to move.
- [Game pending handoff:724–832](<../game.py#L724-L832>): the exact human/AI candidate remains unplaced while the worker runs. Game independently rechecks its own pending token, kind, strict candidate, current context and verdict schema, then installs only a complete **legal** result via Board and applies the existing move path. Illegal/UNKNOWN verdicts do not seed the legal cache. UNKNOWN neither ends the game nor restarts search/validation every frame; retry is explicit with R, or the human can choose another move.
- [Lifecycle and cancellation:79–120](<../game.py#L79-L120>), [navigation/save handlers:576–637](<../game.py#L576-L637>) and [update ordering:1071–1080](<../game.py#L1071-L1080>): validation has an owned runner, is reaped each update and is cancelled on menu/Esc/reset/history/save. Both S and the Save button now use cancellation consistently. Queueing validation cancels competing search/analysis work. The ordinary `AsyncAI` wall watchdog, retirement/reap, close and memory-cap paths are reused rather than spawning a new unmanaged process.

## Initial findings resolved during review

1. **Boolean/int equality in candidate/context matching:** an initial response comparison used Python equality, under which `True == 1`. The implementation now validates the response candidate with the strict shape helper and compares canonical serialized context, rejecting bool substitutions in numeric metadata. The focused tests explicitly exercise both cases.
2. **Semantic metadata changed without changing grid bytes:** validation polling now recomputes the current context, including ruleset and opening policy, in addition to the ordinary position key. A semantic change cancels the response. The focused test changes opening metadata in flight.
3. **Save-action consistency:** the initial S handler cancelled work while the Save button only saved. Both now cancel before saving. This was a consistency concern, not an observed illegal placement.

No production edits were made by this reviewer to resolve these findings; they were reported to the parent/implementation agent and the updated source was re-read.

## Independently executed checks

After the parent explicitly authorized focused tests, this reviewer ran:

```text
python -B -m pytest -q tests/test_adjudication_cache.py tests/test_deferred_validation.py
24 passed in 2.52s
```

The tests cover legal-only Board caching, strict coordinate/count types, unchanged-board cache reuse, stale grid/rules/opening rejection, zero-budget AI validation preserving the exact hand, no recursive main-thread query during validate polling, malformed/contradictory/partial/wrong-kind/candidate/context packets, human and AI eventual legal application, illegal rejection, UNKNOWN with explicit retry, cancellation on reset/Esc/save/history, and a real unfrozen single-candidate worker with a 0.5-second classification budget. The real worker test closes the runner in `finally`; the live Board remains unmodified until explicit trusted handoff.

The Game transition tests deliberately force the UI budget to zero to exercise the deferred path deterministically. This is not evidence that a particular adversarial recursively complex position finishes within five seconds. Such a case may legitimately remain UNKNOWN, preserving the unplayed position and explicit retry behavior.

## Parent-reported integration follow-up

After the independent focused checks, the parent reported **493 integrated tests passing in 12.1 seconds**. This reviewer did not independently rerun or inspect the full-suite transcript, so that count is parent-reported evidence, separate from the 24 independently executed checks above.

The reviewer read the parent's [native Windows SDL smoke artifact](<../benchmarks/results/deferred-ui-smoke.json>): a forced zero-second fast-validation budget entered the detached path, then applied the legal black center move in **0.4484 seconds** over **23 frames**, with a recorded maximum frame duration of **45.86 ms** and the game-over state unchanged. The artifact names the `windows` display driver. This supports the tested normal-window unfrozen deferred path; it is one opening hand, not a worst-case recursive-rule latency bound, a frozen executable check or an independently reproduced native measurement. In particular, 45.86 ms does not establish an uninterrupted 60 FPS guarantee.

## Limits and remaining project gates

- A complete legal verdict is trusted only after task provenance and context validation. The snapshot digest is **not a cryptographic signature** against hostile local code reading/writing the worker directory. The application is not presented as a security sandbox.
- UNKNOWN can remain unresolved after the worker budget. That is an intentional safe state, not proof of illegal play or an automatic win/loss.
- No matches, performance benchmarks, native allocation stress checks, parent-death checks or frozen build were run in this review. This patch does not change the Hard/Very Hard search algorithms or independently establish their strength.
- The parent reports the post-patch integrated suite passing as described above; this reviewer has not independently reproduced it. Frozen readiness and any prior evidence/strength limitations retain their own statuses; this narrow **PASS** does not override them.

**Conclusion:** deferred single-candidate adjudication **PASS** within the source/focused-test scope above. No `REJECTED` architectural issue or unresolved `CHANGES REQUESTED` finding in this patch was identified.
