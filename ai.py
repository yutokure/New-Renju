import random
import math
import numpy as np
import time # Import time module
from board import Board, EMPTY, BLACK as BOARD_BLACK, WHITE as BOARD_WHITE

# Define players for Zobrist hashing (map board state to index)
ZOBRIST_PLAYERS = {BOARD_BLACK: 0, BOARD_WHITE: 1, EMPTY: 2}
NUM_ZOBRIST_PLAYERS = 2 # Only hash for Black and White stones

class AIBase:
    """Base class for different AI difficulties."""
    def __init__(self, player):
        # The player this AI represents (BOARD_BLACK or BOARD_WHITE)
        self.player = player
        self.opponent = BOARD_WHITE if player == BOARD_BLACK else BOARD_BLACK

    def find_move(self, board: Board, move_count):
        """Finds the next move for the AI.

        Args:
            board: The current board state.
            move_count: The current move count.

        Returns:
            tuple: (row, col) of the chosen move, or None if no valid move.
        """
        raise NotImplementedError("Subclasses must implement find_move")


class AIEasy(AIBase):
    """AI that plays completely randomly among valid empty cells."""
    def find_move(self, board: Board, move_count):
        """Finds a random *valid* move respecting opening and forbidden rules."""
        print(f"DEBUG [AIEasy]: find_move called. Player: {self.player}, Move Count: {move_count}") # DEBUG
        empty_cells = board.get_empty_cells()
        if not empty_cells:
            print("DEBUG [AIEasy]: No empty cells.") # DEBUG
            return None

        # Filter empty cells to get only valid moves
        valid_moves = []
        print(f"DEBUG [AIEasy]: Checking {len(empty_cells)} empty cells for validity...") # DEBUG
        for r, c in empty_cells:
            print(f"DEBUG [AIEasy]: Checking validity of ({r}, {c}) with move_count {move_count}...") # DEBUG
            is_valid = board.is_valid_move(r, c, self.player, move_count)
            print(f"DEBUG [AIEasy]: Result for ({r}, {c}): {is_valid}") # DEBUG
            if is_valid:
                valid_moves.append((r, c))

        if valid_moves:
            chosen_move = random.choice(valid_moves)
            print(f"DEBUG [AIEasy]: Found {len(valid_moves)} valid moves. Choosing: {chosen_move}") # DEBUG
            return chosen_move
        else:
            print("DEBUG [AIEasy]: No valid moves found.") # DEBUG
            return None # No valid moves exist


