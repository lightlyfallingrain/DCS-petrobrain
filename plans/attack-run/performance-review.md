### Performance Review

Whole-feature pass, BL-14 (the attack run), Stages 1–7, immediately before DoD. Reviewed at
`feature/bl14-attack-run` tip `468c7b3`, fast-forwarded cleanly from this worktree's stale base
`f25c57c` (strict ancestor, clean tree, no divergence). No test/lint/type gate was re-run here —
`review.md`'s three passes already ran and mutation-tested all four gates in both subprojects on
this same branch; this pass is cost analysis against the merged code, not a re-verification of
correctness.

**Budget context.** No hard real-time budget applies yet (Petrobrain Runtime has not started). The
only standing figures are `BL-11`'s: poll work ~330 ms → **12.6 ms median**, while the callout
tick's **maximum** went 1,579 ms → **1,615 ms** (median improved 26×, worst case did not improve at
all). Everything below is read against that asymmetry — a median win says nothing about a tail the
same release left untouched.

### Findings

#### `drain_attack_run` / the poll-loop addition when no run is active

- **Location:** `logger.py`'s `_run_crew_text_poll_loop` (the `engage`/`disengage` transition block
  + `crew_console.drain_attack_run(...)`, called immediately before `drain_events`).
- **Measured, not reasoned.** With no run engaged, `runner.attack_run_state is None`, so the
  transition block is two string comparisons against `crew_console.attack_run_transition` (almost
  always `None`) and `drain_attack_run(None, ...)` hits its first line, `if state is None: return
  state`, before touching the task store, the contact store, or `decide_attack_run`. Cost is a
  handful of attribute reads and an early return — no allocation, no store I/O. This is correctly
  ~free in the common case, exactly as the plan's Decision 1/Stage 5 design intends.
- **Action:** none needed. Not measured in wall-clock terms because there is nothing on this path
  to time — the code makes the "idle" case a structural no-op rather than a fast branch through
  real work, which is a stronger guarantee than a microbenchmark would add.

#### `drain_attack_run` / `decide_attack_run` while a run is active

- **Location:** `belief/crew_console.py::drain_attack_run`, `belief/attack_run.py::decide`.
- **Measured by reading the call graph, not timed** (no store scales large enough in this codebase
  to make timing informative — see below for why). Per engaged poll: one `_active_attack_target_task`
  scan (linear over `self.tasks.tasks`, a handful of standing intents — scan/watch/attack, never
  more than a few), one `store.contact(id)` dict lookup (O(1)), one `store.group_for_contact(id)`
  scan (linear over *currently observed groups*, which `GroupStore.group_for_contact`'s own
  docstring says is "always far smaller than the number of contacts"), then `decide_attack_run`
  itself: a handful of `math.sin`/`cos`/`atan2` calls (re-rotation, `alignment_direction`,
  `signed_angular_delta_deg`) and one dataclass `replace`/construction. No store mutation, no
  enrichment call, no world-model query (Decision 4 REVISED deleted the one that would have been
  here). This is cheaper, not more expensive, than the world-anchored path it replaces for this
  purpose, exactly as the plan's Decision 16 "what this costs" section claims — confirmed by
  reading every function on the path, not assumed from the claim.
- **Action:** none needed.

#### Stage 2's per-poll `RelativeDirection` population (every admitted cluster, run or no run)

- **Location:** `perception/naked_eye_source.py::_build_observation`, gated on `live_los_clear is
  True`; `perception/estimation.py::perturbed_relative_direction`; `perception/clustering.py`'s
  `centroid_alt_m`.
- **Measured.** `centroid_alt_m` is one more `sum(...)/len(...)` alongside the existing
  `centroid_x`/`centroid_z` reduction over the same `members` list — O(members), not a second pass.
  The relative-direction block (when the gate passes) is 2 `math.cos`/`math.sin` calls to rotate
  into the ownship frame, plus a call into `perturbed_relative_direction`, which at
  `RELATIVE_DIRECTION_SIGMA_DEG = 0.0` returns its three arguments unchanged on the first `if`
  check — confirmed by reading `estimation.py:157-158`: the perturbation draw (two more trig calls
  plus a deterministic-hash lookup) is **skipped entirely**, not computed and discarded. So the
  real per-admitted-cluster cost is 4 trig calls total, independent of whether a run exists. Against
  `BL-11`'s realised clustering/grouping costs (`group_salient_ids` 1.1 ms median / 5.5 ms max), this
  is noise — it does not even reach the rounding error of those figures.
- **Action:** none needed. This is the cost the plan's Decision 16 named ("one truth-to-truth
  subtraction per admitted cluster per poll") and it is exactly as cheap as advertised.

#### `step`'s per-press candidate ordering — the one real finding

- **Location:** `belief/crew_console.py::_step_candidates` (descriptor filter) and
  `_handle_step`/`_bearing_and_range`/`_signed_delta` (the ordering itself).
