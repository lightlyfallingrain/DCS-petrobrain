# Planning & Process Lessons

- **When a fixture is fixed by switching from a filtered accessor to the unfiltered one, check whether production code still reads the filtered accessor on that same object — not just whether the test's final assertion reads correctly.** BL-12 Stage 1 narrowed `GroupStore.groups` to "currently observed"; a fixture that injected a `Group` directly (bypassing `reconcile`) lost visibility under the new filter, and was "fixed" by reading `store.remembered_groups` (the unfiltered superset) in the assertion instead. But `CalloutScheduler.tick`'s group-disclosure loop — the actual mechanism the test exists to exercise — iterates `store.groups`, so the loop body never ran for that group; mutation-testing the suppression check it was meant to pin (`return frozenset()` in place of the real check) left the test green. The rewritten assertion was true for a reason unrelated to the mechanism under test. Verify by mutation whenever a fixture dodges a narrowing by switching accessors (`plans/group-contact-identity/review.md`, Stage 1 round).

- **A finding's own suggested fix is a claim to measure, not a spec to implement — print the quantity the fix would test and the threshold it would test against, at the exact edge the defect occurs, before adopting it.** `BL-B58`'s filed option 3 ("exclude a newly-added member whose own gap fails the pair backstop") was accepted by the user over two alternatives on the strength of its description — but the absorbing edge was measured at 81.9 m against an 88.0 m backstop: it already passes, so the proposed re-check is a no-op. Two further candidates (a cluster-extent bound; any tick-local displacement test) failed the same way once measured: extent is identical between the correct and corrupted cluster, and the corrupted position persists across ticks rather than being tick-local. A defect description earns authority from being measured; its proposed remedy usually isn't, and inherits that authority by sitting next to it (`plans/group-cohesion-admission-gate/`, Architect pass).

- **A guard stated as a plan sentence with more than one clause ("no heading *or* bearing") has to be checked against every rendering branch the sentence names, not just the branch the implementation log's commit message discusses.** BL-12 Stage 4's extent guard suppressed the spoken heading clause but left a second, pre-existing clause (clock/range bearing) in the same render function unconditional — invisible from the committed test, which supplied no `EnrichmentContext` and so never reached that second clause at all, making "gated" and "never ran" indistinguishable from the test alone. Caught only by constructing the plan's own over-wide scene with real enrichment supplied and reading the actual rendered string (`plans/group-contact-identity/review.md`, Stage 4 round 1).

- **Plan "Affected Modules" sections can become stale if locked decisions are made after the list is drafted.** M7's initial "Affected Modules" list named `src/build/ingest_terrain.py` for SRTM-related work, written before the plan's Locked Decision 5 ("M6's ridge/valley classifier is explicitly NOT rerun here") was finalized. The explicit lockout made the named reference stale, but the reference remained in the plan text — Implementer correctly treated the explicit lockout as authoritative and did not touch `src/terrain/`. Lesson: after freezing a plan with locked decisions, do a final pass over the "Affected Modules" section to remove any stale references introduced by the later constraints, or accept a note explaining the divergence (M7 Stage 2 implementation discovery).

- **Commit boundaries are not always obvious in a multi-stage feature branch.** M7's Stage 3 implementation (control-point validation) was coded into existence but not committed to the branch immediately; Stage 4's implementation caught it during testing and prompted a commit. The delay didn't cause a defect, but it meant a single `git log` read across the branch didn't show complete Stage 3 work until Stage 4 was reviewed. Lesson: commit each feature stage as soon as its tests pass and checks clear, not when "the next stage makes sense to combine." Per-stage commits give Reviewer/DoD/future-sessions better visibility into the incremental development (M7 implementation timeline note).

