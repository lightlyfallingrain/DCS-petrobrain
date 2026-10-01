### Debug Report

### Observed Issue

2026-10-01 acceptance sortie on `feature/group-reporting` (merged `main` @ `51a174e`). The user's
own words, in order of arrival during this investigation:

1. *"still 'repetitive' 'ground 12 o'clock 4 km' for each unit individually."* / *"'a couple of
   contacts, 12 o'clock, 2 km' also times x"* -- the original report, read as two symptoms:
   under-merging and a repeating group line.
2. *"grouping seems to work better the closer I get to the target. But to get sane reports, I need
   to be very close. Should work at any distance."*
3. Six consecutive real spoken lines, `t_sim` 296-352 (from `dcs-belief-truth.jsonl`'s `kind:
   "speech"` records), each identical except for the range clause, roughly every 500 m of opening
   range:
   `"Danger, triple A. Also a SA-3 launcher, three armor, two contacts, a triple A, a truck and
   three infantry, 7 o'clock, 1 kilometre."` ... same text at 1.5/2/2.5/3/3.5 km. The user's own
   words: *"while it probably is caused by distance changing, that's still constant reports that
   add no value. I know it's there from the first report. And repeating the whole group
   composition every time adds noise."*

Finding #3 settles what #1 actually was: grouping at the speech layer **does** work (that one line
already aggregates ~11 units into one disclosure with composition) -- the complaint is cadence and
verbosity on an already-formed group, not failure to aggregate.

### Hypothesis

Two independent defects were investigated under one task; only one turned out to be real and
fixable at this layer.

**A. (Confirmed, fixed) `CalloutScheduler`'s group-disclosure trigger compares the full rendered
line, which bakes in the clock/range clause, against the group's last-spoken signature.** Range
drifts on essentially every tick a group is being approached or departed, so the comparison almost
never matches, and the entire composition is re-spoken on a pure range-bucket change -- exactly
symptom #3, and the mechanism behind the second half of symptom #1 (*"'a couple of contacts...'
also times x"*).

**B. (Investigated, not confirmed as a live defect; a speculative fix was built, found to
regress an existing deliberately-pinned test, and reverted) Position-uncertainty-unaware group
cohesion test.** The leading theory after finding #2 was that `belief.groups._cluster_contacts`'s
pairwise world-space-metre test, applied to a freshly founded contact's noisy fused position
(hundreds of metres of RMS uncertainty at a few km of range), caused real site members to read as
too far apart to cohere until enough looks had accumulated -- "better closer" as a side effect of
estimate noise shrinking with more looks, not of range itself. Replaying the real sortie trace
refuted this as the operative bug (see Evidence): the unmodified mechanism already converges to the
correct group once enough looks exist, and a few seconds of individual reports on a brand-new
contact is this system's analogue of a human copilot needing a moment to resolve what he is
looking at, not a defect needing a code fix.

### Evidence

**Reproducing symptom #3's mechanism (A) directly.** `belief/speech.py::render_group_disclosure`
builds the composition (`"Danger, X. Also Y"` / `"Pair of Zs"` / bare `"Group"`), then
unconditionally appends `", {clock} o'clock, {range}"` before the trailing period. `belief/
callouts.py::CalloutScheduler.tick`'s two group-candidate checks compared `speech.text ==
belief_group.last_spoken_signature` -- the *whole* string, range clause included. A direct replay
confirms the shape: a three-member undifferentiated group spoken once as `"Group, 12 o'clock, very
close."`, then with ownship moved 2 km away and nothing else changed, re-renders as `"Group, 12
o'clock, 2 kilometres."` -- different text, same group, same composition, immediately eligible to
speak again under the pre-fix comparison.

**Investigating (B) against the real flown trace, `/Users/sg/dcs-detection-trace.jsonl` +
`/Users/sg/dcs-belief-truth.jsonl`.**

