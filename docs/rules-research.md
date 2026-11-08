# Rules and tactical research for New-Renju

Research performed against the sources below on 2026-11-07/08. This document contains independently composed examples, not reference implementation code. Only documentation and fixture proposals were changed; no production source, git operation, benchmark, or production-engine result was used to establish the claims below.

## 1. Sources, authority, and limits

1. **Normative:** [RIF International Rules of Renju](https://www.renju.net/rifrules/), decisions dated 2 May 1996 and corrected 3 May 1998. Relevant sections: board §2; definitions §3; pass §5; win/forbidden §9.1–9.3; historical opening §§11–12. This is the authority for the rules conclusions here.
2. **Explanatory:** [RenjuNet beginner tutorial](https://old.renju.net/study/rules.php). Explains broken/open threats, blocking threes, and white's forbidden-point trap. It deliberately introduces basic play before explaining formal openings; its first paragraphs are not a complete tournament protocol.
3. **Explanatory:** [RenjuNet advanced tutorial](https://old.renju.net/study/advanced.php). Especially useful for false threes caused by overline endpoints or forbidden double-four extensions. It also illustrates counterplay that changes whether an intersection is forbidden. Use the formal rule rather than memorizing diagram silhouettes.
4. **Search research, not Renju rules:** L. V. Allis, H. J. van den Herik, M. P. H. Huntjens, [*Go-Moku and Threat-Space Search*](https://renju.se/rif/proof/Go-Moku.pdf), especially §§2–6. The PDF was fetched and its FlateDecode text streams extracted in memory using existing Python `requests`, `re`, and `zlib`; no extractor was installed and no PDF/download artifact was retained. Text and section claims were inspected; diagram coordinates were **not** transcribed from the PDF.

The paper's §2 distinguishes unrestricted Gomoku, exact-five Gomoku, and Renju. Its solved variants are unrestricted Gomoku and its variant B (exact-five for both sides), **not a proof that tournament Renju is solved**. Its performance results are historical paper results, not measurements of this project. All coordinates below were derived independently rather than copied from its diagrams or from reference code.

### Existing documentation discrepancy

The existing [README](../README.md#L125-L139) was read before this work. At research start it described black's simultaneous five-plus-overline as forbidden and said white overline is not winning (subsequently corrected by the parent). Both original statements conflict with the cited RIF §9.1–9.2. It also summarizes only a restricted opening, not the full protocol of §§11–12. These are documentation/product issues for the parent implementation; that file was not edited by this research task.

## 2. Official adjudication scope

### 2.1 Exact five has priority over black's other formations

RIF §9.1 awards the first five, and also awards white an overline. §9.2 begins: black loses **“without at the same time attaining five in a row”** if it makes an overline, double-four, or forbidden double-three.

Consequently, after a proposed black placement:

1. Find the maximal contiguous run through the new stone in all four undirected axes.
2. If **any** run has length exactly five, it is a winning move, even if another axis simultaneously has length six or more, two fours, or two real threes.
3. Otherwise an overline is forbidden.
4. Otherwise a double-four is forbidden.
5. Otherwise a forbidden double-three is forbidden.
6. Otherwise the move is nonterminal and legal.

For white, a run of at least five wins; black-only foul restrictions do not apply. Six in one axis is not also an exact five in that same axis: do not count an arbitrary five-cell subwindow of a maximal six-stone run. An exact five in another axis is what invokes the black priority rule.

This is move-local automatic adjudication. Formal tournament §§9.6–9.8 additionally have claims, clocks, and missed-win/missed-foul rules. An app that immediately ends games or rejects black forbidden placements is simplifying those procedures. Such simplification is reasonable if documented, but is not literal implementation of the whole RIF document.

### 2.2 A four is not a direction count or a completion-cell count

Under §3 a four contains four own stones and can reach five with one placement. It can be broken. For black, a nominal fill whose maximal run is an overline is not an exact-five completion. The advanced tutorial explicitly illustrates that a supposed four disappears for this reason.

Useful canonical identity: **axis + unordered set of the four occupied coordinates**. Gather its exact-five completion cells separately. This is an implementation-independent way to preserve the definition, not copied code.

- `.BBBB.` is **one** straight four with **two** winning endpoints, not two fours.
- Two different four-stone sets can lie on the **same axis**, overlap, and both contain the newly played stone. This is a same-direction double-four. Counting at most one four per direction misses it.
- Count only formations containing the newly played intersection for the move's forbidden status. An old unrelated four is not newly created at that intersection.
- A completed five is terminal, not an additional four to be counted before the priority check.

For white tactical search, all immediate winning placements, including overline completions, matter. Do not silently replace “winning move” with a black-specific exact-five pattern predicate.

### 2.3 Real threes require recursive legal extensions

The §3 three must become a **straight four**, not merely a closed or broken four, by adding one stone **without at the same time making a five**. §9.3 then tests whether those straight-four extensions are permitted for black. This creates two distinct checks:

1. **Geometric/exact-five condition:** an extension must produce the required contiguous four with both endpoints capable of attaining exact five in that axis. Board edges, opponent stones, and extra black stones beyond an endpoint can invalidate this condition.
2. **Legality condition:** the extension must not itself be an overline, double-four, or recursively forbidden double-three. It may create one four plus one real three; that is not a foul.

For each axis and three-stone identity containing the root move, collect all qualifying extension cells. The three is real if **at least one** extension survives. A single forbidden extension does not kill a three when another extension is legal. Conversely, a visual `.BBB.` is false when **every** extension fails.

The extension's black legality must be tested on the board **including** the proposed root and that hypothetical extension. If an extension makes two apparent threes, apply §9.3 to their possible straight fours in turn. Repeat as necessary; a fixed recursion-depth cutoff is not the rule. Along an individual recursive branch every hypothetical move adds a stone, so the finite board supplies a termination bound; memoization may avoid repeated subproblems. An operational search limit must report an unknown/incomplete result rather than silently treat an unexamined extension as legal or forbidden.

There is an important distinction between **legal extension** and **three witness**: an extension that wins with an exact five in another direction is legal/winning under §9.1–9.2, but §3 expressly excludes a simultaneous five from the definition of a three. A general legal-move test alone is therefore insufficient to recognize a three.

“Both endpoints open” must mean genuine exact-five completions, not just two empty cells adjacent to four. For example, if a black stone beyond one empty endpoint would turn its fill into six, that side cannot complete the straight four. For a valid black straight four, each exact-five endpoint also invokes win priority even if it simultaneously makes another-axis formation.

### 2.4 Forbidden-point trap is a legal white tactic

White may make a four with only one completion cell `q`, where black's defensive placement at `q` is forbidden. Black cannot use that cell as a legal defense; white can win at `q` next. The engine must evaluate the defender's legality, not assume every empty winning cell can be occupied defensively.

Do not assume that a point remains forbidden after an intervening move: black can change a three to a four, poison a straight-four endpoint with an overline, or create/destroy a forbidden extension. The tutorials show both successful traps and false traps. Exact-five priority can also make an otherwise forbidden-looking black block a winning legal move.

## 3. Opening and configurable Gomoku policy

### Official versus simplified opening

The cited rules specify a 15×15 board and center first move, 26 opening patterns, tentative colors, the initial three placements by tentative Black, White's color choice, fourth move by the now-White player, and two unequal fifth-move proposals from which White chooses (§§11–12). Simply restricting the first three coordinates is **not** this complete opening protocol. Contemporary tournament opening systems also need explicit separate specification; this research does not certify their implementation.

Recommended names/metadata:

- `renju-rif-core-15x15`: RIF five/overline/forbidden definitions; opening is a separately named policy.
- `simplified-center-opening` / `legacy-pattern-opening`: the app's restricted-placement variant, explicitly not full RIF opening compliance.
- `gomoku-custom`: non-RIF board/target-length variant.

### Recommended custom target length 3…7

RIF's three/four definitions and asymmetric fouls are specific to five-in-a-row on 15×15. Do **not** mechanically generalize double-three, double-four, or the 26 openings to targets 3, 4, 6, or 7 while calling the result Renju.

Recommended default for custom Gomoku is **symmetric freestyle connect-K**: both colors win with a maximal contiguous run `>= K`, no black-only fouls, and no Renju opening constraints. This is a product recommendation, not an official RIF rule. If desired, provide an explicitly named **symmetric exact-K** option: exactly K wins; longer runs are legal but nonwinning for both colors. Preserve a documented old behavior through a clearly versioned `legacy`/compatibility ruleset rather than quietly reinterpreting existing saves.

Persist board size, target, victory policy, foul policy, opening policy, and ruleset/version in saves. For old saves without metadata, use an explicit documented migration/legacy assumption; do not infer the rules from whichever UI settings happen to be current. Evaluation, move legality, tactical search, and display must all consume the same resolved policy. These recommendations intentionally leave the choice of compatibility default to the product owner.

## 4. Fixture conventions and proof status

The companion [structured proposals](tactical-proposals.json) contains full coordinate arrays. Coordinates are **`[row, col]`, 0-based, 15×15**, with row increasing downward and column rightward. Only horizontal, vertical, and the two 45-degree diagonals are lines. `B`/`W` below mean occupied black/white sets **before** the stated root move; every omitted cell is empty.

These are **composed position-level fixtures**: opening enforcement and stone-count/history validation are disabled. Sparse positions may have unequal color counts and no supplied legal alternating history. They are not claimed to be reachable tournament records. Translate only the coordinate convention if the engine uses `(x,y)`; never transpose only the root.

Status is **human-checkable analytic fixture proposal, not external-engine-certified**. The explanations below are the certificate to review; no expected result rests solely on an AI solver's output. A small separate in-memory geometric exercise checked the principal rule examples, but is not an independent rules oracle and did not import the project. Suggested tests should verify the listed witness/counterexample, not merely trust the labels. In tactical negatives, **only the nominated root/continuation is refuted**; no claim is made that the entire position has no other winning move.

### 4.1 Rule formations

| ID | Before / root | Expected and hand check |
|---|---|---|
| `exact-five-beats-overline` | B row 7 cols 3,4,5,6; col 7 rows 4,5,6,8,9. Root B `(7,7)`. | Wins: horizontal maximal five, vertical maximal six. §9.2 does not override the five. |
| `black-overline-only` / `white-overline-wins` | Mover row 7 cols 3,4,5,6,8; root `(7,7)`. | Black forbidden with no exact five elsewhere; white wins with the identical six-stone geometry. |
| `open-four-one-identity` | B `(7,5),(7,6),(7,8)`; root B `(7,7)`. | Legal; one four on cols 5…8, endpoints `(7,4)` and `(7,9)`. |
| `same-axis-double-four` | B `(7,3),(7,5),(7,7),(7,9)`; root B `(7,6)`. | Forbidden. Distinct sets `{3,5,6,7}`→fill 4 and `{5,6,7,9}`→fill 8, all in row 7. Each fill gives exact five, not six. |
| `broken-four` | B `(7,4),(7,5),(7,8)`; root B `(7,7)`. | Legal; one four `{4,5,7,8}` completed at `(7,6)`. Contiguous-four-only matching misses it. |
| `broken-three` | B `(7,5),(7,8)`; root B `(7,7)`. | Legal; three `{5,7,8}` has unique straight-four extension `(7,6)` and endpoints `(7,4),(7,9)`. |
| `false-three-overline-endpoint` | B `(7,4),(7,6),(7,8),(6,7),(8,7)`; root B `(7,7)`. | Legal four-plus-real-three, not double-three. Horizontal extension `(7,9)` gives cols 6…9 but its left fill `(7,5)` would make cols 4…9 = six, so it is not a straight four. `(7,5)` itself makes five, not a three witness. Vertical three is real. |

### 4.2 False double-three: extension is forbidden double-four

`false-double-three-double-four-extensions`:

- B = `(7,6),(7,8),(6,7),(8,7),(4,5),(5,5),(6,5),(4,9),(5,9),(6,9)`; W empty; root `(7,7)`.
- The vertical root three has legal extensions `(5,7)` and `(9,7)`.
- The apparent horizontal three has only extensions `(7,5)` and `(7,9)`.
- At `(7,5)`, the horizontal four cols 5…8 and vertical four rows 4…7 in col 5 are distinct fours. This is forbidden double-four.
- At `(7,9)`, the horizontal four cols 6…9 and vertical four rows 4…7 in col 9 are distinct fours. Also forbidden.
- Therefore the horizontal three is false, only one real three remains, and the root is **legal**.

`one-legal-extension-is-enough` removes only `(4,9),(5,9),(6,9)` from that setup. The left extension is still forbidden, but `(7,9)` is now legal. The horizontal and vertical root threes are both real, so the root is **forbidden double-three**. This is a direct test of existential rather than universal extension qualification.

### 4.3 False double-three: recursive extension is forbidden double-three

`false-double-three-recursive-extensions`:

B = `(7,6),(7,8),(6,7),(8,7),(6,5),(8,5),(6,4),(8,6),(6,9),(8,9),(6,10),(8,8)`; W empty; root `(7,7)`.

After the root:

- Horizontal extension `(7,5)` makes one horizontal four **and two real threes**: vertical `{(6,5),(7,5),(8,5)}` and diagonal `{(6,4),(7,5),(8,6)}`. Legal straight-four witnesses are respectively `(5,5)` and `(5,3)`; neither is a five, overline, double-four, or forbidden double-three. Thus `(7,5)` is forbidden double-three despite its horizontal four.
- Horizontal extension `(7,9)` similarly makes a horizontal four plus real vertical `{(6,9),(7,9),(8,9)}` and anti-diagonal `{(6,10),(7,9),(8,8)}` threes. Witnesses `(5,9)` and `(5,11)` are legal.
- Both horizontal extensions are forbidden, so the root's horizontal three is false. The root's vertical three has legal `(5,7)`/`(9,7)` witnesses. The root is **legal**.

This requires recursive examination of a would-be double-three at the extension, rather than only rejecting overline/double-four extensions. It exercises one nested level, **not** arbitrary-depth completeness; a deeper independently reviewed suite is still desirable.

## 5. Tactical proposal certificates

VCF here means a forcing attack whose nonwinning attacking moves create a four; a legal terminal exact five is allowed as the final move. VCT permits real-three threats as well. These are search categories, not extra rules. Merely finding one cooperative line proves neither category. Check the defender's immediate wins first, legal blocks, counter-fours, and all defenses that invalidate a proposed continuation.

### 5.1 Positive black VCF: four → forced block → straight four

`vcf-positive-four-three`:

- B = `(7,4),(7,5),(7,6),(6,7),(8,7)`; W = `(7,3)`; black to move.
- B `(7,7)` is legal four-plus-three. Its only immediate exact-five completion is `(7,8)`.
- **Every white defense:** white has just one preexisting stone. A white placement cannot win immediately. Any placement except `(7,8)`, or a pass, leaves B `(7,8)` as an immediate legal exact-five win. Therefore only W `(7,8)` prolongs play.
- Then B `(5,7)` makes the straight four on col 7 rows 5…8, with exact-five endpoints `(4,7),(9,7)`.
- **Every subsequent white defense:** white then has at most three stones in total after its next placement, so cannot win; one move cannot occupy both endpoints. Black wins at an unoccupied endpoint. B `(5,7)` creates no second four or two real threes.

This certifies the nominated root without relying on a proximity filter or a selected cooperative defense.

### 5.2 Negative: an unrelated immediate defender win

`vcf-negative-defender-immediate-win` adds W `(2,2),(2,3),(2,4),(2,5)` to the preceding setup. Against B `(7,7)`, white wins immediately at `(2,6)` (also `(2,1)`), instead of blocking. The root is **not** a forced win. Testing only the attack's local completion squares would return a false certificate.

### 5.3 Negative: the forced block is a counterattacking open four

`vcf-negative-forced-block-counterfour` instead adds W `(4,8),(5,8),(6,8)` to the positive setup.

After B `(7,7)`, W `(7,8)` blocks the black four **and** makes white's vertical straight four on rows 4…7 of col 8, endpoints `(3,8),(8,8)`. Black has no immediate five: its horizontal four is blocked at both ends and the vertical col-7 line is only a three. One black move cannot stop both white endpoints. Thus the nominated root loses, even though a purely attacker-only continuation still suggests B `(5,7)`. Defensive placement can create a tempo-winning threat.

### 5.4 Positive white VCF by forbidden-point trap

`vcf-positive-white-forbidden-trap`:

- B = `(7,2),(6,7),(8,7),(6,6),(8,8)`; W = `(7,3),(7,4),(7,5)`; white root `(7,6)`.
- White now has a four on cols 3…6, left-blocked by B `(7,2)`, completing only at `q=(7,7)`.
- Black at `q` makes real vertical and diagonal threes, with simple legal straight-four extensions `(5,7)` and `(5,5)` respectively; no black five is made. Thus `q` is forbidden double-three.
- No legal black move can occupy `q`, and no black move can create an immediate five from these sparse black lines. Every legal placement elsewhere, or pass, leaves white's winning `(7,7)` intact.

This is a positive trap, unlike the false-double-three fixtures, where a black block that looks forbidden is actually legal.

### 5.5 Positive white VCT with **all legal defenses** covered

`vct-positive-white-cross-all-defenses`:

- W = `(7,6),(7,8),(6,7),(8,7)`; B empty; white root `(7,7)`.
- The root makes two perpendicular straight threes, not a four. White may legally make double-three.
- After root there are **220** empty cells and all 220 black placements are legal under the core rule; a first black stone cannot be forbidden. Include a black pass if the app supports §5.
- For **any** black defense `d`:
  - If `d.row == 7`, play W `(5,7)`. The vertical six-cell corridor `(4,7)`…`(9,7)` is untouched: the only row-7 member is `(7,7)`, already white and unavailable to black.
  - Otherwise play W `(7,5)`. Its horizontal six-cell corridor `(7,4)`…`(7,9)` is untouched, because `d` is off row 7.
  - For a pass, choose W `(7,5)`.
- The chosen extension makes a straight four, with endpoints `(4,7),(9,7)` or `(7,4),(7,9)` respectively. Black's next move can block at most one endpoint and black has at most two total stones, so cannot win or create a counter-four. White plays the other endpoint and wins (white overline would also be sufficient).

This partitions **every** legal defense, including remote cells, extension cells, endpoints, counterattack attempts, and pass. No branching-factor pruning is part of the proof. It is a minimal composed VCT-positive certificate, not a claim to a difficult/deep Renju solution or an alternating-history game.

### 5.6 VCT negatives: remote block and counter-four

`vct-negative-broken-three-remote-block`: B `(7,5),(7,8)`, black root `(7,7)`, W empty. The only straight-four extension is `(7,6)`. White `(7,9)` is a valid defense despite not occupying that extension cell; it removes an endpoint of the would-be four. In fact `(7,4),(7,6),(7,9)` are the three direct defensive cells for this broken-three threat. This refutes an “extension cell is the only defense” continuation, not every possible future strategy from the position.

`vct-negative-counterfour-tempo`: B `(7,6),(7,8),(2,2)`; W `(2,3),(2,4),(2,5)`; black root `(7,7)`. White `(2,6)` makes a four with sole completion `(2,7)` because `(2,2)` is black. Black has no immediate five, so must block at `(2,7)` to avoid losing next move (or make some separately proved winning move, which this sparse setup does not provide). White then `(7,5)` prevents either black three-extension from yielding a straight four: `(7,5)` is occupied and the line after `(7,9)` has only the right winning endpoint. The nominated attacker-only VCT progression is refuted by a nonlocal counter-four and subsequent block. No global minimax draw/loss assertion is attached to this negative.

## 6. Search implications and remaining uncertainty

The paper's §3.1 explicitly gives two or three direct defenses for different threes, including broken threes. Its §3.2 checks whether the defender can insert fours. §4 calls attacker-only lines **potential** winning sequences and then checks counterattacks; it introduces gain/cost/rest squares, dependencies, and conflicts. Its all-defenses-at-once reduction can miss wins; §5 discusses positions its TSS alone did not solve and the use of proof-number search. A failed restricted TSS search is therefore not a proof of no win. Conversely, an unverified attacker-only line is not a proof of win.

For this app, separate outcomes such as `proven_win`, `no_win_within_model`, and `unknown_or_budget_exhausted`. A timeout, candidate cap, fixed threat-depth limit, or unsupported rule configuration must not become “proven no tactical win”. A positive result should carry the ruleset, legal root, relevant reply coverage, and a replayable continuation or defense-partition certificate. Production game-over and forbidden logic must be shared with tactical verification rather than reimplemented inconsistently in evaluation.

Uncertainties/limitations deliberately retained:

- No claim of full current tournament-opening compliance, clock/claim compliance, or reachability of the composed fixtures.
- No independent external solver/arbitrator certified these positions. The supplied hand arguments should be reviewed and converted into tests against an independently checked rules oracle.
- The recursive fixture exercises one nested double-three legality layer, not every possible depth or every same-axis three identity. A broader independently reviewed corpus remains useful.
- The PDF was read as extracted text; its plotted positions were not geometrically reconstructed. None of the new coordinates is attributed to a PDF diagram.
- Custom 3…7 semantics and old-save migration are recommendations, not settled official rules. Compatibility behavior must be explicit and tested rather than guessed.