- **What is cheap, confirmed by reading:** the ordering primitive itself —
  `signed_angular_delta_deg`, the sort, the stop-at-the-end check — is pure arithmetic over however
  many candidates resolve, and is recomputed from ownship's present position every press by design
  (user direction, not a cacheable "sort once" shortcut; `review.md`'s Stage 4–5 pass mutation-tested
  this and confirmed the recompute is real, not accidental).
- **What is not cheap, and is a real risk at realistic scale.** `_bearing_and_range` (called once for
  the current target and once per "other" candidate) and `_step_candidates`'s own descriptor filter
  (called once per group member, when a descriptor was heard on the selecting command — the common
  case, since the spec grammar is `select target <what> <where>`) both call
  `belief.tools.describe_contact` to get a single `bearing_deg`/`range_m` pair. `describe_contact`
  does not have a narrow "just geometry" path: it runs the **full** enrichment pipeline
  (`_add_enrichment_facts`) whenever `self.enrichment is not None` — which `_handle_step` requires
  before it will even resolve candidates (`if self.enrichment is None: return [...]`). That pipeline
  computes `semantic_facts_for` (cached per contact-id/50 m cell, so repeat calls against an
  unmoving contact are cheap after the first) **and** `terrain_divide_qualifier`, which its own
  docstring states is **never cached** — "ownship-relative... must be recomputed every call."
  Both of `bearing_deg`/`range_m` are then read out of the `relative_now` dict and everything else
  computed (`semantic`, `terrain_qualifier`, `motion_when_seen`) is discarded.
- **This is the same measured pattern as the already-filed `BL-B49`, with a new caller.**
  `BL-B49` measured, against the real `syria-full.sqlite`: `terrain_divide_qualifier` at **6.77 ms
  per contact, never cached**; `semantic_facts_for` at **63.25 ms per contact cold**, cheap once
  warm. `BL-B49`'s own text already predicts this shape: *"designed to increase the rate of exactly
  the query whose cost this entry describes."* `step` is a second instance of that same prediction —
  it was not the caller `BL-B49` was filed against (that was `report`/`_report_scope`), but it pays
  the identical cost through the identical shared function, once or twice per candidate, on every
  press.
- **Scale.** `_find_contact`'s own O(n) linear scan over *all* contacts (not just the group) is
  negligible at the task's cited sortie populations (52–152 contacts; microseconds for a linear
  scan of that size) and is not the driver here. The driver is group size, which this codebase does
  **not** tightly bound: `BL-B61` (class-level composition bucketing, `OP_GROUPSOMETHING`) and
  `BL-B48` (the infantry cohesion bridge merging contacts up to 6 km apart) are both open findings
  that a believed group can legitimately be wider than a real platoon. Taking a illustratively-sized
  group of 15–20 members (not measured against a live sortie — no group that large has been
  recorded in this codebase's own fixtures, so this is a bound from the open defects above, not a
  reproduced number): up to `2G+1` `describe_contact` calls per press, each paying the **uncached**
  6.77 ms terrain term unconditionally — **~210–280 ms of terrain-query cost alone**, before any
  cold-cache `semantic_facts_for` hits. `handle_command` runs inside the poll body (confirmed by
  `BL-B49`'s own citation of `logger.py:1668-1672`, and this feature's `step`/`engage`/`disengage`
  dispatch through the same `handle_command` table), so this is a synchronous stall of perception
  and callouts for that duration, on every `step` press against a large or loosely-grouped formation
  — not a one-time cost.
- **Why this is not a required fix now.** The expensive mechanism is `BL-B49`'s, not something
  `BL-14` introduces — `step` is a new *caller* of a pre-existing, already-filed, architect-owned
  cost. `BL-B49`'s own entry names three candidate mitigations (an enrichment opt-out on
  `get_contacts`, filtering before enriching, caching `terrain_divide_qualifier`) and defers picking
  between them to an Architect pass because "every candidate fix changes a shared tool." Building a
  `step`-local workaround here would either duplicate that fix badly or pick the architecture's
  answer unilaterally, which is exactly the shared-tool blast-radius concern `BL-B49` was filed to
  avoid. The common case (small, cleanly-separated groups — the typical real-world formation) is
  cheap: a handful of candidates, each ~7 ms of uncached terrain cost, is imperceptible against a
  deliberate keypress.
- **Action: MONITOR, and cross-reference.** Recommend `BL-B49`'s entry (or a new backlog item linked
  to it) be updated to name `step` as a second confirmed caller of the same cost, so whichever
  mitigation the Architect eventually picks is sized against both callers, not re-discovered against
  `step` later as if it were new. Worth one line in the acceptance sortie: if `step` against a large
  formation is audibly slow to respond, that is this finding surfacing, not a new defect.

#### `Contact.last_percept` — memory growth

