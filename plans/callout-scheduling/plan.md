<!-- doc-provenance:start -->
**Decision for:** [[AA-1.6]]
<!-- doc-provenance:end -->

### Goal

Replace the current "render every unacknowledged event, every poll, all at once" callout path with
a speech-time scheduler that picks **one** thing to say when the previous line ends, re-renders it
from *current* belief, drops it if it has gone stale, and collapses several indistinguishable
contact reports into one group callout.

Fixes two linked 2026-09-21 cones 2C sortie findings (`todo/todo.md`, "Callouts must not be
backlogged" and "Aggregate repetitive callouts"). They are one design: aggregation shrinks the
candidate set the scheduler chooses from, and the scheduler decides whether an aggregate is still
true at the moment it is spoken.

---

### What is actually broken today

`CrewConsole.drain_events` (`belief/crew_console.py:323`) iterates `store.unacknowledged_events`,
calls `belief.speech.route_event` on each — which renders **and acknowledges** — and hands the whole
list to `_print` in one batch. `_print` pushes every line to the overlay and to
`speech_client.push_speech`. Playback serialisation happens two HTTP hops away, in
`aircraft-layer`'s `AudioPlaybackSender` FIFO queue.

So the text of a callout is frozen at `tick()` time and the delay before it is heard is however
long the downstream queue is. That is precisely the pilot's "12 o'clock when I had already flown
past it". Nothing in body-layer knows or models that Petrovich is still talking.

**Existing mechanisms checked before designing new ones** (none of them is a global speech pace, so
none of them is the missing piece, but each constrains the constants chosen below):

| mechanism | where | scope |
|---|---|---|
| `EVENT_COOLDOWN_S = 15.0` | `belief/events.py:104` | per `(contact, kind)`, suppresses *event creation*, not speech |
| `SCAN_CYCLE_PERIOD_S = 16.0` / `FOCUS_DWELL_S = 2.0` | `perception/gaze.py` | free-scan revisit cadence |
| `OBSERVED_WINDOW_S` (= 16.0), `POSITION_HALF_LIFE_S = 30.0`, `LOST_THRESHOLD_S = 120.0` | `belief/decay.py` | certainty ladder, position confidence |
| `IDENTITY_HALF_LIFE_S = 600.0` | `belief/decay.py` | classification/cardinality confidence |
| `AudioPlaybackSender` FIFO + urgent preempt | `aircraft-layer/src/collector/audio_sender.py` | device contention only, on the Windows box |

Seven contacts each produce their own event, each below its own per-contact cooldown — which is why
seven technically-correct lines were emitted in a row. There is no cross-contact mechanism at all.

---

### Design

#### 1. The decision moves to speech time; the queue holds events, never text

A new `belief/callouts.py` owns a `CalloutScheduler`, held as one more `CrewConsole` field.
`drain_events` stops rendering and becomes a thin delegate:

- **The candidate set is not a queue we build.** It is `store.unacknowledged_events`, filtered —
  i.e. the *belief store itself* is the backlog, re-read every poll. The scheduler holds only
  (a) `busy_until_sim: float`, and (b) `_consumed: set[str]` of event ids it has deliberately
  dropped as stale. No pre-rendered text is ever stored. This is the whole fix for finding 1: there
  is nothing to go stale, because nothing is rendered until the instant it is spoken.
- **`tick(now_sim) -> list[str]`**, called from the same post-`ContactStore.tick()` hook point
  `drain_events` uses today:
  1. If `now_sim < busy_until_sim`, return `[]`. Petrovich is talking.
  2. Build candidates: unacknowledged events whose kind has a template
     (`CONTACT_DETECTED` / `CONTACT_REACQUIRED` / `CONTACT_CLASSIFICATION_CHANGED`), skipping the
     no-template kinds outright rather than re-rendering them to `None` every poll as today.
  3. Expire: any candidate older than `CALLOUT_MAX_AGE_S` is added to `_consumed` and dropped —
     never spoken, and (deliberately) **never acknowledged in the store**, so a future brain's
     `poll_events` still sees it. Body only acks what body actually said; that rule is unchanged.
  4. Group (section 4) and rank (section 3); take the best one.
  5. Render **now**, against current belief, via `route_event` / the new group renderer. If the
     render returns `None` (contact gone, merged away), consume and try the next candidate.
  6. `busy_until_sim = now_sim + estimate_speech_duration_s(text) + INTER_UTTERANCE_GAP_S`.
  7. Return the one line (or the one group line) for `_print`.

At the 1 Hz poll rate (`logger._DEFAULT_POLL_INTERVAL_S`) and a ~2–4 s utterance, this yields one
callout every few seconds, always about something believed true within the last
`CALLOUT_MAX_AGE_S`.

#### 2. Replay determinism — the sharpest constraint

**The scheduler must never learn when audio actually finished.** A real playback-completion signal
would have to come back from the Windows box through `audio-adapter`, is wall-clock timed, does not
exist when `--speech-audio` is off, and is unreproducible under replay. It is rejected outright.

Instead, occupancy is **modelled in sim time from the text itself**:

```
estimate_speech_duration_s(text) = MIN_UTTERANCE_S + len(text.split()) / SPEECH_RATE_WPS
```

A pure function of the string. Every piece of scheduler state is a sim-time float or an id set
derived from events; no `time.time()`, no thread, no I/O. Replaying the same recorded stream
therefore produces a byte-identical sequence of spoken lines — which is a test, not a hope
(see stage 4).

Consequences to accept explicitly:
- A paused sim freezes the scheduler. Correct — belief is frozen too.
- The estimate will drift from real playback. It only has to be close enough that lines do not pile
  up; `INTER_UTTERANCE_GAP_S` absorbs a small under-estimate, and the downstream FIFO absorbs the
  rest without producing staleness, because at most one line is ever in flight.
- Scheduling applies **regardless of which sinks are attached**. One crew voice, one channel: the
  overlay mirror is a transcript of what was *said*, so holding a line back holds it back
  everywhere. `--overlay` without `--speech-audio` therefore also gets quieter. Stated assumption,
  not silently chosen.

#### 3. Priority — an explicitly disposable placeholder

No threat model is built here. `docs/concept/threat-levels.md` is filed and needs coalition
inference, which is gated. But the sort key is shaped so that band slots in as the *first* element
later without touching anything else:

```
callout_priority(facts, event, now_sim) -> tuple[int, int, float, float]
    (threat_band,        # constant DEFAULT_BAND today — the one line threat-levels.md replaces
     -attention_rank,    # priority > watch > normal > ignore
     range_m,            # nearer first
     -event.t_sim)       # newer first
```

Rationale for each surviving key, so none of them reads as invented:
- **Attention** is the crew's own expressed interest, already first-class on `Contact`, and already
  used as a usefulness signal by `speech._cardinality_phrase(attended=...)`.
- **Proximity** is what goes stale fastest and what the pilot can least afford to hear late.
- **Newest-first** is what makes "backlogged" impossible by construction. Combined with
  `CALLOUT_MAX_AGE_S` expiry, starvation of an old candidate is bounded and is the intended
  outcome, not a bug: stale things are supposed to die unspoken.

`threat-levels.md` also independently supports section 4 — *"Low priority units can get a slower and
less granular response"* is aggregation, described before this plan existed.

#### 4. Aggregation — group in report space, not in world space

**Do not reuse `perception.clustering.cluster_candidates`.** Two reasons, and the second is the
invariant:
- It answers a different question. Clustering asks whether two *live candidates* are optically
  resolvable apart (magnitude: one target width). Callout grouping asks whether two *reports* would
  be indistinguishable to a listener (magnitude: the reporting quantisation — a 30° clock bucket, a
  rounded range word). `belief/association_over_time.py`'s own docstring already argues exactly this
  distinction, at length, after Stage 3b-i was reverted for collapsing the two.
- `ClusterCandidate` carries ground-truth positions. `belief/` must not see those
  (`belief/percept.py`'s structural boundary). The import direction `belief -> perception` is legal
  (eleven existing imports), so this is not a layering objection — it is a no-omniscience one.

The grouping rule is computed entirely from `belief.tools.describe_contact` facts:

> Two contact reports merge when they would render the **same unit-type word**
> (`speech._unit_type_display`), the **same range word** (`speech._format_range_km`, so
> `"very close"` never merges with `"0.5 kilometres"` — they *sound* different), and their clock
> positions are within `CALLOUT_GROUP_CLOCK_SPAN_HOURS` (1, i.e. 30°, the same bearing quantum
> `association_over_time` already treats as one bucket), with 12↔1 wraparound.

Single-link within a `(word, range word)` bucket, capped at `CALLOUT_GROUP_MAX_SPAN_HOURS` (2) total
span — a chaining cap `perception/clustering.py` deliberately still lacks, cheap to have here
because the bucket is tiny.

Rendering an aggregate reuses what already exists rather than adding a second phrasing path:
- group interval `lo = sum(member.cardinality.lo)`, `hi = sum(member.cardinality.hi)` — the same
  lower-bound idea as `tools._estimated_units_lower_bound`, per group;
- fed into the existing `speech._cardinality_phrase` / `_plural_unit_type_display`, so the register
  stays hedged ("several infantry", "a couple of trucks") and an exact number is only ever spoken
  under the existing `attended` rule — tightened here to *every* member attended and every interval
  exact, so a group never manufactures precision;
- clock/range taken from the **nearest** member (a crew reports the near edge);
- semantic enrichment fragment dropped for groups (one enrichment fact about one member is not true
  of the group).

**What is lost, and what is not.** Nothing in belief: the individual `Contact`s are untouched, still
individually addressable by `find_contact` / `status <id>` / `watch <id>`, and no group entity is
created or persisted. Aggregation is a **speech-time view**, not a new state. What is lost is
per-member detail inside one line — which is why the merge rule requires the *same unit-type word*:
a BTR-70 among infantry never disappears into the group, it keeps its own line.

Applied to the sortie transcript: lines 1/2/3 merge ("three infantry, 12 o'clock, 0.5 kilometres"),
5/6 merge ("a couple of infantry, 2 o'clock, very close"), and 4 and 7 stay separate — they are
`CONTACT_CLASSIFICATION_CHANGED` lines about one identified thing each, which are never aggregated.
**7 lines becomes 4, not 2.** The remaining gap is closed by the scheduler, not by grouping: at one
line per ~3 s, the later candidates of a fast pass expire before their turn. Do not expect
aggregation alone to hit the pilot's "two would do".

#### 5. The urgent path

`UrgentCall` keeps bypassing everything — it never enters the candidate set, is never grouped, and
is never blocked by `busy_until_sim`. An aggregate never becomes urgent: urgency, when it exists,
will be a property of a specific threat, and a group callout is by construction a routine
environmental report.

**The one real coupling, easy to miss:** an urgent push clears the downstream queue and kills
in-flight playback (`AudioPlaybackSender.interrupt`). The scheduler must therefore **reset its own
occupancy** when an urgent line goes out — `busy_until_sim = now_sim + estimate(urgent_text)` —
otherwise it keeps believing a routine line is still playing that the audio layer has already
destroyed, and stays silent for seconds after the urgent call. `_print(bypass_gate=True)` is the
single place that knows this happened.

---

### Affected Modules / Files

- `body-layer/src/belief/callouts.py` (**new**) — `CalloutScheduler` (`busy_until_sim`,
  `_consumed`, `tick`, `note_urgent`), `estimate_speech_duration_s`, `callout_priority`,
  `group_candidates`, and the five constants below. Pure: sim-time floats and id sets only.
- `body-layer/src/belief/speech.py` — add `render_group_report(facts_list) -> OutgoingSpeech`,
  built from the existing `_cardinality_phrase` / `_plural_unit_type_display` /
  `_format_range_km` helpers. No change to any existing single-contact path; module docstring's
  "No contact clustering" note gets superseded with a pointer to this plan.
- `body-layer/src/belief/crew_console.py` — new `scheduler: CalloutScheduler` field;
  `drain_events` delegates to `scheduler.tick` and returns at most one line (or one group line);
  `_print` calls `scheduler.note_urgent(...)` on the `bypass_gate=True` path. Group speech must
  `acknowledge_event` **every member's** event, not just the one rendered.
- `body-layer/src/belief/events.py` — no code change; the no-template kinds are now filtered by
  the scheduler rather than round-tripped through `route_event` each poll.
- `body-layer/tests/test_callouts.py` (**new**), `tests/test_crew_console.py` (extend),
  `tests/test_speech.py` (extend), plus one committed fixture replaying the 2C transcript.
- `body-layer/ROADMAP.md`, `todo/todo.md` — tick the two 2C findings when this merges.

New constants, all placeholders and all stated as such, chosen against the table above:

| constant | value | why this number |
|---|---|---|
| `CALLOUT_MAX_AGE_S` | 10.0 | shorter than both `EVENT_COOLDOWN_S` (15) and `SCAN_CYCLE_PERIOD_S` (16), so an expired candidate about something still present is regenerated by the next scan cycle — expiring is not losing |
| `INTER_UTTERANCE_GAP_S` | 0.75 | a breath; also absorbs a small duration under-estimate |
| `SPEECH_RATE_WPS` | 2.5 | ~150 wpm, uncalibrated |
| `MIN_UTTERANCE_S` | 0.6 | per-line synthesis/transport overhead, ~the measured `say` latency from `plans/tts-voice-output/plan.md` Decision 2 |
| `CALLOUT_GROUP_CLOCK_SPAN_HOURS` / `_MAX_SPAN_HOURS` | 1 / 2 | the 30° clock bucket already used by `association_over_time`, plus a chaining cap |

---

### Implementation Plan

**Slice A — the scheduler (fixes finding 1 on its own, and is independently shippable).**

1. `belief/callouts.py` with `estimate_speech_duration_s`, `callout_priority`, and a
   `CalloutScheduler` that selects exactly one candidate per free slot, re-rendering through the
   existing `route_event`. No grouping yet. `drain_events` delegates; `_print` resets occupancy on
   urgent.
2. Tests: nothing is spoken while `busy_until_sim` is ahead; an expired candidate is never spoken
   and never acknowledged; a candidate whose contact vanished is skipped and the next one is taken;
   the urgent path is unblocked and resets occupancy.

**Slice B — aggregation (depends on A's candidate structure).**

3. `speech.render_group_report` + `callouts.group_candidates`; the scheduler ranks groups and
   singles in the same pass (a group's priority is its best member's). Multi-member speech
   acknowledges every member event.
4. Tests: the committed 2C transcript fixture renders 4 lines, not 7; a mixed-type pair does not
   merge; `"very close"` never merges with `"0.5 kilometres"`; a group never speaks an exact count
   unless every member is attended and exact; and the **replay-determinism test** — replay the same
   fixture twice and assert the spoken sequence is identical (the analogue of BL-9's
   `test_trace_sink_does_not_perturb_...`).

**Slice A is the seam.** It is a coherent merge on its own: it fixes the pilot's stated defect,
already reduces the line count via expiry, and carries all the replay-determinism risk. B is
phrasing plus a grouping predicate on top of a stable base.

---

### Risks & Unknowns

- **Duration estimation drift is the only load-bearing guess.** If `SPEECH_RATE_WPS` is too fast,
  lines will tread on each other's tails in the downstream FIFO (annoying, not stale); too slow and
  Petrovich goes quiet for a beat too long. Only a live sortie settles it — this is a calibration
  item for the next flight, and the constant is isolated so it can move without touching mechanism
  (the "mechanism and calibration never share a commit" rule from BL-2.6).
- **Aggregation needs `relative_now`, i.e. an `EnrichmentContext`.** Without one, clock/range are
  absent and grouping degrades to "no grouping" — correct, but it means a session run without
  enrichment silently keeps the old line count. Assert the `--crew-text` path always supplies it.
- **Line count after this may still be too high**, as shown above (4, not 2). If the next sortie
  still feels chatty, the next lever is a *global* minimum inter-callout interval, not a tighter
  grouping rule — deliberately not built now, because it trades away responsiveness and should be
  bought with live evidence.
- **`unacknowledged_events` is scanned every poll** and grows with never-templated kinds
  (`CONTACT_LOST`, `CONTACT_ATTENTION_CHANGED`) that are never acknowledged. The kind filter makes
  the per-poll cost small but not bounded over a long sortie. Not a problem at sortie length;
  flagged so it is not discovered as one later.
- **No DCS-internals dependency.** Nothing here touches an unverified DCS claim — the playback
  boundary is deliberately not consulted — so no `investigator` pass is needed.

### Second-order effect

This **unblocks** the threat model rather than narrowing it: `callout_priority`'s first tuple
element is the exact hole `docs/concept/threat-levels.md` fills once coalition inference lands, and
"high threat priority units must be prioritized in contact reporting" then becomes a one-line change
instead of a new subsystem. It also **complicates** the group-contact model slightly: there are now
two distinct groupings in the system — `perception.clustering`'s perceptual one and this reporting
one — and a future reader must not unify them. Both docstrings must say so, in the same terms
`association_over_time.py` already uses for the same mistake.

### Decisions Requiring User Input

The user has asked to work independently, so each of these is an **assumption already taken** in the
design above rather than a blocking question. Any of them is cheap to reverse.

1. **Scheduling applies to the overlay too**, not just to audio — the overlay is a transcript of
   what was said, so text and voice stay in lockstep and both get quieter.
2. **An expired candidate is dropped unspoken and left unacknowledged**, so a future brain can still
   see it. Body acks only what body said.
3. **Priority is attention → proximity → recency** with a constant threat band on top. No threat
   reasoning is invented.
4. **7 lines becomes 4, not 2.** If the pilot expects 2 from aggregation alone, expectations need
   resetting before the next sortie rather than the grouping rule being widened.
