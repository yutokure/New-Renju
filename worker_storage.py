"""Bounded worker directories inheriting the portable folder's existing ACL.

Python 3.12 tempfile.mkdtemp uses mkdir(mode=0700) and retries PermissionError
many times on Windows when access(parent) succeeds. That can block the GUI and
apply a restrictive child DACL incompatible with inherited execution tokens.
Use the existing portable parent's ACL, never modify it or broaden ACL entries.
"""
from pathlib import Path
import shutil
import tempfile
import uuid


class WorkerDirectory:
    def __init__(self, *, root=None, prefix='renju-ai-'):
        parent = Path(root) if root is not None else Path(tempfile.gettempdir())
        # Collisions are negligible but bounded; permission errors propagate now.
        for _ in range(3):
            child = parent / (prefix + uuid.uuid4().hex)
            try:
                child.mkdir(mode=0o777)  # Windows: normal inherited ACL, no ACL edits.
            except FileExistsError:
                continue
            self.name = str(child.resolve())
            return
        raise FileExistsError('Cannot allocate a unique worker directory')

    def cleanup(self):
        path = Path(self.name)
        if path.exists():
            shutil.rmtree(path)