- **Location:** `belief/contacts.py` (`Contact.last_percept`, set in `record()`/`from_percept()`).
- **Measured.** `sys.getsizeof` on this worktree's own `Percept`/`OwnshipState`/`RelativeDirection`
  dataclasses (slots, frozen): 144 + 96 + 56 = **296 bytes shallow** per populated `Percept` (plus
  the handful of boxed floats/strings each already carries, call it ~500–700 bytes all-in — not
  independently re-measured, bounded by the shallow figure above plus known small field counts).
  This is **one overwritten reference per contact, not an accumulating list** — confirmed by reading
  `record()`/`from_percept()`: `self.last_percept = percept`, assignment, never `append`. Against
  `ContactStore`'s existing "full memory, never pruned" posture (`BL-B23`, which left `_contacts`
  untouched for the same reason), this is a fixed per-contact cost that does not grow with sortie
  length, only with contact *count* — at the task's cited sortie populations (52–152 contacts), that
  is on the order of tens of KB for the whole store, not a scale this codebase's own existing
  per-contact state (observation-id lists, sighting spans) doesn't already dwarf.
- **Action:** none needed. Matches `review.md`'s own Stage 1–3 finding (1a), independently
  re-confirmed by measurement rather than accepted from that report.

#### Stage 2's `RelativeDirection` field on every admitted `Observation`, whether or not a run exists

- Covered above (same finding as "Stage 2's per-poll population"). Restating only to answer the
  prompt's explicit question: cost when **no run is active** is identical to cost when one is —
  the gate that populates the field is `live_los_clear is True`, not "a run exists." There is no
  conditional form of this cost to ask for; it runs for every admitted cluster regardless, and it is
  cheap enough (4 trig calls) that gating it on run-activity would save nothing worth the added
  branch. **Not worth making conditional.**

#### `AttackRunState.last_known_target_alt_m`

- **Location:** `belief/attack_run.py::_remembered_target_alt_m`, called from `decide` on every tier-1
  success.
- **Confirmed no lookup.** `percept.ownship_at_observation.alt_m + percept.relative_direction.up_m`
  — both fields already held on the `Percept` object `decide` was handed; no store access, no
  enrichment, one float addition.
- **Action:** none needed.

#### The gaze claim vs. the scan loop's sector computation

- **Location:** `logger.py::_active_gaze`, the attack-run branch (checked before the `scan_area`
  loop).
- **Measured by reading both paths.** The attack-run branch: one linear scan over
  `reversed(tasks.tasks)` to find the live `attack_target` task (same cost class as the `scan_area`
  loop's own scan over the same list), one `store.contact(id)` dict lookup, one
  `alignment_direction` call (the same handful of trig calls `decide_attack_run` already uses), then
  an early `return`. The `scan_area` path it replaces does the same task-list scan plus, depending
  on which directional field fired, a `_SECTOR_CENTER_DEG` dict lookup and comparable angle
  arithmetic. The two paths are the same order of cost — if anything the attack-run branch is
  marginally cheaper, since it returns before the `scan_area` loop's own filtering runs at all.
- **Action:** none needed. Not dearer than what it replaces.

#### Decision 5's suppression gate in `CalloutScheduler.tick`

- **Location:** `belief/callouts.py`, the `_WATCHED_ONLY_KINDS` branch.
- **Confirmed trivial.** One `==` string comparison against `attack_run_target_contact_id`, inside
  an existing per-event loop that already runs regardless of this feature. No new iteration, no new
  store access.
- **Action:** none needed.

### What should be watched on the acceptance sortie

- **`step` against a large or multi-kind formation.** If a `step` press feels sluggish (noticeably
  slower than an ordinary report/follow command), that is the `BL-B49`-class cost above, not a new
  defect — worth one explicit note on the sortie card so it is attributed correctly if it is heard.
  The speech log does not currently carry command-handling latency, only callout content, so this
  would have to be timed separately (a `time.monotonic()` straddle around `handle_command`'s
  `step` branch, or a debug log line) if it needs confirming rather than just listening for it.
- **Tier flap under occlusion.** Not a performance question but adjacent to one worth naming here:
  the plan's own Risks section already documents that one occluded group member silences tier 1 for
  the whole cluster, so "obstructed" will be heard routinely rather than rarely. This doesn't cost
  anything extra (tier 2 is the same cheap arithmetic as tier 1), but a sortie debrief that expects
  "obstructed" to be rare would misread normal behaviour as a defect.
- **The speech log already carries what a cost investigation would need**: attack-run target, tier,
  and both axis errors per utterance (confirmed present end-to-end in `review.md`'s Stage 4–5 pass).
  Nothing further needs adding to the log for the findings above — the one gap (command-handling
  latency for `step`) is a different kind of signal than what the speech log is for.

### Verdict

**APPROVED — MONITOR**

Nothing on the attack-run-specific hot path (the guidance loop itself, the relative-direction
channel, the gaze claim, the suppression gate, the per-contact memory addition) needs a change. One
real finding — `step`'s per-press cost through `describe_contact`'s full enrichment pipeline against
a potentially wide group — is a new caller of an already-filed, architect-owned cost (`BL-B49`), not
a new defect this feature should fix unilaterally. Recommend cross-referencing `step` on `BL-B49`'s
entry and watching for it on the acceptance sortie; no change request is being raised against
Implementer/Reviewer for this pass.
