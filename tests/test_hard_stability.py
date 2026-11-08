"""Fast deterministic regressions, not a performance/playing-strength benchmark."""
from collections import Counter
import math
import random
from threading import Event

import numpy as np
import pytest

import ai as ai_module
from ai import AIEasy, AIHard, AINormal, _SearchInterrupted, _evaluate_line_cached
from board import BLACK, WHITE, EMPTY, Board
from tests.positions import position


def snapshot(board):
    return board.grid.copy(), board.last_move, board.forbidden_checked_pos


def assert_restored(board, state):
    grid, last, marker = state
    assert np.array_equal(board.grid, grid)
    assert board.last_move == last
    assert board.forbidden_checked_pos == marker


@pytest.mark.parametrize('root', [BLACK, WHITE])
@pytest.mark.parametrize('maximizing', [False, True])
def test_terminal_scores_always_root_relative(root, maximizing):
    board = position(size=7, black=[(3, c) for c in range(1, 6)], last=(3, 5))
    hard = AIHard(root)
    score = hard._minimax(board, 1, -math.inf, math.inf, maximizing, 10,
                          hard._calculate_board_hash(board))
    assert (score > 0) == (root == BLACK)


def test_temporary_move_nested_occupied_and_exception():
    board = position(black=[(7, 7)], last=(7, 7))
    board.forbidden_checked_pos = (1, 2)
    state = snapshot(board)
    with pytest.raises(RuntimeError, match='injected'):
        with board.temporary_move(7, 7, WHITE):
            assert board.grid[7, 7] == WHITE
            with board.temporary_move(7, 8, BLACK):
                board.forbidden_checked_pos = (2, 3)
                assert board.last_move == (7, 8)
            assert board.last_move == (7, 7)
            assert board.forbidden_checked_pos == (1, 2)
            raise RuntimeError('injected')
    assert_restored(board, state)
    with pytest.raises(IndexError):
        with board.temporary_move(-1, 0, BLACK):
            pass
    assert_restored(board, state)


@pytest.mark.parametrize('method', ['is_forbidden', '_is_forbidden'])
@pytest.mark.parametrize('cell', [(7, 7), (7, 8), (-1, 0), (15, 0)])
def test_forbidden_queries_are_safe_nonmutating(method, cell):
    board = position(black=[(7, 7)], white=[(7, 8)], last=(7, 7))
    board.forbidden_checked_pos = (3, 4)
    state = snapshot(board)
    check = getattr(board, method)
    args = (*cell, BLACK) if method.startswith('_') else cell
    assert not check(*args)
    assert_restored(board, state)


def test_forbidden_exception_restores_board(monkeypatch):
    board = position(black=[(7, 7)], last=(7, 7))
    board.forbidden_checked_pos = (1, 2)
    state = snapshot(board)
    def fail(*args, **kwargs):
        raise RuntimeError('line details')
    monkeypatch.setattr(board._rules, 'is_legal', fail)
    with pytest.raises(RuntimeError, match='line details'):
        board.is_forbidden(7, 8)
    assert_restored(board, state)


@pytest.mark.parametrize('exact_horizontal', [False, True])
def test_exact_five_priority_not_direction_order(exact_horizontal):
    # Placing the intersection creates an exact five and an overline.
    five = [(7, c) for c in (5, 6, 8, 9)]
    six = [(r, 7) for r in (4, 5, 6, 8, 9)]
    stones = five + six
    if not exact_horizontal:
        stones = [(c, r) for r, c in stones]
    board = position(black=stones, last=stones[-1])
    state = snapshot(board)
    assert not board.is_forbidden(7, 7)
    assert board.is_valid_move(7, 7, BLACK, 9)
    assert_restored(board, state)
    with board.temporary_move(7, 7, BLACK):
        assert board.check_win(BLACK)[0]
    assert_restored(board, state)


@pytest.mark.parametrize('player', [BLACK, WHITE])
def test_five_overline_wins_only_for_white(player):
    board = Board(9, 5)
    board.grid[4, 1:7] = player
    board.last_move = (4, 6)
    assert board.check_win(player)[0] == (player == WHITE)
    hard = AIHard(player)
    value = hard._evaluate_line([player] * 6)
    assert (value == hard.PATTERN_SCORES['p_win']) == (player == WHITE)


