# BL-B59 — The same fold drift that absorbs an unrelated contact also evicts a real member

> **DoD-PASSED 2026-10-13 on `fix/bl-b59-retention-hysteresis` (tip `50428dd`), merge pending user
> approval, `#needs-flight`.** The bound closes the eviction measured below: 0 membership
> transitions over 60 ticks of repeat folds, versus the unbounded baseline's 12 — `GROUP_1` stays
> `['CONTACT_1','CONTACT_2','CONTACT_3']` throughout rather than evicting `CONTACT_2`. Reviewer
> (APPROVED, full read, both NaN-safety fixes closed and re-reviewed), Performance (APPROVED —
> MONITOR, sub-microsecond per fold), Security (APPROVED, one low-severity finding closed) all
> signed off. Full report: `plans/bounded-fold-displacement/dod-check.md`. Acceptance test card
> (branch, setup, what to watch for, `fold_budgets`' honest limit):
> https://claude.ai/artifact/NxSFmKNdjxvGG2JtnVKvUC.
>
> **Fixture-only — no sortie has exercised this path.** The one calibration axis
> (`_PLAUSIBLE_SPEED_MPS`) is a table of stated assumptions, not measured against real DCS
> telemetry; the known regression this bound accepts (a unit at 4× its believed class rate is
> tracked *worse* than before, 104.2 m vs 49.8 m) is exactly the shape of defect only a real
> misclassified fast mover could surface — filed as **[[BL-B60]]**.
>
> **Per-weapon note for whoever reads the 40 m figure next**: it is a naked-eye/binocular-channel
> number. Guns and rockets close the aiming loop visually and this clears that bar. **ATGM (9K113)
> guidance has no naked-eye channel at all** — it is a different perception channel this project
> has not built (`perception/optics.py` declares only `UNAIDED_OPTIC`/`BINOCULAR_OPTIC`) — so this
> number says nothing about missile-guidance accuracy, favourably or unfavourably.

> **Decided 2026-10-13: fixed at source, not by a retention term. The user chose [[BL-B58]]
> **option 2** — bound how far a single fold-driven `Contact.record` may move a fused position —
> over the retention hysteresis this entry names. Plan: **`plans/bounded-fold-displacement/
> plan.md`**. `plans/group-retention-hysteresis/plan.md` §5 is superseded in place (its §2
> measurements are what justify the replacement and still stand).
>
> **Measured under the bound** (`plans/bounded-fold-displacement/scratchpad/`): at a bound of
> `plausible_speed_mps × elapsed` the eviction does not happen (`GROUP_1` stays `[1,2,3]`,
> **0 membership transitions over 60 ticks** against the baseline's 12), the fold's displacement
> drops 132.7 → **40.0 m**, and the absorption half fixes itself too — the absorbing edge to the
> ZSU goes 63.8 → 155.0 m against its 78.0 m backstop, which makes **Stage 3.5's admission gate a
> no-op in this incident** (it is load-bearing again at a 3× looser bound, which is why it stays).
> **Zero new constants.** Of the whole existing suite exactly one test moves, and it is Stage
> 3.5's own provenance test, whose fold is entirely at `t_sim=0.0`.

> **Planned, 2026-10-13 — and the plan reverses this entry's framing of its own mechanism.**
> `plans/group-retention-hysteresis/plan.md`, on `fix/bl-b59-retention-hysteresis`. The user
> prioritised this as the next piece of work after `BL-12` merged. Reproduced against
> `1884775` first, then measured; six probes in that plan's `scratchpad/`. **Four findings
> that correct this entry below rather than confirm it:**
>
> 1. **The threshold tightening is the *minor* cause.** Across the fold tick the relative
>    threshold tightens 13.6 % (195.6 → 169.0 m) while the `CONTACT_1–CONTACT_2` gap grows
>    **170 %** (72.1 → 194.6 m), because the fold drags `CONTACT_1` and `CONTACT_3` 132.7 m
>    and 143.3 m while `CONTACT_2` does not move. Clustering is reading a position the fold
>    corrupted, not mis-reading a correct one — so this is **the same provenance defect as
>    [[BL-B58]], read on the other side of the comparison**, not a second independent one.
> 2. **The instrument this entry names is ruled out, measured.** `plans/watch-reporting/
>    plan.md` §4e's 1.5× hysteresis factor fixes the fold tick and **loses the member again
>    at t=25**; sweeping the bound as any fraction of the pair threshold (0.25 / 0.5 / 1.0)
>    fixes the fold tick and loses the member at t=25 in every case. Only an **unbounded**
>    fold-budget discount holds (0 membership transitions over 60 ticks vs the baseline's 12).
>    The sweep is not a calibration curve with a good value in it.
> 3. **Why: `Contact.fold_displacement_m` never retires in the regime where the defect
>    lives** — it grows 132.7 → 239.0 m over 60 ticks and resets zero times, because in a
>    scene dense enough for the relative term to bind, every re-observation is itself
>    ambiguous and folds again. `position.radius_m()` floors at 120.0 m, so covariance
>    supplies no retiring bound either. **This is a measurement about merged Stage 3.5 code**
>    — see the recheck note on [[BL-B58]].
> 4. **The backstop never evicts**; the `CONTACT_1–CONTACT_2` backstop is 500.0 m (Stage 0b's
>    eager cap) against a 194.6 m gap. Retention must touch the relative term only.
>
> The plan's recommendation is therefore **not** what this entry proposes: [[BL-B58]]'s
> **option 2** (bound a single fold's position displacement at source) fixes *both* halves
> with one mechanism and removes the need for a retention term — bigger, and the user's call.
> Three decisions are open; see that plan's §8.

> **Disposition, 2026-10-12 (user decision, `BL-B58`'s decision 2): out of `BL-12`'s Stage 3.5,
> and prioritised next -- not parked unprioritised.** The admission gate (Stage 3.5, implemented
> this stage) only ever blocks an admission, never an eviction, by design (see below). Confirmed
> still live against the real pipeline after Stage 3.5 landed: probe 2
> (`plans/group-cohesion-admission-gate/scratchpad/probe_b58_second_incident.py`) shows `CONTACT_2`
> dropping out of `GROUP_1`'s membership at t=20 even with the admission gate in place
> (`GROUP_1 members=['CONTACT_1', 'CONTACT_3']` after the fold, down from
> `['CONTACT_1', 'CONTACT_2', 'CONTACT_3']` before it -- `CONTACT_2` evicted, `CONTACT_4` correctly
> excluded rather than absorbed). This is the more dangerous of the two halves (it can **suppress**
> an air-defence report rather than fabricate one) and should be taken up next, not left in the
> general backlog.

- [x] **A Stage 3 within-group fold's position drift shifts the median nearest-neighbour gap, which
  tightens `_cluster_contacts`'s *relative* threshold, which can drop a real, correctly-identified
  member out of the group on the same tick — the eviction half of [[BL-B58]], and the more dangerous
  half, because for an air-defence member it **suppresses** a report rather than fabricating one.
  FIXED by bounding the fold's own displacement (`plans/bounded-fold-displacement/plan.md`).**
  #status/done #needs-flight Found 2026-10-12 by the Architect pass on [[BL-B58]], in the same
  reproduction that answered that entry's two open sub-questions. Measured, not argued.

  **The measurement** (probe 2 of `plans/group-cohesion-admission-gate/plan.md` §2a; three infantry
  in a ~95 m knot at 1,000 m, a continuously-observed ZSU-23-4 195 m away, infantry unobserved for
  20 s, then two fresh infantry percepts fold on at t=20):

  ```
  === t=20, before the fold   relative_threshold=195.6
    CONTACT_1-CONTACT_2        72.1 gap     195.6 thresh   LINK
    GROUP_1 members=['CONTACT_1','CONTACT_2','CONTACT_3'] air_defence=[]

  === t=20, after the fold    relative_threshold=169.0
    CONTACT_1-CONTACT_2       194.6 gap     169.0 thresh   .        <-- EVICTED
    CONTACT_1-CONTACT_4        63.8 gap      78.0 thresh   LINK     <-- ABSORBED (BL-B58)
    GROUP_1 members=['CONTACT_1','CONTACT_3','CONTACT_4'] air_defence=[('OP_SPAAG', 1)]
  ```

  One tick corrupts membership in **both** directions. [[BL-B58]] speculated *"in either
  direction"*; both now fire in one incident. Persistent — t=30's geometry is byte-identical.

  **Why it is not fixed by [[BL-B58]]'s Stage 3.5 gate, deliberately.** That gate only ever blocks an
  *admission*, never an eviction — which is what keeps it from undoing `D5`'s continuity preference
  and from reopening [[BL-B50]]. Fixing eviction means **retention hysteresis against the relative
  test** (an already-formed group's existing members get a looser threshold than a first formation),
  which is a second mechanism with its own calibration. Bundling the two would destroy Stage 3.5's
  zero-new-constant property. `plans/group-undermerging/debug.md` already names this exact shape as
  the right instrument if it is ever needed: *"hysteresis that favours an already-formed group's
  continuity rather than loosening first-contact formation"*.

  **Why it is the more dangerous half.** An absorbed air-defence member makes a group *assert* air
  defence it does not contain — a spurious warning. An **evicted** one makes a group stop reporting
  air defence it does contain. `D6`'s carve-out does not sit on this path at all: it gates the fold's
  *candidate set*, and an evicted member is not a candidate for anything.

  **Priority note.** Should not sit unprioritised. After Stage 3.5 lands, any consecutive-tick
  membership flipping still visible in the group-identity sortie trace (amendment A4) is *this*, not
  absorption — so the trace line makes it directly observable, and [[BL-B50]]'s lapse condition
  becomes a live instrument for it.

  Related: [[BL-B58]] (the absorption half), [[BL-B50]] (membership flipping on consecutive ticks),
  [[BL-12]] Stage 3, `plans/group-cohesion-admission-gate/plan.md` §2b and decision 2.
