"""Portable packaging guards run before PyInstaller can replace user data."""
import sys
import pytest
from tools import build_release as build


@pytest.mark.parametrize('kind',['save','workers'])
def test_preflight_preserves_existing_data_without_invoking_builder(tmp_path,monkeypatch,kind):
    bundle=tmp_path/'dist'/build.BUNDLE_DIRECTORY
    bundle.mkdir(parents=True)
    if kind=='save':
        protected=bundle/'gomoku_save_user.json'
    else:
        (bundle/'workers').mkdir()
        protected=bundle/'workers'/'owned.txt'
    protected.write_bytes(b'important existing user data')
    monkeypatch.setattr(build,'ROOT',tmp_path)
    monkeypatch.setattr(build.os,'name','nt')
    monkeypatch.setattr(build.platform,'machine',lambda:'AMD64')
    monkeypatch.setattr(build.subprocess,'check_output',lambda *a,**k:'')
    monkeypatch.setattr(build.subprocess,'run',lambda *a,**k:pytest.fail('must guard before PyInstaller'))
    monkeypatch.setattr(sys,'argv',['build_release.py','--build-only'])
    with pytest.raises(SystemExit,match='Existing portable data'):
        build.main()
    assert protected.read_bytes()==b'important existing user data'


def test_missing_packaged_links_use_exact_commit_source(tmp_path):
    bundle=tmp_path/'bundle'
    (bundle/'docs').mkdir(parents=True)
    path=bundle/'README.md'
    path.write_text('[manual](<docs/USER_MANUAL.md>) [internal](<docs/design.md>) [anchor](<#x>)')
    (bundle/'docs/USER_MANUAL.md').write_text('[app](<../main.py>)')
    build.rewrite_missing_doc_links(bundle,'abcdef')
    assert '[manual](<docs/USER_MANUAL.md>)' in path.read_text()
    assert '/blob/abcdef/docs/design.md' in path.read_text()
    assert '[anchor](<#x>)' in path.read_text()
    assert '/blob/abcdef/main.py' in (bundle/'docs/USER_MANUAL.md').read_text()


def test_font_bundle_filter_and_production_routing():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    for name in ('main.py','game.py'):
        text=(root/name).read_text(encoding='utf-8')
        assert 'pygame.font.Font(None' not in text
    spec=(root/'New-Renju.spec').read_text(encoding='utf-8')
    assert "name.lower() != 'freesansbold.ttf'" in spec
    assert (root/'fonts/UiSans.ttf').is_file()
    assert (root/'third_party_licenses/DejaVu-LICENSE.txt').is_file()
