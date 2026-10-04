---
name: project-multi-theatre-afghanistan
description: Multi-theatre-afghanistan Stages 1/2/3/5 — plan gaps found, union-extent rationale, Tagged[str] theatre wiring gap
metadata:
  type: project
---

Implemented 2026-10-05 (branch `feature/multi-theatre-afghanistan`, commits `0515e05`..`9c72256`).
Stage 4 (live `coord.LOtoLL` probe) is a user task, not attempted — projection stays
`confidence="provisional"`.

**Plan test-impact list was incomplete, in the direction that matters.** The plan named only the
three `build/pipeline.py`-monkeypatching tests as needing a `theatre` kwarg fix. It missed
`test_towns_lua.py`/`test_beacons_lua.py`, which call `parse_towns_lua`/`parse_beacons_lua`
directly and `monkeypatch.setattr` the (now-dict) `EXPECTED_*_COUNT` module constants — would
have silently replaced the dict with a bare int if not caught. Found by grepping every call site
before starting (the role's own step 1b: treat the plan's test-impact list as a hypothesis, grep
for what it missed).

**Plan's "context already established" section overstated how far an existing data path
reached.** It said mission-interpreter's `Tagged[str]` `theatre` field "carries through to...
`body-layer/src/belief/mission_phase.py`'s `load_mission_understanding`" — read naturally, this
implies that function already parses `theatre`. It did not; `load_mission_understanding` only
ever parsed `phases`/`route`. The field existed in the JSON artifact (confirmed against
`mission-interpreter/src/runtime/compact.py`), just not in body-layer's own loader. Added
`TaggedTheatre`/`_parse_theatre` to `mission_phase.py` as part of Stage 5 (the plan's own Stage 5
prose reads `mission_data.theatre.value`, so this was clearly in-scope, just not flagged as a gap
in the "already established" framing). Lesson: "X already carries through to Y" in a plan's
context section is a claim about data reachability, not about whether Y's code actually reads
it — verify the actual parsing function, not just that the field exists somewhere upstream.

**Region-extent union (towns.lua + beacons.lua) vs. beacons-alone was a real, measurable
difference, not just a safety margin.** Afghanistan's beacons-only z-min (-504,146, per the
2026-10-04 recon note) vs. the union's z-min (-513,487.2, from
`tools/derive_afghanistan_full_region.py`'s real run) differ by ~9.3km — a beacons-only region
would have clipped real Afghan territory a town actually sits in. Confirms the main-loop
amendment's reasoning with a real number rather than just trusting the stated rationale.

**A `Tagged[str]` field (plain-string `value`) cannot reuse a dict-shaped-value unwrap helper.**
`mission_phase.py`'s existing `_unwrap_tagged` asserts `value` is a `dict` (phases/route's value
shape). `theatre`'s `Tagged[str]`'s `value` is a plain string — needed a separate
`_parse_theatre`/`_unwrap_tagged_str`-shaped helper, not a generic fix to `_unwrap_tagged`.

**mypy narrows `argparse.ArgumentParser.error`'s typeshed `NoReturn` correctly across an
`Optional` field set on a non-Namespace dataclass.** `if mission_data.theatre is None:
parser.error(...)` followed by `mission_data.theatre.value` passed `mypy --strict` with no
`assert`/cast needed — confirms this pattern (used elsewhere in the codebase for `args.*`
Namespace attrs, which are `Any` anyway) also works for a real typed `Optional` field, not just
`Any`-typed argparse attributes.

**A full ~1GB `.routes` + 288-tile SRTM `afghanistan-full` build takes ~82 minutes end to end**
(real run): towns/beacons near-instant, OSM overlay 85.9s, routes 320.2s, road junctions
**1751.1s (~29min, the known-slow stage)**, SRTM grid 136.8s, terrain semantics (ridge/valley)
**2640.2s (~44min)** — terrain semantics now dominates even more than junctions, because (see
below) it ran at all.

**`syria-full`'s own RUN.md §3.3 stage table is stale**: it says stage 8 (ridge/valley) is
"skipped" without `--probe-output`. It ran for `afghanistan-full` with real counts
(ridge=634867, valley=551657) — a later milestone (landform-geomorphons) generalized ridge/
valley derivation to run off the primary SRTM grid directly, after that table was written.
Flagged in the new Afghanistan RUN.md section and the dated research note; not fixed in Syria's
own section (out of this plan's scope — a future RUN.md pass should reconcile it).

See `plans/multi-theatre-afghanistan/implementation.md` for the full file list and checks.
