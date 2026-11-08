# Local PyInstaller onedir build. No CI integration.
from pathlib import Path
root = Path(SPECPATH)
a = Analysis(
    [str(root / 'main.py')],
    pathex=[str(root)],
    binaries=[],
    datas=[(str(root / 'joseki.json'), '.'), (str(root / 'fonts'), 'fonts')],
    hiddenimports=['ai_worker', 'very_hard', 'tactics', 'renju_rules', 'worker_limits'],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='New-Renju',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='New-Renju')
