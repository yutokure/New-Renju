"""Composed placement tests, not exhaustive official/tournament certification.

Expected geometry comes from the human certificates in rules-research.md.
No production Board or AI implementation is used as a rules oracle.
"""
import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from renju_rules import (
    BLACK, WHITE, FourSummary, MoveResult, Rules, ThreeWitness, _Context, _Verdict,
)


PROPOSALS = json.loads((Path(__file__).resolve().parents[1] / "docs" /
                        "tactical-proposals.json").read_text(encoding="utf-8"))
RULE_FIXTURES = PROPOSALS["rule_fixtures"]


def transform(point, symmetry, size=15):
    row, col = point
    if symmetry >= 4:
        col = size - 1 - col
    for _ in range(symmetry % 4):
        row, col = col, size - 1 - row
    return row, col


def flat(point, size=15):
    row, col = point
    return row * size + col


def ids(points, symmetry=0):
    return tuple(sorted(flat(transform(point, symmetry)) for point in points))


def position(black=(), white=(), size=15):
    cells = [0] * (size * size)
    for player, points in ((BLACK, black), (WHITE, white)):
        for point in points:
            cell = flat(point, size)
            assert cells[cell] == 0
            cells[cell] = player
    return cells


def fixture(case, symmetry=0):
    cells = position([transform(p, symmetry) for p in case["black"]],
                     [transform(p, symmetry) for p in case["white"]])
    return cells, flat(transform(case["move"], symmetry)), (
        BLACK if case["mover"] == "black" else WHITE)


@pytest.mark.parametrize("symmetry", range(8), ids=lambda i: f"d4-{i}")
@pytest.mark.parametrize("case", RULE_FIXTURES, ids=lambda c: c["id"])
def test_eleven_human_rule_certificates_under_all_dihedral_symmetries(case, symmetry):
    cells, root, player = fixture(case, symmetry)
    original = cells[:]
    rules = Rules()
    result = rules.classify(cells, root, player, check_opening=False)
    assert result.reason == case["expected"]
    assert result.legal == (not case["expected"].startswith("forbidden_"))
    assert result.win == case["expected"].startswith("win_")
    assert rules.is_legal(cells, root, player, check_opening=False) == result.legal
    if "expected_root_four_count" in case:
        assert len(result.fours) == case["expected_root_four_count"]
    if "expected_root_real_three_count" in case:
        assert len(result.threes) == case["expected_root_real_three_count"]
    if "fours" in case:
        expected = {(ids(f["stones"], symmetry), ids(f["completions"], symmetry))
                    for f in case["fours"]}
        assert {(f.stones, f.completions) for f in result.fours} == expected
    if "threes" in case:
        expected = {(ids(t["stones"], symmetry), ids(t["legal_extensions"], symmetry))
                    for t in case["threes"]}
        assert {(t.stones, t.extensions) for t in result.threes} == expected
        for three, spec in zip(result.threes, case["threes"]):
            assert all(w.completions == ids(spec["straight_four_endpoints_after_extension"], symmetry)
                       for w in three.witnesses)
    assert cells == original
    # Every exposed witness is independently replayable, nonwinning, legal,
    # creates the nominated contiguous four, and has two exact-five endpoints.
    cells[root] = player
    for three in result.threes:
        assert three.extensions == tuple(w.extension for w in three.witnesses)
        for witness in three.witnesses:
            extension = rules.classify(cells, witness.extension, player, check_opening=False)
            assert extension.legal and not extension.win
            four_stones = tuple(sorted((*three.stones, witness.extension)))
            assert any(f.stones == four_stones and f.completions == witness.completions
                       for f in extension.fours)
            cells[witness.extension] = player
            try:
                for end in witness.completions:
                    finish = rules.classify(cells, end, player, check_opening=False)
                    assert finish.legal and finish.win
                    if player == BLACK:
                        assert any(len(line.stones) == 5 for line in finish.winning_lines)
            finally:
                cells[witness.extension] = 0
    cells[root] = 0
    assert cells == original


