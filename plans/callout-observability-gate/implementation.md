### Implementation Summary

Review-fix pass on `fix/callout-observability-gate`, 2026-10-06, re-entering the loop per
`AGENTS.md` ("A change request from Security or Performance Reviewer re-enters the loop" — the
same shape applies to a Reviewer required fix). Two changes: the Reviewer's required
documentation fix, and one behavioural change the user decided (excluding
`CONTACT_ENGAGEMENT_CHANGED` from the observability gate). Both of the Reviewer's optional
refinements were taken; both were cheap.

The full reasoning for the exclusion lives in `debug.md`'s "Fix Applied" section and in
`callouts._OBSERVABILITY_EXEMPT_KINDS`'s own docstring, not here — this file is the change log.

### Files Changed

- `body-layer/src/belief/callouts.py`
  - New `_OBSERVABILITY_EXEMPT_KINDS: Final[frozenset[EventKind]]` holding
    `CONTACT_ENGAGEMENT_CHANGED`, with a docstring carrying the user's reasoning (an engagement
    change is a threat cue about an already-perceived, already-watched contact, derived from
    believed classification plus ownship position — not an identification), the asymmetric cost
    of gating it (grace == max age, so a masked threat loses the callout permanently rather than
    late), and **the bar anything else must clear to join the set**. A named set rather than an
    inline `if kind != ...` deliberately: an exemption list has the same failure shape as the
    per-kind list this whole fix removes, only in reverse.
  - The event-loop gate now tests `event.kind not in _OBSERVABILITY_EXEMPT_KINDS` first.
  - Inline comment at the gate: enumerates the real breadth (four of `_TEMPLATED_KINDS`' six
    kinds, plus group disclosure, minus the exemption), and corrects the frame mismatch — the
    90° `FORWARD_HEMISPHERE_HALF_WIDTH_DEG` is against true heading (yaw only), the 130°
    `rear_cutoff_deg` is body-relative and includes pitch and bank, so "90 is narrower than 130"
    is not frame-matched and the `CONTACT_DETECTED`/`CONTACT_REACQUIRED` gating is not *quite* a
    no-op in a hard bank. No behaviour change from that correction.
  - Module docstring: new paragraph enumerating the breadth and the exemption, pointing at the
    exempt set for the argument.
- `body-layer/tests/test_callouts.py` — two new tests (below) plus a corrected block comment that
  now describes what the block actually covers.
- `plans/callout-observability-gate/debug.md`
  - **Leads with 17** and the 17/3 split instead of leading with 20 and correcting four lines
    later; the table's bold rows are annotated so a skim-reader cannot take away 20.
  - "Fix Applied": a per-kind breadth table (before/after per kind), and the exclusion decision
    recorded with the user's reasoning. Notes that it is also recorded in `todo/questions.md`'s
    "Decided without you" section.
  - Evidence 4: the 90°/130° frame correction.
  - "For the user" item 1: rewritten from an open question into a settled decision, enumerating
    all three newly-gated kinds rather than two.
  - Verification: counts updated to 1475/4, and the two new tests listed with the counterfactual
    each was verified against.

No `ROADMAP.md`, `BACKLOG.md` or `todo/` file was touched, per the task's constraint.

### Tests Added

- `test_engagement_change_speaks_about_a_cockpit_masked_bearing` — a watched AAA contact that has
  been astern since its first tick (so `last_observable_sim` is never stamped at all, the gate's
  strictest state, not merely a lapsed grace window) still gets its `"Danger, ZU-23-3 Sergey."`
  call when ownship enters the firing envelope. Deliberately mirrors
  `test_classification_change_is_silent_about_a_cockpit_masked_bearing`'s geometry so the
  contrast is decided by kind alone.
- `test_masked_event_is_retired_once_it_outlives_the_candidate_max_age` — the Reviewer's optional
  gap. Ticks astern past `CALLOUT_MAX_AGE_S` and asserts silence *even after the bearing comes
  back*, pinning the bounded-deferral property that makes "skip without consuming" safe. The
  existing deferral test only proved the deferral half.

**Both were verified by counterfactual, not by reading.** Emptying
`_OBSERVABILITY_EXEMPT_KINDS` makes the first fail; raising `CALLOUT_MAX_AGE_S` to 1e9 makes the
second fail. Each then passes again on restore. A test that passes for a reason other than the
property it names is the failure mode here, and both tests are new assertions about a gate that
already existed.

### Checks

(`body-layer/` only — the diff touches no other subproject. The worktree has no `.venv`; the main
checkout's `body-layer/.venv` binaries were used by absolute path with cwd inside the worktree's
`body-layer/`, after confirming `belief.contacts.__file__`, `belief.callouts.__file__` and
`query.describe.__file__` all resolve inside the worktree.)

- `ruff format --check src tests`: **pass** (115 files already formatted)
- `ruff check src tests`: **pass**
- `mypy src` (cwd `body-layer/`): **pass** (53 source files)
- `pytest tests -q`: **pass** — **1475 passed, 4 xfailed** (branch baseline 1473/4, + the 2 new)

### Notable Discoveries

- **The test-impact surface was exactly one file, and that was checked rather than assumed.**
  `grep -rln "callout_observable\|last_observable_sim\|OBSERVABILITY" tests/ src/` returns
  `tests/test_contacts.py` and `tests/test_callouts.py`. `test_contacts.py`'s references are to
  the *emission-site* gate in the fifth and sixth blocks, which the seventh (engagement) block
  never used — so excluding `CONTACT_ENGAGEMENT_CHANGED` at the speech choke point could not
  reach them, and the suite confirms it: zero existing tests changed behaviour.
- **The defect the Reviewer found has a general shape worth naming.** The gate was widened by
  making it discriminate on the *contact* instead of on the event kind — which is the right call,
  and is what finally covered group disclosure. But it means the gate's breadth is defined by
  `_TEMPLATED_KINDS`, a set declared 600 lines away and maintained for an unrelated reason
  (which kinds `route_event` can render). `grep`ping the gate's own call sites shows two; reading
  `_TEMPLATED_KINDS` shows six. Nobody enumerating call sites would have found the third kind.
- **The exemption is now the thing to watch, not the gate.** A kind added to `_TEMPLATED_KINDS`
  joins the gate automatically, which is the property this fix wanted. A kind added to
  `_OBSERVABILITY_EXEMPT_KINDS` leaves it silently, which is the same hazard inverted — hence the
  explicit admission bar in that set's docstring rather than a bare `frozenset`.
