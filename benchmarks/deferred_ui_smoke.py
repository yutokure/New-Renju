"""Force the UI fast-rule budget to zero, then verify detached exact adjudication."""
import json
from pathlib import Path
import time
import pygame
from board import BLACK
from constants import PLAYER_HUMAN
from game import Game
from settings import Settings


def main():
    pygame.init()
    screen=pygame.display.set_mode((800,600))
    settings=Settings()
    settings.set_game_mode((PLAYER_HUMAN,PLAYER_HUMAN))
    game=Game(screen,settings)
    frames=[]
    try:
        game.telop.active=False
        game.board.validation_budget_sec=0
        began=time.perf_counter()
        applied=game._make_move(7,7)
        assert not applied and not game.move_history
        clock=pygame.time.Clock()
        deadline=began+8
        while not game.move_history and time.perf_counter()<deadline:
            start=time.perf_counter()
            for event in pygame.event.get():
                game.handle_event(event)
            game.update()
            game.draw()
            pygame.display.flip()
            frames.append(time.perf_counter()-start)
            clock.tick(60)
        result={'fast_budget_seconds':0,'move_applied':game.move_history==[(7,7)],
                'board_black_center':bool(game.board.grid[7,7]==BLACK),
                'wall_seconds':time.perf_counter()-began,
                'max_frame_seconds':max(frames,default=0),'frames':len(frames),
                'game_over_unchanged':not game.game_over,'driver':pygame.display.get_driver()}
        pygame.image.save(screen,'benchmarks/results/deferred-ui-smoke.png')
    finally:
        game.close()
        pygame.quit()
    Path('benchmarks/results/deferred-ui-smoke.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
    assert result['move_applied'] and result['board_black_center'] and result['game_over_unchanged']
    assert result['max_frame_seconds']<.3


if __name__=='__main__':
    main()
