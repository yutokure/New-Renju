"""Verify KILL_ON_JOB_CLOSE with disposable controller and child only."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def main():
    if os.name!='nt':
        raise RuntimeError('Windows-only')
    with tempfile.TemporaryDirectory(prefix='renju-parent-test-') as tmp:
        root=Path(tmp)
        script=root/'controller.py'
        script.write_text('''import os,sys,subprocess,time
from pathlib import Path
from worker_limits import ProcessBudget
root=Path(sys.argv[1])
child=subprocess.Popen([sys.executable,'-B','-c','import time; time.sleep(30)'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
cap=ProcessBudget(child,64)
(root/'pid').write_text(str(child.pid))
while not (root/'exit').exists():
    time.sleep(.01)
os._exit(0)
''',encoding='utf-8')
        env=os.environ.copy()
        env['PYTHONPATH']=str(Path.cwd())
        parent=subprocess.Popen([sys.executable,'-B',str(script),str(root)],env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        handle=None
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        kernel.OpenProcess.restype=wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
        kernel.WaitForSingleObject.restype=wintypes.DWORD
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        kernel.CloseHandle.restype=wintypes.BOOL
        try:
            end=time.perf_counter()+5
            while not (root/'pid').exists() and time.perf_counter()<end:
                if parent.poll() is not None:
                    raise RuntimeError('controller failed before assigning job')
                time.sleep(.01)
            pid=int((root/'pid').read_text())
            handle=kernel.OpenProcess(0x00100000,False,pid)  # SYNCHRONIZE only
            if not handle:
                raise ctypes.WinError(ctypes.get_last_error())
            (root/'exit').touch()
            parent.wait(timeout=3)
            state=kernel.WaitForSingleObject(handle,3000)
            result={'controller_exit':parent.returncode,'child_pid':pid,
                    'child_signaled_after_parent_exit':state==0,'parent_survived':True}
            assert state==0,result
        finally:
            if parent.poll() is None:
                parent.kill()
                parent.wait(timeout=2)
            if handle:
                kernel.CloseHandle(handle)
        Path('benchmarks/results/native-parent-death-test.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
