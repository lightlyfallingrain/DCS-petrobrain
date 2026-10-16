---
name: project-mission-interpreter-full-audit-2026-10-16
description: X-B9 full mission-interpreter audit (2026-10-16) — findings, and what was already checked clean, so a later pass doesn't re-derive it
metadata:
  type: project
---

Full-subproject survey written to `mission-interpreter/research/2026-10-16-security-audit.md`
(X-B9's remaining half). Three real findings, none blocking:

1. **`TriggerZone.hidden` is parsed (`miz/tree.py`) but never consulted by
   `filter/crew_available.py`'s author-only-knowledge filter** — zones pass through unfiltered
   regardless of this flag. Whether DCS's zone-level `hidden` means "author secret" (like
   `Group.hidden`) or is purely an editor-canvas display toggle is **unresolved** — needs an
   `investigator` pass against pydcs/Hoggit source, not a guess. Filed as the one open question
   from this audit; do not treat as settled either way without that pass.
2. **Vendored Lua parser (`_vendor/dcs_lua/parse.py`) has no recursion-depth limit**, and
   `miz/reader.py:70-79` only catches `SyntaxError` around `loads(...)` — a deeply-nested
   malformed `.miz` crashes with an unhandled `RecursionError` instead of a clean
   `MizParseError`. Low severity (single-user offline CLI, crash only, no data exposure) but a
   one-line fix (add `RecursionError` to the except clause) if anyone picks it up.
3. **Same shape, different trigger**: `miz/reader.py`'s `_as_ordered_list` does
   `sorted(value.keys())` on a dict that can have mixed str/int keys from a malformed Lua table →
   uncaught `TypeError`. Same fix class as #2.

**Confirmed clean, don't re-check unless the code changes**: no zip-slip/path-traversal (no
`extractall`, kneeboard images are passed through as zip-member *path strings* only, never
read/extracted); no SSRF (both HTTP clients hit fixed localhost base URLs, never
mission-content-derived); no subprocess/eval/pickle/yaml.load anywhere in this subproject's own
code; the coordinate-leak boundary (`threat_signals.py` → `enrich_threat_signals` → `prompts.py`)
holds exactly as the module docstrings claim — `EnrichedThreatSignal` structurally has no x/z
field at all, so `prompts.py` can't leak a raw coordinate even by a future bug in `_place_name`;
`CrewAvailableMission`'s "no raw passthrough field" claim is real (structurally enforced, not a
discipline promise). `OllamaClient` fails closed on model-not-pulled rather than silently
triggering a multi-GB auto-pull.

**Informational, not filed to backlog**: no size cap on `.miz` zip-member reads before decoding
(a single-member zip-bomb could exhaust memory) — not worth it at current single-user scope where
the only precedent input (`Mission 02-Bagram.miz`) is a file the user deliberately chose to add;
worth revisiting only if mission-interpreter is ever pointed at missions sourced less carefully.

See [[project_wm_full_audit_pattern]] if that memory exists — this audit followed the same shape
(sibling pass was `world-model/research/2026-10-05-security-audit.md`, read first per the task
brief) of "whole subproject, no CVE/SBOM step, read the actual boundary code" that Mode 3 of this
role's own instructions now codifies.
