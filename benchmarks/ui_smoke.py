"""Exercise the real SDL window (not dummy) while a detached Hard worker runs."""
import json
import os
from pathlib import Path
import time
import pygame
from constants import PLAYER_AI, PLAYER_HUMAN, STATE_MENU
from game import Game
from settings import Settings
from tests.positions import hard_cases


def main(difficulty='hard', duration=0.12):
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption('New-Renju AI responsiveness verification')
    settings = Settings()
    settings.set_game_mode((PLAYER_AI, PLAYER_HUMAN))
    settings.set_ai_difficulty(difficulty)
    game = Game(screen, settings)
    root = Path('benchmarks/results')
    root.mkdir(parents=True, exist_ok=True)
    report = {'driver': pygame.display.get_driver(), 'dummy': pygame.display.get_driver() == 'dummy'}
    try:
        # A fully occupied-neighborhood position ensures there is actual work.
        _, board, player, count, _ = hard_cases()[-2 if difficulty == 'very_hard' else -1]
        game.board = board
        game.current_player = player
        game.move_history = [(int(r), int(c)) for r, c in zip(*board.grid.nonzero())]
        game.display_move_index = count
        game.telop.active = False
        game.ai_runner.start(board, player, count, difficulty, budget=5.0 if difficulty == 'very_hard' else 1.5)
        game.ai_thinking = True
        proc = game.ai_runner.task.process
        game.telop.show('Thinking / UI remains responsive', None)
        frames, frame_costs = 0, []
        started = time.perf_counter()
        clock = pygame.time.Clock()
        # Poll/update/render a real window for 100ms then cancel via normal Esc.
        while time.perf_counter() - started < duration:
            tick = time.perf_counter()
            for event in pygame.event.get():
                game.handle_event(event)
            game.update()
            game.draw()
            pygame.display.flip()
            frames += 1
            frame_costs.append(time.perf_counter() - tick)
            clock.tick(60)
        pygame.image.save(screen, str(root / f'{difficulty}-ui-smoke.png'))
        cancel_start = time.perf_counter()
        next_state = game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        report.update(frames=frames, max_frame_seconds=max(frame_costs),
                      cancel_seconds=time.perf_counter()-cancel_start,
                      returned_menu=next_state == STATE_MENU,
                      worker_stopped=proc.poll() is not None)
    finally:
        game.close()
        pygame.quit()
    (root / f'{difficulty}-ui-smoke.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    assert not report['dummy']
    assert report['returned_menu'] and report['worker_stopped']
    assert report['max_frame_seconds'] < 0.3


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--difficulty', default='hard')
    parser.add_argument('--duration', type=float, default=0.12)
    args = parser.parse_args()
    main(args.difficulty, args.duration)
