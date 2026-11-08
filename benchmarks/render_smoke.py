"""Small serial SDL draw sample, not a sustained performance benchmark."""
import argparse
import json
import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
import time
from pathlib import Path
import pygame
from constants import SCREEN_WIDTH, SCREEN_HEIGHT
from game import Game
from settings import Settings


def sample(size, frames=200):
    settings = Settings()
    settings.set_game_mode((0,0))
    settings.board_size = size
    game = Game(pygame.display.get_surface(), settings)
    try:
        middle = size // 2
        game.reset_game([[middle,middle],[middle-1,middle],[middle,middle+1]])
        game.telop.active = False
        game.research_mode_enabled = True
        game.evaluation_cache = {(r,c): (r*size+c)*91 for r,c in game.board.get_empty_cells()}
        game._add_text_popup('Display sample', (middle,middle), (255,255,255))
        for _ in range(5):
            game.needs_redraw = True
            game.draw()
        start = time.perf_counter()
        for _ in range(frames):
            game.needs_redraw = True
            game.draw()
        elapsed = time.perf_counter()-start
        return {'board_size':size,'frames':frames,'seconds':elapsed,
                'ms_per_forced_frame':1000*elapsed/frames,
                'driver':pygame.display.get_driver()}
    finally:
        game.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    pygame.init()
    pygame.display.set_mode((SCREEN_WIDTH,SCREEN_HEIGHT))
    try:
        report = {'kind':'lightweight serial forced draw smoke', 'samples':[sample(15),sample(19)]}
        Path(args.output).write_text(json.dumps(report,indent=2), encoding='utf-8')
        print(json.dumps(report,indent=2))
    finally:
        pygame.quit()


if __name__ == '__main__':
    main()
