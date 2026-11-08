"""Separated, observationally pure Renju placement rules (no Board/AI imports).

The core adjudicates pre-move row-major lists: 0 empty, 1 black, 2 white.
Only five-in-a-row uses black fouls. Other targets use symmetric freestyle
connect-N. The optional opening is this project's *simplified* opening, not
an implementation of tournament swaps, passes, clocks, or claims.
"""
from collections import OrderedDict
from dataclasses import dataclass
from operator import index as integer_index
from typing import Optional, Tuple

EMPTY, BLACK, WHITE = 0, 1, 2
DIRECTIONS = ((0, 1), (1, 0), (1, 1), (1, -1))
Axis = Tuple[int, int]


@dataclass(frozen=True, slots=True)
class Four:
    axis: Axis
    stones: Tuple[int, ...]
    completions: Tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ThreeWitness:
    extension: int
    completions: Tuple[int, ...]


@dataclass(frozen=True, slots=True)
class Three:
    axis: Axis
    stones: Tuple[int, ...]
    extensions: Tuple[int, ...]
    witnesses: Tuple[ThreeWitness, ...]


@dataclass(frozen=True, slots=True)
class WinningLine:
    axis: Axis
    stones: Tuple[int, ...]


@dataclass(frozen=True, slots=True)
class MoveResult:
    legal: bool
    win: bool
    reason: str
    fours: Tuple[Four, ...] = ()
    threes: Tuple[Three, ...] = ()
    winning_lines: Tuple[WinningLine, ...] = ()


@dataclass(frozen=True, slots=True)
class FourSummary:
    """Cheap result. legal=None explicitly means double-three is unexamined."""
    legal: Optional[bool]
    win: bool
    reason: str
    fours: Tuple[Four, ...] = ()
    winning_lines: Tuple[WinningLine, ...] = ()


@dataclass(frozen=True, slots=True)
class _Verdict:
    legal: bool
    win: bool
    reason: str


class _Context:
    """One call's mutable workspace and exact incremental position signature."""
    def __init__(self, cells, check):
        self.cells = cells
        self.check = check
        self.black = 0
        self.white = 0
        self.undo = []
        for i, value in enumerate(cells):
            if value == BLACK:
                self.black |= 1 << i
            elif value == WHITE:
                self.white |= 1 << i
            elif value != EMPTY:
                raise ValueError("Cells must be 0 (empty), 1 (black), or 2 (white)")

    def poll(self):
        if self.check is not None:
            self.check()

    def push(self, cell, player):
        # All callers place only on empty cells. Log before any write, so even
        # an exceptional exit can restore the caller's borrowed list.
        self.undo.append((cell, self.cells[cell], self.black, self.white))
        self.cells[cell] = player
        if player == BLACK:
            self.black |= 1 << cell
        else:
            self.white |= 1 << cell

    def restore(self, mark):
        while len(self.undo) > mark:
            cell, old, self.black, self.white = self.undo.pop()
            self.cells[cell] = old


