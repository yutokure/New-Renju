from constants import (
    DEFAULT_BOARD_SIZE,
    DEFAULT_WIN_LENGTH,
    PLAYER_HUMAN,
    PLAYER_AI,
    AI_EASY,
    AI_NORMAL,
    AI_HARD,
)


class Settings:
    """Stores and manages game settings."""

    def __init__(self):
        # Default settings
        self.board_size = DEFAULT_BOARD_SIZE
        self.win_length = DEFAULT_WIN_LENGTH  # How many stones in a row to win
        self.game_mode = (PLAYER_HUMAN, PLAYER_AI)  # Default: Human vs AI
        self.ai_starts = False  # Default: Human starts
        self.ai_difficulty = AI_NORMAL  # Default: Normal AI

        # --- Possible values ---
        self.board_size_options = [9, 11, 13, 15, 17, 19]  # Example options
        self.win_length_options = list(range(3, 8))  # 3 to 7
        self.game_mode_options = [
            (PLAYER_HUMAN, PLAYER_HUMAN),  # Human vs Human
            (PLAYER_HUMAN, PLAYER_AI),     # Human vs AI
            (PLAYER_AI, PLAYER_HUMAN),     # AI vs Human
            (PLAYER_AI, PLAYER_AI),        # AI vs AI (Maybe less common)
        ]
        self.ai_difficulty_options = [AI_EASY, AI_NORMAL, AI_HARD]

    def set_board_size(self, size):
        """Sets the board size if valid."""
        if size in self.board_size_options:
            self.board_size = size
        else:
            print(
                f"Warning: Invalid board size {size}. "
                f"Using default {DEFAULT_BOARD_SIZE}."
            )
            self.board_size = DEFAULT_BOARD_SIZE

    def set_win_length(self, length):
        """Sets the win length if valid."""
        if length in self.win_length_options:
            self.win_length = length
        else:
            print(
                f"Warning: Invalid win length {length}. "
                f"Using default {DEFAULT_WIN_LENGTH}."
            )
            self.win_length = DEFAULT_WIN_LENGTH

    def set_game_mode(self, mode_tuple):
        """Sets the game mode and determines if AI starts."""
        # Basic check, could be more robust
        if (
            isinstance(mode_tuple, tuple)
            and len(mode_tuple) == 2
            and mode_tuple[0] in [PLAYER_HUMAN, PLAYER_AI]
            and mode_tuple[1] in [PLAYER_HUMAN, PLAYER_AI]
        ):
            # Determine if AI starts based on the first player
            self.ai_starts = mode_tuple[0] == PLAYER_AI
            self.game_mode = mode_tuple
        else:
            print(f"Warning: Invalid game mode {mode_tuple}. Using default.")
            self.game_mode = (PLAYER_HUMAN, PLAYER_AI)
            self.ai_starts = False

    def set_ai_difficulty(self, difficulty):
        """Sets the AI difficulty if valid."""
        if difficulty in self.ai_difficulty_options:
            self.ai_difficulty = difficulty
        else:
            print(
                f"Warning: Invalid AI difficulty {difficulty}. "
                f"Using default {AI_NORMAL}."
            )
            self.ai_difficulty = AI_NORMAL

    def get_player_types(self):
        """Returns the tuple representing player types (e.g., ('human', 'ai'))."""
        return self.game_mode

    def get_setting_summary(self):
        """Returns a list of strings summarizing the current settings."""
        mode_map = {
            (PLAYER_HUMAN, PLAYER_HUMAN): "人間 vs 人間",
            (PLAYER_HUMAN, PLAYER_AI):    "人間 vs AI",
            (PLAYER_AI, PLAYER_HUMAN):    "AI vs 人間",
            (PLAYER_AI, PLAYER_AI):        "AI vs AI",
        }
        difficulty_map = {
            AI_EASY: "簡単",
            AI_NORMAL: "普通",
            AI_HARD: "難しい",
        }
        summary = [
            f"盤面サイズ: {self.board_size}x{self.board_size}",
            f"勝利条件: {self.win_length}目並び",
            f"モード: {mode_map.get(self.game_mode, '不明')}",
        ]
        # Only show AI difficulty if AI is involved
        if PLAYER_AI in self.game_mode:
            summary.append(
                f"AIの強さ: {difficulty_map.get(self.ai_difficulty, '不明')}"
            )
            summary.append(f"AIが先手: {'はい' if self.ai_starts else 'いいえ'}")
        return summary


# Example usage (for testing):
if __name__ == "__main__":
    settings = Settings()
    print("Default Settings:")
    for line in settings.get_setting_summary():
        print(line)

    settings.set_board_size(19)
    settings.set_win_length(6)
    settings.set_game_mode((PLAYER_AI, PLAYER_HUMAN))
    settings.set_ai_difficulty(AI_HARD)

    print("\nModified Settings:")
    for line in settings.get_setting_summary():
        print(line) 