@pytest.mark.parametrize("symmetry", range(8))
def test_exact_five_beats_double_four_too(symmetry):
    # Root joins vertical 3..7 into exact five while independently making a
    # horizontal four and down-right diagonal four. No overline is necessary.
    black = [(r, 7) for r in range(3, 7)] + [(7, 4), (7, 5), (7, 6),
                                                (4, 4), (5, 5), (6, 6)]
    cells = position([transform(p, symmetry) for p in black])
    root = flat(transform((7, 7), symmetry))
    rules = Rules(opening=False)
    result = rules.classify(cells, root, BLACK)
    assert result.legal and result.win and result.reason == "win_exact_five"
    assert not result.fours and not result.threes  # terminal short circuit
    assert rules.is_legal(cells, root, BLACK)
    assert rules.four_summary(cells, root, BLACK).win
    # Without the vertical fifth, the two fours really are a double-four.
    cells[flat(transform((3, 7), symmetry))] = 0
    assert rules.classify(cells, root, BLACK).reason == "forbidden_double_four"


@pytest.mark.parametrize("player", (BLACK, WHITE))
@pytest.mark.parametrize("symmetry", range(8))
def test_any_axis_winning_extension_is_not_a_three_witness(player, symmetry):
    # Broken horizontal {5,7,8} has only extension (7,6), but that move
    # simultaneously completes the vertical five 3..7 on column 6.
    stones = [(7, 5), (7, 8)] + [(r, 6) for r in range(3, 7)]
    stones = [transform(p, symmetry) for p in stones]
    cells = position(stones if player == BLACK else (), stones if player == WHITE else ())
    root = flat(transform((7, 7), symmetry))
    extension = flat(transform((7, 6), symmetry))
    rules = Rules(opening=False)
    result = rules.classify(cells, root, player)
    horizontal_stones = ids([(7, 5), (7, 7), (7, 8)], symmetry)
    assert all(t.stones != horizontal_stones for t in result.threes)
    cells[root] = player
    witness = rules.classify(cells, extension, player)
    assert witness.legal and witness.win
    assert any(len(line.stones) == 5 for line in witness.winning_lines)


@pytest.mark.parametrize("symmetry", range(8))
def test_recursive_false_three_certificate_replays_nested_witnesses(symmetry):
    case = RULE_FIXTURES[-1]
    cells, root, player = fixture(case, symmetry)
    rules = Rules(opening=False)
    assert rules.classify(cells, root, player).legal
    cells[root] = player
    for rejected in case["rejected_horizontal_extensions"]:
        extension = flat(transform(rejected["move"], symmetry))
        result = rules.classify(cells, extension, player)
        assert result.reason == rejected["reason"] == "forbidden_double_three"
        assert len(result.fours) == 1
        assert len(result.threes) == 2
        cells[extension] = player
        try:
            for nested in rejected["nested_real_threes"]:
                stone_set = ids(nested["stones"], symmetry)
                witness = flat(transform(nested["legal_straight_four_witness"], symmetry))
                three = next(t for t in result.threes if t.stones == stone_set)
                assert witness in three.extensions
                verdict = rules.classify(cells, witness, player)
                assert verdict.legal and not verdict.win
        finally:
            cells[extension] = 0


