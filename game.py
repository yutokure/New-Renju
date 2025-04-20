import pygame
import json # Import json module
import datetime # Import datetime module
# import time # For potential AI delay
from constants import (
    SCREEN_WIDTH, SCREEN_HEIGHT, BOARD_COLOR, LINE_COLOR, BLACK, WHITE,
    CELL_SIZE, TEXT_COLOR, STATE_MENU, PLAYER_AI, PLAYER_HUMAN,
    GRAY, INVALID_MOVE_COLOR, GAMEOVER_OVERLAY_COLOR, MARGIN,
    ANIMATION_DURATION, BLINK_INTERVAL, BLINK_COUNT,
    BLINK_RADIUS_FACTOR, BLINK_COLOR_APPEAR, BLINK_COLOR_DISAPPEAR,
    POPUP_COLOR_DEFENSE, POPUP_COLOR_PURSUIT, POPUP_COLOR_ATTACK, # Added popup colors
    PLACING_ANIMATION_DURATION, PLACING_ANIMATION_START_SCALE # Added PLACING_ANIMATION_DURATION and PLACING_ANIMATION_START_SCALE constants
)
from board import (
    DIRECTIONS, Board, BLACK as BOARD_BLACK, WHITE as BOARD_WHITE, EMPTY,
    THREAT_OPEN_THREE, THREAT_CLOSED_FOUR, THREAT_OPEN_FOUR # 追加
)
from ui import Button, Checkbox, Telop, TextPopup # Added TextPopup import
from ai import create_ai, AIHard
# Import Joseki related components (Remove JosekiPopup)
from joseki import load_joseki, check_joseki # Removed JosekiPopup import
from collections import defaultdict # Add defaultdict import
import math # For evaluation infinity

# 色の定数を追加
BLUE = (0, 0, 255)
RED = (255, 0, 0)

# Threat/Win Line Styles
THREAT_LINE_WIDTH = 2 # Thinner lines for threats
WIN_LINE_WIDTH = 5    # Thicker line for win

