## Stacked dependency

**Base: `improvement/hard-stability` / PR #1**. This PR contains Very Hard, formal shared placement rules and integration only on top of the conservative Hard changes. Do not merge main before owner approval. CI is not included or used per owner instruction; all validation is local.

## Implementation

- Independent `AIVeryHard`, no AIHard inheritance/evaluator reuse; configurable default5s
- Sound-positive bounded VCF/VCT AND/OR strategy certificates, all-board counterwins, full legal VCT placements + pass, `PROVEN_WIN`/`PROVEN_LOSS`/`UNKNOWN`
- Iterative negamax/alpha-beta, tactical ordering, incremental windows/threats/hash and bounded TT; heuristic beam estimates never advertised as proofs
- Separated formal Renju placement core: exact black five priority, white>=five, broken/same-axis fours, recursively legal nonwinning real-three witnesses
- Explicit custom connect3/4/6/7 policy and legacy simplified opening; shared referee, old-save-compatible v2 metadata
- Four difficulties, detached search/research/forbidden overlay, token rejection, cancellation, time and Windows commit-memory caps
- Independent rules/search/resource reviews, tactical fixtures, serial paired-color games, raw results, local build spec

## Evidence

- **467 local tests pass** (rules198, tactics57, plus Hard/general/UI/resource/compatibility regressions).
- Equal1.5s: VH **20W4L vs improved Hard**, **22W2L vs old Hard**; normal5s vs Hard1.5s **16W0L**.
- Eight unique purposeful openings, paired colors/repeats; confidence intervals and dependence warnings included. Not a universal Elo/strength claim.
- Nominated tactical roots7/7 VH vs6/7 Hard; three proof-positive positions certified; counterattack negatives remain UNKNOWN.
- All80 recorded games/3264 placements legally replayed with independent terminal geometry.
- Python Windows native UI:60frames, max19.56ms; Esc2.02ms; worker RSS~39MB, commit~28MB after removing unused BLAS pools; controlled memory cap and parent-death tests pass.

## Overall acceptance: CHANGES REQUESTED

This is deliberately **Draft**, not full release PASS:

1. Hard non-regression remains unestablished:5W6L5censored vs old Hard, broad dependent confidence interval; no correctness rollback or overfit tuning.
2. Frozen onedir build succeeds but temp-folder worker write/startup fails in this host; packaged executable not certified.
3. Rare complex black move may exceed12ms live revalidation and remain unapplied/UNKNOWN; automatic background single-point continuation not implemented.
4. Sparse composed tactical corpus / limited independent opening diversity; no federation/external strong-engine exhaustive certification.
5. Non-Windows OS memory cap explicitly unsupported; full tournament opening/clocks/claims/pass protocols out of scope.

See `docs/validation-results.md`, `docs/final-acceptance.md`, design docs and four independent reviews. All source-level review PASS labels are bounded and do not override these acceptance gaps.
