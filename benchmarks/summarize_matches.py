"""Summarize raw game and opening-pair outcomes without hiding dependence."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
from benchmarks.compare_engines import wilson


def summarize(path):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    rows=data['rows']
    groups=defaultdict(list)
    for row in rows:
        # Repeated identical openings are NOT new independent opening samples.
        groups[tuple(tuple(p) for p in row['opening'])].append(row)
    pair_scores=[]
    for opening, games in groups.items():
        wins=sum(r['outcome']=='win' for r in games)
        losses=sum(r['outcome']=='loss' for r in games)
        draws=sum(r['outcome']=='draw' for r in games)
        known=wins+losses+draws
        score=(wins+.5*draws)/known if known else None
        pair_scores.append({'opening':opening,'games':len(games),'wins':wins,'losses':losses,
                            'draws':draws,'score':score})
    positive=sum(p['score'] is not None and p['score']>.5 for p in pair_scores)
    negative=sum(p['score'] is not None and p['score']<.5 for p in pair_scores)
    tied=sum(p['score']==.5 for p in pair_scores)
    timed=[]
    for row in rows:
        for color, values in row['time_by_color'].items():
            limit=5.0 if int(color)==row['very_hard_color'] and data['normal_defaults'] else (1.5 if data['normal_defaults'] else data['budget'])
            if values['max']>limit+.1:
                timed.append({'id':row['id'],'color':color,'max':values['max'],'limit':limit})
    return {'file':str(path),'raw_summary':data['summary'],'unique_openings':len(groups),
            'positive_opening_groups':positive,'negative_opening_groups':negative,'tied_opening_groups':tied,
            'wilson95_positive_nontied_opening_fraction':wilson(positive,positive+negative),
            'groups':pair_scores,'overshoot_over_100ms':timed,
            'caution':'Both confidence intervals are descriptive. Openings are purposively selected, small and correlated; repeats do not create independent samples or universal Elo/strength claims.'}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('files',nargs='+')
    p.add_argument('--output',required=True)
    args=p.parse_args()
    rows=[summarize(path) for path in args.files]
    Path(args.output).write_text(json.dumps(rows,indent=2),encoding='utf-8')
    print(json.dumps(rows,indent=2))