class AINormal(AIBase):
    """AI that checks for immediate wins, blocks, threats, then random."""
    def find_move(self, board: Board, move_count):
        print(f"DEBUG [AINormal]: find_move called. Player: {self.player}, Move Count: {move_count}") # DEBUG
        empty_cells = board.get_empty_cells()
        if not empty_cells:
            print("DEBUG [AINormal]: No empty cells.") # DEBUG
            return None

        opponent = self.opponent

        # --- Helper function to check pattern formation ---
        def check_pattern_created(r_check, c_check, p_check, pattern_tuple):
            pattern_str, length, check_indices = pattern_tuple # Unpack the tuple
            board.grid[r_check, c_check] = p_check # Temporarily place
            created = False
            temp_opponent = BOARD_WHITE if p_check == BOARD_BLACK else BOARD_BLACK # Opponent relative to p_check
            for dr, dc in [(0, 1), (1, 0), (1, 1), (1, -1)]:
                for offset in range(-length + 1, 1):
                    segment_states = []
                    positions = []
                    for i in range(length):
                        cr, cc = r_check + (offset + i) * dr, c_check + (offset + i) * dc
                        positions.append((cr, cc))
                        if board.is_within_bounds(cr, cc):
                            segment_states.append(str(board.grid[cr, cc]))
                        else:
                            # Treat border as opponent's stone for pattern matching
                            segment_states.append(str(temp_opponent))

                    current_pattern = "".join(segment_states)
                    # print(f"DEBUG Pattern Check: Pos ({r_check},{c_check}) Player {p_check} Dir {(dr,dc)} Offset {offset} -> '{current_pattern}' vs '{pattern_str}'")
                    if current_pattern == pattern_str:
                        is_relevant = False
                        # Check if the placed stone is part of the core pattern indices
                        for idx in check_indices:
                            if positions[idx] == (r_check, c_check):
                                is_relevant = True
                                break
                        if is_relevant:
                            created = True
                            # print(f"DEBUG Pattern Found!: {pattern_str} at ({r_check},{c_check}) dir {(dr, dc)}")
                            break
                if created:
                    break # Break outer loop as well if pattern found
            board.grid[r_check, c_check] = EMPTY # Revert the temporary placement
            return created

        # --- Pattern Definitions ---
        p_str = str(self.player)
        o_str = str(opponent)
        e_str = str(EMPTY)

        # Patterns: (pattern_string, length, relevant_indices_for_creation)
        open_four_pattern = (f"{e_str}{p_str}{p_str}{p_str}{p_str}{e_str}", 6, [1, 2, 3, 4])
        closed_four_patterns = [
            (f"{o_str}{p_str}{p_str}{p_str}{p_str}{e_str}", 6, [1, 2, 3, 4]),
            (f"{e_str}{p_str}{p_str}{p_str}{p_str}{o_str}", 6, [1, 2, 3, 4]),
        ]
        open_three_pattern = (f"{e_str}{p_str}{p_str}{p_str}{e_str}", 5, [1, 2, 3])
        opp_open_four_pattern = (f"{e_str}{o_str}{o_str}{o_str}{o_str}{e_str}", 6, [1, 2, 3, 4])
        opp_open_three_pattern = (f"{e_str}{o_str}{o_str}{o_str}{e_str}", 5, [1, 2, 3])

        # --- Move Selection Logic ---

        # Priority 1: Win
        for r, c in list(empty_cells):
            if board.is_valid_move(r, c, self.player, move_count):
                board.grid[r, c] = self.player
                original_last_move = board.last_move
                board.last_move = (r, c)
                won, _ = board.check_win(self.player)
                board.grid[r, c] = EMPTY
                board.last_move = original_last_move
                if won:
                    print(f"AINormal: Found winning move at ({r}, {c})")
                    return (r, c)

        # Priority 2: Block Opponent Win
        block_move = None
        for r, c in list(empty_cells):
            if board.is_valid_move(r, c, self.player, move_count):
                board.grid[r, c] = opponent
                original_last_move = board.last_move
                board.last_move = (r, c)
                opponent_wins, _ = board.check_win(opponent)
                board.grid[r, c] = EMPTY
                board.last_move = original_last_move
                if opponent_wins:
                    print(f"AINormal: Found blocking move at ({r}, {c})")
                    block_move = (r, c)
                    return block_move

        # Priority 3: Create Open Four
        for r, c in list(empty_cells):
            if board.is_valid_move(r, c, self.player, move_count):
                # Pass the single open_four_pattern tuple
                if check_pattern_created(r, c, self.player, open_four_pattern):
                    print(f"AINormal: Found move to create Open Four at ({r}, {c})")
                    return (r, c)

        # Priority 4: Block Opponent's Open Four
        opponent_threat_moves = []
        for r, c in list(empty_cells):
            if board.is_empty(r, c):
                # Pass the single opp_open_four_pattern tuple
                if check_pattern_created(r, c, opponent, opp_open_four_pattern):
                    opponent_threat_moves.append((r, c))

        if opponent_threat_moves:
            for block_r, block_c in opponent_threat_moves:
                # Check if *we* can legally block this threat
                if board.is_valid_move(block_r, block_c, self.player, move_count):
                    print(f"AINormal: Found move to block opponent Open Four at ({block_r}, {block_c})")
                    return (block_r, block_c)

        # Priority 5: Create Closed Four
        for r, c in list(empty_cells):
            if board.is_valid_move(r, c, self.player, move_count):
                 # Iterate through the list of closed_four_patterns
                 for pattern_tuple in closed_four_patterns:
                     if check_pattern_created(r, c, self.player, pattern_tuple):
                        print(f"AINormal: Found move to create Closed Four at ({r}, {c})")
                        return (r, c) # Return immediately if any closed four is created

        # Priority 6: Create Open Three
        for r, c in list(empty_cells):
            if board.is_valid_move(r, c, self.player, move_count):
                # Pass the single open_three_pattern tuple
                if check_pattern_created(r, c, self.player, open_three_pattern):
                     print(f"AINormal: Found move to create Open Three at ({r}, {c})")
                     return (r, c)

        # Priority 7: Block Opponent's Open Three
        opponent_threat_moves_3 = []
        for r, c in list(empty_cells):
             if board.is_empty(r, c):
                 # Pass the single opp_open_three_pattern tuple
                 if check_pattern_created(r, c, opponent, opp_open_three_pattern):
                     opponent_threat_moves_3.append((r, c))

        if opponent_threat_moves_3:
             for block_r, block_c in opponent_threat_moves_3:
                 if board.is_valid_move(block_r, block_c, self.player, move_count):
                     print(f"AINormal: Found move to block opponent Open Three at ({block_r}, {block_c})")
                     return (block_r, block_c)

        # Priority 8: Random Valid Move
        valid_moves = []
        for r_val, c_val in empty_cells:
            if board.is_valid_move(r_val, c_val, self.player, move_count):
                valid_moves.append((r_val, c_val))

        if valid_moves:
            chosen_move = random.choice(valid_moves)
            # print(f"AINormal: Found {len(valid_moves)} valid random moves. Choosing: {chosen_move}")
            return chosen_move
        else:
            # print("AINormal: No valid moves found at all.")
            return None


