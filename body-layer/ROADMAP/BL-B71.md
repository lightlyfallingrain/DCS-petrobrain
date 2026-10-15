# BL-B71 — The least-capable-optic guidance ladder

- [ ] **During guidance, use the *least* capable optic that can still resolve the target, evaluated
  continuously in both directions — escalate when the current instrument cannot see it, de-escalate
  as the range closes.** #status/open Planned 2026-10-15,
  `plans/attack-run-sortie-fixes/plan.md`. Depends on `[[BL-B70]]` for the cause taxonomy it reads.

  Source of truth is `docs/acceptance/2026-10-15-attack-run-sortie-feedback.md` §6 and §7. User's
  words: *"for guidance using other than ATGM - use the least capable optic that can see the target.
  Switch from more capable to less capable as range decreases."*

  **Why least-capable is correct rather than a compromise.** A more capable optic is a *narrower*
  one — the 9K113 narrow is 6° of field against the naked eye's 180°. Magnification he does not need
  costs him everything else he would have noticed. **The ordering is derivable, not a new table:**
  `Optic.presence_range_mult` ascending *is* `fov_half_angle_deg` descending across the whole shipped
  table (unaided 1.00/90°, binocular 2.42, sight wide 3.55/5.75°, sight narrow 5.81/3.0°), so the
  ladder is a sort over data that already exists and a future optic joins it by existing.

  Second-order product benefit worth stating: de-escalating as the run closes **restores** situational
  awareness exactly when the pilot most needs Petrovich noticing threats, wingmen and the next target.

  **The hard gate: the 9K113 is never reached for autonomously.** A sight rung may be selected only
  when `OpticState.home_phase is OpticPhase.SIGHTING` — the pilot has already said "Observ on".
  Designating a target must not turn the sight on (§6, and
  `docs/acceptance/2026-10-15-9k113-sight-direction.md` §6). Otherwise the ceiling is binoculars and
  `[[BL-B70]]`'s age-phrase fallback takes over. The ladder may *read* `home_phase` and must **never
  write** it — that is what makes the gate structural rather than a check someone can forget.

  **Boundary: `optic_policy` grants, `attack_run` requests.** `attack_run` knows the target, its range
  and its profile, so it computes which optic would resolve it. `optic_policy` grants or refuses,
  because only it knows `home_phase`, `hands_busy_until_sim`, `sight_steady` and the hands-busy
  exclusivity rule — an attack run reaching for binoculars **is an optic decision with an attention
  cost**, and that cost is `optic_policy`'s whole subject. Mechanically a `guidance_request: Optic |
  None = None` keyword, bit-identical no-op when unset, the same pattern `sight_steady`,
  `group_salient` and `forest` each established in that module.

  **Hysteresis is load-bearing, not polish, and the obvious sizing is wrong.** Measured from both
  sorties' belief-truth logs: the attack target closes at a **median 60 m/s** (not the ~17 m/s one
  15 s slice of §5 implies) and the range **genuinely reverses by up to +130 m/s** on a fly-past. So a
  15% band at the naked-eye rung is crossed in under 6 s, and **no band of any plausible width
  survives a fly-past.** Three guards, in order of cost:

  1. **Do not re-evaluate while the target is behind the cockpit mask** — free, falls out of
     `[[BL-B70]]`'s §2 rule, and removes the fly-past case at its root.
  2. **A fractional margin for de-escalation only** (`GUIDANCE_OPTIC_HYSTERESIS_FRACTION`, recommended
     `0.25`). Fractional, not metric: rungs are 2.42× apart, so a fixed metre band would be enormous
     at the naked-eye rung and negligible at the sight's.
  3. **A minimum interval between grants** (`GUIDANCE_OPTIC_MIN_INTERVAL_S`, recommended `10.0` —
     exceeds the 4.5 s the worst observed reversal needs to re-cross guard 2's band, and bounds the
     worst case to one 1 s blind interval per 10 s).

  **The 1 s hands-busy gap is accepted by direction** — user, verbatim: *"Raising binoculars costs the
  1 s hands-busy interval -> acceptable"*. No pre-emptive raise, no deferring the switch, no
  announcement, no attack-run special case. That *raises* the stakes on the band, because nothing else
  in the design discourages switching.

  **The ATGM arm is shaped for, not built.** §7's mandatory-sight floor with narrow→wide widening has
  no run concept to attach to until `[[BL-B66]]`/`[[BL-B67]]`, so the ladder takes `floor`/`ceiling` as
  **parameters** rather than hardcoding unaided/binocular. The ATGM case is then
  `floor=SIGHT_WIDE_OPTIC, ceiling=SIGHT_NARROW_OPTIC` at one call site. Noted so those entries
  inherit it instead of rediscovering it.

  **The diverged state to build a test for by hand:** `guidance_optic is SIGHT_WIDE_OPTIC` while
  `home_phase is OpticPhase.SCANNING`. Every natural test path sets both consistently, which is exactly
  why `[[BL-B64]]`'s equivalent survived a full suite and had to be found by a reviewer constructing
  the state manually. The plan's Co-moving Fields table lists every transition that must revoke a sight
  grant — including `_force_observ_off` on a violent manoeuvre, which today changes the phase only.

  **Known structural seam, deliberately not fixed here:** the run claims the *gaze* in
  `logger._active_gaze` and its *optic* comes from `optic_policy.decide`'s own scan cycle, so the two
  disagree by construction during a run — which is why nothing ever asked whether the instrument in
  Petrovich's hands could see the thing he was staring at. Unifying them as an `OpticPhase.GUIDING` is
  the tidier shape and is the consolidation `[[BL-B66]]` should absorb while it is already rewriting
  those files for the slew controller.

  Related: `[[BL-B70]]` (prerequisite), `[[BL-B64]]` (made the sight selectable; the bug class above),
  `[[BL-14]]`, `[[BL-B66]]`/`[[BL-B67]]` (the ATGM arm and the `GUIDING` consolidation).
