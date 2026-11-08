"""Exact-candidate deferred rule adjudication; no heavy search benchmarks."""
import copy
import json
import os
from pathlib import Path
import time

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
import pygame
import pytest

import ai_async
from ai_async import AsyncAI, validation_context
from board import Board, BLACK, RuleValidationTimeout
from constants import PLAYER_HUMAN, PLAYER_AI, STATE_MENU
from settings import Settings


def packet(task, state='legal'):
    return {'token': task.token, 'kind': 'validate', 'candidate': list(task.candidate),
            'validation_context': copy.deepcopy(task.validation_context), 'move': None,
            'done': True, 'adjudication': state, 'validation_complete': state != 'unknown',
            'verdict': None if state == 'unknown' else
                {'legal': state == 'legal', 'win': False,
                 'reason': 'legal_nonterminal' if state == 'legal' else 'forbidden_double_three'}}


class FakeProcess:
    def __init__(self):
        self.returncode = None
    def poll(self):
        return self.returncode
    def terminate(self):
        self.returncode = -1
    kill = terminate
    def wait(self, timeout=None):
        self.returncode = -1
        return self.returncode


@pytest.fixture
def mocked_adapter(monkeypatch):
    import worker_limits
    class Limit:
        metadata = {'enforced': True}
        def __init__(self, *args):
            pass
        def close(self):
            pass
    monkeypatch.setattr(ai_async.subprocess, 'Popen', lambda *a, **k: FakeProcess())
    monkeypatch.setattr(worker_limits, 'ProcessBudget', Limit)
    runner = AsyncAI()
    yield runner
    runner.close()


def test_ai_ui_timeout_preserves_exact_candidate(mocked_adapter):
    board = Board()
    board.validation_budget_sec = 0
    runner = mocked_adapter
    runner.start(board, BLACK, 0, 'hard')
    task = runner.task
    (Path(task.directory.name) / 'result.json').write_text(json.dumps(
        {'token': task.token, 'move': [7, 7], 'done': True}))
    result = runner.poll(board, BLACK, 0)
    assert result['move'] is None and result['validation_pending_move'] == (7, 7)
    assert result['validation_required'] is True
    assert not result.get('error')
    assert board._legality_cache == {} and not board.grid.any()


def test_validate_poll_never_runs_recursive_main_thread_query(mocked_adapter, monkeypatch):
    board = Board()
    runner = mocked_adapter
    runner.start(board, BLACK, 0, 'hard', kind='validate', candidate=(7, 7))
    task = runner.task
    (Path(task.directory.name) / 'result.json').write_text(json.dumps(packet(task)))
    monkeypatch.setattr(board, 'is_valid_move', lambda *a: pytest.fail('must not re-adjudicate in poll'))
    answer = runner.poll(board, BLACK, 0)
    assert answer['adjudication'] == 'legal' and answer['validation_complete']
    assert board._legality_cache == {}  # Game owns final exact-key cache handoff.


@pytest.mark.parametrize('mutation', ['candidate_bool', 'context_bool', 'wrong_candidate',
                                     'wrong_kind', 'wrong_snapshot', 'contradiction',
                                     'missing_verdict', 'partial_legal', 'wrong_token'])
def test_malformed_or_mismatched_verdict_cannot_be_accepted(mocked_adapter, mutation):
    board = Board()
    # Candidate row 1 lets bool True expose Python True == 1 edge case.
    runner = mocked_adapter
    runner.start(board, BLACK, 4, 'hard', budget=0, kind='validate', candidate=(1, 7))
    task = runner.task
    task.started -= 10
    response = packet(task)
    if mutation == 'candidate_bool': response['candidate'][0] = True
    if mutation == 'context_bool': response['validation_context']['player'] = True
    if mutation == 'wrong_candidate': response['candidate'] = [2, 7]
    if mutation == 'wrong_kind': response['kind'] = 'move'
    if mutation == 'wrong_snapshot': response['validation_context']['snapshot_id'] = 'wrong'
    if mutation == 'contradiction': response['verdict']['legal'] = False
    if mutation == 'missing_verdict': response.pop('verdict')
    if mutation == 'partial_legal': response['validation_complete'] = False
    if mutation == 'wrong_token': response['token'] = 'unrelated-task'
    (Path(task.directory.name) / 'result.json').write_text(json.dumps(response))
    answer = runner.poll(board, BLACK, 4)
    assert answer['adjudication'] == 'unknown'
    assert answer['validation_complete'] is False
    assert answer.get('move') is None and not board._legality_cache


def test_validation_position_change_cancels_response(mocked_adapter):
    board = Board()
    runner = mocked_adapter
    runner.start(board, BLACK, 0, 'hard', kind='validate', candidate=(7, 7))
    board.grid[0, 0] = 2
    assert runner.poll(board, BLACK, 0) is None
    assert not runner.busy and not board._legality_cache


def test_validation_semantic_metadata_change_cancels_response(mocked_adapter):
    board = Board()
    runner = mocked_adapter
    runner.start(board, BLACK, 0, 'hard', kind='validate', candidate=(7, 7))
    board.opening_policy = 'unexpected'
    assert runner.poll(board, BLACK, 0) is None
    assert not runner.busy


