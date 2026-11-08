"""G01: strict semantic replay, transactional apply, atomic persistence."""
import copy
import json
import os
import threading
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
import pygame
import pytest
import save_data as saves
from board import BLACK, WHITE
from settings import Settings

START = [[7, 7], [6, 7], [7, 8]]
BLACK_WIN = [[7,7],[6,7],[7,6],[0,0],[7,5],[0,2],[7,4],[0,4],[7,3]]
WHITE_OVERLINE = [[7,7],[6,7],[7,8],[0,0],[14,0],[0,1],[14,2],[0,2],
                  [14,4],[0,4],[14,6],[0,5],[14,8],[0,3]]
DOUBLE_THREE = [[7,7],[6,7],[5,5],[0,0],[10,9],[0,2],[10,11],[0,4],
                [9,10],[0,6],[11,10],[0,8],[10,10]]


def payload(moves=None):
    return {'settings': saves.settings_data(Settings()), 'move_history': START if moves is None else moves}


def put(tmp_path, data):
    path = tmp_path / 'save.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    return path


@pytest.mark.parametrize('version', [None, 1, 2])
@pytest.mark.parametrize('moves', [[], START, BLACK_WIN, WHITE_OVERLINE])
def test_valid_legacy_and_terminal_saves(version, moves, tmp_path):
    data = payload(moves)
    if version is not None:
        data['schema_version'] = version
    loaded = saves.read_save(put(tmp_path, data))
    assert loaded.moves == moves
    assert loaded.game_over == (moves in (BLACK_WIN, WHITE_OVERLINE))
    if loaded.game_over:
        assert loaded.winner == (BLACK if moves == BLACK_WIN else WHITE)
        assert loaded.win_line
    assert loaded.board.last_move == (tuple(moves[-1]) if moves else None)


@pytest.mark.parametrize('moves,reason', [([[0,0]], 'opening'),
    ([[7,7],[0,0]], 'opening'), ([[7,7],[6,7],[0,0]], 'opening'),
    (DOUBLE_THREE, 'forbidden_double_three'), (BLACK_WIN+[[0,6]], 'after game'),
    (WHITE_OVERLINE+[[14,10]], 'after game'), ([[7,7],[7,7]], 'occupied')])
def test_illegal_history_fails_whole_load(moves, reason, tmp_path):
    with pytest.raises(saves.SaveError, match=reason):
        saves.read_save(put(tmp_path, payload(moves)))


@pytest.mark.parametrize('version', [True, False, 1.0, 2.0, '2', None, 3])
def test_schema_version_is_exact_int(version, tmp_path):
    data = payload()
    data['schema_version'] = version
    with pytest.raises(saves.SaveError):
        saves.read_save(put(tmp_path, data))


@pytest.mark.parametrize('mode', [[False,True], [0.0,1.0], '01', {}, [0]])
def test_mode_uses_exact_ints(mode, tmp_path):
    data = payload()
    data['settings']['game_mode'] = mode
    with pytest.raises(saves.SaveError):
        saves.read_save(put(tmp_path, data))


@pytest.mark.parametrize('text', ['null', '[]', '{', '{"settings":{},"settings":{}}',
                                     '{"settings":NaN}', '\ufeff{"settings": null}'])
def test_malformed_json_rejected(text, tmp_path):
    path = tmp_path / 'bad.json'
    path.write_text(text, encoding='utf-8')
    with pytest.raises(saves.SaveError):
        saves.read_save(path)


def test_oversize_and_invalid_utf8_fail(tmp_path):
    path = tmp_path / 'bad.json'
    path.write_bytes(b' ' * (saves.MAX_SAVE_BYTES + 1))
    with pytest.raises(saves.SaveError, match='large'):
        saves.read_save(path)
    path.write_bytes(b'\xff')
    with pytest.raises(saves.SaveError, match='UTF-8'):
        saves.read_save(path)


def test_timeout_cancel_are_unconfirmed_and_nonmutating():
    raw = payload()
    original = copy.deepcopy(raw)
    with pytest.raises(saves.SaveError, match='incomplete'):
        saves.validate_history(raw['settings'], raw['move_history'], budget=0)
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(saves.SaveError, match='cancelled'):
        saves.validate_history(raw['settings'], raw['move_history'], cancel=cancel)
    assert raw == original


