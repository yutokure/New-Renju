"""Nonblocking subprocess adapter shared by all difficulty levels.

Main-thread methods only snapshot, launch, poll tiny JSON and validate one move.
Workers never share a live board. Tokens bind results to exact position/context.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import struct
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
    resources: object = None
    kind: str = 'move'
    candidate: object = None
    validation_context: object = None


VALIDATION_PROTOCOL = 'renju-rules-classify-v1'


def validation_context(board, player, move_count, candidate):
    """Exact snapshot provenance for a single-candidate rule request.

    The digest is an integrity/context check, not a signature against a local
    malicious process. It is compared along with the unshared task token.
    """
    context = {'kind': 'validate', 'protocol': VALIDATION_PROTOCOL,
               'candidate': list(candidate), 'size': int(board.size),
               'win_length': int(board.win_length), 'player': int(player),
               'move_count': int(move_count), 'ruleset': board.ruleset,
               'opening_policy': board.opening_policy}
    snapshot = dict(context, grid=board.grid.tolist(),
                    last_move=[int(x) for x in board.last_move] if board.last_move is not None else None)
    context['snapshot_id'] = hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
    return context


def _candidate_shape(candidate):
    return (isinstance(candidate, (list, tuple)) and len(candidate) == 2
            and all(type(x) is int for x in candidate))


def position_key(board, player, move_count):
    return (board.size, board.win_length, board.grid.tobytes(),
            tuple(board.last_move) if board.last_move is not None else None,
            int(player), int(move_count))


class AsyncAI:
    """One active search; cancel is nonblocking, processes are reaped on poll.

    A 2-second startup grace covers Python/NumPy import on Windows; search
    itself uses the engine's normal deadline. Wall cap = budget + grace.
    """
    def __init__(self, startup_grace=2.0, memory_limit_mb=None, worker_directory=None):
        if not math.isfinite(startup_grace) or startup_grace < 0:
            raise ValueError('startup_grace must be finite and nonnegative')
        self.startup_grace = startup_grace
        if memory_limit_mb is None:
            # PyInstaller's boot/runtime imports reserve more committed memory
            # before worker code starts than a plain Python interpreter does.
            memory_limit_mb = 1024 if getattr(sys, 'frozen', False) else 512
        max_mib = min(1_048_576, ((1 << (struct.calcsize('P')*8))-1)//(1024*1024))
        if type(memory_limit_mb) is not int or not 1 <= memory_limit_mb <= max_mib:
            raise ValueError('memory_limit_mb must be a positive integer fitting native SIZE_T')
        self.memory_limit_mb = memory_limit_mb
        # Explicit caller configuration, not a silent fallback on denied TEMP.
        self.worker_directory = worker_directory
        self.task = None
        self.retired = []
        self.orphan_directories = []
        self.last_info = {}

    @property
    def busy(self):
        return self.task is not None

    def start(self, board, player, move_count, difficulty, *, budget=None, kind='move', candidate=None):
        if kind not in ('move', 'analysis', 'legality', 'validate'):
            raise ValueError('Unknown AI request kind')
        context = None
        if kind == 'validate':
            if (not _candidate_shape(candidate) or type(player) is not int
                    or player not in (1, 2) or type(move_count) is not int or move_count < 0
                    or not board.is_within_bounds(*candidate) or not board.is_empty(*candidate)
                    or not board._opening_allows(*candidate, move_count)):
                raise ValueError('Invalid deferred validation candidate')
            candidate = tuple(candidate)
            context = validation_context(board, player, move_count, candidate)
        elif candidate is not None:
            raise ValueError('Candidate is only valid for validation requests')
        self.cancel()
        self.reap()
        if budget is None:
            budget = 5.0 if kind == 'validate' or difficulty == 'very_hard' else 1.5
        budget = float(budget)
        if not math.isfinite(budget) or budget < 0:
            raise ValueError('AI budget must be finite and nonnegative')
        from app_paths import default_worker_directory
        worker_root = self.worker_directory if self.worker_directory is not None else default_worker_directory()
        if os.name == 'nt':
            from worker_storage import WorkerDirectory
            directory = WorkerDirectory(root=worker_root)
        else:
            directory = tempfile.TemporaryDirectory(prefix='renju-ai-', dir=worker_root)
        try:
            root = Path(directory.name)
            token = uuid.uuid4().hex
            request = {'token': token, 'kind': kind, 'difficulty': difficulty,
                       'player': int(player), 'move_count': int(move_count), 'budget': budget,
                       'board': {'size': board.size, 'win_length': board.win_length,
                                 'grid': board.grid.tolist(), 'last_move': board.last_move}}
            if request['board']['last_move'] is not None:
                request['board']['last_move'] = [int(x) for x in board.last_move]
            if context is not None:
                request['validation_context'] = context
            request_path = root / 'request.json'
            request_path.write_text(json.dumps(request), encoding='utf-8')
            # No captured pipes/queues: this is safe on Windows and detached from UI.
            if getattr(sys, 'frozen', False):
                command = [sys.executable, '--ai-worker', str(request_path)]
            else:
                command = [sys.executable, '-B', str(Path(__file__).with_name('ai_worker.py')), str(request_path)]
            worker_env = os.environ.copy()
            # AI uses scalar/grid logic, not BLAS. Thread pools only reserve memory
            # and oversubscribe a tiny worker; set before importing NumPy there.
            worker_env.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
            kwargs = {'stdin': subprocess.DEVNULL, 'stdout': subprocess.DEVNULL,
                      'stderr': subprocess.DEVNULL, 'env': worker_env}
            if os.name == 'nt':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            process = subprocess.Popen(command, **kwargs)
        except Exception as primary:
            try:
                directory.cleanup()
            except OSError as cleanup:
                self.orphan_directories.append(directory)
                primary.add_note('Worker directory cleanup pending: ' + str(cleanup))
            raise
        resources = None
        try:
            from worker_limits import ProcessBudget
            resources = ProcessBudget(process, self.memory_limit_mb)
        except (OSError, ValueError, TypeError):
            # A tiny worker can finish before job assignment; its work is done
            # and final result still safe to read. Otherwise fail closed.
            if process.poll() is None:
                # Keep ownership even if termination itself fails. No worker
                # may escape the adapter's retired/reap lifecycle on this path.
                failed = _Task(process, directory, token, position_key(board, player, move_count),
                               time.perf_counter(), budget)
                self.retired.append(failed)
                try:
                    process.terminate()
                except OSError:
                    try:
                        process.kill()
                    except OSError:
                        pass
                try:
                    process.wait(timeout=0.1)
                except subprocess.TimeoutExpired:
                    try:
                        process.kill()
                    except OSError:
                        pass
                self.reap()
                raise
        self.task = _Task(process, directory, token, position_key(board, player, move_count),
                          time.perf_counter(), budget, resources=resources, kind=kind,
                          candidate=candidate, validation_context=context)
        self.last_info = {'phase': 'starting', 'elapsed': 0.0,
                          'resource_limits': resources.metadata if resources else {'enforced': False, 'diagnostic': 'worker already exited'}}
        return token

    @staticmethod
    def _validation_packet_valid(task, result):
        """Reject unbound, partial or contradictory verdicts before cache handoff."""
        context = result.get('validation_context')
        context_matches = (isinstance(context, dict) and
                           json.dumps(context, sort_keys=True, separators=(',', ':')) ==
                           json.dumps(task.validation_context, sort_keys=True, separators=(',', ':')))
        if (result.get('kind') != 'validate' or result.get('done') is not True
                or result.get('move') is not None or not context_matches
                or not _candidate_shape(result.get('candidate'))
                or tuple(result['candidate']) != task.candidate):
            return False
        state, complete = result.get('adjudication'), result.get('validation_complete')
        verdict = result.get('verdict')
        if state == 'unknown':
            return complete is False and verdict is None
        if state not in ('legal', 'illegal') or complete is not True or not isinstance(verdict, dict):
            return False
        if set(verdict) != {'legal', 'win', 'reason'}:
            return False
        legal, win, reason = verdict['legal'], verdict['win'], verdict['reason']
        if type(legal) is not bool or type(win) is not bool or not isinstance(reason, str):
            return False
        if legal != (state == 'legal') or win and not legal:
            return False
        if legal:
            if win:
                allowed = {'win_connect_n'} if task.position[1] != 5 else {'win_exact_five', 'win_overline'}
                if task.position[4] == 1 and task.position[1] == 5:
                    allowed = {'win_exact_five'}
                return reason in allowed
            return reason == 'legal_nonterminal'
        return not win and reason in {'occupied', 'opening', 'out_of_bounds', 'invalid_player',
                                      'forbidden_overline', 'forbidden_double_four', 'forbidden_double_three'}

    def _read_result(self, task, force=False):
        now = time.perf_counter()
        if not force and now < task.read_after:
            return
        task.read_after = now + 0.03
        try:
            result = json.loads((Path(task.directory.name) / 'result.json').read_text(encoding='utf-8'))
            if not isinstance(result, dict) or result.get('token') != task.token:
                return
            if type(result.get('done', False)) is not bool:
                return
            if task.kind == 'validate' and not self._validation_packet_valid(task, result):
                return
            # Legacy move progress is intentionally accepted without kind;
            # adjudication packets must never masquerade as engine moves.
            if task.kind != 'validate' and result.get('kind', task.kind) != task.kind:
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
            if 'invalid_cells' in result and (not isinstance(result['invalid_cells'], list) or any(
                    not isinstance(p, list) or len(p) != 2 or
                    not all(type(x) is int for x in p) for p in result['invalid_cells'])):
                return
            if task.resources is not None:
                result['resource_limits'] = task.resources.metadata
            task.result = result
            self.last_info = result
        except (OSError, ValueError, OverflowError):
            pass

    def poll(self, board, player, move_count):
        self.reap()
        task = self.task
        if task is None:
            return None
        if (task.position != position_key(board, player, move_count)
                or task.kind == 'validate' and task.validation_context !=
                validation_context(board, player, move_count, task.candidate)):
            self.cancel()
            return None
        self._read_result(task)
        expired = time.perf_counter() - task.started >= task.budget + self.startup_grace
        exited = task.process.poll() is not None
        if exited or expired:
            # Fast workers can finish between throttled progress reads.
            self._read_result(task, force=True)
        done = bool(task.result and task.result.get('done'))
        if not (expired or exited or done):
            return None
        result = dict(task.result or {'move': None, 'error': 'Worker ended without a result'})
        result['timed_out'] = expired and not done
        result['resource_limits'] = task.resources.metadata if task.resources else {'enforced': False, 'diagnostic': 'worker exited before limit attached'}
        if task.kind == 'validate' and not task.result:
            result.update(kind='validate', candidate=list(task.candidate),
                          validation_context=task.validation_context, adjudication='unknown',
                          validation_complete=False, verdict=None,
                          error=result.get('error') or 'Rule validation incomplete')
        self._retire(task)
        self.task = None
        if task.kind == 'move' and result.get('move') is not None:
            move = result['move']
            valid_shape = (_candidate_shape(move) and board.is_within_bounds(*move)
                           and board.is_empty(*move) and board._opening_allows(*move, move_count))
            from board import RuleValidationTimeout
            try:
                legal = valid_shape and board.is_valid_move(*move, player, move_count)
            except RuleValidationTimeout:
                # UNKNOWN is not an illegal verdict. Preserve the exact
                # candidate separately; only a validate request may clear it.
                legal = None
                result['validation_pending_move'] = tuple(move)
                result['validation_required'] = True
                result['move'] = None
                result['phase'] = 'deferred rule validation'
            if legal is False:
                result.update(move=None, error=result.get('error') or 'Rejected invalid worker result')
            elif legal:
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

    def _reap_retired(self, wait_timeout):
        """Attempt every task once, retaining all incomplete cleanup for retry."""
        remaining, errors = [], []
        for task in self.retired:
            try:
                if task.process.poll() is None:
                    # Terminate may have failed or not taken effect. A failed
                    # kill is harmless only if the child meanwhile exited.
                    try:
                        task.process.kill()
                    except OSError:
                        if task.process.poll() is None:
                            raise
                if wait_timeout == 0 and task.process.poll() is None:
                    # Normal polling/cancellation must not wait for a live
                    # worker or remove files it may still be using.
                    remaining.append(task)
                    continue
                task.process.wait(timeout=wait_timeout)
                if task.resources is not None:
                    task.resources.close()
                task.directory.cleanup()
            except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
                # In particular, a failed native CloseHandle deliberately
                # remains owned by ProcessBudget. Never drop that task or let
                # one failure prevent attempts on the other retired children.
                remaining.append(task)
                errors.append(exc)
        self.retired = remaining
        return errors

    def _reap_directories(self):
        remaining, errors = [], []
        for directory in self.orphan_directories:
            try:
                directory.cleanup()
            except OSError as exc:
                remaining.append(directory)
                errors.append(exc)
        self.orphan_directories = remaining
        return errors

    def reap(self):
        self._reap_retired(wait_timeout=0)
        self._reap_directories()

    def close(self):
        """Bounded cleanup; raise on incomplete work while retaining ownership.

        Callers must retain this runner and retry after a transient failure.
        Returning normally means every owned child, job and directory closed.
        """
        if self.task is not None:
            self._retire(self.task)
            self.task = None
        errors = self._reap_retired(wait_timeout=1.0) + self._reap_directories()
        if errors:
            failure = OSError(f'Worker cleanup incomplete for {len(self.retired)} task(s); retry close()')
            for error in errors:
                failure.add_note(f'{type(error).__name__}: {error}')
            raise failure from errors[0]
