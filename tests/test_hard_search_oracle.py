"""Bounded independent depth-two search checks, not playing-strength evidence.

Only leaf static evaluation is shared with Hard. The reference has independent
geometry, legal empty-cell enumeration, and list make/unmake; no production
minimax, ordering, hashing, TT, win checker, or temporary-move helper is used.
"""
import random

import numpy as np
import pytest

from ai import AIHard
from board import BLACK, WHITE, Board


SEED = 20261108
DEPTH = 2


def _winners(cells, size):
    """Full-board connect-three geometry, independent of last_move."""
    result = set()
    for row in range(size):
        for col in range(size):
            player = cells[row * size + col]
            if not player:
                continue
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                if all(0 <= row + step * dr < size
                       and 0 <= col + step * dc < size
                       and cells[(row + step * dr) * size + col + step * dc] == player
                       for step in range(3)):
                    result.add(player)
    return result


def _empty(cells):
    # On these custom 3x3/4x4 boards there are no forbidden/opening restrictions.
    return [index for index, stone in enumerate(cells) if stone == 0]


def _all_empty_adjacent(cells, size):
    """Establish that radius-one production search is full width here."""
    occupied = [divmod(index, size) for index, stone in enumerate(cells) if stone]
    return all(any(max(abs(row - rr), abs(col - cc)) <= 1
                   for rr, cc in occupied)
               for row, col in (divmod(index, size) for index in _empty(cells)))


def _board(cells, size, last=None):
    board = Board(size=size, win_length=3)
    board.grid[:, :] = np.asarray(cells).reshape(size, size)
    board.last_move = divmod(last, size) if last is not None else None
    return board


def _sample_positions():
    """Fixed bounded rejection sample; rejects only terminal/sparse states.

    Every retained state has an alternating legal history with no preceding
    terminal state. Both colors and different occupancies appear on both sizes.
    There is no filtering on engine results, tactical category, or oracle value.
    """
    rng = random.Random(SEED)
    result = []
    for size in (3, 4):
        for parity in (0, 1):
            for sample in range(5):
                count = 4 + 2 * (sample % (2 if size == 3 else 3)) + parity
                for attempt in range(10000):
                    history = rng.sample(range(size * size), count)
                    cells = [0] * (size * size)
                    for ply, index in enumerate(history):
                        cells[index] = BLACK if ply % 2 == 0 else WHITE
                        if _winners(cells, size):
                            break
                    else:
                        if _all_empty_adjacent(cells, size):
                            result.append((size, tuple(history), tuple(cells)))
                            break
                else:
                    raise AssertionError('bounded nonterminal position sampler exhausted')
    return tuple(result)


POSITIONS = _sample_positions()
# Keep this sampled mismatch visible, not silently rejected by the sampler.
# Its tactical-selectivity explanation is checked independently below.
SELECTIVITY_HISTORY = (15, 7, 8, 5, 6)
EXACT_POSITIONS = tuple(case for case in POSITIONS if case[1] != SELECTIVITY_HISTORY)


def _winning_moves(cells, size, player):
    result = []
    for index in _empty(cells):
        old = cells[index]
        cells[index] = player
        try:
            if player in _winners(cells, size):
                result.append(divmod(index, size))
        finally:
            cells[index] = old
    return result


def _reference_value(cells, size, root, side, remaining, evaluator):
    """Unpruned full-width minimax; evaluator is shared only at static leaves."""
    winners = _winners(cells, size)
    assert len(winners) <= 1, 'reachable test tree cannot have two winners'
    if winners:
        return (evaluator.PATTERN_SCORES['p_win'] + remaining if root in winners
                else evaluator.PATTERN_SCORES['o_win'] - remaining)
    empty = _empty(cells)
    if not empty:
        return 0
    if remaining == 0:
        return evaluator._evaluate_board(_board(cells, size))
    values = []
    for index in empty:
        old = cells[index]
        cells[index] = side
        try:
            values.append(_reference_value(cells, size, root, 3 - side,
                                           remaining - 1, evaluator))
        finally:
            cells[index] = old
    return max(values) if side == root else min(values)


def _reference_scores(cells, size, root, evaluator):
    before = list(cells)
    result = {}
    for index in _empty(cells):
        old = cells[index]
        cells[index] = root
        try:
            result[divmod(index, size)] = _reference_value(
                cells, size, root, 3 - root, DEPTH - 1, evaluator)
        finally:
            cells[index] = old
    assert cells == before
    return result


@pytest.mark.parametrize('size,history,cells', EXACT_POSITIONS,
                         ids=[f'{size}x{size}-n{len(history)}-{i}'
                              for i, (size, history, _) in enumerate(EXACT_POSITIONS)])
