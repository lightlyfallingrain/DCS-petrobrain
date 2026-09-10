### Goal

Stop the reproduced runaway duplication where two distinct, moderately-separated real objects
(the BL-2.6 gate-widening fix legitimately overlapping their gates) trigger `ContactStore.
ingest`'s "two-or-more candidates → always new contact" policy repeatedly, spawning roughly one
new contact per poll for the rest of the session — by giving the naked-eye channel a cheap,
non-omniscient way to recognise "this is the same object I saw last poll, no gap" and skip the
gate entirely for that case, rather than by re-tuning gate width (which cannot be made correct
for every unit/range combination) or by relaxing the never-guess-merge invariant.

### Decision

**Primary fix: continuity-of-track for the naked-eye channel only** (`todo/todo.md`'s
2026-09-10 backlog item), with a cheap class-compatibility sanity check riding along as defense
in depth. This is a genuine architectural call with real downstream consequences (it is the
mechanism every future milestone's live contact behavior will depend on), so **flagging for
your confirmation, not deciding silently** — see Decisions Requiring User Input. My
recommendation and reasoning:

- Traced concretely against the debugger's own reproduction (two stationary objects, 60 polls,
  moderate heading drift, `emit_mode="every_poll"`): both objects' `object_id` is present, same
  value, every poll with no gap. A same-id-as-last-poll rule keeps each on its own contact for
  the entire session without ever calling `passes_gate`, which is exactly where the ambiguity
  fires today. This is not a hypothetical extrapolation of the backlog idea — it is a direct
  trace against the exact scenario that broke.
