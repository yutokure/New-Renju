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


def guard_runtime_data(bundle):
    if list(bundle.glob('gomoku_save_*.json')) or (bundle/'workers').exists():
        raise SystemExit('Existing portable data detected; back up/move the whole tested folder before rebuilding')


def rewrite_missing_doc_links(bundle, commit):
    import re
    for path in bundle.rglob('*.md'):
        if '_internal' in path.relative_to(bundle).parts:
            continue
        def resolve(match):
            destination=match.group(1)
            if destination.startswith(('#','https://','http://','mailto:')):
                return match.group(0)
            local=destination.split('#',1)[0]
            target=(path.parent/local).resolve()
            if target.is_relative_to(bundle.resolve()) and target.exists():
                return match.group(0)
            relative=target.relative_to(bundle.resolve()) if target.is_relative_to(bundle.resolve()) else Path(local).name
            return ']('+REPOSITORY_URL+'/blob/'+commit+'/'+str(relative).replace('\\','/')+')'
        path.write_text(re.sub(r'\]\(<([^>]+)>\)',resolve,path.read_text(encoding='utf-8')),encoding='utf-8')


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
    bundle=ROOT/'dist'/BUNDLE_DIRECTORY
    guard_runtime_data(bundle)  # Before COLLECT can replace an existing portable folder.
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
        'Portable: saved games are beside this exe; worker temporary data is in workers/.\n'
        'Use an extracted writable folder. No TEMP/LocalAppData fallback or elevation is used.\n'
        'Check the official release source and SHA-256 before running unsigned software.\n'
        f'{REPOSITORY_URL}\n',encoding='utf-8')
    (bundle/'MANUAL.md').write_text((ROOT/'docs/USER_MANUAL.md').read_text(encoding='utf-8')
        .replace('](<../','](<').replace('](<RELEASE_NOTES_2.0.md','](<docs/RELEASE_NOTES_2.0.md'),encoding='utf-8')
    (bundle/'docs').mkdir(exist_ok=True)
    for name in ('USER_MANUAL.md','RELEASE_NOTES_2.0.md'):
        shutil.copyfile(ROOT/'docs'/name,bundle/'docs'/name)
    images=bundle/'benchmarks/results'
    images.mkdir(parents=True,exist_ok=True)
    for name in ('g04-game.png','g04-settings.png','g04-rules.png'):
        shutil.copyfile(ROOT/'benchmarks/results'/name,images/name)
    shutil.copyfile(ROOT/'README.md',bundle/'README.md')
    shutil.copyfile(ROOT/'requirements.txt',bundle/'requirements.txt')
    # Source-only links in the manual lead to the matching release source, not
    # nonexistent .py files inside the standalone distribution.
    for manual in (bundle/'MANUAL.md',bundle/'docs/USER_MANUAL.md'):
        text=manual.read_text(encoding='utf-8')
        for relative in ('main.py','../main.py'):
            text=text.replace('](<'+relative+'>)',']('+REPOSITORY_URL+'/blob/'+commit+'/main.py)')
        manual.write_text(text,encoding='utf-8')
    shutil.copyfile(ROOT/'LICENSE',bundle/'LICENSE')
    rewrite_missing_doc_links(bundle,commit)
    guard_runtime_data(bundle)
    manifest={'product':PRODUCT_NAME,'version':VERSION,'source_commit':commit,
              'working_tree_clean':not bool(status.strip()),'python':platform.python_version(),
              'dependencies':{name:importlib.metadata.version(name) for name in ('pygame','numpy','pyinstaller')},
              'source_files':{str(p.relative_to(ROOT)).replace('\\','/'):digest(p)
                  for p in ROOT.rglob('*') if p.is_file() and
                  p.suffix in ('.py','.spec','.json','.otf','.ttf','.md','.txt') and
                  not p.name.startswith('gomoku_save_') and
                  not any(part in ('build','dist','workers','.git','__pycache__','.pytest_cache')
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
