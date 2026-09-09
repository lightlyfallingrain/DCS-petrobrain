"""DCS `object_type` -> Petrovich reporting-name lookup, backing
`object_model.py`'s reporting-name-keyed keyword table.

**Why this exists.** `object_model.py`'s keyword table matches against
`LoGetWorldObjects`'s raw `object_type` string, which is irregular for many
unit families (`CHAP_T90M`, `ATZ-5`, `B600_drivable`) -- exactly the reason
coverage of modern ground units was thin (see
`aircraft-layer/research/2026-09-09-object-model-keyword-coverage.md`'s
Addendum). ED's own Petrovich AI faces the same raw `object_type` string and
resolves it to a much more regular spoken-callout name (`"T-90M"`, `"Ural
fuel truck"`, `"Aircraft tug"`) via a literal, complete lookup table in the
Mi-24P module's `HelperAI_reporting_names.lua`. Shipping that table as data
and keying a second keyword pass on the *reporting* name (rather than
inventing per-type regexes against the raw name) is what closes most of the
gap cheaply.

**Provenance and version-specificity.** `data/dcs_type_to_reporting_name.tsv`
(595 rows, 376 distinct reporting names) was extracted from
`HelperAI_reporting_names.lua` in a Windows-box Mi-24P install running DCS
`2.9.29.27278` -- see the research doc above for the extraction session; that
doc, not the gitignored `win-mac-sync/` sync path the source file was
fetched through, is the citable provenance record. **This table is
DCS-version-specific and will drift** as ED adds, renames, or removes unit
types across patches -- it is a snapshot, not a live query. This is exactly
why `object_model.py` tries its own raw-`object_type` keyword table *first*
and only consults this mapping as the next step: a type this table doesn't
know about (added after this extraction, or simply never in Petrovich's own
reporting vocabulary) still gets a fallback chance at the raw-type table,
rather than silently losing coverage it already had.

**Regenerating this table** (next time DCS/the Mi-24P module updates and
coverage should be refreshed), from a Windows box with the DCS install:

1. Locate `HelperAI_reporting_names.lua` under the Mi-24P module's aircraft
   Scripts directory. (Not restated here as a fixed path -- per this
   project's standing convention for install-derived Lua, that path is
   machine-specific and lives under the gitignored `win-mac-sync/` sync
   directory when copied locally; the research doc cited above records
   where this session found it.)
2. The file is a single Lua table literal: `[dcs_object_type] =
   "reporting_name",` entries (occasionally `["some key"] = "..."` for keys
   needing quoting). A short regex extraction is sufficient -- no full Lua
   interpreter needed, e.g. matching `%[?"?([^"%[%]=]+)"?%]?%s*=%s*"([^"]+)"`
   per line (or the Python equivalent against the fetched text).
3. Overwrite `data/dcs_type_to_reporting_name.tsv` with the new extraction:
   header row `dcs_object_type<TAB>petrovich_reporting_name`, one row per
   entry, LF line endings, no quoting/escaping (reporting names in this
   catalogue contain no tabs or newlines).
4. Re-run `pytest body-layer/tests/test_reporting_names.py
   body-layer/tests/test_object_model.py` (see `body-layer/CLAUDE.md`
   Commands for the full invocation) to confirm nothing regressed, and
   re-run this doc's coverage measurement against the refreshed file if a
   new count is worth recording.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

_DATA_PATH: Path = Path(__file__).parent / "data" / "dcs_type_to_reporting_name.tsv"


@cache
def _load_mapping() -> dict[str, str]:
    """Parse `_DATA_PATH` once and cache it -- called from every
    `reporting_name_for` lookup, so re-parsing the file per call would be
    wasted work on a hot-ish path (every `profile_for` call that misses the
    raw-type table)."""
    mapping: dict[str, str] = {}
    with _DATA_PATH.open(encoding="utf-8") as handle:
        next(handle)  # header row: dcs_object_type<TAB>petrovich_reporting_name
        for line in handle:
            line = line.rstrip("\n")
            if not line:
                continue
            object_type, reporting_name = line.split("\t", 1)
            mapping[object_type.lower()] = reporting_name
    return mapping


def reporting_name_for(object_type: str) -> str | None:
    """Case-insensitive exact lookup of `object_type` against ED's own
    DCS-type -> reporting-name table. Returns `None` for a type not present
    in the table -- an unmapped or new-to-this-DCS-version unit, which
    `object_model.py` handles by falling back to its own raw-type keyword
    table (see that module's `profile_for`), not by failing."""
    return _load_mapping().get(object_type.lower())
