"""Easy/Normal policies and the conservative Phase A Hard search core.

Hard remains iterative-deepening alpha-beta minimax with Zobrist hashing,
bounded transpositions and line-pattern evaluation; no threat-space solver.
"""
from collections import OrderedDict
from functools import lru_cache
import logging
import math
import random
import time

import numpy as np
from board import Board, EMPTY, BLACK as BOARD_BLACK, WHITE as BOARD_WHITE

logger = logging.getLogger(__name__)
ZOBRIST_PLAYERS = {BOARD_BLACK: 0, BOARD_WHITE: 1}
NUM_ZOBRIST_PLAYERS = 2


class AIBase:
    """Base class for different AI difficulties."""
    def __init__(self, player):
        self.player = player
        self.opponent = BOARD_WHITE if player == BOARD_BLACK else BOARD_BLACK

    def find_move(self, board: Board, move_count):
        raise NotImplementedError("Subclasses must implement find_move")


class AIEasy(AIBase):
    """Uniform random choice, preserving the original legal-cell order."""
    def find_move(self, board: Board, move_count):
        moves = [move for move in board.get_empty_cells()
                 if board.is_valid_move(*move, self.player, move_count)]
        return random.choice(moves) if moves else None


class AINormal(AIBase):
    """Immediate win/block, original pattern priorities, then random legal."""
    @staticmethod
    def _creates_pattern(board, r, c, player, pattern):
        text, length, indices = pattern
        opponent = BOARD_WHITE if player == BOARD_BLACK else BOARD_BLACK
        with board.temporary_move(r, c, player):
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                for offset in range(-length + 1, 1):
                    if -offset not in indices:
                        continue
                    states = []
                    for i in range(length):
                        nr, nc = r + (offset + i) * dr, c + (offset + i) * dc
                        states.append(str(board.grid[nr, nc])
                                      if board.is_within_bounds(nr, nc)
                                      else str(opponent))
                    if ''.join(states) == text:
                        return True
        return False

    def find_move(self, board: Board, move_count):
        empty = board.get_empty_cells()
        legal = [move for move in empty
                 if board.is_valid_move(*move, self.player, move_count)]
        for move in legal:
            with board.temporary_move(*move, self.player):
                if board.check_win(self.player)[0]:
                    return move
        # Opponent legality is independent of our permission to occupy a cell.
        for move in empty:
            if board.is_valid_move(*move, self.opponent, move_count + 1):
                with board.temporary_move(*move, self.opponent):
                    wins = board.check_win(self.opponent)[0]
                if wins and move in legal:
                    return move

        p, o, e = str(self.player), str(self.opponent), str(EMPTY)
        n = board.win_length
        def pattern(left, stone, count, right):
            return (left + stone * count + right, count + 2,
                    tuple(range(1, count + 1)))
        # For five these are exactly the original open/closed four/three
        # patterns, in the same row-major selection order. Custom Gomoku
        # shifts the same tiers to N-1 and N-2 stones.
        open_four = pattern(e, p, n - 1, e)
        closed_fours = (pattern(o, p, n - 1, e), pattern(e, p, n - 1, o))
        open_three = pattern(e, p, n - 2, e)
        opp_four = pattern(e, o, n - 1, e)
        opp_three = pattern(e, o, n - 2, e)
        priorities = ((self.player, (open_four,)),
                      (self.opponent, (opp_four,)),
                      (self.player, closed_fours),
                      (self.player, (open_three,)),
                      (self.opponent, (opp_three,)))
        for player, patterns in priorities:
            for move in empty:
                count = move_count if player == self.player else move_count + 1
                if not board.is_valid_move(*move, player, count):
                    continue
                if any(self._creates_pattern(board, *move, player, pat)
                       for pat in patterns) and move in legal:
                    return move
        return random.choice(legal) if legal else None


class _SearchInterrupted(Exception):
    """Internal cooperative deadline/cancellation unwind, never a score."""


