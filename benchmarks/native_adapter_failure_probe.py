"""Disposable real allocation failure through the adapter lifecycle, locally."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch
from types import SimpleNamespace
from ai_async import AsyncAI
from board import Board,BLACK


def main():
    if os.name!='nt':
        raise RuntimeError('Windows-only')
    original=subprocess.Popen
    with tempfile.TemporaryDirectory(prefix='renju-native-failure-') as temp:
        root=Path(temp)
        child=root/'child.py'
        child.write_text('''import time
# Parent assigns job immediately; wait briefly before controlled allocation.
time.sleep(.25)
chunks=[]
try:
    for _ in range(32):
        chunks.append(bytearray(8*1024*1024))
except MemoryError:
    raise SystemExit(77)
raise SystemExit(78)
''',encoding='utf-8')
        def launch(command,**kwargs):
            return original([sys.executable,'-B',str(child)],**kwargs)
        runner=AsyncAI(startup_grace=1,memory_limit_mb=64)
        board=Board()
        task=None
        try:
            proxy = SimpleNamespace(Popen=launch, DEVNULL=subprocess.DEVNULL,
                                    CREATE_NO_WINDOW=getattr(subprocess,'CREATE_NO_WINDOW',0),
                                    TimeoutExpired=subprocess.TimeoutExpired)
            with patch('ai_async.subprocess',proxy):
                runner.start(board,BLACK,0,'hard',budget=1)
            task=runner.task
            path=Path(task.directory.name)
            end=time.perf_counter()+4
            result=None
            while result is None and time.perf_counter()<end:
                result=runner.poll(board,BLACK,0)
                if result is None:
                    time.sleep(.01)
            assert result is not None and result.get('error'),result
        finally:
            runner.close()
        output={'child_exit':task.process.returncode,'result':result,
                'resources_closed':task.resources.closed,'temporary_directory_removed':not path.exists(),
                'no_retired_children':not runner.retired,'parent_survived':True}
        assert output['child_exit']==77 and output['resources_closed'] and output['temporary_directory_removed'],output
        Path('benchmarks/results/native-adapter-memory-failure.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
        print(json.dumps(output,indent=2))


if __name__=='__main__':
    main()
