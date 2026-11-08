"""Four-level configuration, versioned saves and detached-overlay integration."""
import json
import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
import pygame
import pytest
from ai_async import AsyncAI
from board import Board, BLACK
from constants import AI_LABELS, PLAYER_HUMAN
from settings import Settings


@pytest.mark.parametrize('difficulty',['easy','normal','hard','very_hard'])
def test_all_difficulties_roundtrip_old_schema(difficulty,tmp_path):
    from main import _load_game_data
    s=Settings()
    assert difficulty in s.ai_difficulty_options
    s.set_ai_difficulty(difficulty)
    assert s.ai_difficulty == difficulty
    assert AI_LABELS[difficulty] == ('Very Hard' if difficulty=='very_hard' else difficulty.capitalize())
    data={'settings':{'board_size':15,'win_length':5,'game_mode':[1,1],'ai_difficulty':difficulty,'ai_starts':True},
          'move_history':[[7,7],[6,7],[6,8]]}
    path=tmp_path/'save.json'
    path.write_text(json.dumps(data))
    settings,history=_load_game_data(path)
    assert settings['ai_difficulty']==difficulty and history==data['move_history']


@pytest.mark.parametrize('field,value',[('board_size',8),('win_length',99),('win_length',False),
                                        ('ai_difficulty','unknown'),('game_mode',[5,6]),
                                        ('ai_starts','false')])
def test_invalid_save_settings_rejected(field,value,tmp_path):
    from main import _load_game_data
    data={'settings':{'board_size':15,'win_length':5,'game_mode':[0,1],'ai_difficulty':'hard','ai_starts':False},'move_history':[]}
    data['settings'][field]=value
    path=tmp_path/'bad.json'
    path.write_text(json.dumps(data))
    assert _load_game_data(path)==(None,None)


@pytest.mark.parametrize('history',[[[7,7],[7,7]], [[15,0]], [[True,7]]])
def test_invalid_history_rejected(history,tmp_path):
    from main import _load_game_data
    data={'settings':{'board_size':15,'win_length':5,'game_mode':[0,1],'ai_difficulty':'hard','ai_starts':False},'move_history':history}
    path=tmp_path/'bad.json'
    path.write_text(json.dumps(data))
    assert _load_game_data(path)==(None,None)


def test_versioned_rules_metadata_is_checked(tmp_path):
    from main import _load_game_data
    data={'schema_version':2,'rules':{'ruleset':'renju-rif-core-15x15','opening_policy':'simplified-center-opening'},
          'settings':{'board_size':15,'win_length':5,'game_mode':[0,1],'ai_difficulty':'very_hard','ai_starts':False},
          'move_history':[[7,7]]}
    path=tmp_path/'v2.json'
    path.write_text(json.dumps(data))
    assert _load_game_data(path)[0]['ai_difficulty']=='very_hard'
    data['rules']['ruleset']='unimplemented-tournament-rule'
    path.write_text(json.dumps(data))
    assert _load_game_data(path)==(None,None)


def test_invalid_adapter_budgets_rejected_before_spawn():
    runner=AsyncAI()
    try:
        for budget in (float('inf'),float('nan'),-1):
            with pytest.raises(ValueError):
                runner.start(Board(),BLACK,0,'very_hard',budget=budget)
            assert not runner.busy
    finally:
        runner.close()


def test_ui_rule_timeout_is_not_cached_as_illegal():
    from board import RuleValidationTimeout
    board = Board()
    board.validation_budget_sec = 0
    with pytest.raises(RuleValidationTimeout):
        board.is_valid_move(7,7,BLACK,0)
    assert not board._legality_cache
    assert not board.grid.any()
    board.validation_budget_sec = None
    assert board.is_valid_move(7,7,BLACK,0)


def test_forbidden_overlay_draw_never_enumerates_recursive_legality(monkeypatch):
    from game import Game
    pygame.init()
    screen=pygame.display.set_mode((800,600))
    s=Settings()
    s.set_game_mode((PLAYER_HUMAN,PLAYER_HUMAN))
    game=Game(screen,s)
    try:
        def fail(*args,**kwargs):
            raise AssertionError('Recursive legality must not run in draw')
        monkeypatch.setattr(game.board,'is_valid_move',fail)
        game._visual_key=None
        game.needs_redraw=True
        game.draw()
        game._queue_legality_overlay()
        assert game.analysis_runner.busy
    finally:
        game.close()
        pygame.quit()
