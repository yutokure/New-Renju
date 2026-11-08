"""Independent Very Hard general engine, with separate tactical certificates.

No AIHard inheritance or evaluation reuse. Search estimates never imply proof.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
import math
import logging
import random
import operator
import time

from renju_rules import Rules

EMPTY, BLACK, WHITE = 0, 1, 2
DIRECTIONS = ((0, 1), (1, 0), (1, 1), (1, -1))
MATE = 1_000_000_000
ESTIMATE_LIMIT = 1_000_000
logger = logging.getLogger(__name__)


class SearchStopped(Exception):
    pass


@lru_cache(maxsize=32)
def geometry(size, target):
    windows, affected = [], [[] for _ in range(size * size)]
    neighbors = []
    for cell in range(size * size):
        r, c = divmod(cell, size)
        neighbors.append(tuple(rr * size + cc for rr in range(max(0, r-2), min(size, r+3))
                               for cc in range(max(0, c-2), min(size, c+3)) if (rr, cc) != (r, c)))
        for dr, dc in DIRECTIONS:
            er, ec = r + (target - 1) * dr, c + (target - 1) * dc
            if not (0 <= er < size and 0 <= ec < size):
                continue
            window = tuple((r + j*dr)*size + c + j*dc for j in range(target))
            before = (r-dr)*size+c-dc if 0 <= r-dr < size and 0 <= c-dc < size else None
            after = (er+dr)*size+ec+dc if 0 <= er+dr < size and 0 <= ec+dc < size else None
            idx = len(windows)
            windows.append((window, before, after))
            for p in set(window) | {x for x in (before, after) if x is not None}:
                affected[p].append(idx)
    rng = random.Random(0x52454E4A55 + size * 8 + target)
    zobrist = tuple((rng.getrandbits(64), rng.getrandbits(64)) for _ in neighbors)
    return tuple(windows), tuple(tuple(x) for x in affected), tuple(neighbors), zobrist


@lru_cache(maxsize=512)
def _window_score(own, other, openness, target):
    if other or not own:
        return 0
    # These are estimates of urgency, NOT proof values. A blocked N-1 is
    # useful; an N-2 with two open ends is a future preparation.
    distance = target - own
    base = {0: 100000, 1: 4500, 2: 300, 3: 22, 4: 3}.get(distance, 1)
    return base * (1 + openness)


class Position:
    """Flat make/unmake position with incremental windows, evaluation and hash."""
    def __init__(self, cells, size, target):
        self.cells = list(cells)
        self.size, self.target = size, target
        self.windows, self.affected, self.neighbors, self.zobrist = geometry(size, target)
        self.black_counts, self.white_counts = [], []
        self.scores = []
        self.total = 0
        self.hash = 0
        self.occupied = set()
        self.threat_windows = {BLACK: set(), WHITE: set()}
        for i, p in enumerate(self.cells):
            if p:
                self.occupied.add(i)
                self.hash ^= self.zobrist[i][p-1]
        for window, _, _ in self.windows:
            self.black_counts.append(sum(self.cells[p] == BLACK for p in window))
            self.white_counts.append(sum(self.cells[p] == WHITE for p in window))
        for i in range(len(self.windows)):
            value = self._score(i)
            self.scores.append(value)
            self.total += value
            self._refresh_threat_window(i)

    def _refresh_threat_window(self, w):
        for player, own, other in ((BLACK, self.black_counts[w], self.white_counts[w]),
                                   (WHITE, self.white_counts[w], self.black_counts[w])):
            if own == self.target-1 and other == 0:
                self.threat_windows[player].add(w)
            else:
                self.threat_windows[player].discard(w)

    def _score(self, w):
        _, before, after = self.windows[w]
        b, v = self.black_counts[w], self.white_counts[w]
        bo = sum(p is not None and self.cells[p] != WHITE for p in (before, after))
        wo = sum(p is not None and self.cells[p] != BLACK for p in (before, after))
        return _window_score(b, v, bo, self.target) - _window_score(v, b, wo, self.target)

    def make(self, cell, player):
        assert self.cells[cell] == EMPTY
        self.cells[cell] = player
        self.occupied.add(cell)
        self.hash ^= self.zobrist[cell][player-1]
        for w in self.affected[cell]:
            if cell in self.windows[w][0]:
                (self.black_counts if player == BLACK else self.white_counts)[w] += 1
            value = self._score(w)
            self.total += value - self.scores[w]
            self.scores[w] = value
            self._refresh_threat_window(w)

    def unmake(self, cell, player):
        self.cells[cell] = EMPTY
        self.occupied.remove(cell)
        self.hash ^= self.zobrist[cell][player-1]
        for w in self.affected[cell]:
            if cell in self.windows[w][0]:
                (self.black_counts if player == BLACK else self.white_counts)[w] -= 1
            value = self._score(w)
            self.total += value - self.scores[w]
            self.scores[w] = value
            self._refresh_threat_window(w)

    @contextmanager
    def played(self, cell, player):
        self.make(cell, player)
        try:
            yield
        finally:
            self.unmake(cell, player)

    def wins_at(self, cell, player):
        r, c = divmod(cell, self.size)
        for dr, dc in DIRECTIONS:
            count = 1
            for sign in (1, -1):
                rr, cc = r+sign*dr, c+sign*dc
                while 0 <= rr < self.size and 0 <= cc < self.size and self.cells[rr*self.size+cc] == player:
                    count += 1
                    rr, cc = rr+sign*dr, cc+sign*dc
            if count == self.target or (not (player == BLACK and self.target == 5) and count > self.target):
                return True
        return False

    def immediate_wins(self, player, rules, move_count):
        possible = set()
        for i in self.threat_windows[player]:
            possible.update(p for p in self.windows[i][0] if not self.cells[p])
        wins = []
        for cell in sorted(possible):
            if not rules.opening_allows(cell, move_count):
                continue
            self.cells[cell] = player
            try:
                if self.wins_at(cell, player):
                    wins.append(cell)
            finally:
                self.cells[cell] = EMPTY
        return wins

    def evaluate(self, player):
        score = self.total if player == BLACK else -self.total
        return max(-ESTIMATE_LIMIT, min(ESTIMATE_LIMIT, score))

    def candidates(self, player, rules, count, check, preferred=None, limit=18):
        wins = self.immediate_wins(player, rules, count)
        if wins:
            return wins
        opponent = 3-player
        blocks = self.immediate_wins(opponent, rules, count+1)
        if blocks:
            # All exact blocking squares, never dropped by general beam cap.
            return [p for p in blocks if rules.is_legal(self.cells, p, player, count, check)]
        possible = set()
        for stone in self.occupied:
            possible.update(self.neighbors[stone])
        if not possible:
            possible.add((self.size//2)*self.size+self.size//2)
        possible.difference_update(self.occupied)
        counts = self.black_counts if player == BLACK else self.white_counts
        others = self.white_counts if player == BLACK else self.black_counts
        ranked = []
        center = self.size//2
        for cell in possible:
            check()
            if not rules.opening_allows(cell, count):
                continue
            attack = defense = 0
            axes = set()
            for w in self.affected[cell]:
                window, before, after = self.windows[w]
                if cell not in window:
                    continue
                a, d = counts[w], others[w]
                if not d:
                    value = _window_score(a+1, 0, 1, self.target)
                    attack += value
                    if a >= self.target-3:
                        # Direction from the window indices, including broken shapes.
                        axes.add(window[1]-window[0])
                if not a:
                    defense += _window_score(d+1, 0, 1, self.target)
            value = attack + defense * 1.15 + len(axes)**2 * 35
            if cell == preferred:
                value += MATE
            ranked.append((-value, abs(cell//self.size-center)+abs(cell%self.size-center), cell))
        ranked.sort()
        selected = []
        for _, _, cell in ranked:
            check()
            if rules.is_legal(self.cells, cell, player, count, check):
                selected.append(cell)
            if len(selected) >= limit:
                break
        # Opening constraints can exclude all local candidates; scan legal cells
        # rather than misreporting no move (not common in the legacy opening).
        if not selected:
            for cell in range(len(self.cells)):
                check()
                if not self.cells[cell] and rules.is_legal(self.cells, cell, player, count, check):
                    return [cell]
        return selected


@dataclass(slots=True)
class _TTEntry:
    depth: int
    score: float
    flag: str
    move: object
    generation: int


class AIVeryHard:
    """Independent tactical-first iterative negamax engine; default 5 seconds."""
    def __init__(self, player, time_limit_sec=5.0, max_depth=8, *,
                 tactical_fraction=0.30, tt_capacity=60000, candidate_limit=18):
        if isinstance(player, bool):
            raise ValueError('player must be BLACK or WHITE')
        try:
            player = operator.index(player)
        except TypeError as exc:
            raise ValueError('player must be BLACK or WHITE') from exc
        if player not in (BLACK, WHITE):
            raise ValueError('player must be BLACK or WHITE')
        if not math.isfinite(float(time_limit_sec)) or float(time_limit_sec) < 0:
            raise ValueError('time_limit_sec must be finite and nonnegative')
        if type(max_depth) is not int or not 0 <= max_depth <= 64:
            raise ValueError('max_depth must be an integer in 0..64')
        if type(tt_capacity) is not int or not 0 <= tt_capacity <= 1_000_000:
            raise ValueError('tt_capacity must be an integer in 0..1000000')
        if type(candidate_limit) is not int or not 1 <= candidate_limit <= 361:
            raise ValueError('candidate_limit must be an integer in 1..361')
        if not math.isfinite(float(tactical_fraction)) or not 0 <= tactical_fraction <= 0.8:
            raise ValueError('tactical_fraction must be finite in 0..0.8')
        self.player, self.opponent = player, 3-player
        self.time_limit = float(time_limit_sec)
        self.max_depth = max_depth
        self.tactical_fraction = float(tactical_fraction)
        self.tt_capacity = tt_capacity
        self.candidate_limit = candidate_limit
        self.tt = {}
        self.generation = 0
        self.completed_depth = self.nodes = self.evaluations = 0
        self.proof_status = 'UNKNOWN'
        self.principal_variation = ()
        self.cancel_event = None
        self.progress_callback = None

    def _check(self):
        if time.perf_counter() >= self.deadline or (self.active_cancel is not None and self.active_cancel.is_set()):
            raise SearchStopped()

    def _publish(self, callback, move, phase, score=None):
        if callback:
            try:
                callback({'move': divmod(move, self.pos.size) if move is not None else None,
                          'completed_depth': self.completed_depth, 'nodes': self.nodes,
                          'evaluations': self.evaluations, 'elapsed': time.perf_counter()-self.started,
                          'score': score, 'phase': phase, 'proof_status': self.proof_status})
            except Exception:
                logger.exception('Very Hard progress observer failed')

    def find_move(self, board, move_count, cancel_event=None, progress_callback=None):
        self.started = time.perf_counter()
        self.deadline = self.started + self.time_limit
        self.active_cancel = cancel_event if cancel_event is not None else self.cancel_event
        callback = progress_callback if progress_callback is not None else self.progress_callback
        self.rules = Rules(board.size, board.win_length)
        self.pos = Position(self.rules.flatten(board.grid), board.size, board.win_length)
        self.completed_depth = self.nodes = self.evaluations = 0
        self.proof_status = 'UNKNOWN'
        self.principal_variation = ()
        self.generation += 1
        self.tt.clear()  # Scores include root-relative distance; do not cross roots.
        # Terminal root detection is all-board, independent of stale/None
        # last_move metadata. Never play beyond a completed game.
        winners = set()
        for stone in self.pos.occupied:
            color = self.pos.cells[stone]
            if self.pos.wins_at(stone, color):
                winners.add(color)
        if winners:
            if len(winners) == 1:
                self.proof_status = 'PROVEN_WIN' if self.player in winners else 'PROVEN_LOSS'
            self._publish(callback, None, 'terminal root')
            return None
        center = board.size//2
        cells = sorted((i for i,p in enumerate(self.pos.cells) if not p),
                       key=lambda i: (abs(i//board.size-center)+abs(i%board.size-center), i))
        best = None
        # Verify fallback even with zero time; adapter provides independent cap.
        for cell in cells:
            if self.rules.is_legal(self.pos.cells, cell, self.player, move_count):
                best = cell
                break
        if best is None:
            return None
        self._publish(callback, best, 'legal fallback')
        if move_count == 0 and self.rules.opening_policy == 'simplified-center-opening':
            self._publish(callback, best, 'forced opening')
            return divmod(best, board.size)
        try:
            self._check()
            wins = self.pos.immediate_wins(self.player, self.rules, move_count)
            if wins:
                self.proof_status = 'PROVEN_WIN'
                self._publish(callback, wins[0], 'immediate win', MATE-1)
                return divmod(wins[0], board.size)
            blocks = self.pos.immediate_wins(self.opponent, self.rules, move_count+1)
            if blocks:
                legal_blocks = [x for x in blocks if self.rules.is_legal(self.pos.cells, x, self.player, move_count, self._check)]
                if legal_blocks:
                    best = legal_blocks[0]
                    self._publish(callback, best, 'forced defense')
                if len(blocks) == 1 and legal_blocks:
                    # A sole immediate completion has a sole nonlosing block.
                    return divmod(best, board.size)
                self.proof_status = 'PROVEN_LOSS'
                self._publish(callback, best, 'certified immediate loss', -MATE+2)
                return divmod(best, board.size)
            best = self._tactical(move_count, best, callback)
            if self.proof_status == 'PROVEN_WIN':
                return divmod(best, board.size)
            for depth in range(1, self.max_depth+1):
                self._check()
                moves = self.pos.candidates(self.player, self.rules, move_count,
                                            self._check, best, self.candidate_limit)
                if not moves:
                    break
                alpha, value, iteration_best = -MATE, -MATE, None
                for cell in moves:
                    self._check()
                    with self.pos.played(cell, self.player):
                        score = -self._negamax(depth-1, -MATE, -alpha, self.opponent,
                                               move_count+1, cell, 1)
                    if score > value:
                        value, iteration_best = score, cell
                    alpha = max(alpha, score)
                self._check()
                best = iteration_best if iteration_best is not None else best
                self.completed_depth = depth
                self._publish(callback, best, 'general search (estimate)', value)
                if abs(value) >= MATE-len(self.pos.cells):
                    # Terminal value found in a candidate-restricted search is
                    # deliberately NOT promoted to a global proof certificate.
                    break
        except SearchStopped:
            pass
        return divmod(best, board.size)

    def _tactical(self, count, best, callback):
        # Independent module; no Hard search/evaluation dependency.
        if self.tactical_fraction <= 0:
            return best
        from tactics import TacticalSolver, ProofStatus
        tactical_deadline = min(self.deadline, self.started + self.time_limit*self.tactical_fraction)
        def check():
            self._check()
            if time.perf_counter() >= tactical_deadline:
                raise SearchStopped()
        try:
            vcf_deadline = self.started + self.time_limit*self.tactical_fraction*0.60
            def vcf_check():
                check()
                if time.perf_counter() >= vcf_deadline:
                    raise SearchStopped()
            result = None
            try:
                result = TacticalSolver(self.rules, check=vcf_check, node_limit=6000,
                                        max_depth=9, mode='vcf').solve(self.pos.cells, self.player, count)
            except SearchStopped:
                check()  # Overall/tactical exhaustion still propagates.
            if result is None or result.status != ProofStatus.PROVEN_WIN:
                # VCT proof has full defender enumeration; bounded work may
                # return UNKNOWN, which never substitutes for a win/loss proof.
                result = TacticalSolver(self.rules, check=check, node_limit=6000,
                                        max_depth=7, mode='vct').solve(self.pos.cells, self.player, count)
            if result.status == ProofStatus.PROVEN_WIN and result.move is not None:
                self.proof_status = 'PROVEN_WIN'
                self.principal_variation = result.pv
                best = result.move
                self._publish(callback, best, 'certified tactical win', MATE-1)
            return best
        except SearchStopped:
            return best

    def _negamax(self, depth, alpha, beta, player, count, last, ply):
        self._check()
        self.nodes += 1
        if self.pos.wins_at(last, 3-player):
            return -MATE+ply
        if len(self.pos.occupied) == len(self.pos.cells):
            return 0
        # At horizon, resolve immediate wins and obligations before estimating.
        wins = self.pos.immediate_wins(player, self.rules, count)
        if wins:
            return MATE-ply-1
        threats = self.pos.immediate_wins(3-player, self.rules, count+1)
        if len(threats) > 1:
            return -MATE+ply+2
        if depth <= 0 and not threats:
            self.evaluations += 1
            return self.pos.evaluate(player)
        if depth < -3:
            self.evaluations += 1
            return self.pos.evaluate(player)
        key = (self.pos.hash, player, count)
        entry = self.tt.get(key)
        a0, b0 = alpha, beta
        if entry and entry.depth == depth:
            if entry.flag == 'exact':
                return entry.score
            if entry.flag == 'lower':
                alpha = max(alpha, entry.score)
            else:
                beta = min(beta, entry.score)
            if alpha >= beta:
                return entry.score
        moves = self.pos.candidates(player, self.rules, count, self._check,
                                    entry.move if entry else None,
                                    max(8, self.candidate_limit-4))
        if not moves:
            # No legal blocking square loses; ordinary quiet no-move is not a
            # winning certificate. The app does not implement tournament pass.
            return -MATE+ply+1 if threats else 0
        value, best = -MATE, None
        for cell in moves:
            with self.pos.played(cell, player):
                score = -self._negamax(depth-1, -beta, -alpha, 3-player,
                                       count+1, cell, ply+1)
            if score > value:
                value, best = score, cell
            alpha = max(alpha, score)
            if alpha >= beta:
                break
        self._check()
        flag = 'upper' if value <= a0 else 'lower' if value >= b0 else 'exact'
        if self.tt_capacity:
            if len(self.tt) >= self.tt_capacity:
                # Bounded root-scoped generations; clear is cheap and correct.
                self.tt.clear()
            self.tt[key] = _TTEntry(depth, value, flag, best, self.generation)
        return value
