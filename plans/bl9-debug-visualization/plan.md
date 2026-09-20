### Goal
Give the next sortie a per-object, per-poll record of why the naked-eye channel did or did not
admit each DCS ground-truth object, and how what it did admit was folded into belief — so
detection-range calibration becomes a measurement ("failed medres at 3.4 km, passed at 2.1 km")
instead of a pilot's recollection of when a callout happened.

### Recommendation: trace first, no live view in this milestone
The calibration question ("why did he not see that?") is answerable from a per-poll gate record
read after landing — it does not need to be watched in real time. A live view would need its own
render surface competing with DCS/VR during the flight the pilot is actually flying, plus a
rendering pipeline this project does not have; that is a materially bigger build for a question a
post-flight trace already answers as well, arguably better, since a trace can be grepped, plotted,
or diffed rather than only glanced at mid-approach. Recommendation: **ship the trace and a
post-flight summarizer only.** If the trace proves insufficient after a real flight — e.g. the
pilot needs to correlate a gate outcome with what was on their own screen at that instant, which a
static log can't give them — a live or replay-driven visual becomes a well-justified slice 2, not
a guess built ahead of the evidence that would justify it. Flagged as a decision below in case the
user weighs this differently before flying.

### Design: the detection chain is already gate-ordered, so tracing is instrumentation, not a new mechanism
`visibility.check_visibility` already evaluates, in order, cockpit mask -> angular-size/range-cap
-> terrain LOS, and returns `None` on the first failing gate (`perception/visibility.py`). The
first-failing-gate *is* the answer to "why did he not see that" — no extra computation is needed
to get it beyond noting which check failed first, because the existing short-circuit already knows
that. `NakedEyePerceptionSource.poll()` runs this gate for every `LoGetWorldObjects` candidate that
survives `filter_ownship` (i.e. every ground-truth object DCS reports minus the player's own
aircraft), so instrumenting this one call point gives full ground-truth coverage for the naked-eye
channel. The scope/hybrid channel has no comparable geometric gate chain (it either has a real
HelperAI detection-existence signal or it doesn't) — out of scope, noted under Risks.

The angular-size and range-cap checks are one arithmetic expression in the current code
(`min(NAKED_EYE_RANGE_CAP_M, size_m / threshold_rad * BINOCULAR_RANGE_MULTIPLIER)`), not two
separable gates — the trace reports the computed `range_threshold_m` plus which term of the `min`
bound it, rather than inventing a code-level distinction that doesn't exist. This still recovers
the two distinct *reasons* the user asked for ("outside the range cap" vs "angular size too small
for this tier") without restructuring `check_visibility`.

### Where ground truth and belief are allowed to meet, and where the line is drawn
Everything computed above (candidate geometry, gate outcome, achieved tier) lives entirely inside
`perception/` and is ground truth by construction — no invariant is at risk there, since
`perception/` already holds ground truth today (`WorldObjectCandidate`, `VisibilityResult`).

The boundary this plan is the first to actually straddle is the join against belief: to show
"what Petrovich believed" next to "what was there," the trace has to also read
`belief.contacts.Contact` state for the same poll. That join is real, but it is **read-only and
one-directional**: a new orchestration-layer module sits beside `logger.py` (not inside
`perception/` or `belief/`) and, after each poll's `run_once()`, reads (a) this poll's
`DetectionTrace` records from the perception side and (b) `store.contacts` (already a public
property) to resolve which `Contact` each admitted object's `Observation.id` ended up in, via
`Contact.contributing_observation_ids` (already public, already exists for BL-2's own history
tooling — no new belief-side field). It writes both to a file. **It never writes anything back**
— no ground-truth field is ever passed into `ContactStore.ingest`, `Percept`, or any `Contact`
field; the structural boundary `belief/percept.py` already enforces (belief never sees
`Observation.derived_world_position` or a DCS object id) is untouched, because this new module
never calls into `belief/` except to *read* `store.contacts`, the same read `tools.get_contacts`
already performs. `perception/` gains no import of `belief/`; `belief/` gains no import of this
new module or of `detection_trace.py` — the no-omniscience invariant holds for Petrovich (the
brain-facing tools, `Contact`, everything `belief/` computes) exactly as before. This module is
explicitly the one place in the codebase deliberately allowed to hold both sides at once; keeping
it a single, narrow, read-only file is what keeps that permission from leaking anywhere else.

### Format: log every poll, summarize after landing
Log every poll's full gate outcome for every candidate, not only transitions. A transitions-only
log would lose exactly the texture block 2 of the flight card wants — "he could see it the whole
approach but only classified at 2 km" is a *shape* over range, and reconstructing that shape from
a transitions-only log means trusting that no intermediate poll flickered across a boundary
unrecorded. Disk cost is not a real constraint: at a 1 Hz poll and a few dozen candidates, an hour
of flight is a few tens of thousands of small JSON lines, a few MB — cheap, and this is a debug
artifact, not a shipped API, so the format can change freely later.

A raw per-poll JSONL is not what a human reads after an hour of flying, though — ship a small
summarizer (`tools/summarize_detection_trace.py`) that reduces the full log to exactly the table
block 2 wants: per object, the range at which presence/class/type were first admitted, and any
object that was in the candidate pool (survived `filter_ownship`, cleared the cockpit mask, i.e.
was plausibly "on screen") but never reached `ADMITTED` at any tier — the closest this can get
automatically to "you could see it but he never called it," since whether the pilot could
*actually* see it on their monitor is not something code can verify. Log everything; read a
summary.

### Affected Modules / Files
- `body-layer/src/perception/detection_trace.py` (new) — `GateOutcome` enum
  (`COCKPIT_MASK`/`RANGE_OR_SIZE`/`TERRAIN_LOS`/`ADMITTED`), `DetectionTrace` dataclass (object_id,
  object_type, t_sim, true range/bearing, the computed `range_threshold_m` and which term of the
  `min()` bound it, outcome, achieved tier when admitted, cluster member object_ids and
  `observation_id` when admitted), and `DetectionTraceCollector`, a small mutable accumulator
  `check_visibility`/`NakedEyePerceptionSource` append to. Pure perception-layer types — no
  `belief/` import, matching `source.py`'s existing perception/belief boundary rule.
- `body-layer/src/perception/visibility.py` — `check_visibility` gains one additive parameter,
  `trace: DetectionTraceCollector | None = None` (default `None`, true no-op, same pattern
  `overlay_client`/`speech_client` already use elsewhere in this codebase). At each of the three
  gates, if `trace` is set, records that gate's outcome before returning/continuing. No change to
  the function's existing return value or gate order.
- `body-layer/src/perception/naked_eye_source.py` — `NakedEyePerceptionSource` gains one additive
  field, `trace_sink: DetectionTraceCollector | None = None`. `poll()` passes it into every
  `check_visibility` call, and — after `cluster_candidates` runs — annotates each admitted
  candidate's trace record with its cluster's member object_ids and the emitted `Observation.id`,
  using data `poll()` already has in hand (no new computation). `None` (default) leaves this
  module's existing behavior, including its exact emission timing, untouched.
- `body-layer/src/detection_trace_writer.py` (new) — the one module allowed to see both ground
  truth and belief (see "Where ground truth and belief are allowed to meet" above). Given a
  `DetectionTraceCollector` and a `ContactStore`, resolves each admitted object's `Contact.id` via
  `Contact.contributing_observation_ids` and appends one JSON line per candidate per poll to a
  file, buffered and flushed every few polls (not every line) so disk I/O never sits on the poll
  loop's critical path. Read-only against `ContactStore` — never calls anything that mutates it.
- `body-layer/src/logger.py` — `--detection-trace PATH` (requires `--console` or `--crew-text`,
  `parser.error` otherwise — there is nothing to join against belief without one of those poll
  loops). `_build_sources` gains an optional `trace_sink` parameter threaded to
  `NakedEyePerceptionSource`; `_run_console_poll_loop`/`_run_crew_text_poll_loop` call the writer
  once per `run_once()`, the same hook point `--overlay`'s push already uses. Off by default, a
  true no-op when absent, same additive posture as every other flag in this file.
- `body-layer/tools/summarize_detection_trace.py` (new) — post-flight reducer, not a test; reads
  the JSONL and prints the per-object first-admitted-range table plus the never-admitted-but-in-FOV
  list. Mirrors `tools/speak_samples.py`'s existing "dev acceptance aid, not a test" posture.
- `body-layer/tests/test_detection_trace.py` (new) — gate-outcome classification per case
  (mask/range-or-size/LOS/admitted, including which term of the `min()` bound); the
  behavioral-equivalence check below; the belief-join logic against a small in-memory
  `ContactStore`.
- `body-layer/CLAUDE.md` — document `--detection-trace`, same convention every other flag in this
  file already follows.

### Implementation Plan
1. `detection_trace.py` — `GateOutcome`, `DetectionTrace`, `DetectionTraceCollector`. No behavior
   yet, just the types and an accumulator with a `record_gate`/`record_admission` API.
2. Instrument `check_visibility` with the optional `trace` parameter. Test: every existing
   `test_visibility.py` case still passes unmodified (proves the no-op default is truly inert);
   add new cases asserting the right `GateOutcome` and threshold detail per failure path.
3. Wire `trace_sink` through `NakedEyePerceptionSource.poll()`, including the post-clustering
   annotation step. Test against fixtures with 1, 2, and >2 objects landing in one cluster, so the
   "merged into another contact by clustering" outcome is exercised directly.
4. `detection_trace_writer.py` — the belief join and JSONL writer, buffered flush. Test the join
   against a small `ContactStore` built from a couple of `poll()` cycles, asserting object_id ->
   observation_id -> contact_id resolves correctly, including a case where two objects fold into
   one contact and a case where continuity is not resolved (fresh contact).
5. Wire `--detection-trace` into `logger.py`'s two poll loops. `main()`'s CLI wiring stays
   untested by design, matching this file's existing convention — `_build_sources` and the writer
   call itself are the tested surface.
6. **Behavioral-equivalence check (the "how will I know it doesn't perturb what it measures"
   answer)**: run `replay.py` over an existing committed fixture sequence twice, once with
   `trace_sink=None` and once with a real collector attached, and assert the resulting
   `Observation`/`Contact`/`Event` streams are identical (same ids, same counts, same order) byte
   for byte. This is the test that actually retires the risk, not an inspection of the diff by eye.
7. `tools/summarize_detection_trace.py` — the post-flight reducer. No test suite obligation
   (matches `speak_samples.py`'s precedent), but run it once against a replay-generated trace file
   as a smoke check before calling this done.
8. Update `body-layer/CLAUDE.md`.

### Risks & Unknowns
- **Scope/hybrid channel is untraced.** `HybridPerceptionSource` has no geometric gate chain to
  instrument — a HelperAI detection either exists or it doesn't. A miss on that channel has no
  "why not" this trace can answer. Acceptable: the sortie's calibration block (2) is specifically
  about the naked-eye channel's newly-changed thresholds.
- **JSONL volume over a long flight** is unbounded by this design (no rotation/trimming). Acceptable
  for a single-sortie debug artifact; would need attention if this became a standing always-on tool.
- **The never-admitted-but-in-FOV list in the summarizer is an approximation of "the pilot could
  see it,"** not a verified one — code can confirm an object cleared the cockpit mask and range
  cap; it cannot confirm the pilot's monitor actually rendered it large enough to notice. State
  this limitation in the summarizer's own output, not just here, so a reader doesn't over-trust it.
- **Buffered-flush writer and an unclean process exit** (crash, Ctrl-C mid-flight) could lose the
  last unflushed batch. Flush cadence should favor "a few polls" over "as rarely as possible" —
  worth deciding a concrete number (e.g. every 5 polls / ~5s) during implementation rather than
  leaving it a guess; not consequential enough to gate the plan on.

### Decisions Requiring User Input
- **Trace-only vs. trace-plus-live-view for this milestone.** Recommendation above is trace only,
  live view deferred until a real flight shows the trace insufficient. Confirm before
  implementation, since it's cheap to build small now and expensive to bolt a live view on later
  if it turns out to be wanted anyway.
- **Flush cadence and whether the JSONL path should default to something under a
  `body-layer/data/`-style gitignored location** versus requiring an explicit `--detection-trace
  PATH` with no default (current plan: no default, matching `--mission-understanding`'s existing
  explicit-path convention) — low-stakes, but worth a one-line confirmation.

### Second-order effect
This trace is the evidence base the cones/optics milestone's slice 1 ("the cone test and the
optics table," `body-layer/ROADMAP.md`) needs to set its FOV/magnification constants from a real
flight instead of another screenshot ladder — and it is also the mechanism that turns the
contact-separation defect (sortie block 3) from "did they merge, yes/no" into "at what range did
they merge, and did closing the range ever split them" — both future calibration passes become
inspect-and-adapt against this log rather than against memory.
