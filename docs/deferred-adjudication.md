# Exact-candidate deferred adjudication

## Why

The UI keeps a 12 ms budget for one synchronous `Board.is_valid_move` query. A complicated recursive real-three question can exceed it. `RuleValidationTimeout` means **UNKNOWN**, not forbidden and not an instruction to abandon a potentially legal move.

The old UI refused that hand permanently; the new path keeps its exact coordinate pending and resolves it in a detached rule worker. This changes execution management only: no search/evaluation algorithm or difficulty setting is changed.

## State machine

1. Human candidate (or final AI candidate) gets cheap shape/range/empty/simplified-opening checks and the short UI rule query.
2. On UI timeout, no stone/history/turn/game-over state changes. `Game` cancels AI search and research/overlay work and starts one dedicated `validation_runner`, `kind='validate'`, for that **single** candidate. Additional board clicks are disabled while pending; menu/Esc/history/reset/save cancel it.
3. The worker reconstructs the exact snapshot, checks request provenance, and runs `Rules.classify_grid` with its ordinary recursive rule logic, cancellation callback and a 5 second budget. This is full rule classification, not a four-only or visual-pattern approximation. No AI engine is instantiated for validation.
4. A complete result is `legal` or `illegal`, plus its `legal/win/reason` diagnostic. Cancellation, budget exhaustion, process/memory failure or absent/malformed result is `unknown`. No UNKNOWN result is cached or applied.
5. A legal response is transferred through `Board.accept_checked_move`; the normal placement path still rechecks the current cheap opening/empty conditions, but recursive black-five legality is now an exact-position cached verdict. The UI does **not** rerun the expensive recursive rule query after the worker completes.
6. An illegal hand stays unplayed and shows feedback. An AI returning an illegal hand stops with a visible error rather than retrying forever.
7. UNKNOWN stays unplayed, displays **Rule check UNKNOWN - R to retry**, and permits an explicit `R` retry. There is no automatic repeat-validation/search loop. A human can instead select a different hand. No UNKNOWN state is converted to a foul, loss, draw or game over.

The nominal upper wall time is 5 seconds rule work plus the adapter's existing 2 second startup grace, observed at the next UI poll. The existing process memory cap and hard termination/reaping protections remain in effect. While pending, animation/event processing stays in the Pygame loop; heavy AI, research and full-board legality overlay requests are not run concurrently.

## Binding and validation

`AsyncAI` stores the request kind, exact candidate and validation context in its private task, in addition to its existing unique token and exact `position_key` (grid bytes, size, target, last move, side and move count).

The context contains protocol `renju-rules-classify-v1`, request kind, primitive-int candidate, size/target/side/count, ruleset/opening policy and a SHA-256 digest over canonical JSON of those fields plus the complete snapshot. The digest is a context/integrity check, **not** a cryptographic signature against a hostile process with local filesystem access.

Before accepting a reply, the adapter requires:

- matching task token and `kind='validate'` (a move/analysis packet cannot adjudicate a hand);
- exact primitive-int coordinates (booleans are rejected even though Python `True == 1`);
- canonical typed context equality and a context freshly recomputed from the current board;
- `done=True`, explicit completeness, and consistent legal/win/reason diagnostics;
- legal state only with a complete legal verdict; illegal state only with a nonwinning complete illegal verdict; UNKNOWN only with no verdict and `validation_complete=False`.

Game repeats the schema and its own pending token/candidate/context binding before handoff. `Board.accept_checked_move` independently checks exact `(size, target, grid bytes)`, current rule/opening metadata, coordinate/player/count types, empty cell and simplified opening. Only the legal verdict for this exact black-five cell is seeded; no stone is placed by the cache helper. Stale/malformed/partial messages never seed the cache or alter the board.

Ordinary AI move polling also preserves timeout candidates in `validation_pending_move` with `validation_required=True`; the actionable `move` field is cleared until adjudication completes. This prevents an AI UI-budget timeout from becoming an error/stall or applying an unchecked move.

## Temporary files

`AsyncAI(worker_directory=...)` permits an **explicit caller-selected existing temporary root** for portable/managed execution. The default is unchanged (`None`: platform TEMP). A denied path is not silently worked around. This parameter does not weaken token/snapshot validation or process budgets.

## Focused verification

Executed locally after this change:

- `python -B -m pytest -q tests/test_deferred_validation.py`: **23 passed** (2.40 s), including wrong-token rejection and Game's independent rejection of a bound legal packet missing its verdict.
- Existing small compatibility suites (`test_async_ui`, `test_adapter_failures`, `test_integration_vh`, `test_adjudication_cache`): **51 passed** (6.45 s).

The focused tests cover human and AI delayed legal application, zero-budget main-thread acceptance through the completed cache, illegal/unknown no-application, manual retry without automatic loops, cancel/reset/save/history, stale grid/semantic metadata, bool-shaped or contradictory packets, and a real subprocess validation of the opening center. These are not a full-project PASS, a new engine strength claim, or a frozen executable validation. Broader suites/native GUI/frozen verification are owned by the parent integration run.
