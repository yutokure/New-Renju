# G05 / Issue25 license coverage review

## Scope and status

Focused review of actual PyInstaller onedir files **and** the executable's embedded PYZ inventory. No application/build edits were made by the licensing reviewer; the only separately authorized asset addition was `fonts/UiSans.ttf`. Original third-party terms are preserved rather than summarized in place of the license. This is an evidence-based packaging review, not legal advice or an assertion that every possible redistribution obligation is conclusively discharged.

**Disposition:** do not publish the old artifact containing Pygame's historical GPL font on the strength of its upstream binary URL alone. A narrow release alternative has been supplied: an unmodified, separately licensed DejaVu Sans Bold UI font. Parent implementation owns routing/default-font exclusion/build verification. Final acceptance remains conditional on the archive checks below.

## Font evidence and resolution path

| Item | Finding |
| --- | --- |
| Original Pygame default font | `pygame/freesansbold.ttf`, 98,600 bytes, SHA-256 `bf9251269f11e4b35582a99376096deee3d0c4973a459cbd97b0bebc01f440ad`; identical to official Pygame 2.5.2 resolved commit `620c37cc9d67d2835313256bd31dc5515bc91c2f`. |
| Original metadata | `Copyright 2002 Free Software Foundation.`, `$Revision: 0.4 $`, GPL notice without a version or exception. |
| Historical preferred source | Official old FreeFont README identifies `.sfd` as the modification form. The downloaded official source archive contains Revision 1.10, and its accompanying TTF has a different size/hash. No exact Revision 0.4 SFD/build correspondence established in the bounded investigation. |
| What a binary hash proves | Exact binary provenance/unmodified bytes only; not that a TTF is the preferred source or that a different SFD is corresponding source. Current FreeFont GPLv3+ embedding exception is not retroactively assumed. |
| Original terms/evidence retained | Full original GPL2 text, original 2002 historical README, verbatim embedded copyright/license strings, official URLs and archive/member hashes are in third_party_licenses. These do not constitute a claim that exact source obligations for the old font are resolved. |
| Safe narrower package alternative | Route production default-font uses/fallbacks to `fonts/UiSans.ttf`, omit all `freesansbold.ttf` copies, keep Pygame library and LGPL/dependency notices unchanged. |
| Replacement | DejaVu Sans Bold 2.35, 704,128 bytes, SHA-256 `b184b89e3c1075f22f6b71575b6fc20d4972b3cfd3b23322ca6fd596dcaef167`; byte-identical to official Matplotlib 3.10.1 font, no glyph/metadata modification. |
| Replacement terms | Exact original LICENSE_DEJAVU: Bitstream 2003 / Tavmjong Bah 2006; DejaVu changes public domain. Notice retention, naming/trademark, larger-package distribution and disclaimer text preserved. |

Official primary sources:

- Exact original TTF: https://raw.githubusercontent.com/pygame/pygame/620c37cc9d67d2835313256bd31dc5515bc91c2f/src_py/freesansbold.ttf
- Historic source/binary archives: https://ftp.gnu.org/gnu/freefont/freefont-sfd.tar.gz and https://ftp.gnu.org/gnu/freefont/freefont-ttf.tar.gz
- Official source history access: https://savannah.gnu.org/projects/freefont/ and https://svn.savannah.gnu.org/svn/freefont/trunk/freefont/
- GPL2 original: https://www.gnu.org/licenses/old-licenses/gpl-2.0.txt
- Replacement exact font: https://raw.githubusercontent.com/matplotlib/matplotlib/v3.10.1/lib/matplotlib/mpl-data/fonts/ttf/DejaVuSans-Bold.ttf
- Replacement exact original terms: https://raw.githubusercontent.com/matplotlib/matplotlib/v3.10.1/lib/matplotlib/mpl-data/fonts/ttf/LICENSE_DEJAVU

## Actual bundle coverage

The initial onedir inventory had 186 files, including duplicate SDL/codec DLLs at `_internal` and `_internal/pygame`, Python extensions, NumPy/OpenBLAS, fonts and notices. The release owner may rebuild/change that count; final BUILD_INFO is authoritative for final bytes. The executable PYZ contains more third-party code than the loose-file list alone reveals.

