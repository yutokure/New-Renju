# Colors (RGB)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (128, 128, 128)
BOARD_COLOR = (220, 179, 92)    # Light brown wood color
LINE_COLOR = (50, 50, 50)      # Dark gray lines
TEXT_COLOR = (10, 10, 10)
POPUP_BG_COLOR = (240, 240, 240)
POPUP_TEXT_COLOR = BLACK
BUTTON_COLOR = (200, 200, 200)
BUTTON_HOVER_COLOR = (170, 170, 170)
BUTTON_TEXT_COLOR = WHITE
RED = (200, 0, 0)
BLUE = (0, 0, 200)
INVALID_MOVE_COLOR = (100, 100, 100, 180) # Semi-transparent gray for invalid spots
GAMEOVER_OVERLAY_COLOR = (50, 50, 50, 180) # Semi-transparent dark overlay

# Screen dimensions
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

# Board dimensions (Default values, can be changed in settings)
DEFAULT_BOARD_SIZE = 15  # 15x15 grid
DEFAULT_WIN_LENGTH = 5  # 5 stones in a row to win
CELL_SIZE = 36  # Pixel size of each cell
MARGIN = 50  # Margin around the board

# Game states
STATE_MENU = 0
STATE_SETTINGS = 1
STATE_GAME = 2
STATE_QUIT = 3
STATE_LOAD_SELECT = 4 # New state for file selection

# Player types
PLAYER_HUMAN = 0
PLAYER_AI = 1

# AI Difficulty
AI_EASY = "easy"
AI_NORMAL = "normal"
AI_HARD = "hard"

# Animation Constants
ANIMATION_DURATION = 600  # Total animation duration in ms (e.g., 2 blinks * 300ms/blink)
BLINK_INTERVAL = 150    # Time for one state (on/off) in ms (duration = interval * 2 * count)
BLINK_COUNT = 2         # Number of blinks
BLINK_RADIUS_FACTOR = 0.6 # Factor of stone radius for blink circle
BLINK_COLOR_APPEAR = (0, 100, 255, 200) # Blueish, semi-transparent
BLINK_COLOR_DISAPPEAR = (255, 50, 50, 200)  # Reddish, semi-transparent

# Text Popup Colors
POPUP_COLOR_DEFENSE = (100, 150, 255) # Light Blue
POPUP_COLOR_PURSUIT = (255, 60, 60)   # Red
POPUP_COLOR_ATTACK = WHITE

# Stone Placing Animation Constants
PLACING_ANIMATION_DURATION = 300 # ms
PLACING_ANIMATION_START_SCALE = 2.0 