@pytest.mark.parametrize('length', [3, 4, 6, 7])
@pytest.mark.parametrize('player', [BLACK, WHITE])
def test_custom_gomoku_at_least_n_no_forbidden(length, player):
    board = Board(11, length)
    board.grid[5, 1:length + 1] = player
    state = snapshot(board)
    # Black used to reject custom N+1 as an overline.
    assert not board.is_forbidden(5, length + 1)
    assert board.is_valid_move(5, length + 1, player, 20)
    with board.temporary_move(5, length + 1, player):
        assert board.check_win(player)[0]
    assert_restored(board, state)
    # No double-three/four restrictions in custom Gomoku either.
    board = position(size=11, win_length=length,
                     black=[(5, 4), (5, 6), (4, 5), (6, 5)])
    assert not board.is_forbidden(5, 5)
    assert board.is_valid_move(5, 5, BLACK, 20)


@pytest.mark.parametrize('length', range(3, 8))
@pytest.mark.parametrize('ai_class', [AIHard, AINormal])
def test_all_supported_lengths_immediate_win_and_eval(length, ai_class):
    board = Board(11, length)
    board.grid[5, 1:length] = WHITE
    board.grid[5, 0] = BLACK
    board.last_move = (5, 0)
    state = snapshot(board)
    hard = AIHard(WHITE)
    assert hard._evaluate_line([WHITE] * length, length, board.size) == hard.PATTERN_SCORES['p_win']
    assert ai_class(WHITE).find_move(board, 20) == (5, length)
    assert_restored(board, state)


@pytest.mark.parametrize('length', range(3, 8))
def test_simplified_opening_preserved_for_custom_lengths(length):
    board = Board(11, length)
    assert board.is_valid_move(5, 5, BLACK, 0)
    assert not board.is_valid_move(0, 0, BLACK, 0)
    assert board.is_valid_move(4, 5, WHITE, 1)
    assert board.is_valid_move(4, 6, WHITE, 1)
    assert not board.is_valid_move(5, 6, WHITE, 1)
    assert not board.is_valid_move(0, 0, BLACK, 2)


@pytest.mark.parametrize('ai_class', [AIEasy, AINormal])
def test_easy_normal_opening_legal_nonmutating_smoke(ai_class, capsys):
    board = Board(7, 5)
    board.forbidden_checked_pos = (0, 0)
    state = snapshot(board)
    assert ai_class(BLACK).find_move(board, 0) == (3, 3)
    assert_restored(board, state)
    assert capsys.readouterr().out == ''


@pytest.mark.parametrize('cancelled', [False, True])
def test_safe_legal_fallback_even_before_search(cancelled):
    board = Board(7, 5)
    event = Event()
    if cancelled:
        event.set()
    seen = []
    hard = AIHard(BLACK, time_limit_sec=0 if not cancelled else 10)
    state = snapshot(board)
    assert hard.find_move(board, 0, cancel_event=event, progress_callback=seen.append) == (3, 3)
    assert hard.completed_depth == 0
    assert len(seen) == 1 and seen[0]['phase'] == 'fallback'
    assert seen[0]['move'] == (3, 3)
    assert_restored(board, state)


def test_full_board_returns_none():
    board = Board(5, 5)
    board.grid[:] = WHITE
    assert AIHard(BLACK, time_limit_sec=0).find_move(board, 20) is None


@pytest.mark.parametrize('stage', ['precheck', 'recursive'])
def test_find_move_exception_restores_state(monkeypatch, stage):
    board = position(size=7, black=[(3, 3)], white=[(2, 3)], last=(2, 3))
    board.forbidden_checked_pos = (0, 0)
    state = snapshot(board)
    hard = AIHard(BLACK, depth=2, time_limit_sec=10)
    def fail(*args):
        raise RuntimeError('injected')
    if stage == 'precheck':
        monkeypatch.setattr(board, 'check_win', fail)
    else:
        monkeypatch.setattr(hard, '_evaluate_board', fail)
    with pytest.raises(RuntimeError, match='injected'):
        hard.find_move(board, 4)
    assert_restored(board, state)
    assert hard._deadline is None