def test_deadline_inside_recursive_classification(monkeypatch):
    from renju_rules import Rules
    now = [0.0]
    monkeypatch.setattr(saves.time, 'perf_counter', lambda: now[0])
    def classify(self, cells, index, player, count, check):
        now[0] = 10.0
        check()
        pytest.fail('timeout must not become legal')
    monkeypatch.setattr(Rules, 'classify', classify)
    with pytest.raises(saves.SaveError, match='incomplete'):
        saves.validate_history(payload()['settings'], START, budget=1)


def test_load_task_is_detached_and_cancellable(monkeypatch, tmp_path):
    entered, release = threading.Event(), threading.Event()
    def reader(filename, cancel):
        entered.set()
        assert release.wait(2)
        assert cancel.is_set()
        raise saves.SaveError('Load cancelled')
    monkeypatch.setattr(saves, 'read_save', reader)
    task = saves.LoadTask(tmp_path / 'unused.json')
    try:
        assert entered.wait(2)
        assert not task.done.is_set()
        task.cancel()
    finally:
        release.set()
        task.thread.join(2)
    assert task.done.is_set() and task.result is None and 'cancelled' in task.error


@pytest.fixture
def game():
    from game import Game
    pygame.init()
    screen = pygame.display.set_mode((800, 800))
    settings = Settings()
    settings.set_game_mode((0,0))
    game = Game(screen, settings)
    game.reset_game(START)
    try:
        yield game
    finally:
        game.close()
        pygame.quit()


def test_draw_restored_with_live_terminal_convention(game):
    black = [(r,c) for r in range(9) for c in range(9) if (r+2*c)%4 < 2]
    white = [(r,c) for r in range(9) for c in range(9) if (r+2*c)%4 >= 2]
    black = [(4,4),(3,3)] + [p for p in black if p not in ((4,4),(3,3))]
    white = [(3,4)] + [p for p in white if p != (3,4)]
    moves = []
    for i, move in enumerate(black):
        moves.append(list(move))
        if i < len(white):
            moves.append(list(white[i]))
    game.settings.board_size, game.settings.win_length = 9, 7
    game.reset_game(moves)
    assert len(game.move_history) == 81 and game.game_over and game.winner is None
    assert game.current_player == BLACK and game.display_move_index == 81
    assert not game.ai_runner.busy


@pytest.mark.parametrize('black,reason', [
    ([(7,7),(5,5),(10,7),(10,8),(10,9),(7,10),(8,10),(9,10),(10,10)], 'double_four'),
    ([(7,7),(5,5),(10,7),(10,8),(10,9),(10,11),(10,12),(10,10)], 'overline')])
def test_other_black_fouls_reject_complete_history(black, reason):
    white = [(6,7)] + [(0,c) for c in range(0,15,2)]
    moves = []
    for i, move in enumerate(black):
        moves.append(list(move))
        if i < len(black)-1:
            moves.append(list(white[i]))
    with pytest.raises(saves.SaveError, match=reason):
        saves.validate_history(payload()['settings'], moves)


def test_failed_direct_reset_preserves_every_live_reference(game):
    board = game.board
    history = game.move_history
    settings = game.settings
    grid = board.grid.copy()
    with pytest.raises(saves.SaveError):
        game.reset_game(DOUBLE_THREE)
    assert game.board is board and game.move_history is history and game.settings is settings
    assert (board.grid == grid).all() and len(history) == 3


def test_direct_replay_resource_failure_preserves_old_game(game, monkeypatch):
    import game as module
    old_board, old_history = game.board, game.move_history
    def fail():
        raise PermissionError('joseki resource unavailable')
    monkeypatch.setattr(module, 'load_joseki', fail)
    with pytest.raises(PermissionError):
        game.reset_game([[7,7]])
    assert game.board is old_board and game.move_history is old_history
    assert len(old_history) == 3


def test_candidate_failure_does_not_modify_old_game(game, monkeypatch):
    import main
    old_settings = saves.settings_data(game.settings)
    old_board = game.board
    def fail(*args, **kwargs):
        raise RuntimeError('construction failed')
    monkeypatch.setattr(main, 'Game', fail)
    loaded = saves.validate_history(payload()['settings'], BLACK_WIN)
    with pytest.raises(RuntimeError):
        main._prepare_loaded_game(game.screen, loaded)
    assert game.board is old_board and saves.settings_data(game.settings) == old_settings


