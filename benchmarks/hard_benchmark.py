"""Serial baseline/after runner. Run: python -m benchmarks.hard_benchmark --output ...

No performance thresholds in CI. Raw environment, seeds, call counts and timings
are retained; a legal tactical precheck is not confused with completed depth.
"""
import argparse
import contextlib
import cProfile
import io
import json
import platform
import random
import statistics
import time
from pathlib import Path
import numpy as np
from ai import AIHard
from tests.positions import hard_cases


def run(output, repeats=3, limit=1.5, profile=None):
    rows = []
    for repeat in range(repeats):
        for name, board, player, count, expected in hard_cases():
            random.seed(20261107)
            np.random.seed(20261107)
            ai = AIHard(player, depth=2, time_limit_sec=limit)
            stats = {'nodes': 0, 'evaluations': 0, 'legality_checks': 0}
            for obj, attr, key in ((ai, '_minimax', 'nodes'), (ai, '_evaluate_board', 'evaluations'), (board, 'is_valid_move', 'legality_checks')):
                original = getattr(obj, attr)
                def wrapped(*args, _fn=original, _key=key, **kwargs):
                    stats[_key] += 1
                    return _fn(*args, **kwargs)
                setattr(obj, attr, wrapped)
            grid, last = board.grid.copy(), board.last_move
            started = time.perf_counter()
            with contextlib.redirect_stdout(io.StringIO()):
                move = ai.find_move(board, count)
            elapsed = time.perf_counter() - started
            rows.append(dict(case=name, repeat=repeat, seconds=elapsed,
                             move=[int(x) for x in move] if move else None,
                             legal=bool(move is not None and board.is_valid_move(*move, player, count)),
                             correct=bool(move in expected) if expected else None,
                             nonmutating=bool(np.array_equal(grid, board.grid) and board.last_move == last),
                             completed_depth=getattr(ai, 'completed_depth', None), **stats))
    result = dict(environment=dict(python=platform.python_version(), numpy=np.__version__, platform=platform.platform(), processor=platform.processor()),
                  seed=20261107, depth=2, limit=limit, repeats=repeats, rows=rows,
                  median_seconds={name: statistics.median(r['seconds'] for r in rows if r['case'] == name) for name, *_ in hard_cases()})
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result['median_seconds'], indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True)
    p.add_argument('--repeats', type=int, default=3)
    p.add_argument('--limit', type=float, default=1.5)
    p.add_argument('--profile')
    args = p.parse_args()
    if args.profile:
        profiler = cProfile.Profile()
        profiler.runcall(run, args.output, args.repeats, args.limit)
        profiler.dump_stats(args.profile)
    else:
        run(args.output, args.repeats, args.limit)
