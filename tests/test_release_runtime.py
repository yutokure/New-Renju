"""G05 identity, storage and failure-cleanup contracts; no source AI changes."""
import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
from pathlib import Path
from types import SimpleNamespace
import pytest
import app_info
import app_paths
import ai_async
from board import Board, BLACK


def test_worker_permission_error_is_not_retried(monkeypatch,tmp_path):
    from worker_storage import WorkerDirectory
    calls=[]
    def fail(*args,**kwargs):
        calls.append(kwargs.get('mode'))
        raise PermissionError('denied')
    monkeypatch.setattr(Path,'mkdir',fail)
    with pytest.raises(PermissionError,match='denied'):
        WorkerDirectory(root=tmp_path)
    assert calls==[0o777]


def test_worker_name_collision_retry_is_bounded(monkeypatch,tmp_path):
    from worker_storage import WorkerDirectory
    calls=[]
    def fail(*args,**kwargs):
        calls.append(True)
        raise FileExistsError('collision')
    monkeypatch.setattr(Path,'mkdir',fail)
    with pytest.raises(FileExistsError,match='unique'):
        WorkerDirectory(root=tmp_path)
    assert len(calls)==3


def test_single_product_identity():
    assert app_info.PRODUCT_NAME=='Gomoku 2.0'
    assert app_info.DISPLAY_VERSION=='2.0' and app_info.VERSION=='2.0.0'
    assert app_info.EXE_NAME=='Gomoku 2.0.exe'
    assert app_info.ZIP_NAME=='Gomoku-2.0-Windows-x64.zip'
    assert app_info.RELEASE_TAG=='v2.0.0'
    about=' '.join(app_info.about_lines())
    for value in ('Gomoku 2.0','Version 2.0.0','Pygame','NumPy','MIT','github.com/yutokure/New-Renju'):
        assert value in about


def test_default_windows_worker_root_is_beside_exe(tmp_path,monkeypatch):
    exe_root=tmp_path/'日本語 portable'
    exe_root.mkdir()
    monkeypatch.setattr(app_paths,'sys',SimpleNamespace(frozen=True,executable=str(exe_root/'Gomoku 2.0.exe')))
    monkeypatch.setenv('LOCALAPPDATA','invalid-unused')
    monkeypatch.setenv('TEMP','invalid-unused')
    root=app_paths.default_worker_directory()
    if os.name=='nt':
        assert root==exe_root/'workers' and root.is_dir()


def test_portable_save_and_list_agree_without_chdir(tmp_path,monkeypatch):
    exe_root=tmp_path/'portable'
    exe_root.mkdir()
    monkeypatch.setattr(app_paths,'sys',SimpleNamespace(frozen=True,executable=str(exe_root/'Gomoku 2.0.exe')))
    work=tmp_path/'unrelated'
    work.mkdir()
    monkeypatch.chdir(work)
    root=app_paths.save_directory()
    assert root==exe_root
    assert app_paths.save_search_directories()==[root,work]
    assert Path.cwd()==work
    import main
    saved=root/'gomoku_save_1.json'
    legacy=work/'gomoku_save_2.json'
    saved.write_text('{}')
    legacy.write_text('{}')
    assert set(main._get_save_files())=={str(saved),str(legacy)}


def test_portable_root_does_not_use_meipass_or_cwd(tmp_path,monkeypatch):
    exe_root=tmp_path/'portable'
    exe_root.mkdir()
    monkeypatch.setattr(app_paths,'sys',SimpleNamespace(frozen=True,
        executable=str(exe_root/'Gomoku 2.0.exe'),_MEIPASS=str(tmp_path/'internal')))
    monkeypatch.chdir(tmp_path)
    assert app_paths.portable_root()==exe_root
    assert app_paths.save_directory()==exe_root


def test_source_save_stays_cwd(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app_paths,'sys',SimpleNamespace(frozen=False))
    assert app_paths.save_directory()==tmp_path


def test_worker_root_obstruction_fails_no_spawn(tmp_path,monkeypatch):
    if os.name!='nt':
        pytest.skip('Windows policy')
    (tmp_path/'workers').write_text('blocked')
    monkeypatch.setattr(app_paths,'sys',SimpleNamespace(frozen=True,executable=str(tmp_path/'Gomoku 2.0.exe')))
    monkeypatch.setattr(ai_async.subprocess,'Popen',lambda *a,**k:pytest.fail('must not spawn'))
    runner=ai_async.AsyncAI()
    with pytest.raises(OSError):
        runner.start(Board(),BLACK,0,'easy')
    runner.close()
    assert not list(tmp_path.glob('renju-ai-*'))


def test_explicit_worker_override_bypasses_default_root(tmp_path,monkeypatch):
    def fail():
        pytest.fail('explicit root must not consult default')
    monkeypatch.setattr(app_paths,'default_worker_directory',fail)
    monkeypatch.setattr(ai_async.subprocess,'Popen',lambda *a,**k: (_ for _ in ()).throw(OSError('expected spawn')))
    runner=ai_async.AsyncAI(worker_directory=tmp_path)
    with pytest.raises(OSError,match='expected spawn'):
        runner.start(Board(),BLACK,0,'easy')
    runner.close()
    assert not list(tmp_path.glob('renju-ai-*'))


