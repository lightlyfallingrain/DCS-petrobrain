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
    `CONTACT_ENGAGEMENT_CHANGED`, with a docstring carrying the reasoning (an engagement
    change is a threat cue about an already-perceived, already-watched contact, derived from
    believed classification plus ownship position — not an identification), the asymmetric cost
    of gating it (grace == max age, so a masked threat loses the callout permanently rather than
    late), and **the bar anything else must clear to join the set**. A named set rather than an
    inline `if kind != ...` deliberately: an exemption list has the same failure shape as the
    per-kind list this whole fix removes, only in reverse.
  - The event-loop gate now tests `event.kind not in _OBSERVABILITY_EXEMPT_KINDS` first.
  - Inline comment at the gate: enumerates the real breadth (five of `_TEMPLATED_KINDS`' six
    kinds, plus group disclosure, with one exempt), and corrects the frame mismatch — the
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
    recorded with its reasoning. Notes that it is also recorded in `todo/questions.md`'s
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
`_OBSERVABILITY_EXEMPT_KINDS` makes the first fail; disabling the retirement check itself
(`if now_sim - event.t_sim > CALLOUT_MAX_AGE_S:` → `if False and …`) makes the second fail. Each
then passes again on restore. (**The second counterfactual was corrected in round 3** — this log
originally recorded "raising `CALLOUT_MAX_AGE_S` to 1e9", which does *not* fail: the test derives
its own clock from that constant, so raising it moves the test's timeline too. See `debug.md`'s
verification section.) A test that passes for a reason other than the
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

---

## Round 3 — Reviewer's required fixes (`review-round2.md`)

All documentation. No `src/` behaviour change: the only `src` edits are the module docstring, the
`_OBSERVABILITY_EXEMPT_KINDS` docstring and the inline comment at the gate.

### Files Changed

