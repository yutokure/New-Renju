"""Explicit per-user runtime storage for the Windows distribution.

No ACL repair, administrator request, hidden TEMP fallback or bundle writes.
Source saves retain cwd compatibility; older cwd saves remain discoverable.
"""
import os
from pathlib import Path
import sys
from app_info import DATA_DIRECTORY


def user_data_root():
    local = os.environ.get('LOCALAPPDATA')
    if not local or not Path(local).is_absolute():
        raise OSError('LOCALAPPDATA must name an absolute user-owned data folder')
    return Path(local) / DATA_DIRECTORY


def default_worker_directory():
    if os.name != 'nt':
        return None
    root = user_data_root() / 'workers'
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_directory(*, create=True):
    if os.name == 'nt' and getattr(sys, 'frozen', False):
        root = user_data_root() / 'Saves'
        if create:
            root.mkdir(parents=True, exist_ok=True)
        return root
    return Path.cwd()


def save_search_directories():
    try:
        roots = [save_directory(create=False)]
    except OSError:
        roots = []
    cwd = Path.cwd()
    if cwd not in roots:
        roots.append(cwd)  # Legacy portable saves are read, never moved/repaired.
    return roots