class AIHard(AIBase):
    """AI that uses Minimax with Alpha-Beta pruning and Iterative Deepening."""
    # Define detailed pattern scores inspired by reference implementation
    # Higher absolute values indicate higher priority. Defensive scores are higher.
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

    def __init__(self, player, depth=3, time_limit_sec=0.8): # Default depth 3, time limit 0.8s
        super().__init__(player)
        self.max_depth = depth # Store max depth allowed
        self.time_limit = time_limit_sec
        # Initialize Transposition Table and Zobrist Hashing
        self.transposition_table = {}
        self.zobrist_table = self._init_zobrist()
        # current_hash will be calculated at the start of find_move based on the actual board
        self.current_hash = 0
        # print(f"AIHard initialized for player {'Black' if player == BOARD_BLACK else 'White'} with Max Depth {self.max_depth}, Time Limit {self.time_limit}s")

    def _init_zobrist(self):
        """Initializes the Zobrist table with random 64-bit integers."""
        # Standard board size assumption (15x15) or get from board?
        # Assuming a max possible size for flexibility, e.g., 19x19
        # Need to know the actual board size used in the game.
        # Let's assume it's fixed or passed somehow. Using a common 15x15 for now.
        # TODO: Get board size dynamically if possible
        max_size = 19 # Assume max board size
        table = np.random.randint(1, 2**63 - 1, size=(max_size, max_size, NUM_ZOBRIST_PLAYERS), dtype=np.uint64)
        return table

    def _calculate_board_hash(self, board: Board):
        """Calculates the Zobrist hash for the entire current board state."""
        h = np.uint64(0)
        for r in range(board.size):
            for c in range(board.size):
                player_state = board.grid[r, c]
                if player_state != EMPTY:
                    player_index = ZOBRIST_PLAYERS[player_state]
                    h ^= self.zobrist_table[r, c, player_index]
        return h

    def find_move(self, board: Board, move_count):
        """Finds the best move using Iterative Deepening Minimax within a time limit,\n           with pre-checks for immediate wins/blocks.\n        """
        start_time = time.time()
        self.transposition_table = {} # Clear TT at the start of each find_move call
        self.current_hash = self._calculate_board_hash(board)

        empty_cells = board.get_empty_cells()
        valid_empty_cells = [(r, c) for r, c in empty_cells if board.is_valid_move(r, c, self.player, move_count)]

        if not valid_empty_cells:
            return None

        # --- Pre-Minimax Checks (similar to AI Normal) --- #
        # 1. Check for immediate win for self
        print(f"AIHard Pre-Check [Player {self.player}]: Checking {len(valid_empty_cells)} valid moves for immediate win...")
        original_last_move = board.last_move # Store original last_move
        for r, c in valid_empty_cells:
            # print(f"AIHard Pre-Check: Testing potential win at ({r},{c})...") # Reduce noise
            board.grid[r, c] = self.player
            board.last_move = (r, c) # <<< Temporarily set last_move for check_win
            won, win_info = board.check_win(self.player)
            board.grid[r, c] = EMPTY
            board.last_move = original_last_move # <<< Restore original last_move
            if won:
                print(f"AIHard Pre-Check: !!! WIN FOUND at ({r}, {c}) with line {win_info}! Returning immediately. !!!")
                return (r, c)
            # else: # Optional: log if not a win
            #     # print(f"AIHard Pre-Check: ({r},{c}) is not an immediate win.") # Reduce noise

        # 2. Check for immediate block of opponent's win
        block_win_move = None
        # original_last_move is already stored from check 1
        for r, c in valid_empty_cells:
            board.grid[r, c] = self.opponent
            board.last_move = (r, c) # <<< Temporarily set last_move for check_win
            opponent_wins, _ = board.check_win(self.opponent)
            board.grid[r, c] = EMPTY
            board.last_move = original_last_move # <<< Restore original last_move
            if opponent_wins:
                # Check if the blocking move itself is valid for the player
                if board.is_valid_move(r, c, self.player, move_count):
                    print(f"AIHard Pre-Check: Found blocking move for opponent win at ({r}, {c})")
                    block_win_move = (r, c)
                    break # Found the necessary block
        if block_win_move:
            return block_win_move

        # 3. Check for immediate block of opponent's open four (optional but good)
        # --- REMOVE THIS CHECK FOR PERFORMANCE/SIMPLICITY --- #
        # block_open_four_move = None
        # for r, c in valid_empty_cells:
        #      opponent_pattern_code = self._check_critical_pattern_at_move(board, r, c, self.opponent)
        #      if opponent_pattern_code == "P_OPEN_FOUR": # Opponent makes open four if they play here
        #          if board.is_valid_move(r, c, self.player, move_count):
        #              print(f"AIHard Pre-Check: Found blocking move for opponent open four at ({r}, {c})")
        #              block_open_four_move = (r,c)
        #              break
        # if block_open_four_move:
        #     return block_open_four_move

        # --- If no immediate critical move, proceed with Minimax --- #
        print("AIHard: No immediate win/block moves found. Starting Minimax search...")
        best_move_so_far = None

        # Select the first valid move as a fallback if time runs out immediately
        if valid_empty_cells:
            best_move_so_far = valid_empty_cells[0]
        else:
             return None # Should not happen if initial check passed

        # --- Iterative Deepening Loop (using self.max_depth, likely 2) --- #
        for current_depth in range(1, self.max_depth + 1):
            print(f"AIHard: Starting search at depth {current_depth}...")
            alpha = -math.inf
            beta = math.inf
            current_best_score = -math.inf
            current_best_move_this_depth = None

            # Use ordered adjacent moves for the root level search
            # Generate candidates based on the simplified heuristic
            ordered_initial_moves = self._get_ordered_adjacent_moves(board, self.player, move_count)
            if not ordered_initial_moves:
                 # Fallback if adjacent move generation fails unexpectedly
                 if best_move_so_far: return best_move_so_far
                 elif valid_empty_cells: return valid_empty_cells[0]
                 else: return None

            for r, c in ordered_initial_moves:
                # --- Time Check --- #
                elapsed_time = time.time() - start_time
                if elapsed_time > self.time_limit:
                    print(f"AIHard: Time limit exceeded during depth {current_depth} search. Returning best move from depth {current_depth - 1}.")
                    return best_move_so_far

                # --- Simulate Move and Call Minimax --- #
                board.grid[r, c] = self.player
                original_last_move = board.last_move
                board.last_move = (r,c)
                move_hash_change = self.zobrist_table[r, c, ZOBRIST_PLAYERS[self.player]]
                self.current_hash ^= move_hash_change

                score = self._minimax(board, current_depth - 1, alpha, beta, False, move_count + 1, self.current_hash)

                self.current_hash ^= move_hash_change
                board.grid[r, c] = EMPTY
                board.last_move = original_last_move

                if score > current_best_score:
                    current_best_score = score
                    current_best_move_this_depth = (r, c)

                alpha = max(alpha, current_best_score)
                # No beta pruning at root typically

            if current_best_move_this_depth is not None:
                best_move_so_far = current_best_move_this_depth
                print(f"AIHard: Depth {current_depth} complete. Best move found: {best_move_so_far} (Score: {current_best_score})")
            else:
                 print(f"AIHard: No best move found at depth {current_depth}. Keeping previous: {best_move_so_far}")

            elapsed_time_after_depth = time.time() - start_time
            if elapsed_time_after_depth > self.time_limit:
                 print(f"AIHard: Time limit exceeded after completing depth {current_depth}. Returning best move found.")
                 break

        final_elapsed = time.time() - start_time
        print(f"AIHard: Search complete. Chose move: {best_move_so_far} (Time: {final_elapsed:.3f}s)")
        return best_move_so_far

    # --- Helper to get ordered adjacent moves (used in minimax root) --- #
    def _get_ordered_adjacent_moves(self, board: Board, player: int, move_count: int):
        """Generates adjacent valid moves and orders them by the lightweight heuristic."""
        possible_moves_set = set()
        occupied_cells = list(zip(*np.where(board.grid != EMPTY)))
        search_radius = 1
        if not occupied_cells:
            center = board.size // 2
            if board.is_valid_move(center, center, player, move_count):
                possible_moves_set.add((center, center))
        else:
            for r_occ, c_occ in occupied_cells:
                for dr in range(-search_radius, search_radius + 1):
                    for dc in range(-search_radius, search_radius + 1):
                        if dr == 0 and dc == 0: continue
                        nr, nc = r_occ + dr, c_occ + dc
                        if board.is_within_bounds(nr, nc) and board.grid[nr, nc] == EMPTY:
                            if board.is_valid_move(nr, nc, player, move_count):
                                possible_moves_set.add((nr, nc))

        candidate_moves = list(possible_moves_set)
        if not candidate_moves: return []

        move_scores = []
        for r, c in candidate_moves:
            score = self._heuristic_score_move_sim(board, r, c, player, move_count)
            move_scores.append(((r, c), score))
        move_scores.sort(key=lambda item: item[1], reverse=True)
        return [move for move, score in move_scores]

    def _heuristic_score_move_sim(self, board: Board, r: int, c: int, player: int, move_count: int):
        """
        Extremely simplified heuristic focusing only on proximity for performance.
        Win/loss checks are removed as they were too slow.
        'player' is the player whose turn it is in the simulation.
        """
        # Only calculate proximity bonus
        proximity_bonus = 0
        for dr in range(-1, 2):
            for dc in range(-1, 2):
                if dr == 0 and dc == 0: continue
                nr, nc = r + dr, c + dc
                if board.is_within_bounds(nr, nc) and board.grid[nr, nc] != EMPTY:
                    proximity_bonus += 1
        return proximity_bonus

    def _minimax(self, board: Board, depth: int, alpha: float, beta: float, maximizing_player: bool, move_count: int, current_board_hash: np.uint64):
        """Minimax algorithm with Alpha-Beta pruning and Transposition Table.
           Includes candidate move generation (neighbor search) to limit branching factor.
        """
        original_alpha = alpha
        original_beta = beta

        # --- Transposition Table Lookup --- #
        tt_entry = self.transposition_table.get(current_board_hash)
        if tt_entry is not None:
            tt_score, tt_depth, tt_flag = tt_entry
            if tt_depth >= depth:
                if tt_flag == 'exact':
                    # print(f"TT Hit (Exact): d={depth}, h={current_board_hash}, score={tt_score}")
                    return tt_score
                elif tt_flag == 'lowerbound' and tt_score > alpha:
                    alpha = tt_score # Use stored lower bound to narrow alpha
                    # print(f"TT Hit (Lower): d={depth}, h={current_board_hash}, alpha updated to {alpha}")
                elif tt_flag == 'upperbound' and tt_score < beta:
                    beta = tt_score # Use stored upper bound to narrow beta
                    # print(f"TT Hit (Upper): d={depth}, h={current_board_hash}, beta updated to {beta}")
                if alpha >= beta:
                    # print(f"TT Cutoff: d={depth}, h={current_board_hash}, score={tt_score}")
                    return tt_score # Pruning based on TT info

        # --- Terminal State Check & Immediate Win/Loss Check --- #
        current_player_sim = self.player if maximizing_player else self.opponent
        opponent_sim = self.opponent if maximizing_player else self.player

        # Check if current player can win immediately (before checking depth)
        # Note: This check might be better placed within the candidate generation loop?
        # Let's check terminal state based on *previous* move first
        won_player = board.check_win(current_player_sim)[0]
        won_opponent = board.check_win(opponent_sim)[0]
        if won_player: return self.PATTERN_SCORES["p_win"] + depth
        if won_opponent: return self.PATTERN_SCORES["o_win"] - depth

        if depth <= 0:
             # Check for draw before evaluating
             if not board.get_empty_cells(): return 0
             return self._evaluate_board(board) # Simplified eval (win/loss only)

        # Check for draw
        empty_cells_check = board.get_empty_cells()
        if not empty_cells_check: return 0

        # --- Candidate Move Generation (Adjacent Cells Only) & Lightweight Ordering --- #
        possible_moves_set = set()
        occupied_cells = list(zip(*np.where(board.grid != EMPTY)))
        search_radius = 1

        if not occupied_cells:
            center = board.size // 2
            if board.is_valid_move(center, center, current_player_sim, move_count):
                possible_moves_set.add((center, center))
        else:
            for r_occ, c_occ in occupied_cells:
                for dr in range(-search_radius, search_radius + 1):
                    for dc in range(-search_radius, search_radius + 1):
                        if dr == 0 and dc == 0: continue
                        nr, nc = r_occ + dr, c_occ + dc
                        if board.is_within_bounds(nr, nc) and board.grid[nr, nc] == EMPTY:
                            if board.is_valid_move(nr, nc, current_player_sim, move_count):
                                possible_moves_set.add((nr, nc))

        candidate_moves = list(possible_moves_set)

        if not candidate_moves:
            return self._evaluate_board(board)

        # Check for immediate winning or blocking moves within candidates
        immediate_win_move = None
        immediate_block_move = None
        for r, c in candidate_moves:
            # Check player win
            board.grid[r, c] = current_player_sim
            if board.check_win(current_player_sim)[0]:
                immediate_win_move = (r, c)
            board.grid[r, c] = EMPTY # Revert
            if immediate_win_move: break # Found a win, no need to check others

        if not immediate_win_move:
             for r, c in candidate_moves:
                 # Check opponent win (block needed)
                 board.grid[r, c] = opponent_sim
                 if board.check_win(opponent_sim)[0]:
                     immediate_block_move = (r, c)
                 board.grid[r, c] = EMPTY # Revert
                 if immediate_block_move: break # Found a block, no need to check others

        # Prioritize immediate win/block if found
        if immediate_win_move:
            ordered_possible_moves = [immediate_win_move]
        elif immediate_block_move:
            ordered_possible_moves = [immediate_block_move]
        else:
            # Order the adjacent candidates using the extremely lightweight heuristic (proximity)
            move_scores = []
            for r, c in candidate_moves:
                score = self._heuristic_score_move_sim(board, r, c, current_player_sim, move_count)
                move_scores.append(((r, c), score))
            move_scores.sort(key=lambda item: item[1], reverse=True)
            ordered_possible_moves = [move for move, score in move_scores]

        # Store original last move before simulation loop
        original_last_move = board.last_move

        # --- Minimax Recursion --- #
        if maximizing_player:
            max_eval = -math.inf
            for r, c in ordered_possible_moves: # Iterate through ordered adjacent moves
                board.grid[r, c] = current_player_sim
                board.last_move = (r,c)
                # Calculate hash change for the move
                move_hash_change = self.zobrist_table[r, c, ZOBRIST_PLAYERS[current_player_sim]]
                next_hash = current_board_hash ^ move_hash_change

                eval_score = self._minimax(board, depth - 1, alpha, beta, False, move_count + 1, next_hash) # Increment move_count here
                board.grid[r, c] = EMPTY
                board.last_move = original_last_move
                max_eval = max(max_eval, eval_score)
                alpha = max(alpha, eval_score)
                if beta <= alpha:
                    break # Beta cut-off
            # --- Transposition Table Store --- #
            tt_flag = 'exact'
            if max_eval <= original_alpha: # Failed low (didn't raise alpha)
                tt_flag = 'upperbound'
            elif max_eval >= beta: # Failed high (caused beta cutoff)
                tt_flag = 'lowerbound'
            self.transposition_table[current_board_hash] = (max_eval, depth, tt_flag)
            # print(f"TT Store: d={depth}, h={current_board_hash}, score={max_eval}, flag={tt_flag}")
            return max_eval
        else: # Minimizing player
            min_eval = math.inf
            for r, c in ordered_possible_moves: # Iterate through ordered adjacent moves
                board.grid[r, c] = current_player_sim
                board.last_move = (r,c)
                # Calculate hash change for the move
                move_hash_change = self.zobrist_table[r, c, ZOBRIST_PLAYERS[current_player_sim]]
                next_hash = current_board_hash ^ move_hash_change

                eval_score = self._minimax(board, depth - 1, alpha, beta, True, move_count + 1, next_hash) # Increment move_count here
                board.grid[r, c] = EMPTY
                board.last_move = original_last_move
                min_eval = min(min_eval, eval_score)
                beta = min(beta, eval_score)
                if beta <= alpha:
                    break # Alpha cut-off
            # --- Transposition Table Store --- #
            tt_flag = 'exact'
            if min_eval <= alpha: # Failed low (caused alpha cutoff)
                tt_flag = 'upperbound'
            elif min_eval >= original_beta: # Failed high (didn't lower beta)
                tt_flag = 'lowerbound'
            self.transposition_table[current_board_hash] = (min_eval, depth, tt_flag)
            # print(f"TT Store: d={depth}, h={current_board_hash}, score={min_eval}, flag={tt_flag}")
            return min_eval

    def _evaluate_board(self, board: Board):
        """Evaluates the board state based on patterns found in all lines.
           Higher score is better for the AI player (self.player).
           Adds extra penalties for critical opponent threats.
        """
        total_score = 0
        opponent_open_three_penalty = self.PATTERN_SCORES["o_open_three"] * 2 # Extra penalty multiplier
        opponent_open_four_penalty = self.PATTERN_SCORES["o_open_four"] * 2 # Extra penalty multiplier
        # Add similar large bonus for player's open four/three? Maybe later.

        # Check all lines: horizontal, vertical, diagonals
        lines = self._get_all_lines(board)

        critical_threat_found = False # Flag to check if immediate loss was already evaluated

        for line in lines:
            # Use the updated evaluate_line method (returning max absolute score)
            line_eval_score = self._evaluate_line(line)

            # Check for immediate win/loss first
            if line_eval_score >= self.PATTERN_SCORES["p_win"] : return self.PATTERN_SCORES["p_win"]
            if line_eval_score <= self.PATTERN_SCORES["o_win"] : return self.PATTERN_SCORES["o_win"]

            # Add the line score (likely the most significant pattern's score)
            total_score += line_eval_score

            # Apply extra penalty if critical opponent threats are the dominant pattern in the line
            if line_eval_score == self.PATTERN_SCORES["o_open_four"]:
                 total_score += opponent_open_four_penalty # Add extra penalty
                 critical_threat_found = True
                 # print(f"DEBUG Eval Board: Extra penalty applied for Opponent Open Four. New total: {total_score}")
            elif line_eval_score == self.PATTERN_SCORES["o_open_three"]:
                 total_score += opponent_open_three_penalty # Add extra penalty
                 critical_threat_found = True
                 # print(f"DEBUG Eval Board: Extra penalty applied for Opponent Open Three. New total: {total_score}")

        # If no critical threats were found via max_abs_score in _evaluate_line,
        # maybe do a simpler check for their existence? (Less accurate due to overlap)
        # For now, rely on _evaluate_line returning the critical score if it's dominant.

        # Add a small bonus/penalty for center control (optional)
        # center = board.size // 2
        # if board.grid[center, center] == self.player: total_score += 5
        # elif board.grid[center, center] == self.opponent: total_score -= 5

        return total_score

    def _get_all_lines(self, board: Board):
        """Extracts all rows, columns, and diagonals from the board."""
        lines = []
        size = board.size
        grid = board.grid

        # Rows
        for r in range(size):
            lines.append(list(grid[r, :]))
        # Columns
        for c in range(size):
            lines.append(list(grid[:, c]))
        # Diagonals (top-left to bottom-right)
        for k in range(-size + 1, size):
            lines.append(list(grid.diagonal(k)))
        # Diagonals (top-right to bottom-left)
        # Use fliplr to get anti-diagonals
        grid_flipped = board.grid[:, ::-1]
        for k in range(-size + 1, size):
            lines.append(list(grid_flipped.diagonal(k)))

        return lines

    def _evaluate_line(self, line: list):
        """
        Evaluates a single line, focusing on win/loss and critical four-patterns.
        Returns the score of the most critical pattern found (max absolute value), or 0.
        """
        n = len(line)
        p = self.player
        o = self.opponent
        e = EMPTY
        found_scores = []

        # Define patterns to check (Win, Fours, Threes only)
        patterns_to_check = {
            # Win
            (p, p, p, p, p): self.PATTERN_SCORES["p_win"],
            (o, o, o, o, o): self.PATTERN_SCORES["o_win"],
            # Open Four
            (e, p, p, p, p, e): self.PATTERN_SCORES["p_open_four"],
            (e, o, o, o, o, e): self.PATTERN_SCORES["o_open_four"],
            # Closed Four
            (o, p, p, p, p, e): self.PATTERN_SCORES["p_closed_four"],
            (e, p, p, p, p, o): self.PATTERN_SCORES["p_closed_four"],
            (p, o, o, o, o, e): self.PATTERN_SCORES["o_closed_four"],
            (e, o, o, o, o, p): self.PATTERN_SCORES["o_closed_four"],
            # Open Three
            (e, p, p, p, e): self.PATTERN_SCORES["p_open_three"],
            (e, o, o, o, e): self.PATTERN_SCORES["o_open_three"],
            # Broken Three
            (e, p, p, e, p, e): self.PATTERN_SCORES["p_broken_three"],
            (e, p, e, p, p, e): self.PATTERN_SCORES["p_broken_three"],
            (e, o, o, e, o, e): self.PATTERN_SCORES["o_broken_three"],
            (e, o, e, o, o, e): self.PATTERN_SCORES["o_broken_three"],
            # Closed Three
            (o, p, p, p, e): self.PATTERN_SCORES["p_closed_three"],
            (e, p, p, p, o): self.PATTERN_SCORES["p_closed_three"],
            (p, o, o, o, e): self.PATTERN_SCORES["o_closed_three"],
            (e, o, o, o, p): self.PATTERN_SCORES["o_closed_three"],
        }
        # Simplified Edge Closed Fours
        if n >= 5:
            if tuple(line[:5]) == (p, p, p, p, e): patterns_to_check[(p,p,p,p,e)] = self.PATTERN_SCORES["p_closed_four"]
            if tuple(line[n-5:]) == (e, p, p, p, p): patterns_to_check[(e,p,p,p,p)] = self.PATTERN_SCORES["p_closed_four"]
            if tuple(line[:5]) == (o, o, o, o, e): patterns_to_check[(o,o,o,o,e)] = self.PATTERN_SCORES["o_closed_four"]
            if tuple(line[n-5:]) == (e, o, o, o, o): patterns_to_check[(e,o,o,o,o)] = self.PATTERN_SCORES["o_closed_four"]
        # Simplified Edge Closed Threes
        if n >= 4:
            if tuple(line[:4]) == (p, p, p, e): patterns_to_check[(p,p,p,e)] = self.PATTERN_SCORES["p_closed_three"]
            if tuple(line[n-4:]) == (e, p, p, p): patterns_to_check[(e,p,p,p)] = self.PATTERN_SCORES["p_closed_three"]
            if tuple(line[:4]) == (o, o, o, e): patterns_to_check[(o,o,o,e)] = self.PATTERN_SCORES["o_closed_three"]
            if tuple(line[n-4:]) == (e, o, o, o): patterns_to_check[(e,o,o,o)] = self.PATTERN_SCORES["o_closed_three"]

        # Sort by length descending (helps prioritize win/longer patterns)
        sorted_patterns = sorted(patterns_to_check.items(), key=lambda item: len(item[0]), reverse=True)

        # Iterate through the line using greedy approach
        i = 0
        while i < n:
            found_pattern_at_i = False
            for pattern_tuple, score in sorted_patterns:
                pattern_len = len(pattern_tuple)
                if i + pattern_len <= n:
                    segment = tuple(line[i : i + pattern_len])
                    if segment == pattern_tuple:
                        found_scores.append(score)
                        # If win/loss, return immediately
                        if score >= self.PATTERN_SCORES["p_win"] or score <= self.PATTERN_SCORES["o_win"]:
                             return score
                        i += pattern_len # Advance past found pattern
                        found_pattern_at_i = True
                        break
            if not found_pattern_at_i:
                i += 1

        # Return score with max absolute value
        if not found_scores:
            return 0
        else:
            max_abs_score = 0
            final_score = 0
            for s in found_scores:
                if abs(s) > max_abs_score:
                    max_abs_score = abs(s)
                    final_score = s
            return final_score


