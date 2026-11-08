# Independent bounded tactical search

## Scope and ownership

The implementation is [tactics.py](../tactics.py), with regression coverage in
[test_tactics.py](../tests/test_tactics.py). It imports the shared placement
[Rules](../renju_rules.py), but **no** general engine, Board, evaluator, game,
settings, or UI module. It does not inherit from Hard or use Hard's evaluation.
It implements bounded attacker-OR / defender-AND VCF and VCT, not unrestricted
minimax and not a claim that Renju is solved.

The design follows the proof semantics in
[the architecture contract](very-hard-architecture.md) and the independently
composed certificates in [rules research](rules-research.md) and
[structured tactical proposals](tactical-proposals.json). Those fixtures are
position-level compositions with opening enforcement disabled; no alternating
legal game history, tournament opening compliance, or external solver
certification is asserted.

## Public contract

```python
from tactics import ProofStatus, TacticalSolver

solver = TacticalSolver(
    rules,
    check=None,            # caller cancellation/deadline callback
    node_limit=20_000,
    max_depth=9,            # plies, INCLUDING the final winning placement
    mode="vcf",            # "vcf" or "vct"
    time_limit=None,        # optional seconds local to EACH solve()
)
result = solver.solve(cells, attacker, move_count, roots=None)
# roots is keyword-only; omitted means generated forcing candidates.
# roots=[] means no nominated root, not unrestricted generation.
result = solver.verify_root(cells, attacker, move_count, root)
# Exactly equivalent to solve(..., roots=[root]).
```

`cells` is row-major `0`/`1`/`2`; `attacker` is black `1` or white `2`.
`move_count` is the placement count used by `Rules.opening_allows`, not a
reconstructed count/history. Hypothetical defender pass does **not** increment
it. A solver is reusable sequentially, but is not thread-safe for concurrent
calls. Rules and attacker policy are fixed for one invocation; the search memo
is invocation-local and cleared afterward.

The frozen `TacticalResult` fields are:

| Field | Meaning |
|---|---|
| `status` | `ProofStatus.PROVEN_WIN`, `.PROVEN_LOSS`, or `.UNKNOWN` |
| `move` | Certified legal root, or `None` |
| `pv` | One legal representative alternating continuation as `tuple[int, ...]` |
| `nodes` | Search states and attempted attacker-candidate events visited |
| `reason` | Diagnostic such as `certified_strategy`, `depth_limit`, `time_limit`, `node_limit`, `no_forcing_proof` |
| `depth` | Maximum certified ply count, including modeled pass plies |
| `ruleset` | `rules.ruleset`; opening remains the supplied Rules instance's separate policy |
| `certificate` | Structured strategy tree, or `None` |

The enum subclasses `str`, with values `proven_win`, `proven_loss`, `unknown`.
Only an already-terminal board whose sole winning color is the opponent yields
public `PROVEN_LOSS`. A refuted nominated root **does not** establish that all
other roots lose. A failed forcing candidate, missing candidate, unsupported
continuation, or resource cutoff is `UNKNOWN`. Boards with wins for both colors
are `UNKNOWN` as inconsistent terminal inputs. An already won board has no new
root or PV. The API does not validate reachability/history or infer a previous
forbidden placement from an arbitrary supplied board.

### Cancellation and budgets

The local time/node guard raises `TacticalInterrupted`, which `solve` catches
and converts to `UNKNOWN`. A caller may explicitly raise that same exception
for an UNKNOWN result. All other caller exceptions (for example the parent's
`SearchStopped`) propagate; the parent owns how it represents cancellation.
Neither rules callbacks nor tactical callbacks turn incomplete work into a
legality or proof verdict. Checks cover candidate/window loops, rule queries,
all-board wins, defender enumeration, recursion, and the completed-proof return.

The public input is copied once, and internal placements use `try/finally`
make/unmake. The rules core also restores its own hypothetical placements.
Consequently cancellation after a root, after a forced reply, or inside a nested
black-three legality query cannot leak changed cells. No partial certificate is
returned on interruption. Nodes are not CPU operations: legal defender checks,
line scans, and rule-recursion polls are not individually counted as tactical
nodes; the callback/local deadline remains the wall-clock guard.

## Geometry helpers for the general engine

```python
winning_moves(cells, player, move_count, rules, check=None) -> tuple[int, ...]
is_winning_move(cells, index, player, rules) -> bool
forcing_moves(cells, player, move_count, rules,
              mode="vcf", check=None) -> tuple[int, ...]
```

- `winning_moves` scans **every board line**, including remote threats; it does
  not classify every empty point. It applies the simplified opening policy.
  A sparse-stone fast exit is exact: fewer than `target-1` own stones cannot
  complete a line with one stone. Geometry uses maximal contiguous runs.
- `is_winning_move` is a scalar geometric predicate on an empty point. It does
  **not** check the opening policy; callers wanting legal immediate wins should
  use `winning_moves` or separately apply `Rules.opening_allows`.
- For connect-five black, a maximal exact five in **any** axis wins. Simultaneous
  overline/double-four/double-three does not defeat exact-five priority, so no
  recursive legality query is needed for a positive black geometric win.
  White, and both colors at custom non-five targets, use `>= target`.
- `forcing_moves` supplies a restricted legal candidate set. It never means
  "all legal moves" or "all winning moves." Generated immediate wins appear
  first. Other candidates are ordered by cheap near-winning line windows.