class Rules:
    """Move-local RIF five/foul core, with separately named opening policy.

    A list[int] is borrowed temporarily and restored with try/finally, including
    cancellation exceptions. Do not concurrently inspect or mutate that list.
    Other flat sequences are copied once. This instance's memo is bounded and
    keys use complete black/white bitsets, never an unchecked position hash.
    Callback ``check()`` may raise any exception; it is never converted into a
    legal/illegal answer. Calls do not validate alternating history/game-over.
    """
    def __init__(self, size=15, win_length=5, opening=True, *, memo_limit=4096):
        self.size = integer_index(size)
        self.win_length = integer_index(win_length)
        self.memo_limit = integer_index(memo_limit)
        if self.win_length < 1 or self.size < self.win_length:
            raise ValueError("Require size >= win_length >= 1")
        if self.memo_limit < 0:
            raise ValueError("memo_limit must be nonnegative")
        self.opening = bool(opening)
        if self.win_length == 5:
            self.ruleset = ("renju-rif-core-15x15" if self.size == 15 else
                            f"renju-core-custom-{self.size}x{self.size}-nonofficial")
        else:
            self.ruleset = f"gomoku-custom-freestyle-connect-{self.win_length}"
        self.opening_policy = ("simplified-center-opening" if self.opening
                               and self.size >= 5 and self.size % 2 else "none")
        self._memo = OrderedDict()
        self._axes = []
        self._five_windows = []
        self._straight_windows = []
        # Reuse full lines; per-index windows contain only local geometry.
        line_cache = {}
        n = self.size
        for cell in range(n * n):
            row, col = divmod(cell, n)
            axes, fives, straights = [], [], []
            for axis in DIRECTIONS:
                dr, dc = axis
                r, c = row, col
                while 0 <= r - dr < n and 0 <= c - dc < n:
                    r, c = r - dr, c - dc
                key = (axis, r, c)
                if key not in line_cache:
                    line = []
                    rr, cc = r, c
                    while 0 <= rr < n and 0 <= cc < n:
                        line.append(rr * n + cc)
                        rr, cc = rr + dr, cc + dc
                    line_cache[key] = tuple(line)
                line = line_cache[key]
                offset = line.index(cell)
                axes.append((axis, line, offset))
                for start in range(max(0, offset - 4), min(offset, len(line) - 5) + 1):
                    fives.append((axis, line[start:start + 5],
                                  line[start - 1] if start else None,
                                  line[start + 5] if start + 5 < len(line) else None))
                # A straight four needs an empty cell at each end; the cell
                # beyond each endpoint must not poison black's exact five.
                for start in range(max(1, offset - 3), min(offset, len(line) - 5) + 1):
                    straights.append((axis, line[start:start + 4],
                                      (line[start - 1], line[start + 4]),
                                      line[start - 2] if start >= 2 else None,
                                      line[start + 5] if start + 5 < len(line) else None))
            self._axes.append(tuple(axes))
            self._five_windows.append(tuple(fives))
            self._straight_windows.append(tuple(straights))

    @property
    def memo_entries(self):
        return len(self._memo)

    def clear_memo(self):
        self._memo.clear()

    def flatten(self, grid):
        """Copy a size-by-size nested grid/NumPy Board.grid to row-major ints."""
        if len(grid) != self.size or any(len(row) != self.size for row in grid):
            raise ValueError("Grid shape does not match Rules.size")
        return [integer_index(value) for row in grid for value in row]

    def opening_allows(self, cell, move_count):
        """Legacy coordinate restriction, independent of player and target."""
        if not 0 <= cell < self.size * self.size:
            return False
        if self.opening_policy == "none":
            return True
        row, col = divmod(cell, self.size)
        center = self.size // 2
        if move_count == 0:
            return (row, col) == (center, center)
        if move_count == 1:
            return (row, col) in ((center - 1, center), (center - 1, center + 1))
        if move_count == 2:
            return abs(row - center) <= 2 and abs(col - center) <= 2
        return True

    def classify(self, grid_flat, index, player, move_count=0, check=None, *, check_opening=True):
        """Fully classify an empty candidate, restoring the pre-move input.

        Full nonterminal classifications include *all* root four identities
        and real-three witnesses, even if the move is already a foul. Winning
        moves are terminal and have empty fours/threes. For fast legality use
        is_legal; for geometric four ordering use four_summary instead.
        """
        return self._query(grid_flat, index, player, move_count, check,
                           check_opening, False, "full")

    def is_legal(self, grid_flat, index, player, move_count=0, check=None, *, check_opening=True):
        """Complete legality, short-circuiting after a decisive foul/witness."""
        return self._query(grid_flat, index, player, move_count, check,
                           check_opening, False, "legal")

    def four_summary(self, grid_flat, index, player, move_count=0, check=None, *, check_opening=True):
        """No recursive three work; legal=None is not permission to play."""
        return self._query(grid_flat, index, player, move_count, check,
                           check_opening, False, "four")

    def classify_grid(self, grid, row, col, player, move_count=0, check=None, *, check_opening=True):
        """Board.grid adapter; validate row/col separately (no index wrapping)."""
        if not (0 <= row < self.size and 0 <= col < self.size):
            if check is not None:
                check()
            return MoveResult(False, False, "out_of_bounds")
        return self.classify(self.flatten(grid), row * self.size + col, player,
                             move_count, check, check_opening=check_opening)

    def analyze_placed(self, grid_flat, index, player, check=None):
        """Full local classification with the root already placed; no opening."""
        return self._query(grid_flat, index, player, 0, check, False, True, "full")

    def four_summary_placed(self, grid_flat, index, player, check=None):
        """Four-only version of analyze_placed; same unresolved-legal contract."""
        return self._query(grid_flat, index, player, 0, check, False, True, "four")

    def _query(self, grid_flat, index, player, move_count, check, opening, placed, mode):
        if check is not None:
            check()
        if len(grid_flat) != self.size * self.size:
            raise ValueError("Flat board length does not match Rules.size")
        cells = grid_flat if isinstance(grid_flat, list) else list(grid_flat)
        try:
            cell = integer_index(index)
        except TypeError:
            cell = -1
        invalid = None
        if player not in (BLACK, WHITE):
            invalid = "invalid_player"
        elif not 0 <= cell < len(cells):
            invalid = "out_of_bounds"
        elif placed and cells[cell] != player:
            invalid = "not_player_stone"
        elif not placed and cells[cell] != EMPTY:
            invalid = "occupied"
        elif not placed and opening and not self.opening_allows(cell, move_count):
            invalid = "opening"
        if invalid:
            if mode == "legal":
                return False
            return (FourSummary if mode == "four" else MoveResult)(False, False, invalid)
        # White and custom connect-N have no placement fouls; a legality-only
        # query needs neither a position signature nor any hypothetical write.
        if mode == "legal" and (player != BLACK or self.win_length != 5):
            return True
        ctx = _Context(cells, check)
        mark = len(ctx.undo)
        try:
            if not placed:
                ctx.push(cell, player)
            if mode == "legal":
                return self._solve_black(ctx, cell).legal
            return self._classify_placed(ctx, cell, player, mode == "four")
        finally:
            ctx.restore(mark)

    def _terminal(self, ctx, cell, player):
        wins = []
        overline = False
        for axis, line, offset in self._axes[cell]:
            ctx.poll()
            lo, hi = offset, offset + 1
            while lo and ctx.cells[line[lo - 1]] == player:
                lo -= 1
            while hi < len(line) and ctx.cells[line[hi]] == player:
                hi += 1
            length = hi - lo
            black_core = player == BLACK and self.win_length == 5
            winning = length == 5 if black_core else length >= self.win_length
            if winning:
                wins.append(WinningLine(axis, tuple(sorted(line[lo:hi]))))
            if black_core and length > 5:
                overline = True
        if wins:
            if self.win_length != 5:
                reason = "win_connect_n"
            elif any(len(win.stones) > 5 for win in wins):
                reason = "win_overline"
            else:
                reason = "win_exact_five"
            return tuple(wins), overline, reason
        return (), overline, None

    def _fours(self, ctx, cell, player):
        groups = {}
        for axis, window, before, after in self._five_windows[cell]:
            if player == BLACK and ((before is not None and ctx.cells[before] == player)
                                    or (after is not None and ctx.cells[after] == player)):
                continue
            stones, empties = [], []
            for point in window:
                value = ctx.cells[point]
                if value == player:
                    stones.append(point)
                elif value == EMPTY:
                    empties.append(point)
                else:
                    break
            else:
                if len(stones) == 4 and len(empties) == 1:
                    key = (axis, tuple(sorted(stones)))
                    groups.setdefault(key, set()).add(empties[0])
        ctx.poll()
        return tuple(Four(axis, stones, tuple(sorted(completions)))
                     for (axis, stones), completions in sorted(groups.items()))

    def _three_candidates(self, ctx, cell, player):
        # Group by axis + three-stone identity, not by direction or extension.
        groups = {}
        for axis, window, endpoints, before, after in self._straight_windows[cell]:
            if any(ctx.cells[point] != EMPTY for point in endpoints):
                continue
            if player == BLACK and ((before is not None and ctx.cells[before] == player)
                                    or (after is not None and ctx.cells[after] == player)):
                continue
            stones, empties = [], []
            for point in window:
                value = ctx.cells[point]
                if value == player:
                    stones.append(point)
                elif value == EMPTY:
                    empties.append(point)
                else:
                    break
            else:
                if len(stones) == 3 and len(empties) == 1:
                    key = (axis, tuple(sorted(stones)))
                    groups.setdefault(key, {})[empties[0]] = tuple(sorted(endpoints))
        ctx.poll()
        return tuple((axis, stones, tuple(sorted(extensions.items())))
                     for (axis, stones), extensions in sorted(groups.items()))

    def _remember(self, key, verdict):
        if self.memo_limit:
            self._memo[key] = verdict
            self._memo.move_to_end(key)
            while len(self._memo) > self.memo_limit:
                self._memo.popitem(last=False)
        return verdict

    def _judge_black(self, ctx, cell):
        """Generator requests child placements; the iterative driver owns undo."""
        ctx.poll()
        key = (ctx.black, ctx.white, cell)
        cached = self._memo.get(key)
        if cached is not None:
            self._memo.move_to_end(key)
            return cached
        wins, overline, reason = self._terminal(ctx, cell, BLACK)
        if wins:
            return self._remember(key, _Verdict(True, True, reason))
        if overline:
            return self._remember(key, _Verdict(False, False, "forbidden_overline"))
        if len(self._fours(ctx, cell, BLACK)) >= 2:
            return self._remember(key, _Verdict(False, False, "forbidden_double_four"))
        candidates = self._three_candidates(ctx, cell, BLACK)
        real_count = 0
        if len(candidates) >= 2:
            for _, _, extensions in candidates:
                for extension, _ in extensions:
                    child = yield extension
                    # An exact five in ANY axis is legal but not a three witness.
                    if child.legal and not child.win:
                        real_count += 1
                        break
                if real_count >= 2:
                    return self._remember(key, _Verdict(False, False, "forbidden_double_three"))
        return self._remember(key, _Verdict(True, False, "legal_nonterminal"))

    def _solve_black(self, ctx, cell):
        """Exact finite recursion without a Python call-stack/depth cutoff.

        Each generator is one hypothetical placement. Children add a black
        stone; an explicit stack, bounded by the board's empty cells, evaluates
        existential witnesses. A final restore covers cancellation at any level.
        """
        mark = len(ctx.undo)
        stack = [(self._judge_black(ctx, cell), mark)]
        answer = None
        started = False
        try:
            while stack:
                generator, own_mark = stack[-1]
                try:
                    extension = generator.send(answer) if started else next(generator)
                except StopIteration as done:
                    answer = done.value
                    stack.pop()
                    ctx.restore(own_mark)
                    started = True
                else:
                    child_mark = len(ctx.undo)
                    ctx.push(extension, BLACK)
                    stack.append((self._judge_black(ctx, extension), child_mark))
                    answer = None
                    started = False
            return answer
        finally:
            # Generators own no mutations, but close suspended frames promptly.
            for generator, _ in reversed(stack):
                generator.close()
            ctx.restore(mark)

    def _real_threes(self, ctx, cell, player):
        threes = []
        for axis, stones, extensions in self._three_candidates(ctx, cell, player):
            witnesses = []
            for extension, completions in extensions:
                ctx.poll()
                mark = len(ctx.undo)
                try:
                    ctx.push(extension, player)
                    if player == BLACK:
                        verdict = self._solve_black(ctx, extension)
                        qualifies = verdict.legal and not verdict.win
                    else:
                        wins, _, _ = self._terminal(ctx, extension, player)
                        qualifies = not wins
                    if qualifies:
                        witnesses.append(ThreeWitness(extension, completions))
                finally:
                    ctx.restore(mark)
            if witnesses:
                threes.append(Three(axis, stones, tuple(w.extension for w in witnesses), tuple(witnesses)))
        return tuple(threes)

    def _classify_placed(self, ctx, cell, player, four_only):
        result_type = FourSummary if four_only else MoveResult
        wins, overline, reason = self._terminal(ctx, cell, player)
        if wins:
            return result_type(True, True, reason, winning_lines=wins)
        if self.win_length != 5:
            return result_type(True, False, "legal_nonterminal")
        fours = self._fours(ctx, cell, player)
        if four_only:
            if player == WHITE:
                return FourSummary(True, False, "legal_nonterminal", fours)
            if overline:
                return FourSummary(False, False, "forbidden_overline", fours)
            if len(fours) >= 2:
                return FourSummary(False, False, "forbidden_double_four", fours)
            return FourSummary(None, False, "needs_three_check", fours)
        threes = self._real_threes(ctx, cell, player)
        if player == BLACK:
            if overline:
                reason = "forbidden_overline"
            elif len(fours) >= 2:
                reason = "forbidden_double_four"
            elif len(threes) >= 2:
                reason = "forbidden_double_three"
        return MoveResult(reason is None, False, reason or "legal_nonterminal", fours, threes)
