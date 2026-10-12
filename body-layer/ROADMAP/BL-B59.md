# BL-B59 — The same fold drift that absorbs an unrelated contact also evicts a real member

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

- [ ] **A Stage 3 within-group fold's position drift shifts the median nearest-neighbour gap, which
  tightens `_cluster_contacts`'s *relative* threshold, which can drop a real, correctly-identified
  member out of the group on the same tick — the eviction half of [[BL-B58]], and the more dangerous
  half, because for an air-defence member it **suppresses** a report rather than fabricating one.**
  #status/open Found 2026-10-12 by the Architect pass on [[BL-B58]], in the same reproduction that
  answered that entry's two open sub-questions. Measured, not argued.

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
