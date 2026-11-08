"""Headless UI integration, plus real Windows-compatible subprocess smoke tests."""
import json
import os
from pathlib import Path
import time
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
import numpy as np
import pygame
import pytest
from ai_async import AsyncAI, position_key
from board import Board, BLACK, WHITE
from constants import PLAYER_AI, PLAYER_HUMAN, STATE_MENU
from settings import Settings
from tests.positions import hard_cases


@pytest.fixture
def screen():
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    yield screen
    pygame.quit()


def wait_result(runner, board, player, count, timeout=6):
    deadline = time.perf_counter() + timeout
    clock = pygame.time.Clock()
    while time.perf_counter() < deadline:
        result = runner.poll(board, player, count)
        if result is not None:
            return result
        clock.tick(100)
    pytest.fail('Worker failed wall-clock guard')


@pytest.mark.parametrize('difficulty', ['easy', 'normal', 'hard'])
def test_real_worker_legal_nonmutating(difficulty):
    board = Board()
    grid = board.grid.copy()
    runner = AsyncAI()
    try:
        runner.start(board, BLACK, 0, difficulty, budget=0.1)
        result = wait_result(runner, board, BLACK, 0)
        assert result.get('error') is None, result
        assert result['move'] == (7, 7)
        assert np.array_equal(board.grid, grid)
        assert board.last_move is None
    finally:
        runner.close()
    assert not runner.retired


def test_stale_board_cancels_worker():
    board = Board()
    runner = AsyncAI()
    try:
        runner.start(board, BLACK, 0, 'hard')
        proc = runner.task.process
        board.grid[7,7] = BLACK
        board.last_move = (7,7)
        assert runner.poll(board, WHITE, 1) is None
        assert not runner.busy
    finally:
        runner.close()
    assert proc.poll() is not None


def test_external_watchdog_uses_only_verified_result():
    board = Board()
    runner = AsyncAI(startup_grace=0)
    try:
        runner.start(board, BLACK, 0, 'hard', budget=0)
        task = runner.task
        # Simulate a legal progress packet from a worker that does not finish.
        result = {'token': task.token, 'move': [7,7], 'done': False}
        (Path(task.directory.name) / 'result.json').write_text(json.dumps(result))
        answer = runner.poll(board, BLACK, 0)
        assert answer['move'] == (7,7)
        assert answer['timed_out']
    finally:
        runner.close()


def test_finished_worker_result_bypasses_progress_read_throttle():
    board = Board()
    runner = AsyncAI(startup_grace=0)
    try:
        runner.start(board, BLACK, 0, 'hard', budget=0)
        task = runner.task
        task.read_after = time.perf_counter() + 100
        (Path(task.directory.name) / 'result.json').write_text(json.dumps(
            {'token': task.token, 'move': [7,7], 'done': True}))
        result = runner.poll(board, BLACK, 0)
        assert result['move'] == (7,7)
        assert not result['timed_out']
    finally:
        runner.close()


def test_invalid_result_rejected():
    board = Board()
    runner = AsyncAI(startup_grace=0)
    try:
        runner.start(board, BLACK, 0, 'hard', budget=0)
        task = runner.task
        (Path(task.directory.name) / 'result.json').write_text(json.dumps({'token': task.token, 'move': [0,0], 'done': True}))
        answer = runner.poll(board, BLACK, 0)
        assert answer['move'] is None
        assert answer['error']
    finally:
        runner.close()


@pytest.mark.parametrize('payload', [[], None, 42, {'scores': [[1,2,'bad']]},
                                      {'elapsed': 'bad'}, {'completed_depth': []},
                                      {'done': 'yes'}, {'elapsed': 10**400}])
def test_malformed_worker_packets_do_not_crash(payload):
    board = Board()
    runner = AsyncAI(startup_grace=0)
    try:
        runner.start(board, BLACK, 0, 'hard', budget=0)
        task = runner.task
        if isinstance(payload, dict):
            payload['token'] = task.token
        (Path(task.directory.name) / 'result.json').write_text(json.dumps(payload))
        answer = runner.poll(board, BLACK, 0)
        assert answer['move'] is None
        assert answer.get('error')
    finally:
        runner.close()