- Isolated the real continuous sortie segment (both files are append-mode logs spanning many
  separate logger launches within one test session -- `dcs-belief-truth.jsonl`'s `t_sim` resets to
  near-zero 16 times; the segment matching the detection trace's `CONTACT_1` at `t_sim=2.041` runs
  to `t_sim≈330s` in one file and, in the larger file collected later, the single longest run
  (`CONTACT_1` at `t_sim=58.6`, contact numbers increasing monotonically with time) runs to
  `t_sim≈1528s` with 50+ contacts.
- `cluster_member_object_ids` (the *perception*-layer, angular, naked-eye blob -- `perception.
  clustering.cluster_candidates`) never exceeds length 2 anywhere in the trace (3458 admitted
  rows). Read the code: this is real, proper single-link union-find with full transitive closure
  (`for i: for j>i: if not separable: union(i,j)`), not a pairwise-only bug -- the ceiling reflects
  the angular separability predicate rarely admitting a 3-way merge at the geometries this flight
  produced, not a structural defect in that algorithm. This layer is unrelated to the user's
  complaint: it governs how many real objects one naked-eye *Observation* claims to be, not
  whether several already-individuated *Contact*s get reported together.
- `belief.groups._cluster_contacts` (the belief-layer mechanism the user's complaint is actually
  about) is *also* real union-find with full transitive closure -- confirmed by reading it, not
  assumed.
- Replayed the real S-125-site-plus-armor encounter (`CONTACT_11`-`17`, `t_sim≈128-240s`) through
  this exact algorithm using the sortie's own logged `believed_x/z` and `position_uncertainty_m`.
  At `t_sim=128-145s` position uncertainty was 400-900 m while the site's true inter-member
  spacing was 14-157 m -- the cohesion test, using *raw* believed positions with no uncertainty
  term, flickered (partial 2-member clusters forming and dissolving as more members were founded
  and positions refined). By `t_sim≈194s`, using the **unmodified** algorithm and the sortie's own
  believed positions, all 7 members formed one cluster -- matching the real spoken output at that
  point in the sortie (`"Danger, short range SAM. Also three armor..."`).
- A second, larger real site surfaced in the bigger belief-truth file: an S-300 battery
  (`CONTACT_3/8/15/16`, `tr`/`sr`/`54K6 cp`/`64H6E sr` components) with *true* ground-truth
  inter-member spacing of 236-838 m -- large for a single-vehicle backstop
  (`GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS * 7m default ≈ 140m`), since none of those component
  names match `object_model.py`'s keyword table and all fall back to the generic unknown-size
  default. This is real and confirmed from ground truth (not noise), but it is a **calibration**
  question (how should a tactical site's allowed spread relate to a single member's physical
  size, when the two are unrelated for an air-defence battery) that a single constant cannot
  honestly answer from one data point in each direction -- flagged below, not patched.
- **Built, and reverted, an uncertainty-budgeted version of (B).** The pairwise test became
  `effective_gap = max(0, raw_gap - (unc_i + unc_j))`, budgeting each member's own
  `Contact.position.radius_m()`. This passed its own new tests but broke
  `tests/test_callouts.py::test_2c_transcript_fixture_renders_four_lines_not_seven` -- a
  deliberately-pinned regression test from the original group-reporting work, asserting that two
  infantry 260 m apart at 500 m range must *not* merge (36 m backstop at that scale). Measured why:
  a single naked-eye look at 500 m range already carries ~300 m of RMS position uncertainty in
  this codebase's `position_belief` model, so the uncertainty budget alone (600 m combined)
  swallowed a 260 m gap nearly 10x the relevant backstop. Confirmed with a direct script
  (`c.position.radius_m()` printed after one `ContactStore.tick`), not guessed. That single-look
  covariance figure may itself be too loose, but revising it is a `belief.position_belief`
  calibration question, out of scope here, and not something this debug pass has evidence the
  user is actually hearing as a problem (see next point).
- **Finding #3 (the six identical-except-for-range lines) directly confirms grouping already
  works in the field** -- the user's own eleven-unit, correctly-composed line. This re-weights (B)
  down: there is no live evidence the pilot is hearing a failure to aggregate, only a failure to
  stop re-announcing an aggregate he already has. Given that, and given the regression a
  uncertainty-budget fix caused, (B) was not pursued further.
- **`gaze_label` swinging across the six lines while reported bearing holds steady at 7-8
  o'clock, checked against the observability gate rather than assumed:** `belief/callouts.py`'s
  group-candidate loop (`for belief_group in store.groups: ...`) carries no gaze check at all, and
  neither does the per-contact `WATCHED_ONLY_KINDS` path (`belief/contacts.py`'s range-crossing
  block gates on attention + belief freshness, never on current gaze -- confirmed already in
  `plans/callout-outside-gaze/debug.md`, a prior, separate investigation of the identical
  principle). This is deliberate, documented design: Petrovich reports on an already-known
  contact/group from memory regardless of where he is currently looking, exactly matching the
  user's own words here (*"I know it's there from the first report"*). Not a defect.
- **Secondary findings surfaced by the coordinator's review, checked and resolved as non-issues
  for this task:**
  - `believed_cardinality_lo/hi == 1-1` for every contact near closest approach is **not** the
    same question as group-level aggregation -- cardinality is a within-one-`Contact` count (how
    many real objects does *this* belief stand for), while a `Group` is several already-
    individuated `Contact`s. Checked the actual geometry behind the "12 distinct contacts" sample
    the coordinator flagged: true inter-contact distances there ranged 390 m to several km
    (scattered sightings across a wide scan, not one formation), except for the S-300 site
    discussed above, which *is* the site B describes.
  - `believed_classification_value == "OP_GROUPSOMETHING"` is ED's "unclassified, possibly
    several units" catch-all string at the `PRESENCE` specificity level (`belief.classification.
    PRESENCE_CLASS`/`object_model.DEFAULT_OP_CLASS`) -- it has no relationship to `belief.groups.
    Group` at all, and does not reach the callout path "as if it were a group." The word "ground"
    in early single-contact lines is `_unit_type_display`'s fallback for this same presence level,
    unrelated to grouping.
  - `detection_trace.jsonl` stopping at `t_sim≈290s` while `belief-truth.jsonl` from the same
    session continues to `t_sim≈1521s`: `DetectionTraceWriter` opens in append mode, flushes every
    5 polls, and flushes again on `close()` -- a graceful shutdown cannot lose more than 4 polls.
    Both files are demonstrably the product of many separate logger launches within one test
    session (`belief-truth.jsonl` resets 16 times); the simplest explanation consistent with the
    writer's own flush/close behaviour is that `--detection-trace` was not passed on every later
    launch, not a writer defect. Not chased further -- no evidence of code fault, and reproducing
    the actual CLI invocation history was not possible from the artifacts alone.
  - Four admitted rows with an empty `cluster_member_object_ids` list: `annotate_admission` is the
    only writer of that field and always receives a non-empty tuple from a `Cluster.members`
    built by `cluster_candidates` (which never returns an empty-member group). Could not reproduce
    or explain from static reading alone in the time available; genuinely still open, flagged for
    a follow-up debug pass rather than guessed at here.

### Fix Applied

**Mechanism A only.** `belief/speech.py`: added `OutgoingSpeech.content_signature: str | None =
None` (defaults to not-set for every template that never needed the distinction).
`render_group_disclosure` now captures the composition text *before* appending the clock/range
clause (and the `watched` clause is added to both `text` and `content_signature` identically, since
attention state is real content, unlike position), and returns it as `content_signature`.

`belief/callouts.py`: both of `CalloutScheduler.tick`'s group-candidate checks (the scoring pass and
the re-render-at-speak-time pass) now compare `speech.content_signature` against
`belief_group.last_spoken_signature` instead of `speech.text`, and `mark_group_spoken` is now
called with the content signature rather than the full rendered line, so the stored signature and
the comparison stay consistent across ticks. The spoken `text` itself is unchanged -- the pilot
still hears the current range every time the group speaks; the fix only changes *when* it speaks.

No change to `belief/groups.py`'s cohesion mechanism (mechanism B's uncertainty-budget attempt was
written, tested, found to regress `test_2c_transcript_fixture_renders_four_lines_not_seven`, and
reverted -- see Evidence). The module's docstring for `_cluster_contacts` now records this
investigation (what was tried, why it was reverted, and what a real fix would need) so it is not
re-derived blind on a future pass.

### Open, flagged for the user rather than fixed here

1. **Point 3 of the sortie report -- re-reports should be a delta, not the whole roster.** Once a
   genuine refinement legitimately re-triggers a group's disclosure (a new member resolves, a
   classification firms up, the threat lead changes), the current design still speaks the *entire*
   composition again (`render_group_disclosure` has no notion of "what's new since last time,
   specifically"). The user's own words: *"repeating the whole group composition every time adds
   noise."* The honest minimal change would be for `render_group_disclosure` (or a caller) to diff
   the new member-facts against whatever was last spoken and render only the delta on a
   content-change re-trigger -- but that changes what the disclosure *says*, not a bug in what it
   currently does, and is a design decision for the user, not this debug pass.
2. **The S-300-battery backstop mismatch (finding B's second site).** `GROUP_REPORTING_COHESION_
   GAP_UNIT_WIDTHS` (20 unit-widths of a single member's believed size) cannot honestly cover both
   an infantry pair (needs ~36 m to stay strict, confirmed by the pinned regression test) and an
   air-defence battery (needs >840 m, confirmed from this sortie's own ground truth) with one
   constant, because a site's spread is a property of the *site type*, not of any one member's
   physical size. Needs either a per-class-of-formation backstop or a different cohesion currency
   entirely (e.g. a Mahalanobis-style test, or hysteresis that favours an already-formed group's
   continuity over re-litigating formation every tick) -- an architectural question, not a
   constant to retune blind.
3. **Four empty-`cluster_member_object_ids` admitted rows** -- confirmed present in the trace,
   not reproduced or explained from static reading. Worth a short follow-up debug pass with a
   live repro rather than guessing from the artifact alone.

### Verification

- `tests/test_speech.py::test_render_group_disclosure_content_signature_excludes_clock_range` --
  new, pins that `content_signature` is stable across a range-only change while `text` changes.
- `tests/test_callouts.py::test_opening_range_alone_does_not_re_speak_the_group` -- new,
  integration-level reproduction of the exact sortie symptom (a formed group, then ownship opens
  range across several polls with no composition change): confirmed to fail before the fix
  (`speech.text` differs from the stored full-text signature every time, so the group re-speaks on
  every tick) and pass after it.
- Full `body-layer` suite: `1351 passed, 4 xfailed` (`pytest tests -q`), including every
  pre-existing `belief.groups`/`belief.callouts`/`belief.speech` test unchanged in behaviour (the
  reverted mechanism-B attempt's own regression, `test_2c_transcript_fixture_renders_four_lines_
  not_seven`, passes again with `belief/groups.py` back to its original pairwise test).
- `ruff format src tests --check`, `ruff check src tests`: clean.
- `mypy src`: `Success: no issues found in 53 source files`.
