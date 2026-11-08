"""Independent, bounded VCF/VCT certificates over the shared placement Rules.

Attacker move generation is deliberately incomplete. Failure, an exhausted
budget, and a refuted *nominated* root therefore all mean UNKNOWN, not a game
loss. Only an already terminal opponent position produces public PROVEN_LOSS.
No Board, AI, evaluator, UI, or mutable global search state is imported here.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from operator import index as integer_index
from time import perf_counter
from typing import Callable, Optional, Tuple

from renju_rules import BLACK, WHITE, EMPTY, DIRECTIONS


class ProofStatus(str, Enum):
    PROVEN_WIN = "proven_win"
    PROVEN_LOSS = "proven_loss"
    UNKNOWN = "unknown"


class TacticalInterrupted(Exception):
    """Our node/time limit; unrelated caller cancellation exceptions propagate."""


@dataclass(frozen=True, slots=True)
class DefenseBranch:
    move: Optional[int]  # None is a conservative defender pass.
    continuation: "TacticalCertificate"


@dataclass(frozen=True, slots=True)
class TacticalCertificate:
    """A strategy tree, not just a cooperative principal variation.

    ``winning_square_partition`` covers every nonwinning defender placement
    outside the listed squares by an immediate win, after an all-board defender
    counterwin check. ``forced_block`` additionally records its sole legal
    prolonging reply. ``all_defenses`` records EVERY legal placement and pass.
    A terminal node is a rule-checked winning attacker placement.
    """
    kind: str
    attacker_move: Optional[int]
    winning_squares: Tuple[int, ...] = ()
    defenses: Tuple[DefenseBranch, ...] = ()
    includes_pass: bool = False
    pass_winning_squares: Tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class TacticalResult:
    status: ProofStatus
    move: Optional[int]
    pv: Tuple[int, ...]
    nodes: int
    reason: str = ""
    depth: int = 0
    ruleset: str = ""
    certificate: Optional[TacticalCertificate] = None


@dataclass(frozen=True, slots=True)
class _Win:
    pv: Tuple[int, ...]
    certificate: TacticalCertificate
    depth: int


@lru_cache(maxsize=16)
def _lines(size):
    lines = []
    for dr, dc in DIRECTIONS:
        for row in range(size):
            for col in range(size):
                if 0 <= row - dr < size and 0 <= col - dc < size:
                    continue
                line = []
                r, c = row, col
                while 0 <= r < size and 0 <= c < size:
                    line.append(r * size + c)
                    r, c = r + dr, c + dc
                lines.append(tuple(line))
    return tuple(lines)


@lru_cache(maxsize=32)
def _windows(size, target):
    return tuple(line[start:start + target] for line in _lines(size)
                 for start in range(len(line) - target + 1))


def is_winning_move(cells, index, player, rules):
    """Geometric immediate win on an EMPTY point; does not check the opening.

    Black connect-five needs a maximal exact five in ANY axis (priority over
    simultaneous fouls/overlines). White and custom connect-N need >= target.
    Consequently a positive geometric result needs no recursive black legality.
    """
    n, target = rules.size, rules.win_length
    if player not in (BLACK, WHITE) or not 0 <= index < n * n or cells[index]:
        return False
    row, col = divmod(index, n)
    exact = player == BLACK and target == 5
    for dr, dc in DIRECTIONS:
        length = 1
        for sign in (-1, 1):
            r, c = row + sign * dr, col + sign * dc
            while 0 <= r < n and 0 <= c < n and cells[r * n + c] == player:
                length += 1
                r, c = r + sign * dr, c + sign * dc
        if (length == target if exact else length >= target):
            return True
    return False


def winning_moves(cells, player, move_count, rules, check=None):
    """ALL legal immediate wins, including remote lines and white overlines.

    Scans line geometry, not 225 recursive Rules.classify calls. Each gap's
    adjoining maximal runs are counted. Exact-five precedence means a black
    geometric win is fully legal, subject only to opening_allows. Input is never
    modified. ``check`` is polled even on the sparse-stone fast exit.
    """
    if check is not None:
        check()
    if len(cells) != rules.size * rules.size:
        raise ValueError("Flat board length does not match Rules.size")
    if player not in (BLACK, WHITE):
        raise ValueError("Invalid player")
    target = rules.win_length
    if cells.count(player) < target - 1:
        return ()
    exact = player == BLACK and target == 5
    found = set()
    for line in _lines(rules.size):
        if check is not None:
            check()
        if len(line) < target:
            continue
        left = 0
        for offset, cell in enumerate(line):
            value = cells[cell]
            if value == player:
                left += 1
                continue
            if value == EMPTY:
                right = 0
                cursor = offset + 1
                while cursor < len(line) and cells[line[cursor]] == player:
                    right += 1
                    cursor += 1
                length = left + 1 + right
                wins = length == target if exact else length >= target
                if wins and rules.opening_allows(cell, move_count):
                    found.add(cell)
            left = 0
    return tuple(sorted(found))


def _geometric_candidates(cells, player, rules, mode, check):
    """Cheap, incomplete ordering; every returned move still needs full legality."""
    # Only five has real-three/four definitions in the Rules API. For custom N,
    # near-winning windows are useful candidates but never invented Renju threes.
    target = rules.win_length
    minimum = max(1, target - (3 if mode == "vct" and target == 5 else 2))
    scores = {}
    opponent = 3 - player
    for window in _windows(rules.size, target):
        if check is not None:
            check()
        own = 0
        empties = []
        for cell in window:
            value = cells[cell]
            if value == opponent:
                break
            if value == player:
                own += 1
            else:
                empties.append(cell)
        else:
            if own >= minimum:
                # Repeated overlapping windows prefer straight over closed fours.
                score = 16 ** max(0, own - minimum)
                for cell in empties:
                    scores[cell] = scores.get(cell, 0) + score
    return tuple(sorted(scores, key=lambda cell: (-scores[cell], cell)))


def _forcing_result(cells, cell, player, count, rules, mode, check):
    summary = rules.four_summary(cells, cell, player, count, check=check)
    if summary.legal is False:
        return None
    if summary.win:
        return summary
    if summary.fours:
        if summary.legal is True or rules.is_legal(cells, cell, player, count, check=check):
            return summary
        return None
    if mode == "vct" and rules.win_length == 5:
        # A cheap geometric candidate is NOT a real-three or legality verdict.
        result = rules.classify(cells, cell, player, count, check=check)
        if result.legal and result.threes:
            return result
    elif rules.win_length != 5:
        # Custom-N four_summary intentionally has no Renju formations. A move
        # creating an immediate next-turn winning square is a sound forcing move.
        if not rules.is_legal(cells, cell, player, count, check=check):
            return None
        with _placed(cells, cell, player):
            if winning_moves(cells, player, count + 1, rules, check):
                return summary
    return None


def forcing_moves(cells, player, move_count, rules, mode="vcf", check=None):
    """Legal forcing candidates, ordered fours before real threes; incomplete.

    Includes all immediate wins first. Does NOT claim to enumerate every legal
    move or every possible winning plan. No result from four_summary with
    legal=None is accepted without the full is_legal/classify query.
    """
    if mode not in ("vcf", "vct"):
        raise ValueError("mode must be 'vcf' or 'vct'")
    wins = winning_moves(cells, player, move_count, rules, check)
    fours, threes = [], []
    for cell in _geometric_candidates(cells, player, rules, mode, check):
        if check is not None:
            check()
        if cell in wins:
            continue
        result = _forcing_result(cells, cell, player, move_count, rules, mode, check)
        if result is not None:
            (fours if result.fours or rules.win_length != 5 else threes).append(cell)
    return (*wins, *fours, *threes)


@contextmanager
def _placed(cells, cell, player):
    old = cells[cell]
    if old != EMPTY:
        raise ValueError("Search attempted an occupied placement")
    cells[cell] = player
    try:
        yield
    finally:
        cells[cell] = old


def _terminal_players(cells, rules, check):
    winners = set()
    for line in _lines(rules.size):
        check()
        previous, length = EMPTY, 0
        for cell in (*line, None):
            value = EMPTY if cell is None else cells[cell]
            if value == previous:
                length += 1
                continue
            if previous:
                exact = previous == BLACK and rules.win_length == 5
                if (length == rules.win_length if exact else length >= rules.win_length):
                    winners.add(previous)
            previous, length = value, 1
    return winners


class TacticalSolver:
    """Sound positive proof search, with incomplete attacker OR candidates.

    max_depth counts plies, including the final winning placement; defender pass
    consumes one depth ply but does not increase the placement move_count.
    Instances may be reused sequentially, not concurrently. A supplied check()
    may raise arbitrary cancellation exceptions; only TacticalInterrupted is
    caught. The caller's cells are copied, and all internal placements restore
    even when Rules or the callback raises.
    """
    def __init__(self, rules, check: Optional[Callable] = None, node_limit=20_000,
                 max_depth=9, mode="vcf", *, time_limit=None):
        if mode not in ("vcf", "vct"):
            raise ValueError("mode must be 'vcf' or 'vct'")
        self.rules = rules
        self.check = check
        self.node_limit = integer_index(node_limit)
        self.max_depth = integer_index(max_depth)
        if self.node_limit < 0 or self.max_depth < 0:
            raise ValueError("node_limit and max_depth must be nonnegative")
        if time_limit is not None and time_limit < 0:
            raise ValueError("time_limit must be nonnegative or None")
        self.time_limit = time_limit
        self.mode = mode
        self.nodes = 0
        self._deadline = None
        self._memo = {}
        self._reason = "no_forcing_proof"

    def _poll(self):
        if self._deadline is not None and perf_counter() >= self._deadline:
            raise TacticalInterrupted("time_limit")
        if self.check is not None:
            self.check()

    def _visit(self):
        self._poll()
        if self.nodes >= self.node_limit:
            raise TacticalInterrupted("node_limit")
        self.nodes += 1

    def solve(self, cells, attacker, move_count, *, roots=None):
        if len(cells) != self.rules.size * self.rules.size:
            raise ValueError("Flat board length does not match Rules.size")
        if attacker not in (BLACK, WHITE) or any(v not in (EMPTY, BLACK, WHITE) for v in cells):
            raise ValueError("Invalid player/cells")
        move_count = integer_index(move_count)
        if move_count < 0:
            raise ValueError("move_count must be nonnegative")
        self.nodes = 0
        self._memo = {}
        self._reason = "no_forcing_proof"
        self._deadline = None if self.time_limit is None else perf_counter() + self.time_limit
        work = list(cells)
        try:
            self._visit()
            terminal = _terminal_players(work, self.rules, self._poll)
            if len(terminal) > 1:
                return self._result(ProofStatus.UNKNOWN, reason="inconsistent_terminal_position")
            if terminal:
                status = ProofStatus.PROVEN_WIN if attacker in terminal else ProofStatus.PROVEN_LOSS
                return self._result(status, reason="already_terminal")
            nominated = None if roots is None else tuple(dict.fromkeys(integer_index(r) for r in roots))
            proof = self._attack(work, attacker, move_count, self.max_depth, nominated)
            if proof is not None:
                self._poll()
                return self._result(ProofStatus.PROVEN_WIN, proof=proof, reason="certified_strategy")
            return self._result(ProofStatus.UNKNOWN, reason=self._reason)
        except TacticalInterrupted as stopped:
            return self._result(ProofStatus.UNKNOWN, reason=str(stopped) or "interrupted")
        finally:
            self._memo.clear()

    def verify_root(self, cells, attacker, move_count, root):
        return self.solve(cells, attacker, move_count, roots=[root])

    def _result(self, status, *, proof=None, reason=""):
        return TacticalResult(status, proof.pv[0] if proof and proof.pv else None,
                              proof.pv if proof else (), self.nodes, reason,
                              proof.depth if proof else 0, self.rules.ruleset,
                              proof.certificate if proof else None)

    def _attack(self, cells, attacker, count, depth, roots=None):
        self._visit()
        if depth < 1:
            self._reason = "depth_limit"
            return None
        key = None
        if roots is None:
            key = (tuple(cells), attacker, count, depth)
            cached = self._memo.get(key)
            if cached is not None:
                return cached
        immediate = winning_moves(cells, attacker, count, self.rules, self._poll)
        if roots is not None:
            allowed = set(roots)
            immediate = tuple(move for move in immediate if move in allowed)
        if immediate:
            move = immediate[0]
            proof = _Win((move,), TacticalCertificate("terminal", move), 1)
            if key is not None:
                self._memo[key] = proof
            return proof
        # A defender counterfour made by its preceding forced block must not be
        # ignored. With no attacker win, only occupation of a sole opponent
        # endpoint can avoid losing next turn; two endpoints refute every move.
        enemy_wins = winning_moves(cells, 3 - attacker, count + 1, self.rules, self._poll)
        if len(enemy_wins) >= 2:
            self._reason = "opponent_multiple_winning_squares"
            return None
        candidates = roots if roots is not None else _geometric_candidates(
            cells, attacker, self.rules, self.mode, self._poll)
        if enemy_wins:
            candidates = tuple(cell for cell in candidates if cell == enemy_wins[0])
        for cell in candidates:
            self._poll()
            if not 0 <= cell < len(cells) or cells[cell]:
                continue
            self._visit()
            result = _forcing_result(cells, cell, attacker, count, self.rules,
                                     self.mode, self._poll)
            if result is None:
                continue
            if result.win:
                proof = _Win((cell,), TacticalCertificate("terminal", cell), 1)
            else:
                with _placed(cells, cell, attacker):
                    proof = self._defend(cells, attacker, count + 1, depth - 1, cell)
            if proof is not None:
                if key is not None:
                    self._memo[key] = proof
                return proof
        return None

    def _defend(self, cells, attacker, count, depth, last_move):
        self._visit()
        defender = 3 - attacker
        # This all-board check MUST precede endpoint shortcuts, even if the
        # defender's win is unrelated to the attack or itself a forbidden-look.
        if winning_moves(cells, defender, count, self.rules, self._poll):
            self._reason = "defender_immediate_win"
            return None
        if depth < 2:
            self._reason = "depth_limit"
            return None
        wins = winning_moves(cells, attacker, count + 1, self.rules, self._poll)
        pass_wins = winning_moves(cells, attacker, count, self.rules, self._poll)
        if wins:
            # Inserting an opponent stone cannot invalidate an unoccupied
            # immediate win elsewhere: exact black five has legality priority.
            # A pass is handled separately because opening uses placement count.
            pass_proof = None
            if not pass_wins:
                pass_proof = self._attack(cells, attacker, count, depth - 1)
                if pass_proof is None:
                    return None
            block = wins[0] if len(wins) == 1 else None
            block_legal = block is not None and self.rules.is_legal(
                cells, block, defender, count, check=self._poll)
            branches = []
            if pass_proof is not None:
                branches.append(DefenseBranch(None, pass_proof.certificate))
            if block_legal:
                with _placed(cells, block, defender):
                    child = self._attack(cells, attacker, count + 1, depth - 1)
                if child is None:
                    return None
                branches.append(DefenseBranch(block, child.certificate))
                pv = (last_move, block, *child.pv)
                proof_depth = 2 + child.depth
                kind = "forced_block"
            else:
                tail = self._representative_finish(cells, attacker, count, wins)
                pv = (last_move, *tail)
                proof_depth = 3
                kind = "winning_square_partition"
            cert = TacticalCertificate(kind, last_move, wins, tuple(branches), True, pass_wins)
            return _Win(pv, cert, max(proof_depth, 2 + pass_proof.depth if pass_proof else 0))
        if self.mode != "vct":
            return None
        # NO SELECTED-BLOCK REDUCTION for a three: endpoints, distant moves,
        # counterfours, and pass are all actual AND children. Short-circuiting on
        # one unknown/refutation is safe; a positive answer must visit them all.
        branches = []
        representative = None
        maximum_depth = 0
        for cell, value in enumerate(cells):
            self._poll()
            if value or not self.rules.is_legal(cells, cell, defender, count, check=self._poll):
                continue
            with _placed(cells, cell, defender):
                child = self._attack(cells, attacker, count + 1, depth - 1)
            if child is None:
                return None
            branches.append(DefenseBranch(cell, child.certificate))
            maximum_depth = max(maximum_depth, 2 + child.depth)
            if representative is None or child.depth > representative[1].depth:
                representative = (cell, child)
        child = self._attack(cells, attacker, count, depth - 1)
        if child is None:
            return None
        branches.append(DefenseBranch(None, child.certificate))
        maximum_depth = max(maximum_depth, 2 + child.depth)
        if representative is None:
            # No placement exists: the modeled pass is conservative. PV is only
            # the root because tuple[int,...] cannot encode a pass faithfully.
            pv = (last_move,)
        else:
            cell, child = representative
            pv = (last_move, cell, *child.pv)
        return _Win(pv, TacticalCertificate("all_defenses", last_move,
                                          defenses=tuple(branches), includes_pass=True),
                    maximum_depth)

    def _representative_finish(self, cells, attacker, count, wins):
        defender = 3 - attacker
        # Produce a replayable legal representative, preferably an endpoint
        # block. The certificate, rather than this one PV, covers other replies.
        options = (*wins, *(i for i, value in enumerate(cells) if not value and i not in wins))
        for cell in options:
            self._poll()
            if not self.rules.is_legal(cells, cell, defender, count, check=self._poll):
                continue
            finish = next((win for win in wins if win != cell), None)
            if finish is not None:
                return cell, finish
        return ()
