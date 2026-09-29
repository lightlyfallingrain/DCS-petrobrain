### Review Summary

Reviewed `feature/group-reporting` @ `e34443d` (Stages 1-4 of `plans/group-reporting/plan.md`, plus
the two-commit sparse-scene backstop fix) against `main` @ `f940867`, via an isolated `git archive`
snapshot (this worktree had landed on `main`'s tip, not the branch — confirmed by `git rev-parse
HEAD` mismatch before doing anything else, per dispatch instructions).

Mechanically: `ruff format --check`, `ruff check`, `mypy src` (strict, confirmed via
`pyproject.toml`) all pass clean; `pytest tests -q` gives **1349 passed, 4 xfailed**, matching the
implementation log's claimed numbers exactly and up from main's 1313/4. No regressions.

The architecture is sound and matches the plan closely, including its own mid-flight addenda
(Stage 4 design section, the two coordinator decisions on the 2-member floor and the pair/couple
wording, and the backstop fix). Documentation quality is unusually high — module/function
docstrings carry the actual reasoning, not just a restatement of behaviour, and every deliberate
divergence from the plan's prose is called out explicitly rather than silently absorbed. The
acknowledgement/double-speak mechanics, the split/merge identity logic, and the singular-contact
regression guard all check out under direct code reading, not just by trusting the tests.

One thing does **not** check out: `body-layer/ROADMAP.md`'s milestone entry is now stale relative
to the code it describes, in a way that materially understates what shipped. See Required Fixes.

---

### Required Fixes

- **`body-layer/ROADMAP.md`'s group-reporting entry (line ~1260) predates the backstop fix and now
  misdescribes the branch.** It says "1347 passed/4 xfailed" (the count *before* the two backstop
  commits) and frames the n=2 sparse-scene tautology as "not fixed here... a mechanism decision for
  the next design pass, not this implementation's to make silently" — but `9ecedaf`/`b0f9518`, both
  on this same branch, *did* fix exactly that case (the `GROUP_PROXIMITY_ABSOLUTE_BACKSTOP_M`
  mechanism, confirmed by `test_two_distant_contacts_do_not_form_a_group`/`test_two_close_contacts_
  within_the_backstop_still_form_a_group`). The roadmap needs a pass to say what's actually true now:
  the **n=2 tautology is fixed**; a **separate, still-open n≥3 sparse-scene risk remains** (see next
  item) and that is the one still needing a decision before the next sortie. As written, a reader
  (including the user, whose top priority this is) would believe the wrong thing is still broken and
  the right thing was accepted-as-risk when it wasn't.

- **Tell the user, explicitly, before the sortie: the backstop only covers the n=2 case. A distinct,
  still-open risk exists at n≥3.** Confirmed directly by reading `_cluster_contacts`: the backstop
  (`GROUP_PROXIMITY_ABSOLUTE_BACKSTOP_M`) only applies when `len(contacts) < 3`. At 3+ tracked
  contacts spread kilometres apart with nothing else in the scene, the *relative*-gap rule alone
  still merges dissimilar unit types into one `Group` — this is not hypothetical, it is pinned by two
  of this branch's own tests: `test_report_all_groups_and_truncates_multiple_contacts` needed its
  `store._groups._groups = {}` workaround kept because four different-type contacts 1 km apart
  legitimately cohere, and `test_2c_transcript_fixture_renders_four_lines_not_seven`'s content
  changed because five objects (three infantry, a BTR-70, a truck) within a few hundred metres of
  each other, nothing else tracked, cohere into one composite line
  (`"Three infantry, a BTR-70 and a truck, 1 o'clock, very close."`). Both are well-documented in
  `implementation.md` and in each test's own docstring — this is not a hidden defect — but it is not
  yet surfaced anywhere the user would see it before flying (the ROADMAP entry, once fixed per the
  item above, is the right place). Worth naming concretely: because `render_group_disclosure`'s
  threat-leading clause reports **clock/range from the nearest member, not the leading (threat)
  member**, a sparse-scene merge that pulls a distant threat-capable unit into a near, harmless
  group could speak `"Danger, ZSU-23-4... 3 o'clock, 1 kilometre"` when the ZSU-23-4 is actually
  several kilometres away in a different direction. This is a correctness concern with a plausible,
  not merely theoretical, trigger condition (early sortie, few tracked contacts, exactly the shape
  most fixtures in this codebase already use) — recommend the user either accept it explicitly for
  this sortie (Stage 5's common-fate gate was always going to be the real fix and was deliberately
  deferred pending exactly this kind of evidence) or ask for a quick mitigation (e.g. widening
  `_MIN_CONTACTS_FOR_MEANINGFUL_MEDIAN`'s reach, or reporting the *leading* member's own clock/range
  when a threat leads) before flying. This is a decision for the user, not something I am unilaterally
  fixing or blocking on — flagging per Escalation Rules ("existing tests must be rewritten" doesn't
  apply, but "a new dependency"/"much larger than expected" territory is close: the true fix is
  Stage 5, out of scope here).

- **`_handle_report`'s sector leak is real, confirmed by code reading, not just by the implementer's
  own note.** `CrewConsole._handle_report` filters `facts_list` to the requested clock/sector, but
  once a filtered contact resolves to a `Group`, it calls `render_group_disclosure(self.store,
  belief_group, ...)` on the **full**, unfiltered `Group` (`_group_member_facts` iterates `group.
  member_contact_ids`, not the report's in-scope subset) — so a request like "report clock 3" can
  speak about a group member sitting at clock 12 if the two happen to share a persisted `Group`. This
  is the same underlying n≥3 (or n=2) sparse-scene risk as the item above, surfacing through a
  different call site with a sharper, more clearly-wrong symptom (the pilot asked a scoped question
  and got an answer describing something outside the scope he asked about). Same recommendation:
  surface to the user as a known limitation of this pass rather than silently shipping it undocumented
  — it is currently only documented in `implementation.md`'s Notable Discoveries, not in anything the
  user is likely to read before flying.

None of the three items above require unwinding this branch's actual mechanism — the code does
exactly what its own extensive documentation says it does, and the documentation itself is honest
about the residual risk. The fix required is **disclosure**, and possibly a decision, not a rewrite.

---

### Optional Refinements

- **Test coverage gap vs. the plan's own "Tests this design needs" list**: no test exercises a
  grouped, *watched* contact's `CONTACT_MOTION_CHANGED`/`CONTACT_RANGE_CROSSED`/`CONTACT_ENGAGEMENT_
  CHANGED` still speaking independently of its group's own line. Verified by code reading that the
  mechanism is correct regardless (the group-membership filter in `CalloutScheduler.tick` only ever
  tests `event.kind in (CONTACT_DETECTED, CONTACT_REACQUIRED)`, so `_WATCHED_ONLY_KINDS` structurally
  cannot be caught by it) — this is a missing regression pin, not a live defect, but the plan
  specifically called for it and it would be cheap to add.
- **No integration-level test for the two-candidate-type priority sort** (an `Event` and a `Group`
  actually competing in the same `scored` list inside `tick()`, in both directions) — `group_priority`
  is unit-tested in isolation and `callout_priority`'s own watched-vs-normal ordering is tested
  separately, but nothing drives both candidate kinds through one `tick()` call to confirm they sort
  correctly against each other. Same class of gap as above: mechanically low-risk (identical tuple
  shape, generic Python sort), but named explicitly in the plan's test list and not present.
- **No test for a group with a mix of undifferentiated and differentiated members** (e.g. one member
  still at `presence`, one refined to a real type) going through `_group_composition_clause` — this
  path exists (the `elif differentiated:` branch doesn't filter by level) and would render an
  undifferentiated member as `"a ground"` alongside a real type word, which is a legitimate rendering
  given the accepted `_unit_type_display(None, "presence") == "ground"` quirk, but it is untested and
  the resulting phrase ("a ground and a T-72", say) is worth a human listen before assuming it reads
  naturally.
- **Pre-existing, unrelated-to-this-branch grammar quirk, noted in passing**: `_group_composition_
  clause`'s singular article is always `"a"`, never `"an"` (`test_render_group_disclosure_mixed_pair_
  uses_the_composition_clause` pins `"A armor and a truck."`). This predates Stage 4 (it's Stage 3's
  own behaviour) and is not this branch's to fix, but it will be audible the first time a vowel-led
  class name reaches this clause.
- **The acknowledgement lag for a grouped contact whose group never re-triggers** (e.g. a `CONTACT_
  REACQUIRED` for an existing member that doesn't change the group's composition or rendered text)
  can leave that event permanently unacknowledged in `store.unacknowledged_events`, with no expiry.
  This is the same accepted cost class the plan's own "Decisions Requiring User Input" section already
  named and asked the user to confirm ("no explicit bound is acceptable") — not a new finding, just
  confirming by code reading that the described behaviour is real and matches the accepted-risk
  framing, not worse than described.

---

### Verdict

**APPROVED WITH MINOR FIXES** — the "minor fixes" here are documentation/disclosure, not code. The
mechanism is correct, tested, and matches the plan (including its own honest, explicit deviations).
Before this is flown as the user's top-priority sortie item:

1. Update `body-layer/ROADMAP.md`'s group-reporting entry to state the backstop fix accurately (test
   count, what it actually resolved) and separate the n=2 fix from the still-open n≥3 sparse-scene
   risk.
2. Make sure the user has actually seen and accepted the n≥3 sparse-scene merge risk and the
   `_handle_report` sector-leak consequence before flying — both are real, both are currently
   documented only in `implementation.md`, which the user is not guaranteed to read.

No code required-fix is being asked for; if the user reads the risk and wants it narrowed before
flying, that becomes a short follow-up (Implementer → Reviewer → DoD, per the re-entry rule), not a
rework of this branch.

---

### Review Confidence

Full read of `groups.py`, `callouts.py`, the changed portions of `speech.py`, `contacts.py`'s `tick`
docstring/wiring, `tools.py`, `console.py`, and `crew_console.py`'s `_handle_report`. Full read of
`plan.md` (including the Stage 4 addendum) and `implementation.md`. Spot-checked `test_groups.py` in
full and `test_callouts.py`/`test_speech.py`'s new/changed tests directly (not just their names) —
did not re-read every pre-existing, untouched test in those files line by line. Ran the actual
mechanical checks in an isolated snapshot rather than trusting the implementation log's numbers, and
they matched exactly.
