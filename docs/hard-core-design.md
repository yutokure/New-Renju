# Phase A: conservative Hard core

## Scope and preserved algorithm

The Hard engine in [ai.py](<../ai.py>) remains a lightweight **iterative-deepening minimax search with alpha-beta pruning, Zobrist hashing, a transposition table (TT), radius-one adjacent candidates, proximity ordering, and weighted line-pattern static evaluation**. Constructor and factory defaults are depth **2** and **1.5 seconds**. Phase A does not introduce VCF/VCT, threat-space proof search, a new board representation, or a dependency on a future Very Hard engine.

The pre-existing immediate-win/block policy is retained, including recursive narrowing to one immediate winning or blocking candidate. This is a heuristic engine, not a proof that every forced line is solved. Root tactical checks run over empty cells; recursive search still uses adjacent candidates. Easy retains uniform random selection among row-major legal cells. Normal retains its five-in-a-row win/block/open-four/block-open-four/closed-four/open-three/block-open-three/random priorities. Transaction restoration, opponent legality, and custom-win-length correctness fixes intentionally affect previously incorrect choices.

## Public search contract

```python
hard = AIHard(player, depth=2, time_limit_sec=1.5,
              seed=0, tt_capacity=50000)
move = hard.find_move(board, move_count,
                      cancel_event=None, progress_callback=None)
```

- `cancel_event`, when supplied, provides `is_set()`. Instance attributes `cancel_event` and `progress_callback` are also supported as defaults. Explicit non-`None` arguments take precedence.
- `progress_callback` receives **one dictionary** containing `move`, `completed_depth`, `depth` (an alias), `score`, `nodes`, `evaluations`, `elapsed`, and `phase`. `phase` is `fallback`, `tactical`, or `search`. `score` can be `None`. Callback exceptions are logged and do not abort search.
- Public `completed_depth`, `nodes`, and `evaluations` reset on every search. A tactical return can have completed depth zero: it is a directly checked immediate result, not a completed minimax iteration.
- A legal deterministic fallback near the last move (then the center, with coordinate tie breaks) is verified and published **before** expensive prechecks, hash construction, or any deadline/cancel unwind. A zero budget or an already-set cancellation event returns that fallback. No legal move returns `None`.
- The budget uses monotonic `time.perf_counter()`, including root prechecks and evaluation. Checks occur at recursive entry, candidate generation, tactical probes, recursion loops, TT-store boundaries, and each evaluated line. A cooperative internal exception unwinds to `find_move`.
- A partially searched depth is never promoted. The result is the last fully completed root iteration, a verified tactical choice, or the early legal fallback. An unfinished subtree is never stored as a TT result.
- The first-legal scan is deliberately finite and uninterruptible until it establishes a safe fallback (or proves there is no legal move). Therefore the time budget is cooperative, not a hard real-time guarantee. The process adapter supplies the independent worker watchdog described in [the asynchronous design](<hard-async-design.md>).
- Ordinary programming errors propagate, but all hypothetical board scopes unwind first. A single AI instance and its board should not be used concurrently; the adapter owns its isolated snapshot.

## Transactional board safety

[board.py](<../board.py>) supplies `Board.temporary_move(row, col, player)`, a reusable context manager. It temporarily sets both the cell and `last_move`, then restores the prior cell, `last_move`, and `forbidden_checked_pos` in `finally`. It supports nested scopes and occupied-cell replacement for analysis; out-of-bounds coordinates raise `IndexError`. It is a placement mechanism, **not** a legality check.

All AI hypothetical win/pattern probes and recursive moves use this scope. Hash changes are local values rather than mutable make/unmake state, so cancellation cannot leave `current_hash` half-updated. Terminal values are always rooted in `self.player`: root wins are positive, root losses negative, regardless of the maximizing/minimizing flag.

`is_valid_move`, `is_forbidden`, and `_is_forbidden` are nonmutating queries. A forbidden query on an occupied or out-of-bounds cell returns `False`; complete legality is the responsibility of `is_valid_move`, which rejects occupied/out-of-bounds cells. Only a real `place_stone` attempt updates the visual forbidden marker. Board copies now preserve that marker as well as grid/last-move state.

Opponent threats are validated for the **opponent**, using the hypothetical next move count, independently of whether the defender can occupy the cell. A block is selected only if it is also legal for the defender. In particular, a forbidden black overline cannot masquerade as a white defensive obligation.

## Determinism and bounded caches

Zobrist values use a local NumPy generator seeded by `seed` (default zero), without consuming global NumPy or Python random streams. Boards larger than the initial table grow the table deterministically. Candidate coordinates are deduplicated before legality checks, then ordered by the original proximity heuristic with a stable coordinate tie break. Search choices and counters are reproducible for the same position, settings, and completed search horizon. Wall-clock cancellation can naturally change which depth finishes; reproducibility is not a promise that different CPU loads produce the same deadline-limited move.

