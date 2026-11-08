"""Baseline tactical cases and corrected Phase A terminal/probe regressions."""
import math
import numpy as np
import pytest
from ai import AIHard, create_ai
from board import BLACK, WHITE
from tests.positions import hard_cases, position


@pytest.mark.parametrize('name,board,player,count,expected', hard_cases())
def test_legal_nonmutating_moves(name, board, player, count, expected):
    original, last = board.grid.copy(), board.last_move
    move = AIHard(player, depth=2, time_limit_sec=0.15).find_move(board, count)
    assert move is not None and board.is_valid_move(*move, player, count)
    assert np.array_equal(original, board.grid)
    assert board.last_move == last
    if expected:
        assert move in expected


def test_factory_lightweight_configuration():
    ai = create_ai('hard', BLACK)
    assert ai.max_depth == 2
    assert ai.time_limit == 1.5


@pytest.mark.parametrize('player', [BLACK, WHITE])
def test_root_win_is_positive_at_minimizing_node(player):
    board = position(black=[(7,c) for c in range(3,8)], last=(7,7))
    if player == WHITE:
        board.grid[board.grid == BLACK] = WHITE
    ai = AIHard(player)
    assert ai._minimax(board, 1, -math.inf, math.inf, False, 10, ai._calculate_board_hash(board)) > 0


def test_recursive_immediate_win_probe(monkeypatch):
    board = position(black=[(7,c) for c in range(4,8)], white=[(7,3)], last=(7,3))
    ai = AIHard(BLACK)
    original = board.check_win
    def checked(player):
        if board.grid[7,8] == BLACK and player == BLACK:
            assert board.last_move == (7,8)
        return original(player)
    monkeypatch.setattr(board, 'check_win', checked)
    ai._minimax(board, 1, -math.inf, math.inf, True, 8, ai._calculate_board_hash(board))


def test_major_line_scores():
    ai = AIHard(BLACK)
    assert ai._evaluate_line([0,1,1,1,1,0]) == ai.PATTERN_SCORES['p_open_four']
    assert ai._evaluate_line([0,2,2,2,0]) == ai.PATTERN_SCORES['o_open_three']
