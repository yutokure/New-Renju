"""Nonblocking subprocess adapter shared by all difficulty levels.

Main-thread methods only snapshot, launch, poll tiny JSON and validate one move.
Workers never share a live board. Tokens bind results to exact position/context.
"""
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid


@dataclass
class _Task:
    process: subprocess.Popen
    directory: object
    token: str
    position: tuple
    started: float
    budget: float
    result: object = None
    read_after: float = 0.0


def position_key(board, player, move_count):
    return (board.size, board.win_length, board.grid.tobytes(),
            tuple(board.last_move) if board.last_move is not None else None,
            int(player), int(move_count))


class AsyncAI:
    """One active search; cancel is nonblocking, processes are reaped on poll.

    A 2-second startup grace covers Python/NumPy import on Windows; search
    itself uses the engine's normal deadline. Wall cap = budget + grace.
    """
    def __init__(self, startup_grace=2.0):
        self.startup_grace = max(0.0, startup_grace)
        self.task = None
        self.retired = []
        self.last_info = {}

    @property
    def busy(self):
        return self.task is not None

    def start(self, board, player, move_count, difficulty, *, budget=None, kind='move'):
        self.cancel()
        self.reap()
        if budget is None:
            budget = 5.0 if difficulty == 'very_hard' else 1.5
        budget = max(0.0, float(budget))
        directory = tempfile.TemporaryDirectory(prefix='renju-ai-')
        root = Path(directory.name)
        token = uuid.uuid4().hex
        request = {'token': token, 'kind': kind, 'difficulty': difficulty,
                   'player': int(player), 'move_count': int(move_count), 'budget': budget,
                   'board': {'size': board.size, 'win_length': board.win_length,
                             'grid': board.grid.tolist(), 'last_move': board.last_move}}
        if request['board']['last_move'] is not None:
            request['board']['last_move'] = [int(x) for x in board.last_move]
        request_path = root / 'request.json'
        request_path.write_text(json.dumps(request), encoding='utf-8')
        # No captured pipes/queues: this is safe on Windows and detached from UI.
        if getattr(sys, 'frozen', False):
            command = [sys.executable, '--ai-worker', str(request_path)]
        else:
            command = [sys.executable, '-B', str(Path(__file__).with_name('ai_worker.py')), str(request_path)]
        kwargs = {'stdin': subprocess.DEVNULL, 'stdout': subprocess.DEVNULL,
                  'stderr': subprocess.DEVNULL}
        if os.name == 'nt':
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
        try:
            process = subprocess.Popen(command, **kwargs)
        except Exception:
            directory.cleanup()
            raise
        self.task = _Task(process, directory, token, position_key(board, player, move_count),
                          time.perf_counter(), budget)
        self.last_info = {'phase': 'starting', 'elapsed': 0.0}
        return token

    def _read_result(self, task):
        now = time.perf_counter()
        if now < task.read_after:
            return
        task.read_after = now + 0.03
        try:
            result = json.loads((Path(task.directory.name) / 'result.json').read_text(encoding='utf-8'))
            if not isinstance(result, dict) or result.get('token') != task.token:
                return
            if type(result.get('done', False)) is not bool:
                return
            for field in ('elapsed', 'score'):
                value = result.get(field)
                if value is not None and (type(value) not in (int, float) or not math.isfinite(value)):
                    return
            if type(result.get('completed_depth', 0)) is not int:
                return
            if 'scores' in result:
                scores = result['scores']
                if not isinstance(scores, list) or any(
                        not isinstance(row, list) or len(row) != 3 or
                        type(row[0]) is not int or type(row[1]) is not int or
                        type(row[2]) not in (int, float) or not math.isfinite(row[2])
                        for row in scores):
                    return
            task.result = result
            self.last_info = result
        except (OSError, ValueError, OverflowError):
            pass

    def poll(self, board, player, move_count):
        self.reap()
        task = self.task
        if task is None:
            return None
        if task.position != position_key(board, player, move_count):
            self.cancel()
            return None
        self._read_result(task)
        expired = time.perf_counter() - task.started >= task.budget + self.startup_grace
        exited = task.process.poll() is not None
        done = bool(task.result and task.result.get('done'))
        if not (expired or exited or done):
            return None
        result = dict(task.result or {'move': None, 'error': 'Worker ended without a result'})
        result['timed_out'] = expired and not done
        self._retire(task)
        self.task = None
        if 'move' in result and result['move'] is not None:
            move = result['move']
            if (not isinstance(move, (list, tuple)) or len(move) != 2 or
                    not all(type(x) is int for x in move) or
                    not board.is_valid_move(*move, player, move_count)):
                result.update(move=None, error='Rejected invalid worker result')
            else:
                result['move'] = tuple(move)
        self.last_info = result
        return result

    def _retire(self, task):
        if task.process.poll() is None:
            try:
                (Path(task.directory.name) / 'cancel').touch()
            except OSError:
                pass
            # Cooperative signal is useful inside search; terminate guarantees
            # prompt menu/reset even if a future engine ignores cancellation.
            try:
                task.process.terminate()
            except OSError:
                pass
        self.retired.append(task)

    def cancel(self):
        if self.task is not None:
            self._retire(self.task)
            self.task = None
        self.reap()

    def reap(self):
        remaining = []
        for task in self.retired:
            if task.process.poll() is None:
                remaining.append(task)
            else:
                task.process.wait(timeout=0)
                try:
                    task.directory.cleanup()
                except OSError:
                    remaining.append(task)
        self.retired = remaining

    def close(self):
        self.cancel()
        for task in self.retired:
            if task.process.poll() is None:
                task.process.kill()
            task.process.wait(timeout=1.0)
            task.directory.cleanup()
        self.retired.clear()