# Factory function to create AI instance based on difficulty
def create_ai(difficulty: str, player):
    """Factory function to create an AI instance."""
    if difficulty == "easy":
        return AIEasy(player)
    elif difficulty == "normal":
        return AINormal(player)
    elif difficulty == "hard":
        # Set desired max_depth and time_limit here
        # Increase time limit to allow deeper search
        # Reduce depth significantly to combat persistent time limit issues
        # Further reduce depth to 2 as depth 3 still times out
        return AIHard(player, depth=2, time_limit_sec=1.5) # Reduced depth to 2, time limit 1.5s
    else:
        print(f"Warning: Unknown AI difficulty '{difficulty}'. Defaulting to Easy.")
        return AIEasy(player)


# Example Usage
if __name__ == '__main__':
    from board import Board, BLACK as BOARD_BLACK, WHITE as BOARD_WHITE

    board = Board(size=7, win_length=4)  # Smaller board for testing

    # Setup scenario where White can win or Black needs to block
    # Add move_count=0 to all place_stone calls
    mc = 0 # Use a variable for clarity if needed, though 0 works fine here.
    board.place_stone(2, 2, BOARD_BLACK, mc); mc += 1
    board.place_stone(3, 3, BOARD_WHITE, mc); mc += 1
    board.place_stone(2, 3, BOARD_BLACK, mc); mc += 1
    board.place_stone(3, 4, BOARD_WHITE, mc); mc += 1
    board.place_stone(2, 4, BOARD_BLACK, mc); mc += 1
    board.place_stone(3, 5, BOARD_WHITE, mc); mc += 1 # White has 3 in a row
    board.place_stone(1, 5, BOARD_BLACK, mc); mc += 1

    print("Current board:")
    board.print_board()

    ai_normal_white = create_ai("normal", BOARD_WHITE)
    ai_normal_black = create_ai("normal", BOARD_BLACK)
    current_move_count = mc # Keep track of current move count for AI calls

    print("\nWhite's Turn (should find winning move):")
    white_move = ai_normal_white.find_move(board, current_move_count)
    print(f"Normal AI (White) chose: {white_move}") # Expecting (3, 2) or (3, 6)
    if white_move:
        board.place_stone(white_move[0], white_move[1], BOARD_WHITE, current_move_count)
        current_move_count += 1
    board.print_board()

    print("\nBlack's Turn (should find blocking move):")
    # Reset white's winning move for black's turn test
    if white_move:
        board.grid[white_move[0], white_move[1]] = EMPTY
        current_move_count -= 1 # Decrement count since move was reverted
    # Let White place one winning option again
    board.place_stone(3, 2, BOARD_WHITE, current_move_count); current_move_count += 1
    board.print_board()
    black_move = ai_normal_black.find_move(board, current_move_count)
    print(f"Normal AI (Black) chose: {black_move}") # Expecting (3, 6)
    if black_move:
        board.place_stone(black_move[0], black_move[1], BOARD_BLACK, current_move_count)
        current_move_count += 1
    board.print_board()

    print("\nHard AI White's Turn (should find winning move?):")
    ai_hard_white = create_ai("hard", BOARD_WHITE)
    # Use the latest move count for the AIHard test
    white_move_hard = ai_hard_white.find_move(board, current_move_count)
    print(f"Hard AI (White) chose: {white_move_hard}") # Behavior depends on depth/time
    if white_move_hard:
        board.place_stone(white_move_hard[0], white_move_hard[1], BOARD_WHITE, current_move_count)
        current_move_count += 1
    board.print_board() 