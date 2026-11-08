# Third-party software and font notices

Gomoku 2.0 itself is MIT licensed (see the archive root LICENSE). Bundled libraries/assets retain their own terms. No dependency library is modified by this application. The onedir layout keeps extension modules and DLLs replaceable; this app imposes no restriction on reverse engineering to debug modifications of LGPL components.

## Font

`YasashisaGothicBold-V2.otf` is the repository's existing unmodified font. Embedded metadata identifies `Copyright(c)Fontna.com , Copyright(c) 2019 M+ FONTS PROJECT`, family `YasashisaGothicBoldV2 bold`, version `2.063;hotconv 1.0.109;makeotfexe 2.5.65596`.

Fontna's official family page expressly licenses use/embedding under M+ terms and credits Fontna (kana) and M+ FONTS PROJECT:
https://www.fontna.com/blog/yasashisagothic_b.html

The official legacy family distribution remains available at:
https://www.fontna.com/font/07YasashisaBold.zip

Its original LICENSE_E, LICENSE_J and Fontna readme are included here (Japanese EUC-JP converted to UTF-8 without changing the text). The legacy package is not asserted to contain the identical V2 binary; the current font's copyright above is preserved separately. M+ grants unlimited use/copy/distribution with or without modification, commercial or noncommercial, without warranty. No new OFL terms are retroactively substituted for this legacy font.

## Build dependencies

- Python 3.12.3: Python-3.12.3-LICENSE.txt, copied from the build interpreter. Source https://www.python.org/downloads/release/python-3123/.
- NumPy 1.26.3: NumPy-1.26.3-LICENSE.txt copied from its installed distribution, including bundled OpenBLAS/LAPACK/GCC runtime notices. Source https://github.com/numpy/numpy/tree/v1.26.3.
- Pygame 2.5.2: Pygame-LGPL-2.1.txt. Source and build information https://github.com/pygame/pygame/tree/2.5.2. Its upstream docs/licenses files are included verbatim as LICENSE.*.txt, covering SDL2 and bundled codec/font libraries where present. Pygame copyright is held by its authors (Pete Shinners, René Dudfield and contributors); see upstream source notices. The bundled Pygame files are unmodified.
- SDL2, SDL_image, SDL_mixer and native codecs: corresponding upstream Pygame 2.5.2 notices are included. These do not claim that every optional library mentioned is present in this particular artifact; BUILD_INFO.json enumerates the actual files.
- PyInstaller 6.13.0 bootloader: GPL with special exception permitting distribution of non-GPL applications; see PyInstaller-COPYING.txt. Source https://github.com/pyinstaller/pyinstaller/tree/v6.13.0.
- Microsoft runtime components supplied with CPython: covered by the Python distribution's notices/redistribution terms. Windows system libraries are not relicensed by this app.

Exact bundled files and SHA-256 values are recorded in BUILD_INFO.json. Full app source and local build recipe are available at https://github.com/yutokure/New-Renju. Upstream library source links above provide the corresponding unmodified versions; retain these notices with redistributed copies.
