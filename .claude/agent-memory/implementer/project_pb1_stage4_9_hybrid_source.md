---
name: pb1-stage4-9-hybrid-source
description: PB-1 stages 4-9 (2026-09-08) -- HybridPerceptionSource, association.py, HelperAI wire parser; key non-obvious choices
metadata:
  type: project
---

Built `plans/pb1-perception-logger/plan.md` stages 4-9 (the redesigned hybrid, superseding the
original two-tier `petrovich_feed.py`/`proxy.py` split after Session 4's live spike found every
native-geometry channel dead and only HelperAI's classification text alive). See
[[project_pb1_stage2_3_body_layer]] for stages 2-3's scaffolding this builds on.

**Key non-obvious choices:**

- The recursive HelperAI wire format (`-----...-----\n<name>\n<value-if-any>\nchildren are
  {...}`) has no literal example dump anywhere in the research notes -- only prose description.
  The parser (`aircraft-layer/src/schema/petrovich_indication.py`) was built from that prose
  description alone (recursive-descent, degrades gracefully on unrecognized structure rather than
  raising) and its own hand-built test fixtures. If a real captured dump ever surfaces, diff it
  against this parser's assumptions before trusting it blind.
- `association.py`'s "one is unambiguously top-scored (score margin above a threshold)" line is
  ambiguous between "strict inequality" and "beats by more than some positive margin." Implemented
  as `TYPE_MATCH_TIE_MARGIN=0` (strict-tie-only counts as ambiguous) -- a named, tunable constant,
  not a hardcoded interpretation, so this is a one-line change if the plan author disagrees.
- `association.py` deliberately computes bearing/range *inside* `associate()` (needed anyway for
  the plausibility filter), not in `hybrid_source.py` after the fact -- keeps `HybridPerceptionSource`
  genuinely thin composition, matching the plan's own framing.
- Debounce semantics were left as "an implementation detail, not architectural" by the plan.
  Chose: reset debounce state whenever `middle_list_text` goes empty, so a detection that
  disappears and later reappears with *identical* text still re-emits (not just on any text
  *change*). Flagged as a judgment call in the implementation log in case live testing wants a
  different policy (e.g. periodic keep-alive re-emit).
- `logger.py`'s new `main()` CLI entrypoint is intentionally untested (same posture as
  `aircraft-layer/src/collector/__main__.py`'s own `main()`) -- the logic it wires
  (`PerceptionLogger`, `HybridPerceptionSource`) is fully tested; the poll-loop driver itself
  isn't.
- `WorldObjectCandidate` (in `association.py`) intentionally does NOT reuse aircraft-layer's
  `schema.WorldObjectSample` -- body-layer's `pyproject.toml` `mypy_path`/`pythonpath` only
  include its own `src` + `world-model/src`, not `aircraft-layer/src`, so there's no import path
  to aircraft-layer's schema types at all. Body-layer always works from the raw dict
  `aircraft_client` returns and builds its own lightweight dataclass, same pattern
  `OwnshipState.from_telemetry_dict` already established.
- `geometry.range_m` includes the altitude component (slant range) -- tripped up a first draft of
  `test_association.py`'s fixtures (expected flat ground distance, got slant range). Test
  candidates now default to ownship's own altitude so expected values stay simple integers.
