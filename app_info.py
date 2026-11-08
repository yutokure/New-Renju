"""Product identity: import here, never duplicate executable/version strings."""
PRODUCT_NAME = 'Gomoku 2.0'
DISPLAY_VERSION = '2.0'
VERSION = '2.0.0'
WINDOWS_VERSION = tuple(int(part) for part in VERSION.split('.')) + (0,)
RELEASE_TAG = 'v' + VERSION
ZIP_NAME = 'Gomoku-' + DISPLAY_VERSION + '-Windows-x64.zip'
EXE_NAME = PRODUCT_NAME + '.exe'
BUNDLE_DIRECTORY = 'Gomoku-' + DISPLAY_VERSION
DATA_DIRECTORY = 'Gomoku2'
REPOSITORY_URL = 'https://github.com/yutokure/New-Renju'
LICENSE_NAME = 'MIT License'


def about_lines():
    return [PRODUCT_NAME, 'Version ' + VERSION,
        'Gomoku / Renju-core board game with four AI difficulty levels.',
        'Human vs Human, Human vs AI, AI vs Human, AI vs AI.',
        'Libraries: Python, Pygame (SDL), NumPy; packaged by PyInstaller.',
        'License: ' + LICENSE_NAME + ' (app). Third-party licenses bundled.',
        'Pygame (c) Pete Shinners / Rene Dudfield / contributors; LGPL 2.1.',
        'See _internal/THIRD_PARTY_LICENSES/Pygame-LGPL-2.1.txt.',
        'Copyright (c) 2025 yutokure. No warranty.',
        REPOSITORY_URL]