- It resolves the structural problem (no single gate radius is right for both a single
  stationary object's bucket-requantisation jump *and* realistic multi-object spacing) rather
  than picking a new constant that is merely less wrong — matching your stated preference
  (`todo/todo.md`) to avoid further range-gate tuning.
- It leaves `association_over_time`'s gate and `ContactStore.ingest`'s never-guess-merge policy
  completely untouched for the case they were built for: genuine re-acquisition after a real
  gap in observation. Continuity only ever *skips* the gate for the zero-gap case; it never
  replaces the gate's fuzzy logic for the has-a-gap case.
- Root cause of the current bug is honestly structural (see debug.md), not a mistake in either
  the 7581928 fix or the Stage 1 invariant — so a fix that removes the *need* for the gate to
  cover the zero-gap case at all is a better answer than adjusting either side of a tradeoff
  that has no correct fixed point.

**Rejected as primary fix, for the record:**

- *Bound/self-limit the ambiguity rule* (candidate 2) — any cap needs a tiebreak rule to decide
  which candidate absorbs the (K+1)th ambiguous percept once the cap is hit, which is exactly
  the best-match guess Stage 1 deliberately refused to build, for exactly the reason it matters
  here: a silently-wrong merge is worse than a visible duplicate. It also treats the symptom
  (unbounded spawning) without touching the cause (the gate legitimately overlapping two real
  objects), so a session that never exhausts the cap still mis-tracks silently below it.
- *Narrow the gate back down, handle bucket-requantisation specially* (candidate 3) — on
  inspection this converges with continuity-of-track anyway: the only reason bucket noise needs
  gate-level robustness at all is the *absence* of a continuity signal for a continuously-visible
  object. Once continuity exists, the single-object bug that motivated 7581928 is moot for any
  object continuity covers, so there's no independent surgical fix worth building alongside it.
  Not pursued as a separate track.

### Boundary reading (needs your sign-off)

The backlog item's title says "using `object_id` within `perception/` only (never crossing into
`belief/`)". Taken completely literally that's impossible: `ContactStore.ingest` (`belief/
contacts.py`) is the only place that calls `passes_gate`, so something has to reach it to skip
that call. What I'm proposing keeps the spirit while touching the letter:

- `object_id` itself never leaves `perception/` — it is consumed only inside
  `NakedEyePerceptionSource` to decide continuity, never serialised onto `Observation`,
  `Percept`, or a `Contact`.
- What crosses is a new optional field, `continues_observation_id: str | None`, carrying a
  *previously emitted `Observation.id`* — a value `Percept` already legitimately carries
  (`percept.py`'s own docstring names `observation_id` as bookkeeping, not a truth field). The
  claim this field encodes is "this report continues that earlier report," which is a fact
  about observation continuity, not a DCS ground-truth fact about the world — the same kind of
  thing a human tracking a target with their own eyes has for free, matching root CLAUDE.md's
  anti-omniscience framing rather than violating it.
- `belief/contacts.py` and `belief/percept.py` do change (see Affected Modules). If you read the
  backlog item's "never crossing into belief/" as a harder constraint than this, say so and I'll
  redesign — the alternative (keeping the skip-decision entirely inside `perception/`) would
  require `perception/` to know about `Contact.id`, which is a worse boundary violation the
  other direction (perception reaching into belief's own identity space).

### Affected Modules / Files

- `body-layer/src/perception/naked_eye_source.py` — `_acquire_every_poll` (the only path that
  matters here; `emit_mode="every_poll"` is what `--console`/`--crew-text` use) already tracks
  `_acquired_ids` across polls. Add a small `_last_poll_object_id_to_observation_id: dict[int,
  str]` field: before updating `_acquired_ids`, compute the continuity set as `(previous
  acquired ids) ∩ (currently visible ids)`; for objects in that set, look up the prior
  `Observation.id` and pass it through to `_build_observation` as `continues_observation_id`.
  For every other emitted object (newly acquired, or acquired-but-was-gapped), pass `None`.
  `on_change` mode's `_acquire_on_change` is untouched — continuity is not populated there (see
  Risk on scope below).
- `body-layer/src/perception/source.py` — add `continues_observation_id: str | None = None` to
  `Observation`. Docstring note: this is bookkeeping about report continuity, never a DCS id.
- `body-layer/src/belief/percept.py` — thread the new field through unchanged (`Percept` already
  carries `observation_id`; add the sibling field, update `percept_of`). No change to the
  "structurally narrower type" argument in the module docstring — this field carries the same
  *kind* of value (`observation_id`) the type already allows.
- `body-layer/src/belief/contacts.py` — `ContactStore`:
  - Add `self._observation_id_to_contact_id: dict[str, str]`, populated alongside
    `contributing_observation_ids` in both `Contact.from_percept`'s and `Contact.record`'s call
    sites inside `ingest` (cheap O(1) index; avoids scanning every contact's
    `contributing_observation_ids` list per percept).
  - `ingest`: if `percept.continues_observation_id` is set and resolves through that index to a
    known contact, `record()` into that contact directly, **skip `passes_gate` entirely** for
    this percept. If it does not resolve (stale/unknown id — should not happen in practice, but
    the id space is not guaranteed by this design to survive e.g. a `ContactStore` reset), fall
    back to the existing gate/ambiguity logic unchanged — never treat an unresolved continuity
    hint as an error.
  - **Defense in depth**: even on a continuity hit, run the existing `class_compatibility` check
    (`association_over_time.class_compatibility`, already used inside `passes_gate`) between the
    percept and the target contact's `last_class_raw`. An `incompatible` result on a same-id
    continuity claim is a strong anomaly signal (id reuse, or the live-stability claim below
    turning out false in some edge case) — fall back to the normal gate/ambiguity path rather
    than trusting continuity blindly. This is the mitigation for the one fact this plan cannot
    fully verify offline (see Risks).
- `body-layer/src/belief/association_over_time.py` — no change to `spatial_gate_radius_m` or the
  gate formula (7581928 stays exactly as-is). Docstring addition only: note that continuity
  (`contacts.py`) is now the primary path for the zero-gap case, and this gate's job is now
  scoped to genuine re-acquisition after a gap — so its own remaining false-merge risk at
  close range is smaller in practice than before, without the module itself changing.
- Tests:
  - `body-layer/tests/test_naked_eye_source.py` — continuity tagging: same `object_id` two polls
    running → second `Observation.continues_observation_id` set to the first's id; a poll gap
    (object drops out of the visible set, later reappears) → `None`; two different objects never
    cross-tag each other.
  - `body-layer/tests/test_contacts.py` — extend `test_two_ambiguous_candidates_create_a_new_
    contact_not_a_merge`'s scenario across many polls per the debugger's recommendation, now with
    continuity populated: two real, ~874m-separated objects, 60 polls, moderate heading drift →
    stays at 2 contacts (the debugger's own repro parameters, now as a permanent regression
    test). A second test keeps the *existing* many-poll ambiguity-without-continuity scenario
    (e.g. force `continues_observation_id=None` every poll, simulating the hybrid channel or a
    channel with real gaps) to confirm the gate/ambiguity policy's current behavior is
    unchanged when continuity isn't available — this is deliberately still capable of the
    runaway shape; that's the accepted residual (see Risks).
  - New test for the defense-in-depth check: same `object_id` continuity claim, but the second
    percept's class is `incompatible` with the contact's `last_class_raw` → falls back to gate
    logic (spawns a new contact via the normal ambiguity path, not a forced merge).

**Explicitly out of scope**: `body-layer/src/perception/hybrid_source.py` (the scope/HelperAI
channel). It has no per-object continuity state today — `associate()` re-resolves each leaf's
text fresh from geometry every poll, with no persisted mapping from a leaf to the `object_id` it
last resolved to. Adding continuity there means first solving "which of last poll's resolved
objects does this poll's leaf-text refer to," a real matching problem in its own right, not a
small addition. The reproduced bug is a naked-eye-channel scenario; scoping this fix there
covers the reported failure. Flagged as follow-up, not silently dropped.

### Implementation Plan

1. **Live verification of the one unconfirmed fact (before or alongside code).** The fix's
   safety case rests on `object_id` being stable, non-reused, across consecutive polls of an
   undisturbed object. Current evidence (`aircraft-layer/research/2026-09-09-...` on the
   unmerged `feature/omniscient-mission-memory` branch, plus this session's follow-up,
   `aircraft-layer/research/2026-09-10-worldobjects-object-id-stability-tacview-confirmation.md`)
   is high-confidence desk research — ED's own doc comment, and now Tacview's current shipped
   `TacviewExportDCS.lua` structurally depending on the same claim with no known defect reports
   — but not a project-run live probe. Per this project's "never run real DCS sessions myself"
   convention, the command to close this gap is yours to run, not mine: deploy the
   `pairs(LoGetWorldObjects())` debug-log `Export.lua` variant described in both research files,
   watch one stationary/slow AI unit for 30-60s at the existing 5Hz rate, confirm a constant key.
   The defense-in-depth class check in Stage 3 below means shipping without this is not unsafe
   (a false continuity claim degrades to the existing gate path, not a silent merge, *provided*
   the reused id also carries an incompatible class — see Risks for the gap that doesn't cover),
   but I'd recommend running it before this reaches live acceptance testing again, given BL-5a
   was already blocked once by this bug class.
2. **Minimal working version.** Add `continues_observation_id` to `Observation`/`Percept`
   (plumbing only, always `None` until Stage 2 populates it) — smallest independently-testable
   slice, confirms the type threads through cleanly with no behavior change yet.
3. **Naked-eye continuity tagging.** Implement the `_acquire_every_poll` continuity-set logic in
   `naked_eye_source.py`. Test in isolation (Stage's own test file) before touching `contacts.py`
   at all — confirms the *signal* is correct before anything consumes it.
4. **`ContactStore.ingest` consumption, with defense-in-depth class check.** Wire the
   observation-id index and the gate-skip path, including the class-compatibility fallback.
   Extend `test_contacts.py` with the debugger's many-poll two-object regression scenario (now
   passing) and the fallback-on-class-mismatch test.
5. **Validate correctness against the exact reproduction.** Re-run the debugger's random-sweep
   harness (already exists in the debug investigation, not merged as a test) against the fixed
   code for both: (a) the specific 874m-separation case that produced 120 contacts, now expected
   to stay near 2; (b) the original single-object bucket-requantisation sweep (2000+ trials),
   confirming continuity doesn't regress that case either (it shouldn't — that scenario is
   exactly the zero-gap case continuity now shortcuts, even more directly than the widened gate
   did).
6. **Refine — docstring/module-boundary write-up.** Update `association_over_time.py`'s and
   `contacts.py`'s module docstrings to state the new division of labor (continuity handles
   zero-gap, gate handles genuine re-acquisition) so a future reader doesn't have to reconstruct
   this reasoning from git history.

### Risks & Unknowns

- **Residual runaway risk, accepted, not fixed by this plan**: two real, nearby objects that
  *both* experience a genuine simultaneous gap (e.g. both briefly masked by the same terrain
  fold, then both reappear the same poll) still hit the untouched gate/ambiguity path on
  reacquisition and can still, in principle, reproduce the runaway shape. This plan reduces
  exposure sharply (most of a session's polls are zero-gap, continuity-covered) but does not
  eliminate it structurally, because doing so would mean touching the Stage 1 invariant, which
  this plan deliberately does not do. Revisit only if this specific shape (both re-tagging
  ambiguous on the same poll after a shared gap) is observed live, per the project's
  revisit-when-real pattern — not worth building for on spec.
- **`object_id` stability is high-confidence, not live-confirmed** (see Stage 1). The
  class-compatibility fallback bounds the damage of a false continuity claim to "falls back to
  today's already-shipped gate behavior," *except* when the reused/incorrect id also happens to
  carry a compatible class — a real but narrow residual gap (e.g. two same-type trucks, if IDs
  were ever reused mid-session, which no evidence found suggests happens). Closing this
  completely requires the live probe in Stage 1, not more code.
- **`hybrid_source.py` is out of scope** — cross-channel duplication (one naked-eye contact, one
  hybrid-channel contact, both near the same real object) is not addressed by this plan and was
  part of the debugger's mixed-channel sweep. If it manifests live, it needs its own design pass
  (the leaf-to-object_id matching problem noted above), not a quick extension of this fix.
  Continuity is even less possible under `emit_mode="on_change"`, but that mode is only used by
  the text-only `PerceptionLogger` path, which never feeds `ContactStore` today — no functional
  regression there, just no continuity benefit either.
- **New coupling in `Observation`**: a field that only naked-eye populates and only
  `ContactStore.ingest` consumes is a bit of cross-module plumbing carried by every other
  `PerceptionSource`/consumer for no benefit yet. Acceptable now (it's `None`-default,
  zero-cost elsewhere), but if a third source is ever added, revisit whether this belongs on
  `Observation` generically or as a narrower per-source mechanism.

### Second-Order Effect

This is the first place a cross-poll continuity signal is threaded from `perception/` into
`belief/` without carrying a DCS truth field — it sets the concrete precedent (an
`observation_id`-shaped reference, never an `object_id`) for how future perception-continuity
work (hybrid-channel continuity, or later track-quality signals) should cross this boundary,
rather than each future milestone re-deriving whether that's permissible from first principles.
It also unblocks BL-5a's live acceptance testing, which this bug blocked once already.

### Decisions Requiring User Input

1. **Confirm the primary direction** (continuity-of-track, naked-eye channel only, with the
   class-compatibility defense-in-depth check) over the rejected alternatives above — this
   touches how every future milestone's live contact behavior works, and partially reinterprets
   (without violating) the "never crossing into belief/" phrasing in your own backlog item.
2. **Confirm the boundary reading** in the "Boundary reading" section above — `object_id` itself
   stays inside `perception/`, but `belief/contacts.py` and `belief/percept.py` do change to
   consume the continuity signal. If you intended a stricter reading, say so before Stage 2.
3. **Whether to require the live probe (Stage 1) before merging**, or accept the current
   high-confidence-desk-research level given the class-compatibility fallback bounds the risk.
   My recommendation is to run it before the next live acceptance pass, not necessarily before
   merging the code — but this is your call given BL-5a was already blocked once.
4. **Accept the residual "simultaneous gap for two nearby objects" risk as unfixed**, per the
   Risks section, rather than additionally building a bounded circuit-breaker (rejected
   candidate 2) as a belt-and-suspenders layer. I lean toward not building it (it's the same
   guessing-under-pressure shape Stage 1 already rejected, and the exposure window left after
   this fix is small), but it's a defensible alternative if you'd rather have a loud, visible
   failure mode than none at all in that specific edge case.
