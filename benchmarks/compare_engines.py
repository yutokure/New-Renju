"""Serial, paired-color tactical and match measurements, never parallel games.

Run from repository root. Historical engine snapshots are extracted from Git
into a temporary directory; all engines use the SAME current Board referee.
"""
import argparse
import contextlib
import io
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import statistics
import subprocess
import tempfile
import time
import types

import numpy as np
from ai import AIHard
from board import Board, BLACK, WHITE
from renju_rules import Rules
from very_hard import AIVeryHard
from tests.positions import hard_cases


def historical_ai(ref):
    # Git writes to a file, not a captured child pipe (Windows sandbox safe).
    with tempfile.TemporaryFile(mode='w+b') as output:
        subprocess.run(['git', 'show', ref+':ai.py'], stdout=output, check=True)
        output.seek(0)
        source = output.read().decode('utf-8-sig')
    module = types.ModuleType('historical_ai_'+ref)
    exec(compile(source, '<Git '+ref+' ai.py>', 'exec'), module.__dict__)
    return module.AIHard


def wilson(wins, total):
    if not total:
        return [0.0, 1.0]
    z = 1.959963984540054
    p = wins/total
    d = 1+z*z/total
    center = (p+z*z/(2*total))/d
    half = z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/d
    return [max(0,center-half), min(1,center+half)]


def make_ai(name, player, budget, legacy, hard_a):
    cls = {'old_hard': legacy, 'hard_a': hard_a, 'hard': AIHard, 'very_hard': AIVeryHard}[name]
    return cls(player, time_limit_sec=budget, **({'depth': 2} if name != 'very_hard' else {}))


def environment():
    return {'source_sha256': {name:hashlib.sha256(Path(name).read_bytes()).hexdigest()
                              for name in ('ai.py','board.py','renju_rules.py','tactics.py','very_hard.py')},
            'python': platform.python_version(), 'numpy': np.__version__,
            'platform': platform.platform(), 'processor': platform.processor()}


def tactics(output, budget, legacy, hard_a):
    proposals = json.loads(Path('docs/tactical-proposals.json').read_text(encoding='utf-8'))
    cases = []
    for fixture in proposals['tactical_fixtures']:
        # Positive roots have hand-certified accepted moves. Negatives require
        # solver status checks, not treating one root's failure as global loss.
        if fixture['expected'] != 'nominated_root_forced_win':
            continue
        board = Board()
        for color, key in ((BLACK,'black'), (WHITE,'white')):
            for r,c in fixture[key]:
                board.grid[r,c] = color
        count = max(4, len(fixture['black'])+len(fixture['white']))
        player = BLACK if fixture['attacker']=='black' else WHITE
        cases.append((fixture['id'], board, player, count, {tuple(fixture['root'])}))
    cases += [x for x in hard_cases() if x[4] is not None]
    rows = []
    for name in ('old_hard','hard_a','hard','very_hard'):
        for case, board, player, count, accepted in cases:
            random.seed(42)
            np.random.seed(42)
            engine = make_ai(name, player, budget, legacy, hard_a)
            grid,last = board.grid.copy(),board.last_move
            start = time.perf_counter()
            with contextlib.redirect_stdout(io.StringIO()):
                move = engine.find_move(board,count)
            elapsed = time.perf_counter()-start
            rows.append({'engine':name,'case':case,'move':list(map(int,move)) if move is not None else None,
                         'accepted_nominated_move':bool(move in accepted),
                         'legal':bool(move is not None and board.is_valid_move(*move,player,count)),
                         'nonmutating':bool(np.array_equal(grid,board.grid) and last==board.last_move),
                         'seconds':elapsed,'completed_depth':getattr(engine,'completed_depth',None),
                         'proof_status':getattr(engine,'proof_status',None),
                         'nodes':getattr(engine,'nodes',None)})
    result = {'kind':'tactical_nominated_roots','budget':budget,'environment':environment(),
              'warning':'Accepted nominated roots are sufficient not exhaustive best-move labels; alternate sound wins can be marked false. Negative solver certificate suite separate.', 'rows':rows}
    Path(output).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(rows,indent=2))


def openings():
    # All legal legacy first three; color swaps use the identical stone layout.
    for third in ((6,8),(8,8),(5,7),(7,8),(5,9),(9,7),(8,6),(6,6)):
        yield [(7,7),(6,7),third]