The TT is cleared at each root search and bounded by `tt_capacity` (default 50,000; zero disables stores). Its key includes board Zobrist hash, root player, side to move, board size, win length, move count, `last_move`, and score configuration. Stored flags are exact/lower bound/upper bound relative to the original alpha-beta window. Entries are reused only at the same remaining depth because both horizon evaluation and terminal distance bonuses depend on depth. Deeper entries are protected from replacement by shallower entries. Capacity eviction is insertion/update ordered. Standard 64-bit Zobrist collision risk remains; Phase A does not replace hashing with a full position encoding.

Repeated line scoring uses a process-wide `lru_cache(maxsize=65536)` with immutable keys containing the line, root player, win length, board size, and score settings. Pattern construction has a separate `lru_cache(maxsize=128)`. Neither cache retains board or AI instances. Rows, columns, and both diagonal families are yielded in the original traversal order instead of materializing a full list first.

For five-in-a-row, static evaluation keeps the original greedy length-first pattern scan, most-significant absolute score per line, edge closed-pattern handling, asymmetric defensive weights, and extra opponent open-three/open-four penalties. Black overlines are no longer terminal wins. Nonterminal summed scores are clamped strictly between the terminal loss and win values, so a pessimistic estimate cannot rank worse than an actual loss. This is a static heuristic, not legal-threat proof or official recursive Renju analysis. For custom N, the same pattern tiers shift from four/three to N−1/N−2 stones, and broken near-threat patterns are generalized without changing five's pattern order.

## Explicit rule split: 3–7 in a row

| Win length | Winning line | Forbidden moves | Opening |
| --- | --- | --- | --- |
| 5 | Black: exact five; White: at least five | Existing simplified contiguous black overline / double-three / double-four approximation | Existing simplified opening |
| 3, 4, 6, 7 | Both colors: at least N | None: custom Gomoku, not generalized Renju | Existing simplified opening |

For five, every direction is collected before applying **exact-five priority**. If one placement makes an exact black five and an overline in another direction, the exact five wins and the move is legal. Without exact five, a black overline is forbidden and is not a winning line. White overlines win. The simple contiguous-only double-three/double-four checker is deliberately retained; broken formations, legal continuation/real-three recursion, official opening/swap procedures, and full official rule conformance belong to Phase B. See [rules research](<rules-research.md>) for the independent rule analysis.

The existing opening remains unchanged: on odd boards of size at least five, move 0 is center; move 1 is immediately above center or diagonally up-right; move 2 is within two rows/columns of center. Other move counts are unrestricted by this opening. Even/smaller boards skip it as before. This simplified policy is not advertised as a complete official tournament opening protocol.

Custom 3–7 support is intentionally a **bug-fix compatibility change**: previous non-five games mixed a fixed five-pattern evaluator with N-dependent black overline restrictions and fixed three/four forbidden checks. Those positions can now be legal or winning where the old implementation disagreed. Saved stone layouts remain readable, but reevaluating an old custom position, black overline position, or exact-five/overline crossing can change legality/winner and the AI's next choice. Easy/Normal changes outside this correctness scope are not intended. Existing optional board threat-line hints remain five-specific; they are visual heuristics and are not used to establish custom-game legality or Hard search correctness.

## Regression coverage and measurement boundary

[Baseline tests](<../tests/test_hard_baseline.py>) retain the original legal/tactical cases, factory defaults, and major line scores. The three formerly strict expected failures (two root-player terminal cases and the recursive `last_move` probe) now pass normally.

[Stability tests](<../tests/test_hard_stability.py>) cover root-relative terminal signs; nested/occupied temporary moves; restoration on exceptions, timeouts, and recursive cancellation; nonmutating forbidden queries; exact-five priority in both direction orders; black/white overlines; custom 3–7 rules/evaluation/Normal tactics; preserved opening; Easy/Normal smoke; legal early fallback and full board; completed-depth-only publication; candidate deduplication; deterministic seeded hashes/ties without global RNG use; TT key isolation/capacity/depth reuse; bounded line cache context; and illegal-opponent-threat rejection.

Core validation command (not a benchmark):

```text
python -m pytest tests/test_hard_baseline.py tests/test_hard_stability.py -q
```

Result at handoff: **70 passed**, no xfails. No playing-strength or performance benchmark was run by the core implementation agent. The parent runs the original/updated benchmark serially with identical profiling settings; benchmark speed or playing strength is not claimed from these regression tests.
