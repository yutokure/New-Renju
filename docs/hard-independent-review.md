# Phase A independent review — Hard stability and asynchronous UI

## Verdict

**PASS — bounded Phase A source/correctness review after parent fixes.** No unresolved blocking source defect remains from the findings below. This is **not** a release-wide PASS, a proof of full Renju rules, a playing-strength non-regression certification, or a frozen-executable certification. The separate product acceptance gate can remain **CHANGES REQUESTED** until its required strength/executable evidence exists.

Reviewed independently against `main` in `yutokure/New-Renju`, on 2026-11-08. The reviewer did not implement or edit production sources, tests, or Git state. Production/test corrections during this review were made by the parent and then reread/revalidated here. This review document is the reviewer's only repository write. No performance benchmark was run by the reviewer.

Scope: [ai.py](<../ai.py>), [board.py](<../board.py>), [game.py](<../game.py>), [main.py](<../main.py>), the new [async adapter](<../ai_async.py>) and [worker](<../ai_worker.py>), and the scoped [tests](<../tests/test_hard_stability.py>). Untracked new modules/tests were read explicitly; they do not appear in a normal tracked-only `git diff main`.

## Findings, reproductions, and disposition

Line references below identify the final reviewed repair locations, not immutable commit anchors. The working tree was changing under the parent during review.

### R1 — HIGH — Nonterminal heuristics could rank below an actual terminal loss — RESOLVED