- `Rules.four_summary` is a cheap filter, **not** a permission to play black:
  `legal=None` always leads to full `Rules.is_legal` before acceptance. VCT
  three-only candidates additionally use full `Rules.classify` and its actual
  legal real-three witnesses. No visual pseudo-three is a proof.

The helper API accepts pre-move lists and uses the same rules policy and move
count as search. Cached geometry depends only on board size/target, not position
or rules verdict. Exact tuple position keys are used for invocation-local proven
subtrees; no unchecked Zobrist collision can become a tactical certificate.

## AND/OR soundness

### Attacker OR nodes

1. An immediate legal winning move ends the proof.
2. The opponent's immediate winning squares are checked all-board. Without an
   attacker immediate win, two opponent winning squares refute every available
   attacker move: one placement cannot occupy both. With one opponent endpoint,
   only its occupation can avoid a loss next turn. This catches a counter-four
   made by the **preceding forced block**, before considering another attack.
3. Otherwise only selected forcing candidates are tried: legal four creation
   for VCF; legal four or real-three creation for VCT. Every accepted move is
   rule checked before placement.
4. Any one completed AND child establishes the OR win. If none completes, return
   no certificate/UNKNOWN, not PROVEN_LOSS.

The candidate restriction can miss a quiet winning preparation, a quiet forced
block followed by a renewed attack, or a winning strategy outside the depth
budget. That is intentional incompleteness, not a negative game proof.

### Defender AND nodes

Always first enumerate the defender's immediate legal wins geometrically over
**all board lines**. One such move refutes the nominated attack even if remote
from it, even if occupying the attack's only completion is also possible.

Then distinguish:

- **Two or more immediate attacker winning squares:** absent a defender
  immediate win, every defender placement leaves at least one endpoint. An
  opponent stone cannot change an already-completing line at an unoccupied
  different point. Black exact-five priority ensures that surviving completion
  remains legal even when other axes have forbidden-looking formations.
- **One immediate attacker winning square:** all nonwinning defender replies
  outside it lose next ply. If the defender cannot legally occupy that point
  (including a black forbidden-point trap), this partitions all replies and
  certifies the win. Otherwise search the **actual legal block** and its
  counterplay; do not carry on an attacker-only line past a counter-four.
- **No immediate attacker winning square, VCT real-three attack:** enumerate
  **every** legal defender placement and a conservative pass. These are actual
  separate AND branches, not simultaneous stones or selected extension blocks.
  A single unknown/refuting branch stops the proof safely. Only completion of
  all legal branches can return PROVEN_WIN.

The pass makes the defender stronger than the app's placement-only game, which
is conservative for a positive proof. Opening counts can differ after pass and
placement: the partition separately checks attacker winning squares at both
counts; if pass has no immediate winning square, its entire continuation is
searched rather than silently borrowing the placement-count result.

For custom connect-N the solver may use a legal placement creating next-turn
immediate winning square(s). It does not invent Renju four/real-three foul
semantics for non-five targets. Incompleteness for custom tactics is UNKNOWN.

## Certificate versus principal variation

`TacticalCertificate` has `kind`, `attacker_move`, `winning_squares`, `defenses`,
`includes_pass`, and `pass_winning_squares`. Each `DefenseBranch` contains a
placement integer (or `None` for pass) and a complete attacker continuation.

- `terminal`: a rule-checked immediate attacker winning placement.
- `winning_square_partition`: all legal nonwinning defender placements are
  covered by the stable immediate-winning-square argument; it records all
  winning squares and the independently evaluated pass endpoints.
- `forced_block`: the same partition plus the sole legal prolonging block and
  its full continuation.
- `all_defenses`: one branch per legal placement, plus pass, each certified.

The `pv` alone is **not** evidence for universal response coverage. It is one
replayable legal representative, normally choosing an actual endpoint block
where possible. In the exceptional case of no legal defender placement but a
modeled pass, the integer-only PV stops before that pass; the certificate still
records the complete coverage. `depth` counts that hypothetical pass. The tests
independently replay the full certificate tree, check rule legality and terminal
wins, enumerate the true full legal reply set at `all_defenses`, and reconstruct
the all-board partition endpoints without calling the tactical helper/solver.

## Validation and limits

Focused tests cover all seven independent tactical proposals:

- positive black VCF four → forced block → straight four;
- negative unrelated defender immediate win;
- negative forced-block counter-four;
- positive white forbidden-point trap;
- positive white VCT cross with **all 220 legal placements plus pass** recorded;
- negative broken-three remote endpoint defense;
- negative nonlocal counter-four tempo continuation.

They also sample dihedral transforms; replay legal terminal PVs; verify illegal
black roots; compare fast winning geometry with full shared Rules on the rule
fixtures, deterministic random boards and custom targets 3–7; exercise opening
and exact-five priority; enforce node/depth/time UNKNOWN; interrupt nested
rules work; verify parent exceptions propagate; and ensure solver reuse/empty
roots never imports a prior proof. These are regression tests and fixture
certificates, **not independent external Renju adjudication**, a performance
benchmark, or evidence that Very Hard is stronger than Hard.

The white-cross fixture is intentionally shallow and sparse. Its practical
runtime demonstrates that explicit all-defense coverage is feasible for this
minimal case, not that arbitrary deep VCT is cheap. The parent should first use
a bounded VCF slice, preserve a safe legal general-search fallback, and only
allocate VCT the remaining tactical slice. No promise of success fits every
position within a 0.3–0.5 second tactical budget or a five-second overall budget.
Time/node exhaustion yields UNKNOWN with no winning claim.
