# Model Selection & Local LLM Serving (brain-layer BR-1)

- **A smaller reasoning model can be slower than a larger one — reasoning-token count dominates
  latency, not parameter count.** Measured on the same prompt, warm: `qwen3:14b` answered in 16.0 s,
  `qwen3:4b` took 32.7 s — nearly twice as long from the *smaller* model, because `/no_think` does
  not reliably suppress `qwen3`'s reasoning trace and the reasoning trace itself is what costs the
  seconds, independent of model size. Lesson: for a latency-sensitive local-model pick, measure the
  actual wall time of the target model family under the target prompt shape before assuming smaller
  = faster; a reasoning-capable model's thinking budget can dominate parameter-count effects
  entirely (`plans/brain-layer/plan.md` Measurement 1, 2026-09-25).

- **A model recommendation based on "what's already on disk" is a different claim from "the current
  landscape was surveyed," and a reviewer without domain expertise can still catch the gap by
  knowing a release date.** The architect's original D6 pick (`qwen2.5:7b-instruct`) came from
  measuring two models that happened to already be pulled locally. The user's objection —
  "qwen2.5 is old, 2 years at this time... do investigation... first by web search" — was correct
  on a fact anyone could check (qwen2.5 released September 2024) without needing to know anything
  about model internals. The resulting search-first survey (`body-layer/research/
  2026-09-25-small-local-model-survey.md`) then vindicated the objection on the merits too: both
  replacement candidates (`qwen3:4b-instruct-2507-q4_K_M`, `granite4:micro`) matched or beat the
  incumbent's best behaviour at under a tenth of the latency and roughly half the disk footprint.
  Lesson: "measured what was on hand" and "surveyed what exists" are different claims, and a plan
  should say which one it's making — a recency check on a named model doesn't require domain
  expertise, only checking a release date (`plans/brain-layer/plan.md` D6 revision, 2026-09-25).

- **A plan's affected-files table naming a specific dependency is not itself a decision to use it.**
  The brain-layer plan's own affected-files table named FastAPI for `server.py` in one line, but no
  numbered Decision in the plan actually argued for that choice, and every other subproject in this
  repo declares `dependencies = []`. The implementer built on stdlib `http.server.
  ThreadingHTTPServer` instead — a structural copy of `audio-adapter/src/server.py`'s existing
  shape — and documented the refusal in `server.py`'s own docstring. Lesson: a table listing a
  dependency in passing does not carry the same weight as a reasoned Decision section, and per
  root `CLAUDE.md`/`AGENTS.md` a new third-party dependency is escalation-worthy on its own — an
  implementer should treat an unargued dependency mention as a candidate to challenge, not a
  commitment to honor (`plans/brain-layer/implementation.md`, 2026-09-25).

- **A thread-pool timeout wrapped around a blocking call bounds the caller, not the call.**
  `brain-layer/server.py`'s `_run_job` races `Decider.decide()` on a `ThreadPoolExecutor` and gives
  up after `decide_timeout_s`, but `shutdown(wait=False)` does not — cannot — stop the underlying
  call: Python has no mechanism to preempt a blocked thread. A genuinely hung call (not just a slow
  one) leaks its worker thread permanently; the timeout only lets the *caller* move on. The actual
  fix has to live one layer down, in whatever can make the blocking call itself return — here,
  `OllamaClient`'s own socket-level `urllib` timeout. A server-side wrapper timeout is worth keeping
  anyway as a decider-agnostic backstop, but it must be understood as bounding the symptom, not the
  cause (BR-1 Stage 2 performance review prerequisite 2, `plans/brain-layer/performance-review.md`).

- **A safety claim that holds in one drift direction is not thereby safe in the other, and adding a
  second trust boundary nearby can flip a previously-true claim false.** `brain-layer`'s
  `CLASSIFY_COMMAND_VOCABULARY` and body-layer's mirrored `OFFERED_CONFIRM_VOCABULARY` were
  documented as safe to let drift ("a mismatch here costs accuracy, never safety") when only the
  wider `DISPATCHED_COMMAND_TOKENS` check existed. Once a stricter membership check was added
  specifically against the offered vocabulary, the claim became true in only one direction (the
  list widening) and false in the other (a token *removed* from what's offered but not from the
  mirror re-admits exactly the gap the new check was built to close). The bug was in the docstring,
  not the code — caught only because Reviewer traced both drift directions explicitly rather than
  accepting the existing comment. Lesson: when a new check is added near an existing "safe to
  drift" claim, re-derive the claim rather than trusting it still holds — the claim's truth can
  depend on what else reads the same data, not just on the data itself (BR-1 Stage 2
  Security/Performance fold review, `d51a25b`, 2026-09-25).

- **A fix that makes a silent failure loud can introduce a new silent failure of its own — and a
  docstring claiming the mechanism is safe is not evidence that it is.** `aircraft-layer-hardening`'s
  first `CollectorServer.serve_forever` `accept()` guard classified a clean shutdown by re-reading
  `self._socket` inside the `except OSError` block, and the implementer's own docstring,
  `implementation.md`, and agent-memory file all stated this was safe because the attribute was
  "never re-read after the exception fires." That claim was false: `close()` sets `self._socket.close()`
  then `self._socket = None` as two separate statements, and a blocked `accept()` could raise from the
  `close()` call itself while `self._socket` still held the old object — misclassified as a real
  failure on 161 of ~230 real shutdowns (measured, not theoretical), teaching an operator to ignore
  the very ERROR line the fix existed to raise. The correct fix was an explicit flag
  (`self._shutting_down`) set as the first statement of `close()`, before the socket is actually
  closed, so the flag-write happens-before the syscall that can trigger the exception — inference
  from a mutated value replaced by an explicit signal set before the mutation. Lesson: when a fix's
  whole justification is "condition A is distinguished from condition B by reading attribute X, and
  that's safe because X is never re-read," don't accept that from the docstring — reproduce the
  actual race (run the real shutdown path repeatedly) before trusting it, and prefer an explicit
  flag written before the racy event over inferring intent from a value another thread also mutates
  (`plans/aircraft-layer-hardening/review.md`, `ac0bff9`, 2026-09-26).

