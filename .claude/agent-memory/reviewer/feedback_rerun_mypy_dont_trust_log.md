---
name: rerun-mypy-dont-trust-implementation-log
description: A dependency shipping py.typed stubs after implementation can silently break mypy --strict via stale type:ignore comments — always rerun mypy yourself.
metadata:
  type: feedback
---

Caught during M9 (world-model/) review: the implementation log reported `mypy src` (strict)
clean, but rerunning it myself in the actual `world-model/.venv` failed with "Unused 'type:
ignore' comment" on `src/osm/pbf.py`'s `class _FeatureCollector(osmium.SimpleHandler):  # type:
ignore[misc]`. Root cause: the installed `osmium==4.3.1` ships `py.typed` + full `.pyi` stubs, so
a suppression that was needed against an untyped/partially-typed version of the dependency became
stale, and `strict = true` (which implies `warn_unused_ignores`) turns that into a hard failure.

**Why:** this is a class of drift a written implementation log cannot catch after the fact — a
dependency's type-stub coverage can change between when the implementer last ran the checks and
when Reviewer re-verifies, even with zero code change in between. Trusting the log's "mypy pass"
line would have let this ship.

**How to apply:** always literally re-run the subproject's format/lint/type/test commands during
review (per the Reviewer checklist and root CLAUDE.md's Verification section) — never treat the
implementer's reported results as sufficient, especially for `mypy --strict` when the change adds
or bumps a third-party dependency that ships its own type stubs (numpy, osmium, etc.). The fix
itself is usually trivial (drop the stale `# type: ignore`) but only if caught.
