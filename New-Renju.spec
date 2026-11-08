# Local Windows x64 PyInstaller onedir build. No CI integration.
from pathlib import Path
import sys
root = Path(SPECPATH)
sys.path.insert(0,str(root))
from app_info import PRODUCT_NAME, BUNDLE_DIRECTORY
from tools.build_release import version_file, guard_runtime_data
guard_runtime_data(root / 'dist' / BUNDLE_DIRECTORY)
version_path = root / 'build' / 'windows-version.txt'
version_path.parent.mkdir(exist_ok=True)
version_file(version_path)
a = Analysis(
    [str(root / 'main.py')], pathex=[str(root)], binaries=[],
    datas=[(str(root / 'joseki.json'), '.'), (str(root / 'fonts'), 'fonts'),
           (str(root / 'LICENSE'), '.'),
           (str(root / 'third_party_licenses'), 'THIRD_PARTY_LICENSES')],
    hiddenimports=['ai_worker', 'very_hard', 'tactics', 'renju_rules', 'worker_limits'],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False,
)
# The application always supplies its own permissively licensed fonts. Do not
# redistribute Pygame's historical FreeSans whose editable source is unverified.
a.datas = [entry for entry in a.datas if Path(entry[0]).name.lower() != 'freesansbold.ttf']
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=PRODUCT_NAME,
          version=str(version_path), debug=False, bootloader_ignore_signals=False,
          strip=False, upx=False, console=False, disable_windowed_traceback=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=BUNDLE_DIRECTORY)
