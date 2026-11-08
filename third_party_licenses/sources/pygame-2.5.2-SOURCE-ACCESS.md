# Pygame 2.5.2 library source supplied with this release

The accompanying `pygame-2.5.2-source-no-default-font.tar.gz` supplies Pygame 2.5.2 C/Python library source, headers, build/configuration scripts, original notices and documentation directly with this application's distribution. The original LGPL 2.1 text is in `../Pygame-LGPL-2.1.txt` and in the archive's `pygame-2.5.2/docs/LGPL.txt`. Recipients may modify/rebuild/replace the Pygame library under its original terms. This application does not add a restriction on reverse engineering for debugging such modifications.

## Provenance and precise filtering

Official PyPI release metadata:
https://pypi.org/pypi/pygame/2.5.2/json

Official source distribution:
https://files.pythonhosted.org/packages/c6/aa/2c0c867d6cff00966cfc2152b25f61599f87e88b239e4dcb8ad5357f0f69/pygame-2.5.2.tar.gz

- Official archive: 15,788,328 bytes, SHA-256 `c1b89eb5d539e7ac5cf75513125fb5f2f0a2d918b1fd6e981f23bf0ac1b1c24a`, checked against official PyPI metadata.
- Supplied filtered archive: 15,413,195 bytes, SHA-256 `c984cc239ff0459f2eb71d9ac223b5a1fb93abe45d1b82da24607e312e8de9da`.
- 1,417 retained members. Every retained regular member's bytes were compared equal to the official source archive.
- Only six `.ttf`/`.otf` data files were omitted: the historical default GPL font and five example/test font binaries not shipped as runtime assets by this application. Their complete names, sizes and hashes are in the adjacent `pygame-2.5.2-SOURCE-PROVENANCE.json`.
- No C/Python library code, headers, build scripts, notices or documentation were modified. The tar/gzip container was regenerated and is not represented as identical to the official tarball. The small editable `PyGameMono.sfd` test font source remains in the archive.

This explicit filtering avoids shipping the unresolved historical default font inside a nested source archive, and avoids importing unrelated example/test font binaries. It does not claim that the official default font's exact preferred editable source was found. See `../FreeSans-PROVENANCE.md`.

## Rebuild and font-data note

Extract the archive and follow its README and `buildconfig` instructions to compile the library for the target Python/SDL configuration. The archive includes `setup.py`, `setup.cfg`, all `src_c`/`src_py` files except the listed font data, and Windows build configuration/download scripts. Upstream source/build overview: https://github.com/pygame/pygame/tree/2.5.2 and https://www.pygame.org/wiki/Compilation.

If an upstream installation/packaging step expects `src_py/freesansbold.ttf`, copy this application's separately supplied, unmodified `fonts/UiSans.ttf` into that data location before that step, retaining its DejaVu terms. This replaces only default font data, not the library source. The application explicitly routes its UI font calls to its own `UiSans.ttf` and omits Pygame's default font data in its release, so the historical font is not needed to reproduce the Pygame library used here.

The shared extension modules and DLLs remain ordinary onedir files. A replacement must remain interface-compatible with the Python/SDL versions used by the app. This source copy does not promise bit-for-bit reproduction of the third-party prebuilt Windows wheel or assert provenance for its compiler environment. The final release owner must keep this source archive accessible alongside the library binary and preserve the original LGPL terms/notices.
