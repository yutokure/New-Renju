"""Local Windows onedir build + reproducible payload manifest and ZIP.

No upload/Release publication here. Build accepted clean commit, test extracted
ZIP and only then tag/publish via the documented G05 gate.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import importlib.metadata
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app_info import (PRODUCT_NAME, VERSION, WINDOWS_VERSION, ZIP_NAME,
                      EXE_NAME, BUNDLE_DIRECTORY, REPOSITORY_URL)


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()


def version_file(path):
    from PyInstaller.utils.win32.versioninfo import (VSVersionInfo,FixedFileInfo,
        StringFileInfo,StringTable,StringStruct,VarFileInfo,VarStruct)
    strings={'CompanyName':'yutokure','FileDescription':PRODUCT_NAME,'FileVersion':VERSION,
        'InternalName':PRODUCT_NAME,'LegalCopyright':'Copyright (c) 2025 yutokure',
        'OriginalFilename':EXE_NAME,'ProductName':PRODUCT_NAME,'ProductVersion':VERSION}
    info=VSVersionInfo(ffi=FixedFileInfo(filevers=WINDOWS_VERSION,prodvers=WINDOWS_VERSION,
        mask=0x3f,flags=0,OS=0x40004,fileType=1,subtype=0,date=(0,0)),
        kids=[StringFileInfo([StringTable('040904B0',[StringStruct(k,v) for k,v in strings.items()])]),
              VarFileInfo([VarStruct('Translation',[1033,1200])])])
    path.write_text(str(info),encoding='utf-8')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--build-only',action='store_true')
    args=parser.parse_args()
    if os.name!='nt' or platform.machine().lower() not in ('amd64','x86_64'):
        raise SystemExit('Build requires native Windows x64')
    # Output capture is git only; PyInstaller inherits stdio, no hidden pipe.
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    status=subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)
    if status.strip():
        if not args.build_only:
            raise SystemExit('Refusing release ZIP from a dirty working tree; commit accepted changes first')
        print('WARNING: working tree is dirty; development build is not releasable',flush=True)
    build=ROOT/'build'
    build.mkdir(exist_ok=True)
    version_file(build/'windows-version.txt')
    subprocess.run([sys.executable,'-B','-m','PyInstaller','--noconfirm',str(ROOT/'New-Renju.spec')],
                   cwd=ROOT,check=True)
    bundle=ROOT/'dist'/BUNDLE_DIRECTORY
    (bundle/'README.txt').write_text(
        f'{PRODUCT_NAME}\nVersion {VERSION}\n\nExtract the complete ZIP and open {EXE_NAME}.\n'
        'No Python install is required. Windows 10/11 x64.\n'
        'Manual: MANUAL.md. License: LICENSE. Third-party notices: _internal/THIRD_PARTY_LICENSES/.\n'
        'Saves: %LOCALAPPDATA%\\Gomoku2\\Saves. Workers: %LOCALAPPDATA%\\Gomoku2\\workers.\n'
        'Check the official release source and SHA-256 before running unsigned software.\n'
        f'{REPOSITORY_URL}\n',encoding='utf-8')
    (bundle/'MANUAL.md').write_text((ROOT/'docs/USER_MANUAL.md').read_text(encoding='utf-8')
        .replace('](<../','](<').replace('](<RELEASE_NOTES_2.0.md','](<docs/RELEASE_NOTES_2.0.md'),encoding='utf-8')
    shutil.copytree(ROOT/'docs',bundle/'docs',dirs_exist_ok=True)
    shutil.copytree(ROOT/'benchmarks/results',bundle/'benchmarks/results',dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('*.prof','g05-*','*.json','*.txt'))
    shutil.copyfile(ROOT/'README.md',bundle/'README.md')
    shutil.copyfile(ROOT/'LICENSE',bundle/'LICENSE')
    manifest={'product':PRODUCT_NAME,'version':VERSION,'source_commit':commit,
              'working_tree_clean':not bool(status.strip()),'python':platform.python_version(),
              'dependencies':{name:importlib.metadata.version(name) for name in ('pygame','numpy','pyinstaller')},
              'source_files':{str(p.relative_to(ROOT)).replace('\\','/'):digest(p)
                  for p in ROOT.rglob('*') if p.is_file() and
                  p.suffix in ('.py','.spec','.json','.otf','.md','.txt') and
                  not any(part in ('build','dist','.git','__pycache__','.pytest_cache')
                          for part in p.relative_to(ROOT).parts)},
              'files':{str(p.relative_to(bundle)).replace('\\','/'):digest(p)
                       for p in sorted(bundle.rglob('*')) if p.is_file()}}
    (bundle/'BUILD_INFO.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    if args.build_only:
        return
    archive=ROOT/'dist'/ZIP_NAME
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as zip:
        for file in sorted(bundle.rglob('*')):
            if file.is_file():
                zip.write(file,str(Path(BUNDLE_DIRECTORY)/file.relative_to(bundle)))
    checksum=archive.with_suffix(archive.suffix+'.sha256')
    checksum.write_text(digest(archive)+'  '+archive.name+'\n',encoding='ascii')
    print(json.dumps({'zip':str(archive),'sha256':digest(archive),'source_commit':commit,
                      'clean':not bool(status.strip())},indent=2))


if __name__=='__main__':
    main()
