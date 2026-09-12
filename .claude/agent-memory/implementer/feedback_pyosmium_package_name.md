---
name: feedback-pyosmium-package-name
description: PyPI/import name for "pyosmium" is actually "osmium" -- pip install pyosmium 404s
metadata:
  type: feedback
---

The pyosmium project (pyosmium.org, OSM .pbf parsing) is named "pyosmium" everywhere in its own
docs and in this project's M9 plan, but its PyPI distribution name AND its import name are both
`osmium`. `pip install pyosmium` returns a 404 from PyPI's JSON API (not just "no matching
version" -- the project literally doesn't exist under that name on PyPI); `pip install osmium`
is correct.

**Why this matters**: an earlier planning session's sandbox couldn't resolve `pyosmium` from
PyPI and flagged it as an unresolved dependency-install risk requiring escalation on the real
dev machine. When actually tested on the real `world-model/.venv` (Python 3.14), the "no
versions found" error was investigated further via PyPI's JSON API
(`https://pypi.org/pypi/<name>/json`) rather than accepted at face value -- that revealed the
404 and the correct name. This was never a wheel-availability problem (cp314 wheels exist for
`osmium` as of 4.3.1, macOS arm64/x86_64 + manylinux + Windows) or a sandbox network restriction
(a fresh unrelated package like `cowsay` installed fine, proving PyPI access itself worked).

**How to apply**: when a `pip install <name>` for a dependency named in a plan returns "no
versions found" or 404, check `https://pypi.org/pypi/<name>/json` (or try common
alt-capitalization/prefix variants) before concluding the dependency is genuinely unavailable
and escalating per AGENTS.md's dependency-decision rule -- the package may just be misnamed in
the plan. `world-model/pyproject.toml`'s dependency list now documents this for `osmium`
specifically (see the comment above the `osmium>=4.3` entry).
