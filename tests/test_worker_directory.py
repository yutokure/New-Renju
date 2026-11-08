import os
from pathlib import Path
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
import pygame
import pytest
from game import Game
from settings import Settings
import main


def test_game_propagates_explicit_worker_root(tmp_path):
    pygame.init()
    game=Game(pygame.display.set_mode((800,600)),Settings(),worker_directory=tmp_path)
    try:
        assert all(Path(r.worker_directory)==tmp_path for r in
                   (game.ai_runner,game.analysis_runner,game.validation_runner))
    finally:
        game.close()
        pygame.quit()


def test_main_rejects_missing_worker_root_before_ui_init(tmp_path,monkeypatch):
    monkeypatch.setattr(pygame,'init',lambda:pytest.fail('Must validate config first'))
    with pytest.raises(FileNotFoundError):
        main.main(worker_directory=tmp_path/'missing')
    path=tmp_path/'not-directory'
    path.write_text('x')
    with pytest.raises(ValueError):
        main.main(worker_directory=path)
