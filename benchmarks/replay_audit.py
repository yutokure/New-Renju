"""Independent recorded-game geometry audit using the shared legal referee."""
import argparse
import json
from pathlib import Path
from board import Board


def geometric_win(board, move, player):
    n=board.size
    r,c=move
    for dr,dc in ((0,1),(1,0),(1,1),(1,-1)):
        count=1
        for sign in (-1,1):
            rr,cc=r+sign*dr,c+sign*dc
            while 0<=rr<n and 0<=cc<n and board.grid[rr,cc]==player:
                count+=1
                rr,cc=rr+sign*dr,cc+sign*dc
        if count==5 or (player==2 and count>=5):
            return True
    return False


def audit(path):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    checked=0
    for game in data['rows']:
        board=Board()
        first_winner=None
        for count, move in enumerate(game['moves']):
            assert first_winner is None,(path,game['id'],'played beyond terminal',count)
            player=1+count%2
            assert board.place_stone(*move,player,count),(path,game['id'],'illegal',count,move)
            if geometric_win(board,move,player):
                first_winner=player
            checked+=1
        assert first_winner==game['winner'],(path,game['id'],'winner mismatch')
    return {'file':str(path),'games':len(data['rows']),'legal_placements_replayed':checked,
            'no_postterminal_moves':True,'independent_winner_geometry_matches':True,
            'note':'Legality uses shared separately reviewed Rules; terminal geometry is independently coded.'}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('files',nargs='+')
    p.add_argument('--output',required=True)
    a=p.parse_args()
    rows=[audit(x) for x in a.files]
    Path(a.output).write_text(json.dumps(rows,indent=2),encoding='utf-8')
    print(json.dumps(rows,indent=2))
