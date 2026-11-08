# Pygame 2.5.2 historical FreeSans Bold: evidence and disposition

## Exact binary inspected (not approved for continued shipping)

The original G05 artifact contained `_internal/pygame/freesansbold.ttf`:

- 98,600 bytes.
- SHA-256 `bf9251269f11e4b35582a99376096deee3d0c4973a459cbd97b0bebc01f440ad`.
- Identical bytes were fetched from the official Pygame 2.5.2 tree, resolved commit `620c37cc9d67d2835313256bd31dc5515bc91c2f`:
  https://raw.githubusercontent.com/pygame/pygame/620c37cc9d67d2835313256bd31dc5515bc91c2f/src_py/freesansbold.ttf
- Versioned upstream tree:
  https://github.com/pygame/pygame/tree/2.5.2

Relevant embedded name-table strings, verbatim (English):

```text
Copyright 2002 Free Software Foundation.
FreeSans
Bold
PfaEdit 1.0 : Free Sans Bold : 15-4-2072
Free Sans Bold
$Revision: 0.4 $
FreeSansBold
The use of this font is granted subject to GNU General Public License.
http://www.gnu.org/copyleft/gpl.html
```

The Slovenian name-table notice is also preserved here verbatim:

```text
Dovoljena je uporaba v skladu z licenco GNU General Public License.
```

The binary notice does not name a GPL version or a font exception. `GPL-2.0.txt` preserves the GNU project's original full GPL version 2 text, fetched unchanged from https://www.gnu.org/licenses/old-licenses/gpl-2.0.txt (SHA-256 `edaef632cbb643e4e7a221717a6c441a4c1a7c918e6e4d56debc3d8739b233f6`). Inclusion of that document is not a claim that the binary specifies GPLv2-only, or that adding a license alone supplies corresponding source.

## Official historical source investigation

Official GNU distribution index:
https://ftp.gnu.org/gnu/freefont/

The old, undated official source archive remains accessible:
https://ftp.gnu.org/gnu/freefont/freefont-sfd.tar.gz

- Archive bytes: 3,013,860.
- Archive SHA-256: `4a5c5c9c0265466e5b619f3b8ae7e9ea544d9ef5d81b2b0e0e877abe54f231e4`.
- Its `README` has `$Id: README,v 1.1 2002/11/28 10:10:30 peterlin Exp $`.
- That README is preserved byte-for-byte as `FreeFont-historical-README.txt` (SHA-256 `9271061938872b3a3c5cd9d29cd627646ce46320b160e9dfa6956395dfe1344f`).
- It identifies `.sfd` as PfaEdit's native form and says: "Please use these if you plan to modify the font files."
- Archive member `sfd/FreeSansBold.sfd`: 421,810 bytes, SHA-256 `1148d83cff3025b955ff71ce3bd2389fe02891fbd732da63d002e93a452f6ec7`, copyright `Copyleft 2002, 2003 Free Software Foundation.`, version `$Revision: 1.10 $`.

The accompanying official old binary archive is:
https://ftp.gnu.org/gnu/freefont/freefont-ttf.tar.gz

- Archive bytes: 1,189,011.
- Archive SHA-256: `45774ef967e70509af3436ef6c8eb2c92c84c24b8002cf7101a4541d55e1b321`.
- Its `sfd/FreeSansBold.ttf` is 91,432 bytes, SHA-256 `5b0765156a7522e1b20f16cb911bf3a03d568d8ee9f5cab18481d8449fa81040`.
- This is **not** the Pygame font binary.

Official project/history access:
https://savannah.gnu.org/projects/freefont/
https://svn.savannah.gnu.org/svn/freefont/trunk/freefont/

The project records a 2011 CVS-to-SVN change. Historical SVN directories were reachable, but the bounded review did not identify an exact SFD revision/build recipe corresponding to Pygame's Revision 0.4 font. No guessed SFD is being passed off as corresponding source. The current FreeFont page https://www.gnu.org/software/freefont/license.html states GPLv3-or-later and a document embedding exception for current releases; it is not used to retroactively assert those terms for this 2002 binary.

## Conclusion limited to evidence

A hash match with the official Pygame binary establishes where the distributed binary came from and that the application did not modify its bytes. It does **not** establish that the binary itself is the preferred form for modification, or identify the exact editable SFD/build inputs. The historical project's own README points to SFD for modifications. Therefore this review does not claim the old artifact's GPL font source-delivery question is resolved merely by the matching upstream TTF URL.

## Narrow release alternative

The release implementation can avoid distributing this font: explicitly route production UI/default-font fallbacks to the separately licensed `fonts/UiSans.ttf`, and filter only `pygame/freesansbold.ttf` from collected package data. Preserve Pygame's own LGPL and dependency notices; no Pygame library byte changes are needed. See `DejaVu-PROVENANCE.md` for the unmodified replacement's exact binary, original terms and official provenance.

Acceptance for that alternative requires verification of the actual rebuilt directory **and** final ZIP: no `freesansbold.ttf`, replacement font hash matches, license present, and startup/UI/fallback rendering works without the Pygame default font. Until that check passes, the original GPL-font concern remains a release blocker. This is an evidence report, not a legal opinion about the entire application.
