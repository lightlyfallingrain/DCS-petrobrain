# Debugging & Root-Cause Diagnosis

- **A confident, code-derived reproduction can be a real defect on an unreachable path, while the
  user's own one-line diagnosis names the path that actually fires.** The `position-belief-runaway`
  debug session's own hypothesis (ill-conditioned triangulation — near-parallel disagreeing looks
  intersecting far outside either input) reproduced the reported numbers exactly, and was fixed.
  But the pre-existing association gate in `association_over_time.passes_gate` already rejects
  that large a single-poll disagreement before it ever reaches fusion in production — a fact
  established only by tracing `ContactStore.ingest`'s call path, not by the reproduction script
  itself. The mechanism that actually produced the live 87.5 km callout was a slow directional
  drift (many small, individually-plausible steps, each passing every existing gate), which is
  exactly what the user's own diagnosis named: *"position uncertainty needs a gate, cannot be
  further than detection range."* That one line pointed at a missing invariant (nothing checked a
  fused position against physical detection range at all), not at a numerically fragile formula.
  Lesson: when a live defect prompts a debugging session, a hypothesis that reproduces the
  reported numbers under direct construction is not yet shown to be the *production* path — trace
  whether the gates the real pipeline runs the input through would actually let that input reach
  the reproduced code, and weigh a domain expert's structural diagnosis ("there's no gate for X")
  as seriously as a numerically-confirmed mechanism (`position-belief-runaway` debug report +
  review, 2026-09-25).

- **A correct measurement that a test's premise is false on this host is not, by itself, evidence
  the test is out of scope or untestable here — it may mean the test depends on the wrong premise
  and should stop depending on it.** `connection-reporter-flaky`'s debugger measured, correctly,
  that a `bind()`-but-never-`listen()`-ed socket does not refuse `connect()` instantly on this
  host (it blocks ~5.0 s) and concluded the test "cannot presently be driven to a real pass on
  this particular machine" — out of scope. The reviewer's first pass reproduced the identical
  measurement and reached the identical conclusion, independently. Both were wrong in the same
  way: the test's own docstring claimed to test "connection refused," and the real fix was to stop
  depending on real socket timing at all (monkeypatch `urlopen` to raise the same exception shape
  a refusal produces) — not to leave a correctly-diagnosed, always-failing test unfixed. Two roles
  made the identical inferential error on the same ticket in the same session; the lesson is to
  treat "this premise is false on this host" as a prompt to ask whether the premise itself should
  change, not as a verdict that the test cannot be fixed (`connection-reporter-flaky` debug + review
  reports, 2026-10-23).

- **When two debug views disagree on "what is the current state," check which one reads the
  commanded value and which reads the applied value before assuming either is wrong on its own
  terms.** `--eyesight-view` and `--pov-view` showed different gaze directions for the same poll,
  same optic, because `--eyesight-view` read `runner.scan_plan` (the *commanded* free-scan plan,
  set once per poll before any override) while `--pov-view`'s sight-tier branch already read the
  sight head's real world direction. The commanded value and the applied value only diverge when
  something overrides the plan without writing back onto the field every other reader assumes is
  current (here: a fixed look — sight aim or a binocular glass phase — applied onto a *different*
  attribute, `OpticState.actual_aim_*`, never back onto `scan_plan`). The fix was not "pick the
  right one of the two existing readers" but a third function reading the actual per-case inputs
  `_apply_active_gaze` itself reads, because writing the resolved value back onto the shared field
  would have fixed one case and broken the other (the sight override's own frame is body-relative,
  wrong for a heading/horizon-relative display). General form: a "plan" field and an "actual/
  applied" field that can diverge need every downstream reader of "current state" to go through
  one shared resolver, not through whichever field happened to be convenient at each call site
  (`optic-views-actual-look` debug + review, 2026-10-26).
