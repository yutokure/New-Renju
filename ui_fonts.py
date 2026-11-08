"""Permissively licensed application fonts; no bundled Pygame FreeSans use."""
import pygame
from resources import asset_path


def ui_font(size):
    # Pygame's former Font(None) rescales its FreeSans face internally. Keep
    # comparable pixel metrics for the fixed 800x600 UI using our own bold face.
    return pygame.font.Font(asset_path('fonts/UiSans.ttf'), max(8, round(size * 0.6875)))
