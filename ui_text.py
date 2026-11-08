"""Single English UI vocabulary; Japanese joseki names are proper names."""
from constants import AI_LABELS

MODE_LABELS = {(0,0): 'Human vs Human', (0,1): 'Human vs AI',
               (1,0): 'AI vs Human', (1,1): 'AI vs AI'}


def rules_label(settings):
    if settings.win_length == 5:
        suffix = '' if settings.board_size == 15 else ' (nonstandard board)'
        return 'Renju core: Black exact 5 / White 5+' + suffix
    return f'Custom connect-{settings.win_length}: both colors {settings.win_length}+, no black fouls'


def mode_label(settings):
    mode = MODE_LABELS[settings.game_mode]
    if 1 in settings.game_mode:
        mode += ' | ' + AI_LABELS[settings.ai_difficulty]
    return mode


def rules_help(settings):
    return [rules_label(settings),
        'Black moves first. Click an empty intersection on your turn.',
        '5 only: Black double-three / double-four / overline are forbidden.',
        'A simultaneous exact black five takes priority over other fouls.',
        'Custom 3 / 4 / 6 / 7: either color wins with at least the target.',
        'Simplified opening (all targets, all supported board sizes):',
        '1. Black: center.  2. White: above center or above-right.',
        '3. Black: within 2 rows and 2 columns of center.',
        'Not tournament openings: no swaps, fifth-move proposals or clocks.',
        'Colored lines / Attack / Defense / Pressure: 5-only pattern hints.',
        'Hints are not foul verdicts or a proof of a forced win.',
        'Shaded points: confirmed restrictions; unmarked is NOT guaranteed legal.',
        'Research: Hard static estimates for the side to move, NOT a win proof.',
        'Prev / Next: view history and return to the latest position.',
        'S: save current game. Esc: Menu. R: retry an UNKNOWN move check.',
        'UNKNOWN leaves the stone unplayed. Retry, choose another point, or Menu.']


MOVE_REASONS = {
    'occupied': 'Occupied intersection. Choose an empty point.',
    'opening': 'Opening restriction. See Rules for the first three moves.',
    'out_of_bounds': 'Click an intersection inside the board.',
    'forbidden': 'Forbidden black move (Renju core).',
    'forbidden_overline': 'Forbidden: black overline.',
    'forbidden_double_four': 'Forbidden: black double-four.',
    'forbidden_double_three': 'Forbidden: black double-three.',
}
