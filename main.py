import pygame
import sys
import json # Import json module
import os # Import os module for listing files
import glob # Import glob for pattern matching
from constants import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    WHITE,
    TEXT_COLOR,
    GRAY,
    STATE_MENU,
    STATE_SETTINGS,
    STATE_GAME,
    STATE_QUIT,
    PLAYER_AI,
    PLAYER_HUMAN,
    STATE_LOAD_SELECT, # Import new state
)
from ui import Button
from settings import Settings
from game import Game  # Import the Game class

# --- Helper function for loading game data ---
def _load_game_data(filename="gomoku_save.json"):
    """Loads game settings and move history from a JSON file."""
    try:
        with open(filename, 'r') as f:
            data = json.load(f)

        # Validate loaded data
        required_keys = ["settings", "move_history"]
        if not all(key in data for key in required_keys):
            print(f"Error: Save file '{filename}' is missing required keys.")
            return None, None

        required_settings = [
            "board_size", "win_length", "game_mode",
            "ai_difficulty", "ai_starts"
        ]
        if not all(key in data["settings"] for key in required_settings):
            print(f"Error: Save file '{filename}' settings section is missing keys.")
            return None, None

        # Convert game_mode back to tuple if needed (JSON saves lists)
        if isinstance(data["settings"].get("game_mode"), list):
             data["settings"]["game_mode"] = tuple(data["settings"]["game_mode"])

        # Validate move history format (list of lists/tuples with 2 ints)
        if not isinstance(data["move_history"], list):
             print(f"Error: Invalid move_history format in '{filename}'.")
             return None, None
        for move in data["move_history"]:
             if not (isinstance(move, (list, tuple)) and len(move) == 2 and
                     isinstance(move[0], int) and isinstance(move[1], int)):
                  print(f"Error: Invalid move format {move} in '{filename}'.")
                  return None, None

        print(f"Game data loaded successfully from {filename}")
        return data["settings"], data["move_history"]

    except FileNotFoundError:
        print(f"Error: Save file '{filename}' not found.")
        return None, None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from '{filename}'. File might be corrupt.")
        return None, None
    except Exception as e:
        print(f"An unexpected error occurred during loading: {e}")
        return None, None

# --- Helper function to get save files ---
def _get_save_files():
    """Returns a sorted list of save file names matching the pattern."""
    try:
        files = glob.glob("gomoku_save_*.json")
        # Sort by modification time, newest first
        files.sort(key=os.path.getmtime, reverse=True)
        return files
    except Exception as e:
        print(f"Error getting save files: {e}")
        return []