- **A regression test that only asserts final outward status can pass for a reason unrelated to the
  bug it claims to guard against — and a reviewer's own suggested fix mechanism can share the same
  blind spot.** `audio-adapter-review-findings`'s negative-`Content-Length` tests asserted only
  `status == 400`, which passed against both the pre-fix and post-fix `server.py` — the pre-fix code
  already had an incidental `self.rfile.read(length) if length > 0 else b""` guard that took a
  different rejection path (JSON-parse failure on an empty body) to the same status code, so the
  hang the security review described was never actually reachable through this test. The reviewer's
  first suggested fix (spy on `rfile.read`, assert it's never called with a negative count) would
  *also* have passed on both versions, for the identical reason — the pre-fix ternary keeps that
  call from ever happening either way. What actually distinguished the two versions was the response
  body's specific error message, visible only once someone read both code paths' literal source
  rather than reasoning about them. Lesson: a review's suggested test mechanism is a hypothesis, not
  a verified fact — before writing the assertion, revert to the pre-fix code and run the candidate
  test against it; if it passes, the mechanism doesn't discriminate, no matter how plausible it reads
  (`plans/audio-adapter-review-findings/review.md` round 2, `1b2e337`, 2026-09-26).

- **A tuning-parameter widening (a threshold, a window, a word set) tends to fail in rounds, each
  round's single rule correct about the case that motivated it and wrong just outside that case —
  and each round is found by running the real adjacent subsystem end to end, not by reasoning about
  it or trusting a test that supplies its own default for the parameter under scrutiny.** The
  confirm-band affirmatives fix (widened `_AFFIRM_WORDS`/`_NEGATIVE_WORDS`, `CONFIRM_WINDOW_S`
  8.0→15.0s, new `CONFIRM_LATE_ANSWER_GRACE_S`) took five review rounds to land safely: first word
  is an answer word → swallows a real utterance opening with that word; require the whole transcript
  to match → breaks "roger, cancelling" style acknowledgements; and so on, each fix correct about its
  own motivating input and wrong on the next one probed. Every round was actually caught by
  constructing a real transcript and running it through the live matcher/`handle_transcript`, never
  by inspecting the widened set and reasoning "this looks safe." This is now the second/third time
  this exact lesson has surfaced in this project's retro material (see also the shutdown-race and
  audio-adapter-review-findings entries above) — it is a process pattern, not a one-off code note:
  any change that widens what a fixed set/threshold/window accepts should budget for multiple rounds
  of adjacent-subsystem end-to-end probing before it is trusted, not one plausible-looking pass
  (`plans/confirm-band-affirmatives/review.md`, five rounds, `867cbfe`, 2026-09-28).

- **A measured data-quality figure recorded correctly in a roadmap/docstring is not the same as
  that figure reaching its consumer.** M7's SRTM-vs-DCS elevation accuracy (mean −7.19 m, stddev
  11.52 m) was measured and written down accurately in `world-model/ROADMAP.md` three weeks before
  a real sortie found `query.line_of_sight.line_of_sight_clear` treating the same grid as exact —
  a unit sitting under a cell that overestimated ground height by close to that stddev read as
  permanently masked from every angle. Neither the measurement nor the consumer code was wrong in
  isolation; the defect lived in the unchecked gap between them. Fixed by adding an explicit
  tolerance sized to the recorded stddev (`_TERRAIN_TOLERANCE_M = 12.0`), not by re-measuring
  anything. Worth checking, whenever a store gains a new measured error figure, whether its
  consumers were re-examined against it — a number sitting in a research note does not audit its
  own callers (`plans/missed-aaa-detection/debug.md`, `fix/los-elevation-tolerance`, 2026-09-29).
