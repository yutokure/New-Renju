# DejaVu Sans Bold UI font provenance

## Distributed asset

- Application filename: `fonts/UiSans.ttf`.
- Original upstream filename: `DejaVuSans-Bold.ttf`.
- Unmodified bytes: 704,128.
- SHA-256: `b184b89e3c1075f22f6b71575b6fc20d4972b3cfd3b23322ca6fd596dcaef167`.
- Embedded family/style/version: `DejaVu Sans` / `Bold` / `Version 2.35`.
- Embedded copyright, verbatim:

```text
Copyright (c) 2003 by Bitstream, Inc. All Rights Reserved.
Copyright (c) 2006 by Tavmjong Bah. All Rights Reserved.
DejaVu changes are in public domain
```

The file was copied without changing its contents from the build environment's Matplotlib 3.10.1 distribution, `matplotlib/mpl-data/fonts/ttf/DejaVuSans-Bold.ttf`. Its bytes were independently fetched from the official Matplotlib v3.10.1 repository and compared equal:

https://raw.githubusercontent.com/matplotlib/matplotlib/v3.10.1/lib/matplotlib/mpl-data/fonts/ttf/DejaVuSans-Bold.ttf

Official versioned repository location:
https://github.com/matplotlib/matplotlib/blob/v3.10.1/lib/matplotlib/mpl-data/fonts/ttf/DejaVuSans-Bold.ttf

## License document

`DejaVu-LICENSE.txt` is a byte-for-byte copy of that release's original `LICENSE_DEJAVU`, including both the Bitstream Vera and Arev permission/copyright/trademark/disclaimer notices. It is not an SIL OFL or MIT substitution.

- Bytes: 4,816.
- SHA-256: `d75938dec098f06f0ac3c00853065d94f020be1c3c62ef1dc2975ba15b4d9b0e`.
- Official exact source (also fetched and compared equal):
  https://raw.githubusercontent.com/matplotlib/matplotlib/v3.10.1/lib/matplotlib/mpl-data/fonts/ttf/LICENSE_DEJAVU
- DejaVu project license page:
  https://dejavu-fonts.github.io/License.html

The original permission expressly covers reproduction/distribution and sale as part of a larger software package, subject to its notice and naming conditions. `UiSans.ttf` is only a packaging filename; the internal family remains DejaVu Sans and no glyphs or font metadata were altered. Matplotlib code is not added to the application by this font copy.

## Why this asset is used

The previous PyInstaller artifact contained Pygame's historical `freesansbold.ttf` with a GPL notice, but the exact preferred editable font source was not established in the bounded review. See `FreeSans-PROVENANCE.md`. Using this separately licensed UI font and omitting that historical font avoids relying on an unproven source/license correspondence. Release verification must still confirm that the actual rebuilt archive contains this file with the hash above, contains its license, and contains no `freesansbold.ttf` copy.