class FakeRunner:
    def __init__(self):
        self.busy = False
        self.task = None
        self.last_info = {}
        self.calls = []
        self.answer = None
    def start(self, board, player, count, difficulty, **kwargs):
        self.calls.append(kwargs)
        self.busy = True
        self.task = type('Task', (), {'token': 'validation-test', 'started': time.perf_counter(),
                    'candidate': kwargs.get('candidate'),
                    'validation_context': validation_context(board, player, count, kwargs['candidate'])
                    if kwargs.get('kind') == 'validate' else None})()
        return self.task.token
    def poll(self, *args):
        if self.answer is not None:
            answer, self.answer = self.answer, None
            self.busy = False
            return answer
        return None
    def cancel(self):
        self.busy = False
        self.task = None
    close = cancel
    def reap(self):
        pass


@pytest.fixture
def game(monkeypatch):
    import game as game_module
    monkeypatch.setattr(game_module, 'AsyncAI', FakeRunner)
    # Schema validation remains the actual adapter implementation even when
    # worker execution itself is mocked for a responsive Game pipeline.
    FakeRunner._validation_packet_valid = staticmethod(AsyncAI._validation_packet_valid)
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    settings = Settings()
    settings.set_game_mode((PLAYER_HUMAN, PLAYER_HUMAN))
    instance = game_module.Game(screen, settings)
    instance.telop.active = False
    yield instance
    instance.close()
    pygame.quit()


def trigger_pending(game):
    game.board.validation_budget_sec = 0
    assert game._make_move(7, 7) is False
    assert game._pending_validation is not None
    assert game.validation_runner.busy
    assert not game.move_history and not game.board.grid.any()
    assert not game.ai_runner.busy and not game.analysis_runner.busy


def test_human_timeout_eventually_applies_legal_candidate_without_repeat_query(game):
    trigger_pending(game)
    game.validation_runner.answer = packet(game.validation_runner.task)
    game.update()
    assert game.move_history == [(7, 7)]
    assert game.board.grid[7, 7] == BLACK
    assert game._pending_validation is None and game._validation_retry is None
    assert not game.game_over and not game.ai_error


def test_game_rejects_bound_legal_packet_without_verdict(game):
    trigger_pending(game)
    response = packet(game.validation_runner.task)
    response.pop('verdict')
    game.validation_runner.answer = response
    game.update()
    assert game.validation_status == 'unknown'
    assert not game.board._legality_cache and not game.move_history
    assert not game.game_over and game.winner is None


def test_illegal_verdict_does_not_apply_or_retry(game):
    trigger_pending(game)
    game.validation_runner.answer = packet(game.validation_runner.task, 'illegal')
    game.update()
    assert not game.move_history and not game.board.grid.any()
    assert game.validation_status == 'illegal'
    assert game._validation_retry is None and not game.game_over


def test_unknown_is_not_illegal_and_requires_explicit_retry(game):
    trigger_pending(game)
    game.validation_runner.answer = packet(game.validation_runner.task, 'unknown')
    game.update()
    assert game.validation_status == 'unknown'
    assert game._validation_retry is not None
    assert not game.board._legality_cache and not game.move_history
    game.update()
    assert len(game.validation_runner.calls) == 1  # No infinite automatic loop.
    game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r))
    assert len(game.validation_runner.calls) == 2 and game.validation_runner.busy
    assert not game.game_over and game.winner is None


@pytest.mark.parametrize('action', ['reset', 'escape', 'save', 'history'])
def test_navigation_cancels_pending_and_stale_candidate(game, action, monkeypatch):
    trigger_pending(game)
    if action == 'reset': game.reset_game()
    elif action == 'escape':
        assert game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)) == STATE_MENU
    elif action == 'save':
        monkeypatch.setattr(game, '_save_game', lambda: None)
        game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_s))
    else:
        game.prev_move_button.is_hovering = True
        game.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1,
                                            pos=game.prev_move_button.rect.center))
    assert game._pending_validation is None and not game.validation_runner.busy
    assert game._validation_retry is None and not game.move_history


def test_ai_pending_validation_queues_instead_of_error(game):
    game.player_types = (PLAYER_AI, PLAYER_HUMAN)
    game.ai_thinking = True
    game.ai_runner.busy = True
    game.ai_runner.answer = {'move': None, 'validation_pending_move': (7, 7),
                             'validation_required': True}
    game.update()
    assert game._pending_validation is not None and game.ai_error is None
    assert not game.move_history
    game.validation_runner.answer = packet(game.validation_runner.task)
    game.update()
    assert game.move_history == [(7, 7)] and game.ai_error is None


def test_real_single_candidate_opening_validation(tmp_path):
    runner = AsyncAI(worker_directory=tmp_path)
    board = Board()
    board.validation_budget_sec = 0
    try:
        runner.start(board, BLACK, 0, 'hard', budget=0.5, kind='validate', candidate=(7, 7))
        end = time.perf_counter() + 4
        clock = pygame.time.Clock()
        result = None
        while result is None and time.perf_counter() < end:
            result = runner.poll(board, BLACK, 0)
            clock.tick(100)
        assert result is not None and result['adjudication'] == 'legal', result
        assert result['verdict'] == {'legal': True, 'win': False, 'reason': 'legal_nonterminal'}
        assert not board.grid.any() and not board._legality_cache
        assert board.accept_checked_move(7, 7, BLACK, 0,
            expected_key=(15, 5, board.grid.tobytes()), ruleset=result['validation_context']['ruleset'],
            opening_policy=result['validation_context']['opening_policy'])
        assert board.place_stone(7, 7, BLACK, 0)  # Cached, even with zero UI budget.
    finally:
        runner.close()