def test_recursive_deadline_checks_and_unwinds(monkeypatch):
    board = position(size=7, black=[(3, 3)], white=[(2, 3)], last=(2, 3))
    state = snapshot(board)
    hard = AIHard(BLACK)
    clock = [0]
    monkeypatch.setattr(ai_module.time, 'perf_counter', lambda: clock[0])
    hard._deadline = 1
    original = hard._get_all_lines
    def slow_lines(board):
        for line in original(board):
            clock[0] += 0.5
            yield line
    monkeypatch.setattr(hard, '_get_all_lines', slow_lines)
    with pytest.raises(_SearchInterrupted):
        hard._minimax(board, 2, -math.inf, math.inf, True, 4,
                      hard._calculate_board_hash(board))
    assert hard.nodes >= 3  # Interrupted below the root, inside leaf evaluation.
    assert not hard.transposition_table  # No incomplete subtree stored.
    assert_restored(board, state)


def test_completed_depth_only_on_partial_iteration(monkeypatch):
    board = position(size=7, black=[(3, 3)], white=[(2, 3)], last=(2, 3))
    state = snapshot(board)
    hard = AIHard(BLACK, depth=2, time_limit_sec=10)
    event = Event()
    seen = []
    moves = [(3, 4), (4, 3)]
    monkeypatch.setattr(hard, '_get_ordered_adjacent_moves', lambda *args: moves)
    def search(board, depth, *args):
        if depth == 1:
            event.set()  # Depth 2 would favor first, but it never completes.
            return 999
        return 1 if board.last_move == moves[0] else 2
    monkeypatch.setattr(hard, '_minimax', search)
    result = hard.find_move(board, 4, cancel_event=event, progress_callback=seen.append)
    assert result == moves[1]
    assert hard.completed_depth == 1
    assert [item['phase'] for item in seen] == ['fallback', 'search']
    assert seen[-1]['completed_depth'] == 1
    assert_restored(board, state)


def test_real_recursive_cancellation_unwinds(monkeypatch):
    board = position(size=7, black=[(3, 3)], white=[(2, 3)], last=(2, 3))
    state = snapshot(board)
    event = Event()
    hard = AIHard(BLACK, depth=2, time_limit_sec=10)
    original = hard._evaluate_board
    def cancel(board):
        event.set()
        return original(board)
    monkeypatch.setattr(hard, '_evaluate_board', cancel)
    seen = []
    result = hard.find_move(board, 4, cancel_event=event, progress_callback=seen.append)
    assert result == seen[0]['move']
    assert hard.nodes > 0 and hard.completed_depth == 0
    assert_restored(board, state)


def test_candidates_deduplicate_before_legality(monkeypatch):
    board = position(size=7, black=[(3, 3), (3, 4)], last=(3, 4))
    hard = AIHard(WHITE)
    calls = Counter()
    original = board.is_valid_move
    def checked(r, c, player, count):
        calls[(r, c)] += 1
        return original(r, c, player, count)
    monkeypatch.setattr(board, 'is_valid_move', checked)
    moves = hard._get_ordered_adjacent_moves(board, WHITE, 4)
    assert moves and all(count == 1 for count in calls.values())
    assert len(moves) == len(set(moves))


def test_reproducible_hash_search_and_no_global_rng_consumption():
    board = position(size=7, black=[(3, 3)], white=[(2, 3)], last=(2, 3))
    np_state, py_state = np.random.get_state(), random.getstate()
    first = AIHard(BLACK, depth=1, time_limit_sec=10, seed=42)
    second = AIHard(BLACK, depth=1, time_limit_sec=10, seed=42)
    assert np.array_equal(first.zobrist_table, second.zobrist_table)
    assert first.find_move(board, 4) == second.find_move(board, 4)
    assert first.completed_depth == second.completed_depth == 1
    assert first.nodes == second.nodes
    after = np.random.get_state()
    assert after[0] == np_state[0]
    assert np.array_equal(after[1], np_state[1])
    assert after[2:] == np_state[2:]
    assert random.getstate() == py_state
    assert AIHard(BLACK, seed=43)._calculate_board_hash(board) != first._calculate_board_hash(board)


