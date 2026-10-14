---
name: reference_pdftotext_sweep_quickstart_pdf
description: pdftotext -layout + grep is the fast way to sweep the whole Mi-24P QuickStart RU PDF for a keyword (missile speed, FOV degrees, etc.) before concluding a figure is absent
type: reference
---

`pdftotext` (Homebrew, `/opt/homebrew/bin/pdftotext`) is available in this environment and
produces clean enough text from `docs/concept/mi-24_info/DCS Mi-24P QuickStart RU.pdf` (`-layout`
flag preserves table columns reasonably) to `grep -n -iE` across the entire ~5375-line document in
one shot, rather than reading page ranges blind looking for a number.

Used 2026-10-14 (BL-B64 investigation) to confirm **no missile speed/range figure for 9M114 exists
anywhere in this PDF** (only the GSh-2-30 cannon's muzzle velocity uses "м/с") and that **no FOV
figure in degrees exists anywhere** (only the ×3.3/×10 magnification ratios) — both negative
results that would have been hard to trust from page-by-page reading alone, since the `Read` tool's
`pages` param caps at 20 pages/call and the manual is 160+ pages.

```sh
pdftotext -layout "docs/concept/mi-24_info/DCS Mi-24P QuickStart RU.pdf" /tmp/quickstart.txt
grep -n -iE "<keywords>" /tmp/quickstart.txt
```

Do this sweep **before** declaring a figure "not in the document" from a targeted page read — a
targeted read only proves the figure isn't on the pages you looked at, not that it's absent from
the whole manual. See `body-layer/research/2026-10-14-9k113-warmup-atgm-procedure.md` for the
worked example (Findings 4 and 5).

Images/screenshots embedded in the PDF are not covered by this (text layer only) — a figure that
exists only as a diagram annotation (e.g. the ±40°/±15°/+20° console-travel numbers the 2026-09-20
sight-optics note found, which are printed *inside* a photograph) will not show up in the text
sweep and still needs a page image read.
