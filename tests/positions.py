"""Hand-constructed fixtures; zero-based coordinates, not AI-generated answers."""
from board import Board, BLACK, WHITE


def position(black=(), white=(), size=15, win_length=5, last=None):
    board = Board(size, win_length)
    for player, stones in ((BLACK, black), (WHITE, white)):
        for r, c in stones:
            board.grid[r, c] = player
    board.last_move = last
    return board


def hard_cases():
    return [
        ("opening", position(), BLACK, 0, {(7, 7)}),
        ("white_win", position(black=[(7, 3)], white=[(7, c) for c in range(4, 8)]), WHITE, 9, {(7, 8)}),
        ("black_win", position(black=[(7, c) for c in range(4, 8)], white=[(7, 3)]), BLACK, 8, {(7, 8)}),
        ("forced_block", position(black=[(7, c) for c in range(4, 8)], white=[(7, 3)]), WHITE, 9, {(7, 8)}),
        ("quiet_opening", position(black=[(7, 7), (8, 8)], white=[(6, 7), (7, 8)], last=(7, 8)), BLACK, 4, None),
        ("midgame", position(black=[(7, 7), (8, 8), (6, 6), (9, 7), (7, 9)], white=[(6, 7), (7, 8), (5, 5), (8, 7), (8, 9)], last=(8, 9)), BLACK, 10, None),
    ]