def matches(output, games, budget, normal, opponent, max_moves, legacy, hard_a, challenger='very_hard'):
    rows=[]
    path=Path(output)
    def save():
        decisive=[r for r in rows if r['outcome'] in ('win','loss')]
        w=sum(r['outcome']=='win' for r in decisive)
        d=sum(r['outcome']=='draw' for r in rows)
        data={'kind':'paired_color_matches','environment':environment(),'equal_budget':not normal,
              'budget':budget,'normal_defaults':normal,'opponent':opponent,'challenger':challenger,'max_moves':max_moves,
              'rules':'current shared formal core; historical source uses current Board, not old referee',
              'rows':rows,'summary':{'games':len(rows),'wins':w,'losses':len(decisive)-w,'draws':d,
                                    'censored':sum(r['outcome']=='censored' for r in rows),
                                    'errors':sum(r['outcome']=='error' for r in rows),
                                    'decisive_win_fraction':w/len(decisive) if decisive else None,
                                    'wilson95_decisive':wilson(w,len(decisive)),
                                    'caution':'Wilson treats games independent; color-paired correlated games/openings reduce effective sample size; not a release strength PASS by itself.'}}
        path.write_text(json.dumps(data,indent=2),encoding='utf-8')
    opening_list=list(openings())
    for game_id in range(games):
        opening=opening_list[(game_id//2)%len(opening_list)]
        vh_color=BLACK if game_id%2==0 else WHITE
        board=Board()
        for count,move in enumerate(opening):
            assert board.place_stone(*move,1+count%2,count)
        history=list(opening)
        engines={}
        for player in (BLACK,WHITE):
            name=challenger if player==vh_color else opponent
            limit=(5.0 if name=='very_hard' else 1.5) if normal else budget
            engines[player]=make_ai(name,player,limit,legacy,hard_a)
        times={BLACK:[],WHITE:[]}
        result={'id':game_id,'pair':game_id//2,'very_hard_color':vh_color,'opening':opening,
                'outcome':'censored','winner':None,'moves':history,'errors':[]}
        start=time.perf_counter()
        while len(history)<max_moves:
            count=len(history)
            player=1+count%2
            engine=engines[player]
            random.seed(20261108+count)
            np.random.seed(20261108+count)
            t=time.perf_counter()
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    move=engine.find_move(board,count)
                times[player].append(time.perf_counter()-t)
                if move is None:
                    if not board.get_empty_cells():
                        result['outcome']='draw'
                    else:
                        result['outcome']='error'
                        result['errors'].append('no_move_with_empty_cells')
                    break
                move=tuple(map(int,move))
                if not board.place_stone(*move,player,count):
                    result['outcome']='error'
                    result['errors'].append('illegal_move '+str(move))
                    break
                history.append(move)
                if board.check_win(player)[0]:
                    result['winner']=player
                    result['outcome']='win' if player==vh_color else 'loss'
                    break
                if not board.get_empty_cells():
                    result['outcome']='draw'
                    break
            except Exception as exc:
                result['outcome']='error'
                result['errors'].append(repr(exc))
                break
        result['seconds']=time.perf_counter()-start
        result['time_by_color']={str(p):{'max':max(v,default=0),'mean':statistics.mean(v) if v else 0,'total':sum(v)} for p,v in times.items()}
        rows.append(result)
        save()
        print(f"game {game_id+1}/{games}: {challenger} color{vh_color} {result['outcome']} moves={len(history)} seconds={result['seconds']:.2f}",flush=True)
    save()


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--output',required=True)
    p.add_argument('--mode',choices=['tactics','matches'],default='tactics')
    p.add_argument('--budget',type=float,default=1.5)
    p.add_argument('--games',type=int,default=16)
    p.add_argument('--normal',action='store_true')
    p.add_argument('--opponent',choices=['old_hard','hard_a','hard'],default='hard')
    p.add_argument('--challenger',choices=['very_hard','hard','hard_a'],default='very_hard')
    p.add_argument('--max-moves',type=int,default=100)
    args=p.parse_args()
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    legacy=historical_ai('d4b2edd')
    hard_a=historical_ai('bdfcef2')
    if args.mode=='tactics':
        tactics(args.output,args.budget,legacy,hard_a)
    else:
        matches(args.output,args.games,args.budget,args.normal,args.opponent,args.max_moves,legacy,hard_a,args.challenger)