- **When a design decision rests on lived-cockpit intuition rather than code, expect it to be
  refuted within minutes by the next thing the user says — the lesson is about *when* to ask, not
  about the domain.** During group-reporting's explore phase, the user's grouping input arrived
  across five short messages, and at least three of them invalidated a design just proposed: a
  gaze-wedge/sector model for group boundaries was refuted immediately by the convoy-through-
  ownship case ("I could fly through the middle of it and it would be on both sides of ownship, but
  be single group"); a floor of 3 members was refuted by "a pair of aircraft are a group, in theory
  — lead and wingman"; and a feared pair/couple vocabulary collision turned out to be one
  specificity ladder, not two competing forms. None of these were derivable from the code or from
  more design reasoning — they needed the person who has flown the aircraft. The actionable form of
  this is not "ask more" in general, but: when a design choice is about how a human perceives the
  simulated world (grouping, salience, disclosure), show a concrete proposal early and expect the
  first answer to move it, rather than iterating internally first (`plans/group-reporting/
  explore-notes.md`, 2026-09-28/29).

- **A tuning value chosen to compensate for a known-defective adjacent step is not stable once
  that step is fixed, and retuning it blind (without re-checking against the fixed step) can land
  on the same compensating value for the wrong reason.** The terrain-watershed valley geometry had
  a real defect (zigzag line extraction inflating sinuosity), and the first tuning round picked
  `core_fraction=0.1` specifically because widening it exposed more of that zigzag — the knob was
  compensating for the bug, not expressing the intended tradeoff. Fixing the geometry step first
  dropped sinuosity from 3.57 to 1.17 at that *same* 0.1 value with no retune at all, then a proper
  re-sweep against the fixed geometry found a better point (0.3) the old geometry could never have
  reached without a sinuosity penalty. Lesson: when a parameter's "best" value was set while a
  known adjacent defect was still present, treat that value as provisional and re-sweep after the
  fix lands, rather than inheriting it — a value that happens to look stable across a fix can still
  be compensating for the wrong thing (`plans/terrain-feature-probing/implementation.md`, second
  round, 2026-10-01).

- **A hand-built test fixture that is uniformly asymmetric/monotonic "to avoid tie-breaking
  ambiguity" is a documented design choice that doubles as a blind spot for exactly the bug class
  it was built to avoid.** Every fixture in `test_terrain_features.py` was deliberately constructed
  strictly monotonic specifically so axis-projection tie-breaks never occur — a reasonable choice
  for keeping the tests' expected values easy to hand-derive — but it also meant no test in the
  suite could ever exercise `_axis_sliced_line`'s `round()`-half-to-even tie-break, which collapsed
  a legitimate symmetric 4-cell component to a single point. The Reviewer found it only by
  constructing a new, deliberately symmetric case outside the existing fixture family. Lesson: when
  a fixture docstring says it avoids a class of input "to keep this simple/unambiguous," that is a
  flag to add one separate fixture that does the opposite, not a reason to trust the simple ones
  cover the mechanism (`plans/terrain-feature-probing/review.md`, round 1, 2026-10-01).

- **A plan's stated reason for scoping a dependency can be wrong even when the scoping decision
  itself is still correct — measure before repeating the justification, not just the conclusion.**
  The terrain-watershed plan scoped numpy/scipy to smoothing and extremum detection on the
  reasoning that basin growth and geometry extraction were "not the bottleneck." Measured: the
  numpy-scoped stages are under 5% of the terrain pipeline's runtime; the stdlib basin-growth/
  geometry stages are over 95%. The stated reasoning was backwards from what the measurement
  showed, but the conclusion (don't vectorize the inherently-serial priority-flood) still held for
  an unrelated reason (it doesn't vectorize, and the absolute cost is cheap regardless). A
  plausible-sounding justification that happens to produce the right answer is not evidence the
  reasoning was sound — it is worth measuring even when nobody doubts the conclusion
  (`plans/terrain-feature-probing/performance.md`, 2026-10-01).
- **In speech-rendering code, a test that asserts shape instead of the sentence is not a safety
  net — three wording defects in a row survived a fully green suite this way.** Group cohesion's
  review found `"a armor"`, `"a infantry"`, and `"A ground and a truck."` all shipped as the
  *expected* output of their own tests, because the assertions checked the absence of other
  branches' markers (`"in" not in speech.text`, `not speech.text.startswith("Now leading")`)
  rather than the actual rendered string. If a line is ever spoken to the pilot, its test must
  pin the literal sentence, not a property the sentence happens to have (`plans/
  group-cohesion-redesign/review.md`, both rounds; `plans/group-undermerging/implementation.md`).
- **The user's own worked utterances, not the rules inferred from them, are the specification —
  and checking the rendered output against the utterances directly is what catches defects that
  internal consistency never will.** The group-cohesion plan's first draft inferred a taxonomy
  from the debug pass's framing before utterances existed; once the user gave worked examples
  (`"AAA in the group"`, `"Shilka and zsu"`, `"SRSAM, Shilka, armor 2 o'clock 2.5 km"`), re-deriving
  the design against them directly (not the inferred rules) reversed one branch (leader change:
  full → delta) and found the indefinite-article defect, since every worked example renders class
  nouns bare (`plans/group-cohesion-redesign/plan.md` §4, `explore-notes-delta-taxonomy.md`).
- **A filter that duplicates an existing, cheaper gate can measure near-zero end-to-end saving and
  still be the right thing to ship — the measurement and the decision answer different questions.**
  The 10 km player bubble excludes 76.6% of raw candidates in a real sortie trace, but both
  perception channels already had their own range gate at or below that radius
  (`NAKED_EYE_RANGE_CAP_M` = 10 000 m, `associate()`'s `RANGE_CAP_M` = 5 000 m, stricter), so the
  expensive work those candidates would have reached (terrain-LOS, ~540 us/candidate) was already
  unreachable before this feature existed. Measured end-to-end saving: 0.955 ms/tick, ~1.4%. The
  implementation's own docstrings were already honest that this is a *computation-scope* decision
  ("not measured, deliberately"), not a discovered perf win — Performance Review's job here was to
  put a number on that so nobody later cites "76.6% excluded" as the feature's payoff. The real
  payoff is structural and future: keeping the two constants independent (rather than folding the
  bubble into `NAKED_EYE_RANGE_CAP_M`) is what lets the bubble start mattering once the 9K113
  sight's 20 km cone makes them diverge (`plans/player-bubble/performance.md`, 2026-10-02).
- **When two constants legitimately share a value today but must stay independent, test the
  import/namespace relationship, not the numeric equality.** `PLAYER_BUBBLE_RADIUS_M` and
  `NAKED_EYE_RANGE_CAP_M` are both `10000.0` right now, by coincidence, and are required to diverge
  later (9K113 sight). A value-equality assertion either direction would be meaningless noise; the
  actual guard needed is `dir()`-namespace checks that neither module imports the other's constant
  by name (`test_player_bubble_radius_is_not_imported_from_visibility` and its pair) — this catches
  a direct aliasing import but not a value-derivation form (`CONST = other_module.OTHER_CONST`),
  a residual gap the Reviewer flagged as acceptable to leave open until the 9K113 work actually
  touches either constant (`plans/player-bubble/implementation.md`, `review.md`).
- **When a growth-path fix is found, the obvious wrong move is pruning the store — the right move
  is excluding the stale records from the one expensive consumer.** `ContactStore` accumulated every
  contact ever seen for the whole sortie, and the O(n²) cost was in `GroupStore.reconcile`'s
  clustering, not in holding the records. Deleting `lost` contacts from `_contacts` would have fixed
  the timing at the cost of memory Petrovich should still have (`describe_contact` must still answer
  for a contact that went quiet ten minutes ago); filtering `reconcile`'s *input* to not-`lost`
  fixed the same cost with no memory loss, reusing the existing `belief.decay` lifecycle ladder
  rather than adding a new field (`BL-B23`, `plans/contact-store-pruning/implementation.md`).
- **"The fix works" and "the cost is now bounded" are different claims, and a benchmark that
  confirms the first can be silently read as confirming the second.** `BL-B23`'s fix made clustering
  cost flat across a 55x range in *total contacts ever seen* (403 ms -> 1.4 ms at n=1200) — a real
  fix for the defect it targeted. But clustering's cost is still exactly as quadratic as before
  along the *live-contact-count* axis, by design (the filter changes which contacts are counted, not
  the O(n²) algorithm over however many pass the filter): 20 live -> 0.15 ms, 300 -> 25 ms, 500 ->
  70 ms, all simultaneously fresh. Performance Review caught this by sweeping a second axis the
  implementer's own benchmark never varied, not by finding an error in what was measured
  (`plans/contact-store-pruning/performance.md`).
- **A one-directional module-independence rule forces duplication of small shared checks, and the
  failure mode of that duplication drifting out of sync presents as "the upstream fix didn't work"
  rather than as a visible divergence.** `WM-B1` added a Latin-1-renderability check at OSM ingest
  (`world-model/src/build/ingest_osm.py::_is_latin1_renderable`) that mirrors `body-layer`'s
  existing render-time guard (`belief/enrichment.py::displayable_name`) byte-for-byte. Importing one
  from the other was not an option — `body-layer` may import `world-model` in-process (the one
  sanctioned coupling), never the reverse — so the only choices were duplication with a
  keep-in-sync-by-hand docstring note on both sides, or no ingest-side fix at all. If the two checks
  ever diverge, the symptom will not look like a sync bug: a name that the ingest-side check now
  accepts but the render-time guard still rejects (or vice versa) will read as "the ingest fix
  didn't take effect," sending debugging toward the wrong side. Lesson: wherever a module-boundary
  rule forces a logic duplicate rather than a shared import, name the duplicate's drift failure mode
  explicitly (not just "keep in sync") so a future debugger recognizes it instead of re-diagnosing
  the fix itself (`WM-B1`, `plans/latin-place-names/implementation.md`, `security-review.md`).
- **The risk named in a plan is not necessarily the risk that dominates — profile the whole
  pipeline before optimising the step everyone is worried about.** The geomorphons plan flagged
  Zhang-Suen thinning as "the main technical risk... the thing that resolves full-theatre
  feasibility," on the reasonable-sounding theory that a per-pixel Python loop over a theatre-scale
  raster would be slow. Measured (`cProfile` on a real tile): thinning was 0.5-1.4% of per-tile
  time. The actual dominant cost — 92% of per-tile time, unflagged by anyone until profiled — was
  the Chaikin-smoothing deviation check's O(line_length²) full-polyline scan, invisible from reading
  the plan because nothing in the design discussion mentioned it as expensive. A plan's own risk
  assessment is a hypothesis, not a profiling result, even when the hypothesis sounds obviously
  right (`plans/landform-geomorphons/performance.md`).
- **A render used as evidence a change preserved behaviour is only evidence for the code paths it
  actually exercises — check what it calls, not just that its output looks the same.** The
  performance fix's own report noted that `tools/inspect_terrain.py`'s unchanged, byte-identical
  acceptance render proves classification and tracing are untouched, but that tool never calls
  `_smooth_for_storage` or `ingest_terrain` at all — so it says nothing about whether the Chaikin
  deviation-check rewrite preserved geometry, which is exactly the part that changed. The real
  evidence for that claim was a separate, explicit old-vs-new smoothed-geometry comparison run over
  real traced lines. The implementer caught and disclosed this gap in its own report rather than
  letting the unchanged render imply more than it proved (`plans/landform-geomorphons/
  implementation.md`; independently re-run by Reviewer round 3 on different tiles, zero
  mismatches).
- **On this project, a detector's output is accepted by looking at it, not by its metrics.** The
  geomorphons detector is the third attempt at ridge/valley extraction, after two were rejected on
  sight (a per-cell curvature classifier, then a marker-controlled watershed) despite both having
  internally-consistent metrics and passing review. The user's own description of what changed his
  mind was a side-by-side rendered comparison on one real ridge, not a number: watershed drainage
  broke the crest at every saddle, geomorphons kept it whole. Any future terrain/perception work
  whose correctness is fundamentally a matter of "does this look right to a pilot" should budget
  for a rendered comparison early, before investing in tuning metrics that a correct-looking render
  might make moot (`world-model/ROADMAP.md`'s `WM-B6` entry, decision dated 2026-10-01).
- **A new one-word voice phrase needs a collision check against ordinary speech, not just against
  the existing vocabulary table.** `audio-adapter`'s `command_matcher.VERB_ANCHOR_WORDS` derives an
  anchor word from each phrase's first word, with a deliberately loose fuzzy floor (`VERB_FLOOR =
  0.5`) because false anchors are cheap and false rejections are not. A candidate bare `"quiet"`
  phrase for the `silence` command was clean against every existing command phrase but sat a 0.889
  `difflib.SequenceMatcher` ratio from the ordinary word `"quite"` — enough to anchor
  `"quite a nice day for flying today"` as a command and break a pinned regression test. Found only
  by actually running the matcher with the candidate wired in and testing it against plausible
  near-neighbour English words, not by eyeballing the word or checking it against other commands.
  Multi-word phrasings (`"be quiet"`) are safe by construction, since only a phrase's first word
  becomes an anchor (`plans/silence-command/implementation.md`).
- **`belief.groups`' cohesion gate is measurably tighter than `belief.association_over_time`'s
  contact-founding gate — two observations the founding gate keeps as distinct `Contact`s do not
  automatically cohere into a `Group`.** Found while writing a test meant to reuse an existing
  merge-echo fixture's geometry (500 m apart, bearing 0, ranges 1000/1500 m): `GroupStore.reconcile`
  never clustered them on its own, so the test had to construct the `Group` directly rather than
  relying on natural clustering. Worth knowing before assuming any two contacts close enough to be
  founding-gate-ambiguous will also test group-level behaviour for free
  (`plans/redundant-group-disclosure/implementation.md`).
- **When a suppression mechanism composes with a second, independent suppression mechanism, verify
  the composition is per-member, not per-group (or per-whatever-the-container-is) — a per-group
  check can silently let one suppressed member's "already handled" status silence a sibling that
  was never itself reported.** `_already_reported_member_ids` computes the "already reported" set
  per individual member and the worth-announcing filter is then applied per member, so a group of
  {suppressed, never-reported} members still speaks the never-reported one; full silence only
  occurs when every member independently qualifies. Confirmed by a dedicated composition test, not
  inferred from the two mechanisms each being individually correct
  (`plans/redundant-group-disclosure/security-review.md`).
- **A plan's own design can go stale underneath it when an earlier-stage mechanism it depends on is
  later replaced — re-check the dependency's current shape before resuming a parked later stage,
  not just whether the stage itself was ever built.** `terrain-feature-probing`'s original Stages
  3-5 design assumed basin adjacency "comes free" from Stage 1-2's marker-controlled watershed
  detector; that detector was abandoned for geomorphons before Stages 3-5 were ever built, and
  geomorphons produces traced lines, not basins. Revision 3 replaced the whole adjacency design
  with a query-time divide counter (count ridge-crossings on the straight observer-target segment,
  dedup within 400 m) rather than re-deriving a basin-like structure solely to keep the original
  design's shape. Worth checking for on any plan that sat parked across an earlier stage's own
  redesign (`plans/terrain-feature-probing/plan.md`, Revision 3 preamble).
- **`audioop` is removed outright in Python 3.13 (deprecated since 3.11), and a `requires-python
  = ">=3.11"` bound does not exclude 3.13** — any PCM volume/format manipulation in this repo must
  use stdlib `wave` + `array` instead, never `audioop`, or a 3.13 interpreter fails at import time
  with no fallback. Caught before it shipped only because the main-loop amendment to
  `spu8-intercom`'s plan named the Python version explicitly rather than assuming "stdlib audio
  module" meant `audioop` as it would have on an older interpreter (`plans/spu8-intercom/plan.md`
  Stage 3).
- **Python's `wave.Wave_read.readframes` does not raise when a WAV's declared `nframes` header
  value exceeds the file's actual data — it silently returns however many bytes are really
  present**, which can be an odd byte count for 16-bit PCM. Any code that reads a `wave`-opened
  file's frames and immediately does fixed-width sample arithmetic on the result (e.g.
  `array("h").frombytes(...)`) needs its own guard against that odd-length case; `wave.open`'s own
  header validation does not cover it. This was the exact unguarded path Security found in
  `scale_wav_volume` (`plans/spu8-intercom/security-deep-analysis.md`) — reproduced with a WAV
  whose data chunk was truncated to an odd length while its header's `nframes` stayed stale.
- **A branch handed over from another machine/session with zero gate having run on it is a real
  risk, not a formality** — `spu8-intercom`'s Architect and Implementer both ran cross-machine, and
  the first gate run anywhere on the branch found the implementer had never run the test suite at
  all: a shadowed test helper (reusing a name already bound elsewhere in the test file) was
  breaking 80 pre-existing, unrelated tests. Worth treating "this branch has never had any
  check run on it" as its own flag when picking up cross-machine/cross-session handoff work, rather
  than assuming a clean-looking diff implies the suite was ever green (`plans/spu8-intercom/
  implementation.md`).
- **A constant shared between an outer Hook-script Lua local and a `dostring_in` string-literal
  snippet it dispatches cannot be a single source of truth — the snippet must be a fixed string
  literal (per this project's own `dostring_in` safety rule) and so cannot interpolate an outer
  Lua variable.** `MAX_SIGHTLINES_PER_CALL = 128` exists as two independent literals in
  `petrobrain-line-of-sight-hook.lua` for exactly this reason, with no mechanical guard against them
  drifting apart (unlike the project's own `%d`-count static test for the look-direction splice).
  Worth a similar static test if either copy is ever revisited (`plans/dcs-driven-los/
  implementation.md`, review.md's "Optional Refinements").
- **Gate 4's live-first/offline-fallback join pattern (`candidate.live_los_clear is not None`
  short-circuits the world-model primitive) silently narrows an existing live-acceptance-debt
  entry's scope rather than clearing it** — `fix/los-elevation-tolerance`'s 12 m tolerance stopped
  being consulted for any unit the live DCS feed covers, but the debt entry describing it still read
  as if the tolerance were the only LOS answer. When a new mechanism supersedes part of what an old
  debt item was tracking, the debt entry needs re-reading and re-scoping, not just a new entry
  alongside it (`plans/dcs-driven-los/plan.md`; `world-model/ROADMAP.md`'s "Live acceptance debt").
- **A counterfactual that perturbs a constant the test itself imports fails *open*: it reports the
  property as pinned either way, which is worse than having no counterfactual at all.** The
  bounded-deferral test for the callout observability gate derives its own clock from the constant
  under test (`aged_out = masked_at + CALLOUT_MAX_AGE_S + 1.0`), so raising `CALLOUT_MAX_AGE_S` to
  `1e9` moves the test's entire timeline with it and the deferral still ends just past the budget —
  the recorded counterfactual read "FAIL" and the re-run said PASS. Perturb the **code path**
  (`if now_sim - event.t_sim > CALLOUT_MAX_AGE_S:` → `if False and …`) or a constant the test does
  not read. Deriving thresholds from the constants they exercise is good practice *for the test* and
  a trap for its counterfactual, and several tests in `body-layer` do it. Sharper than the
  pre-fix-revert rule above: there the test didn't discriminate, here the *probe* didn't
  (`plans/callout-observability-gate/{debug.md, implementation.md}` round 3, `304a367`).
- **A gate placed at event emission can be structurally incompletable, not merely under-wired — and
  the difference decides whether "finish wiring it up" is even a valid fix.** The 2026-09-27
  observability gate sat inside `ContactStore.tick`'s per-contact loop and so could only ever reach
  kinds that mint an `Event`. Group disclosure mints none by design (`CalloutScheduler.tick` reads
  `store.groups` as a second candidate source), so no amount of wiring at emission sites could have
  covered it. Before concluding a gate is "correct but under-applied", enumerate the *paths* that
  reach the behaviour, not the call sites of the gate — a path with no event has no emission site to
  gate, and will be invisible to that whole class of search.
- **Moving a gate to discriminate on the *subject* instead of the *kind* is usually the right call
  and it relocates the gate's breadth into a set declared somewhere else, so enumerating its call
  sites can no longer find its real scope.** The observability gate's two call sites in
  `callouts.py` now cover six kinds, because the set that decides membership (`_TEMPLATED_KINDS`) is
  declared ~600 lines away and maintained for an unrelated reason (which kinds `route_event` can
  render). `grep` on the gate showed two; reading `_TEMPLATED_KINDS` showed six, and the third
  newly-covered kind was found by a reviewer rather than by the author. The safe direction is
  automatic (a new kind joins the gate), so what needs a documented admission bar is the
  **exemption** set — an exemption list has the per-kind list's failure shape inverted, and a kind
  joining it leaves the gate silently.
- **Before sizing a push-path reporting defect from a speech log, split the lines by proximity to
  the `acted_token` history — or the count includes pull-path answers and the "fix" targets a
  documented decision.** 20 masked-hour lines in the 2026-10-05 sortie were 17 unprompted callouts
  (the defect) plus 3 answers to a pilot `report` within 4.4 s, which
  `CrewConsole._handle_report` produces deliberately (*"belief survives the aircraft turning away;
  only the absence claim is withheld"*). The wrong figure had already propagated into a roadmap
  milestone and a backlog item before the split was measured. The two paths are
  indistinguishable in the speech log itself; `~/dcs-speech.jsonl`'s command history joined on
  `now_sim` is what separates them (`plans/post-review-fixes/explore-notes.md` §9).
- **An entry in a guard's exception tuple that no test defends is a comment, not a contract — and
  the next tidy-up deletes it for free.** `logger._RESOLVE_FAILURES` enumerates four types; review
  round 5 dropped each in turn and found that removing `OverflowError` **left the whole suite
  green**, while the other three each had a test holding them in place. The argument for keeping it
  was sound (`run_stamp`'s `time.localtime` raises it, and "unreachable from `argv`" is a property of
  today's callers rather than of the code — `when` is a typed keyword a replay tool could feed from a
  JSONL stamp), but an argument is not a guard. Worth applying to any defensive `except (A, B, C)`:
  **drop each entry and see whether anything fails.** Generalises past exception tuples to any
  enumerated defensive set — a validator's allowed-value list, a retry's retryable-error set
  (`plans/bl11-tick-cost/review-round5.md`; commit `f70ff3e`).
- **Two fixes can each pass its own counterfactual while the pair still leaves the seam open,
  because a per-fix counterfactual only ever tests the statement the fix touched.** Round 4 widened
  `resolve`'s guard to `(OSError, ValueError)` and added `expanduser()` — both verified by mutation,
  independently — but put the `expanduser()` call *outside* the `try:` it had just widened, so
  `--detection-trace '~nosuchuser/trace.jsonl'` still killed startup via `RuntimeError`: the same
  defect the round was convened to fix, now also contradicted by the docstring it had just added. The
  fix was structural rather than a third exception type — **one `try:` over every statement in the
  closure**, with a named module-level tuple whose comment enumerates the raising types *per
  statement*, so a fifth call added later lands inside the guard by default instead of sitting above
  it unnoticed (`plans/bl11-tick-cost/review-round4.md`, `review-round5.md`).
- **A benchmark that cannot fail proves nothing, so a performance harness needs its own
  can-this-fail probe asserted before any timing is reported.** Distinct from the already-recorded
  "fix works ≠ cost is bounded" lesson above (`BL-B23`, which measured a real thing along only one
  axis): this is the harness measuring *nothing* while printing plausible numbers. `BL-11`'s
  performance pass gave every harness a probe — mutate the mechanism, assert the measurement moves —
  and one genuinely tripped, on the enrichment-cache counter's first smoke run, which is the only
  reason the instrument was known to be live. Cheap insurance: the probe is usually the mutation the
  review wanted to run anyway (`plans/bl11-tick-cost/performance-review.md`).
- **A diagnostic signature can survive the fix it diagnosed and come to mean the opposite, which
  makes re-running the original diagnostic actively misleading.**
  `distinct_positions == describe_calls == cache_misses` was the equality that identified
  body-layer's enrichment cache as missing by construction. After the fix it **still holds in 37 of
  37 callout-bearing ticks** — but now because each miss is a genuinely new 50 m cell rather than
  because the cache does nothing. The discriminator is the hit count beside it (0 % → 89.7 %), never
  the equality alone. **When a fix lands, check whether the signature that found the bug is still
  true, and if it is, write down what now distinguishes the two cases** — otherwise the next person
  reaches for the trusted diagnostic and concludes the fix failed
  (`plans/bl11-tick-cost/performance-review.md`, finding 3).
- **Wrapping an enumeration call in `pcall` to degrade gracefully is not complete without a paired
  failure counter.** `fix/los-hook-statics` wrapped `coalition.getGroups`/`grp:getUnits()`/
  `unit:isExist()`/`unit:getID()` in `pcall` so a per-side failure yields fewer candidates instead of
  losing the whole poll — correct, but on its own it converts a *loud* failure (previously an
  uncaught error, logged by the caller) into a *silent* one: fewer candidates with nothing saying
  why, which biases exactly the number a later measurement would trust. The fix needed a dedicated
  counter (`unitEnumFailures`, mirroring the already-shipped `staticEnumFailures`) emitted on the
  same log line. Lesson: a `pcall` added for graceful degradation and a counter recording that the
  degradation happened are two different changes — shipping the first without the second looks safe
  and is not (`plans/los-hook-statics/review.md` Required Fix 1).
- **A delimiter-joined wire field is only as safe as the external strings allowed into it.** This
  project's LOS feed joins per-object entries with `;` (`name:building_clear:terrain_clear`); a
  mission-author-chosen DCS object name containing a literal `;` splits into a malformed fragment
  that the Python parser rejects, dropping every verdict in that poll — not just the offending
  object's. The population at risk (free-text names on mission-editor-placed objects) was widened by
  an unrelated change (adding statics) without anyone revisiting the wire format's assumptions about
  what characters a name can contain. Lesson: when a feed widens *which objects* feed a
  delimiter-joined format, re-check what characters the delimiter still assumes are impossible in the
  field's content — the assumption can go from "false in practice" to "one bad mission away" without
  the wire format itself changing at all (`plans/los-hook-statics/security-review.md` Finding 1).
- **A `caplog.at_level(...)` test proves a log call fires; it cannot prove the call is visible
  under the configuration a real run actually has.** The fixture forcibly lowers the effective
  level for its own block, which is exactly what hid a real defect from three review rounds and a
  security deep analysis: `body-layer`'s `logger.py` configured no handler or level anywhere, so
  Python's `logging.lastResort` fallback (threshold `WARNING`) silently dropped every `INFO` call
  on a real run, while every test for those same calls used `caplog.at_level(logging.INFO, ...)`
  and passed. A module with no logging configuration of its own needs at least one test that
  captures the real stream (`capsys`, or a subprocess) with no `caplog` level override at all —
  that is the only way to tell "the call fires" from "the call is visible"
  (`plans/bl11-stage4-fail-closed/dod-check.md`, implementation.md round 4).
- **A fixture can be realistic, assert the right thing, and still be unable to fail — because the
  *value* it picked makes the two outcomes identical.** A third shape alongside the two already
  recorded above (a floor no fixture can breach; a fabricated string that matches by construction):
  BL-13's summary-wording guards all used `OP_ARMORED`/`OP_INFANTRY`, whose plural display word
  *equals* the singular, so `assert "One armor" in text` passed identically whether the code chose
  the singular or the plural table. A real defect — *"One trucks"*, *"One short range SAMs"*, on the
  single-contact scene that is the most common thing a report ever answers — survived three review
  rounds and reached the audio channel's doorstep behind a green guard. The fix was not a new
  assertion but a new fixture *value*: a class whose plural actually inflects, plus a derived
  exhaustiveness test over the display tables so the next `OP_*` class fails a test rather than
  escaping the guard. Lesson: when a test distinguishes two code paths, check that its chosen input
  makes them produce *different* output — a parametrisation whose cases all collapse to one outcome
  is a guard in name only (`plans/crew-query-path/review.md` round 1 required fix).
- **An honesty marker can itself state a false claim, when its wording is fixed and the window it
  describes is wide.** BL-13's freshness hedge had to speak the age of a remembered contact, and the
  user's own phrase for it was *"a couple minutes old"* — said about a ~119 s scene. But the window
  the marker covers runs from the stale threshold (16 s, one scan cycle) to the lost threshold
  (120 s), so the same fixed phrase would have been spoken about a contact seen twenty seconds ago.
  A false freshness claim dressed as an honesty marker is a worse outcome than the unqualified
  sentence it replaced, because it spends the pilot's trust in the mechanism that exists to earn it.
  The resolution was rungs off `round(ago_s / 60)` — *"under a minute"* / *"about a minute"* /
  *"a couple minutes"* — keeping the user's wording for the band he actually spoke it about, and
  adding no staleness constant. Lesson: a qualifier quoted from one observed scene is calibrated to
  that scene; before fixing its wording, brute-force it across the whole range of values it can be
  spoken at and check that every one of them is true (`plans/crew-query-path/implementation.md`
  Discovery 13, round 3 review's age-ladder sweep).
- **A keyword table can be entirely correct and still be the wrong resolver for its caller — the
  defect is the lookup choice, not the table's contents.** Distinct from the namespace-mismatch
  entry above (where the table's own keywords were unreachable): here
  `perception.object_model.profile_for` is right about everything it claims, but it keyword-matches
  DCS *type* designations, and `speech._is_air_defence` was handing it a **believed classification**,
  which at class level carries an `OP_*` lattice string instead. Measured,
  `profile_for("OP_SRSAM")` and `profile_for("OP_LRSAM")` both fell into the default bucket, so four
  of the five air-defence classes were not air defence to that predicate at all — on the push path,
  for the one class the project singles out as the difference between a threat you can fly around
  and one you cannot, and in the state a contact holds *before* identification, i.e. most of the
  time at range. `OP_LRSAM` was silent for months behind a function that read as obviously correct.
  **What hid it was coincidental coverage, not a missing test:** `OP_ZU23` worked by accident,
  because the literal string `"OP_ZU23"` happens to match that table's own `"zu23"` keyword, so any
  test sampling the set's members would have found nothing wrong as long as it sampled that one.
  The fix was to resolve through `classification.parent_class_of` — the lattice walk the pull path
  already used, so push and pull now agree by construction rather than by coincidence — and to
  parametrise the test over `AIR_DEFENSE_OP_CLASSES` *itself* rather than a hand-picked sample.
  Lesson: when a predicate takes a value from one vocabulary and resolves it through a table keyed
  on another, the two being non-interchangeable is invisible at the call site; and when
  parametrising over a set, check whether a *passing* member passes for the right reason, because
  one coincidentally-working member masks the whole set (`BL-B47`,
  `plans/air-defence-class-level/`).
- **An ad-hoc probe that reconstructs a pipeline instead of driving it will skip the production
  gate, and inflate every number it reports.** On `BL-B47` the Reviewer's and the Security
  reviewer's *first* churn probes independently made the same error: both measured callout
  repetition without applying the scheduler's real suppression check
  (`content_signature == belief_group.last_spoken_signature → continue`, `callouts.py:1190`,
  re-checked at `:1221`), and both got counts inflated enough to change the conclusion. Each was
  caught only by re-running through the actual gate. Two independent parties building the same wrong
  instrument is the signal: the error is not carelessness but that a hand-built probe naturally
  contains the steps you are thinking about and omits the ones you are not — and a suppression check
  is exactly what you are not thinking about when measuring how often something fires. Lesson: when
  measuring the rate of a user-visible behaviour, drive the real entry point and assert the probe
  reproduces a known-quiet baseline first (here: steady state is one line then silence for 19
  ticks). A probe that cannot reproduce silence cannot be trusted about noise
  (`plans/air-defence-class-level/security.md` §3, `review.md`).
- **A NaN-safety guard can close the reachable operand and still leave another one in the same
  arithmetic expression open, and reasoning from the docstring's own completeness claim will not
  catch it.** `clamp_fold_displacement`'s first fix guarded `fused.x`/`fused.z` against non-finite
  values; the same `dx * scale` expression the fix patched also depends on `max_displacement_m`,
  a second operand the guard's own author did not re-enumerate before declaring the function
  "NaN-safe on its own terms." Found only because the Reviewer, on the fix's own review round, was
  asked to re-run the enumeration (every operand feeding the arithmetic) rather than to confirm the
  fix worked — "does the guard still claim more than it covers" is a different question from "does
  the test pass," and only the first one finds a second unguarded operand sharing the same line.
  Lesson: a safety-claim docstring invites checking the claim against every operand in the
  expression it protects, not just the one the original finding named
  (`plans/bounded-fold-displacement/review.md`, "NaN-safety fix close-out" round).
- **A hold branch that returns a value by bare identity instead of constructing a fresh object is
  an easy way to silently violate a "bump the timestamp on every poll" invariant**, and this
  project has now been caught by the same shape twice in the same file. `position_belief.py`'s own
  "Hold-recovery timing" invariant (hardened once already, 2026-09-25, after a different hold
  branch's `as_of_sim` bug scaled hold-recovery time as `1 / poll_interval_s`) was violated again by
  a brand-new hold branch (`clamp_fold_displacement`'s NaN guard) returning bare `prior` instead of
  a `PositionEstimate` with `as_of_sim` bumped to the current poll. The sibling function three lines
  above it in the same module gets this right, and the new guard's own docstring explained why it
  could not re-inflate covariance (true) without noticing that reasoning does not extend to
  `as_of_sim`, which needs no growth rate and costs nothing to bump. Lesson: when a module states an
  invariant as a numbered rule in its own header docstring, a *new* code path added to that module
  needs to be checked against that rule explicitly, not just against its nearest sibling's shape —
  shape-matching catches "did I copy the pattern," not "did I satisfy the rule the pattern exists
  to satisfy" (`plans/bounded-fold-displacement/review.md`, `body-layer/src/belief/
  position_belief.py`'s "Hold-recovery timing" docstring section).
- **A retention-hysteresis candidate copied the exact bound *shape* of an existing in-repo
  precedent (`watch-reporting` §4e's 1.5× factor) and failed anyway, because the factor was never
  re-derived against the new defect's own geometry.** Sweeping the factor (0.25× / 0.5× / 1.0× /
  1.5×) fixed the fold tick in every case and lost the member again a few ticks later in every
  case — not a near-miss that calibration would close, a sweep with no good value in it. Only an
  *unbounded* discount held. Measurement is what told the two apart; reading the shapes side by
  side would not have, because the candidate looked like a reasonable generalisation of working
  code. Lesson: a bound shape that works elsewhere transfers its *form*, never its *factor*, and a
  sweep across plausible factors — not a single plausible-looking value — is what actually tells
  you whether the shape itself is wrong (`plans/group-retention-hysteresis/plan.md` §2, superseded
  by `plans/bounded-fold-displacement/plan.md`).
- **When a module's test is meant to pin behaviour that actually lives in a dependency it calls
  unchanged, mutate the dependency, not the module.** `forest.py`'s hole-handling test
  (a clearing inside a forest polygon is not forest) exercises `store.reader.containing_polygons`'s
  own inner-ring logic end to end — `forest.py` itself contains no hole-handling code at all, just
  a pass-through call. Mutating `forest.py` to try to break that test would have nothing to break;
  the test was verified by temporarily mutating `containing_polygons` in world-model instead
  (passing `[]` where it should pass the real inner rings) and confirming the test goes red. The
  general rule: before asserting a test is mutation-verified, check which module actually computes
  the behaviour under test — a thin pass-through has nothing of its own to mutate, and "this test
  passed before and after my mutation" on the wrong file is a false confirmation, not a check
  (`plans/forest-occlusion/implementation.md`, "Notable Discoveries").
- **A numeric assumption repeated in a plan's own cost-reasoning prose can go stale relative to the
  codebase's current constants without anyone noticing, because the plan is internally
  consistent with itself.** `plans/forest-occlusion/plan.md` argued a cache's hit rate from "~25
  polls per miss at 5 Hz" — arithmetically fine on its own terms, and wrong, because this project's
  poll loop has been 1.0 s (not 5 Hz) since `abf49cd`. The number survived architect review and
  into the plan because nothing checked it against the actual constant (`logger.py`'s
  `_DEFAULT_POLL_INTERVAL_S`) rather than against the plan's own arithmetic. Caught by Reviewer, not
  Architect. Lesson: a plan's cost/rate arguments need their inputs checked against the current
  value in code, not just checked for internal consistency — a wrong constant and a consistent
  argument built on it both read as "checked."
