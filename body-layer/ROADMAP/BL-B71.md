# BL-B71 — The least-capable-optic guidance ladder

- [x] **During guidance, use the *least* capable optic that can still resolve the target, evaluated
  continuously in both directions — escalate when the current instrument cannot see it, de-escalate
  as the range closes.** #status/done #needs-flight Planned 2026-10-15,
  `plans/attack-run-sortie-fixes/plan.md`. Depends on `[[BL-B70]]` for the cause taxonomy it reads.
  Merged `feature/bl-b71-optic-ladder` (DoD pass, tip `91b3c489`); mechanical checks green
  (ruff format/check, `mypy src` 60 files, `pytest` 2090 passed/4 xfailed), full
  Architect(roadmap entry)→Implementer→Reviewer(×2)→Performance→Security chain complete and
  APPROVED at every gate.

  **What shipped**, exactly as specified above: `_LADDER` (presence-ascending over the shipped
  optic table), `least_capable_sufficient_optic`/`guidance_request_for` (the hysteresis-guarded
  escalate-immediately/de-escalate-one-rung-at-a-time ladder, guards 1-3 all as planned), and
  `OpticState.guidance_optic`/`_apply_guidance`'s structural sight-ceiling clamp (re-derives
  `home_phase` fresh every call — the hard gate holds under direct mutation testing by Reviewer
  and independently by Security). `attack_run` requests, `optic_policy` grants, exactly the module
  boundary the plan drew.

  **One required Reviewer fix, caught and corrected twice, not once.** The first review found
  `_no_look_cause`'s range gate hardcoded to `UNAIDED_OPTIC` — once the ladder grants binoculars,
  a live resolvable look could still be reported `"too_far"` and trigger the "last I saw…" branch
  about a target currently in view, exactly the defect class this feature exists to prevent. The
  first fix round wired the *granted* optic (`OpticState.guidance_optic`); asked directly whether
  this was a test artefact or real behaviour, the user ruled **"actual behavior must measure by
  used optic"** — `guidance_optic` is `None` through ordinary glassing with no guidance grant
  standing, so that fix reintroduced the same bug in miniature for the ordinary-glassing case. The
  second round rewired it to `runner.optic` (renamed `resolving_optic`), the value that actually
  admitted the tick's percept, confirmed by Reviewer and Security independently tracing the full
  call chain (`logger.py` → `naked_eye_source.py` → `visibility.check_visibility`) rather than
  trusting the fix's own account. **The lesson generalises beyond this item**: a fix that answers a
  review's narrower wording can still miss the user's actual direction behind it — see
  `.claude/agent-memory/dod/project_fix_answers_review_wording_not_user_direction.md`.

  **Acceptance boundary, stated plainly.** Everything above is verified against fixtures and unit
  tests — 2090 passed, including hand-built diverged states (`guidance_optic is SIGHT_WIDE_OPTIC`
  while `home_phase is SCANNING`) and three independently-rerun mutation counterfactuals. No
  fixture can confirm whether the ladder's *cadence* reads right in the air — whether escalation
  and de-escalation feel responsive rather than jumpy or laggy at the pilot's own closing rates.
  The sight rung is also unreachable without the pilot's own prior "Observ on" command, so the
  common case a flight will actually exercise is naked-eye ↔ binoculars; the full four-rung ladder
  including the 9K113 sight needs a run flown with OBSERV already commanded on to be exercised at
  all. That is exactly what the next sortie is for.

  **Two accepted gaps are carried forward, not fixed, and named here so a flight planner sees
  them:**
  - `GUIDANCE_OPTIC_MIN_INTERVAL_S`/`HANDS_BUSY_DURATION_S` cross-key coupling: at the declared
    bound extremes (`MIN_INTERVAL_S=1.0`, `HANDS_BUSY_DURATION_S=5.0`) a grant could re-charge
    hands-busy before the previous charge finishes — Petrovich going quiet mid-run under
    aggressive manual tuning. Single-key tuning is safe by a wide margin; this needs more than one
    key retuned together to trigger, which is not the motivating case. No code change — flagged in
    the constant's own rendered `#:` comment.
  - A two-poll (not the usual one-poll) revocation lag on `disengage`/`drop_target`: the guidance
    request can stare at an already-dropped target for one extra poll (sub-second to ~1 s) before
    clearing. Bounded, symmetric across both exit paths, and cannot grant a sight rung that was not
    already pilot-authorized (Security, `project_optic_revocation_two_poll_lag.md`). Worth
    revisiting when `[[BL-B66]]`'s planned `OpticPhase.GUIDING` consolidation touches this same
    revocation path.

  **Downstream effect, per the Milestone Completion question:** does not change what `[[BL-B66]]`
  or `[[BL-B76]]` should do next. `[[BL-B66]]`'s planned `OpticPhase.GUIDING` consolidation
  (gaze/optic unification for the slew controller) will want to absorb both the known structural
  seam named below and the two-poll revocation lag above while it is already rewriting these
  files — noted, not newly assigned. `[[BL-B76]]` (the `", obstructed"` dead-code gap) is
  independent of this entry: this ladder reads `_no_look_cause`'s cause taxonomy but does not touch
  the `live_los_clear` admission path `BL-B76` is about.

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
