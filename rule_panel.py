"""In-app rule guide shared by menu/settings and the game."""
import pygame
from constants import SCREEN_WIDTH, SCREEN_HEIGHT, TEXT_COLOR
from ui import Button
from ui_text import rules_help


def close_button(font):
    return Button('Close Rules', (SCREEN_WIDTH//2, SCREEN_HEIGHT-36), font, width=180)


def draw_rules(screen, settings, font):
    screen.fill((248,248,242))
    title = font.render('Rules & controls', True, TEXT_COLOR)
    screen.blit(title, (25,15))
    for index, line in enumerate(rules_help(settings)):
        rendered = font.render(line, True, TEXT_COLOR)
        screen.blit(rendered, (25, 50+index*28))
    close_button(font).draw(screen)
