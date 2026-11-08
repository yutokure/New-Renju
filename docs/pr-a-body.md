## Summary

Conservative Hard repairs, retaining minimax + alpha-beta + iterative deepening + Zobrist/TT + weighted line patterns, depth 2 / 1.5s. No Very Hard engine dependency.

- Root-relative terminal values; safe hypothetical make/unmake including last_move and visual marker
- Recursive monotonic deadline/cancellation, legal local fallback, completed-iteration publication
- Deterministic ordering/hash, bounded pattern/line caches and root-scoped TT
- Independent opponent legality; explicit custom connect-3/4/6/7 semantics
- Detached subprocess execution shared by all difficulties, cancellation/watchdog/stale-position rejection
- Detached cached research (Hard static), per-position visual caches, save/replay compatibility
- Regression tests + Windows/Linux CI and before/after serial benchmark evidence

## Validation

- 93 tests passed locally (Python 3.12.3 / Windows 11 / pygame 2.5.2 / NumPy 1.26.3).
- Baseline frozen before production edits: 8 passed, 3 reproduced known defects (now fixed).
- Profiled median quiet/midgame: 605.53/888.43ms -> 58.52/85.47ms; immediate forced-block path costs ~4.3ms more due to correctness checks. All tactical baseline answers remain legal/correct/nonmutating.
- Real SDL Windows smoke (not dummy): max frame 18.03ms, Esc cancellation 1.25ms, worker stopped.
- Independent reviewer identified issues which were fixed with regressions; see review document.

## Scope / acceptance limitations

Overall gate **CHANGES REQUESTED**, not a claim of complete release PASS: full playing-strength/no-regression matches and frozen exe validation are still outstanding and will be reported in the stacked Very Hard work. Five's double-three/four check remains deliberately contiguous-only in Phase A; formal recursive Renju rules belong to Phase B. Custom non-five targets now both win with >=N and have no black-only fouls; old saved layouts remain readable, but previously inconsistent outcomes may be reinterpreted. Simplified opening preserved and not called tournament opening compliance.

See `docs/hard-core-design.md`, `docs/hard-async-design.md`, `docs/hard-validation.md`, `docs/hard-independent-review.md`, and `benchmarks/results`.

**Do not merge main without owner approval.** PR-B will be stacked on this branch; it must not replace the Hard search algorithm.
