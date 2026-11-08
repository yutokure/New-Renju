"""Drive real Pygame main menu/settings/game transitions via queued UI events.

Runs main() itself; optional frozen launch is tested separately.
"""
import json
from pathlib import Path
import threading
import time
import pygame
import main as app


def click(pos):
    pygame.event.post(pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0,0), buttons=(0,0,0)))
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1))


def drive(done,errors):
    try:
        # Brief waits synchronize known screen transitions in this local GUI
        # test; this is not waiting/polling a harness background job.
        time.sleep(.3)
        click((400,405))  # Menu Settings
        time.sleep(.2)
        click((585,350))  # Normal -> Hard
        time.sleep(.15)
        click((585,350))  # Hard -> Very Hard
        time.sleep(.2)
        screen=pygame.display.get_surface()
        pygame.image.save(screen,'benchmarks/results/settings-four-levels.png')
        click((400,520))  # Back
        time.sleep(.15)
        click((400,265))  # Start New Game
        time.sleep(.25)
        click((400,310))  # Human black center
        time.sleep(.5)
        pygame.image.save(screen,'benchmarks/results/main-ui-game.png')
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_ESCAPE))
        time.sleep(.15)
        click((400,335))  # Load Game selection
        time.sleep(.15)
        click((400,550))  # Back (fallback QUIT below always closes)
        time.sleep(.1)
        pygame.event.post(pygame.event.Event(pygame.QUIT))
    except Exception as exc:
        errors.append(repr(exc))
        pygame.event.post(pygame.event.Event(pygame.QUIT))
    finally:
        done.set()


def main():
    done=threading.Event()
    errors=[]
    recorded=[]
    OriginalGame=app.Game
    class RecordedGame(OriginalGame):
        def __init__(self,screen,settings):
            recorded.append({'difficulty':settings.ai_difficulty,'board_size':settings.board_size,'target':settings.win_length})
            super().__init__(screen,settings)
    app.Game=RecordedGame
    thread=threading.Thread(target=drive,args=(done,errors),daemon=True)
    thread.start()
    try:
        app.main()
    except SystemExit:
        pass
    finally:
        app.Game=OriginalGame
        thread.join(timeout=2)
    report={'errors':errors,'created_games':recorded,'driver':'native windows SDL main loop',
            'closed_cleanly':done.is_set()}
    Path('benchmarks/results/main-ui-smoke.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
    assert not errors and done.is_set()
    assert recorded and recorded[0]['difficulty']=='very_hard'


if __name__=='__main__':
    main()
