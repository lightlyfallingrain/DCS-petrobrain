# BL-B72 — A firing unit gives itself away, out to the player bubble

- [ ] **BL-B72 — While a unit is actively firing, muzzle flash and tracers make it detectable at any
  range out to the player bubble, through tree cover, regardless of the optic's own distance
  limits — detection only, and only while it fires.** #status/open Filed 2026-10-15 from user
  direction; his words and the structural reading are in
  `docs/acceptance/2026-10-15-firing-unit-visibility.md`.

  **The rule, as a modification to `check_visibility`'s existing gate chain** — this is the form the
  work takes, and the asymmetry is the whole item:

  | gate | firing unit |
  |---|---|
  | gaze | still applies — he must be looking that way |
  | cockpit mask | presumably still applies (open question 2) |
  | optic FOV | **still applies** — the user names it: *"with optic where FOV allows seeing"* |
  | range / size | **bypassed**, out to `PLAYER_BUBBLE_RADIUS_M` |
  | terrain / building LOS | **open** (question 1) |
  | tree cover | **bypassed** — *"a unit firing from a forest gives it location away"* |

  **Detection only.** It admits at `PRESENCE` and must not raise `CLASS` or `TYPE` — a muzzle flash
  at 9 km says *something is shooting there*, not *that is a BMP-2*. **Strictly time-bounded** by the
  DCS start/stop firing events: *"once it stops firing, we cannot see it anymore."* What survives is
  an ordinary decaying memory of having seen it, not a continuing sighting.

  ## Why this is worth more than its size

  It is **the first perception path where the target's own behaviour decides whether it is seen**,
  rather than the observer's instrument or the geometry. Everything so far is a function of range,
  size, optic and occlusion; this adds an emitter.

  And it closes a gap the pilot would notice immediately: today a unit shooting from 4 km is
  invisible to Petrovich, because that is past the naked eye's ~2.3 km presence threshold for a 7 m
  vehicle (`7 / LOWRES_ANGULAR_RADIUS_RAD`). **The thing most worth telling the pilot about is
  currently the hardest for Petrovich to see.** Measured on the 2026-10-15T17:55 sortie, where the
  attack target sat unresolvable between 2.6 km and 2.36 km for fifteen seconds.

  ## SAM launch is the same rule with a decaying tail

  **Added by the same direction.** A SAM launch is comparable, *"but SAM missiles leave smoke trail,
  so that especially gives away the launcher position. Pick a constant to simulate smoke trail
  dissipation -> SAM launch shows where the launcher was for quite a while."*

  This is **the first perception source with a decaying external lifetime**: gun fire is visible
  only between start and stop, while a launch stays visible *after* the event ends because the smoke
  hangs. It reveals **where the launcher was** — a sighting with an age, which belief already
  models — and must not read as "a launcher is there now". The dissipation constant is
  behaviour-affecting and goes in the tuning file; it is exactly what a sortie retunes.

  ## The export mechanism exists; the open question is narrower than it looked

  **Corrected 2026-10-15** against
  `aircraft-layer/research/2026-09-24-damage-and-firing-events-over-mission-bridge.md`, which the
  user remembered and which settles most of this:

  - Reachable over the **mission-scripting bridge** (`net.dostring_in("scripting", ...)`, polled at
    1 Hz from a Hook) — **already shipping** for F10 commands and unit velocity. No new mechanism.
  - **`S_EVENT_SHOT` covers missiles and excludes machine-gun/autocannon fire**, which routes to
    **`S_EVENT_SHOOTING_START`** instead; both have paired end events. **The gun half and the SAM
    half of this feature therefore need different events** — and that split happens to line up
    exactly with the two halves.
  - ~~**The one open point**: whether ground AAA raises `S_EVENT_SHOOTING_START` at all.~~
    **ANSWERED — and it was already flown.** `docs/acceptance/2026-09-24-damage-and-firing-probes.md`
    is marked **FLOWN AND CLOSED, 2026-09-25**, with its own instruction *"do not re-fly it"*:
    *"a ground gun unit's `SHOOTING_START` names the player as its target, so 'we are being shot at'
    needs no inference"*. Confirmed live, not inferred. **There is no probe outstanding for this
    entry.**

  **Three findings from that same closed probe bear on the design**, two of which would otherwise
  have been got wrong:

  - **The event carries its target.** A ground gun firing *at the player* is distinguishable from
    one firing at something else, for free. That is a product-level difference — *"we are being shot
    at"* versus *"something is firing over there"* — and it sharpens the open question about what
    Petrovich actually says.
  - **Gun rounds are not objects in `LoGetWorldObjects`; rockets are.** So the tracer channel *has*
    to be the event — exactly as the user recalled it (*"unit firing is exportable event while
    tracers are not"*). There is no world-object path to fall back on.
  - Unrelated but adjacent, and in the same note: the visible damage state is **fire, not smoke**,
    bracketed to a life fraction of (0.69, 0.84]. Its one remaining follow-up — the exact threshold
    inside that band, and whether it is global or per-type — is not this entry's.

  ## A burning unit is the third emitter, and the cheapest

  **Added by the same direction**: *"oh, burning and smoking targets -> those are similarly visible
  from far away"*.

  **It is a polled state rather than an event**, which exempts it from every hard problem the other
  two halves carry — no latching, no burst missed between 1 Hz polls, no start-without-end when a
  unit dies mid-burst, no external lifetime to model. `getLife()`/`getLife0()` are read per unit
  over the bridge already in production.

  **The threshold is already measured, not open**: the closed probe records that the visible state
  is **fire, not smoke**, meaning doomed-with-a-delay, bracketed to a life fraction of
  **(0.69, 0.84]**. Its one follow-up — the exact value inside that band and whether it is global or
  per-type — is a tuning question and belongs in the tuning file, not a feasibility question.

  **What it tells the pilot is categorically different from the other two.** Gun fire says
  *something there is dangerous now*; a burning unit says *something there is already dead or
  dying*. That is not a threat report. Detection-only still holds.

  **It does NOT answer *"did we get it?"*** (user direction, 2026-10-15): *"It might be 'we got it'
  but it might be another unit that somebody else got."* That question needs **attribution** — that
  this burning unit is the one we engaged — and a life-fraction reading carries nothing of the kind.
  Asserting the link from fire alone would be an omniscience leak of exactly the sort this
  project's central invariant forbids. `plans/brain-layer/explore-notes.md`'s question **stays
  open**; this entry supplies one input a future attribution model could use, not the answer.

  ## Planned, and split three ways

  **Architect pass 2026-10-15: `plans/emitter-visibility/plan.md`.** The gate change is one
  mechanism for all three emitters — a per-candidate `emitter` parameter on `check_visibility` that
  bypasses the range/size and forest gates only, and clamps the achieved tier to `lowres` whenever
  either bypass was used. `_classification_for_tier("lowres", …)` already yields the presence class,
  so detection-only needs no new classification path. Provenance rides on `Observation.provenance`,
  which is already a free-form string, so no schema changes anywhere.

  **This entry keeps the shared bypass plus the burning emitter** (`[[AC-B7]]`), which needs no new
  transport and ships first. The two event-driven halves split out: **`[[BL-B73]]`** gun fire and
  **`[[BL-B74]]`** the SAM smoke tail, both blocked on **`[[AC-B8]]`**.

  **Stage A merged 2026-10-15** (`f06802e`, `feature/emitter-visibility`, DoD PASS at
  `plans/emitter-visibility/dod-check.md`): the shared `emitter` bypass on `check_visibility`, the
  `lowres` tier clamp, and `EmitterKind.BURNING` in `body-layer/src/perception/emitters.py`.
  **Stage B merged 2026-10-16** as `[[BL-B73]]`/`[[AC-B8]]`. **This entry stays open on Stage C
  only** — `[[BL-B74]]`'s decaying launch-smoke lifetime is the one emitter kind
  `resolve_emitters` does not yet fold in; neither Stage A nor Stage B has been flown
  (`#needs-flight` sits on `[[BL-B73]]`/`[[AC-B8]]`/`[[AC-B7]]`).

  **Two findings from that pass worth having here**: the existing threat path keys on classification
  and so would schedule a `PRESENCE`-only firing contact at the *lowest* priority there is — new
  event kinds are required, not a reuse; and `petrobrain-line-of-sight-hook.lua`'s
  `MAX_SIGHTLINES_PER_CALL = 128` nearest-first cap drops the *far* candidates, which with a
  fail-closed LOS gate can silently neuter the whole feature in a dense scene.

  Related: `[[BL-B64]]` (the optic model this bypasses a gate of), `[[BL-B70]]`/`[[BL-B71]]` (the
  attack-run work whose `", obstructed"` semantics question 1 interacts with), `[[BL-2]]`
  (contact decay, which owns what happens after the firing stops).