| Actual dependency family | Coverage / review result |
| --- | --- |
| CPython 3.12.3 + stdlib/extensions | Existing Windows binary LICENSE includes PSF/history, MS runtime conditions, bzip2/libffi/OpenSSL texts. Added original official `Doc/license.rst` to preserve incorporated-code acknowledgments including Expat, MT, hashing, libmpdec, sockets, asyncio and other upstream notices. |
| NumPy 1.26.3 + numpy.libs OpenBLAS | Existing exact binary-distribution LICENSE includes OpenBLAS/LAPACK/GCC runtime notices and exceptions. Added referenced lapack-lite/libdivide notices and verbatim Dragon4 MIT license header from exact v1.26.3 source. Build-only Meson/spin references do not imply runtime inclusion. |
| Pygame 2.5.2 library | Existing LGPL2.1 retained. Official 2.5.2 source distribution is now supplied in the notices `sources` subtree, with only six runtime/example/test .ttf/.otf font binaries omitted; every retained regular source/build/doc member was byte-compared to official sdist. Default GPL font disposition is separate, above. |
| SDL2 / image / mixer / ttf / FreeType | Runtime queries: SDL 2.28.3, image 2.0.5, mixer 2.6.2, ttf 2.20.1, FreeType 2.11.1. Existing notices plus SDL_ttf exact 2.20.1 license; full original texts retained. Explicit FreeType acknowledgment added to notices README. |
| Actual codec DLL basenames | libmodplug, libwebp, libjpeg, libpng, libtiff, zlib, libogg, libopus, libopusfile and portmidi all have existing original LICENSE.* notices. Extra upstream FLAC/fluidsynth/mpg123 notices retained; their presence is not asserted solely because their terms exist. |
| OpenSSL 3.0.13 | ssl module reports 3.0.13; libcrypto-3/libssl-3 DLL families plus _ssl/_hashlib present. Existing OpenSSL-LICENSE exactly matches official 3.0.13 Apache2 license bytes. |
| PyInstaller 6.13.0 bootloader/hooks | Existing complete COPYING including special exception retained; versioned upstream source identified. |
| Setuptools/pkg_resources 78.1.1 | **Actually present in PYZ**, not merely build tooling. Added exact installed MIT terms. A source-code structural comparison against installed setuptools/pkg_resources confirmed matching bytecode/constant semantics (filename/line mapping ignored). |
| Setuptools generated validator | PYZ includes `_validate_pyproject` modules. Official NOTICE identifies BSD3 fastjsonschema and MPL2 validate-pyproject material. Added entire original NOTICE and six exact official source .py files, plus adjacent NOTICE, for direct source access without relying only on a link. |
| Setuptools vendored packages actually in PYZ | backports.tarfile 1.2.0, importlib_metadata 8.0.0, jaraco.context 5.3.0, jaraco.functools 4.0.1, jaraco.text 3.12.1, more-itertools 10.3.0, packaging 24.2, tomli 2.0.1, wheel 0.45.1 (with its own packaging terms), zipp 3.19.2: exact installed-distribution licenses added, with versioned source URLs. |
| Other actual PYZ dependencies | Top-level packaging 24.2 (identical terms to vendored copy), platformdirs 4.3.7, typing_extensions 4.13.1: exact terms added. `backports`/`jaraco` namespace stubs covered by their actual bundled subpackages. |
| Setuptools optional vendor packages not detected in PYZ | autocommand, inflect, jaraco.collections, typeguard, vendor platformdirs 4.2.2/vendor typing_extensions 4.12.2 not observed; no assertion that installed metadata alone means bundled. Re-review if the final PYZ adds them. |
| Japanese Yasashisa Gothic V2 | Existing Fontna/M+ original terms, embedded copyright and explicit limitation (legacy ZIP not asserted byte-identical to V2) retained. No retroactive SIL OFL substitution. |

Important official links:

