---
name: m5-stage4-validation-and-resync-fix
description: M5 Stage 4 validation + debugger resync false-positive fix review outcome and reasoning
metadata:
  type: project
---

Reviewed 2026-09-04: M5 Stage 4 validation (`fbb2c80`) + Debugger's same-day resync
false-positive fix (`527a0e8`, `56ff90c`, `c237d26`). Verdict: **APPROVED**, no required fixes,
one optional (test fixture literal fidelity — see below).

**What held up well:**
- All 8 checklist bullets genuinely addressed; R*Tree-vs-brute-force correctly identified as
  already satisfied by Stage 1 rather than padded with redundant new work.
- Two "surprising number" investigations (DCS-vs-OSM displacement ~5m vs ~1.2km predicted;
  coverage-mismatch sampling bug) were both real, correctly root-caused, and the explanations
  checked against the actual code (`ingest_roadnet.py`'s clip-keeps-whole-route rule vs
  `ingest_osm`'s fully-inside-bbox rule) rather than taken on the implementer's word.
- The resync fix (`container.py::_triple_plausible` rejects nonzero magnitude < 1e-6) is
  correctly scoped, doesn't over-tighten (exact 0.0 still accepted, pinned by a dedicated test),
  and the `.rn4` "shared function" framing checks out structurally even though M5's `.rn4`
  parsing never actually calls `find_next_point_block` (decoding `.rn4` geometry is an explicit
  M5 non-goal) — so no untested `.rn4` behavior risk exists this milestone.
- Corrections were done honestly: dated "Correction" section appended (not editing away original
  numbers), before/after table, debugger's own residual doubt about ~27 more possible
  false-positives stated in three cross-linked places, not buried.

**Judgment call worth remembering:** declined to block Stage 5/6 on a systematic per-route
audit of the remaining ~14,833 routes despite the debugger's own flagged doubt. Reasoning: the
fix closed a *confirmed* failure signature and was verified store-wide (zero remaining
denormalized points); Stage 4's independent cross-subsystem check (getSurfaceType vs .routes,
median 129m agreement) is itself strong indirect evidence the remaining geometry is sound; and
a full audit is theatre-wide effort disproportionate to what M5 actually needs (in-region
nearest-road distance/orientation, not a routing-grade completeness guarantee). Flagged into M6
backlog instead. If a future milestone needs road *connectivity/routing*, revisit this — that's
exactly where undetected garbage routes would start to matter more.

**Minor finding, not blocking:** regression test fixtures in `test_roadnet_container.py`/
`test_roadnet_routes.py` (commit `527a0e8`) encode the *original* 2-garbage-point version of
feature id=3711's corruption; a later same-day correction (`56ff90c`) revised the real count to
3 points, but the test literals were never updated to match. Also one reconstructed test triple
places a real feature's z-value into the y-slot (y isn't preserved in `geom_json` at all, so
perfect fidelity wasn't fully recoverable). Doesn't affect what the tests prove — worth a
tightening pass next time `roadnet` is touched, not worth blocking on.