@pytest.mark.parametrize('tt_capacity', [0, 128], ids=['no-tt', 'bounded-tt'])
def test_hard_selected_value_matches_independent_depth_two(size, history, cells,
                                                           tt_capacity):
    count = len(history)
    root = BLACK if count % 2 == 0 else WHITE
    assert not _winners(cells, size)
    assert _all_empty_adjacent(cells, size)
    # Adding a stone cannot uncover a cell from the occupied neighborhood.
    # Explicitly verify full width at the only recursive candidate layer too.
    for index in _empty(cells):
        child = list(cells)
        child[index] = root
        assert _all_empty_adjacent(child, size)

    evaluator = AIHard(root)
    expected = _reference_scores(list(cells), size, root, evaluator)
    board = _board(cells, size, history[-1])
    before = board.grid.copy(), board.last_move, board.forbidden_checked_pos
    engine = AIHard(root, depth=DEPTH, time_limit_sec=10, seed=SEED,
                    tt_capacity=tt_capacity)
    progress = []
    move = engine.find_move(board, count, progress_callback=progress.append)
    assert move in expected
    assert expected[move] == max(expected.values()), (
        {'size': size, 'history': history, 'root': root, 'move': move,
         'selected_value': expected[move], 'oracle_values': expected,
         'completed_depth': engine.completed_depth, 'progress': progress})
    assert engine.completed_depth == DEPTH or progress[-1]['phase'] == 'tactical'
    assert np.array_equal(board.grid, before[0])
    assert (board.last_move, board.forbidden_checked_pos) == before[1:]


@pytest.mark.parametrize('tt_capacity', [0, 128], ids=['no-tt', 'bounded-tt'])
def test_known_forced_reply_selectivity_differs_from_fullwidth_horizon(tt_capacity):
    """Keep the one sampled mismatch visible as a tactical limitation.

    Strict two-ply minimax may have the defender ignore a win-in-one threat,
    because that win happens on ply three. Hard instead forces one blocking
    reply, yet cannot distinguish a two-endpoint fork from a single threat.
    This is neither evidence of full-width equivalence nor a strength PASS.
    """
    size, history, cells = next(case for case in POSITIONS
                               if case[1] == SELECTIVITY_HISTORY)
    assert size == 4 and len(history) == 5
    assert not _winners(cells, size)
    assert _all_empty_adjacent(cells, size)
    root = WHITE
    evaluator = AIHard(root)
    expected = _reference_scores(list(cells), size, root, evaluator)
    assert max(expected, key=expected.get) == (2, 1)
    assert expected[(2, 1)] == -18813000
    assert expected[(2, 3)] == -19397000

    # Independently establish the policy's forced-block branches and values.
    # Every empty cell is legal on these custom boards; no Renju oracle needed.
    def forced_branch(root_move, reply, remaining_wins, forced_value):
        working = list(cells)
        working[root_move[0] * size + root_move[1]] = root
        assert not _winners(working, size)  # A threat, not a terminal root win.
        assert _winning_moves(working, size, BLACK) == []
        assert _winning_moves(working, size, root) == remaining_wins
        working[reply[0] * size + reply[1]] = BLACK
        assert not _winners(working, size)
        assert evaluator._evaluate_board(_board(working, size)) == forced_value
        return working

    # Production sees the single threat as better under its forced leaf score.
    single = forced_branch((2, 3), (0, 3), [(0, 3)], -962500)
    assert _winning_moves(single, size, root) == []
    fork = forced_branch((2, 1), (0, 1), [(0, 1), (3, 1)], -1392500)
    assert _winning_moves(fork, size, root) == [(3, 1)]

    board = _board(cells, size, history[-1])
    before = board.grid.copy(), board.last_move, board.forbidden_checked_pos
    engine = AIHard(root, depth=DEPTH, time_limit_sec=10, seed=SEED,
                    tt_capacity=tt_capacity)
    progress = []
    move = engine.find_move(board, len(history), progress_callback=progress.append)
    assert move == (2, 3)
    assert engine.completed_depth == DEPTH
    assert progress[-1]['score'] == -962500
    assert expected[move] < max(expected.values())
    assert np.array_equal(board.grid, before[0])
    assert (board.last_move, board.forbidden_checked_pos) == before[1:]


def test_sample_is_bounded_reachable_diverse_and_reproducible():
    assert len(POSITIONS) == 20
    assert len(EXACT_POSITIONS) == 19
    assert sum(history == SELECTIVITY_HISTORY for _, history, _ in POSITIONS) == 1
    assert POSITIONS == _sample_positions()
    assert {(size, len(history) % 2) for size, history, _ in POSITIONS} == {
        (3, 0), (3, 1), (4, 0), (4, 1)}
    assert len({(size, cells) for size, _, cells in POSITIONS}) == 20
    for size, history, expected in POSITIONS:
        cells = [0] * (size * size)
        for ply, index in enumerate(history):
            assert cells[index] == 0
            cells[index] = BLACK if ply % 2 == 0 else WHITE
            assert not _winners(cells, size)
        assert tuple(cells) == expected


def test_reference_terminal_priority_and_root_sign_without_static_eval():
    class NoStaticEvaluation(AIHard):
        def _evaluate_board(self, board):
            raise AssertionError('terminal/draw nodes must not use static evaluation')
    black_win = [BLACK, BLACK, BLACK, WHITE, WHITE, 0, 0, 0, 0]
    draw = [BLACK, WHITE, BLACK, BLACK, WHITE, WHITE, WHITE, BLACK, BLACK]
    for root in (BLACK, WHITE):
        evaluator = NoStaticEvaluation(root)
        value = _reference_value(black_win[:], 3, root, WHITE, 1, evaluator)
        assert value == (evaluator.PATTERN_SCORES['p_win'] + 1 if root == BLACK
                         else evaluator.PATTERN_SCORES['o_win'] - 1)
        assert _reference_value(draw[:], 3, root, WHITE, 0, evaluator) == 0