@pytest.mark.parametrize("method", ("classify", "is_legal", "four_summary"))
def test_queries_restore_input_normally_and_on_every_sampled_callback_exception(method):
    cells, root, player = fixture(RULE_FIXTURES[-1])
    original = cells[:]
    baseline_polls = []
    getattr(Rules(opening=False), method)(cells, root, player,
                                         check=lambda: baseline_polls.append(1))
    assert cells == original

    class Cancelled(BaseException):
        pass

    # Include entry, after root make, inside geometry, and deeper child work.
    points = sorted({1, 2, 3, len(baseline_polls), len(baseline_polls) // 2})
    for fail_at in points:
        calls = 0

        def check():
            nonlocal calls
            calls += 1
            if calls == fail_at:
                raise Cancelled("deadline/cancellation must propagate")

        with pytest.raises(Cancelled):
            getattr(Rules(opening=False), method)(cells, root, player, check=check)
        assert cells == original


@pytest.mark.parametrize("method", ("classify", "is_legal", "analyze_placed"))
def test_deep_cancellation_restores_all_hypothetical_stones(method):
    cells, root, player = fixture(RULE_FIXTURES[-1])
    if method == "analyze_placed":
        cells[root] = player
    original = cells[:]
    initial_count = cells.count(BLACK)

    def check():
        if cells.count(BLACK) >= initial_count + (2 if method == "analyze_placed" else 3):
            raise TimeoutError("nested child reached")

    with pytest.raises(TimeoutError, match="nested child reached"):
        getattr(Rules(opening=False), method)(cells, root, player, check=check)
    assert cells == original


def test_after_placed_and_grid_adapters_preserve_transient_state():
    import numpy as np
    from board import Board

    cells, root, player = fixture(RULE_FIXTURES[6])  # broken three
    rules = Rules()
    result = rules.classify(cells, root, player, check_opening=False)
    board = Board()
    board.grid = np.array(cells).reshape((15, 15))
    board.last_move = (1, 2)
    board.forbidden_checked_pos = (3, 4)
    snapshot = board.grid.copy()
    assert rules.classify_grid(board.grid, *divmod(root, 15), player,
                               check_opening=False) == result
    assert board.last_move == (1, 2) and board.forbidden_checked_pos == (3, 4)
    assert np.array_equal(board.grid, snapshot)
    assert rules.flatten(board.grid) == cells
    nested = [cells[i:i + 15] for i in range(0, 225, 15)]
    assert rules.flatten(nested) == cells
    assert rules.classify(tuple(cells), root, player, check_opening=False) == result
    cells[root] = player
    original = cells[:]
    assert rules.analyze_placed(cells, root, player) == result
    summary = rules.four_summary_placed(cells, root, player)
    assert summary.fours == result.fours and summary.legal is None
    assert cells == original
    with pytest.raises(TimeoutError):
        rules.analyze_placed(cells, root, player, check=lambda: (_ for _ in ()).throw(TimeoutError()))
    assert cells == original


def test_four_summary_is_explicitly_not_a_double_three_verdict():
    cells = position([(7, 6), (7, 8), (6, 7), (8, 7)])
    rules = Rules(opening=False)
    summary = rules.four_summary(cells, flat((7, 7)), BLACK)
    assert isinstance(summary, FourSummary)
    assert summary.legal is None and summary.reason == "needs_three_check"
    assert not summary.win and summary.fours == ()
    assert not rules.is_legal(cells, flat((7, 7)), BLACK)
    assert rules.classify(cells, flat((7, 7)), BLACK).reason == "forbidden_double_three"
    white = rules.four_summary(cells, flat((7, 7)), WHITE)
    assert white.legal is True
    # No recursive solving is performed by four_summary, even for a black
    # candidate with apparent multiple threes.
    rules._solve_black = lambda *args: pytest.fail("four_summary must not recurse")
    assert rules.four_summary(cells, flat((7, 7)), BLACK).legal is None


def test_memo_is_bounded_exact_position_and_callback_is_polled_on_hits():
    cells = position([(7, 6), (7, 8), (6, 7), (8, 7)])
    root = flat((7, 7))
    rules = Rules(opening=False, memo_limit=2)
    assert not rules.is_legal(cells, root, BLACK)
    assert 0 < rules.memo_entries <= 2
    # The same black bitset but changed white bitset changes the real threes.
    blocked = cells[:]
    blocked[flat((7, 5))] = blocked[flat((7, 9))] = WHITE
    assert rules.is_legal(blocked, root, BLACK)
    assert not rules.is_legal(cells, root, BLACK)
    assert rules.memo_entries <= 2
    with pytest.raises(TimeoutError):
        rules.is_legal(cells, root, BLACK, check=lambda: (_ for _ in ()).throw(TimeoutError()))
    rules.clear_memo()
    assert rules.memo_entries == 0
    uncached = Rules(opening=False, memo_limit=0)
    assert not uncached.is_legal(cells, root, BLACK)
    assert uncached.memo_entries == 0


def test_mutable_flat_list_is_scanned_once_not_copied_at_each_child():
    class CountingList(list):
        iterations = 0

        def __iter__(self):
            self.iterations += 1
            return super().__iter__()

    plain, root, player = fixture(RULE_FIXTURES[-1])
    cells = CountingList(plain)
    result = Rules(opening=False).classify(cells, root, player)
    assert result.legal
    assert cells.iterations == 1  # one signature scan, then indexed make/unmake
    assert cells == plain


def test_explicit_recursion_driver_has_no_python_depth_cutoff(monkeypatch):
    # Mechanical stack test, NOT an additional independently adjudicated
    # Renju position. Real nested geometry is checked separately above.
    depth = 1100
    rules = Rules(size=34, opening=False)
    cells = [BLACK] + [0] * (34 * 34 - 1)
    ctx = _Context(cells, None)
    original = cells[:]

    def chain(context, cell):
        if cell < depth:
            child = yield cell + 1
            assert child.legal
        return _Verdict(True, False, "legal_nonterminal")

    monkeypatch.setattr(rules, "_judge_black", chain)
    assert rules._solve_black(ctx, 0).legal
    assert cells == original and ctx.black == 1 and not ctx.undo


@pytest.mark.parametrize("symmetry", range(8))
def test_edges_opponent_blocks_and_unrelated_old_formations(symmetry):
    rules = Rules(opening=False)
    # At the edge, even a contiguous three cannot gain a two-ended four.
    cells = position([transform(p, symmetry) for p in ((7, 0), (7, 2))])
    root = flat(transform((7, 1), symmetry))
    assert not rules.classify(cells, root, BLACK).threes
    # Blocking one endpoint of a unique broken-three extension destroys it.
    cells = position([transform(p, symmetry) for p in ((7, 5), (7, 8))],
                     [transform((7, 9), symmetry)])
    root = flat(transform((7, 7), symmetry))
    assert not rules.classify(cells, root, BLACK).threes
    # A pre-existing remote four is not created by an unrelated placement.
    cells = position([transform((2, c), symmetry) for c in (3, 4, 5, 6)])
    result = rules.classify(cells, root, BLACK)
    assert result.legal and not result.fours and not result.threes
    # An overline-poisoned exact-five completion is not a black four.
    # Existing stones c2,c4,c5,c7; root c6 nominally has four c4..7,
    # but left fill c3 would make six, while c8 really makes five c4..8.
    cells = position([transform((7, c), symmetry) for c in (2, 4, 5, 7)])
    root = flat(transform((7, 6), symmetry))
    result = rules.classify(cells, root, BLACK)
    assert len(result.fours) == 1
    assert result.fours[0].completions == ids([(7, 8)], symmetry)


def test_white_overline_threat_and_three_data_are_unrestricted():
    rules = Rules(opening=False)
    cells = position(white=[(7, 2), (7, 3), (7, 4), (7, 7)])
    result = rules.classify(cells, flat((7, 6)), WHITE)
    completions = {cell for four in result.fours for cell in four.completions}
    assert flat((7, 5)) in completions  # this is a white six, not black five
    cells[flat((7, 6))] = WHITE
    assert rules.classify(cells, flat((7, 5)), WHITE).reason == "win_overline"
    cross = position(white=[(7, 6), (7, 8), (6, 7), (8, 7)])
    root = rules.classify(cross, flat((7, 7)), WHITE)
    assert root.legal and not root.win and len(root.threes) == 2
    # Cheap white/custom legality does not even scan a position signature.
    class NoScanList(list):
        def __iter__(self):
            pytest.fail("white/custom quick legality must not scan the board")
    assert rules.is_legal(NoScanList([0] * 225), flat((7, 7)), WHITE)
    assert Rules(win_length=4, opening=False).is_legal(NoScanList([0] * 225), 0, BLACK)


def test_result_and_nested_formation_values_are_immutable():
    cells, root, player = fixture(RULE_FIXTURES[6])
    result = Rules(opening=False).classify(cells, root, player)
    assert isinstance(result, MoveResult)
    assert isinstance(result.threes[0].witnesses[0], ThreeWitness)
    hash(result)
    with pytest.raises(FrozenInstanceError):
        result.legal = False
    with pytest.raises(FrozenInstanceError):
        result.threes[0].witnesses[0].extension = 0


@pytest.mark.parametrize("size", (3, 4, 5, 6, 7, 9, 15, 16, 19))
@pytest.mark.parametrize("target", (3, 4, 5, 6, 7))
def test_simplified_opening_custom_configuration_matrix(size, target):
    if size < target:
        with pytest.raises(ValueError):
            Rules(size, target)
        return
    rules = Rules(size, target)
    no_opening = Rules(size, target, opening=False)
    center = size // 2
    active = size >= 5 and size % 2 == 1
    assert rules.opening_policy == ("simplified-center-opening" if active else "none")
    cells = [0] * (size * size)
    for move_count in (0, 1, 2, 3):
        for row in range(size):
            for col in range(size):
                index = row * size + col
                expected = (not active or move_count >= 3 or
                            (move_count == 0 and (row, col) == (center, center)) or
                            (move_count == 1 and (row, col) in ((center - 1, center),
                                                              (center - 1, center + 1))) or
                            (move_count == 2 and abs(row - center) <= 2 and abs(col - center) <= 2))
                assert rules.opening_allows(index, move_count) == expected
        # Probe representative restrictions through all public pre-move paths.
        for index in {0, center * size + center, (center - 1) * size + center}:
            expected = rules.opening_allows(index, move_count)
            for player in (BLACK, WHITE):
                assert rules.is_legal(cells, index, player, move_count) == expected
                assert rules.classify(cells, index, player, move_count).legal == expected
                assert no_opening.is_legal(cells, index, player, move_count)
                assert rules.is_legal(cells, index, player, move_count, check_opening=False)


@pytest.mark.parametrize("target", (3, 4, 6, 7))
@pytest.mark.parametrize("player", (BLACK, WHITE))
def test_nonfive_custom_is_symmetric_freestyle_without_black_fouls(target, player):
    rules = Rules(size=15, win_length=target, opening=False)
    stones = [(7, col) for col in range(2, 2 + target)]
    cells = position(stones if player == BLACK else (), stones if player == WHITE else ())
    result = rules.classify(cells, flat((7, 2 + target)), player)
    assert result.legal and result.win and result.reason == "win_connect_n"
    assert not result.fours and not result.threes
    assert rules.ruleset == f"gomoku-custom-freestyle-connect-{target}"
    # Apparent Renju double-three never fouls when target != 5.
    cells = position([(7, 6), (7, 8), (6, 7), (8, 7)])
    assert rules.is_legal(cells, flat((7, 7)), BLACK)


def test_target_five_other_sizes_explicitly_nonofficial_but_same_core():
    for size in (9, 16, 19):
        rules = Rules(size, 5, opening=False)
        assert "nonofficial" in rules.ruleset
        cells = position([(3, col) for col in (1, 2, 3, 4, 6)], size=size)
        result = rules.classify(cells, flat((3, 5), size), BLACK)
        assert result.reason == "forbidden_overline"
    assert Rules().ruleset == "renju-rif-core-15x15"


@pytest.mark.parametrize("method", ("classify", "is_legal", "four_summary"))
def test_invalid_inputs_safe_without_mutation(method):
    rules = Rules()
    cells = [0] * 225
    cells[1] = WHITE
    original = cells[:]
    for cell, player, reason in ((-1, BLACK, "out_of_bounds"), (225, BLACK, "out_of_bounds"),
                                 (1, BLACK, "occupied"), (0, 3, "invalid_player"),
                                 (0, BLACK, "opening")):
        result = getattr(rules, method)(cells, cell, player)
        if method == "is_legal":
            assert result is False
        else:
            assert not result.legal and result.reason == reason
        assert cells == original
    assert rules.classify_grid([[0] * 15 for _ in range(15)], 0, 15, BLACK).reason == "out_of_bounds"
    assert rules.analyze_placed(cells, 0, BLACK).reason == "not_player_stone"
    with pytest.raises(ValueError):
        rules.classify(cells[:-1], 0, BLACK)
    bad = original[:]
    bad[3] = 9
    with pytest.raises(ValueError):
        rules.classify(bad, flat((7, 7)), BLACK)
    with pytest.raises(ValueError):
        rules.flatten([[0]])
    assert cells == original