- **Full-rebuild-only pipeline architecture should be surfaced during Architect's planning phase, not discovered as a gap during DoD acceptance testing.** M7's user raised a real architectural limitation ("destructive full-rebuild" per `build_region`'s current design) during DoD acceptance testing, after code and tests were complete. The user explicitly deferred it as not blocking M7, but the discovery pattern is worth noting: for future multi-stage pipeline features, Architect should explicitly ask "will the user want to run individual stages incrementally, or always full-rebuild?" and document the answer in the plan's constraints section. This surfaces the question when scoping is still cheap, not when implementation is done (M7 DoD acceptance-testing finding).

- **Never undo a live-patch-and-revert sanity check with `git checkout -- <tracked file>` if that file carries unstaged work.** Proving a new tripwire test actually fails on a reverted implementation (patch a constant/behavior, run the test, confirm red, then undo) is good practice — but `git checkout --` on a file with unstaged edits silently discards everything back to `HEAD`, not just the temporary patch. Happened live during binocular-optic Stage 3b: all of `optic_policy.py`'s Stage 3b edits were lost this way and had to be reconstructed from memory of the diff — the file looked "restored" (green tests) but was actually reverted past the pre-patch state. Use a scratch copy instead (`cp file /tmp/backup`, patch, test, `cp /tmp/backup file`) for this class of check, unconditionally (binocular-optic Stage 3b implementation, 2026-09-23).

- **A verification/inspection tool that doesn't exercise the real code path proves nothing about
  it, even when its output looks plausible for weeks.** `world-model/tools/inspect_terrain.py`
  rendered `comp.points` — the raw traced skeleton before smoothing or decimation — while the
  pipeline actually stored Chaikin-smoothed, later decimated `feature.geometry`. Every landform
  judgement call this project made by eye (including the 2026-10-01 "choose geomorphons" decision
  and the 2026-10-02 acceptance renders) was looking at something other than what the store held.
  Caught only when the relief-gate/decimation fix needed a render that matched the real output
  (`fix/landform-relief-gate`, 2026-10-04). Lesson: an inspection tool that reimplements "roughly
  what the pipeline does" instead of calling the pipeline's own functions is a liability that
  compounds the longer it goes unnoticed, because each use builds more confidence in the wrong
  picture.

- **A safety/deviation check can fail *toward* safety and still be a real defect.** An early
  version of `terrain.features._decimate_for_storage`'s deviation guard measured each original
  point against only the one decimated segment a windowing shortcut assigned it to, rather than
  the whole decimated polyline — this *overstated* true deviation by up to 5x on real traced
  lines near a genuine turn, so it never let through a decimation it should have rejected, it just
  rejected almost every decimation outright, neutering the fix while looking conservative. The
  check's own tests all passed throughout, because "never exceeds the cap" was never false — it
  was caught only by noticing an unrelated number (the real built output's point-density
  reduction) stayed far below the expected ~37x. Lesson: a safety check passing tells you it is
  safe, not that the thing it's supposed to enable is actually happening — verify the feature's
  own effect size independently, not just that its guard never trips (`fix/landform-relief-gate`,
  2026-10-04).

- **An approved plan can be wrong in a way only real data shows.** `contact-report-flood`'s plan
  specified a `CONTACT_DETECTED` suppression check ("suppress if any other not-yet-`lost`,
  plausibly-same contact exists") that reads correctly and passed Architect review. Implemented
  literally, it has a failure mode no synthetic fixture caught: when N contacts are founded in the
  *same poll* and are pairwise plausibly-same, each sees every other as a live peer and suppresses
  — a 4-vehicle cluster founded together produced zero spoken lines, directly violating the plan's
  own stated acceptance bound. Found only by running the real scheduler against a real sortie
  snapshot; the fix (exclude same-poll peers) cost one boolean clause. General shape: any "does
  another live X already exist" dedup check scored once per batch must explicitly exclude peers
  from the *same* batch unless the guarded-against mechanism can originate within one batch — a
  hand-picked fixture with contacts founded on different polls will never exercise this. Second
  time in one week real data overturned a design that had already passed review (see the
  geomorphons deviation-check entry above) — a pattern worth treating as recurring rather than
  isolated (`plans/contact-report-flood/plan.md`, `implementation.md`).
- **When a public constant changes shape (e.g. int → dict-keyed-by-theatre), grep every real call
  site of the functions that read it, not just the plan's named "Affected Modules" list — tests
  that call the function directly are easy to miss alongside the ones that only monkeypatch it.**
  `multi-theatre-afghanistan`'s plan named the three pipeline tests that monkeypatch
  `parse_towns_lua`/`parse_beacons_lua`'s now-dict `EXPECTED_*_COUNT` constants, but missed
  `test_towns_lua.py`/`test_beacons_lua.py`, which call the real parsers directly and
  `monkeypatch.setattr` the old bare-int constant — a pattern that would have silently replaced
  the new dict with an int rather than failing loudly. Caught by grepping every call site across
  both `src/` and `tests/` before starting, not by trusting the plan's own list.

- **A plan's "context already established" section (meant to avoid re-deriving prior findings)
  can itself overstate how far existing wiring actually reaches — verify the real consumer
  function before treating the plan's forward-reference as confirmed.** `multi-theatre-
  afghanistan`'s plan stated the mission-interpreter `theatre` field "carries through to ... the
  runtime artifact body-layer already loads at startup ... → `load_mission_understanding`",
  reading as if that function already parsed it. It did not — the field existed in the JSON
  artifact, but body-layer's own loader only ever parsed `phases`/`route`; the Stage 5 code to
  read `theatre` had to be written, not merely wired through. The plan's own Stage 5 prose
  already assumed this field would be readable, so the gap was implemented in scope rather than
  escalated, but it would have been worth catching before implementation began by actually
  reading `mission_phase.py` rather than trusting the context section's forward-reference.

- **Accepted debt is only accepted once its unblock condition has been *executed*.** A declined
  review fix can be the right call and still leave the project worse off, if the escape route it
  names has never been run. `doc-provenance-gate.sh` was deliberately left unwired with a
  carefully-argued comment, a reproducible counterfactual measurement, and an explicit exit — *"one
  command, `.claude/scripts/doc-provenance-refresh.sh`, when the document-graph work unpauses."*
  Running that command aborts `rc=1` on its first validated citation and writes nothing, so the
  condition could never have been met as written; the debt was recorded as temporary while being
  permanent. The reasoning for a departure gets scrutinised because it is an argument; the
  one-line remedy attached to it reads as housekeeping and gets none. **Run the unblock command at
  the moment the debt is accepted, and paste what it did** — the cost is one command, against a
  caveat that otherwise expires silently (`plans/obsidian-links-and-tags/dod-check.md` §2).

- **Generalising a hardcoded scope has two halves — discovery and resolution — and fixing one
  reads as fixing both.** `doc_provenance.py`'s entry *discovery* was widened from a hardcoded
  `audio-adapter/ROADMAP` to all seven split directories, verified by a measured 22→245 entry
  count; the same file's *path resolution* kept `f"audio-adapter/research/{filename}"` as the
  default for a bare `research/<file>.md` citation, so 17 citations now resolve confidently into
  the wrong subproject. The widened half makes the symptom appear only *after* the fix, which
  invites reading it as a new defect rather than the old one's remainder. When removing a
  hardcoded scope, grep the whole module for the literal rather than the function — and where a
  bare basename could exist under more than one subproject (`2026-10-05-security-audit.md` does),
  a fixed prefix is unfixable by any default: it has to resolve relative to the citing document
  and reject the ambiguous case rather than guess (`plans/obsidian-links-and-tags/dod-check.md`
  §2c).

- **A plan's own cost table can cite the wrong column of its own measured data and still read as internally consistent — check which depth the caller actually requests, not which depth the headline number assumes.** `group-collapse`'s plan multiplied a realistic roster size by the *group*-depth (shallowest) column of its own measured per-member cost table to produce "~5 µs/tick shallow," but the push-path caller it was describing actually requests *sub-class* depth, a different column 5–47x larger. The arithmetic was self-consistent and the conclusion ("depth is affordable") still held at the correct figure, but the understated number would have been cited later as headroom that does not exist. Caught by Performance Review re-deriving the figure from the same measured table rather than trusting the plan's own multiplication (`plans/group-collapse/performance-review.md`, `plans/group-collapse/plan.md` §1 correction note). Same failure shape as the forest-occlusion poll-rate bullet above — a plan's numeric claim needs its inputs checked against the actual call site/constant, not just checked for internal arithmetic consistency.

- **A number cited from a docstring's neighbouring paragraph is not the same claim as the number the code path actually computes — recompute `size_m / threshold` directly rather than reusing a nearby figure that reads as though it answers the same question.** `visibility.py`'s own docstring carries "~9.3 km" as an unrelated S-300 atmospheric-limit observation, explicitly flagged there as not usable to bound the naked-eye presence threshold. It was nonetheless cited as that threshold's upper bound twice — once in `configurable-constants/review.md` (corrected in the same review, to ~2.3 km) and again in `emitter-visibility/review.md`'s own Required Fix #2 (corrected by the implementer, to 5469 m, the real `RESOLUTION_ANGULAR_RADIUS_RAD` bound). Both corrections required recomputing `size_m / threshold` from the live constant rather than trusting a figure that was adjacent to the right paragraph. A stale or borrowed number reads as more authoritative the more official-sounding its source sentence is — check what question it was actually answering, not just whether it looks like the answer to the question in front of you.

- **A free-form string field that is "self-description today" is only a discipline, not a guard, the moment something more convenient starts riding it — add a closed field instead, even when it costs one more assignment site.** `Observation.provenance`'s first production use was every value a project-chosen description string, which made widening it into `Percept` (an otherwise-truth-free boundary type) look safe by inspection. It was not: the field's *declared type* was unconstrained `str`, one existing value (`hybrid_source.py`'s `"...ambiguous_association"`) already carried internal pipeline detail rather than perception, and nothing mechanical would have stopped the next producer going further. The fix that held was a closed mapping (`Percept.emitter_kind`, `_EMITTER_KIND_BY_PROVENANCE.get(...)` with no override) rather than loosening the boundary test to match what had already crossed — confirmed by mutation twice (Reviewer's fix-pass, Security's deep analysis) that the restored guard is live, not a comment (`plans/emitter-visibility/review.md` Required Fix #1, `security.md` finding 3). When a boundary type's guard test needs editing to let a change through, that is usually the signal to narrow the field being added, not the test.

- **Retrofitting a "defer the speaking" mechanism onto several existing handlers can silently defer the action too, when a handler's side effect and its spoken acknowledgment were written as one step.** Voice-latency-instrumentation's Stage 6 added a shared `_speak_or_defer` helper so a positional readback waits for the channel to clear rather than speaking over another utterance; five of six handlers already resolved/acted unconditionally before rendering text, so wrapping only the render was safe. The sixth (`_handle_mark_target`) had always written the mission-memory mark and spoken its acknowledgment as adjacent lines in one method, and the first draft moved the *write* inside the deferred closure along with the text — so a pending entry dropped by a later refusal or mission reset discarded the mark the pilot asked for, not just its echo, with no error anywhere. Caught only by running the refusal/reset path and checking the write actually happened, not by reading the diff (`plans/voice-latency-instrumentation/review.md`, Required Fix 1). Lesson: when wrapping several existing handlers in a new defer mechanism, check each one's side effect independently — a handler whose action and acknowledgment look like one step is the one most likely to get bundled into the deferred half by accident.

- **A completeness/parity invariant drafted against an *inferred* structure for an external file can undercount by a whole term once the real structure is read — a plan that says "heads = handled + unhandled" is a guess about how many ways a unit can resolve, not a fact.** BL-B90 Stage 0's plan specified the effector-registry generator's fail-closed completeness check as two-way (every `elements[...]` head is either emitted or unhandled), written against `mi24p-command-surface.md`'s own prior inference about the real Lua file. Live recon (`aircraft-layer/research/2026-10-23-mi24p-clickabledata-forms.md`) found a third, large category the plan never considered: 235 of the file's 749 heads are post-assignment field *patches* on an already-defined element, not new definitions — a generator built strictly to the plan's two-way text would have silently misclassified all 235 as either spurious unhandled entries or an undercount. The fix was a third arithmetic term (`heads == handled + unhandled + patches`), caught before the real run rather than after. General shape: when a plan's "fails closed" invariant is written before the external format it checks has been read firsthand, treat the arithmetic itself as an open question for the recon pass to confirm or correct, not just the field names and helper list.