- CPython complete incorporated-software acknowledgments: https://raw.githubusercontent.com/python/cpython/v3.12.3/Doc/license.rst
- Setuptools validator original NOTICE (BSD3 + MPL2): https://raw.githubusercontent.com/pypa/setuptools/v78.1.1/setuptools/config/_validate_pyproject/NOTICE
- SDL_ttf exact terms: https://raw.githubusercontent.com/libsdl-org/SDL_ttf/release-2.20.1/LICENSE.txt
- OpenSSL exact terms: https://raw.githubusercontent.com/openssl/openssl/openssl-3.0.13/LICENSE.txt
- Remaining added exact source locations and SHA-256 values: see the notice directory's ADDITIONAL-PROVENANCE.json and component provenance documents.

## Lightweight verification performed

- Read required existing notices and Issue25 acceptance text; enumerated actual loose files.
- Opened PyInstaller CArchive/PYZ via its reader without executing the frozen application; inventoried actual bundled modules.
- Compared selected installed dependency sources' bytecode/constant structure against PYZ to avoid assuming every installed dependency was bundled.
- Fetched DejaVu font and license from official versioned repository; verified both byte-for-byte against installed copies, then copied unchanged.
- Compared existing SDL_ttf/OpenSSL license bytes against exact official versions: equal.
- Downloaded and hashed official historic FreeFont archives; compared actual fonts/source headers and preserved limits.
- Hashed every entry in added provenance JSON against the saved document/source: passed for 38 entries at completion of collection (some identical packaging license files have two installed origins).
- No heavy test suite, application process, build, GitHub operation or source edits were run by this reviewer.

## Pygame LGPL source access addendum

LGPL2.1 section 4 addresses redistribution of the library binary with complete corresponding source, including an equivalent same-place source-access route. Section 6(b)'s suitable shared-library mechanism addresses the app/library link; it should not be treated as making a bare third-party source link sufficient for library-binary distribution. To avoid relying on the external link alone, the release now directly supplies Pygame's official 2.5.2 source/build scripts in a filtered archive under the notices `sources` subtree. See its adjacent SOURCE-ACCESS document for extraction/build/font-data substitution instructions and source-provenance limitations. No legal certification or promise of bit-identical wheel reproduction is made.

Official archive hash (checked against PyPI): `c1b89eb5d539e7ac5cf75513125fb5f2f0a2d918b1fd6e981f23bf0ac1b1c24a`. Supplied filtered archive: 15,413,195 bytes, SHA-256 `c984cc239ff0459f2eb71d9ac223b5a1fb93abe45d1b82da24607e312e8de9da`, 1,417 retained members. All retained regular members equal the original sdist bytes; six explicitly listed .ttf/.otf binary data members omitted, including the old default font. Auxiliary Liberation/OFL font binaries were not reintroduced through example/test assets; editable PyGameMono.sfd remains. C/Python code, headers, build scripts, notices and docs remain unchanged.

## Release-owner acceptance checklist

1. Rebuild/assemble **after** all notice/source additions: the licensing reviewer did not edit the built artifact. Ensure the entire notices tree, including nested `python-packages`, `numpy-1.26.3` and `sources` subdirectories, reaches the final ZIP unchanged.
2. Confirm no `freesansbold.ttf` at any path in the onedir/ZIP, not merely unused by the application. Confirm the replacement font and exact original DejaVu notice hashes above.
3. Exercise default-font UI/startup and Japanese-font-failure fallback without the old font, including any hidden production `Font(None, ...)`, `SysFont` fallback, freetype default or Pygame error-path usage. Parent owns these source/UI checks.
4. Compare final loose inventory and final embedded PYZ against covered families. If versions/new modules differ, update exact notices rather than assuming coverage from the build machine.
5. Ensure license text and source files are discoverable to recipients, with unchanged LGPL module/DLL replacement/debugging permissions; retain upstream version/source access evidence. Parent owns final release packaging and any source-access hosting.
6. Generate final BUILD_INFO/ZIP hashes after last content changes. Do not call the old artifact or an earlier ZIP accepted based only on repository notices.

**Remaining blocker until parent verification:** final rebuilt directory/ZIP/font-routing acceptance has not been certified by this licensing-only task. The old GPL font's exact editable source remains unestablished; removal of that asset, not a fabricated corresponding-source claim, is the proposed resolution.
