# Review — round 2: `fix/callout-observability-gate` @ `4648532`

**Date:** 2026-10-06 · **Reviewer** · **Scope:** commit `4648532`
("Exempt engagement-envelope calls from the observability gate") in the context of the
branch `31d5733` → `61edc58` → `61d5362` → `4648532`. Earlier commits were reviewed in
`review.md` and are not re-reviewed here except where `4648532` changes their meaning.

**Branch contract:** `git rev-parse HEAD` = `464853257493ad9a7789552f59f35d86876b8a20`,
`git branch --show-current` = `fix/callout-observability-gate`, tree clean. Imports proved to
resolve to this worktree's own `src`
(`.../agent-a6ff8c31e011ce890/body-layer/src/belief/callouts.py`) before any check was run.

**Checks (main checkout's binaries, `cwd` = this worktree's `body-layer/`):**
`ruff format --check src tests` → 115 files already formatted ·
`ruff check src tests` → All checks passed ·
`mypy src` → Success, 53 source files ·
`pytest tests -q` → **1475 passed, 4 xfailed**. Matches the expected counts.

---

### Review Summary

The exemption is **correctly bounded as a mechanism**, and more narrowly than the commit
message claims credit for. Everything it removes is the observability predicate and nothing
else: an exempt `CONTACT_ENGAGEMENT_CHANGED` still passes through `_TEMPLATED_KINDS`
membership, the `_consumed` check, the group-disclosure deferral, `_WATCHED_ONLY_KINDS`'
watch/priority requirement, `WATCH_REPORT_MIN_GAP_S`, and `CALLOUT_MAX_AGE_S` — all of which
sit *above* the gate in `CalloutScheduler.tick`. So the hole is one predicate wide, for one
kind, that independently must already be watched and under ten seconds old.

Three things I was asked to test, verified rather than read:

1. **Does the exempt callout leak anything beyond the cue?** No omniscience leak. The event is
   minted by `ContactStore.tick`'s seventh block from `envelope_for(contact.classification)`
   (believed; `belief/threat.py`'s signature *is* the guard — it accepts `ClassificationBelief`
   and imports nothing from `perception.source`), `contact.last_position` (believed), and
   ownship's own state. The rendered line is `_contact_report_text(facts, lead="Danger, ")`,
   so with an `EnrichmentContext` present it *does* additionally speak the believed clock/range
   and the believed unit type — but every one of those facts is belief-derived
   (`_classification_facts` reads `Contact.classification`, not `last_class_raw`;
   `facts["relative_now"]` is `relative_geometry(ownship, world_position)` over
   `Contact.last_position`) and is word-for-word what the deliberately ungated **pull** path
   already discloses on a `report`. Nothing ground-truth-derived reaches it. See Optional 1 —
   the docstring's phrasing understates this, which is a documentation point, not a leak.

