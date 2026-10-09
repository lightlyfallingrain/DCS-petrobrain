# BL-W21 — Group contacts: cardinality and composition as refinable beliefs

- [~] **Group contacts: cardinality and composition as refinable beliefs.** #status/in-progress **Stages 0-4a done
  2026-09-18 on `feature/group-contact-cardinality`; 3b-ii, 4b, 5 and 6 pending.** Plan:
  `plans/group-contact-model/plan.md`. Diagnosis: `plans/contact-merge-undercount/debug.md`.

  **What the model became, after two reworks.** A `Contact` is a belief about the occupants of one
  **resolution cluster**, not one object — and separability is **angular**, measured at ownship in
  3D: two units are separable when the angle between them exceeds half the sum of their own angular
  sizes (the disc-overlap criterion), with an acuity floor. The user's framing that forced this:
  *"two apples 20 cm apart at 50 cm are obviously two side by side, and may be one when one sits
  behind the other"*.

  **Two reworks, and why.** Stage 3b-i rev.1 modelled the uncertainty as a world-space **ellipse**
  (cross-range acuity, down-range bucket width). That was an approximation of the angular reality,
  and it cost a full implement-review cycle before the user restated the problem in its natural
  space. rev.2 replaced it with the angular predicate and **deleted 144 net lines of `src/`** —
  the correction made the code smaller. Before that, the radius itself had been built on half a
  **30 degree clock bucket**, a *reporting* quantisation mistaken for *resolving* power, roughly 50x
  too coarse.

  **Two findings that paid for themselves:**
  - **The optic multiplier cancels out** of the separability test — both sides are angles through
    the same optic. Verified in the code, not just the algebra.
  - **The acuity floor is provably non-binding for anything the channel detected**, since detection
    is itself an angular-size test against the same constant. So the acuity *magnitude* is not
    load-bearing for clustering — which **removed Stage 3b-ii's headline reason to fly**.

  **Behaviour now** (all fixture-verified): twelve units perpendicular to the line of sight at 9 km
  → **12 contacts**; the same twelve *along* it at 200 m AGL → **1 contact, `OP_1UNIT`** — correct
  and confident, he genuinely sees one dot; the same layout at **1000 m AGL → `OP_TO5UNITS`**,
  because climbing widens the depression-angle spread. Altitude-sensitive counting falls out of
  geometry with no tuned parameter, which is the clearest evidence the model is right.

  **Stages:** 0 ✅ presence-tier veto (interim, removed by Stage 2 as designed) · 1 ✅ cardinality
  mechanism (a no-op by merge criterion — 608 pre-existing tests passed untouched) · 2 ✅ clustering,
  which fixed the live defect · 3a ✅ same-source/same-poll exclusion in `ContactStore.ingest`,
  radius-independent · 4a ✅ cardinality observable in `facts`/console · 3b-i ✅ angular separability
  (rev.2) · 3b-ii ⚠ scope now questionable (see below) · **4b ✅ speech and events — merged
  2026-09-19** (feature/group-contact-speech) · **5 ⏸ composition — DEFERRED** · 6 ⛔ hardening.

  **Rule delivered in Stage 4b — Attention earns precision:** A `watch` or `priority` contact with an
  exact cardinality interval (`lo == hi`, no uncertainty) speaks its real count, capped at twelve.
  An inexact interval (`lo ≠ hi`) stays hedged regardless of attention — no manufactured precision.
  Honesty condition: attention buys disclosure of precision already held, never creates precision.

  **Open questions for the next pass, both real rather than rhetorical:**
  - **Does Stage 3b-ii still justify a sortie?** Its headline purpose was pinning the acuity
    magnitude, which rev.2 showed is not load-bearing. What remains is the tier → count-coarseness
    cap and the chaining cap. Consider folding them elsewhere rather than flying for them. **Status
    (2026-09-19):** Still deferred pending F10 vocabulary sortie feedback; user to re-judge.
  - **Is Stage 5 (composition) still worth building?** The angular model resolves the twelve-unit
    case that originally motivated the whole group model, so the headline example has largely
    dissolved. Cardinality retains real uses — along-LOS columns, tight formations, infantry below
    detection size. The user's own instruction was to re-judge this after flying. **Status
    (2026-09-19):** Same sortie (F10 vocabulary + Stage 4b speech live) will exercise whether
    kind separation (tanks vs. BTRs) adds tactical value beyond cardinality alone. DoD's acceptance
    plan documents what to listen for that argues for or against this stage.

  **Stage 5 (composition) is deferred, and may never be built** (user, 2026-09-19: *"Let's at least
  defer stage 5. It may become entirely redundant, but that needs testing first."*). The case for
  it has weakened twice over. The angular model resolved the twelve-unit scenario that motivated the
  whole group model, so the headline example dissolved; and Stage 4b's hedged register plus
  attention-earned counts may already carry what a crew member actually needs to hear. *"Several
  armor, eleven o'clock, two kilometres"* — with an exact count available on anything watched —
  might simply be enough.

  **What would settle it, and it is a listening test rather than an analysis**: fly with 4b and
  notice whether the missing piece is *what they are*. If "several contacts" leaves a real question
  unanswered in the moment, composition earns its build. If the hedge plus a watch mark covers it,
  Stage 5 is redundant and not building it is a saving, not a compromise. Do not start it on
  reasoning alone — the whole point of deferring is that the evidence comes from the air.

  **Deferred, recorded so they are not silently assumed away** (user, 2026-09-18): occlusion (a near
  object hiding a far one on the same line of sight), and shape, colour and movement as
  separability cues. Movement especially is a strong real-world cue this model ignores entirely.

