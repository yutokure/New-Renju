"""Predeclare a legal random-local opening sample without consulting engines."""
import json
from pathlib import Path
import random
from board import Board


def main():
    rng=random.Random(202611081245)
    rows=[]
    while len(rows)<16:
        board=Board()
        history=[]
        target=5+2*(len(rows)%3)
        while len(history)<target:
            count=len(history)
            side=1+count%2
            candidates=[(r,c) for r in range(4,11) for c in range(4,11)
                        if board.is_valid_move(r,c,side,count)
                        and (count==0 or any(max(abs(r-a),abs(c-b))<=2 for a,b in history))]
            if not candidates:
                break
            move=rng.choice(candidates)
            board.place_stone(*move,side,count)
            history.append(move)
            if board.check_win(side)[0]:
                break
        if len(history)==target and not any(board.check_win(side)[0] for side in (1,2)):
            if history not in rows:
                rows.append(history)
    path=Path('benchmarks/results/hard-predeclared-openings.json')
    if path.exists():
        raise RuntimeError('Do not overwrite a predeclared opening sample')
    path.write_text(json.dumps(rows,indent=2),encoding='utf-8')
    print(f'Predeclared {len(rows)} engine-independent legal openings (length5/7/9)')


if __name__=='__main__':
    main()
