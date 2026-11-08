"""Controlled real Windows Job Object allocation test on one disposable child."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from worker_limits import ProcessBudget


def main():
    if os.name!='nt':
        raise RuntimeError('Windows-only native cap test')
    with tempfile.TemporaryDirectory(prefix='renju-limit-test-') as temp:
        root=Path(temp)
        child=root/'allocation_child.py'
        child.write_text('''from pathlib import Path
import sys,time
root=Path(sys.argv[1])
while not (root/'go').exists():
    time.sleep(.005)
chunks=[]
try:
    for i in range(24):
        chunks.append(bytearray(8*1024*1024))
    (root/'outcome').write_text('allocation_unexpectedly_succeeded')
except MemoryError:
    (root/'outcome').write_text('MemoryError_as_expected')
''',encoding='utf-8')
        proc=subprocess.Popen([sys.executable,'-B',str(child),str(root)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        resources=None
        try:
            resources=ProcessBudget(proc,64)
            metadata=resources.metadata
            (root/'go').touch()
            proc.wait(timeout=5)
            outcome=(root/'outcome').read_text() if (root/'outcome').exists() else 'native_exit_before_marker'
            result={'limit_mb':64,'attempted_allocation_mb':192,'exit_code':proc.returncode,
                    'outcome':outcome,'metadata':metadata,'parent_survived':True}
            assert outcome=='MemoryError_as_expected',result
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=2)
            if resources:
                resources.close()
        Path('benchmarks/results/native-memory-limit-test.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
