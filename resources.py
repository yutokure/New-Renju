"""Read-only bundled assets resolve independently from writable save directory."""
from pathlib import Path
import sys


def asset_path(name):
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    return str(root / name)
