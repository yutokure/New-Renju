"""Isolated, cancellable AI work; never imports or operates the Pygame UI.

The small JSON file protocol deliberately avoids multiprocessing queues/pipes.
It also works with Windows spawn and permits hard termination of runaway code.
"""
import argparse
import json
import os
from pathlib import Path
import time
import traceback


class FileCancellation:
    def __init__(self, path):
        self.path = Path(path)

    def is_set(self):
        return self.path.exists()


def _plain(value):
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if hasattr(value, 'item'):
        return value.item()
    return value


def run_request(request_path):
    request_path = Path(request_path)
    request = json.loads(request_path.read_text(encoding='utf-8'))
    result_path = request_path.with_name('result.json')
    cancel = FileCancellation(request_path.with_name('cancel'))
    started = time.perf_counter()
    latest = {'move': None, 'completed_depth': 0, 'phase': 'starting'}

    def publish(update, done=False):
        latest.update(_plain(update))
        latest.update(token=request['token'], done=done,
                      elapsed=time.perf_counter() - started)
        temp = result_path.with_suffix('.tmp')
        temp.write_text(json.dumps(latest, allow_nan=False), encoding='utf-8')
        # A reader may briefly hold the destination on Windows. Never let a
        # transient telemetry sharing violation abort otherwise valid search.
        try:
            os.replace(temp, result_path)
        except PermissionError:
            pass

    try:
        from board import Board, EMPTY
        from ai import create_ai, AIHard
        import numpy as np
        data = request['board']
        board = Board(data['size'], data['win_length'])
        board.grid = np.array(data['grid'], dtype=int)
        board.last_move = tuple(data['last_move']) if data['last_move'] is not None else None
        ai = create_ai(request['difficulty'], request['player'])
        if hasattr(ai, 'time_limit'):
            ai.time_limit = request['budget']
        if request['kind'] in ('analysis', 'legality'):
            # Both exhaustive forbidden overlays and research run detached.
            # Recursive rule work receives the same deadline/cancel callback.
            from renju_rules import Rules
            rules = Rules(board.size, board.win_length)
            flat = rules.flatten(board.grid)
            evaluator = AIHard(request['player'], time_limit_sec=request['budget'])
            scores, invalid = [], []
            checked = 0
            deadline = time.perf_counter() + request['budget']
            class Interrupted(Exception):
                pass
            def check():
                if cancel.is_set() or time.perf_counter() >= deadline:
                    raise Interrupted()
            empty = board.get_empty_cells()
            try:
                for r, c in empty:
                    check()
                    legal = rules.is_legal(flat, int(r*board.size+c), request['player'], request['move_count'], check)
                    checked += 1
                    if not legal:
                        invalid.append([int(r), int(c)])
                        continue
                    if request['kind'] == 'analysis':
                        with board.temporary_move(r, c, request['player']):
                            score = evaluator._evaluate_board(board)
                        scores.append([int(r), int(c), float(score)])
            except Interrupted:
                pass
            publish({'scores': scores, 'invalid_cells': invalid,
                     'phase': 'Hard static estimate' if request['kind'] == 'analysis' else 'legality overlay',
                     'legality_complete': checked == len(empty), 'partial': checked < len(empty)}, done=True)
        else:
            # Publish a verified legal move before expensive Easy/Normal or
            # engine initialization work. Keep fallback deterministic/local.
            center = board.size // 2
            cells = sorted(board.get_empty_cells(), key=lambda p: (abs(p[0]-center)+abs(p[1]-center), p[0], p[1]))
            for r, c in cells:
                if cancel.is_set():
                    return
                if board.is_valid_move(r, c, request['player'], request['move_count']):
                    publish({'move': [int(r), int(c)], 'phase': 'legal fallback'})
                    break
            if cancel.is_set():
                return
            if isinstance(ai, AIHard) or request['difficulty'] == 'very_hard':
                move = ai.find_move(board, request['move_count'], cancel_event=cancel,
                                    progress_callback=publish)
            else:
                move = ai.find_move(board, request['move_count'])
            if cancel.is_set():
                return
            if move is not None and not board.is_valid_move(*move, request['player'], request['move_count']):
                raise ValueError('AI returned an illegal move')
            final = {'move': move, 'phase': 'complete'}
            if hasattr(ai, 'proof_status'):
                final['proof_status'] = ai.proof_status
            publish(final, done=True)
    except Exception:
        publish({'error': traceback.format_exc(), 'phase': 'error'}, done=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('request')
    run_request(parser.parse_args().request)
