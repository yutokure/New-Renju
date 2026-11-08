# Hard: bounded shallow search differential oracle

## Purpose and boundary

[The independent test suite](<../tests/test_hard_search_oracle.py>) checks a bounded part of [Hard's search](<../ai.py>): root-relative terminal values, root choice under a two-ply horizon, restoration, and sensitivity to a bounded or disabled transposition table. It is **not** a statistical playing-strength measurement, an official Renju rule oracle, proof of complete minimax equivalence, or a Hard non-regression PASS.

The reference deliberately shares Hard's static leaf evaluator. Therefore these tests cannot establish that its line-pattern evaluation is a good estimate of game-theoretic value or that it exactly matches historical scoring. Search correctness and evaluator quality are different questions.

## Independent reference

The reference uses a flat Python list, full-board connect-three winner geometry, exhaustive empty-cell enumeration, ordinary maximizing/minimizing recursion, and independent `try/finally` make/unmake. It does **not** call production `_minimax`, candidate ordering, TT/hash methods, `Board.check_win`, or `Board.temporary_move`.

- Geometry: both colors win with at least three connected stones in any of four directions.
- Terminal scores use root perspective before static evaluation: root win `p_win + remaining_depth`, root loss `o_win - remaining_depth`, full-board draw zero.
- Depth is two plies including the root move and one opponent reply. There is no alpha-beta pruning, TT, tactical narrowing, or extension in the reference.
- Leaf evaluation alone is delegated to a fresh Hard evaluator and a newly constructed custom board. Reference search never uses the production board's move or win helpers.
- Every sample is 3×3 or 4×4 custom connect-three. The project's opening policy does not restrict these board sizes, and custom games have no forbidden moves. Thus every empty cell is independently known legal.
- Each sampled state must have every empty cell within Chebyshev distance one of an existing stone. Adding a stone cannot reduce this coverage; the suite also checks every child explicitly. Therefore Hard's radius-one candidate geometry is genuinely full width at both candidate layers, not an excuse for differences.

## Bounded reproducible sample

A local Python RNG with fixed seed `20261108` generates **20 reachable nonterminal positions**: five per board-size/side-to-move combination, with varied counts (4–9). Candidate histories alternate black/white; every prefix is checked for terminal geometry. Rejection is bounded to 10,000 attempts and rejects only terminal histories or inadequate neighborhood coverage. **No position is rejected for engine behavior, tactical category, or reference value.**

All 20 positions remain in the suite. Each is tested with TT disabled (`tt_capacity=0`) and bounded (`128`). The engine is configured depth two with an ample ten-second budget to avoid interpreting a partial iteration as a search differential; these tiny cases actually complete promptly. Legal-move membership and restoration of grid/last move/forbidden marker are asserted.

### Outcome: 19 matches, one explicit selective-policy difference

For **19 of 20 positions**, the move returned by Hard has the best value under the independent exhaustive depth-two reference, with both TT settings. Tie choices are compared by value, not arbitrary coordinate identity. A root tactical result or completed depth two is required.

The remaining sampled position is **not removed, xfailed, or presented as oracle agreement**. Its separate regression characterizes the known difference between Hard's retained forced-reply policy and strict two-ply static minimax.

## Preserved counterexample: forced reply hides a fork

Board: 4×4 custom connect-three, White to move after five legal plies. Zero-based coordinates:

```text
History: B(3,3), W(1,3), B(2,0), W(1,1), B(1,2)

       c0 c1 c2 c3
r0     .  .  .  .
r1     .  W  B  W
r2     B  .  .  .
r3     .  .  .  B
```

There is no terminal line. Every empty cell is in the occupied radius-one neighborhood. White has no immediate win at the root, and neither root candidate below is itself terminal.

| White root candidate | White winning endpoints next turn | Forced Black reply selected by Hard | Forced-reply leaf score | Strict exhaustive two-ply value |
| --- | --- | --- | --- | --- |
| `(2,3)` — selected | `(0,3)` | `(0,3)` | −962,500 | −19,397,000 |
| `(2,1)` — exhaustive best | `(0,1)`, `(3,1)` | `(0,1)` | −1,392,500 | −18,813,000 |

Hard's recursive policy first looks for an immediate current-player win, then narrows to one block of an opponent win. After White `(2,3)`, Black is assumed to block `(0,3)`. Strict two-ply minimax can instead have Black ignore that threat with `(2,1)` to obtain a much lower **static** leaf score, even though White would win on ply three. This explains why the reference and production objective differ; it is not an alpha-beta sign/bound error or TT collision.

There is also a real tactical limitation: White `(2,1)` creates a two-endpoint fork. Blocking `(0,1)` still leaves White `(3,1)` winning. Hard nevertheless values the single-threat forced-reply leaf more highly because it does not recognize the surviving win beyond its two-ply static horizon. This is a missing fork/horizon capability of the retained selective policy, **not** evidence that Hard implements complete full-width minimax. The counterexample test independently verifies all these win endpoints, nonterminal branches, numeric leaf values, selected move, completed depth, and the strict reference mismatch for both TT settings.

A single bounded historical sensitivity check loaded original `d4b2edd` Hard with the same current custom-board referee, depth two, 1.5 seconds, and fixed Python/NumPy seed `20261108`. It chose `(2,2)` and restored the board. Thus the exact current `(2,3)` choice is not claimed to reproduce the original; the repaired hypothetical `last_move` probes activate the retained forced-reply policy. One position is insufficient to attribute historical playing-strength change, and the historical move is not asserted optimal by this check.

No production fix is included. Adding fork recognition, quiescence/tactical extension, or retuning the evaluator would expand the engine behavior beyond this bounded validation task. Restoring the original broken hypothetical `last_move` probing to regain historical behavior would not be an appropriate correctness fix.

## Test command and interpretation

```text
python -B -m pytest tests/test_hard_search_oracle.py -q
```

Validation result: **42 passed in 0.53 seconds**, no xfails. The suite reports 42 cases: 38 exhaustive-optimal comparisons (19 positions × two TT settings), two explicit selective-policy characterization cases, one sample/reachability/diversity check, and one terminal-priority/root-sign reference sanity check. Passing all tests means the stated comparisons and the known limitation reproduce; **it does not mean 20/20 oracle equality**.

This evidence is complementary to recorded serial matches. The previously recorded 16-game Hard-vs-original sample was 5 wins, 6 losses, and 5 censored, with wide and correlated uncertainty. This shallow oracle neither changes those measurements nor establishes the Hard playing-strength non-regression gate.
