"""Integration regressions identified while reviewing the stability patch."""
import math
import numpy as np
from ai import AIHard
from board import BLACK, WHITE
from tests.positions import position


def test_timeout_fallback_is_local_not_upper_left_corner():
    board = position(black=[(7,7)], white=[(6,7)], last=(6,7))
    hard = AIHard(BLACK, time_limit_sec=0)
    move = hard.find_move(board, 4)
    assert max(abs(move[0]-7), abs(move[1]-7)) <= 1
    assert board.is_valid_move(*move, BLACK, 4)


def test_nonterminal_estimate_cannot_outrank_terminal_loss():
    board = position(size=19, white=[(r,c) for r in (1,4,7,10,13,16) for c in range(7,11)], last=(16,10))
    hard = AIHard(BLACK)
    score = hard._evaluate_board(board)
    assert hard.PATTERN_SCORES['o_win'] < score < hard.PATTERN_SCORES['p_win']


def test_loaded_json_last_move_can_be_used_in_tt():
    board = position(size=7, black=[(3,3)], white=[(2,3)], last=[2,3])
    hard = AIHard(BLACK)
    key = hard._tt_key(board, True, 4, hard._calculate_board_hash(board))
    assert isinstance(hash(key), int)
    assert math.isfinite(hard._minimax(board, 1, -math.inf, math.inf, True, 4, hard._calculate_board_hash(board)))