def test_main_load_thread_start_failure_stays_in_gui(monkeypatch):
    import main
    pygame.init()
    def click(pos):
        return [pygame.event.Event(pygame.MOUSEMOTION, pos=pos),
                pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)]
    batches = iter([click((400,335)), click((400,150)),
                    [pygame.event.Event(pygame.QUIT)]])
    monkeypatch.setattr(pygame.event, 'get', lambda: next(batches))
    monkeypatch.setattr(main, '_get_save_files', lambda: ['gomoku_save_test.json'])
    attempts = []
    def fail(filename):
        attempts.append(filename)
        raise RuntimeError('cannot start new thread')
    monkeypatch.setattr(main, 'LoadTask', fail)
    with pytest.raises(SystemExit) as exc:
        main.main()
    assert exc.value.code is None and attempts == ['gomoku_save_test.json']
    assert not pygame.get_init()


def test_main_back_discards_late_load_result(monkeypatch):
    import main
    pygame.init()
    def click(pos):
        return [pygame.event.Event(pygame.MOUSEMOTION, pos=pos),
                pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)]
    batches = iter([click((400,335)), click((400,150)),
                    [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)],
                    [pygame.event.Event(pygame.QUIT)]])
    monkeypatch.setattr(pygame.event, 'get', lambda: next(batches))
    monkeypatch.setattr(main, '_get_save_files', lambda: ['gomoku_save_test.json'])
    class LateTask:
        def __init__(self, filename):
            self.done, self.cancelled = threading.Event(), threading.Event()
            self.result = saves.validate_history(payload()['settings'], START)
            self.error = None
        def cancel(self):
            self.cancelled.set()
            self.done.set()  # Completion races navigation but must not publish.
    task = LateTask('unused')
    monkeypatch.setattr(main, 'LoadTask', lambda filename: task)
    def unexpected(*args):
        pytest.fail('cancelled load published')
    monkeypatch.setattr(main, '_prepare_loaded_game', unexpected)
    with pytest.raises(SystemExit):
        main.main()
    assert task.cancelled.is_set() and not pygame.get_init()


def test_two_saves_unique_and_valid(tmp_path):
    data = payload()
    first = saves.atomic_save(data, directory=tmp_path)
    second = saves.atomic_save(data, directory=tmp_path)
    assert first != second
    assert saves.read_save(first).moves == saves.read_save(second).moves == START
    assert not list(tmp_path.glob('*.tmp'))


@pytest.mark.parametrize('failure', ['write', 'fsync', 'replace', 'link'])
def test_save_failure_never_truncates_old_file(failure, monkeypatch, tmp_path):
    target = tmp_path / 'existing.json'
    original = b'important existing data'
    target.write_bytes(original)
    def fail(*args, **kwargs):
        if failure == 'write':
            args[1].write('{partial')
        raise OSError('injected failure')
    if failure == 'write':
        monkeypatch.setattr(saves.json, 'dump', fail)
    else:
        monkeypatch.setattr(saves.os, failure, fail)
    with pytest.raises(OSError):
        saves.atomic_save(payload(), target, overwrite=failure != 'link')
    assert target.read_bytes() == original
    assert sorted(p.name for p in tmp_path.iterdir()) == ['existing.json']


def test_no_clobber_and_explicit_atomic_replace(tmp_path):
    target = tmp_path / 'existing.json'
    target.write_text('old')
    with pytest.raises(FileExistsError):
        saves.atomic_save(payload(), target)
    assert target.read_text() == 'old'
    saves.atomic_save(payload(), target, overwrite=True)
    assert saves.read_save(target).moves == START


def test_save_success_failure_and_history_notice(game, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert game._save_game() is not None
    assert 'saved successfully' in game.save_notice[0]
    def fail(*args, **kwargs):
        raise PermissionError('denied')
    monkeypatch.setattr(saves, 'atomic_save', fail)
    assert game._save_game() is None
    assert 'failed' in game.save_notice[0]
    game.is_history_mode = True
    assert game._save_game() is None
    assert 'current position' in game.save_notice[0]
