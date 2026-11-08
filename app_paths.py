"""Portable runtime storage, rooted at the executable, never the launch cwd.

No ACL repair, administrator request, hidden TEMP/LocalAppData fallback or
writes into PyInstaller's _internal assets. Source saves retain cwd behavior.
"""
import os
from pathlib import Path
import sys


def portable_root():
    """Frozen: folder containing the exe. Source: folder containing this file."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def default_worker_directory():
    if os.name != 'nt':
        return None
    root = portable_root() / 'workers'
    root.mkdir(exist_ok=True)
    return root


def save_directory(*, create=True):
    # The existing exe folder is the save root; never create an alternative.
    return portable_root() if getattr(sys, 'frozen', False) else Path.cwd()


def save_search_directories():
    roots = [save_directory(create=False)]
    cwd = Path.cwd()
    if cwd not in roots:
        roots.append(cwd)  # Read-only legacy discovery; no migration or fallback.
    return roots
