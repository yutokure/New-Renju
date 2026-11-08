"""Local-only worker wall/RSS/cancellation smoke (run after match benchmarks)."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import time
from ai_async import AsyncAI
from board import BLACK
from tests.positions import hard_cases


class ProcessMemoryCounters(ctypes.Structure):
    _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD),
              ('PeakWorkingSetSize',ctypes.c_size_t),('WorkingSetSize',ctypes.c_size_t),
              ('QuotaPeakPagedPoolUsage',ctypes.c_size_t),('QuotaPagedPoolUsage',ctypes.c_size_t),
              ('QuotaPeakNonPagedPoolUsage',ctypes.c_size_t),('QuotaNonPagedPoolUsage',ctypes.c_size_t),
              ('PagefileUsage',ctypes.c_size_t),('PeakPagefileUsage',ctypes.c_size_t)]


def probe(output, budget=5):
    if os.name!='nt':
        raise RuntimeError('This native RSS probe requires Windows')
    from ctypes import WinDLL
    get=WinDLL('psapi',use_last_error=True).GetProcessMemoryInfo
    get.argtypes=[wintypes.HANDLE,ctypes.POINTER(ProcessMemoryCounters),wintypes.DWORD]
    get.restype=wintypes.BOOL
    _,board,player,count,_=hard_cases()[-2]
    runner=AsyncAI()
    peak_rss=peak_commit=0
    ticks=0
    start=time.perf_counter()
    try:
        runner.start(board,player,count,'very_hard',budget=budget)
        task=runner.task
        metadata=getattr(task,'budget',budget)
        while runner.busy:
            counters=ProcessMemoryCounters()
            counters.cb=ctypes.sizeof(counters)
            if get(wintypes.HANDLE(int(task.process._handle)),ctypes.byref(counters),counters.cb):
                peak_rss=max(peak_rss,counters.PeakWorkingSetSize)
                peak_commit=max(peak_commit,counters.PeakPagefileUsage)
            result=runner.poll(board,player,count)
            ticks+=1
            # Sampling cadence only, not busy-polling an external harness job.
            if result is None:
                time.sleep(.01)
        answer={'budget':budget,'wall_seconds':time.perf_counter()-start,
                'peak_worker_rss_bytes':peak_rss,'peak_worker_commit_bytes':peak_commit,
                'samples':ticks,'result':result,'platform':'Windows native GetProcessMemoryInfo',
                'limits':runner.last_info.get('resource_limits'),
                'note':'One quiet15x15 position; sampled OS peak counters, not maximum over all possible games.'}
    finally:
        runner.close()
    Path(output).write_text(json.dumps(answer,indent=2),encoding='utf-8')
    print(json.dumps(answer,indent=2))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    parser.add_argument('--budget',type=float,default=5)
    args=parser.parse_args()
    probe(args.output,args.budget)
