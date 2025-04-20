import numpy as np
from constants import DEFAULT_BOARD_SIZE, DEFAULT_WIN_LENGTH

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

    def is_valid_move(self, row, col, player, move_count):
        """Checks if a move is valid (bounds, empty, Renju rules)."""
        # print(f"DEBUG [Board]: is_valid_move checking ({row}, {col}) for player {player}, move_count {move_count}") # DEBUG

        # 1. Check bounds
        if not self.is_within_bounds(row, col):
            # print(f"DEBUG [Board]: Invalid - Out of bounds.") # DEBUG
            return False

        # 2. Check if cell is empty
        if not self.is_empty(row, col):
            # print(f"DEBUG [Board]: Invalid - Cell not empty.") # DEBUG
            return False

        # 3. Check Renju Opening Rules (Shukei)
        # print(f"DEBUG [Board]: Checking Shukei rules... Center: {self.center}, Size: {self.size}") # DEBUG
        if self.center is not None and self.size >= 5:
            center_r, center_c = self.center
            if move_count == 0:  # Black's 1st move
                # print("DEBUG [Board]: Checking Move 0 (Black 1st)") # DEBUG
                if (row, col) != self.center:
                    # print("DEBUG [Board]: Invalid - Move 0 must be center.") # DEBUG
                    return False
            elif move_count == 1:  # White's 1st move (2nd overall) - Specific Shukei positions
                # print("DEBUG [Board]: Checking Move 1 (White 1st) - Shukei") # DEBUG
                allowed_pos1 = (center_r - 1, center_c) # Directly above center
                allowed_pos2 = (center_r - 1, center_c + 1) # Diagonally up-right from center
                if (row, col) not in [allowed_pos1, allowed_pos2]:
                    print(f"DEBUG [Board]: Invalid - Move 1 must be {allowed_pos1} or {allowed_pos2}. Got ({row},{col})") # DEBUG
                    return False
            elif move_count == 2:  # Black's 2nd move (3rd overall)
                # print("DEBUG [Board]: Checking Move 2 (Black 2nd)") # DEBUG
                is_within_2 = abs(row - center_r) <= 2 and abs(col - center_c) <= 2
                if not is_within_2:
                    # print("DEBUG [Board]: Invalid - Move 2 must be within 2 steps of center.") # DEBUG
                    return False
                # Implicitly handled by is_empty: cannot be center or where White placed move 1
            # else:
                # print(f"DEBUG [Board]: Move Count {move_count} >= 3, Shukei rules do not restrict.") # DEBUG
        # else:
             # print(f"DEBUG [Board]: Shukei rules not applicable (Center: {self.center}, Size: {self.size})") # DEBUG

        # 4. Check Forbidden Moves (only for Black)
        if player == BLACK:
            # print(f"DEBUG [Board]: Checking forbidden moves for Black at ({row},{col})...") # DEBUG
            is_forbidden = self._is_forbidden(row, col, player)
            # print(f"DEBUG [Board]: Is forbidden? {is_forbidden}") # DEBUG
            if is_forbidden:
                # print(f"DEBUG [Board]: Invalid - Forbidden move for Black.") # DEBUG
                self.forbidden_checked_pos = (row, col) # Mark for visual feedback
                return False
        # else:
            # print(f"DEBUG [Board]: Not Black, skipping forbidden check.") # DEBUG

        # If all checks pass
        # print(f"DEBUG [Board]: Move ({row}, {col}) is VALID.") # DEBUG
        self.forbidden_checked_pos = None # Clear marker if move is valid
        return True

    def place_stone(self, row, col, player, move_count):
        """Places a stone on the board if the move is valid."""
        if self.is_valid_move(row, col, player, move_count):
            self.grid[row, col] = player
            self.last_move = (row, col)
            return True
        return False

    def check_win(self, player):
        """Checks if the player has won. Returns (bool, win_info tuple) or (False, None)."""
        if self.last_move is None:
            return False, None
        r, c = self.last_move
        if self.grid[r, c] != player:
            return False, None

        for dr, dc in DIRECTIONS:
            count = 1  # Start with the stone at (r, c)
            line_coords = [(r, c)] # Store coordinates of stones in the line

            # Count in the positive direction (dr, dc)
            cr, cc = r + dr, c + dc
            while self.is_within_bounds(cr, cc) and self.grid[cr, cc] == player:
                count += 1
                line_coords.append((cr, cc))
                cr += dr
                cc += dc

            # Count in the negative direction (-dr, -dc)
            cr, cc = r - dr, c - dc
            while self.is_within_bounds(cr, cc) and self.grid[cr, cc] == player:
                count += 1
                line_coords.append((cr, cc))
                cr -= dr
                cc -= dc

            # Standard Gomoku win condition: >= win_length stones
            if count >= self.win_length: # Modified condition to >= for standard Gomoku
                # Sort coordinates to find start and end points correctly
                line_coords.sort() # Sorting might mix up directions if needed later, but ok for start/end
                start_pos = line_coords[0]
                end_pos = line_coords[-1]
                win_info = (start_pos, end_pos, (dr, dc))
                return True, win_info

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
        """Checks if placing a BLACK stone at (r, c) is a forbidden move."""
        # Rule: Forbidden moves only apply to Black.
        # They are: Three-Three, Four-Four, and Overline (> win_length).
        # Assumes the check is for an empty cell within bounds.

        # Temporarily place the stone to check the resulting patterns
        self.grid[r, c] = BLACK
        forbidden = False
        open_threes = 0
        fours = 0  # Counts lines that form a four

        for dr, dc in DIRECTIONS:
            # 1. Check Overline
            line_len = self._count_line_length(r, c, dr, dc, BLACK)
            if line_len > self.win_length:
                forbidden = True
                break  # Overline is definitively forbidden

            # 2. Check Threes and Fours for 3-3 / 4-4 rules
            count, open_ends = self._count_line_details(r, c, dr, dc, BLACK)

            # Check for Open Three
            if count == 3 and open_ends == 2:
                open_threes += 1

            # Check for Four (includes closed fours for 4-4 rule)
            if count == 4:
                fours += 1

        # Revert the temporary placement *before* returning the result
        self.grid[r, c] = EMPTY

        if forbidden:  # Overline check result
            return True

        # Check for Three-Three or Four-Four
        if open_threes >= 2 or fours >= 2:
            return True

        # TODO: Add more robust check for complex 4-4 scenarios if needed.

        return False

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
        """
        Checks if placing a stone at (r, c) for the player results
        in a forbidden move (specifically for Black in standard Gomoku).
        Forbidden moves:
        1. Double Three (三三): Creates two simultaneous open threes.
        2. Double Four (四四): Creates two simultaneous fours (any type).
        3. Overline (長連): Creates a line of 6 or more stones.
        Assumes (r, c) is within bounds and currently empty.
        """
        if player != BLACK:
            return False # Only Black has forbidden moves

        # Temporarily place the stone to check patterns
        self.grid[r, c] = player

        overline_created = False
        open_threes = 0 # For 3-3 check
        fours = 0       # For 4-4 check

        # Check all 4 directions
        for dr, dc in DIRECTIONS:
            # --- 1. Check Overline --- Checks the entire line through (r, c)
            count = 1 # Start with the placed stone
            line_coords = [(r,c)]
            # Count positive direction
            for i in range(1, self.size):
                nr, nc = r + i * dr, c + i * dc
                if self.is_within_bounds(nr, nc) and self.grid[nr, nc] == player:
                    count += 1
                    line_coords.append((nr, nc))
                else:
                    break
            # Count negative direction
            for i in range(1, self.size):
                nr, nc = r - i * dr, c - i * dc
                if self.is_within_bounds(nr, nc) and self.grid[nr, nc] == player:
                    count += 1
                    line_coords.append((nr, nc))
                else:
                    break

            if count > self.win_length:
                overline_created = True
                break # Overline found, immediately forbidden

            # --- 2. Check if it creates exactly win_length (Winning move) --- #
            if count == self.win_length:
                self.grid[r, c] = EMPTY
                return False # Not forbidden because it's a winning move

            # --- 3. Count Threes and Fours for 3-3 / 4-4 checks --- #
            # Use _count_line_details for accurate counting including ends
            count_details, open_ends = self._count_line_details(r, c, dr, dc, player)

            # Check for Open Three (exactly 3 stones, both ends open)
            if count_details == 3 and open_ends == 2:
                open_threes += 1

            # Check for Four (exactly 4 stones, regardless of ends)
            if count_details == 4:
                fours += 1

        # Revert the temporary placement before returning the result
        self.grid[r, c] = EMPTY

        # Check forbidden conditions based on collected counts
        if overline_created:
            # print(f"DEBUG [Board]: Forbidden - Overline created.")
            return True
        if open_threes >= 2:
            # print(f"DEBUG [Board]: Forbidden - Double Three created ({open_threes} open threes)")
            return True
        if fours >= 2:
            # print(f"DEBUG [Board]: Forbidden - Double Four created ({fours} fours)")
            return True

        # If none of the above conditions met
        return False

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
        # forbidden_checked_pos is transient, probably don't need to copy
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