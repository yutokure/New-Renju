import time
import random
import numpy as np
import pytest
from board import BLACK, WHITE, Board
from ai import AIHard, create_ai
from renju_rules import Rules
from very_hard import AIVeryHard, Position, MATE
from tests.positions import hard_cases, position


@pytest.mark.parametrize('kwargs', [{'player':0}, {'time_limit_sec':float('inf')},
                                    {'time_limit_sec':float('nan')}, {'max_depth':1.5},
                                    {'tt_capacity':-1}, {'candidate_limit':0},
                                    {'tactical_fraction':float('nan')}])
def test_invalid_configuration_rejected(kwargs):
    options = {'player':BLACK}
    options.update(kwargs)
    with pytest.raises(ValueError):
        AIVeryHard(**options)


def test_independent_factory():
    hard = create_ai('hard', BLACK)
    very = create_ai('very_hard', BLACK)
    assert isinstance(very, AIVeryHard) and not isinstance(very, AIHard)
    assert hard.max_depth == 2 and hard.time_limit == 1.5
    assert very.time_limit == 5.0


@pytest.mark.parametrize('target', range(3,8))
def test_incremental_state_matches_rebuild_and_unmakes(target):
    rules = Rules(9, target)
    cells = [0]*81
    pos = Position(cells, 9, target)
    initial = (pos.total, pos.hash)
    rng = random.Random(73)
    moves = rng.sample(range(81), 20)
    for j, p in enumerate(moves):
        player = 1+j%2
        pos.make(p, player)
        rebuilt = Position(pos.cells, 9, target)
        assert pos.total == rebuilt.total
        assert pos.hash == rebuilt.hash
        assert pos.black_counts == rebuilt.black_counts
        assert pos.white_counts == rebuilt.white_counts
        assert pos.threat_windows == rebuilt.threat_windows
    for j in range(19,-1,-1):
        pos.unmake(moves[j], 1+j%2)
    assert (pos.total, pos.hash) == initial
    assert pos.cells == cells and not pos.occupied


@pytest.mark.parametrize('target', range(3,8))
@pytest.mark.parametrize('player', [BLACK, WHITE])
def test_immediate_wins_and_blocks_all_targets(target, player):
    board = position(size=11, win_length=target, black=[(5,0)] if player == WHITE else [(5,c) for c in range(1,target)],
                     white=[(5,c) for c in range(1,target)] if player == WHITE else [(5,0)], last=(5,0))
    very = AIVeryHard(player, time_limit_sec=.2, tactical_fraction=0)
    assert very.find_move(board, 20) == (5,target)
    assert very.proof_status == 'PROVEN_WIN'
    defender = AIVeryHard(3-player, time_limit_sec=.2, tactical_fraction=0)
    assert defender.find_move(board, 20) == (5,target)


def test_deadline_legal_nonmutating_general_search():
    _, board, player, count, _ = hard_cases()[-1]
    grid, last = board.grid.copy(), board.last_move
    very = AIVeryHard(player, time_limit_sec=.1, tactical_fraction=0)
    started = time.perf_counter()
    move = very.find_move(board, count)
    elapsed = time.perf_counter()-started
    assert elapsed < .5
    assert board.is_valid_move(*move, player, count)
    assert np.array_equal(grid, board.grid) and board.last_move == last
    assert very.proof_status == 'UNKNOWN'
    assert very.nodes > 0


def test_zero_time_legal_fallback_and_cancel():
    from threading import Event
    board = Board()
    event = Event()
    event.set()
    very = AIVeryHard(BLACK, time_limit_sec=0)
    assert very.find_move(board, 0, cancel_event=event) == (7,7)
    assert very.completed_depth == 0 and very.proof_status == 'UNKNOWN'


def test_position_scope_unwinds_exception():
    pos = Position([0]*225, 15, 5)
    with pytest.raises(RuntimeError):
        with pos.played(112, BLACK):
            with pos.played(113, WHITE):
                raise RuntimeError('fault')
    assert pos.hash == 0 and pos.total == 0 and not pos.occupied


@pytest.mark.parametrize('last', [None, (0,0)])
@pytest.mark.parametrize('winner', [BLACK, WHITE])
def test_terminal_roots_never_play_beyond_game(last, winner):
    board = position(black=[(7,c) for c in range(3,8)] if winner == BLACK else [],
                     white=[(7,c) for c in range(3,8)] if winner == WHITE else [], last=last)
    very = AIVeryHard(BLACK, time_limit_sec=.1, tactical_fraction=0)
    very.principal_variation = (112, 113)
    assert very.find_move(board, 10) is None
    assert very.principal_variation == ()
    assert very.proof_status == ('PROVEN_WIN' if winner == BLACK else 'PROVEN_LOSS')


def test_contradictory_terminal_root_unknown():
    board = position(black=[(7,c) for c in range(3,8)], white=[(2,c) for c in range(3,8)])
    very = AIVeryHard(BLACK)
    assert very.find_move(board, 10) is None
    assert very.proof_status == 'UNKNOWN'


def test_black_overline_not_immediate_win():
    cells = [0]*225
    for c in (3,4,5,6,8):
        cells[7*15+c] = BLACK
    pos = Position(cells, 15, 5)
    assert 7*15+7 not in pos.immediate_wins(BLACK, Rules(), 20)
