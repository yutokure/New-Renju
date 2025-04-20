import json
import pygame
from constants import (
    POPUP_BG_COLOR, POPUP_TEXT_COLOR, SCREEN_WIDTH, SCREEN_HEIGHT
)

JOSEKI_FILE = 'joseki.json'

def load_joseki(filename=JOSEKI_FILE):
    """Loads joseki patterns from a JSON file."""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            joseki_data = json.load(f)
        # Validate and process each joseki entry
        validated_data = []
        for joseki in joseki_data:
            if 'name' not in joseki or 'moves' not in joseki:
                print(f"Warning: Skipping invalid joseki entry (missing name or moves): {joseki}")
                continue
            joseki['moves'] = [tuple(move) for move in joseki['moves']]
            # Get 'is_shukei' value, default to False if missing for backward compatibility
            # (Although we updated the file, this makes the code more robust)
            joseki['is_shukei'] = joseki.get('is_shukei', False)
            validated_data.append(joseki)

        print(f"Loaded {len(validated_data)} joseki patterns from {filename}")
        return validated_data
    except FileNotFoundError:
        print(f"Error: Joseki file '{filename}' not found.")
        return []
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from '{filename}'.")
        return []

def transform_moves(moves, transformation_index, board_size):
    """Applies one of 8 symmetries to a list of moves.

    Args:
        moves (list): List of (row, col) tuples.
        transformation_index (int): 0-7 representing the transformation.
            0: Identity, 1-3: Rotations 90, 180, 270 CW
            4: Flip Horizontal, 5-7: Flip Horiz + Rotations 90, 180, 270 CW
        board_size (int): The size of the board (e.g., 15).

    Returns:
        list: List of transformed (row, col) tuples.
    """
    transformed = []
    size_m1 = board_size - 1 # Pre-calculate size - 1
    for r, c in moves:
        nr, nc = r, c # Default to identity
        if transformation_index == 1:   # Rotate 90 CW
            nr, nc = c, size_m1 - r
        elif transformation_index == 2: # Rotate 180 CW
            nr, nc = size_m1 - r, size_m1 - c
        elif transformation_index == 3: # Rotate 270 CW
            nr, nc = size_m1 - c, r
        elif transformation_index == 4: # Flip Horizontal
            nr, nc = r, size_m1 - c
        elif transformation_index == 5: # Flip Horiz + Rot 90
            # Apply flip: (r, size_m1 - c), then rotate 90:
            nr, nc = size_m1 - c, size_m1 - r
        elif transformation_index == 6: # Flip Horiz + Rot 180
            # Apply flip: (r, size_m1 - c), then rotate 180:
            nr, nc = size_m1 - r, c
        elif transformation_index == 7: # Flip Horiz + Rot 270
            # Apply flip: (r, size_m1 - c), then rotate 270:
            nr, nc = c, r

        transformed.append((nr, nc))
    return transformed

def check_joseki(move_history, joseki_list, board_size):
    """Checks if the move history matches any joseki based on its type (Shukei or other)."""
    current_len = len(move_history)
    if current_len == 0:
        return None

    current_history_tuples = move_history # Assume history is already tuples

    for joseki in joseki_list:
        joseki_moves = joseki['moves']
        is_shukei = joseki.get('is_shukei', False) # Default to False if key missing

        # Only compare with joseki of the same length
        if current_len == len(joseki_moves):
            # Determine the range of transformations to check
            num_transformations = 8 if is_shukei else 4 # 8 for Shukei (rot+flip), 4 for others (rot only)

            for transform_idx in range(num_transformations):
                transformed_history = transform_moves(
                    current_history_tuples, transform_idx, board_size
                )
                if transformed_history == joseki_moves:
                    transform_type = "Shukei" if is_shukei else "Joseki"
                    print(
                        f"{transform_type} detected: {joseki['name']} "
                        f"(Transform index {transform_idx})"
                    )
                    return joseki['name'] # Return the name on match
    return None # No match found

# --- JosekiPopup class removed as Telop is used instead --- #
# class JosekiPopup:
#     """Displays a temporary popup message for detected joseki."""
#     def __init__(self):
#         self.font = pygame.font.Font(None, 48)  # Larger font for popup
#         self.message = None
#         self.display_start_time = 0
#         self.duration = 2000  # Display duration in milliseconds (2 seconds)
#         self.active = False
#         self.surface = None
#         self.rect = None
#
#     def show(self, message):
#         """Activates the popup with a message."""
#         self.message = message
#         self.text_surf = self.font.render(self.message, True, POPUP_TEXT_COLOR)
#         text_rect = self.text_surf.get_rect()
#         padding = 20
#         surf_width = text_rect.width + padding * 2
#         surf_height = text_rect.height + padding * 2
#         self.surface = pygame.Surface((surf_width, surf_height))
#         self.surface.fill(POPUP_BG_COLOR)
#         border_rect = self.surface.get_rect()
#         pygame.draw.rect(self.surface, POPUP_TEXT_COLOR, border_rect, 2)
#         text_blit_pos = (padding, padding)
#         self.surface.blit(self.text_surf, text_blit_pos)
#         self.rect = self.surface.get_rect(
#             center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
#         )
#         self.display_start_time = pygame.time.get_ticks()
#         self.active = True
#
#     def update(self):
#         if self.active:
#             current_time = pygame.time.get_ticks()
#             if current_time - self.display_start_time > self.duration:
#                 self.active = False
#                 self.message = None
#                 self.surface = None
#
#     def draw(self, screen):
#         if self.active and self.surface:
#             screen.blit(self.surface, self.rect)


# Example Usage (Updated for rotation/reflection check)
if __name__ == '__main__':
    BOARD_TEST_SIZE = 15
    # Simulate Kagetsu moves
    kagetsu_hist = [(7, 7), (6, 8), (7, 8), (8, 7), (6, 7)]
    # Simulate Kagetsu rotated 90 degrees CW on a 15x15 board
    # (7, 7) -> (7, 7)
    # (6, 8) -> (8, 8) # 14-6=8
    # (7, 8) -> (8, 7) # 14-7=7
    # (8, 7) -> (7, 6) # 14-8=6
    # (6, 7) -> (7, 8) # 14-6=8
    kagetsu_rot90_hist = [(7, 7), (8, 8), (8, 7), (7, 6), (7, 8)]
    # Simulate Kagetsu flipped horizontally on a 15x15 board
    # (7, 7) -> (7, 7)
    # (6, 8) -> (6, 6)
    # (7, 8) -> (7, 6)
    # (8, 7) -> (8, 7)
    # (6, 7) -> (6, 7)
    kagetsu_flip_hist = [(7, 7), (6, 6), (7, 6), (8, 7), (6, 7)]

    joseki_patterns = load_joseki()
    if joseki_patterns:
        print("\nTesting Joseki Checks (15x15 Board):")
        match1 = check_joseki(kagetsu_hist, joseki_patterns, BOARD_TEST_SIZE)
        print(f"Original Kagetsu match: {match1}")

        match2 = check_joseki(kagetsu_rot90_hist, joseki_patterns, BOARD_TEST_SIZE)
        print(f"Rotated Kagetsu match: {match2}") # Should match Kagetsu

        match3 = check_joseki(kagetsu_flip_hist, joseki_patterns, BOARD_TEST_SIZE)
        print(f"Flipped Kagetsu match: {match3}") # Should match Kagetsu 