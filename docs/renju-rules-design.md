# Phase B: separated Renju placement core

## Scope and authority

[The implementation](../renju_rules.py) is independent of the AI and production
Board. It imports neither of them, NumPy, settings, nor game constants. The
parent integration now delegates Board forbidden queries to this core, with exact-position cache invalidation; the core itself still imports no Board.
The implementation follows the RIF placement definitions and priorities
summarized in [the research](rules-research.md), with composed, human-checkable
certificates from [the proposal data](tactical-proposals.json). Normative source:
[RIF International Rules of Renju](https://www.renju.net/rifrules/), definitions
§3 and adjudication §§9.1–9.3.

This is **move-local automatic placement adjudication**, not full tournament
compliance. It does not implement swaps, pass protocols, clocks, claims,
missed-foul procedures, legal-history reconstruction, or pre-existing game-over
validation. An already completed remote five does not automatically terminate a
query at an unrelated intersection. Position-level fixtures intentionally bypass
opening and alternating-history requirements.

Finite tests, especially the supplied nested-three fixture, are not an official
exhaustive certification or an independent external-solver oracle.

## Stable API

```python
from renju_rules import Rules, BLACK, WHITE

rules = Rules(size=15, win_length=5, opening=True, memo_limit=4096)
# Row-major list[int], before the candidate placement: empty=0, black=1, white=2
result = rules.classify(cells, row * rules.size + col, BLACK, move_count,
                        check=check_deadline, check_opening=False)
legal = rules.is_legal(cells, index, BLACK, move_count,
                       check=check_deadline, check_opening=False)
summary = rules.four_summary(cells, index, BLACK, move_count,
                             check=check_deadline, check_opening=False)

# Optional adapter; accepts NumPy Board.grid or a nested list of rows.
result = rules.classify_grid(board.grid, row, col, BLACK, move_count,
                             check=check_deadline, check_opening=False)
cells = rules.flatten(board.grid)

# Search may already have made the root. These do not check opening.
result = rules.analyze_placed(cells, index, BLACK, check=check_deadline)
summary = rules.four_summary_placed(cells, index, BLACK, check=check_deadline)
```

`classify`, `is_legal`, and `four_summary` require an **empty pre-move root**.
`analyze_placed` and `four_summary_placed` require the root to already contain
`player`. Queries restore all their hypothetical writes. `Rules.flatten` copies
once; a flat list is borrowed without a whole-board copy. Flat non-list
sequences are accepted and copied once. Do not pass a two-dimensional array to
the flat API; use the adapter or explicitly flatten it.

Opening enforcement is the conjunction of constructor `opening` and per-query
`check_opening`. Composed fixtures should use `check_opening=False` or
`Rules(opening=False)`. `move_count` does not enforce color parity or history.

### Immutable return types

All result/formation records are frozen, slotted dataclasses. All collection
fields are tuples; cell IDs are sorted flat indices. Axes are `(dr, dc)` from
`((0, 1), (1, 0), (1, 1), (1, -1))`.

- `MoveResult(legal: bool, win: bool, reason: str, fours, threes, winning_lines)`.
- `Four(axis, stones, completions)`: a four-stone identity and its one-move
  winning fills. An open four has two completions but is one identity. Distinct
  stone sets on the same axis remain distinct fours.
- `Three(axis, stones, extensions, witnesses)`: a three-stone identity and **all**
  qualifying extensions, not just the first witness.
- `ThreeWitness(extension, completions)`: maps a legal, nonwinning extension to
  its resulting straight four's two endpoints.
- `WinningLine(axis, stones)`: full maximal winning run through the root.
- `FourSummary(legal: bool | None, win, reason, fours, winning_lines)`.

Winning root moves are terminal and return empty `fours`/`threes`. Nonterminal
full classifications expose all root four identities and real-three witnesses,
even if an earlier foul already decides the verdict. Non-five configurations
return no Renju four/three data.

`four_summary` deliberately has **no `threes` field** and performs no recursive
three validation. A nonwinning black candidate without overline/double-four
returns `legal=None, reason="needs_three_check"`. This is *not permission to
play*. White and non-five candidates have definitive legality without black
foul analysis. `is_legal` is a complete, early-out query, not an approximation.

### Reasons and validation

Conclusive reasons:

- `legal_nonterminal`
- `win_exact_five`, `win_overline`, `win_connect_n`
- `forbidden_overline`, `forbidden_double_four`, `forbidden_double_three`
- `invalid_player`, `out_of_bounds`, `occupied`, `opening`, `not_player_stone`

`needs_three_check` occurs only on an unresolved `FourSummary`. Invalid board
length/shape, unsupported cell values encountered during a signature scan, or
invalid constructor dimensions raise `ValueError`. Callers are responsible for
well-formed integer 0/1/2 cells; the fast white/custom legality path intentionally
avoids a full-board validation scan. Invalid coordinates are not wrapped across
rows by the grid adapter.

`check` is a zero-argument callback. Its return value is ignored; cancellation or
deadline expiry must **raise**. Any exception, including `BaseException`,
propagates. There is no silent unknown-to-legal/illegal conversion. Search must
catch its own deadline exception and report budget exhaustion separately.

## Adjudication and formation construction

### Five priority

Read maximal runs through the root on **all four axes** before deciding:

1. Black: any exact five wins, even simultaneously with an overline, two fours,
   or two real threes in other axes.
2. White: any run of at least five wins.
3. Black without a five: overline, then double-four, then double-real-three are
   forbidden, in that diagnostic priority order.
4. Otherwise the placement is legal and nonterminal.

A length-six black run is not an exact five merely because it contains five-cell
subwindows. Winning lines retain their maximal lengths.

### Fours, including broken and same-axis distinct identities

Only five-cell windows containing the root are inspected. Four own stones plus
one empty intersection define a potential four. Opponent stones invalidate a
window. For black, a black neighbor immediately outside the window poisons its
fill into an overline, so it is not an exact-five completion in that axis.

Group by `(axis, sorted four-stone set)` and union completion cells. This
preserves a straight four's two endpoints without double counting, while
retaining same-axis double-fours with distinct stone sets. Old unrelated
formations that do not contain the root are excluded. White completion windows
may join further white stones: a white overline is a winning fill.

### Real threes and recursive legal nonwinning extensions

Inspect four-cell intervals containing the root, with three own stones and one
empty extension, plus an empty intersection at both ends. Black also requires
neither endpoint to be poisoned by a black stone immediately beyond it. This
ensures each endpoint makes an exact five in that formation axis. Group by
`(axis, sorted three-stone set)` and collect candidate extensions/endpoints.

For each candidate extension on the board **including the current root**:

1. Hypothetically add the extension.
2. Run full black legality (exact-five priority, overline, fours, recursively
   real threes).
3. Accept it only if it is both **legal and nonwinning**. A simultaneous exact
   five in *any* axis is a win, hence not a three witness under §3.
4. The three is real if at least one candidate survives. The full classification
   retains every surviving witness; the quick legality query stops once enough
   real identities decide the foul.

White has no black fouls. Its tactical three data uses geometric straight-four
extensions with both winning endpoints and excludes a simultaneous white win,
including an overline. This does not impose any white three/double-three foul.

An extension making one four plus two real threes is forbidden double-three;
one four does not exempt the extension. Conversely, a root with one genuine
three and one visually similar but recursively false three remains legal.

### Termination without an arbitrary recursion-depth rule

Every recursive child adds a black stone to an empty intersection; the finite
board bounds each path. No fixed threat-depth cutoff changes a rule answer.

The implementation evaluates the recursive dependency using suspended generator
frames and an **explicit stack**, not recursive Python calls. A generator
requests an extension, the driver makes the stone, evaluates its child, restores
the child mark, and returns the child's verdict to its parent. This avoids the
Python recursion limit becoming an implicit rules cutoff on a large custom
board. A mechanical 1,100-level stack test checks this driver separately from
actual Renju geometry; it is not a claimed 1,100-level certified Renju position.

Adversarial composed positions can still be expensive. The bounded memo and
local geometry improve practical work but do not create a polynomial-time
complexity guarantee. Use `check` to implement an operational budget and retain
a distinct incomplete/unknown search result when it raises.

## Mutation, memoization, and performance boundaries

- Each call scans the flat list once to construct two exact Python integer
  bitsets (black and white). Recursion updates these incrementally.
- All placements have an undo entry, and all query/child scopes are guarded by
  `try/finally`. Suspended generator frames own no independent mutations.
- Caller root, hypothetical child stones, and both signature bitsets restore on
  normal completion and exceptions. The Board adapter does not modify Board
  `last_move`, `forbidden_checked_pos`, or `grid`.
- Memo keys are `(complete_black_bitset, complete_white_bitset, last_cell)` on a
  Rules instance whose size/target semantics are fixed. These are complete
  signatures, not unverified Zobrist hashes. A Python dictionary hash collision
  cannot alias distinct tuple keys.
- Only complete `_Verdict`s are retained, never interrupted partial answers.
  Already completed child entries remain valid if a later callback aborts.
- The per-instance LRU is bounded by `memo_limit` (default 4096); zero disables
  storage. `clear_memo()` and `memo_entries` support lifecycle/testing.
- Geometry is precomputed for each intersection: four shared axis lines, at
  most twenty five-cell windows, and at most sixteen straight-four intervals.
  Formation work is local to the new stone, not a whole-board pattern sweep.
- `is_legal` stops after exact five, overline, two fours, or two real threes; it
  need not solve a lone three's witnesses to establish legal placement.
- White/custom legality-only calls are constant-size checks and do not scan a
  signature or make/unmake a root.
- `four_summary` provides cheap candidate ordering and immediate-win tests with
  no recursive threes. It still scans one position signature for its workspace.
- Full `classify` is intentionally richer/more expensive: it enumerates all
  witnesses even when quick legality would already be decisive. Use it for
  selected tactical candidates/certificates, not indiscriminately on every
  empty square when the search only needs a boolean.

A borrowed list must not be concurrently observed/mutated, and callbacks should
not mutate it. Use one Rules instance per search/thread. Memo/settings are not a
supported cross-thread mutation interface. No full-board copy is made at every
recursive child.

## Custom boards and simplified opening

Metadata explicitly separates core and opening:

| Configuration | `ruleset` | Win/foul behavior |
|---|---|---|
| 15×15, target 5 | `renju-rif-core-15x15` | Black exact-five priority/fouls, white ≥5 |
| Other size, target 5 | `renju-core-custom-SxS-nonofficial` | Same placement core, explicitly nonofficial board variant |
| Target other than 5 | `gomoku-custom-freestyle-connect-N` | Both colors ≥N; no black-only fouls |

The opening metadata is `simplified-center-opening` when enabled on an odd board
of size at least five, otherwise `none`. It preserves the existing project's
coordinate policy **independently of target length and player**:

- Count 0: center only.
- Count 1: `(center-1, center)` or `(center-1, center+1)`.
- Count 2: Chebyshev distance at most 2 from center.
- Count ≥3: no restriction.
- Even boards and boards smaller than 5: no opening restriction.

This is deliberately **not the full historical RIF opening**, a swap system, or
a claim that these coordinate restrictions alone define an official opening.
The constructor accepts any positive target fitting the board, although product
settings currently focus on 3…7. Persisting/migrating save-game rules metadata
remains a parent integration concern, not part of this isolated module.

## Focused verification and results

Run from the canonical project directory:

```text
python -m pytest tests/test_renju_rules.py -q
```

Final focused run on Python 3.12 (2026-11-08):

```text
........................................................................ [ 36%]
........................................................................ [ 72%]
......................................................                   [100%]
198 passed in 1.29s
```

[The tests](../tests/test_renju_rules.py) include:

- All **11** independent human rule certificates under all **8** rotations and
  reflections; exact stone-set/completion checks when provided, plus replay of
  every returned three witness and its two winning endpoints.
- Black exact-five plus overline, exact-five plus double-four, white overline,
  open-four identity, broken four/three, and same-axis distinct double-four.
- Overline-poisoned endpoints; an extension winning on another axis excluded
  as a witness for **both** colors; edges, opponent blocks, and unrelated old
  formations.
- Both recursive forbidden horizontal extensions and their explicit nested
  legal nonwinning witnesses from the supplied nested certificate.
- Normal and exception restoration, entry and nested deadline/cancellation
  callbacks (including `BaseException`), placed-root and NumPy Board adapters,
  and unchanged Board transient state.
- Rich-vs-quick semantics, immutable records, signature changes including white
  stones, bounded/disabled memo, and callback polling despite cached work.
- One initial list scan, not one copy per child; a mechanical recursion-driver
  stack test beyond Python's usual recursion limit.
- The 9-board-size × 5-target opening matrix, disabled/bypassed opening,
  non-five symmetric freestyle behavior, and explicitly nonofficial target-five
  custom-board behavior.

The eleven-fixture direct smoke also passed before the pytest suite. No heavy
benchmark, AI match, full-match test, git command, or frozen production-source
edit was performed by this Phase B task. These tests establish the listed
regressions, **not exhaustive RIF correctness**; deeper independently reviewed
real-position certificates and an external rules oracle remain useful.
