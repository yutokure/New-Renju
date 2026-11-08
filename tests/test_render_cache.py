"""G03 pixel cleanup and per-position display cache regression."""
import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
import pygame
import pytest
from game import Game
from settings import Settings
from constants import PLACING_ANIMATION_DURATION, BLINK_INTERVAL, STATE_MENU
from ui import TextPopup


@pytest.fixture
def game(monkeypatch):
    pygame.init()
    screen = pygame.display.set_mode((800,600))
    s = Settings()
    s.set_game_mode((0,0))
    g = Game(screen,s)
    g.telop.active = False
    # No workers needed for pixel lifecycle tests.
    monkeypatch.setattr(g, '_queue_legality_overlay', lambda: None)
    try:
        yield g
    finally:
        g.close()
        pygame.quit()


@pytest.mark.parametrize('kind',['placing','blink','telop','popup'])
def test_last_animation_frame_redraws_and_clears_pixels(game,monkeypatch,kind):
    now = [100]
    monkeypatch.setattr(pygame.time,'get_ticks',lambda:now[0])
    game.needs_redraw = True
    game.draw()
    baseline = pygame.image.tostring(game.screen,'RGB')
    if kind == 'placing':
        # Actual board stone first, compare final normal render below.
        game._make_move(7,7)
        game.placing_animation_start_time = now[0]
        now[0] += PLACING_ANIMATION_DURATION // 2
    elif kind == 'blink':
        game.animating_stones = [(7,7,(255,0,0))]
        game.show_blink = True
        game.animation_start_time = now[0]
        game.animation_blink_count = 2
    elif kind == 'telop':
        game.telop.show('Temporary overlay',1)
    else:
        popup = TextPopup('Temporary',(400,300),game.font,duration=1)
        popup.show()
        game.text_popups = [popup]
    game.needs_redraw = True
    game.draw()
    assert pygame.image.tostring(game.screen,'RGB') != baseline
    game.needs_redraw = False
    now[0] = 5000
    game.update()
    if kind == 'telop':
        game.draw()
        game.needs_redraw = False
        now[0] = 10000
        game.update()
    assert game.needs_redraw
    game.draw()
    rendered = pygame.image.tostring(game.screen,'RGB')
    if kind != 'placing':
        assert rendered == baseline
    else:
        assert not game.placing_stone_animation
        game.needs_redraw = True
        game.draw()
        assert pygame.image.tostring(game.screen,'RGB') == rendered


def test_popup_update_runs_once_and_removal_invalidates(game):
    calls = []
    class Popup:
        def update(self):
            calls.append(True)
            return len(calls) == 1
    game.text_popups = [Popup()]
    game.needs_redraw = False
    game.update()
    assert calls == [True] and len(game.text_popups) == 1 and game.needs_redraw
    game.needs_redraw = False
    game.update()
    assert calls == [True,True] and not game.text_popups and game.needs_redraw


def test_history_clears_live_animation_and_stale_research(game):
    game._make_move(7,7)
    game.evaluation_cache = {(0,0):12345}
    game._add_text_popup('Live',(7,7),(255,255,255))
    game.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=game.prev_move_button.rect.center))
    assert game.is_history_mode and game.display_move_index == 0
    assert not game.placing_stone_animation and not game.animating_stones and not game.text_popups
    assert not game.evaluation_cache and not game.telop.active
    game.draw()
    # Empty historical board must contain neither the stone nor transient ghost.
    reference = game.screen.copy()
    game.placing_stone_animation = True
    game.placing_animated_stone_info = (7,7,1)
    game.needs_redraw = True
    game.draw()
    assert pygame.image.tostring(reference,'RGB') == pygame.image.tostring(game.screen,'RGB')


def test_history_marker_coordinate_is_normalized(game):
    game.reset_game([[7,7],[6,7],[7,8]])
    game.is_history_mode, game.display_move_index = True,1
    assert game._get_current_board_for_display().last_move == (7,7)


def test_forced_draws_reuse_threat_geometry_surface_and_text(game,monkeypatch):
    game.reset_game([[7,7],[6,7],[7,8]])
    game.telop.active = False
    game.research_mode_enabled = True
    game.evaluation_cache = {(0,0):12345}
    calls = []
    original = game._cache_threat_segments
    def count():
        calls.append(True)
        original()
    monkeypatch.setattr(game,'_cache_threat_segments',count)
    for _ in range(5):
        game.needs_redraw = True
        game.draw()
    assert len(calls) == 1
    surface = game._invalid_surface
    texts = dict(game._text_surfaces)
    game.needs_redraw = True
    game.draw()
    assert game._invalid_surface is surface and game._text_surfaces == texts
    game.board.grid[0,0] = 1
    game.needs_redraw = True
    game.draw()
    assert len(calls) == 2


def test_many_popups_keep_menu_available_without_mutating_judgment(game):
    before = game.board.grid.tobytes()
    for index in range(30):
        game._add_text_popup(str(index),(7,7),(255,255,255))
    game.needs_redraw = True
    game.update()
    game.draw()
    assert game.board.grid.tobytes() == before and not game.game_over
    assert game.handle_event(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_ESCAPE)) == STATE_MENU


def test_telop_is_not_recomposited_on_unchanged_frame(game):
    game.telop.show('Visible',1000)
    game.needs_redraw = True
    game.draw()
    first = pygame.image.tostring(game.screen,'RGB')
    game.draw()
    assert pygame.image.tostring(game.screen,'RGB') == first


def test_hover_forces_dirty_frame(game):
    game.needs_redraw = False
    game.handle_event(pygame.event.Event(pygame.MOUSEMOTION,pos=game.back_button.rect.center))
    assert game.needs_redraw and game.back_button.is_hovering


def test_research_interrupts_incomplete_overlay_then_requeues(game):
    # Minimal fake: no subprocess, only shared runner scheduling.
    class Runner:
        def __init__(self):
            self.busy = False
            self.calls = []
        def start(self,*args,**kwargs):
            self.busy = True
            self.calls.append(kwargs['kind'])
        def cancel(self):
            self.busy = False
        def close(self):
            self.cancel()
    game.analysis_runner.close()
    game.analysis_runner = Runner()
    # Restore real method shadowed by fixture.
    game._queue_legality_overlay = Game._queue_legality_overlay.__get__(game)
    game._queue_legality_overlay()
    assert game.analysis_runner.calls == ['legality'] and game._overlay_key
    pos = game.research_mode_checkbox.clickable_area.center
    game.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN,pos=pos,button=1))
    assert game.analysis_runner.calls == ['legality','analysis']
    assert game._overlay_key is None and game._overlay_done_key is None
    game.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN,pos=pos,button=1))
    game._queue_legality_overlay()
    assert game.analysis_runner.calls == ['legality','analysis','legality']
