"""Launch the frozen worker protocol against all four difficulty factories."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from worker_limits import ProcessBudget


def main(exe, request_root=None):
    exe=Path(exe).resolve()
    if request_root is not None:
        request_root=Path(request_root).resolve()
        request_root.mkdir(parents=True,exist_ok=True)
    rows=[]
    for difficulty in ('easy','normal','hard','very_hard'):
        with tempfile.TemporaryDirectory(prefix='renju-frozen-',dir=request_root) as tmp:
            root=Path(tmp)
            token='frozen-'+difficulty
            request={'token':token,'kind':'move','difficulty':difficulty,'player':1,'move_count':0,'budget':.2,
                     'board':{'size':15,'win_length':5,'grid':[[0]*15 for _ in range(15)],'last_move':None}}
            path=root/'request.json'
            path.write_text(json.dumps(request))
            env=os.environ.copy()
            env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
            start=time.perf_counter()
            proc=subprocess.Popen([str(exe),'--ai-worker',str(path)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=env)
            cap=None
            try:
                cap=ProcessBudget(proc,1024)
                print(f'testing frozen {difficulty} pid={proc.pid}',flush=True)
                try:
                    proc.wait(timeout=20)
                except subprocess.TimeoutExpired as exc:
                    detail=(root/'result.json').read_text() if (root/'result.json').exists() else 'no result'
                    raise RuntimeError(f'Frozen {difficulty} timeout: {detail}') from exc
                if not (root/'result.json').exists():
                    raise RuntimeError(f'Frozen {difficulty} exited {proc.returncode} without result (cap={cap.metadata})')
                result=json.loads((root/'result.json').read_text())
                row={'difficulty':difficulty,'exit_code':proc.returncode,'wall_seconds':time.perf_counter()-start,'result':result}
                assert result['done'] and result['move']==[7,7] and not result.get('error'),row
                rows.append(row)
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=2)
                if cap:
                    cap.close()
    output=Path('benchmarks/results/frozen-worker-smoke-explicit-root.json' if request_root else 'benchmarks/results/frozen-worker-smoke.json')
    output.write_text(json.dumps(rows,indent=2),encoding='utf-8')
    print(json.dumps(rows,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('exe')
    p.add_argument('--request-root')
    args=p.parse_args()
    main(args.exe,args.request_root)