class AIHard(AIBase):
    """Iterative-deepening minimax, alpha-beta, Zobrist TT and patterns."""
    PATTERN_SCORES = {
        # AI Player (self.player = p)
        "p_win": 10000000,  # Five in a row
        "p_open_four": 100000,  # _pppp_
        "p_closed_four": 10000,  # xpppp_ or _ppppx or edge cases
        "p_open_three": 5000,  # _ppp_
        "p_closed_three": 500,  # xppp_ or _pppx or edge cases
        "p_broken_three": 450,  # _p_pp_ or _pp_p_ (Slightly less than closed three)
        "p_open_two": 100,  # _pp_
        "p_closed_two": 10,  # xpp_ or _ppx or edge cases
        "p_broken_two": 5,  # p_p_ (Less valuable)

        # Opponent (self.opponent = o) - Negative scores, weighted higher for defense
        "o_win": -100000000,  # Opponent five (Loss)
        "o_open_four": -6000000,  # Block opponent open four - Critical (Increased abs value)
        "o_closed_four": -50000,  # Block opponent closed four
        "o_open_three": -150000, # Block opponent open three - Very important (Increased abs value)
        "o_closed_three": -5000,  # Block opponent closed three
        "o_broken_three": -4500, # Block opponent broken three
        "o_open_two": -1000,
        "o_closed_two": -100,
        "o_broken_two": -50,
    }


    def __init__(self, player, depth=2, time_limit_sec=1.5, *, seed=0,
                 tt_capacity=50000):
        super().__init__(player)
        self.max_depth = max(0, int(depth))
        self.time_limit = max(0.0, float(time_limit_sec))
        self.seed = int(seed)
        self.tt_capacity = max(0, int(tt_capacity))
        self.transposition_table = OrderedDict()
        self.zobrist_table = self._init_zobrist()
        self.current_hash = 0
        self.cancel_event = None
        self.progress_callback = None
        self.completed_depth = 0
        self.nodes = 0
        self.evaluations = 0
        self._deadline = None
        self._active_cancel_event = None
        self._search_started = None

    def _init_zobrist(self, size=19):
        # Local seeded generator: does not consume either global RNG stream.
        # Rebuilding for larger boards preserves determinism for that size.
        rng = np.random.default_rng(self.seed % (1 << 64))
        return rng.integers(1, 2**63 - 1, size=(size, size, 2), dtype=np.uint64)

    def _ensure_zobrist(self, size):
        if size > self.zobrist_table.shape[0]:
            self.zobrist_table = self._init_zobrist(size)
            self.transposition_table.clear()

    def _calculate_board_hash(self, board: Board):
        self._ensure_zobrist(board.size)
        h = 0
        for r, c in zip(*np.where(board.grid != EMPTY)):
            h ^= int(self.zobrist_table[r, c, ZOBRIST_PLAYERS[board.grid[r, c]]])
        return h

    def _check_interrupt(self):
        if (self._active_cancel_event is not None
                and self._active_cancel_event.is_set()):
            raise _SearchInterrupted()
        if self._deadline is not None and time.perf_counter() >= self._deadline:
            raise _SearchInterrupted()

    def _publish(self, callback, move, score=None, phase='search'):
        if callback is None:
            return
        progress = {'move': move, 'completed_depth': self.completed_depth,
                    'depth': self.completed_depth, 'score': score,
                    'nodes': self.nodes, 'evaluations': self.evaluations,
                    'elapsed': time.perf_counter() - self._search_started,
                    'phase': phase}
        # Observers must not be able to corrupt the move search or board state.
        try:
            callback(progress)
        except Exception:
            logger.exception('Hard progress callback failed')

    def find_move(self, board: Board, move_count, cancel_event=None,
                  progress_callback=None):
        """Return a legal fallback or the last *completed* depth's choice.

        A callback receives one dict for the verified fallback, tactical result,
        and every completed iteration. Cancellation returns the same safe best
        move, never a partial depth. Search exceptions propagate after all
        hypothetical board changes have been restored.
        """
        self._search_started = time.perf_counter()
        self._deadline = self._search_started + self.time_limit
        self._active_cancel_event = (cancel_event if cancel_event is not None
                                     else self.cancel_event)
        callback = progress_callback if progress_callback is not None else self.progress_callback
        self.completed_depth = self.nodes = self.evaluations = 0
        self.transposition_table.clear()  # root-scoped, bounded even within a turn
        best_move = None
        try:
            # Find one verified legal move before any deadline/cancel unwind.
            # With no legal move this necessarily scans the finite board.
            center = board.size // 2
            anchor_r, anchor_c = board.last_move if board.last_move is not None else (center, center)
            fallback_cells = sorted(board.get_empty_cells(), key=lambda move: (
                max(abs(move[0] - anchor_r), abs(move[1] - anchor_c)),
                abs(move[0] - center) + abs(move[1] - center), move[0], move[1]))
            for r, c in fallback_cells:
                if board.is_valid_move(r, c, self.player, move_count):
                    best_move = (int(r), int(c))
                    break
            if best_move is None:
                return None
            self._publish(callback, best_move, phase='fallback')
            self._check_interrupt()
            self.current_hash = self._calculate_board_hash(board)
            self._check_interrupt()

            empty = board.get_empty_cells()
            legal = []
            for move in empty:
                self._check_interrupt()
                if board.is_valid_move(*move, self.player, move_count):
                    legal.append(move)
                    with board.temporary_move(*move, self.player):
                        wins = board.check_win(self.player)[0]
                    self._check_interrupt()
                    if wins:
                        self._publish(callback, move, self.PATTERN_SCORES['p_win'], 'tactical')
                        return move
            legal_set = set(legal)
            for move in empty:
                self._check_interrupt()
                if not board.is_valid_move(*move, self.opponent, move_count + 1):
                    continue
                with board.temporary_move(*move, self.opponent):
                    wins = board.check_win(self.opponent)[0]
                self._check_interrupt()
                if wins and move in legal_set:
                    self._publish(callback, move, phase='tactical')
                    return move

            for depth in range(1, self.max_depth + 1):
                self._check_interrupt()
                moves = self._get_ordered_adjacent_moves(board, self.player, move_count)
                if not moves:
                    break
                alpha, score, depth_move = -math.inf, -math.inf, None
                for r, c in moves:
                    self._check_interrupt()
                    next_hash = self.current_hash ^ int(self.zobrist_table[r, c, ZOBRIST_PLAYERS[self.player]])
                    with board.temporary_move(r, c, self.player):
                        value = self._minimax(board, depth - 1, alpha, math.inf,
                                              False, move_count + 1, next_hash)
                    self._check_interrupt()
                    if value > score:
                        score, depth_move = value, (r, c)
                    alpha = max(alpha, score)
                # Only this point promotes a result: all root moves finished.
                self._check_interrupt()
                if depth_move is not None:
                    best_move = depth_move
                    self.completed_depth = depth
                    self._publish(callback, best_move, score)
            return best_move
        except _SearchInterrupted:
            return best_move
        finally:
            self._deadline = None
            self._active_cancel_event = None

    def _get_ordered_adjacent_moves(self, board: Board, player: int, move_count: int):
        """Radius-one neighborhood, deduplicated *before* expensive legality."""
        possible = set()
        occupied = list(zip(*np.where(board.grid != EMPTY)))
        if not occupied:
            possible.add((board.size // 2, board.size // 2))
        for r, c in occupied:
            self._check_interrupt()
            for dr in range(-1, 2):
                for dc in range(-1, 2):
                    nr, nc = int(r + dr), int(c + dc)
                    if board.is_within_bounds(nr, nc) and board.grid[nr, nc] == EMPTY:
                        possible.add((nr, nc))
        candidates = []
        for move in sorted(possible):
            self._check_interrupt()
            if board.is_valid_move(*move, player, move_count):
                candidates.append(move)
        # Stable coordinate tie breaks, independent of sets/global random state.
        candidates.sort(key=lambda move: (-self._heuristic_score_move_sim(
            board, *move, player, move_count), move))
        return candidates

    def _heuristic_score_move_sim(self, board: Board, r: int, c: int, player: int, move_count: int):
        return sum(board.is_within_bounds(r + dr, c + dc)
                   and board.grid[r + dr, c + dc] != EMPTY
                   for dr in range(-1, 2) for dc in range(-1, 2)
                   if dr or dc)

    def _tt_key(self, board, maximizing_player, move_count, board_hash):
        # last_move is terminal-check metadata, move_count controls opening.
        # Root player/settings prevent interpretation of a score in another game.
        return (int(board_hash), self.player, bool(maximizing_player),
                board.size, board.win_length, int(move_count),
                tuple(board.last_move) if board.last_move is not None else None,
                tuple(sorted(self.PATTERN_SCORES.items())))

    def _store_tt(self, key, score, depth, flag):
        if not self.tt_capacity:
            return
        old = self.transposition_table.get(key)
        if old is not None and old[1] > depth:
            return
        self.transposition_table[key] = (score, depth, flag)
        self.transposition_table.move_to_end(key)
        while len(self.transposition_table) > self.tt_capacity:
            self.transposition_table.popitem(last=False)

    def _minimax(self, board: Board, depth: int, alpha: float, beta: float,
                 maximizing_player: bool, move_count: int, current_board_hash):
        self._check_interrupt()
        self.nodes += 1
        # Root perspective, never the side-to-move perspective. Do not allow a
        # TT hit to bypass terminal metadata checks.
        if board.check_win(self.player)[0]:
            return self.PATTERN_SCORES['p_win'] + depth
        if board.check_win(self.opponent)[0]:
            return self.PATTERN_SCORES['o_win'] - depth
        self._check_interrupt()
        if not np.any(board.grid == EMPTY):
            return 0
        if depth <= 0:
            return self._evaluate_board(board)

        original_alpha, original_beta = alpha, beta
        key = self._tt_key(board, maximizing_player, move_count, current_board_hash)
        entry = self.transposition_table.get(key)
        # Exact requested remaining depth: terminal distance and heuristic
        # horizon differ by depth, so deeper results are not reused as exact.
        if entry is not None and entry[1] == depth:
            score, _, flag = entry
            if flag == 'exact':
                return score
            if flag == 'lowerbound':
                alpha = max(alpha, score)
            elif flag == 'upperbound':
                beta = min(beta, score)
            if alpha >= beta:
                return score

        player = self.player if maximizing_player else self.opponent
        opponent = self.opponent if maximizing_player else self.player
        moves = self._get_ordered_adjacent_moves(board, player, move_count)
        if not moves:
            return self._evaluate_board(board)

        # Preserve existing immediate win/block narrowing, now with correct
        # last_move and independent opponent legality. All probes unwind safely.
        winning = blocking = None
        for move in moves:
            self._check_interrupt()
            with board.temporary_move(*move, player):
                wins = board.check_win(player)[0]
            if wins:
                winning = move
                break
        if winning is None:
            for move in moves:
                self._check_interrupt()
                if not board.is_valid_move(*move, opponent, move_count + 1):
                    continue
                with board.temporary_move(*move, opponent):
                    wins = board.check_win(opponent)[0]
                if wins:
                    blocking = move
                    break
        if winning is not None or blocking is not None:
            moves = [winning if winning is not None else blocking]

        score = -math.inf if maximizing_player else math.inf
        for r, c in moves:
            self._check_interrupt()
            next_hash = int(current_board_hash) ^ int(self.zobrist_table[r, c, ZOBRIST_PLAYERS[player]])
            with board.temporary_move(r, c, player):
                value = self._minimax(board, depth - 1, alpha, beta,
                                      not maximizing_player, move_count + 1,
                                      next_hash)
            self._check_interrupt()
            if maximizing_player:
                score = max(score, value)
                alpha = max(alpha, score)
            else:
                score = min(score, value)
                beta = min(beta, score)
            if alpha >= beta:
                break
        # A deadline/cancel never stores an unfinished subtree as a TT score.
        self._check_interrupt()
        flag = ('upperbound' if score <= original_alpha else
                'lowerbound' if score >= original_beta else 'exact')
        self._store_tt(key, score, depth, flag)
        return score

    def _evaluate_board(self, board: Board):
        """Original most-significant-line pattern sum and defensive weights."""
        self.evaluations += 1
        total = 0
        for line in self._get_all_lines(board):
            self._check_interrupt()
            score = self._evaluate_line(line, board.win_length, board.size)
            if score >= self.PATTERN_SCORES['p_win']:
                return self.PATTERN_SCORES['p_win']
            if score <= self.PATTERN_SCORES['o_win']:
                return self.PATTERN_SCORES['o_win']
            total += score
            if score in (self.PATTERN_SCORES['o_open_four'],
                         self.PATTERN_SCORES['o_open_three']):
                total += score * 2
        # A heuristic estimate must never outrank an actual win or loss.
        return max(self.PATTERN_SCORES['o_win'] + 1,
                   min(self.PATTERN_SCORES['p_win'] - 1, total))

    def _get_all_lines(self, board: Board):
        grid, size = board.grid, board.size
        # Yield rather than materialize, retaining original line traversal order.
        for r in range(size):
            yield tuple(grid[r, :])
        for c in range(size):
            yield tuple(grid[:, c])
        for k in range(-size + 1, size):
            yield tuple(grid.diagonal(k))
        flipped = grid[:, ::-1]
        for k in range(-size + 1, size):
            yield tuple(flipped.diagonal(k))

    def _evaluate_line(self, line, win_length=5, board_size=None):
        # Full immutable context, including overridable score settings, avoids
        # cross-player/custom-rule cache contamination. The global LRU holds no
        # AI instances and is bounded across all searches.
        values = tuple(line)
        return _evaluate_line_cached(values, self.player, win_length,
                                     board_size if board_size is not None else len(values),
                                     tuple(self.PATTERN_SCORES.items()))


@lru_cache(maxsize=128)
def _line_patterns(player, win_length, scores_tuple):
    scores = dict(scores_tuple)
    opponent = BOARD_WHITE if player == BOARD_BLACK else BOARD_BLACK
    p, o, e = player, opponent, EMPTY
    patterns = []
    def add(pattern, name):
        patterns.append((pattern, scores[name]))
    add((p,) * win_length, 'p_win')
    add((o,) * win_length, 'o_win')
    for left, stone, right, name in (
            (e, p, e, 'p_open_four'), (e, o, e, 'o_open_four'),
            (o, p, e, 'p_closed_four'), (e, p, o, 'p_closed_four'),
            (p, o, e, 'o_closed_four'), (e, o, p, 'o_closed_four')):
        add((left,) + (stone,) * (win_length - 1) + (right,), name)
    add((e,) + (p,) * (win_length - 2) + (e,), 'p_open_three')
    add((e,) + (o,) * (win_length - 2) + (e,), 'o_open_three')
    # Five's two broken-three patterns keep their exact original order.
    if win_length >= 4:
        for stone, prefix in ((p, 'p'), (o, 'o')):
            for split in range(win_length - 3, 0, -1):
                add((e,) + (stone,) * split + (e,)
                    + (stone,) * (win_length - 2 - split) + (e,),
                    prefix + '_broken_three')
    for left, stone, right, name in (
            (o, p, e, 'p_closed_three'), (e, p, o, 'p_closed_three'),
            (p, o, e, 'o_closed_three'), (e, o, p, 'o_closed_three')):
        add((left,) + (stone,) * (win_length - 2) + (right,), name)
    return tuple(patterns)


@lru_cache(maxsize=65536)
def _evaluate_line_cached(line, player, win_length, board_size, scores_tuple):
    scores = dict(scores_tuple)
    opponent = BOARD_WHITE if player == BOARD_BLACK else BOARD_BLACK
    n = len(line)
    if n < win_length - 1:
        return 0
    patterns = list(_line_patterns(player, win_length, scores_tuple))
    # Preserve the original edge-pattern meaning: only add the short pattern
    # if it is present at the appropriate edge, then use the same greedy scan.
    for count, tier in ((win_length - 1, 'closed_four'),
                        (win_length - 2, 'closed_three')):
        length = count + 1
        if n >= length:
            for stone, prefix in ((player, 'p'), (opponent, 'o')):
                left = (stone,) * count + (EMPTY,)
                right = (EMPTY,) + (stone,) * count
                if line[:length] == left:
                    patterns.append((left, scores[prefix + '_' + tier]))
                if line[-length:] == right:
                    patterns.append((right, scores[prefix + '_' + tier]))
    patterns.sort(key=lambda item: len(item[0]), reverse=True)
    result, i = 0, 0
    while i < n:
        for pattern, score in patterns:
            length = len(pattern)
            if line[i:i + length] != pattern:
                continue
            # On five's black lines an overline is not itself a win. Crossing
            # exact-five wins are handled by Board's terminal check.
            stone = pattern[0]
            is_win = score in (scores['p_win'], scores['o_win'])
            if (is_win and win_length == 5 and stone == BOARD_BLACK
                    and ((i > 0 and line[i - 1] == stone)
                         or (i + length < n and line[i + length] == stone))):
                continue
            if is_win:
                return score
            if abs(score) > abs(result):
                result = score
            i += length
            break
        else:
            i += 1
    return result


def create_ai(difficulty: str, player):
    """Factory keeps Hard independent from any future Very Hard engine."""
    if difficulty == 'easy':
        return AIEasy(player)
    if difficulty == 'normal':
        return AINormal(player)
    if difficulty == 'hard':
        return AIHard(player)
    logger.warning("Unknown AI difficulty %r; defaulting to Easy", difficulty)
    return AIEasy(player)
