from pathlib import Path
import sys
from resources import asset_path


def test_source_assets_are_independent_of_cwd(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert Path(asset_path('joseki.json')).is_file()
    assert Path(asset_path('fonts/YasashisaGothicBold-V2.otf')).is_file()


def test_frozen_assets_resolve_bundle_root(tmp_path,monkeypatch):
    monkeypatch.setattr(sys,'_MEIPASS',str(tmp_path),raising=False)
    assert Path(asset_path('joseki.json')) == tmp_path/'joseki.json'