def test_game_update_and_menu_are_nonblocking(screen, monkeypatch):
    from game import Game
    settings = Settings()
    settings.set_game_mode((PLAYER_AI, PLAYER_HUMAN))
    settings.set_ai_difficulty('hard')
    game = Game(screen, settings)
    try:
        game.telop.active = False
        start = time.perf_counter()
        game.update()
        assert time.perf_counter() - start < 0.3
        assert game.ai_thinking
        proc = game.ai_runner.task.process
        # Main event handling does not wait for AI.find_move.
        start = time.perf_counter()
        assert game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)) == STATE_MENU
        assert time.perf_counter() - start < 0.3
        assert not game.ai_runner.busy
    finally:
        game.close()
    assert proc.poll() is not None


def test_noop_next_during_thinking_cannot_stall_ai(screen):
    from game import Game
    settings = Settings()
    settings.set_game_mode((PLAYER_AI, PLAYER_HUMAN))
    game = Game(screen, settings)
    try:
        game.telop.active = False
        game.update()
        assert game.ai_thinking
        game.next_move_button.is_hovering = True
        game.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=game.next_move_button.rect.center))
        assert game.telop.state != 'visible' or game.telop.duration is not None
        assert not game.ai_thinking
    finally:
        game.close()


def test_reset_discards_pending_result(screen):
    from game import Game
    settings = Settings()
    settings.set_game_mode((PLAYER_AI, PLAYER_AI))
    game = Game(screen, settings)
    try:
        game.telop.active = False
        game.update()
        old_token = game.ai_runner.task.token
        game.reset_game()
        assert not game.ai_runner.busy
        assert not game.ai_thinking
        assert not game.move_history
        game.telop.active = False
        game.update()
        assert game.ai_runner.task.token != old_token
    finally:
        game.close()


def test_analysis_detached_and_one_request_per_position(screen):
    from game import Game
    settings = Settings()
    settings.set_game_mode((PLAYER_HUMAN, PLAYER_HUMAN))
    game = Game(screen, settings)
    try:
        game.research_mode_enabled = True
        game._evaluate_empty_cells()
        token = game.analysis_runner.task.token
        game._evaluate_empty_cells()
        assert token == game.analysis_runner.task.token
        result = wait_result(game.analysis_runner, game.board, BLACK, 0)
        assert result.get('error') is None, result
        assert result['phase'] == 'Hard static estimate'
        assert [(r,c) for r,c,_ in result['scores']] == [(7,7)]
        assert not np.any(game.board.grid)
        assert game.board.last_move is None
    finally:
        game.close()


def test_research_spawn_failure_is_contained_and_not_retried(screen, monkeypatch):
    from game import Game
    settings = Settings()
    settings.set_game_mode((PLAYER_HUMAN, PLAYER_HUMAN))
    game = Game(screen, settings)
    calls = []
    def fail(*args, **kwargs):
        calls.append(1)
        raise OSError('spawn denied')
    monkeypatch.setattr(game.analysis_runner, 'start', fail)
    try:
        game.research_mode_enabled = True
        game._evaluate_empty_cells()
        game._evaluate_empty_cells()
        assert len(calls) == 1
        assert not game.evaluation_in_progress
    finally:
        game.close()


def test_old_save_loader_and_replay(screen, tmp_path):
    from main import _load_game_data
    from game import Game
    data = {'settings': {'board_size': 15, 'win_length': 5, 'game_mode': [0,1], 'ai_difficulty': 'hard', 'ai_starts': False},
            'move_history': [[7,7],[6,7],[7,8]]}
    path = tmp_path / 'old.json'
    path.write_text(json.dumps(data))
    settings_data, moves = _load_game_data(path)
    assert settings_data['game_mode'] == (0,1)
    game = Game(screen, Settings())
    try:
        game.reset_game(moves)
        assert game.current_player == WHITE
        assert len(game.move_history) == 3
        assert game.board.last_move == [7,8] or game.board.last_move == (7,8)
        game.is_history_mode = True
        game.display_move_index = 1
        assert game._get_current_board_for_display().grid[7,7] == BLACK
    finally:
        game.close()