def main():
    pygame.init()

    settings = Settings()  # Create a Settings instance

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Gomoku")

    clock = pygame.time.Clock()

    game_state = STATE_MENU
    current_game = None  # Placeholder for the active Game instance

    # --- Fonts ---
    title_font = pygame.font.Font(None, 70)
    menu_font = pygame.font.Font(None, 50)
    settings_label_font = pygame.font.Font(None, 36)
    settings_value_font = pygame.font.Font(None, 36)
    settings_button_font = pygame.font.Font(None, 40)  # Font for < > buttons
    list_font = pygame.font.Font(None, 36) # Font for file list

    # --- Menu UI Elements ---
    title_text = title_font.render("Gomoku", True, TEXT_COLOR)
    title_rect = title_text.get_rect(
        center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 4)
    )
    start_button = Button(
        "Start New Game", (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 35), menu_font
    )
    load_button = Button(
        "Load Game", (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 35), menu_font
    )
    settings_button = Button(
        "Settings", (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 105), menu_font
    )
    quit_button = Button(
        "Quit", (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 175), menu_font
    )
    menu_buttons = [start_button, load_button, settings_button, quit_button]

    # --- Settings UI Elements Layout ---
    settings_title_text = menu_font.render("Settings", True, TEXT_COLOR)
    settings_title_rect = settings_title_text.get_rect(
        center=(SCREEN_WIDTH // 2, 80)
    )
    y_offset = 150
    label_x = 100
    value_x = 350
    value_width = 200
    button_offset = 35
    line_height = 60

    def create_setting_controls(label_text, initial_y):
        """Creates label, value rect, and buttons for a setting row."""
        label = settings_label_font.render(label_text, True, TEXT_COLOR)
        label_rect = label.get_rect(midleft=(label_x, initial_y + 20))
        value_rect = pygame.Rect(value_x, initial_y, value_width, 40)
        next_pos = (value_rect.right + button_offset, value_rect.centery)
        prev_pos = (value_rect.left - button_offset, value_rect.centery)
        next_button = Button(
            ">", next_pos, settings_button_font, text_color=GRAY
        )
        prev_button = Button(
            "<", prev_pos, settings_button_font, text_color=GRAY
        )
        return label, label_rect, value_rect, prev_button, next_button

    # Create all setting controls
    (
        board_size_label,
        board_size_label_rect,
        board_size_value_rect,
        board_size_prev_button,
        board_size_next_button,
    ) = create_setting_controls("Board Size:", y_offset)
    y_offset += line_height
    (
        win_length_label,
        win_length_label_rect,
        win_length_value_rect,
        win_length_prev_button,
        win_length_next_button,
    ) = create_setting_controls("Win Length:", y_offset)
    y_offset += line_height
    (
        game_mode_label,
        game_mode_label_rect,
        game_mode_value_rect,
        game_mode_prev_button,
        game_mode_next_button,
    ) = create_setting_controls("Game Mode:", y_offset)
    y_offset += line_height
    (
        ai_difficulty_label,
        ai_difficulty_label_rect,
        ai_difficulty_value_rect,
        ai_difficulty_prev_button,
        ai_difficulty_next_button,
    ) = create_setting_controls("AI Difficulty:", y_offset)
    back_button = Button("Back", (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 80), menu_font)

    # --- Load Game Select UI Elements ---
    load_title_text = menu_font.render("Load Game", True, TEXT_COLOR)
    load_title_rect = load_title_text.get_rect(center=(SCREEN_WIDTH // 2, 80))
    files_per_page = 8
    current_page = 0
    selected_file_index = -1 # Index within the current page
    save_files = [] # Updated when entering the state
    load_list_buttons = [] # Buttons for each file on the current page
    load_list_y_start = 150
    load_list_line_height = 40
    # Center the list horizontally
    load_list_width = SCREEN_WIDTH * 0.6 # Set desired width (e.g., 60% of screen)
    load_list_x = (SCREEN_WIDTH - load_list_width) // 2
    # Page navigation buttons (position adjusted)
    page_nav_y = SCREEN_HEIGHT - 80
    load_prev_page_button = Button("<<", (load_list_x, page_nav_y), menu_font)
    load_next_page_button = Button(">>", (SCREEN_WIDTH - load_list_x, page_nav_y), menu_font) # Adjusted x based on load_list_x
    load_back_button = Button("Back", (SCREEN_WIDTH // 2, page_nav_y), menu_font) # Align with page buttons

    def update_load_list_buttons():
        nonlocal load_list_buttons, save_files, current_page, files_per_page
        load_list_buttons.clear()
        start_index = current_page * files_per_page
        end_index = min(start_index + files_per_page, len(save_files))
        for i in range(start_index, end_index):
            filename = os.path.basename(save_files[i]) # Show only filename
            button_y = load_list_y_start + (i - start_index) * load_list_line_height
            # Create button using the calculated x and width
            button = Button(filename, (load_list_x + load_list_width / 2, button_y), list_font, width=load_list_width - 20, height=35)
            # Add the full path as a custom attribute after creation
            button.data = save_files[i]
            load_list_buttons.append(button)

    # --- Main Loop ---
    running = True
    while running:
        ai_active = PLAYER_AI in settings.game_mode
        settings_value_renders = {} # Initialize here, ensuring it always exists

        # --- Render Setting Values (only when in settings state) ---
        if game_state == STATE_SETTINGS:
            board_size_value_text = settings_value_font.render(
                f"{settings.board_size}x{settings.board_size}", True, GRAY
            )
            board_size_value_text_rect = board_size_value_text.get_rect(
                center=board_size_value_rect.center
            )
            win_length_value_text = settings_value_font.render(
                f"{settings.win_length}", True, GRAY
            )
            win_length_value_text_rect = win_length_value_text.get_rect(
                center=win_length_value_rect.center
            )
            mode_map = {
                (PLAYER_HUMAN, PLAYER_HUMAN): "Human vs Human",
                (PLAYER_HUMAN, PLAYER_AI): "Human vs AI",
                (PLAYER_AI, PLAYER_HUMAN): "AI vs Human",
                (PLAYER_AI, PLAYER_AI): "AI vs AI",
            }
            game_mode_value_str = mode_map.get(settings.game_mode, "Unknown")
            game_mode_value_text = settings_value_font.render(
                game_mode_value_str, True, GRAY
            )
            game_mode_value_text_rect = game_mode_value_text.get_rect(
                center=game_mode_value_rect.center
            )
            ai_difficulty_str = (
                settings.ai_difficulty.capitalize() if ai_active else "N/A"
            )
            ai_difficulty_value_text = settings_value_font.render(
                ai_difficulty_str, True, GRAY
            )
            ai_difficulty_value_text_rect = ai_difficulty_value_text.get_rect(
                center=ai_difficulty_value_rect.center
            )
            # Store renders needed for drawing this frame
            settings_value_renders = {
                "board_size": (board_size_value_text, board_size_value_text_rect),
                "win_length": (win_length_value_text, win_length_value_text_rect),
                "game_mode": (game_mode_value_text, game_mode_value_text_rect),
                "ai_difficulty": (
                    ai_difficulty_value_text, ai_difficulty_value_text_rect
                ),
            }

        # --- Event Handling ---
        mouse_pos = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                game_state = STATE_QUIT

            # Handle events based on the current state
            if game_state == STATE_MENU:
                for button in menu_buttons:
                    result = button.handle_event(event)
                    if result == "Start New Game":
                        current_game = Game(screen, settings)
                        game_state = STATE_GAME
                        print("Starting New Game:", settings.get_setting_summary())
                    elif result == "Load Game":
                        # Transition to Load Select state
                        save_files = _get_save_files()
                        current_page = 0
                        selected_file_index = -1
                        update_load_list_buttons()
                        game_state = STATE_LOAD_SELECT
                        print(f"Entering Load Select. Found {len(save_files)} save files.")
                    elif result == "Settings":
                        game_state = STATE_SETTINGS
                    elif result == "Quit":
                        running = False
                        game_state = STATE_QUIT

            elif game_state == STATE_SETTINGS:
                if back_button.handle_event(event) == "Back":
                    game_state = STATE_MENU
                    continue

                def cycle_setting(
                    current_value, options_list, set_function, direction
                ):
                    try:
                        current_index = options_list.index(current_value)
                        new_index = (current_index + direction) % len(
                            options_list
                        )
                        set_function(options_list[new_index])
                    except ValueError:
                        print(
                            f"Error: Current value {current_value} not in options."
                        )
                        if options_list:
                            set_function(options_list[0])

                # Handle setting cycle buttons
                if board_size_prev_button.handle_event(event) == "<":
                    cycle_setting(
                        settings.board_size, settings.board_size_options,
                        settings.set_board_size, -1
                    )
                elif board_size_next_button.handle_event(event) == ">":
                    cycle_setting(
                        settings.board_size, settings.board_size_options,
                        settings.set_board_size, 1
                    )
                elif win_length_prev_button.handle_event(event) == "<":
                    cycle_setting(
                        settings.win_length, settings.win_length_options,
                        settings.set_win_length, -1
                    )
                elif win_length_next_button.handle_event(event) == ">":
                    cycle_setting(
                        settings.win_length, settings.win_length_options,
                        settings.set_win_length, 1
                    )
                elif game_mode_prev_button.handle_event(event) == "<":
                    cycle_setting(
                        settings.game_mode, settings.game_mode_options,
                        settings.set_game_mode, -1
                    )
                elif game_mode_next_button.handle_event(event) == ">":
                    cycle_setting(
                        settings.game_mode, settings.game_mode_options,
                        settings.set_game_mode, 1
                    )
                elif ai_active:
                    if ai_difficulty_prev_button.handle_event(event) == "<":
                        cycle_setting(
                            settings.ai_difficulty, settings.ai_difficulty_options,
                            settings.set_ai_difficulty, -1
                        )
                    elif ai_difficulty_next_button.handle_event(event) == ">":
                        cycle_setting(
                            settings.ai_difficulty, settings.ai_difficulty_options,
                            settings.set_ai_difficulty, 1
                        )

            elif game_state == STATE_LOAD_SELECT:
                # Handle Back button
                if load_back_button.handle_event(event) == "Back":
                    game_state = STATE_MENU
                    continue
                # Handle Page buttons
                num_pages = (len(save_files) + files_per_page - 1) // files_per_page
                if load_prev_page_button.handle_event(event) == "<<":
                    if current_page > 0:
                        current_page -= 1
                        update_load_list_buttons()
                elif load_next_page_button.handle_event(event) == ">>":
                    if current_page < num_pages - 1:
                        current_page += 1
                        update_load_list_buttons()

                # Handle File selection buttons
                for i, button in enumerate(load_list_buttons):
                     clicked_file_path = button.handle_event(event) # Returns button.data (full path)
                     if clicked_file_path:
                         print(f"Load selected: {clicked_file_path}")
                         loaded_settings_data, loaded_moves = _load_game_data(clicked_file_path)
                         if loaded_settings_data and loaded_moves is not None:
                             # Update settings
                             try:
                                 settings.board_size = int(loaded_settings_data['board_size'])
                                 settings.win_length = int(loaded_settings_data['win_length'])
                                 loaded_game_mode = loaded_settings_data['game_mode']
                                 if isinstance(loaded_game_mode, list):
                                      settings.game_mode = tuple(loaded_game_mode)
                                 elif isinstance(loaded_game_mode, tuple):
                                      settings.game_mode = loaded_game_mode
                                 else:
                                      raise ValueError("Invalid game_mode type")
                                 settings.ai_difficulty = str(loaded_settings_data['ai_difficulty'])
                                 settings.ai_starts = bool(loaded_settings_data['ai_starts'])
                             except Exception as e:
                                  print(f"Error applying loaded settings: {e}")
                                  continue # Stay in load select screen

                             # Validate settings
                             if settings.board_size not in settings.board_size_options:
                                 print(f"Warning: Invalid board size {settings.board_size}")
                                 continue

                             # Start game with loaded data
                             current_game = Game(screen, settings)
                             current_game.reset_game(move_history_to_load=loaded_moves)
                             game_state = STATE_GAME
                             print("Loaded Game:", settings.get_setting_summary())
                         else:
                             print("Failed to load game data from selected file.")
                         break # Exit file button loop once one is clicked

            elif game_state == STATE_GAME:
                if current_game:
                    next_state = current_game.handle_event(event)
                    if next_state == STATE_MENU:
                        current_game = None # Clear game instance when going back to menu
                        game_state = STATE_MENU

        # --- Updates --- (e.g., AI moves)
        if game_state == STATE_GAME and current_game:
            current_game.update()

        # --- Drawing by State ---
        # screen.fill(WHITE)  # Remove default background fill here

        if game_state == STATE_MENU:
            screen.fill(WHITE) # Fill white only for menu
            screen.blit(title_text, title_rect)
            for button in menu_buttons:
                button.draw(screen)

        elif game_state == STATE_SETTINGS:
            screen.fill(WHITE) # Fill white only for settings
            screen.blit(settings_title_text, settings_title_rect)
            # Draw settings controls and values
            screen.blit(board_size_label, board_size_label_rect)
            # Check if renders exist before blitting
            if "board_size" in settings_value_renders:
                 screen.blit(settings_value_renders["board_size"][0], settings_value_renders["board_size"][1])
            board_size_prev_button.draw(screen)
            board_size_next_button.draw(screen)
            screen.blit(win_length_label, win_length_label_rect)
            if "win_length" in settings_value_renders:
                 screen.blit(settings_value_renders["win_length"][0], settings_value_renders["win_length"][1])
            win_length_prev_button.draw(screen)
            win_length_next_button.draw(screen)
            screen.blit(game_mode_label, game_mode_label_rect)
            if "game_mode" in settings_value_renders:
                 screen.blit(settings_value_renders["game_mode"][0], settings_value_renders["game_mode"][1])
            game_mode_prev_button.draw(screen)
            game_mode_next_button.draw(screen)
            if ai_active:
                screen.blit(ai_difficulty_label, ai_difficulty_label_rect)
                if "ai_difficulty" in settings_value_renders:
                     screen.blit(settings_value_renders["ai_difficulty"][0], settings_value_renders["ai_difficulty"][1])
                ai_difficulty_prev_button.draw(screen)
                ai_difficulty_next_button.draw(screen)
            back_button.draw(screen)

        elif game_state == STATE_LOAD_SELECT:
            screen.fill(WHITE) # ★★★ Add background fill for Load Select ★★★
            screen.blit(load_title_text, load_title_rect)
            # Draw file list buttons
            for button in load_list_buttons:
                button.draw(screen)
            # Draw page info and navigation buttons
            num_pages = (len(save_files) + files_per_page - 1) // files_per_page
            page_text = list_font.render(f"Page {current_page + 1} / {max(1, num_pages)}", True, TEXT_COLOR)
            # Position page text above the buttons
            page_rect = page_text.get_rect(center=(SCREEN_WIDTH // 2, page_nav_y - 40))
            screen.blit(page_text, page_rect)
            # Draw navigation buttons conditionally
            if current_page > 0:
                 load_prev_page_button.draw(screen)
            if current_page < num_pages - 1:
                 load_next_page_button.draw(screen)
            load_back_button.draw(screen)

        elif game_state == STATE_GAME:
            if current_game:
                current_game.draw()  # Let the Game instance handle drawing (including its background)
            else:
                # Fallback if game state is GAME but no instance exists
                screen.fill(WHITE) # Fill white for error screen
                font = pygame.font.Font(None, 30)
                text = font.render("Error: Game not initialized.", True, TEXT_COLOR)
                rect = text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
                screen.blit(text, rect)

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main() 