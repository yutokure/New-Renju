from contextlib import contextmanager
import time


class RuleValidationTimeout(Exception):
    """A UI validation budget expired; this is NOT an illegal-move verdict."""


import numpy as np
from constants import DEFAULT_BOARD_SIZE, DEFAULT_WIN_LENGTH
from renju_rules import Rules

# Player representation
EMPTY = 0
BLACK = 1
WHITE = 2

# Directions for checking lines (Horizontal, Vertical, Diagonal /, Diagonal \)
DIRECTIONS = [(0, 1), (1, 0), (1, 1), (1, -1)]

# Define threat types
THREAT_OPEN_THREE = 1
THREAT_CLOSED_FOUR = 2
THREAT_OPEN_FOUR = 3


class Board:
    """Represents the Gomoku game board and handles game logic including Renju rules."""

    def __init__(self, size=DEFAULT_BOARD_SIZE, win_length=DEFAULT_WIN_LENGTH):
        if size < win_length:
            raise ValueError("Board size must be >= win length")
        self.size = size
        self.win_length = win_length
        self.grid = np.zeros((size, size), dtype=int)
        self._rules = Rules(size, win_length)
        self.ruleset = self._rules.ruleset
        self.opening_policy = self._rules.opening_policy
        self._legality_key = None
        self._legality_cells = None
        self._legality_cache = {}
        self.validation_budget_sec = None
        self.last_move = None  # Store the last move (row, col)
        self.forbidden_checked_pos = None  # Store pos just checked for forbidden
        self.center = (size // 2, size // 2) if size % 2 == 1 else None

    def is_within_bounds(self, row, col):
        """Checks if the given coordinates are within the board bounds."""
        return 0 <= row < self.size and 0 <= col < self.size

    def is_empty(self, row, col):
        """Checks if the cell at the given coordinates is empty."""
        # Assumes coordinates are within bounds for internal checks
        return self.grid[row, col] == EMPTY

    @contextmanager
    def temporary_move(self, row, col, player):
        """Temporarily place a stone, restoring *all* transient state on exit.

        This is a hypothetical placement, not a legality check. Occupied cells
        are supported for analysis and restored to their previous value.
        Nested scopes and exceptions are safe; no move count lives on Board.
        """
        if not self.is_within_bounds(row, col):
            raise IndexError("Temporary move is outside the board")
        old_cell = self.grid[row, col]
        old_last = self.last_move
        old_forbidden = self.forbidden_checked_pos
        try:
            self.grid[row, col] = player
            self.last_move = (row, col)
            yield self
        finally:
            self.grid[row, col] = old_cell
            self.last_move = old_last
            self.forbidden_checked_pos = old_forbidden

    def _opening_allows(self, row, col, move_count):
        """Keep the project's simplified opening, also in custom Gomoku."""
        if self.center is None or self.size < 5:
            return True
        center_r, center_c = self.center
        if move_count == 0:
            return (row, col) == self.center
        if move_count == 1:
            return (row, col) in ((center_r - 1, center_c),
                                  (center_r - 1, center_c + 1))
        if move_count == 2:
            return abs(row - center_r) <= 2 and abs(col - center_c) <= 2
        return True

    def is_valid_move(self, row, col, player, move_count):
        """Nonmutating legality query; forbidden rules apply only to five."""
        return (player in (BLACK, WHITE)
                and self.is_within_bounds(row, col)
                and self.is_empty(row, col)
                and self._opening_allows(row, col, move_count)
                and not self._is_forbidden(row, col, player))

    def place_stone(self, row, col, player, move_count):
        """Place a legal stone; only real attempts update visual feedback."""
        if self.is_valid_move(row, col, player, move_count):
            self.grid[row, col] = player
            self.last_move = (row, col)
            self.forbidden_checked_pos = None
            return True
        if (player == BLACK and self.is_within_bounds(row, col)
                and self.is_empty(row, col)
                and self._opening_allows(row, col, move_count)
                and self.is_forbidden(row, col)):
            self.forbidden_checked_pos = (row, col)
        return False

    def check_win(self, player):
        """Check lines through last_move; black five must be exact.

        An exact black five has priority across *all* directions, including
        when the same move makes an overline elsewhere. White and custom
        (win_length != 5) Gomoku both win with at least win_length stones.
        """
        if self.last_move is None:
            return False, None
        r, c = self.last_move
        if not self.is_within_bounds(r, c) or self.grid[r, c] != player:
            return False, None
        for dr, dc in DIRECTIONS:
            count = self._count_line_length(r, c, dr, dc, player)
            wins = (count == 5 if player == BLACK and self.win_length == 5
                    else count >= self.win_length)
            if wins:
                start_r, start_c = r, c
                while (self.is_within_bounds(start_r - dr, start_c - dc)
                       and self.grid[start_r - dr, start_c - dc] == player):
                    start_r -= dr
                    start_c -= dc
                end = (start_r + (count - 1) * dr,
                       start_c + (count - 1) * dc)
                start, end = sorted(((start_r, start_c), end))
                return True, (start, end, (dr, dc))
        return False, None

    def _count_line_length(self, r, c, dr, dc, player):
        """Counts total connected stones for player along a direction vector."""
        count = 1  # Start with the stone at (r, c)
        # Count in the positive direction (dr, dc)
        cr, cc = r + dr, c + dc
        while self.is_within_bounds(cr, cc) and self.grid[cr, cc] == player:
            count += 1
            cr += dr
            cc += dc
        # Count in the negative direction (-dr, -dc)
        cr, cc = r - dr, c - dc
        while self.is_within_bounds(cr, cc) and self.grid[cr, cc] == player:
            count += 1
            cr -= dr
            cc -= dc
        return count

    def _count_line_details(self, r, c, dr, dc, player):
        """Counts connected stones and checks if the line ends are open."""
        count = 1
        open_ends = 0

        # Check positive direction
        cr, cc = r + dr, c + dc
        while self.is_within_bounds(cr, cc) and self.grid[cr, cc] == player:
            count += 1
            cr += dr
            cc += dc
        # Check if the line is open in this direction
        if self.is_within_bounds(cr, cc) and self.grid[cr, cc] == EMPTY:
            open_ends += 1

        # Check negative direction
        cr, cc = r - dr, c - dc
        while self.is_within_bounds(cr, cc) and self.grid[cr, cc] == player:
            count += 1
            cr -= dr
            cc -= dc
        # Check if the line is open in this direction
        if self.is_within_bounds(cr, cc) and self.grid[cr, cc] == EMPTY:
            open_ends += 1

        return count, open_ends

    def is_forbidden(self, r, c):
        """Nonmutating black forbidden query; occupied/outside cells are safe.

        An occupied cell is not a candidate move, so this returns False rather
        than overwriting it. Use is_valid_move for complete move legality.
        """
        return self._is_forbidden(r, c, BLACK)

    def get_empty_cells(self):
        """Returns a list of (row, col) tuples for all empty cells."""
        return list(zip(*np.where(self.grid == EMPTY)))

    def print_board(self):
        """Prints the current board state to the console (for debugging)."""
        header = "   " + " ".join([f"{i:2}" for i in range(self.size)])
        print(header)
        print("  " + "-" * (self.size * 3 + 1))
        for r in range(self.size):
            row_str = "|"
            for c in range(self.size):
                mark = "."
                if self.grid[r, c] == BLACK:
                    mark = "X"
                elif self.grid[r, c] == WHITE:
                    mark = "O"

                cell_str = f" {mark} "
                # Highlight the last move
                if self.last_move == (r, c):
                    cell_str = f"<{mark}>"
                # Highlight the position just checked for forbidden move
                elif self.forbidden_checked_pos == (r, c):
                    cell_str = " ! "  # Indicate forbidden attempt location

                row_str += cell_str + "|"
            print(f"{r:2} {row_str}")
        print("  " + "-" * (self.size * 3 + 1))
        # Clear the forbidden marker *after* printing so it's visible
        if self.forbidden_checked_pos:
            self.forbidden_checked_pos = None

    def _is_forbidden(self, r, c, player):
        """Shared verified rule core, independent from all AI evaluations.

        Public grid writes by legacy callers are detected by an exact byte key;
        one flattened copy and per-cell results are reused within a position.
        """
        if (player != BLACK or self.win_length != 5
                or not self.is_within_bounds(r, c) or not self.is_empty(r, c)):
            return False
        key = (self.size, self.win_length, self.grid.tobytes())
        if key != self._legality_key:
            if self._rules.size != self.size or self._rules.win_length != self.win_length:
                self._rules = Rules(self.size, self.win_length)
                self.ruleset = self._rules.ruleset
                self.opening_policy = self._rules.opening_policy
            self._legality_key = key
            self._legality_cells = self._rules.flatten(self.grid)
            self._legality_cache = {}
        cell = int(r * self.size + c)
        if cell not in self._legality_cache:
            check = None
            if self.validation_budget_sec is not None:
                deadline = time.perf_counter() + self.validation_budget_sec
                def check():
                    if time.perf_counter() >= deadline:
                        raise RuleValidationTimeout('Rule validation incomplete; try another move or use research')
            self._legality_cache[cell] = not self._rules.is_legal(
                self._legality_cells, cell, player, check=check, check_opening=False)
        return self._legality_cache[cell]

    def find_threats(self, player):
        """盤面上の脅威を検出します。
        修正: 飛び四は端の状態に関わらずコアパターン(長さ5)で検出し、CLOSED_FOURとして扱う。
        """
        threats = []
        p = int(player)
        opponent = int(WHITE if p == BLACK else BLACK)
        e = int(EMPTY)

        if self.win_length != 5:
            return []

        # パディンググリッドは削除

        # --- Define Patterns (Simplified for Jumping Fours) ---
        patterns_to_check = [
            # Open Threes (Normal and Jumping) - Length 5 or 6
            (THREAT_OPEN_THREE, (e, p, p, p, e)),    # .XXX.
            (THREAT_OPEN_THREE, (e, p, p, e, p, e)), # .XX.X.
            (THREAT_OPEN_THREE, (e, p, e, p, p, e)), # .X.XX.
            (THREAT_OPEN_THREE, (e, p, e, p, e, p, e)), # .P.P.P. (New)
            # Closed Fours (Normal Only) - Length 6
            (THREAT_CLOSED_FOUR, (opponent, p, p, p, p, e)), # OXXXX.
            (THREAT_CLOSED_FOUR, (e, p, p, p, p, opponent)), # .XXXXO
            # Open Fours (Normal Only) - Length 6
            (THREAT_OPEN_FOUR, (e, p, p, p, p, e)),   # .XXXX.
            # --- Core Jumping Four Patterns (Treated as Closed Four Threat) - Length 5 ---
            (THREAT_CLOSED_FOUR, (p, p, p, e, p)), # BBB_B
            (THREAT_CLOSED_FOUR, (p, p, e, p, p)), # BB_BB
            (THREAT_CLOSED_FOUR, (p, e, p, p, p)), # B_BBB
        ]

        processed_threat_locations = set()

        for r in range(self.size):
            for c in range(self.size):
                for threat_type, pattern in patterns_to_check:
                    pattern_len = len(pattern)

                    # Helper to add threat if valid and not already processed
                    def add_threat_if_valid(direction_char):
                        # Calculate pattern end coordinates based on direction
                        if direction_char == 'h':
                            pattern_start_coord = (r, c)
                            pattern_end_coord = (r, c + pattern_len - 1)
                        elif direction_char == 'v':
                            pattern_start_coord = (r, c)
                            pattern_end_coord = (r + pattern_len - 1, c)
                        elif direction_char == 'd1': # Down-Right
                            pattern_start_coord = (r, c)
                            pattern_end_coord = (r + pattern_len - 1, c + pattern_len - 1)
                        elif direction_char == 'd2': # Up-Right
                            pattern_start_coord = (r, c)
                            pattern_end_coord = (r - (pattern_len - 1), c + pattern_len - 1)
                        else:
                            return

                        # Extract player stone coordinates within the pattern on the original board
                        player_stone_coords = []
                        for i in range(pattern_len):
                            r_check, c_check = -1, -1
                            if direction_char == 'h': r_check, c_check = r, c + i
                            elif direction_char == 'v': r_check, c_check = r + i, c
                            elif direction_char == 'd1': r_check, c_check = r + i, c + i
                            elif direction_char == 'd2': r_check, c_check = r - i, c + i

                            if self.is_within_bounds(r_check, c_check) and self.grid[r_check, c_check] == p:
                                player_stone_coords.append((r_check, c_check))

                        # If no player stones found in the pattern (shouldn't happen for valid threats), skip
                        if not player_stone_coords:
                            return

                        # Use a frozenset of the *player stone coordinates* for uniqueness check
                        # This prevents adding the same threat line based on overlapping empty cells
                        threat_cells = frozenset(player_stone_coords)

                        if not threat_cells:
                             return

                        if threat_cells not in processed_threat_locations:
                            # Include player_stone_coords in the appended tuple
                            threats.append((threat_type, pattern_start_coord, pattern_end_coord, direction_char, player_stone_coords))
                            processed_threat_locations.add(threat_cells)
                            # print(f"DEBUG add_threat: Added Threat {threat_type} ... Stones: {player_stone_coords}")
                        # else:
                            # print(f"DEBUG add_threat: Threat already processed (Duplicate stones: {threat_cells})")
                        # --- End of Re-inserted helper content --- #

                    # --- Check Horizontal (Using self.grid) ---
                    if c + pattern_len <= self.size:
                        segment = tuple(int(self.grid[r, c + i]) for i in range(pattern_len))
                        # DEBUG: Check all length 7 patterns
                        # if pattern_len == 7:
                            # print(f"DEBUG L7 Check (H) at ({r},{c}) for P{p}: Match={segment == pattern}, Seg={segment}, Pat={pattern}")
                        if segment == pattern:
                            add_threat_if_valid('h')

                    # --- Check Vertical (Using self.grid) ---
                    if r + pattern_len <= self.size:
                        segment = tuple(int(self.grid[r + i, c]) for i in range(pattern_len))
                        # if pattern_len == 7:
                            # print(f"DEBUG L7 Check (V) at ({r},{c}) for P{p}: Match={segment == pattern}, Seg={segment}, Pat={pattern}")
                        if segment == pattern:
                            add_threat_if_valid('v')

                    # --- Check Diagonal Down-Right (Using self.grid) ---
                    if r + pattern_len <= self.size and c + pattern_len <= self.size:
                         segment = tuple(int(self.grid[r + i, c + i]) for i in range(pattern_len))
                         # if pattern_len == 7:
                             # print(f"DEBUG L7 Check (D1) at ({r},{c}) for P{p}: Match={segment == pattern}, Seg={segment}, Pat={pattern}")
                         if segment == pattern:
                             add_threat_if_valid('d1')

                    # --- Check Diagonal Up-Right (Using self.grid) ---
                    if r >= pattern_len - 1 and c + pattern_len <= self.size:
                        segment = tuple(int(self.grid[r - i, c + i]) for i in range(pattern_len))
                        # if pattern_len == 7:
                            # print(f"DEBUG L7 Check (D2) at ({r},{c}) for P{p}: Match={segment == pattern}, Seg={segment}, Pat={pattern}")
                        if segment == pattern:
                            add_threat_if_valid('d2')

        # Note: Removed the previous complex boundary checks for closed fours.
        # The pattern itself now includes the opponent or edge check implicitly
        # by defining Closed Four as OXXXX. or .XXXXO.
        # Also removed the set conversion at the end, as uniqueness is handled during addition.

        # print(f"Found {len(threats)} threats for player {player}") # Debug
        return threats

    def copy(self):
        """Creates a deep copy of the board."""
        new_board = Board(self.size, self.win_length)
        new_board.grid = np.copy(self.grid)
        new_board.last_move = self.last_move
        new_board.forbidden_checked_pos = self.forbidden_checked_pos
        return new_board


# Example Usage (for testing forbidden moves):
if __name__ == '__main__':
    board = Board(size=15, win_length=5)

    # Test Overline
    print("\nTesting Overline...")
    board.place_stone(7, 7, BLACK, 0)
    board.place_stone(8, 8, WHITE, 0)
    board.place_stone(7, 8, BLACK, 0)
    board.place_stone(8, 9, WHITE, 0)
    board.place_stone(7, 9, BLACK, 0)
    board.place_stone(8, 10, WHITE, 0)
    board.place_stone(7, 10, BLACK, 0)
    board.place_stone(8, 11, WHITE, 0)
    board.place_stone(7, 11, BLACK, 0)  # 5th black stone
    board.place_stone(8, 12, WHITE, 0)
    board.print_board()
    print("Placing Black at (7, 12) makes 6-in-a-row (Overline)?")
    print(f"> Is Forbidden? {board.is_forbidden(7, 12)}")  # Should be True
    print(f"> Is Valid Move? {board.is_valid_move(7, 12, BLACK, 0)}") # Should be False
    board.print_board()  # Show forbidden marker '!' at (7, 12)

    # Reset board
    board = Board(size=15, win_length=5)

    # Test Three-Three
    print("\nTesting Three-Three...")
    board.place_stone(1, 2, BLACK, 0)
    board.place_stone(0, 0, WHITE, 0)
    board.place_stone(1, 3, BLACK, 0)
    board.place_stone(0, 1, WHITE, 0)
    board.place_stone(2, 2, BLACK, 0)
    board.place_stone(0, 2, WHITE, 0)
    board.place_stone(3, 2, BLACK, 0)
    board.place_stone(0, 3, WHITE, 0)
    board.print_board()
    print("Placing Black at (2, 3) creates two open threes (3-3)?")
    print(f"> Is Forbidden? {board.is_forbidden(2, 3)}")  # Should be True
    print(f"> Is Valid Move? {board.is_valid_move(2, 3, BLACK, 0)}") # Should be False
    board.print_board()  # Show '!' at (2, 3)

    # Reset board
    board = Board(size=15, win_length=5)

    # Test Four-Four (Simple Case)
    print("\nTesting Four-Four (Simple)...")
    board.place_stone(1, 2, BLACK, 0)
    board.place_stone(0, 0, WHITE, 0)
    board.place_stone(1, 3, BLACK, 0)
    board.place_stone(0, 1, WHITE, 0)
    board.place_stone(1, 4, BLACK, 0)  # First line of 3
    board.place_stone(0, 2, WHITE, 0)
    board.place_stone(2, 1, BLACK, 0)
    board.place_stone(0, 3, WHITE, 0)
    board.place_stone(3, 1, BLACK, 0)
    board.place_stone(0, 4, WHITE, 0)
    board.place_stone(4, 1, BLACK, 0)  # Second line of 3
    board.print_board()
    print("Placing Black at (1, 1) creates two fours (4-4)?")
    print(f"> Is Forbidden? {board.is_forbidden(1, 1)}")  # Should be True
    print(f"> Is Valid Move? {board.is_valid_move(1, 1, BLACK, 0)}") # Should be False
    board.print_board()

    # Reset board and test win condition again
    print("\nTesting Win Condition...")
    board = Board(size=15, win_length=5)
    board.place_stone(7, 7, BLACK, 0)
    board.place_stone(8, 8, WHITE, 0)
    board.place_stone(6, 7, BLACK, 0)
    board.place_stone(8, 9, WHITE, 0)
    board.place_stone(5, 7, BLACK, 0)
    board.place_stone(8, 10, WHITE, 0)
    board.place_stone(4, 7, BLACK, 0)
    board.place_stone(8, 11, WHITE, 0)
    # Last move for black to win
    print("Placing final winning stone for Black at (3, 7)")
    valid = board.place_stone(3, 7, BLACK, 0)
    board.print_board()
    print(f"> Move valid? {valid}") # Should be True
    print(f"> Black wins: {board.check_win(BLACK)}")  # Should be True
    print(f"> White wins: {board.check_win(WHITE)}")  # Should be False 