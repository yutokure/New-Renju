"""G02 event coordinates and transition barriers (no AI engine changes)."""
import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
import pygame
import pytest
from constants import PLAYER_HUMAN, PLAYER_AI, STATE_MENU
from settings import Settings
from ui import Button


@pytest.fixture
def screen():
    pygame.init()
    screen = pygame.display.set_mode((800,600))
    yield screen
    pygame.quit()


@pytest.fixture
def game(screen):
    from game import Game
    s = Settings()
    s.set_game_mode((PLAYER_HUMAN, PLAYER_HUMAN))
    instance = Game(screen, s)
    try:
        yield instance
    finally:
        instance.close()


def click(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)


def cell(game, row, col):
    return (game.start_x + col*game.cell_size, game.start_y + row*game.cell_size)


def test_fixed_button_long_label_fits_and_retains_data(screen):
    from ui_fonts import ui_font
    name='gomoku_save_20261108_160132_986089_c050f008.json'
    button=Button(name,(400,150),ui_font(36),width=460,height=35,data='full/path/'+name)
    assert button.rect.contains(button.text_rect)
    assert button.text_surf.get_width()<=440
    assert button.text==name
    assert button.handle_event(click((400,150)))=='full/path/'+name


def test_button_direct_click_without_hover(screen):
    button = Button('Do it', (100,100), pygame.font.Font(None,24))
    assert not button.is_hovering
    assert button.handle_event(click((100,100))) == 'Do it'
    assert button.is_hovering


def test_stale_hover_cannot_activate_another_coordinate(screen):
    button = Button('Do it', (100,100), pygame.font.Font(None,24), data=42)
    button.is_hovering = True
    assert button.handle_event(click((700,500))) is None
    assert not button.is_hovering
    assert button.handle_event(click((100,100))) == 42
    assert button.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(100,100), button=3)) is None


def test_board_click_uses_event_not_current_pointer(game, monkeypatch):
    monkeypatch.setattr(pygame.mouse, 'get_pos', lambda: game.research_mode_checkbox.clickable_area.center)
    game.handle_event(click(cell(game,7,7)))
    assert game.move_history == [(7,7)]


def test_two_human_clicks_during_animation_apply_only_one(game):
    game.handle_event(click(cell(game,7,7)))
    assert game.interaction_state == 'animating'
    game.handle_event(click(cell(game,6,7)))
    assert game.move_history == [(7,7)]
    game.placing_stone_animation = False
    game.animation_blink_count = 0
    game.handle_event(click(cell(game,6,7)))
    assert game.move_history == [(7,7),(6,7)]


def test_history_and_live_return_preserve_actual_position(game):
    game.reset_game([[7,7],[6,7],[7,8]])
    board_bytes = game.board.grid.tobytes()
    epoch = game.input_epoch
    game.handle_event(click(game.prev_move_button.rect.center))
    assert game.interaction_state == 'history' and game.display_move_index == 2
    assert game.input_epoch > epoch
    game.handle_event(click(cell(game,7,9)))
    assert len(game.move_history) == 3 and game.board.grid.tobytes() == board_bytes
    game.handle_event(click(game.next_move_button.rect.center))
    assert game.interaction_state == 'playing' and game.display_move_index == 3
    assert game.board.grid.tobytes() == board_bytes


def test_navigation_and_save_available_during_animation(game, monkeypatch):
    game.handle_event(click(cell(game,7,7)))
    calls = []
    monkeypatch.setattr(game, '_save_game', lambda: calls.append(True))
    game.handle_event(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_s))
    assert calls == [True] and len(game.move_history) == 1
    game.handle_event(click(game.prev_move_button.rect.center))
    assert game.is_history_mode and game.display_move_index == 0
    assert game.handle_event(click(game.back_button.rect.center)) == STATE_MENU
    assert not any(r.busy for r in (game.ai_runner,game.analysis_runner,game.validation_runner))


def test_explicit_unknown_state_does_not_become_legal(game):
    game._validation_retry = {'candidate': (7,7)}
    game.validation_status = 'unknown'
    assert game.interaction_state == 'unconfirmed'
    game.handle_event(click((0,0)))
    assert not game.move_history and not game.board.grid.any()
    assert game.validation_status == 'unknown'


def test_rematch_failure_preserves_finished_game_and_notifies(game, monkeypatch):
    import game as module
    game.game_over, game.winner = True, 1
    board, history = game.board, game.move_history
    def fail():
        raise PermissionError('resource unavailable')
    monkeypatch.setattr(module, 'load_joseki', fail)
    game.handle_event(click(game.rematch_button.rect.center))
    assert game.board is board and game.move_history is history
    assert game.game_over and game.winner == 1 and 'preserved' in game.save_notice[0]


def test_rematch_resets_all_state_and_advances_input_epoch(game):
    game.reset_game([[7,7],[6,7],[7,8]])
    game.game_over = True
    epoch = game.input_epoch
    game.handle_event(click(game.rematch_button.rect.center))
    assert not game.move_history and not game.board.grid.any()
    assert game.interaction_state == 'playing' and game.input_epoch > epoch
    assert game.current_player == 1 and not game.ai_runner.busy


def test_start_resource_failure_stays_in_menu(screen, monkeypatch):
    import main
    attempts = []
    def fail(*args, **kwargs):
        attempts.append(True)
        raise PermissionError('font or joseki unavailable')
    monkeypatch.setattr(main, 'Game', fail)
    batches = iter([[click((400,265))],[pygame.event.Event(pygame.QUIT)]])
    monkeypatch.setattr(pygame.event, 'get', lambda: next(batches))
    with pytest.raises(SystemExit):
        main.main()
    assert attempts == [True] and not pygame.get_init()


def test_main_queued_start_click_cannot_place_on_new_screen(screen, monkeypatch):
    import main
    original = main.Game
    games = []
    class RecordedGame(original):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            games.append(self)
    # Start click and board center are in one queued batch; only Start is valid.
    batches = iter([[click((400,265)),click((400,310))], [pygame.event.Event(pygame.QUIT)]])
    monkeypatch.setattr(main, 'Game', RecordedGame)
    monkeypatch.setattr(pygame.event, 'get', lambda: next(batches))
    with pytest.raises(SystemExit):
        main.main()
    assert len(games) == 1 and games[0].move_history == []


@pytest.mark.parametrize('difficulty', ['easy','normal','hard','very_hard'])
def test_four_difficulties_complete_human_ai_human_transition(screen, difficulty):
    """Real workers serially: human Black -> AI White -> human Black."""
    import time
    from game import Game
    s = Settings()
    s.set_game_mode((PLAYER_HUMAN,PLAYER_AI))
    s.set_ai_difficulty(difficulty)
    game = Game(screen,s)
    try:
        game.handle_event(click(cell(game,7,7)))
        assert game.move_history == [(7,7)]
        game.placing_stone_animation = False
        game.animation_blink_count = 0
        deadline = time.perf_counter() + 9
        clock = pygame.time.Clock()
        while len(game.move_history) < 2 and not game.ai_error and time.perf_counter() < deadline:
            game.update()
            clock.tick(100)
        assert not game.ai_error, game.ai_error
        assert len(game.move_history) == 2 and game.current_player == 1
        assert game.move_history[1] in ((6,7),(6,8))
        assert not game.ai_thinking and not game._pending_validation
    finally:
        game.close()
    assert not game.ai_runner.retired