2. **Can a contact reach this kind without having been perceived?** No, and structurally so.
   `ContactStore.ingest` has exactly one production call site (`logger.py:539`), fed only by
   `source.poll(...)` over the perception sources, so every `Contact` is perception-founded.
   The seventh block then additionally requires `is_watched` and a non-`None`
   `envelope_for(contact.classification)` — an unresolved belief yields no envelope and
   therefore no event (`threat.py`'s "no fallback envelope, ever").

3. **Is the stated admission bar precise enough to decide a future kind's membership?**
   **No** — see Required 2. This is the one real finding.

The structural characterisation I was asked to confirm **is accurate**. Grepping the gate's own
predicate gives `contacts.py:1237` (motion) and `contacts.py:1349` (range) at emission, plus the
two new call sites in `callouts.py` — two kinds by name. The breadth actually lives in
`_TEMPLATED_KINDS` (declared at `callouts.py:259`, ~650 lines above the gate at `callouts.py:941`,
and maintained for an unrelated purpose: which kinds `route_event` can render). I confirmed the
set holds six members by importing it. Nobody enumerating call sites could have found
`CONTACT_CLASSIFICATION_CHANGED`, `CONTACT_DETECTED` or `CONTACT_REACQUIRED` that way. The real
scope **is now findable from the gate itself** — the inline comment at `callouts.py:909` names
every member and, more importantly, carries the load-bearing sentence *"The gate discriminates on
the contact, not on the kind, so every templated kind is in scope unless that set says
otherwise"*, which is the rule rather than a snapshot of the list. Good fix, subject to Required 1.

**And yes, I agree with the judgement call** to document the whole breadth rather than the
literal three newly-gated kinds the required fix asked for. Naming only the delta would
reproduce the defect one level up: the next reader needs to know what the gate covers, not what
this commit changed about what it covers. The required fix asked for the narrower thing; the
broader thing is what it was asking for the narrower thing *in service of*.

---

### Required Fixes

All three are documentation-only; no `src/` behaviour change is needed. They are required rather
than optional because in this commit the documentation **is** the guard — the whole reason the
exemption is a named set with a docstring instead of an inline `!=` is that the prose is what
stops the next kind joining silently.

**R1 — "four of six" is five. Stated in three places, each immediately followed by a list of
five.** 6 templated kinds − 1 exempt = 5 gated. Verified by import:
`_TEMPLATED_KINDS` = {`CONTACT_CLASSIFICATION_CHANGED`, `CONTACT_DETECTED`,
`CONTACT_ENGAGEMENT_CHANGED`, `CONTACT_MOTION_CHANGED`, `CONTACT_RANGE_CROSSED`,
`CONTACT_REACQUIRED`}; `_OBSERVABILITY_EXEMPT_KINDS` = {`CONTACT_ENGAGEMENT_CHANGED`}.

- `body-layer/src/belief/callouts.py:54` — *"The breadth is four kinds plus group disclosure"*,
  then names five.
- `body-layer/src/belief/callouts.py:909` — *"this gates four of `_TEMPLATED_KINDS`' six kinds"*,
  then names five.
- `plans/callout-observability-gate/debug.md:172` — *"covers **four** of `_TEMPLATED_KINDS`' six
  kinds plus group disclosure"*; the table directly beneath it is correct and lists five.
  (`implementation.md:25` repeats the same number, and may as well be corrected with them.)

No reading makes "four" right: 5 gated in total, 3 newly gated here (`CLASSIFICATION_CHANGED`,
`DETECTED`, `REACQUIRED`), 2 already gated at emission. The round-1 required fix was *"three
places describe the widening as two kinds"*; replacing a wrong number with a different wrong
number, beside the correct list, is the same defect with a smaller magnitude.

**R2 — the admission bar does not discriminate: as written it admits
`CONTACT_RANGE_CROSSED`, which must never join.** `callouts.py`'s `_OBSERVABILITY_EXEMPT_KINDS`
docstring closes with:

> *"Anything added here must be a cue derivable from already-held belief plus ownship state, and
> never a claim about what Petrovich can see **right now**."*

Both clauses fail to separate the member from the non-members:

- *"derivable from already-held belief plus ownship state"* is **equally true of
  `CONTACT_RANGE_CROSSED`** (`contacts.py`' sixth block compares `contact.last_position` against
  ownship, exactly as the seventh block does) and of `CONTACT_MOTION_CHANGED` (believed motion
  state). Range-crossing lines are precisely what the user's own explore decision keeps gated.
- *"never a claim about what Petrovich can see right now"*, read strictly against the **rendered
  text**, excludes the exempt kind itself — `"Danger, ZU-23-3, six o'clock, 1.0 km."` is built by
  the same `_contact_report_text` that produced the sortie's complained-of masked-hour lines.

So a future reader applying the bar literally gets either "range-crossed qualifies" or "engagement
does not", and the set is as silently joinable as the per-kind list this fix removed.

The two properties that *do* separate it are already in the docstring — as motivation, not as the
criterion: (a) the consequence of silence is a **missed threat cue the pilot needs in order to
evade**, not a missed identification; and (b) because `CALLOUT_OBSERVABILITY_GRACE_S ==
CALLOUT_MAX_AGE_S`, gating costs the callout **permanently rather than late**. Fold those into the
bar so membership turns on them. One or two sentences; the reasoning does not need to be
rediscovered, only moved.

**R3 — two recorded claims that do not hold when checked.**

- **`todo/questions.md`'s "Decided without you" does not contain this decision.** Claimed in
  three places: `callouts.py:261-264` (*"recorded in `plans/callout-observability-gate/debug.md`
  and `todo/questions.md`'s 'Decided without you'"*), `debug.md:188-190`, and `debug.md:322-323`.
  The section exists (`todo/questions.md:85`) and the entry does not — `grep -n
  "ENGAGEMENT_CHANGED\|observability gate" todo/questions.md` is empty. `debug.md` *does* record
  it, so the fix is to either add the entry or drop the half of the claim that is false. (I was
  instructed not to edit `todo/`.) Note that the section's own framing may not even fit — the
  user decided this one; it was not decided without them.
- **`debug.md:293-295`'s recorded counterfactual for the bounded-deferral test is not
  reproducible as written.** It records *"`CALLOUT_MAX_AGE_S` raised to 1e9 → **FAIL**"*. I patched
  `callouts.py:332` to `1e9` and ran the test: **1 passed**. The reason is structural, not a
  flaky run — `test_masked_event_is_retired_once_it_outlives_the_candidate_max_age` imports
  `CALLOUT_MAX_AGE_S` (`tests/test_callouts.py:33`) and derives its own clock from it
  (`aged_out = masked_at + CALLOUT_MAX_AGE_S + 1.0`), so raising the constant moves the test's
  timeline with it and the deferral always ends just past the budget. At `1e9` the test passes for
  a second, different reason as well: the contact is long past `LOST_THRESHOLD_S`. A recorded
  counterfactual exists so a later reader can re-run it and trust the result; this one
  **fails open** — re-running it would report the property as pinned either way.

  **The test itself is sound**, which I established with the counterfactual that does bite:
  disabling the retirement check (`callouts.py:888` → `if False and ...`) makes it fail with
  `assert ['unit is truck.'] == []` — a 12-second-stale identification spoken once the bearing
  returns, which is exactly the property the test claims. Replace the recorded counterfactual
  with that one. (Both edits were reverted; tree clean.)

---

### Optional Refinements

1. *(optional)* **The exemption's docstring understates what the exempt line actually says.**
   *"derived from its believed classification plus ownship's own position"* describes the
   **trigger**; the **utterance** is `_contact_report_text(facts, lead="Danger, ")`, which with an
   `EnrichmentContext` present also speaks the believed clock/range and the unit type. That is not
   a leak — all of it is belief, and the ungated pull path says the same — but a future reader
   deciding a new kind's membership on "it only speaks the cue" would be working from a narrower
   picture than the code's. One clause naming the rendered shape would close it.
2. *(optional)* **No test pins what the exempt line says with enrichment present.**
   `test_engagement_change_speaks_about_a_cockpit_masked_bearing` asserts
   `["Danger, ZU-23-3 Sergey."]` with no `EnrichmentContext`, so `relative_now` is absent and the
   clock/range branch never runs — i.e. the assertion covers the narrow form, and the form that
   carries the position is untested for this kind. Given that "does the exemption speak a
   position?" is the question the exemption's safety argument turns on, pinning the enriched
   string would be cheap and would make the answer legible in a test rather than in a reviewer's
   note.
3. *(optional)* **One clause in the docstring inverts its own mechanism.** *"a kind added here, or
   added to `_TEMPLATED_KINDS` under a mistaken reading of this one, exempts itself quietly"* —
   adding a kind to `_TEMPLATED_KINDS` **gates** it, which is the safe direction; only adding to
   `_OBSERVABILITY_EXEMPT_KINDS` exempts. The sentence as written tells a future reader the risk
   lies in the wrong set.
4. *(optional)* **The bounded-deferral test does not assert the premise it rests on.** At
   `back_in_view` it asserts silence without asserting that the contact is observable again, so a
   geometry regression that left it masked would let the test pass for the wrong reason. I
   verified by instrumentation that it is genuinely the strong case —
   `store.callout_observable(contact, now_sim=32.0)` is `True`, `last_observable_sim` is `32.0`,
   and the `CONTACT_CLASSIFICATION_CHANGED` event (t_sim 20.0) is still present in
   `unacknowledged_events`, so the silence is the `_consumed` retirement and nothing else. One
   `assert store.callout_observable(...)` would move that from my notes into the test.

**Also checked and clean:** no `src/` writes outside `callouts.py`; no behaviour change beyond the
one-predicate exemption; the 90/130 frame correction at `callouts.py:918-934` is comment-only and
its reasoning is right (`FORWARD_HEMISPHERE_HALF_WIDTH_DEG` is yaw-only against true heading,
`_CO_PILOT_MASK.rear_cutoff_deg` is body-relative including pitch and bank, so the two are not
frame-matched and "near no-op" is the honest claim); no debug instrumentation or TODO left behind;
no DCS-installation writes; no `world-model/data/` staging; the implementer's agent-memory file is
at the repo-root-relative `.claude/agent-memory/implementer/` and is committed; `mypy --strict`
re-run here rather than taken from the log.

---

### Verdict

**APPROVED WITH REQUIRED FIXES**

The behaviour is right and the mechanism is bounded. R1–R3 are all documentation, all small, and
all in the prose that this commit itself designates as the guard against the next silent
widening — R2 most of all, since a bar that admits `CONTACT_RANGE_CROSSED` is not a bar. None of
them needs a code change, a re-plan, or a user decision.

### Review Confidence

**Full read**, with the load-bearing claims re-run rather than read: both new tests exercised
under counterfactuals (the engagement test fails with the exempt set emptied; the deferral test
*passes* under the recorded `1e9` counterfactual and fails under the one that actually disables
retirement), the exempt/templated sets printed from an import proved to resolve to this worktree,
the deferral test's geometry premise instrumented, the `todo/questions.md` cross-reference
grepped, and the full `ruff`/`mypy`/`pytest` set run in this worktree at `4648532`.
