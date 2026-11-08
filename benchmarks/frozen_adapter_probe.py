"""Exercise the actual adapter against a frozen exe in an explicit local root.

This does not certify the default system TEMP or the complete packaged GUI.
"""
import argparse
import json
from pathlib import Path
import time
from types import SimpleNamespace
from unittest.mock import patch
import ai_async
from ai_async import AsyncAI
from board import Board,BLACK,WHITE


def position():
    board=Board()
    for index,(row,col) in enumerate(((7,7),(6,7),(8,8),(6,6))):
        assert board.place_stone(row,col,BLACK if index%2==0 else WHITE,index)
    return board


def run(exe,root):
    exe=Path(exe).resolve()
    root=Path(root).resolve()
    root.mkdir(parents=True,exist_ok=True)
    rows=[]
    with patch.object(ai_async,'sys',SimpleNamespace(executable=str(exe),frozen=True)):
        for difficulty in ('easy','normal','hard','very_hard'):
            board=position()
            runner=AsyncAI(worker_directory=root)
            try:
                runner.start(board,BLACK,4,difficulty,budget=1)
                task=runner.task
                start=time.perf_counter()
                result=None
                while result is None and time.perf_counter()-start<5:
                    result=runner.poll(board,BLACK,4)
                    if result is None:
                        time.sleep(.01)
                assert result is not None and result.get('move') and not result.get('error'),result
                assert board.is_valid_move(*result['move'],BLACK,4)
                rows.append({'kind':'move','difficulty':difficulty,'wall_seconds':time.perf_counter()-start,
                             'result':result})
            finally:
                runner.close()
            assert task.resources.closed and not Path(task.directory.name).exists() and not runner.retired
        board=Board()
        runner=AsyncAI(worker_directory=root)
        try:
            runner.start(board,BLACK,0,'very_hard',kind='validate',candidate=(7,7),budget=1)
            task=runner.task
            end=time.perf_counter()+5
            result=None
            while result is None and time.perf_counter()<end:
                result=runner.poll(board,BLACK,0)
                if result is None:
                    time.sleep(.01)
            assert result and result.get('adjudication')=='legal' and result.get('validation_complete'),result
            rows.append({'kind':'validate','result':result})
        finally:
            runner.close()
        assert task.resources.closed and not Path(task.directory.name).exists() and not runner.retired
        board=position()
        runner=AsyncAI(worker_directory=root)
        try:
            runner.start(board,BLACK,4,'very_hard',budget=5)
            task=runner.task
            before=time.perf_counter()
            runner.cancel()
            cancel_seconds=time.perf_counter()-before
        finally:
            runner.close()
        assert task.process.poll() is not None and task.resources.closed and not Path(task.directory.name).exists() and not runner.retired
        rows.append({'kind':'cancel','cancel_seconds':cancel_seconds,'child_exited':True,
                     'resources_closed':True,'temporary_directory_removed':True,'no_retired_children':True})
    Path('benchmarks/results/frozen-adapter-explicit-root.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    print(json.dumps(rows,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('exe')
    p.add_argument('--request-root',required=True)
    args=p.parse_args()
    run(args.exe,args.request_root)
