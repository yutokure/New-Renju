"""G04 truthful UI states, rule explanations, display-only hints."""
import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
import pygame
import pytest
from board import BLACK, WHITE
from constants import BUTTON_TEXT_COLOR, BUTTON_COLOR
from game import Game
from settings import Settings
from ui_text import rules_help, rules_label, mode_label


@pytest.fixture
def game():
    pygame.init()
    screen = pygame.display.set_mode((800,600))
    s=Settings()
    s.set_game_mode((0,0))
    g=Game(screen,s)
    g.telop.active=False
    try:
        yield g
    finally:
        g.close()
        pygame.quit()


def test_english_rules_distinguish_core_custom_and_opening(game):
    text=' '.join(rules_help(game.settings))
    for phrase in ('Black exact 5','White 5+','double-three','overline','Simplified opening',
                   'Not tournament','no swaps','NOT guaranteed legal','NOT a win proof'):
        assert phrase in text
    for target in (3,4,6,7):
        game.settings.win_length=target
        assert f'Custom connect-{target}' in rules_label(game.settings)
        assert 'no black fouls' in rules_label(game.settings)
    game.settings.game_mode=(1,0)
    game.settings.ai_difficulty='very_hard'
    assert mode_label(game.settings)=='AI vs Human | Very Hard'


def test_button_contrast_not_white_on_light_gray():
    assert max(BUTTON_TEXT_COLOR)<40 and min(BUTTON_COLOR)>=170


def test_invalid_reasons_are_certain_and_occupancy_not_foul(game):
    assert not game._make_move(0,0)
    assert 'Opening' in game.invalid_reason
    game._make_move(7,7)
    assert game.invalid_reason is None
    assert not game._make_move(7,7)
    assert 'Occupied' in game.invalid_reason
    assert 'Forbidden' not in game.invalid_reason
    assert 'Occupied' in game.status_text()


def test_status_priority_and_unknown_keep_stone_unplayed(game):
    game.validation_status='unknown'
    assert 'UNKNOWN / unplayed' in game.status_text()
    assert not game.move_history
    game._pending_validation={}
    assert 'Checking move legality' in game.status_text()
    game._pending_validation=None
    game.ai_error='failed'
    assert 'AI unavailable' in game.status_text()
    game.game_over=True
    assert 'Game over' in game.status_text()
    game.is_history_mode=True
    assert 'History' in game.status_text()


def test_rules_panel_pauses_workers_and_consumes_input(game):
    click=lambda pos: pygame.event.Event(pygame.MOUSEBUTTONDOWN,pos=pos,button=1)
    game.handle_event(click(game.rules_button.rect.center))
    assert game.rules_visible and game.interaction_state=='rules'
    game.handle_event(click((400,310)))
    game.update()
    game.draw()
    assert not game.move_history and not game.ai_runner.busy
    game.handle_event(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_ESCAPE))
    assert not game.rules_visible


def test_own_four_completed_to_win_does_not_emit_defense(game):
    moves=[[7,7],[6,7],[7,6],[0,0],[7,5],[0,2],[7,4],[0,4]]
    game.reset_game(moves)
    assert game._make_move(7,3)
    assert game.game_over and game.winner==BLACK
    assert not game.text_popups


def test_opponent_open_four_downgrade_is_defense_hint(game):
    # Display-isolated position; adjudication still uses normal place_stone.
    game.board.grid[7,5:9]=BLACK
    game.board.grid[0,0:3]=WHITE
    game.board.last_move=(7,8)
    game.move_history=[(7,5),(0,0),(7,6),(0,1),(7,7),(0,2),(7,8)]
    game.current_player=WHITE
    assert game._make_move(7,4)
    assert not game.game_over
    assert 'Defense' in [popup.text for popup in game.text_popups]


@pytest.mark.parametrize('target',[3,4,6,7])
def test_custom_target_has_no_five_only_attack_popup(game,target):
    game.settings.win_length=target
    game.reset_game()
    game.board.grid[7,5:7]=BLACK
    game.move_history=[(7,5),(0,0),(7,6),(0,2)]
    game.board.grid[0,0]=game.board.grid[0,2]=WHITE
    game.current_player=BLACK
    assert game._make_move(7,7)
    assert not game.text_popups
    assert game.game_over == (target==3)


class Runner:
    def __init__(self,result=None,fail=False):
        self.busy=False
        self.result=result
        self.fail=fail
        self.calls=[]
    def start(self,*args,**kwargs):
        self.calls.append(kwargs['kind'])
        if self.fail:
            raise OSError('denied')
        self.busy=True
    def poll(self,*args):
        self.busy=False
        return self.result
    def cancel(self):
        self.busy=False
    close=cancel
    def reap(self):
        pass


@pytest.mark.parametrize('result,status',[({'partial':True,'legality_complete':False,'scores':[[7,7,1]]},'partial'),
    ({'error':'failed'},'failed'), ({'legality_complete':True,'invalid_cells':[]},'complete')])
def test_analysis_result_has_explicit_completeness(game,result,status):
    game.analysis_runner.close()
    game.analysis_runner=Runner(result)
    game.analysis_runner.busy=True
    before=game.board.grid.tobytes()
    game._poll_analysis()
    assert game.analysis_status.startswith(status)
    assert game.overlay_status.startswith(status)
    assert (game._overlay_done_key is not None)==(status=='complete')
    assert game.board.grid.tobytes()==before and not game.game_over


def test_overlay_spawn_failure_does_not_spin_and_r_is_explicit_retry(game):
    game.analysis_runner.close()
    game.analysis_runner=Runner(fail=True)
    game._queue_legality_overlay()
    assert 'failed' in game.overlay_status
    game._queue_legality_overlay()
    assert len(game.analysis_runner.calls)==1
    game.handle_event(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_r))
    game._queue_legality_overlay()
    assert len(game.analysis_runner.calls)==2


def test_move_clears_position_specific_analysis_status(game):
    game.reset_game([[7,7]])
    game.player_types=(1,0)
    game.overlay_status='no black fouls on this turn'
    game.analysis_status='complete'
    assert game._make_move(6,7)
    assert game.current_player==BLACK
    assert game.overlay_status==game.analysis_status=='not checked'
    assert game._overlay_done_key is None


def test_rules_close_advances_input_generation(game):
    game.rules_visible=True
    epoch=game.input_epoch
    game.handle_event(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_ESCAPE))
    assert not game.rules_visible and game.input_epoch>epoch


def test_layout_text_fits_screen(game):
    for text in rules_help(game.settings):
        assert game.small_font.size(text)[0] <= 750, text
    controls=[game.research_mode_checkbox.clickable_area,game.rules_button.rect,
              game.save_button.rect,game.back_button.rect]
    for i,rect in enumerate(controls):
        for other in controls[i+1:]:
            assert not rect.colliderect(other)
