"""Capture actual SDL screens for G04/G05 local visual review."""
import json
from pathlib import Path
import pygame
from constants import SCREEN_WIDTH,SCREEN_HEIGHT
from game import Game
from settings import Settings
from rule_panel import draw_rules
import main as app


def main():
    root=Path('benchmarks/results')
    root.mkdir(exist_ok=True)
    pygame.init()
    screen=pygame.display.set_mode((SCREEN_WIDTH,SCREEN_HEIGHT))
    settings=Settings()
    settings.set_game_mode((0,0))
    game=Game(screen,settings)
    try:
        game.reset_game([[7,7],[6,7],[7,8]])
        game.telop.active=False
        game.needs_redraw=True
        game.draw()
        pygame.display.flip()
        pygame.image.save(screen,str(root/'g04-game.png'))
        draw_rules(screen,settings,game.small_font)
        pygame.display.flip()
        pygame.image.save(screen,str(root/'g04-rules.png'))
        driver=pygame.display.get_driver()
    finally:
        game.close()
        pygame.quit()
    original=pygame.event.get
    batches=iter([[pygame.event.Event(pygame.MOUSEBUTTONDOWN,pos=(400,405),button=1)],
                  [pygame.event.Event(pygame.QUIT)]])
    captured=[]
    def events():
        batch=next(batches)
        if batch[0].type==pygame.QUIT:
            pygame.image.save(pygame.display.get_surface(),str(root/'g04-settings.png'))
            captured.append(True)
        return batch
    pygame.event.get=events
    try:
        app.main()
    except SystemExit:
        pass
    finally:
        pygame.event.get=original
    result={'driver':driver,'game_rules_settings_captured':bool(captured),'native_windows':__import__('os').name=='nt'}
    (root/'g04-ui-smoke.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
