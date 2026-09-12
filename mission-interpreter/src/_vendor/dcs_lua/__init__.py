"""Vendored Lua table parse/serialize subpackage from pydcs (LGPL-3.0).

See `plans/mission-interpreter/plan.md` Decision 1: mission-interpreter needs
a DCS-`.miz`-Lua-table parser but not the rest of pydcs (its generated
`weapons_data.py`/`countries.py` catalogs are ~1.7MB combined and unneeded --
Mission Interpreter's own semantic layer is bespoke). `dcs/lua/parse.py` and
`dcs/lua/serialize.py` have no imports beyond `typing`, so they vendor
cleanly on their own without pulling in the rest of `dcs/`.

Provenance: vendored verbatim (no functional changes) from
https://github.com/pydcs/dcs at commit `55dc18adbd6907ea17d87de559445c4f9bc39146`
(`pydcs` version 0.15.0), `dcs/lua/parse.py` and `dcs/lua/serialize.py`.
`LICENSE.txt` in this directory is pydcs's own LGPL-3.0 license file,
included verbatim per the license's own terms for redistributing a
(sub-)component of the covered library.

This module is intentionally excluded from this subproject's `mypy --strict`
run (see `pyproject.toml`'s `[[tool.mypy.overrides]]` for this module) --
it is third-party code we did not write and do not want to reformat/
re-annotate just to satisfy our own strictness bar; treat it as an opaque
dependency, not code to edit. If a bug is found in it, prefer reporting/
fixing upstream and re-vendoring rather than patching this copy in place,
unless the fix is trivial and DCS-specific enough that upstreaming doesn't
make sense.

Public API: `loads(tablestr, ...)` (parse.py) and `dumps(value, ...)`
(serialize.py) -- only `loads` is used by `mission-interpreter/src/miz/`
today; `dumps` is exported for completeness (round-tripping is not this
subproject's job) since both come from the same subpackage.
"""

from _vendor.dcs_lua.parse import loads
from _vendor.dcs_lua.serialize import dumps

__all__ = ["loads", "dumps"]
