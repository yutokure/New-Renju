# Independent Phase B Renju placement review

## Decision and scope

**PASS — bounded source review of the placement-rule core and its Board delegation.**

No confirmed rule-adjudication defect was found in the reviewed implementation. This is **not** exhaustive RIF certification, approval of the full Very Hard engine, a playing-strength claim, or approval of tournament opening/claim/pass procedures. Outstanding integration and corpus limitations below remain explicit. The parent must separately close its operational/UI and overall acceptance gates.

Review date: 2026-11-08. Reviewer was independent of the rule implementation and research-fixture authors. The reviewer changed only this document, did not alter production/test code, and did not run matches or heavy performance benchmarks.

Reviewed material:

- [Rule core](../renju_rules.py), especially terminal priority, four identity, real-three witnesses, explicit-stack recursion, and bounded memoization.
- [Board delegation](../board.py), including exact-byte invalidation and temporary scopes.
- [Rule design](renju-rules-design.md), [research/certificates](rules-research.md), [composed fixtures](tactical-proposals.json), and [rule tests](../tests/test_renju_rules.py).
- Normative [RIF rules](https://www.renju.net/rifrules/), definitions §3 and §§9.1–9.3, fetched and read independently during this review. The cited source also makes clear that tournament procedure and full opening are separate concerns.

## Findings

### No blocking placement-core defect found

1. **Black exact-five priority:** all axes are inspected before overline/four/three fouls decide legality. An exact five in one axis therefore correctly takes precedence over a simultaneous overline elsewhere. A maximal six in one axis does not become a five by selecting a subwindow. This agrees with the qualifying phrase in RIF §9.2, not merely with the supplied tests.
2. **White victory:** maximal runs of at least five win; white has no black-only placement fouls.
3. **Four identity:** five-cell windows construct `(axis, four-stone-set)` identities and merge endpoints. A straight four is one identity with two completions. Two overlapping but distinct fours in one axis remain distinct. Black overline-poisoned fills are excluded. Because an exact-five fill wins before other-axis fouls, these valid exact-five completions do not require another foul veto.
4. **Real three:** a proposed extension must produce a contiguous four with two genuine exact-five endpoints and be legal **and nonwinning**. A winning extension in a different axis is not a three witness. One permitted extension suffices; every possible extension need not be permitted.
5. **Recursive three legality:** an extension with one four plus two real threes remains forbidden. Child witnesses are evaluated on the state containing the root and every current hypothetical extension. There is no fixed rule-recursion cutoff.
6. **Termination and memo:** each child occupies an empty cell with black, so a path is finite. Explicit suspended frames avoid Python's recursion limit. A memo key includes both complete color bitsets and the placed root cell; size and target semantics are fixed on the Rules instance. Interrupted partial verdicts are not inserted. Already finished child verdicts remain sound after a later interruption. Dictionary hash collisions cannot equate unequal tuple keys.
7. **Mutation/callbacks:** callback exceptions propagate instead of becoming legal/illegal answers. Root and child writes are guarded by restoration, including `BaseException`. The initial context scan performs no writes. The callback must not mutate the borrowed list; this restriction is documented. These objects are not a shared concurrent-mutation API.
8. **Custom/opening consistency:** non-five targets use symmetric `>=N` wins without black fouls. Other sizes with target five are explicitly nonofficial Renju-core extensions. Board and Rules preserve the same simplified coordinate-opening policy independently of target/player; that is intentionally not the complete RIF opening protocol.
9. **Board caching:** exact grid bytes, size and target invalidate the per-position flat-list/cache. Direct grid edits affecting white blockers invalidate as required. Nested `temporary_move` restoration may leave an internal cache for the last queried hypothetical state, but the next query detects the byte mismatch and refreshes it. Returning to an identical byte state can safely reuse its correct result. Neither `last_move` nor opening count belongs in this particular foul-cache key, because foul classification explicitly bypasses opening and is move-local.

### Operational/integration follow-ups, not demonstrated core misadjudications

| Priority | Observation | Required treatment |
|---|---|---|
| P2 — parent reports remediated | [Game visual cache](../game.py) originally called full black legality over all empty cells on the main thread. One-position caching removed repeated frame work, but exact recursive foul adjudication has no polynomial/wall-time bound. | Parent subsequently reports moving the exhaustive overlay into [the worker](../ai_worker.py), kind `legality`, with rule deadline callback and serial analysis-runner queue/poll; incomplete overlays hide unknown cells instead of inventing markers, and main render computes only opening geometry. This rules-only review acknowledges the remediation but does not independently sign off its UI integration tests. A final selected-move validation is a different, much smaller workload. |
| P3 | [Rule design](renju-rules-design.md) initially said the isolated task had not installed Board delegation; production now delegates. [Research](rules-research.md) describes README discrepancies from its earlier snapshot. | Mark these as historical scope notes or update integration wording; avoid implying the currently corrected README still has the historical defect. |
| P3 | Directly reassigning Board `size`/`win_length` can recreate its internal Rules object, but public ruleset/opening metadata was not refreshed there at review time. Normal game settings construct a new Board, so this is not a demonstrated supported-path error. | Either document dimensions/semantics as immutable per Board or refresh related metadata together if direct semantic mutation is supported. |

No claim is made that `_Context` initial signature scans or full white classification are constant-time. White/custom **legality-only** calls do bypass the scan; rich summary/classification builds a context and is intentionally more expensive. This is an optimization boundary, not a correctness finding.

## Independent adjudication of supplied fixture oracles

The labels were not accepted merely because the production Rules implementation returned them. I read the certificate geometry against RIF and ran a second, disposable in-memory reference with different construction:

- Enumerate four-stone **combinations** on each full axis through the root, then try empty fills and inspect the resulting maximal exact-five run.
- Enumerate three-stone combinations, try a fourth stone, require a contiguous four and two unpoisoned endpoints, then recursively evaluate that extension for legal/nonwinning status.
- Inspect terminal maximal runs before foul logic.
- Do not import Rules internals, Board, or either AI into that reference. Use independent immutable-tuple memoization only to avoid redundant reference work.

This is a second implementation derived from the same normative interpretation, not a maintained external oracle. Its agreement increases confidence in geometry and bookkeeping but cannot resolve a shared misunderstanding of the official rule.

### Rule certificates: all 11 accepted within their stated scope

| Fixture | Independently checked conclusion |
|---|---|
| `exact-five-beats-overline` | Row 7 columns 3…7 is an exact five; column 7 rows 4…9 is six. The five wins. |
| `black-overline-only` | Only the horizontal maximal six is made; forbidden for black. |
| `white-overline-wins` | The same six-stone shape wins for white. |
| `open-four-one-identity` | Columns 5…8 form one four; columns 4 and 9 are its two completions. |
| `same-axis-double-four` | Distinct sets `{3,5,6,7}` and `{5,6,7,9}` in row 7 complete at columns 4 and 8 respectively; neither completion is an overline. Forbidden double-four. |
| `broken-four` | The set at columns 4,5,7,8 completes uniquely at 6. Legal single four. |
| `broken-three` | The set at columns 5,7,8 extends uniquely at 6 to a straight four, with endpoints 4 and 9. |
| `false-three-overline-endpoint` | The apparent horizontal three fails: extension at 5 wins immediately; extension at 9 has a poisoned left endpoint at 5 joining column 4 into six. The vertical three remains real. |
| `false-double-three-double-four-extensions` | Each horizontal extension makes both a horizontal and a vertical four; both are forbidden. Root vertical witnesses survive; root legal. |
| `one-legal-extension-is-enough` | Removing the right-side extra stones makes extension at `(7,9)` legal. Together with the vertical real three, the root is now forbidden double-three. |
| `false-double-three-recursive-extensions` | Both horizontal extensions create one four plus two real threes. The listed nested witnesses `(5,5)`, `(5,3)`, `(5,9)`, `(5,11)` are legal and nonwinning in their respective branches. These children are forbidden, leaving only the root vertical real three; root legal. |

The separate reference matched all 11 root legal/win labels, the explicit forbidden extension labels, and all listed nested legal/nonwinning witnesses. The nested fixture genuinely exercises the specified next layer, but it does **not** establish arbitrary-depth corpus coverage.

### Tactical certificate sanity review

These are checks of the supplied **hand arguments**, not a review of production tactical proof statuses/search coverage:

- **Black four-three VCF positive:** after the nominated root, every white nonblocking placement leaves the horizontal immediate five. The one prolonging block is `(7,8)`; the vertical straight-four continuation then has two available endpoints. White's sparse stone count rules out an immediate counterwin. Accepted as a root-specific composed proof.
- **Remote immediate-win negative:** white's separate row-2 four wins instead of defending. Accepted as an explicit root counterexample, not a global no-win assertion.
- **Blocking counter-four negative:** the block `(7,8)` simultaneously creates a white open four in column 8; black has no immediate five and cannot stop both endpoints. Accepted.
- **White forbidden-point trap:** the sole completion `(7,7)` is forbidden to black by two real threes with the listed simple witnesses. Black's other sparse lines have no immediate win, so a legal remote placement cannot remove white's next winning stone. Accepted.
- **White double-three VCT positive:** after the root, the 220 black placements are partitioned into row-7 versus off-row defenses. The prescribed perpendicular straight-four corridor is untouched in either case. Black's at-most-two-stone count at the following turn rules out an immediate win. Pass, if modeled, leaves both corridors untouched. Accepted as a deliberately shallow composed all-defense proof.
- **Broken-three remote endpoint defense:** `(7,9)` defeats the specified straight-four extension at `(7,6)` even though it is not the extension square. Accepted only as continuation refutation.
- **Counter-four tempo negative:** the nonlocal white four forces the nominated black block, after which white `(7,5)` spoils the two-ended three continuation. Accepted only as attacker-only progression refutation.

None of these sparse setups supplies an alternating legal game history. Test harnesses must disable opening and history checks for these position-level oracles; the same arrays are not official tournament records.

## Reproduced checks

1. Focused suite:

   ```text
   python -B -m pytest tests/test_renju_rules.py -q
   198 passed in 1.30s
   ```

   The count includes symmetric transforms and API/mechanical cases, not 198 unrelated authoritative Renju positions.

2. Independent reference differential check: **600** seeded pseudo-random black placements on **9×9** geometry, root `(4,4)`, rows/columns 1…7 filled independently with probabilities empty `.60`, black `.32`, white `.08`, root cleared before move. Seed **761239**. Full classification legal/win and quick legality agreed for every case; no mismatch. These are custom-board geometric stress cases, not RIF game-history fixtures.
3. Board direct-write/cache probe: the simple black cross root changes from forbidden double-three to legal when both horizontal endpoints are blocked by white; deleting/restoring each blocker through nested `temporary_move` scopes produces the corresponding verdicts and finally returns to the original forbidden state. All probes passed.
4. A small rule-call timing probe completed before the parent requested exclusive serial tactical benchmarking; no subsequent timing work was run. On the two supplied false-three setups, cold full black-legal-map calls were roughly **6.2–7.6 ms**, warmed cache roughly **0.31–0.34 ms**. These are local descriptive samples, not a performance benchmark, not representative-game statistics, and not a pathological upper bound. The main-thread risk above is retained despite these fast examples.

## Exact remaining evidence gaps

- No official federation adjudicator or independently maintained external rules solver has certified the implementation.
- Only one supplied nested false-three layer has an independently examined geometric certificate. More deep nested patterns, same-axis edge cases, and published reachable Renju positions would improve coverage.
- Differential testing is finite, shares the same stated RIF interpretation, and does not prove all possible 15×15 states.
- Full tournament opening, passes/clock/claims/missed-foul protocol, and historical reachability are deliberately outside the placement core. Product documentation must not label this complete competitive-protocol compliance.
- Save migration, full UI responsiveness, worker deadlines/memory, tactical proof soundness, general-search quality, and superiority to Hard remain separate parent acceptance tasks. This review's scoped **PASS** must not be promoted to an overall Very Hard PASS without that evidence.