- `body-layer/src/belief/callouts.py`
  - **R1** — module docstring and the inline gate comment now say **five** of `_TEMPLATED_KINDS`'
    six kinds, split as *3 newly gated here* (`CONTACT_CLASSIFICATION_CHANGED`,
    `CONTACT_DETECTED`, `CONTACT_REACQUIRED`) + *2 already gated at emission*
    (`CONTACT_MOTION_CHANGED`, `CONTACT_RANGE_CROSSED`) + *1 exempt*. Verified by import, not by
    counting the prose: `len(_TEMPLATED_KINDS) == 6`, `len(_OBSERVABILITY_EXEMPT_KINDS) == 1`,
    `len(_TEMPLATED_KINDS - _OBSERVABILITY_EXEMPT_KINDS) == 5`.
  - **R2** — the admission bar is rewritten into a criterion that discriminates. It now states
    explicitly that *"derivable from already-held belief plus ownship state"* is **not** the bar
    (equally true of `CONTACT_RANGE_CROSSED`, which must stay gated) and that *"never a claim
    about what Petrovich can see right now"* is **not** the bar either (the exempt kind's own
    rendered line would fail it). Membership turns on two properties, **both** required: the cost
    of silence is a *missed threat cue the pilot needs in order to evade*, not a missed
    identification; and gating it costs the callout *permanently rather than late*, because
    `CALLOUT_OBSERVABILITY_GRACE_S == CALLOUT_MAX_AGE_S`. The paragraph closes by naming the kind
    the bar must exclude and which clause does it — `CONTACT_RANGE_CROSSED` satisfies (2) and
    fails (1). Both properties were already in the docstring as motivation; this moves them into
    the criterion, nothing was newly reasoned.
  - **R3** — the `todo/questions.md` cross-reference now cites commit `156f965`, not the filename
    alone, and says why: the entry postdates this branch's own copy of that file, so grepping the
    branch for it comes up empty (which is exactly what happened in review round 2).
  - **Attribution corrected throughout** (the Reviewer's aside, and it is a real misstatement):
    every *"user decision, 2026-10-06"* becomes *"decided in the review loop, 2026-10-06, on the
    Reviewer's recommendation"*, with the explicit note that the user was **not** consulted. The
    section it is filed under is called "Decided without you"; claiming the user's authority for
    it both misreports who decided and quietly removes the reason the entry exists.
    **Correction, round 4: this sweep was not complete, and this entry overstated it.** The
    security deep analysis (Finding 2) found one surviving occurrence at
    `body-layer/tests/test_callouts.py:1929`, twelve lines above a docstring that said the
    opposite — so the file contradicted itself on exactly the fact worth keeping honest. Fixed in
    round 4; the claim here is left standing with this correction attached rather than rewritten,
    because "swept throughout" reading as verified is itself part of what went wrong.
  - **Optional 1, taken** — a new paragraph records what the exempt line *actually says*
    (`_contact_report_text(facts, lead="Danger, ")`, so with an `EnrichmentContext` it also speaks
    believed clock hour, range and unit type, e.g. `"Danger, ZU-23-3, six o'clock, 1.0 km."`), that
    every one of those facts is belief-derived and identical to what the ungated pull path already
    discloses, and that it is recorded so a future reader does not decide a new kind's membership
    on "it only speaks the cue".
  - **Optional 3, taken** — the inverted clause is fixed. It read as though adding a kind to
    `_TEMPLATED_KINDS` were the hazard; adding to `_TEMPLATED_KINDS` *gates* a kind, which is the
    safe direction, and only `_OBSERVABILITY_EXEMPT_KINDS` exempts one.
- `body-layer/tests/test_callouts.py` — comment/docstring only, plus **Optional 4, taken**:
  `test_engagement_change_speaks_about_a_cockpit_masked_bearing`'s docstring loses the "user
  decision" misattribution, and `test_masked_event_is_retired_once_it_outlives_the_candidate_max_
  age` now asserts its own premise (`store.callout_observable(..., back_in_view)`) before
  asserting silence. Without that, a geometry regression leaving the contact masked at
  `back_in_view` would let the test pass for the wrong reason — the gate skipping the candidate
  rather than the age check having retired it. No assertion was weakened and no test was removed.
- `plans/callout-observability-gate/debug.md`
  - R1 at `:173` (five, with the 3/2/1 split spelled out) and in the "For the user" item, which
    now carries the full tally because an earlier draft of that same paragraph got the number
    wrong twice.
  - R3 second half — the bounded-deferral test's recorded counterfactual is replaced. See below.
  - Attribution and the `156f965` citation, as above.
- `plans/callout-observability-gate/implementation.md` — R1 at `:25`, the same attribution fix,
  the same corrected counterfactual in the "Tests Added" note, and this section.

### The corrected counterfactual (R3, second half), re-run rather than copied

The recorded counterfactual for `test_masked_event_is_retired_once_it_outlives_the_candidate_max_
age` was *"`CALLOUT_MAX_AGE_S` raised to 1e9 → FAIL"*. It **fails open**: the test imports that
constant and derives its own clock from it (`aged_out = masked_at + CALLOUT_MAX_AGE_S + 1.0`), so
raising it moves the test's entire timeline and the deferral still ends just past the budget. A
counterfactual exists so a later reader can re-run it and trust the result, and one that reports
the property as pinned either way is worse than none.

Replaced with the one that bites, and **run here before being written down** — the retirement
check itself disabled in the worktree (`callouts.py`'s `if now_sim - event.t_sim >
CALLOUT_MAX_AGE_S:` → `if False and …`), then:

```
pytest tests/test_callouts.py::test_masked_event_is_retired_once_it_outlives_the_candidate_max_age -q
→ 1 failed
  assert ['unit is truck.'] == []
  tests/test_callouts.py:2156: AssertionError
```

That is a 12-second-stale identification (event at `t_sim` 20.0, spoken at 32.0) delivered the
moment the bearing returns — exactly the property the test claims. The edit was reverted
immediately and `git status --porcelain` confirmed empty before any documentation edit began, so
no part of the probe is in the commit.

### Left, with reasons

- **Optional 2 (a test pinning the enriched exempt line) was not taken.** It is the one optional
  refinement with real value — it would move "does the exemption speak a position?" out of a
  reviewer's note and into an assertion — but it adds a test, and this round was dispatched as
  documentation-only against an explicitly unchanged expected count of 1475/4. Its substance is
  recorded in the `_OBSERVABILITY_EXEMPT_KINDS` docstring instead (Optional 1), which is where a
  reader deciding a new kind's membership will look. **Worth doing as its own small commit**, and
  it is the only thing from this review round still outstanding.
- **`todo/questions.md` itself was not edited**, per the task's constraint. Nothing needs editing
  there: the entry is present on `main` at `156f965`. The branch's own copy predates it and will
  pick it up at merge.
- **`review-round2.md` was left verbatim**, including its quotations of the wrong numbers. It is a
  record of what the branch said at `4648532`, not a claim about what it says now.

### Checks (round 3)

(`body-layer/` only. Worktree has no `.venv`; the main checkout's `body-layer/.venv` binaries were
used by absolute path with `cwd` inside the worktree's `body-layer/`, after proving imports resolve
to the worktree's own `src` — `belief/callouts.py` and `world-model/src/query/describe.py` both
printed worktree paths.)

- `ruff format --check src tests`: **pass**
- `ruff check src tests`: **pass**
- `mypy src` (cwd `body-layer/`): **pass**
- `pytest tests -q`: **pass** — **1475 passed, 4 xfailed**, unchanged from round 2 as expected

### Notable discovery (round 3)

- **A recorded counterfactual can be wrong in a way that is invisible to re-running it.** The
  `1e9` one did not merely fail to reproduce; it reported *success at pinning the property* because
  the test derives its own clock from the constant being perturbed. **A counterfactual that
  perturbs a constant the test itself imports is structurally untrustworthy** — the test's
  timeline moves with it. Perturb the *code path* (`if False and …`) instead, or perturb a
  constant the test does not read. This generalises beyond this file: several tests in this suite
  derive thresholds from the constants they exercise, which is good practice for the test and a
  trap for its counterfactual.

---

## Round 4 — security deep analysis required fixes

Source: `plans/callout-observability-gate/security-review.md` (APPROVED WITH REQUIRED FIXES).
Two required fixes plus its "fix before public release" item 3, taken now because two agents had
separately named it as the residual risk.

### Files changed

- `body-layer/src/belief/callouts.py` — the gate now requires `event.engaged is True` in addition
  to kind membership, and the three places that describe the exemption (module docstring,
  `_OBSERVABILITY_EXEMPT_KINDS`' docstring and bar, the inline comment at the gate) all say
  **per-transition** rather than per-kind.
- `body-layer/tests/test_callouts.py` — the provenance correction, plus three tests.
- this file — the round-3 sweep claim corrected in place.

### Required fix 1 — the exemption is per-transition

**The decision taken, and it is a fork the review left open.** Narrowed to `engaged is True`
rather than ratifying the kind-level form. Two reasons, both recorded in the commit: it is what
the written admission bar actually licenses (property (1) is a *threat cue the pilot needs in
order to evade*, and a "Safe from" line is not one), and the user's standing complaint about
Petrovich is report *volume*, so the default should be to say less about what he cannot see.
The reviewer's counter-argument — that a pilot who heard "Danger" is arguably owed the "Safe
from" that closes it — is real, and is queued for the user to reverse. **It is not settled
engineering; it is the conservative branch of a live disclosure question.**

**What made it a defect rather than a preference**: the code and the docstring disagreed about
which branch had been chosen. The bar's own closing sentence says *"Either property alone admits
something that should stay gated"*, and the leaving transition was admitted on property (2)
alone.

### Required fix 2 — the surviving false attribution

`test_callouts.py:1929` still read *"user decision 2026-10-06"*, twelve lines above a docstring
in the same file saying *"not by the user"*. Committed separately from the mechanism, and
round 3's "swept throughout" claim above was corrected in place rather than rewritten — see that
entry.

### Finding 3 — two assertions, no production change

- `test_exempt_line_discloses_only_belief_derived_facts` renders the exempt line the way it
  renders in flight: through `_contact_report_text` with an `EnrichmentContext`, which also
  speaks believed clock hour and believed range. The contact is astern with
  `last_observable_sim is None` — never once observable — so the test is asserting what he is
  willing to volunteer about something he has never been able to see.
- `test_observability_exemption_set_membership_is_pinned` asserts the set's exact contents.
  Growing it is now a two-part deliberate edit: that assertion, and the per-transition condition
  at the gate.

### Counterfactual run

One, against the **shipped** file rather than an intermediate: reverting the `engaged is True`
condition (`exempt = event.kind in _OBSERVABILITY_EXEMPT_KINDS`) fails
`test_engagement_change_is_silent_about_leaving_a_masked_envelope` with
`AssertionError: assert ['Safe from ZU-23-3 Sergey.'] == []` — the exact line the review
predicted, from the production path rather than a reconstruction. Restored from a scratch copy
(never `git checkout --`) and confirmed byte-identical, `shasum 207f191360cade4e7e232adb90505b8b036df3a2`.
It perturbs the **code path**, not a constant the test imports, per round 3's own discovery.

### Checks (round 4)

(`body-layer/` only, the sole subproject touched. Worktree has no `.venv`; the main checkout's
`body-layer/.venv` binaries were used by absolute path with `cwd` inside the worktree's
`body-layer/`, after proving `belief.callouts` imports from the worktree's own `src`.)

- `ruff format --check src tests`: **pass**
- `ruff check src tests`: **pass**
- `mypy src` (cwd `body-layer/`): **pass**
- `pytest tests -q`: **pass** — **1478 passed, 4 xfailed** (baseline 1475/4, +3 new tests)

### Notable discoveries (round 4)

- **A docstring written to compensate for a missing test had itself gone stale, and writing the
  test is what found it.** The `_OBSERVABILITY_EXEMPT_KINDS` paragraph recorded the exempt line's
  enriched form as `"Danger, ZU-23-3, six o'clock, 1.0 km."`; the real render is
  `"Danger, ZU-23-3 Sergey, 6 o'clock, 1 kilometre."` — `belief.speech`'s `_format_range_km` had
  replaced that wording (`speech.py:162`) and the prose did not follow. Round 3 took this
  paragraph as "Optional 1" *in place of* Round 2's "Optional 2" test, so the cheaper half was
  taken and the thing it substituted for was what would have kept it honest. Prose explaining
  what a test would have asserted is not a weaker version of the test; it is a claim with no
  mechanism holding it true.
- **`-k` substring selection silently skipped a new test.** `-k "engagement or exemption"` matched
  the leaving-transition and membership tests but **not**
  `test_exempt_line_discloses_only_belief_derived_facts` — "exempt" is not "exemption". It
  reported `4 passed` and looked like full coverage of the new work; the full suite then failed on
  the untested one. Run the full suite before believing a `-k` selection was representative.
