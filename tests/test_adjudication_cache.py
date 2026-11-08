"""Exact-position acceptance boundary for detached complete rule results."""
import pytest
from board import Board,BLACK,WHITE


def key(board):
    return board.size,board.win_length,board.grid.tobytes()


def test_only_current_complete_adjudication_is_cached():
    board=Board()
    snapshot=key(board)
    assert board.accept_adjudication(7,7,BLACK,0,legal=True,expected_key=snapshot,ruleset=board.ruleset)
    board.validation_budget_sec=0
    assert board.is_valid_move(7,7,BLACK,0)
    # UNKNOWN is not a bool, so cannot poison the live cache.
    assert not board.accept_adjudication(7,7,BLACK,0,legal=None,expected_key=snapshot,ruleset=board.ruleset)
    board.grid[6,7]=WHITE
    assert not board.accept_adjudication(7,7,BLACK,0,legal=True,expected_key=snapshot,ruleset=board.ruleset)


def test_checked_move_handoff_is_strict_and_legal_only():
    board=Board()
    kwargs={'expected_key':key(board),'ruleset':board.ruleset,'opening_policy':board.opening_policy}
    assert not board.accept_checked_move(True,7,BLACK,0,**kwargs)
    assert not board.accept_checked_move(7,7,BLACK,False,**kwargs)
    assert not board.accept_checked_move(7,7,BLACK,0,**dict(kwargs,opening_policy='other'))
    assert board.accept_checked_move(7,7,BLACK,0,**kwargs)
    board.validation_budget_sec=0
    assert board.place_stone(7,7,BLACK,0)


def test_semantics_opening_and_bounds_are_rechecked():
    board=Board()
    for move in ((-1,0),(15,0),(0,0)):
        assert not board.accept_adjudication(*move,BLACK,0,legal=True,expected_key=key(board),ruleset=board.ruleset)
    assert not board.accept_adjudication(7,7,BLACK,0,legal=True,expected_key=key(board),ruleset='other')
    assert not board._legality_cache