- Relevant code: [terminal scores, ai.py:330–344](<../ai.py#L330-L344>), [heuristic accumulation and clamp, ai.py:415–432](<../ai.py#L415-L432>).
- Originally, six independent opponent open fours each contributed `-18,000,000` including the extra defensive penalty. Their sum was `-108,000,000`, below the terminal loss value `-100,000,000 - depth`. Maximizing/minimizing decisions could therefore prefer an actual loss over a nonterminal leaf. Correct terminal **signs** alone did not establish correct terminal **hierarchy**.
- Reproduction, using a deliberately adversarial static position rather than claiming it is a typical legal game trajectory:

```python
from ai import AIHard
from board import Board, BLACK, WHITE
b = Board(19, 5)
for r in (1, 4, 7, 10, 13, 16):
    b.grid[r, 7:11] = WHITE
b.last_move = (16, 10)
hard = AIHard(BLACK)
assert not b.check_win(WHITE)[0]
print(hard._evaluate_board(b))
```

- Before repair: `-108000000`. After repair: `-99999999`. Nonterminal accumulated estimates are now strictly inside the configured terminal interval, while detected winning lines retain terminal scores.
- Revalidated directly and through [the hierarchy regression, test_hard_additional.py:17–21](<../tests/test_hard_additional.py#L17-L21>).

### R2 — HIGH — No-op Next during AI thinking permanently stalled the game — RESOLVED

- Relevant code: [shared cancellation, game.py:93–101](<../game.py#L93-L101>), [Next navigation, game.py:590–601](<../game.py#L590-L601>), [worker-start telop gate, game.py:959–973](<../game.py#L959-L973>).
- Reproduction: start AI-vs-Human; clear the initial telop; call `game.update()` to start the AI; click `Next >` while already at the latest history index. Before repair this canceled the worker and cleared `ai_thinking`, but left the indefinite thinking telop visible. There was no history transition. Subsequent updates could not restart AI because `telop_is_active` remained true forever.
- Observed pre-repair state after click/update: `ai_thinking=False`, runner not busy, telop `active=True`, `duration=None`, `state='visible'`, history mode false.
- Repair: shared cancellation hides the thinking telop before clearing the thinking flag. Its fade-out can finish, permitting a new search; reset construction is protected with `getattr`.
- Revalidated by source inspection and [the no-op Next regression, test_async_ui.py:142–156](<../tests/test_async_ui.py#L142-L156>). This test establishes that the indefinite visible state is removed; it is not a long-duration manual GUI exercise.

### R3 — MEDIUM — Malformed but valid JSON worker packets could crash the main loop — RESOLVED

- Relevant code: [packet validation, ai_async.py:88–116](<../ai_async.py#L88-L116>), [coordinate revalidation, ai_async.py:136–143](<../ai_async.py#L136-L143>), [analysis coordinate bounds, game.py:1162–1173](<../game.py#L1162-L1173>).
- Original reproduction: create an adapter task with a matching position and an exited process; put JSON `[]` in its result file; call `poll`. `_read_result` called `.get` on the decoded list and raised uncaught `AttributeError`. A legal/illegal coordinate test did not cover this failure. Malformed analysis score rows could also fail tuple unpacking in the game.
- First repair added mapping/type/finite checks. An additional review probe with `{'token': token, 'done': True, 'elapsed': 10**400}` still raised `OverflowError` in `math.isfinite`. This is a valid, small JSON packet despite being outside the worker's meaningful numeric domain.
- Final repair validates packet root/done/depth/numeric/analysis-row shapes, catches `OverflowError`, and bounds analysis coordinates before displaying them. Invalid coordinates are still independently checked against the live board before a move is applied.
- Revalidated directly for list/null roots, null scores, and boolean move coordinates. The final [malformed-packet parameterization, test_async_ui.py:100–116](<../tests/test_async_ui.py#L100-L116>) includes the oversized integer and passes. Invalid packets cannot authorize a move; at exit/watchdog they become a controlled no-result error, or the prior verified progress result remains usable.
- This is robustness against broken internal results, not an assertion that a hostile local process cannot modify this application's temporary files.

### R4 — MEDIUM — Research worker startup failure escaped UI exception handling — RESOLVED

- Relevant code: [research startup, game.py:1139–1160](<../game.py#L1139-L1160>).
- Reproduction in SDL dummy mode:

```python
from unittest.mock import patch
# With an initialized human-vs-human Game:
game.research_mode_enabled = True
with patch.object(game.analysis_runner, 'start',
                  side_effect=OSError('spawn denied')):
    game._evaluate_empty_cells()
```

- Before repair: uncaught `OSError`, propagating from event/update handling and terminating the main loop. Move-worker startup already handled this failure class, but research startup did not.
- Repair catches `OSError`/`ValueError`, logs the failure, clears the in-progress flag, and records the failed position key so update does not spawn/retry every frame.
- Revalidated directly: calling twice under the injected exception called `start` exactly once and left evaluation not in progress. [The parent regression, test_async_ui.py:200–217](<../tests/test_async_ui.py#L200-L217>) also passes. The traceback logged by this deliberately injected probe is expected, not a failing command or real worker crash.

## Requested adversarial checks and invariants

### Algorithm and search correctness

- **Required architecture retained:** [AIHard](<../ai.py#L109-L159>) still uses iterative deepening, explicit maximizing/minimizing minimax, alpha-beta windows, incremental Zobrist XOR, a bounded TT, radius-one adjacent candidate generation, and weighted line evaluation. Factory/constructor defaults remain maximum depth **2** and **1.5 seconds**. Neither the search nor worker imports a Very Hard engine or tactical proof solver. The adapter's unused difficulty-string budget branch is not an engine dependency.
- **Signs:** terminal values are based on `self.player`/`self.opponent`, not whose turn/maximizing flag it is. Both colors and maximizing flags are covered. R1 separately addressed hierarchy.
- **Hypothetical restoration:** [Board.temporary_move](<../board.py#L42-L62>) restores the prior cell, exact prior `last_move` object, and forbidden marker in `finally`. All reviewed AI hypothetical placements use it. Nested/occupied scopes, injected exceptions, recursive deadlines, and cancellation are tested. Hash changes are local values; no mutable incremental board hash must be rolled back.
- **Deadline/completed depth:** monotonic checks occur inside recursion, ordering, tactics, TT storage boundaries, and per evaluated line. Only fully finished root iterations replace the best move. The verified fallback stage intentionally runs before cancellation/deadline unwind; it is finite but not a hard real-time guarantee. External worker wall caps provide the separate containment layer.
- **Fallback row-major quality:** the initial row-major-first implementation was changed by the parent before final review. [ai.py:212–224](<../ai.py#L212-L224>) now chooses deterministically by distance to the last move, then center distance and coordinates. The zero-budget local fallback regression passes. The worker initially publishes a legal center-biased fallback and then accepts Hard progress; neither promises tactical quality before tactical prechecks complete.
- **TT context:** [the key](<../ai.py#L311-L317>) includes root perspective, side, size, winning length, count, normalized last move, and score configuration as well as board hash. Bound flags use the original window; unfinished subtrees are not stored. Same-depth-only reuse avoids horizon/terminal-distance mismatch. Capacity is enforced. This is not a claim that the TT materially accelerates the shallow default depth.
- **Loaded `last_move` list hashability:** the parent normalized it to a tuple in the TT key. Direct hashing of a key from JSON-style `[row, col]` passed; the recursive regression passes. Live loaded lists remain supported by board checks, adapter keys, and worker reconstruction.
- An additional short independent differential probe used five deterministic small boards and both root colors: depth-two TT-enabled scores equaled TT-disabled scores in **10 checks**, and repeated exact TT reads agreed. This samples correctness; it is not exhaustive equivalence proof.

### Rules, legal moves, and compatibility

- [Legality queries](<../board.py#L64-L98>) are nonmutating. Tactical opponent probes use opponent legality at the hypothetical next count, and a chosen defensive move must be legal for the moving side. Forbidden black overlines do not become fictitious white blocking obligations.
- [Win detection](<../board.py#L100-L126>) and [forbidden queries](<../board.py#L213-L233>) implement the declared Phase A split: exact black five, white at least five; exact-five priority across directions; custom 3/4/6/7 at least N for both colors without black forbidden restrictions. Existing simplified opening remains. This is not full official recursive double-three/double-four adjudication.
- Custom-length tests cover immediate wins and evaluation. Additional independent immediate-**block** probes covered both colors, Normal and Hard, all lengths 3–7: **20 checks passed**, with grid and original list-valued last-move identity restored.
- Easy still uniformly chooses among row-major legal cells. Normal retains its priority ordering; legality/restoration/custom-N fixes intentionally change previously incorrect moves. Tests do not prove identical random gameplay sequences across isolated processes or a no-strength-regression claim.
- Old JSON keys and stone-history layout remain supported. Loaded/reconstructed histories can intentionally bypass current legality; legacy custom/overline winner reevaluation can change under the corrected rule split. Malformed-history sanitation beyond this pre-existing behavior was not redesigned.
- Independently exercised loaded list history `[[7,7],[6,7],[7,8]]`, Prev then Next back to live, board drawing, and the save serialization path with an in-memory file capture. Output retained the existing `settings`/`move_history` schema and five settings keys; no save file was written by that probe.

### UI cancellation, rendering, and workers

- Worker processes own snapshots; result tokens and exact position/context keys reject stale results. Final move legality is rechecked on the main thread. Menu/Esc/reset/history cancel work. The app exit path closes the game and the frozen dispatch branch exists in [main.py:498–509](<../main.py#L498-L509>).
- **Disabled research cancellation:** direct checkbox-event probe confirmed runner no longer busy, research false, evaluation false, cache empty, key null; closing the game confirmed the spawned process had exited. No stale analysis values were applied.
- **Draw/history responsiveness:** no search remains inline in update/draw. Position cache invalidation is keyed by board/player/count. Independent repeated-draw probe on a loaded three-move board showed threat/legality counts unchanged after a second forced redraw: `(2, 222)` then `(2, 222)`. Navigation invalidates the appropriate context. This checks cache behavior, not a frame-time guarantee on all positions.
- Startup/error/no-result paths now avoid silent infinite replacement search. Research startup has R4 containment. [Thinking telemetry](<../game.py#L1083-L1088>) now formats adapter elapsed/completed depth; those are worker progress snapshots, not continuously updated wall time or a claim that an unfinished iteration completed.

## Validation performed by the independent reviewer

Final scoped command, after all listed repairs:

```text
python -B -m pytest -q -p no:cacheprovider tests/test_hard_baseline.py tests/test_hard_stability.py tests/test_hard_additional.py tests/test_async_ui.py
```

**93 passed in 2.40s**, no xfails. Earlier scoped runs were 91 and 93 passes while the parent was adding repairs; the final count is the one above. Python bytecode writes and pytest's cache provider were disabled. These results accompany source review and the adversarial probes; they are not the reason correctness is assumed.

Additional probes were short functional tests only: terminal hierarchy, fallback/list metadata, malformed protocol packets, research disable/start failure, no-op Next cancellation, custom tactical legality/restoration, TT-enabled/disabled sampled equivalence, draw cache, history/save serialization. All real worker processes started by these checks were closed. No background job was left running.

## Performance evidence reviewed, not rerun

Read the existing [before JSON](<../benchmarks/results/hard-before.json>), [after JSON](<../benchmarks/results/hard-after.json>), and [serial benchmark harness](<../benchmarks/hard_benchmark.py>). Both JSONs identify Python 3.12.3 / NumPy 1.26.3, the same Windows/CPU metadata, seed, depth two, 1.5-second limit, six cases, three repeats. The harness profiles the core directly, not GUI/subprocess startup. Final recorded medians:

| Case | Before ms | After ms |
| --- | ---: | ---: |
| Opening | 17.47 | 2.53 |
| White immediate win | 1.11 | 1.76 |
| Black immediate win | 3.98 | 3.61 |
| Immediate block | 1.81 | 6.11 |
| Quiet opening | 605.53 | 58.52 |
| Midgame | 888.43 | 85.47 |

These support improvement on the two sampled search-heavy fixtures and show tactical overhead increases rather than concealing them. They do **not** establish universal latency improvement, playing strength, startup-inclusive UI latency, or unchanged results on unlabelled positions. Before-data completed depth is null; no before depth equivalence is inferred. The binary profiler artifacts were not independently reanalyzed. Final repairs landed while evidence was being regenerated by the parent; exact source-to-artifact identity is not cryptographically captured in the JSON.

## Separate untested/release concerns

### Real GUI — independently untested

The reviewer used SDL dummy events/rendering, not a human-operated real window. The parent's existing [real SDL smoke JSON](<../benchmarks/results/hard-ui-smoke.json>) and [smoke source](<../benchmarks/ui_smoke.py>) were read: they report Windows driver, eight frames, maximum frame 18.03 ms, Esc close 1.25 ms, worker stopped. That is useful separate evidence, but not an independent replay here and not a full-session manual visual/interactivity certification. Long-session AI-vs-AI, loaded terminal games, rapid repeated navigation/toggles, full window-close paths, fonts/layout, and transient disk-sharing behavior remain manual/release checks. Nothing in this review labels them independently tested.

### Frozen executable — untested

No executable was built or launched. The `sys.frozen` self-launch command and dispatch are plausible by source inspection, but packaging must include the new worker/adapter and dependencies/assets. Real distributed onefile/onedir startup, repeated self-launch behavior, cancellation, temp cleanup, save paths/permissions, and absence of orphan processes require the actual packaged artifact. Source/subprocess pytest success does not clear this gate.

### Playing strength and full rules — not certified

No strength games or performance benchmark were authorized/run by this reviewer. Tactical fixtures, sampled minimax comparisons, and preserved architecture do not prove no playing-strength regression. Full official Renju legality/proof-search work is explicitly outside Phase A; the contiguous-only checker and greedy static evaluator remain heuristics. The parent owns these separate acceptance decisions.

## Follow-up: final-result read race, commit `9b20bc6`

**Verdict: PASS / safe for this narrow patch.** Independently inspected the patch and regression on 2026-11-08 in the separate Hard review worktree. Only this document was modified by the reviewer. No broad test suite, benchmark, strength match, real GUI, or executable run was performed for this follow-up.

### R5 — MEDIUM — Progress-read throttle could discard an available final worker result — RESOLVED

- Relevant changes: [forced-result read, ai_async.py:88–95](<../ai_async.py#L88-L95>), [exit/watchdog reread before retirement, ai_async.py:126–146](<../ai_async.py#L126-L146>), and [regression, test_async_ui.py:86–99](<../tests/test_async_ui.py#L86-L99>).
- Reproduction: retain an earlier incomplete progress packet, set `task.read_after` into the future, write a newer valid `done=True` result, and observe worker exit or watchdog expiry before the next scheduled progress read. Previously, `poll` could skip the file read and immediately retire the task using stale progress or report no result. A successfully completed higher-quality move could be lost solely because of polling timing.
- The repair retains the 30 ms throttle for normal progress reads, but bypasses it when process exit or expiry makes the poll final. It recomputes `done` after that forced read, before selecting the result or setting `timed_out`. Token/schema validation and live-move legality checks remain in place. An unreadable/invalid last packet does not erase a previously valid progress result. At watchdog expiry, a packet written only after the final read can still be excluded; that is a legitimate cutoff, not a promise to await future worker writes.
- Independently ran **two lightweight deterministic probes**, with temporary JSON files and fake process/board objects, without launching an AI subprocess or importing NumPy: (1) exited process with budget still remaining; (2) watchdog expired with process still running. Both started with a stale legal incomplete move and a future `read_after`, then returned the newer final legal move, `timed_out=False`, and cleared the active task. **Both passed.**
- **LOW, nonblocking coverage note:** the committed regression sets `budget=0` and `startup_grace=0`, so it deterministically exercises the **watchdog** trigger; its name alone does not prove the independent exit-only path. The reviewer probe separately covered exit-only. A future parameterized regression using a fake process/clock could preserve both paths without process-startup timing. This is not a remaining source blocker.
- The parent's reported local 21-test result was not rerun by this follow-up reviewer; it is distinct from the two independent probes above. The earlier 93-test result in this document is historical, not a claim that the full suite was rerun at this commit.

### Owner's local-only validation policy

The owner explicitly requested **no CI**, and the parent reports CI configuration was removed from both branches/PRs. CI support is **not** a deliverable or recommendation of this review. Validation remains local and scoped; no CI file was created, restored, or modified here. Existing real-GUI, packaged-executable, full-rule, and playing-strength evidence limits remain unchanged by this polling fix.