@pytest.mark.skipif(os.name!='nt',reason='Windows inherited-directory implementation')
def test_request_write_failure_cleans_owned_dir_and_preserves_error(tmp_path,monkeypatch):
    original=Path.write_text
    created=[]
    import worker_storage
    actual=worker_storage.WorkerDirectory
    def directory(*args,**kwargs):
        item=actual(*args,**kwargs)
        created.append(Path(item.name))
        return item
    monkeypatch.setattr(worker_storage,'WorkerDirectory',directory)
    def fail(path,*args,**kwargs):
        if path.name=='request.json':
            raise PermissionError('primary write denied')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'write_text',fail)
    monkeypatch.setattr(ai_async.subprocess,'Popen',lambda *a,**k:pytest.fail('must not spawn'))
    runner=ai_async.AsyncAI(worker_directory=tmp_path)
    with pytest.raises(PermissionError,match='primary write denied'):
        runner.start(Board(),BLACK,0,'easy')
    assert created and not created[0].exists()
    runner.close()


@pytest.mark.skipif(os.name!='nt',reason='Windows inherited-directory implementation')
def test_spawn_failure_retains_failed_temp_cleanup_and_primary_error(monkeypatch):
    class Directory:
        name='mock-owned-directory'
        fails=True
        def cleanup(self):
            if self.fails:
                raise OSError('secondary cleanup denied')
    directory=Directory()
    import worker_storage
    monkeypatch.setattr(worker_storage,'WorkerDirectory',lambda **kwargs:directory)
    monkeypatch.setattr(Path,'write_text',lambda *a,**k:None)
    def spawn(*a,**k):
        raise PermissionError('primary spawn denied')
    monkeypatch.setattr(ai_async.subprocess,'Popen',spawn)
    runner=ai_async.AsyncAI(worker_directory='explicit')
    with pytest.raises(PermissionError,match='primary spawn denied') as failure:
        runner.start(Board(),BLACK,0,'easy')
    assert 'cleanup pending' in failure.value.__notes__[0]
    assert runner.orphan_directories==[directory]
    directory.fails=False
    runner.close()
    assert not runner.orphan_directories


def test_game_close_attempts_all_runners_and_retains_failure(monkeypatch):
    import game
    calls=[]
    class Runner:
        fail=False
        def close(self):
            calls.append(self)
            if self.fail:
                raise OSError('cleanup blocked')
    first,second,third=Runner(),Runner(),Runner()
    first.fail=True
    instance=object.__new__(game.Game)
    instance.ai_runner,instance.analysis_runner,instance.validation_runner=first,second,third
    monkeypatch.setattr(game,'_PENDING_CLEANUP',[])
    assert instance.close() is False
    assert calls==[first,second,third] and game._PENDING_CLEANUP==[first]
    first.fail=False
    assert game.retry_pending_cleanup(final=True) and not game._PENDING_CLEANUP


def test_listing_legacy_does_not_create_user_save_directory(tmp_path,monkeypatch):
    if os.name!='nt':
        pytest.skip('Windows policy')
    monkeypatch.setattr(app_paths,'sys',SimpleNamespace(frozen=True,executable=str(tmp_path/'Gomoku 2.0.exe')))
    monkeypatch.chdir(tmp_path)
    (tmp_path/'gomoku_save_old.json').write_text('{}')
    def forbidden(*args,**kwargs):
        pytest.fail('read-only listing must not mkdir')
    monkeypatch.setattr(Path,'mkdir',forbidden)
    import main
    assert str(tmp_path/'gomoku_save_old.json') in main._get_save_files()


def test_japanese_font_missing_uses_licensed_ui_fallback(monkeypatch):
    import pygame
    import resources
    from settings import Settings
    from constants import PLAYER_HUMAN
    from game import Game
    actual=resources.asset_path
    monkeypatch.setattr(resources,'asset_path',lambda name:'missing-font.otf' if name.endswith('.otf') else actual(name))
    pygame.init()
    instance=None
    try:
        settings=Settings();settings.set_game_mode((PLAYER_HUMAN,PLAYER_HUMAN))
        instance=Game(pygame.display.set_mode((800,600)),settings)
        assert instance.telop_font.size('Game started')[0]>0
    finally:
        if instance:
            instance.close()
        pygame.quit()


def test_startup_exception_quits_pygame(monkeypatch):
    import pygame
    import main
    def fail(*args,**kwargs):
        raise pygame.error('display unavailable')
    monkeypatch.setattr(pygame.display,'set_mode',fail)
    with pytest.raises(pygame.error,match='display unavailable'):
        main.main()
    assert not pygame.get_init()


def test_main_exception_always_quits_pygame(monkeypatch):
    import pygame
    import main
    def fail():
        raise RuntimeError('unexpected event failure')
    monkeypatch.setattr(pygame.event,'get',fail)
    with pytest.raises(RuntimeError,match='unexpected event failure'):
        main.main()
    assert not pygame.get_init()
