"""Bounded, detached save validation and atomic UTF-8 persistence.

No pygame or live Settings/Game mutations here. Historical v1/v2 containers are
accepted, but every move must satisfy today's shared rules before resuming.
"""
from dataclasses import dataclass
import datetime
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import uuid

from board import Board, BLACK, WHITE
from settings import Settings

MAX_SAVE_BYTES = 1_048_576
LOAD_BUDGET_SEC = 3.0


class SaveError(ValueError):
    pass


@dataclass
class ValidatedGame:
    settings: dict
    moves: list
    board: Board
    winner: object = None
    win_line: object = None
    game_over: bool = False


def settings_data(settings):
    return {name: getattr(settings, name) for name in
            ('board_size', 'win_length', 'game_mode', 'ai_difficulty', 'ai_starts')}


def _settings(raw):
    if not isinstance(raw, dict):
        raise SaveError('Settings must be an object')
    valid = Settings()
    keys = settings_data(valid)
    if not all(k in raw for k in keys):
        raise SaveError('Missing game settings')
    size, length, mode = raw['board_size'], raw['win_length'], raw['game_mode']
    if (type(size) is not int or size not in valid.board_size_options
            or type(length) is not int or length not in valid.win_length_options
            or length > size or not isinstance(mode, (list, tuple)) or len(mode) != 2
            or any(type(v) is not int for v in mode)
            or tuple(mode) not in valid.game_mode_options
            or raw['ai_difficulty'] not in valid.ai_difficulty_options
            or type(raw['ai_starts']) is not bool):
        raise SaveError('Unsupported game settings')
    # ai_starts is retained as legacy metadata, not used to change stone order.
    return dict((k, tuple(mode) if k == 'game_mode' else raw[k]) for k in keys)


def validate_history(settings, moves, *, budget=LOAD_BUDGET_SEC, cancel=None):
    resolved = _settings(settings)
    size = resolved['board_size']
    if not isinstance(moves, list) or len(moves) > size * size:
        raise SaveError('Invalid history length or type')
    normalized = []
    seen = set()
    for i, move in enumerate(moves):
        if (not isinstance(move, (tuple, list)) or len(move) != 2
                or any(type(v) is not int or not 0 <= v < size for v in move)):
            raise SaveError(f'Move {i + 1}: invalid coordinates')
        cell = tuple(move)
        if cell in seen:
            raise SaveError(f'Move {i + 1}: occupied intersection')
        seen.add(cell)
        normalized.append(list(cell))
    deadline = time.perf_counter() + budget

    def check():
        if cancel is not None and cancel.is_set():
            raise SaveError('Load cancelled')
        if time.perf_counter() >= deadline:
            raise SaveError('Validation incomplete (time limit); game not loaded')

    board = Board(size, resolved['win_length'])
    result = ValidatedGame(resolved, normalized, board)
    cells = [0] * (size * size)
    for i, (row, col) in enumerate(normalized):
        check()
        if result.game_over:
            raise SaveError(f'Move {i + 1}: move after game ended')
        player = BLACK if i % 2 == 0 else WHITE
        verdict = board._rules.classify(cells, row * size + col, player, i, check=check)
        if verdict.legal is not True:
            raise SaveError(f'Move {i + 1}: {verdict.reason}')
        cells[row * size + col] = player
        board.grid[row, col] = player
        board.last_move = (row, col)
        won, line = board.check_win(player)
        if won:
            result.game_over, result.winner, result.win_line = True, player, line
        elif i + 1 == size * size:
            result.game_over = True
    check()
    return result


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SaveError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def read_save(filename, *, budget=LOAD_BUDGET_SEC, cancel=None):
    with open(filename, 'rb') as stream:
        payload = stream.read(MAX_SAVE_BYTES + 1)
    if len(payload) > MAX_SAVE_BYTES:
        raise SaveError('Save file too large')
    def invalid_constant(value):
        raise SaveError(f'Invalid JSON value: {value}')
    try:
        data = json.loads(payload.decode('utf-8-sig'), object_pairs_hook=_object,
                          parse_constant=invalid_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise SaveError('Invalid UTF-8 JSON save') from exc
    if not isinstance(data, dict) or 'settings' not in data or 'move_history' not in data:
        raise SaveError('Missing save data')
    version = data.get('schema_version', 1)
    if type(version) is not int or version not in (1, 2):
        raise SaveError('Unsupported save version')
    resolved = _settings(data['settings'])
    if 'rules' in data:
        from renju_rules import Rules
        expected = Rules(resolved['board_size'], resolved['win_length'])
        metadata = data['rules']
        if (not isinstance(metadata, dict) or metadata.get('ruleset') != expected.ruleset
                or metadata.get('opening_policy') != expected.opening_policy):
            raise SaveError('Unsupported rule policy')
    return validate_history(resolved, data['move_history'], budget=budget, cancel=cancel)


class LoadTask:
    """One cancellable GUI-independent load. Completion never changes live state."""
    def __init__(self, filename):
        self.cancelled = threading.Event()
        self.done = threading.Event()
        self.result = None
        self.error = None
        def run():
            try:
                self.result = read_save(filename, cancel=self.cancelled)
            except Exception as exc:
                self.error = str(exc) or type(exc).__name__
            finally:
                self.done.set()
        self.thread = threading.Thread(target=run, name='save-validation', daemon=True)
        self.thread.start()

    def cancel(self):
        self.cancelled.set()


def save_payload(settings, board, moves):
    return {'schema_version': 2,
            'rules': {'ruleset': board.ruleset, 'opening_policy': board.opening_policy,
                      'legacy_save_migration': 'validated-current-adjudication'},
            'settings': settings_data(settings),
            'move_history': [[int(r), int(c)] for r, c in moves]}


def atomic_save(data, filename=None, *, directory='.', overwrite=False):
    """Publish only complete files; default publication never replaces a save.

    Hard-link publication is atomic and fails closed on unsupported filesystems.
    Explicit overwrite uses same-directory os.replace after flush/fsync.
    """
    if filename is None:
        stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        filename = Path(directory) / f'gomoku_save_{stamp}_{uuid.uuid4().hex[:8]}.json'
    target = Path(filename)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=target.parent,
                                         prefix='.gomoku-save-', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, allow_nan=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        if overwrite:
            os.replace(temporary, target)
        else:
            os.link(temporary, target)  # Atomic no-clobber, unlike POSIX rename.
        return target
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