def test_tt_key_isolates_turn_opening_rules_last_move_and_root():
    board = position(size=7, black=[(3, 3)], last=(3, 3))
    hard = AIHard(BLACK)
    h = hard._calculate_board_hash(board)
    keys = {hard._tt_key(board, True, 4, h), hard._tt_key(board, False, 4, h),
            hard._tt_key(board, True, 1, h), AIHard(WHITE)._tt_key(board, True, 4, h)}
    board.last_move = None
    keys.add(hard._tt_key(board, True, 4, h))
    board.last_move = (3, 3)
    board.win_length = 4
    keys.add(hard._tt_key(board, True, 4, h))
    assert len(keys) == 6


def test_tt_capacity_and_real_search_bound():
    hard = AIHard(BLACK, tt_capacity=2)
    for i in range(10):
        hard._store_tt(('key', i), i, 1, 'exact')
    assert len(hard.transposition_table) == 2
    assert ('key', 0) not in hard.transposition_table
    board = position(size=7, black=[(3, 3)], white=[(2, 3)], last=(2, 3))
    hard.transposition_table.clear()
    hard._minimax(board, 2, -math.inf, math.inf, True, 4,
                  hard._calculate_board_hash(board))
    assert len(hard.transposition_table) <= 2
    assert all(len(key) == 8 for key in hard.transposition_table)


def test_tt_not_reused_across_remaining_depth(monkeypatch):
    board = position(size=7, black=[(3, 3)], last=(3, 3))
    hard = AIHard(WHITE)
    h = hard._calculate_board_hash(board)
    key = hard._tt_key(board, True, 4, h)
    hard._store_tt(key, 123456789, 2, 'exact')
    monkeypatch.setattr(hard, '_get_ordered_adjacent_moves', lambda *args: [])
    assert hard._minimax(board, 1, -math.inf, math.inf, True, 4, h) != 123456789


def test_line_cache_context_and_capacity():
    _evaluate_line_cached.cache_clear()
    black, white = AIHard(BLACK), AIHard(WHITE)
    line = [EMPTY, BLACK, BLACK, BLACK, EMPTY]
    assert black._evaluate_line(line, 5, 15) == black.PATTERN_SCORES['p_open_three']
    hits = _evaluate_line_cached.cache_info().hits
    black._evaluate_line(line, 5, 15)
    assert _evaluate_line_cached.cache_info().hits == hits + 1
    assert white._evaluate_line(line, 5, 15) == white.PATTERN_SCORES['o_open_three']
    assert black._evaluate_line([BLACK] * 4, 4, 15) == black.PATTERN_SCORES['p_win']
    assert black._evaluate_line([BLACK] * 4, 5, 15) != black.PATTERN_SCORES['p_win']
    custom = Board(7, 4)
    custom.grid[3, 1:5] = BLACK
    assert black._evaluate_board(custom) == black.PATTERN_SCORES['p_win']
    assert _evaluate_line_cached.cache_info().maxsize == 65536


@pytest.mark.parametrize('ai_class', [AIHard, AINormal])
def test_illegal_opponent_overline_not_a_threat(ai_class, monkeypatch):
    board = position(size=9, black=[(4, c) for c in (1, 2, 3, 5, 6)],
                     white=[(3, 3)], last=(3, 3))
    original = board.check_win
    def checked(player):
        # A forbidden black overline completion must never be probed as a win.
        assert not (player == BLACK and board.last_move == (4, 4)
                    and board.grid[4, 4] == BLACK)
        return original(player)
    monkeypatch.setattr(board, 'check_win', checked)
    instance = ai_class(WHITE)
    if ai_class is AIHard:
        instance.max_depth = 0
    assert instance.find_move(board, 12) is not None
