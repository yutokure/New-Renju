"""Small exact custom-connect-N game tree, independent of VH evaluation/beam.

This is a finite full-width oracle, not an official Renju oracle.
"""
from functools import lru_cache
import random
import pytest
from renju_rules import Rules
from very_hard import AIVeryHard, Position, MATE
from tests.positions import position


def terminal(cells,size,target):
    winners=set()
    for r in range(size):
        for c in range(size):
            p=cells[r*size+c]
            if not p:
                continue
            for dr,dc in ((0,1),(1,0),(1,1),(1,-1)):
                if all(0<=r+j*dr<size and 0<=c+j*dc<size and cells[(r+j*dr)*size+c+j*dc]==p for j in range(target)):
                    winners.add(p)
    return winners


@lru_cache(maxsize=10000)
def exact_value(cells,player):
    winners=terminal(cells,3,3)
    if winners:
        return 1 if player in winners else -1
    empty=[i for i,p in enumerate(cells) if not p]
    if not empty:
        return 0
    values=[]
    for i in empty:
        child=list(cells)
        child[i]=player
        values.append(-exact_value(tuple(child),3-player))
    return max(values)


@pytest.mark.parametrize('seed',range(12))
def test_small_full_width_tactical_value_matches_exact_oracle(seed):
    rng=random.Random(seed)
    while True:
        order=rng.sample(range(9),6)
        cells=[0]*9
        for j,i in enumerate(order):
            cells[i]=1+j%2
        if not terminal(cells,3,3):
            break
    ai=AIVeryHard(1,time_limit_sec=1,tactical_fraction=0,candidate_limit=9)
    ai.pos=Position(cells,3,3)
    ai.rules=Rules(3,3,opening=False)
    ai.started=0
    ai.deadline=float('inf')
    ai.active_cancel=None
    ai.generation=1
    ai.nodes=ai.evaluations=0
    # Last move was white; the position is nonterminal by independent check.
    score=ai._negamax(3,-MATE,MATE,1,6,order[-1],0)
    oracle=exact_value(tuple(cells),1)
    actual=1 if score>MATE//2 else -1 if score<-MATE//2 else 0
    assert actual==oracle
    assert ai.pos.cells==cells