class Game:
    """Handles the game screen logic, drawing, and player/AI interaction."""
    def __init__(self, screen, settings):
        self.screen = screen
        self.settings = settings
        self.font = pygame.font.Font(None, 30)
        self.small_font = pygame.font.Font(None, 24) # Font for move counter
        self.game_over_font = pygame.font.Font(None, 72)
        # --- Use a Japanese Font --- #
        # !!! Replace with the actual path to your Japanese font file !!!
        japanese_font_path = "./fonts/YasashisaGothicBold-V2.otf"
        try:
            self.telop_font = pygame.font.Font(japanese_font_path, 48)
        except pygame.error as e:
            print(f"Error loading Japanese font '{japanese_font_path}': {e}")
            print("Falling back to default font for telop.")
            self.telop_font = pygame.font.Font(None, 48) # Fallback
        self.evaluation_font = pygame.font.Font(None, 16) # Font for evaluation scores

        # Initialize Telop instance
        self.telop = Telop(screen_width=SCREEN_WIDTH, # Pass screen width
                           center_pos=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2),
                           font=self.telop_font)

        # Initialize Animation state
        self.animating_stones = [] # List of [(r, c, color), ...]
        self.animation_start_time = 0
        self.animation_blink_count = 0 # Remaining blinks
        self.show_blink = False # Whether to show blink circle in current frame

        # Initialize Text Popup manager
        self.text_popups = []
        # Initialize consecutive pursuit count for each player
        self.consecutive_pursuit_count = {BOARD_BLACK: 0, BOARD_WHITE: 0}

        # --- Stone Placing Animation State ---
        self.placing_stone_animation = False
        self.placing_animation_start_time = 0
        self.placing_animated_stone_info = None # (r, c, player)

        self.reset_game()

    def reset_game(self, move_history_to_load=None):
        """Resets the game state. Can optionally load a move history."""
        self.board = Board(
            size=self.settings.board_size, win_length=self.settings.win_length
        )
        self.game_over = False
        self.winner = None
        self.win_line = None # ★★★ Initialize win_line here ★★★
        self.current_player = BOARD_BLACK # Always start with Black unless loading history alters it
        self.move_history = []

        # Load history if provided
        if move_history_to_load:
            print(f"Loading move history with {len(move_history_to_load)} moves.")
            temp_board = Board(self.settings.board_size, self.settings.win_length)
            for i, move in enumerate(move_history_to_load):
                player = BOARD_BLACK if i % 2 == 0 else BOARD_WHITE
                # We need to place stones directly for loading, bypass normal validation for speed/simplicity
                if temp_board.is_within_bounds(move[0], move[1]) and temp_board.is_empty(move[0], move[1]):
                    temp_board.grid[move[0], move[1]] = player
                    temp_board.last_move = move
                    self.move_history.append(move) # Add to the game's history
                else:
                    print(f"Warning: Invalid move {(move[0], move[1])} found in loaded history at index {i}. Skipping.")
            # Set the actual board and current player based on loaded history
            self.board = temp_board
            if self.move_history: # If any moves were loaded
                 self.current_player = BOARD_BLACK if len(self.move_history) % 2 == 0 else BOARD_WHITE
                 # Check if the last move resulted in a win/draw
                 last_player = BOARD_WHITE if self.current_player == BOARD_BLACK else BOARD_BLACK
                 won, win_info = self.board.check_win(last_player)
                 if won:
                     self.game_over = True
                     self.winner = last_player
                     self.win_line = win_info
                 elif not self.board.get_empty_cells():
                      self.game_over = True
                      self.winner = None
            else:
                 self.current_player = BOARD_BLACK # Default if history was empty or all invalid

        # If not loading history, apply AI start setting
        elif self.settings.game_mode == (PLAYER_HUMAN, PLAYER_AI) and self.settings.ai_starts:
            self.current_player = BOARD_WHITE

        self.player_types = self.settings.get_player_types()
        self.ai_instances = {BOARD_BLACK: None, BOARD_WHITE: None}
        if self.player_types[0] == PLAYER_AI:
            self.ai_instances[BOARD_BLACK] = create_ai(
                self.settings.ai_difficulty, BOARD_BLACK
            )
        if self.player_types[1] == PLAYER_AI:
            self.ai_instances[BOARD_WHITE] = create_ai(
                self.settings.ai_difficulty, BOARD_WHITE
            )

        self.needs_redraw = True
        self.ai_thinking = False
        # self.move_history = [] # Already initialized or loaded above
        self.joseki_patterns = load_joseki()
        # self.joseki_popup = JosekiPopup() # Removed JosekiPopup instance
        self.invalid_move_pos = None
        self.invalid_move_timer = 0
        self.invalid_move_duration = 500
        # self.threat_lines = [] # Calculated on demand in draw
        # self.win_line = None # Initialized or loaded above

        # --- History/Replay State ---
        self.display_move_index = len(self.move_history) # Start at the latest move
        self.is_history_mode = False # Initialize to False, only enter history via button press
        self.history_board_cache = None # Cache for the reconstructed board

        # --- Research Mode State ---
        self.research_mode_enabled = False
        self.evaluation_cache = {} # Cache for { (r, c): score }
        self.evaluation_in_progress = False # Flag to prevent concurrent evaluation

        # --- Dynamic calculation of board position and size --- #
        # Define Y positions for top elements
        top_status_y = 20
        top_button_y = 60
        min_top_margin_for_board = top_button_y + 40 # Space above board below buttons
        min_bottom_margin_for_board = 80 # Space below board above history buttons

        # Calculate max possible board area height based on UI margins
        max_board_area_height = SCREEN_HEIGHT - min_top_margin_for_board - min_bottom_margin_for_board
        max_board_area_width = SCREEN_WIDTH - MARGIN * 2 # Use constant side margins

        # Calculate cell size based on the smaller dimension and board size
        cell_size_width = max_board_area_width // (self.settings.board_size - 1) if self.settings.board_size > 1 else max_board_area_width
        cell_size_height = max_board_area_height // (self.settings.board_size - 1) if self.settings.board_size > 1 else max_board_area_height
        self.cell_size = min(cell_size_width, cell_size_height, CELL_SIZE) # Use smaller cell size, cap at default max

        self.board_pixel_size = (self.board.size - 1) * self.cell_size
        self.start_x = (SCREEN_WIDTH - self.board_pixel_size) // 2
        # Position board below the top UI elements
        self.start_y = min_top_margin_for_board

        # If the board is very large vertically, center it within the allowed area
        allowed_board_area_height = SCREEN_HEIGHT - min_top_margin_for_board - min_bottom_margin_for_board
        if self.board_pixel_size < allowed_board_area_height:
             self.start_y = min_top_margin_for_board + (allowed_board_area_height - self.board_pixel_size) // 2
        # Else (if board pixel size >= allowed height), start_y remains min_top_margin_for_board

        # --- UI Buttons and Controls (Positions relative to screen/board) ---
        # Top Bar Buttons
        self.back_button = Button("Menu", (SCREEN_WIDTH - 80, top_button_y), self.font)
        save_button_width_estimate = 150
        save_button_spacing = 20
        self.save_button = Button("Save Game", (self.back_button.rect.left - save_button_width_estimate - save_button_spacing, top_button_y), self.font, width=save_button_width_estimate)
        # Research Mode Checkbox (Far Left Top)
        self.research_mode_checkbox = Checkbox("Research Mode", (20, top_button_y), self.small_font)

        # Game Over Buttons (Center Screen)
        button_y_gameover = SCREEN_HEIGHT // 2 + 100
        self.rematch_button = Button("Rematch", (SCREEN_WIDTH // 2 - 100, button_y_gameover), self.font, width=180)
        self.menu_button_gameover = Button("Menu", (SCREEN_WIDTH // 2 + 100, button_y_gameover), self.font, width=180)

        # History Buttons (Below Board, dynamic Y)
        history_btn_y = self.start_y + self.board_pixel_size + 40
        # Ensure buttons don't go off screen bottom
        history_btn_y = min(history_btn_y, SCREEN_HEIGHT - 40)
        history_btn_x_center = SCREEN_WIDTH // 2
        self.prev_move_button = Button("< Prev", (history_btn_x_center - 80, history_btn_y), self.font)
        self.next_move_button = Button("Next >", (history_btn_x_center + 80, history_btn_y), self.font)

        # Show "Game Start" telop
        self.telop.show("対局開始", 2000) # Show for 2 seconds
        # --- Force draw telop immediately ---
        self.draw() # Draw everything including the now visible telop
        pygame.display.flip() # Update screen
        # --- End Force draw --- #

        print("Game Reset" + (" with loaded history" if move_history_to_load else "")) # Debug
        if self.current_player == BOARD_WHITE and self.player_types[1] == PLAYER_AI:
             print("AI (White) starts.")
        elif self.current_player == BOARD_BLACK and self.player_types[0] == PLAYER_AI:
             print("AI (Black) starts.")
        else:
             print(f"Player {'Black' if self.current_player == BOARD_BLACK else 'White'} starts.")

        # --- Animation State --- #
        self.animating_stones = []
        self.animation_start_time = 0
        self.animation_blink_count = 0
        self.show_blink = False
        # Clear popups on reset
        self.text_popups = []
        # Reset consecutive pursuit count
        self.consecutive_pursuit_count = {BOARD_BLACK: 0, BOARD_WHITE: 0}

        # Reset placing animation state
        self.placing_stone_animation = False
        self.placing_animation_start_time = 0
        self.placing_animated_stone_info = None

    def _reconstruct_board(self, target_index):
        """Reconstructs the board state up to the target move index."""
        # print(f"DEBUG: Reconstructing board up to index {target_index}") # Debug
        if target_index < 0 or target_index > len(self.move_history):
            # print(f"DEBUG: Invalid target_index {target_index}") # Debug
            return None # Or maybe return empty board?

        # Use cache if available and valid
        if self.history_board_cache and self.history_board_cache['index'] == target_index:
            # print("DEBUG: Using cached board")
            return self.history_board_cache['board']

        temp_board = Board(self.settings.board_size, self.settings.win_length)
        for i in range(target_index):
            move = self.move_history[i]
            player = BOARD_BLACK if i % 2 == 0 else BOARD_WHITE
            # Direct placement, assume history is valid here
            if temp_board.is_within_bounds(move[0], move[1]) and temp_board.is_empty(move[0], move[1]):
                temp_board.grid[move[0], move[1]] = player
                temp_board.last_move = move # Update last move for reconstruction context
            else:
                # Should not happen if history was validated on load/during game
                print(f"Error reconstructing history at index {i}, move {move}")

        # Cache the result
        self.history_board_cache = {'index': target_index, 'board': temp_board}
        return temp_board

    def _get_current_board_for_display(self):
        """Returns the board object to be used for drawing, based on history mode."""
        if self.is_history_mode:
            # Reconstruct board if needed, or return cached
            board_to_draw = self._reconstruct_board(self.display_move_index)
            if board_to_draw is None: # Handle case where reconstruction failed or index is 0
                return Board(self.settings.board_size, self.settings.win_length) # Return empty board
            return board_to_draw
        else:
            return self.board # Use the live game board

    def _get_current_win_line_for_display(self):
         """Gets the win line for the currently displayed board state."""
         if self.is_history_mode:
             # Check win condition for the reconstructed board at the display index
             board_to_check = self._get_current_board_for_display()
             if board_to_check and self.display_move_index > 0:
                  last_player = BOARD_BLACK if (self.display_move_index - 1) % 2 == 0 else BOARD_WHITE
                  won, win_info = board_to_check.check_win(last_player)
                  return win_info if won else None
             return None
         else:
             # Use the live game's win line (set in _make_move)
             return self.win_line

    def _draw_board(self):
        """Draws the Gomoku board lines and star points (uses current display board size and calculated cell_size)."""
        board_to_draw = self._get_current_board_for_display()
        board_pixel_size = (board_to_draw.size - 1) * self.cell_size # Use instance cell_size
        # start_x and start_y are now calculated in reset_game and draw based on self.cell_size
        end_x = self.start_x + board_pixel_size
        end_y = self.start_y + board_pixel_size

        self.screen.fill(BOARD_COLOR)
        for i in range(board_to_draw.size):
            # Use self.cell_size for drawing
            x = self.start_x + i * self.cell_size
            pygame.draw.line(self.screen, LINE_COLOR, (x, self.start_y), (x, end_y))
            y = self.start_y + i * self.cell_size
            pygame.draw.line(self.screen, LINE_COLOR, (self.start_x, y), (end_x, y))
        # Draw star points based on the board being drawn and cell_size
        if board_to_draw.size >= 9: # Adjust star point logic for different sizes
            radius = self.cell_size // 6
            points = []
            if board_to_draw.size == 15:
                 points = [(3, 3), (3, 11), (11, 3), (11, 11), (7, 7)]
            elif board_to_draw.size == 19:
                 points = [(3,3), (3,9), (3,15), (9,3), (9,9), (9,15), (15,3), (15,9), (15,15)]
            elif board_to_draw.size >= 9: # Generic for others >= 9
                 mid = board_to_draw.size // 2
                 offset = 3 if board_to_draw.size < 15 else 4
                 points.append((mid, mid))
                 points.append((offset, offset))
                 points.append((offset, board_to_draw.size - 1 - offset))
                 points.append((board_to_draw.size - 1 - offset, offset))
                 points.append((board_to_draw.size - 1 - offset, board_to_draw.size - 1 - offset))

            for r_idx, c_idx in points:
                center_x = self.start_x + c_idx * self.cell_size
                center_y = self.start_y + r_idx * self.cell_size
                pygame.draw.circle(
                    self.screen, LINE_COLOR, (center_x, center_y), max(1, radius) # Ensure radius >= 1
                )

    def _draw_stones_and_markers(self):
        """Draws stones, markers, AND evaluation scores (uses current display board and cell_size)."""
        board_to_draw = self._get_current_board_for_display()
        stone_radius = self.cell_size // 2 - 2
        last_move_marker_radius = stone_radius // 3
        invalid_marker_size = self.cell_size * 0.6

        # Determine the player whose turn it *would* be at this history index
        current_player_at_index = BOARD_BLACK if self.display_move_index % 2 == 0 else BOARD_WHITE

        # Draw invalid move markers (only if NOT in history mode)
        if not self.is_history_mode:
            move_count = len(self.move_history) # Use actual move count for live game
            invalid_surface = pygame.Surface((invalid_marker_size, invalid_marker_size), pygame.SRCALPHA)
            invalid_surface.fill(INVALID_MOVE_COLOR)
            for r in range(board_to_draw.size):
                for c in range(board_to_draw.size):
                    if board_to_draw.grid[r, c] == EMPTY:
                        # Check validity for the *live* current player
                        if not self.board.is_valid_move(r, c, self.current_player, move_count):
                            center_x = self.start_x + c * self.cell_size
                            center_y = self.start_y + r * self.cell_size
                            # Don't draw invalid marker if the placing animation is happening there
                            if not (self.placing_stone_animation and self.placing_animated_stone_info[:2] == (r, c)):
                                rect = invalid_surface.get_rect(center=(center_x, center_y))
                                self.screen.blit(invalid_surface, rect)

        # Draw stones (use self.cell_size)
        for r in range(board_to_draw.size):
            for c in range(board_to_draw.size):
                player = board_to_draw.grid[r, c]

                # Check if this is the stone being animated for placing
                is_placing_animated = False
                if self.placing_stone_animation and self.placing_animated_stone_info:
                    anim_r, anim_c, anim_player = self.placing_animated_stone_info
                    if r == anim_r and c == anim_c:
                        is_placing_animated = True
                        player = anim_player # Use the player from animation info

                if player != EMPTY: # Draw if stone exists or is being placed
                    center_x = self.start_x + c * self.cell_size
                    center_y = self.start_y + r * self.cell_size
                    color = BLACK if player == BOARD_BLACK else WHITE

                    if is_placing_animated:
                        # Calculate animation progress and properties
                        now = pygame.time.get_ticks()
                        elapsed = now - self.placing_animation_start_time
                        progress = min(1.0, elapsed / PLACING_ANIMATION_DURATION)

                        # Scale from START_SCALE down to 1.0
                        current_scale = PLACING_ANIMATION_START_SCALE + (1.0 - PLACING_ANIMATION_START_SCALE) * progress
                        # Alpha from 0 to 255
                        current_alpha = 255 * progress

                        # Calculate size and create surface
                        current_radius = int(stone_radius * current_scale)
                        if current_radius < 1: current_radius = 1 # Ensure radius is at least 1
                        stone_size = current_radius * 2
                        temp_surface = pygame.Surface((stone_size, stone_size), pygame.SRCALPHA)
                        pygame.draw.circle(temp_surface, color, (current_radius, current_radius), current_radius)
                        temp_surface.set_alpha(int(current_alpha))

                        # Blit the scaled and faded surface
                        blit_rect = temp_surface.get_rect(center=(center_x, center_y))
                        self.screen.blit(temp_surface, blit_rect)

                    else:
                        # Draw normal stone if not animating
                        pygame.draw.circle(
                            self.screen, color, (center_x, center_y), max(1, stone_radius)
                        )

                    # Draw marker on the last placed stone *for the currently displayed history index*
                    # Don't draw last move marker if this stone is being animated
                    if not is_placing_animated and board_to_draw.last_move == (r, c):
                        marker_color = GRAY
                        pygame.draw.circle(
                            self.screen, marker_color, (center_x, center_y),
                            max(1, last_move_marker_radius) # Ensure radius >= 1
                         )

        # Draw feedback for the specific invalid click (only in live mode)
        if not self.is_history_mode and self.invalid_move_pos:
            r_inv, c_inv = self.invalid_move_pos
            center_x = self.start_x + c_inv * self.cell_size
            center_y = self.start_y + r_inv * self.cell_size
            radius = self.cell_size // 2
            pygame.draw.circle(self.screen, RED, (center_x, center_y), radius, 2)

        # Draw evaluation scores if research mode is enabled (use self.cell_size)
        if self.research_mode_enabled and not self.evaluation_in_progress:
            for r in range(board_to_draw.size):
                for c in range(board_to_draw.size):
                    if board_to_draw.grid[r, c] == EMPTY:
                        score = self.evaluation_cache.get((r, c))
                        # Check if score is valid number or +/- inf before rendering
                        if isinstance(score, (int, float)):
                            if score == math.inf:
                                score_str = "Inf"
                            elif score == -math.inf:
                                score_str = "-Inf"
                            else:
                                score_str = f"{score:.0f}" # Display as integer for clarity
                            # Choose color based on score
                            color = GRAY
                            # Adjust thresholds based on expected score range from _evaluate_board
                            eval_threshold = 10000 # Example threshold
                            if score > eval_threshold: color = (0, 200, 0) # Green
                            elif score < -eval_threshold: color = (200, 0, 0) # Red

                            score_surf = self.evaluation_font.render(score_str, True, color)
                            center_x = self.start_x + c * self.cell_size
                            center_y = self.start_y + r * self.cell_size
                            score_rect = score_surf.get_rect(center=(center_x, center_y))
                            # Optional: Add background for readability
                            # pygame.draw.rect(self.screen, BOARD_COLOR, score_rect.inflate(2,2))
                            self.screen.blit(score_surf, score_rect)
                        elif score == "Err":
                             # Draw error indicator (e.g., a small red X)
                             center_x = self.start_x + c * self.cell_size
                             center_y = self.start_y + r * self.cell_size
                             err_surf = self.evaluation_font.render("X", True, RED)
                             err_rect = err_surf.get_rect(center=(center_x, center_y))
                             self.screen.blit(err_surf, err_rect)
                        # else: score is None (invalid move), draw nothing

        # --- Draw Blinking Animation --- #
        if self.animation_blink_count > 0 and self.show_blink:
            stone_radius = self.cell_size // 2 - 2 # Use stone radius
            blink_line_width = 2 # Line thickness for the circle
            for r_anim, c_anim, blink_color in self.animating_stones:
                 center_x = self.start_x + c_anim * self.cell_size
                 center_y = self.start_y + r_anim * self.cell_size
                 # Create a surface large enough for the stone radius outline
                 surface_size = stone_radius * 2
                 blink_surface = pygame.Surface((surface_size, surface_size), pygame.SRCALPHA)
                 # Draw an outline circle on the surface
                 # Use max(1, stone_radius) to avoid radius 0 error for very small cell_size
                 pygame.draw.circle(blink_surface, blink_color, (stone_radius, stone_radius), max(1, stone_radius), width=blink_line_width)
                 # Blit the surface centered on the stone
                 blit_pos_x = center_x - stone_radius
                 blit_pos_y = center_y - stone_radius
                 self.screen.blit(blink_surface, (blit_pos_x, blit_pos_y))

    def _get_board_pos_from_mouse(self, mouse_pos):
        """Converts mouse coordinates to board row and column indices (uses self.cell_size)."""
        mouse_x, mouse_y = mouse_pos
        # Use self.cell_size for calculations
        half_cell = self.cell_size // 2
        board_rect = pygame.Rect(
            self.start_x - half_cell, self.start_y - half_cell,
            self.board_pixel_size + self.cell_size,
            self.board_pixel_size + self.cell_size
        )
        if not board_rect.collidepoint(mouse_x, mouse_y):
            return None, None
        col = round((mouse_x - self.start_x) / self.cell_size)
        row = round((mouse_y - self.start_y) / self.cell_size)
        if 0 <= row < self.board.size and 0 <= col < self.board.size:
            return row, col
        else:
            return None, None

    def _is_human_turn(self):
        """Checks if the current player is human."""
        player_index = 0 if self.current_player == BOARD_BLACK else 1
        return self.player_types[player_index] == PLAYER_HUMAN

    def _save_game(self):
        """Saves the current game settings and move history to a JSON file named with timestamp."""
        if self.is_history_mode:
            print("Cannot save while viewing history.")
            return

        # Generate filename with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"gomoku_save_{timestamp}.json"

        # Convert potential NumPy types to standard Python types for JSON serialization
        serializable_settings = {
            "board_size": int(self.settings.board_size),
            "win_length": int(self.settings.win_length),
            "game_mode": self.settings.game_mode,
            "ai_difficulty": self.settings.ai_difficulty,
            "ai_starts": self.settings.ai_starts,
        }
        serializable_history = [
            (int(move[0]), int(move[1])) for move in self.move_history
        ]

        save_data = {
            "settings": serializable_settings,
            "move_history": serializable_history,
        }

        try:
            with open(filename, 'w') as f:
                json.dump(save_data, f, indent=4)
            print(f"Game saved successfully to {filename}")
        except IOError as e:
            print(f"Error saving game to {filename}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred during saving: {e}")

    def handle_event(self, event):
        """Handles events for game screen, including history and save buttons."""
        # Always handle Menu button
        if self.back_button.handle_event(event) == "Menu":
            return STATE_MENU

        # Handle Game Over buttons if game is over and not in history mode
        if self.game_over and not self.is_history_mode:
            if self.rematch_button.handle_event(event) == "Rematch":
                self.reset_game()
                return None
            if self.menu_button_gameover.handle_event(event) == "Menu":
                return STATE_MENU

        # Handle History Navigation and Save Buttons (available always, except AI thinking)
        if not self.ai_thinking:
            prev_clicked = self.prev_move_button.handle_event(event) == "< Prev"
            next_clicked = self.next_move_button.handle_event(event) == "Next >"
            save_clicked = self.save_button.handle_event(event) == "Save Game"

            if prev_clicked:
                if self.display_move_index > 0:
                    self.display_move_index -= 1
                    self.is_history_mode = True # Enter history mode
                    self.history_board_cache = None # Invalidate cache
                    self.needs_redraw = True
                    print(f"History: Moved to index {self.display_move_index}")
                return None # Consume event

            if next_clicked:
                if self.display_move_index < len(self.move_history):
                    self.display_move_index += 1
                    self.history_board_cache = None # Invalidate cache
                    self.needs_redraw = True
                    print(f"History: Moved to index {self.display_move_index}")
                    # If we reached the current actual game state, exit history mode
                    if self.display_move_index == len(self.move_history):
                         self.is_history_mode = False
                         print("History: Reached current game state.")
                return None # Consume event

            if save_clicked:
                 print("Save button clicked.")
                 self._save_game() # Call the save function (no filename needed)
                 return None # Consume event

        # Handle Research Mode Checkbox click (always available except AI thinking)
        if not self.ai_thinking:
            if self.research_mode_checkbox.handle_event(event):
                 self.research_mode_enabled = self.research_mode_checkbox.checked
                 print(f"Research Mode Toggled: {'Enabled' if self.research_mode_enabled else 'Disabled'}")
                 if self.research_mode_enabled:
                     self.evaluation_cache.clear()
                     self._evaluate_empty_cells() # Trigger evaluation immediately
                 else:
                      self.evaluation_cache.clear()
                 self.needs_redraw = True
                 return None # Consume event

        # Handle Gameplay Input
        if not self.is_history_mode and not self.ai_thinking and self._is_human_turn() and not self.game_over:
            # Check if the click was NOT on the checkbox
            # Need to update clickable_area check if checkbox moved
            # Re-get mouse pos as event.pos might be old if checkbox handled event
            current_mouse_pos = pygame.mouse.get_pos()
            if not self.research_mode_checkbox.clickable_area.collidepoint(current_mouse_pos):
                 if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                     row, col = self._get_board_pos_from_mouse(event.pos) # Use event.pos for click location
                     if row is not None and col is not None:
                         move_made = self._make_move(row, col)
                         if move_made:
                             # --- Force redraw immediately after human move --- #
                             # print("DEBUG: Human move made, forcing immediate redraw...") # Comment out
                             self.draw() # Draw the updated board state
                             pygame.display.flip() # Update the actual screen
                             # --- End Force redraw --- #
                             if self.research_mode_enabled:
                                  # Re-evaluate AFTER the move is made and player switched
                                  self.evaluation_cache.clear()
                                  self._evaluate_empty_cells()
                     return None
        return None # No state change by default

    def _start_threat_animation(self, added_threats, removed_threats):
        """Starts the blinking animation for added/removed threats simultaneously, prioritizing appear (blue)."""
        self.animating_stones = []
        animation_triggered = False
        stones_to_animate = [] # Store tuples of (r, c, color)
        coords_for_blue = set() # Track stones already marked for blue blinking

        # Process added threats first (Blue)
        if added_threats:
            print(f"DEBUG: Processing APPEAR animation for {len(added_threats)} threats") # Debug
            for threat_info in added_threats:
                if len(threat_info) >= 5:
                    current_stones = set(threat_info[4]) # Get stone coords for this threat
                    coords_for_blue.update(current_stones) # Add them to the blue set
                else:
                     print(f"Warning: Added threat info missing stone coords: {threat_info}")
            # Add all blue stones to the main animation list
            for r, c in coords_for_blue:
                 stones_to_animate.append((r, c, BLINK_COLOR_APPEAR))

        # Process removed threats (Red), avoiding overlap with blue
        removed_stone_coords = set()
        if removed_threats:
            print(f"DEBUG: Processing DISAPPEAR animation for {len(removed_threats)} threats") # Debug
            for threat_info in removed_threats:
                if len(threat_info) >= 5:
                    removed_stone_coords.update(threat_info[4])
                else:
                    print(f"Warning: Removed threat info missing stone coords: {threat_info}")
            # Add red stones only if they weren't already marked for blue
            for r, c in removed_stone_coords:
                 if (r, c) not in coords_for_blue:
                     stones_to_animate.append((r, c, BLINK_COLOR_DISAPPEAR))
                 # else: print(f"DEBUG: Stone ({r},{c}) appeared, prioritizing blue blink.")

        if stones_to_animate:
            self.animating_stones = stones_to_animate
            self.animation_start_time = pygame.time.get_ticks()
            self.animation_blink_count = BLINK_COUNT * 2 # Total states (on/off)
            self.show_blink = True # Start with blink visible
            self.needs_redraw = True
            animation_triggered = True

        if animation_triggered:
             print(f"DEBUG: Animation started. Total blinking stones: {len(self.animating_stones)}")

    def _make_move(self, row, col):
         """Attempts to make a move, checks win/threats/joseki, switches player, starts animation."""
         current_player = self.current_player
         opponent_player = BOARD_WHITE if current_player == BOARD_BLACK else BOARD_BLACK
         # Get threats *before* the move
         threats_before_list = self.board.find_threats(current_player) + self.board.find_threats(opponent_player)

         move_count = len(self.move_history)
         if self.board.place_stone(row, col, current_player, move_count):
            self.needs_redraw = True
            self.move_history.append((row, col))
            self.invalid_move_pos = None # Clear invalid click feedback
            self.win_line = None

            # Check Joseki
            matched_joseki = check_joseki(
                self.move_history, self.joseki_patterns, self.board.size
            )
            if matched_joseki:
                # Display Joseki name via Telop for 1 second
                print(f"DEBUG: Joseki matched: {matched_joseki}. Showing telop.") # Debug
                self.telop.show(matched_joseki, 1000) # Show for 1000ms
                # Also show the original popup (optional, can be removed)
                # self.joseki_popup.show(matched_joseki) # Removed JosekiPopup show call

            # Check Win
            won, win_info = self.board.check_win(current_player)
            if won:
                self.game_over = True
                self.winner = current_player
                self.win_line = win_info
                winner_name = 'Black' if current_player == BOARD_BLACK else 'White'
                print(f"Game Over! Winner: {winner_name}")
            else:
                # Check Draw
                if not self.board.get_empty_cells():
                    self.game_over = True
                    self.winner = None # Indicates a draw
                    print("Game Over! It's a draw.")
                else:
                    self._switch_player()

            # Get threats *after* the move
            threats_after_list = self.board.find_threats(current_player) + self.board.find_threats(opponent_player)

            # Compare threat sets based on frozenset of stone coordinates
            def get_threat_id(threat_info):
                # Ensure threat_info has the 5th element (player_stone_coords)
                if len(threat_info) >= 5 and isinstance(threat_info[4], list):
                    return frozenset(threat_info[4])
                return None # Return None if format is unexpected

            threat_ids_before = {get_threat_id(t) for t in threats_before_list if get_threat_id(t)}
            threat_ids_after = {get_threat_id(t) for t in threats_after_list if get_threat_id(t)}

            added_threat_ids = threat_ids_after - threat_ids_before
            removed_threat_ids = threat_ids_before - threat_ids_after

            # Get the full threat info tuples corresponding to the added/removed IDs
            added_threats_info = [t for t in threats_after_list if get_threat_id(t) in added_threat_ids]
            removed_threats_info = [t for t in threats_before_list if get_threat_id(t) in removed_threat_ids]

            # --- Start Placing Animation --- #
            self.placing_stone_animation = True
            self.placing_animation_start_time = pygame.time.get_ticks()
            self.placing_animated_stone_info = (row, col, current_player)
            print(f"DEBUG: Started placing animation for ({row},{col}), player {current_player}")

            # --- Determine and add Text Popups --- #
            popups_to_add = []
            # Get the player who just moved BEFORE switching
            player_who_moved = current_player

            move_pos = (row, col)
            popup_base_center_x = self.start_x + col * self.cell_size
            popup_base_center_y = self.start_y + row * self.cell_size
            popup_base_pos = (popup_base_center_x, popup_base_center_y)

            pursuit_added = False
            defense_added = False

            if added_threats_info:
                # Increment pursuit count for the player who moved
                self.consecutive_pursuit_count[player_who_moved] += 1
                count = self.consecutive_pursuit_count[player_who_moved]
                popup_text = "追い手" if count == 1 else f"追い手×{count}"
                popups_to_add.append({"text": popup_text, "color": POPUP_COLOR_PURSUIT})
                pursuit_added = True # Set flag to skip other checks
                print(f"DEBUG Popups: '{popup_text}' triggered at {move_pos} for player {player_who_moved} (Count: {count})")
            else:
                # Reset pursuit count for the player who moved if they didn't make a pursuit move
                self.consecutive_pursuit_count[player_who_moved] = 0

                # Check for defense and attack only if no pursuit was added
                if removed_threats_info:
                    popups_to_add.append({"text": "防手", "color": POPUP_COLOR_DEFENSE})
                    defense_added = True
                    print(f"DEBUG Popups: '防手' triggered at {move_pos}")

                # Check for "攻手"
                if self._check_if_move_created_three(self.board, row, col, player_who_moved):
                    # Add attack popup (stacking will handle if defense also added)
                    popups_to_add.append({"text": "攻手", "color": POPUP_COLOR_ATTACK})
                    print(f"DEBUG Popups: '攻手' triggered at {move_pos}")

            # --- Add and stack popups --- #
            num_popups = len(popups_to_add)
            base_offset_y = -30 # Default vertical offset
            vertical_spacing = -25 # Space between stacked popups (negative means going up)
            for i, popup_data in enumerate(popups_to_add):
                # Calculate vertical offset for stacking
                # Center the stack around the base offset
                stack_offset = base_offset_y + (i - (num_popups - 1) / 2) * vertical_spacing
                # Create the popup with adjusted position (using a TextPopup specific offset)
                # Use self.telop_font as requested
                popup = TextPopup(popup_data["text"], popup_base_pos, self.telop_font, 1000, popup_data["color"], offset_y=int(stack_offset))
                popup.show()
                self.text_popups.append(popup)

            # Start blinking animation AFTER popups are potentially added
            if added_threats_info or removed_threats_info:
                self._start_threat_animation(added_threats_info, removed_threats_info)

            return True # Indicate move was successful
         else:
            # Invalid move attempted
            print("Invalid move.")
            self.invalid_move_pos = (row, col) # Store position for feedback circle
            self.invalid_move_timer = pygame.time.get_ticks() # Start feedback timer
            self.needs_redraw = True # Need to redraw to show feedback
            return False # Indicate move failed

    def _check_if_move_created_three(self, board, r, c, player):
        """Checks if placing the stone at (r, c) creates any three-in-a-row (normal or jumping)."""
        # This check runs AFTER the stone is already placed on the board by _make_move
        # So, we don't need to temporarily place/revert here.

        if board.grid[r, c] != player:
            # Should not happen if called correctly after placing
            print(f"Warning: _check_if_move_created_three called for cell not matching player at ({r},{c})")
            return False

        for dr, dc in DIRECTIONS:
            # Use _count_line_details to check the line length through (r, c)
            count_details, _ = board._count_line_details(r, c, dr, dc, player)
            if count_details == 3:
                # print(f"DEBUG: Move ({r},{c}) created a three in direction ({dr},{dc}). Count: {count_details}") # Debug
                return True # Found a three-in-a-row

        return False # No three-in-a-row found

    def _switch_player(self):
        """Switches the current player."""
        self.current_player = (
            BOARD_WHITE if self.current_player == BOARD_BLACK else BOARD_BLACK
        )
        turn_name = 'Black' if self.current_player == BOARD_BLACK else 'White'
        print(f"Turn: {turn_name}")

    def update(self):
        """Handles AI moves, UI element updates, and animations."""
        # self.joseki_popup.update() # Removed JosekiPopup update

        # Update invalid move feedback timer
        if self.invalid_move_pos:
            if pygame.time.get_ticks() - self.invalid_move_timer > self.invalid_move_duration:
                self.invalid_move_pos = None
                self.needs_redraw = True

        # Call Telop update here, after potential state changes
        telop_is_active = self.telop.update()
        # Force redraw if telop is animating/visible
        if telop_is_active:
            self.needs_redraw = True

        # Update Text Popups FIRST (so they animate even during blinking)
        # Iterate backwards to allow removal during iteration
        popup_updated = False
        for i in range(len(self.text_popups) - 1, -1, -1):
            popup = self.text_popups[i]
            if popup.update(): # update returns True if still active
                 popup_updated = True
            else: # update returned False, popup duration passed
                self.text_popups.pop(i)
        # If any popup was updated (is still active), force redraw
        if popup_updated:
             self.needs_redraw = True

        # --- Update Placing Animation State --- #
        placing_anim_active = False
        if self.placing_stone_animation:
            placing_anim_active = True # Assume active until duration check
            now = pygame.time.get_ticks()
            elapsed = now - self.placing_animation_start_time
            if elapsed >= PLACING_ANIMATION_DURATION:
                self.placing_stone_animation = False
                self.placing_animated_stone_info = None
                placing_anim_active = False # Animation ended
                print("DEBUG: Placing animation finished.")
            else:
                self.needs_redraw = True # Keep redrawing during animation
        # --- End Placing Animation Update --- #

        # --- Update Blinking Animation State --- #
        is_animating = False
        if self.animation_blink_count > 0:
            is_animating = True
            now = pygame.time.get_ticks()
            elapsed = now - self.animation_start_time
            # Calculate current blink state index (0, 1, 2, 3 for 2 blinks)
            blink_state_index = elapsed // BLINK_INTERVAL

            if blink_state_index >= self.animation_blink_count:
                # Animation finished
                self.animation_blink_count = 0
                self.animating_stones = []
                self.show_blink = False
                print("DEBUG: Animation finished.") # Debug
            else:
                # Determine if blink should be shown (even indices: ON, odd indices: OFF)
                self.show_blink = (blink_state_index % 2 == 0)
                self.needs_redraw = True # Need to redraw during animation
        # --- End Blinking Animation Update --- #

        # Update Text Popups
        # Iterate backwards to allow removal during iteration
        for i in range(len(self.text_popups) - 1, -1, -1):
            popup = self.text_popups[i]
            if not popup.update(): # update returns False if duration passed
                self.text_popups.pop(i)

        # Don't update AI or switch turns if game is over, history mode, OR ANIMATING
        # (includes both blinking animation and placing animation)
        if self.game_over or self.is_history_mode or is_animating or placing_anim_active:
            # Ensure "Thinking..." message disappears if we enter history/game over/animation
            if self.ai_thinking:
                self.telop.hide()
            self.ai_thinking = False
            return

        # Handle AI turn (only if not game over, not history, not animating, not telop active)
        if not self.ai_thinking and not self._is_human_turn() and not telop_is_active:
            ai = self.ai_instances[self.current_player]
            if ai:
                player_name = 'Black' if self.current_player == BOARD_BLACK else 'White'
                print(f"AI ({player_name}) is thinking...")
                self.ai_thinking = True
                self.telop.show("思考中...", None) # Show thinking message indefinitely
                # --- Force draw thinking telop before AI calculation --- #
                # print("DEBUG: AI turn, showing 'Thinking...', forcing immediate redraw...") # Comment out
                self.draw() # Draw screen with telop
                pygame.display.flip() # Update display
                # --- End Force draw --- #

                move_count = len(self.move_history)
                move = ai.find_move(self.board, move_count) # <<< AI Calculation starts HERE
                self.ai_thinking = False
                self.telop.hide() # Hide thinking message
                if move:
                    print(f"AI chose: {move}")
                    self._make_move(move[0], move[1])
                    # Clear eval cache after AI moves
                    if self.research_mode_enabled:
                         self.evaluation_cache.clear()
                         self._evaluate_empty_cells()
                else:
                    print("AI could not find a valid move.")
                    if not self.board.get_empty_cells():
                        self.game_over = True
                        self.winner = None
                        print("Game Over! It's a draw because AI cannot move.")
                        self.telop.hide() # Ensure telop is hidden on draw too

    def _get_coords_on_line(self, start_pos, end_pos, direction):
        """Helper function to get all (r, c) coordinates on a threat line."""
        coords = []
        start_r, start_c = start_pos
        end_r, end_c = end_pos

        if direction == 'h':
            for c in range(min(start_c, end_c), max(start_c, end_c) + 1):
                coords.append((start_r, c))
        elif direction == 'v':
            for r in range(min(start_r, end_r), max(start_r, end_r) + 1):
                coords.append((r, start_c))
        elif direction == 'd1': # Down-Right (or Up-Left)
            r, c = min(start_r, end_r), min(start_c, end_c)
            while r <= max(start_r, end_r) and c <= max(start_c, end_c):
                coords.append((r, c))
                r += 1
                c += 1
        elif direction == 'd2': # Up-Right (or Down-Left)
            r, c = max(start_r, end_r), min(start_c, end_c) # Start from top-left based on row
            while r >= min(start_r, end_r) and c <= max(start_c, end_c):
                 coords.append((r, c))
                 r -= 1
                 c += 1
        return coords

    def _draw_threat_and_win_lines(self):
        """Draws threat lines and the win line (uses self.cell_size)."""
        board_to_draw = self._get_current_board_for_display()
        current_win_line = self._get_current_win_line_for_display()

        # Calculate threats based on the board being displayed
        black_threats = board_to_draw.find_threats(BOARD_BLACK)
        white_threats = board_to_draw.find_threats(BOARD_WHITE)
        all_threats = black_threats + white_threats

        if not all_threats and not current_win_line:
            return

        # Use self.cell_size for coordinate calculations
        # --- Threat Drawing Logic --- #
        # 1. Map threats to coordinates
        threat_map = defaultdict(list)
        for threat_info in all_threats:
            threat_type, start_pos, end_pos, direction, _ = threat_info
            coords = self._get_coords_on_line(start_pos, end_pos, direction)
            for r, c in coords:
                 threat_map[(r, c)].append((threat_type, direction))
        # 2. Identify intersection points
        intersection_points = set()
        for pos, threats_at_pos in threat_map.items():
            if len(threats_at_pos) >= 2:
                directions = set(d for t, d in threats_at_pos)
                has_horizontal = any(d == 'h' for d in directions)
                has_vertical = any(d == 'v' for d in directions)
                has_diagonal1 = any(d == 'd1' for d in directions)
                has_diagonal2 = any(d == 'd2' for d in directions)
                direction_categories = sum([has_horizontal, has_vertical, has_diagonal1, has_diagonal2])
                if direction_categories >= 2:
                    intersection_points.add(pos)
        # 3. Draw threat lines
        for threat_info in all_threats:
            # Unpack threat info, including the stone coordinates (ignored for line drawing)
            threat_type, start_pos_tuple, end_pos_tuple, direction, _ = threat_info

            start_r, start_c = start_pos_tuple
            end_r, end_c = end_pos_tuple

            start_pos_screen = (self.start_x + start_c * self.cell_size, self.start_y + start_r * self.cell_size)
            end_pos_screen = (self.start_x + end_c * self.cell_size, self.start_y + end_r * self.cell_size)
            line_coords = self._get_coords_on_line(start_pos_tuple, end_pos_tuple, direction)
            intersects = any(coord in intersection_points for coord in line_coords)
            if intersects:
                threat_color = RED
            else:
                threat_color = BLUE # Default or based on threat type
                if threat_type == THREAT_OPEN_THREE: threat_color = (0, 150, 255)
                elif threat_type == THREAT_CLOSED_FOUR: threat_color = (255, 165, 0)
                elif threat_type == THREAT_OPEN_FOUR: threat_color = (255, 69, 0)
            pygame.draw.line(self.screen, threat_color, start_pos_screen, end_pos_screen, THREAT_LINE_WIDTH)

        # --- 勝利ラインの描画 (using self.cell_size) --- #
        if current_win_line:
            start_pos_tuple_win, end_pos_tuple_win, direction_win = current_win_line
            start_r_win, start_c_win = start_pos_tuple_win
            end_r_win, end_c_win = end_pos_tuple_win
            start_pos_screen_win = (self.start_x + start_c_win * self.cell_size, self.start_y + start_r_win * self.cell_size)
            end_pos_screen_win = (self.start_x + end_c_win * self.cell_size, self.start_y + end_r_win * self.cell_size)
            win_color = RED
            pygame.draw.line(self.screen, win_color, start_pos_screen_win, end_pos_screen_win, WIN_LINE_WIDTH)

    def _draw_status_and_turn(self):
        """Draws the top status text (turn/history) and player indicator stone."""
        status_text_str = ""
        if self.is_history_mode:
            status_text_str = f"History: Move {self.display_move_index} / {len(self.move_history)}"
            current_player_at_index = BOARD_BLACK if self.display_move_index % 2 == 0 else BOARD_WHITE
        elif self.ai_thinking:
             status_text_str = "AI Thinking..."
             # Assign current player for indicator color during AI thinking
             current_player_at_index = self.current_player
        else:
            turn_str = "Black" if self.current_player == BOARD_BLACK else "White"
            status_text_str = f"Turn: {turn_str}"
            current_player_at_index = self.current_player

        status_text = self.font.render(status_text_str, True, TEXT_COLOR)
        status_rect = status_text.get_rect(center=(SCREEN_WIDTH // 2, 30))
        # Background rectangle centered with the text
        bg_rect = status_rect.inflate(60, 10) # Increased horizontal padding
        bg_rect.center = status_rect.center # Ensure bg is centered on text
        pygame.draw.rect(self.screen, BOARD_COLOR, bg_rect, border_radius=5)
        pygame.draw.rect(self.screen, LINE_COLOR, bg_rect, 1, border_radius=5)
        self.screen.blit(status_text, status_rect)

        # Turn indicator circle (Positioned LEFT of the text background)
        # Define top_status_y in reset_game or here if static
        top_status_y = 20 # Match the value used for status_rect centering
        if not self.game_over or self.is_history_mode:
            indicator_radius = 10
            # Position indicator left of the status text background
            indicator_x = bg_rect.left - 20 # Position left of the background rect
            indicator_y = top_status_y # Align vertically with the status text center
            indicator_color = BLACK if current_player_at_index == BOARD_BLACK else WHITE
            pygame.draw.circle(self.screen, indicator_color, (indicator_x, indicator_y), indicator_radius)
            pygame.draw.circle(self.screen, TEXT_COLOR, (indicator_x, indicator_y), indicator_radius, 1)

        self.back_button.draw(self.screen) # Draw menu button (already positioned top-right)

    def _draw_game_over_overlay(self):
        """Draws the semi-transparent overlay and game over message/buttons."""
        overlay_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay_surface.fill(GAMEOVER_OVERLAY_COLOR)
        self.screen.blit(overlay_surface, (0, 0))

        # Determine message
        if self.winner is None:
            message = "Draw!"
        else:
            winner_str = "Black Wins!" if self.winner == BOARD_BLACK else "White Wins!"
            message = f"{winner_str}"

        # Render message
        message_render = self.game_over_font.render(message, True, WHITE)
        message_rect = message_render.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 50))
        self.screen.blit(message_render, message_rect)

        # Draw buttons
        self.rematch_button.draw(self.screen)
        self.menu_button_gameover.draw(self.screen)

    def _get_ai_for_evaluation(self):
         """Gets an AIHard instance configured for evaluation (can be cached)."""
         # Simple caching example, could be more robust
         if not hasattr(self, '_eval_ai') or self._eval_ai is None:
              # Use settings or default values for depth/time limit for evaluation
              # Using a lower depth for responsiveness might be good
              self._eval_ai = AIHard(self.current_player, depth=2, time_limit_sec=0.1)
         # Ensure AI player matches current player context if needed for eval
         # self._eval_ai.player = self.current_player # Might not be needed if eval is generic
         return self._eval_ai

    def _evaluate_empty_cells(self):
        """Calculates evaluation scores using AI's static board evaluation."""
        if self.evaluation_in_progress:
            return
        self.evaluation_in_progress = True
        print("Evaluating empty cells using static evaluation...") # Debug
        self.evaluation_cache.clear()
        board_to_eval = self._get_current_board_for_display()
        # Evaluate from the perspective of the player whose turn it is *at this display index*
        player_to_eval = BOARD_BLACK if self.display_move_index % 2 == 0 else BOARD_WHITE
        move_count_at_index = self.display_move_index

        eval_ai = self._get_ai_for_evaluation()
        eval_ai.player = player_to_eval # Set AI context for evaluation perspective

        empty_cells = board_to_eval.get_empty_cells()

        for r, c in empty_cells:
            # Basic validity check (empty cell) - forbidden check is complex, rely on AI eval
            if not board_to_eval.is_within_bounds(r,c) or not board_to_eval.is_empty(r,c):
                self.evaluation_cache[(r, c)] = None
                continue

            # Simulate move and call evaluate_board
            temp_board_copy = board_to_eval.copy()
            temp_board_copy.grid[r, c] = player_to_eval
            temp_board_copy.last_move = (r, c)

            # Check if the move is forbidden for Black *before* evaluating
            is_forbidden = False
            if player_to_eval == BOARD_BLACK:
                 # Use the board's method to check forbidden status after placing the stone
                 is_forbidden = temp_board_copy._is_forbidden(r, c, player_to_eval)
                 # Note: _is_forbidden temporarily places/removes stone, so our copy is fine
                 # We need to re-place it for the evaluation function if it wasn't forbidden
                 if not is_forbidden:
                      temp_board_copy.grid[r, c] = player_to_eval # Ensure stone is placed for eval
                 else:
                      self.evaluation_cache[(r, c)] = None # Mark forbidden as None/Invalid
                      # print(f"DEBUG: Skipping evaluation for forbidden move at ({r},{c})")
                      continue # Skip evaluation for forbidden moves

            try:
                # Call static evaluation for the board state *after* the move
                # The score is relative to the 'eval_ai.player' (which is player_to_eval)
                # Remove extra arguments player_to_eval and move_count_at_index + 1
                score = eval_ai._evaluate_board(temp_board_copy)
                self.evaluation_cache[(r, c)] = score
                # print(f"DEBUG: Evaluated ({r},{c}) score: {score}") # Debug
            except Exception as e:
                 print(f"Error evaluating ({r},{c}): {e}")
                 self.evaluation_cache[(r, c)] = "Err"

        print(f"Evaluation complete. Cached {len(self.evaluation_cache)} scores.")
        self.evaluation_in_progress = False
        self.needs_redraw = True

    def _add_text_popup(self, text, pos_on_board, color, duration=1000):
        """Creates and adds a TextPopup instance near the board position."""
        row, col = pos_on_board
        target_center_x = self.start_x + col * self.cell_size
        target_center_y = self.start_y + row * self.cell_size
        # Use a smaller font for these popups maybe?
        popup_font = self.font # Using the standard button font for now
        popup = TextPopup(text, (target_center_x, target_center_y), popup_font, duration, color)
        popup.show() # Activate it immediately
        self.text_popups.append(popup)
        print(f"DEBUG: Added text popup: '{text}' at {pos_on_board}") # Debug

    def draw(self):
        """Draws the entire game screen, adapting to board size."""
        if self.needs_redraw:
            self._draw_board()             # Uses self.start_x/y, self.cell_size
            self._draw_stones_and_markers()# Uses self.start_x/y, self.cell_size
            self._draw_threat_and_win_lines()# Uses self.start_x/y, self.cell_size
            self._draw_status_and_turn()   # Positioned top-center/left
            # Draw other UI elements (already positioned in reset_game relative to screen)
            self.prev_move_button.draw(self.screen)
            self.next_move_button.draw(self.screen)
            self.save_button.draw(self.screen)
            self.research_mode_checkbox.draw(self.screen)
            # self.joseki_popup.draw(self.screen) # Removed JosekiPopup draw call

            # Draw Text Popups
            for popup in self.text_popups:
                 popup.draw(self.screen)

            # Game Over overlay (only if game is actually over and not in history mode)
            if self.game_over and not self.is_history_mode:
                self._draw_game_over_overlay()
                # Game over buttons are drawn within the overlay function now or kept separate?
                # Keep separate for consistency:
                self.rematch_button.draw(self.screen)
                self.menu_button_gameover.draw(self.screen)

            self.needs_redraw = False

        # Draw Telop last (outside the needs_redraw block)
        # Telop draw itself checks if active
        self.telop.draw(self.screen)

        # No need to flip here, handled in main loop after all updates/draws 