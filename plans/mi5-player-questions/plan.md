### Goal

Add MI-5: a deterministic ambiguity detector over `MissionUnderstanding` plus a typed console
loop (mirroring body-layer's `CrewConsole`/`escalation.py` pattern) that surfaces only high-value
questions to the player and writes structured answers back into a new `player_intent` field.

### Context this plan rests on

- Read `plans/mission-interpreter/plan.md`'s MI-5/MI-5b stages (lines 268-287) and
  `docs/concept/MISSION_INTERPRETER.md`'s "Player questions" section — the concept doc's three
  worked examples (route-deviation, reporting-priority, Mi-8-vs-attack priority) all depend on
  schema concepts (`protected_element`, a `task.type` enum, a masking-terrain flag) that **do not
  exist yet** on `MissionUnderstanding` — MI-3 never modeled them, MI-4 doesn't add them. This
  plan's detector is therefore grounded in what MI-3/MI-4 actually produce today
  (`Tagged.epistemic_status == "UNKNOWN"`, `Tagged.confidence == "low"`), not a literal
  reimplementation of the three example questions. See Decision 1.
- `mission-interpreter/src/schema/build.py`'s `_build_ownship` already produces exactly the
  concept doc's "which aircraft is yours?" scenario mechanically: 0 or ≥2 `Player`/`Client`-skill
  units both resolve `ownship` to `Tagged(value=None, epistemic_status="UNKNOWN", basis=(...))`.
  This is the one ambiguity signal that already exists in the codebase before this plan — MI-5's
  detector reuses it rather than inventing a new one.
- `mission-interpreter/src/synth/synthesize.py`/`prompts.py` (MI-4) is the other existing source
  of ambiguity signal: every model-produced `purpose`/`task`/`known_threats` `Tagged` value
  carries a `confidence: "low" | "medium" | "high" | None` (`schema/tags.py`), populated only when
  a model (never a mechanical mapping) produced the value.
- `body-layer/src/belief/crew_console.py` + `escalation.py` is the confirmed pattern to mirror
  (per the task brief and `mission-interpreter/plan.md`'s MI-5 line): typed line-based I/O,
  answers persisted as structured dataclass fields rather than raw chat history, a small ordered
  dispatch table rather than free-text NLU. **This is a pattern to copy, not a shared import** —
  root `CLAUDE.md`'s module-independence rule makes body-layer↔world-model the sole in-process
  exception; mission-interpreter gets its own `player_intent/` package with no import of
  `body-layer`.
- `mission-interpreter/src/schema/understanding.py`'s current `player_intent: Tagged[str] | None
  = None` is an MI-3 placeholder never populated and never consumed (`grep` confirms the only
  other reference is `test_schema_understanding.py`'s `assert understanding.player_intent is
  None`). Nothing downstream depends on its shape, so this plan is free to retype it rather than
  bolt a second field alongside it. See Decision 2.
- No DCS-internals claim is introduced by this plan (no new `.miz`/scripting-API dependency) —
  the investigator step is not needed.

### Affected Modules / Files

- `mission-interpreter/src/schema/understanding.py` — add `PlayerAnswer` dataclass; retype
  `player_intent` from `Tagged[str] | None` to `tuple[Tagged[PlayerAnswer], ...] = field(default=
  ())`, mirroring `known_threats`'s existing per-item-tagged-tuple shape (Decision 2).
- `mission-interpreter/src/player_intent/__init__.py` — new package (new top-level sibling of
  `miz/`, `filter/`, `world_enrich/`, `schema/`, `synth/`).
- `mission-interpreter/src/player_intent/questions.py` — `Question` dataclass
  (`id`, `text`, `kind: Literal["free_text", "bool", "choice"]`, `options: tuple[str, ...] = ()`
  — only populated for `kind="choice"` — see Decision 3, resolved) + `detect_questions
  (understanding: MissionUnderstanding) -> tuple[Question, ...]`, the deterministic detector.
- `mission-interpreter/src/player_intent/console.py` — `PlayerIntentConsole`: takes a
  `MissionUnderstanding` and an input/output stream pair, runs `detect_questions`, asks each in
  turn, parses each typed line into a `PlayerAnswer`, and returns a new `MissionUnderstanding`
  with `player_intent` populated (via `dataclasses.replace`, matching `synth/synthesize.py`'s own
  return-a-new-instance convention rather than mutating the frozen input).
- `mission-interpreter/tests/test_player_intent_questions.py` — detector unit tests: one case
  per rule (ownship UNKNOWN, low-confidence purpose, low-confidence task, low-confidence threat,
  purpose/task still `None`), plus a no-questions case on a fully-resolved, high-confidence
  understanding.
- `mission-interpreter/tests/test_player_intent_console.py` — console loop tests driving
  `PlayerIntentConsole` against an in-memory `io.StringIO` pair (mirrors
  `body-layer/tests`' fixture-only, no-live-dependency convention — no real stdin/stdout needed).
- `mission-interpreter/tests/test_schema_understanding.py` — update the existing
  `player_intent is None` assertion for the new default (`== ()`), add a round-trip test for a
  populated `player_intent` tuple through `dataclasses.asdict()`.
- `mission-interpreter/ROADMAP.md` — mark MI-5 done once implemented (Implementer/DoD's job, not
  this plan's).

### Implementation Plan

1. **Schema change first (minimal working version).** Add `PlayerAnswer` (`question_id: str`,
   `question_text: str`, `question_kind: Literal["free_text", "bool", "choice"]`,
   `parsed: bool | str | int`) to `understanding.py` — `parsed`'s runtime type is determined by
   `question_kind` (a `bool` for `"bool"`, the matched option string for `"choice"`, `str` for
   `"free_text"` including the give-up-after-one-reprompt case per Decision 3). Retype
   `player_intent` to `tuple[Tagged[PlayerAnswer], ...]`. Every populated `Tagged[PlayerAnswer]`
   uses `epistemic_status="FACT"` — the player stating their own intent directly is the most
   ground-truth a value can be in this schema's vocabulary, `basis=("player:console",)`. Update
   the one existing test assertion. Run mypy/pytest before continuing — this is a schema-shape
   change every later stage depends on.

2. **Deterministic detector (validate correctness before any I/O).** `detect_questions` reads
   `understanding` only (no model, no world-model call, pure function — cheapest stage of this
   plan to test, per the task brief's own observation). Rule set (Decision 1 fixes this list;
   `kind`/`options` per Decision 3's resolution — typed answers from the start):
   - `ownship.epistemic_status == "UNKNOWN"` → `kind="choice"`, `options` built from the candidate
     unit ids/names recoverable from `ownship.basis` (if `basis` doesn't already carry enough to
     enumerate real choices, fall back to `kind="free_text"` for this one question only and note
     the gap — don't invent unit data that isn't there), text: "Which aircraft is yours?", `id=
     "ownship"`.
   - `purpose is not None and purpose.confidence == "low"` → `kind="bool"`, text: "Petrovich's
     best guess at the mission purpose is: '{purpose.value}'. Is that right?", `id="purpose"`.
     (A "no" answer just records `False` — MI-5 does not chain a follow-up free-text correction
     question this pass; that's a real, deliberate scope cut, not an oversight — see Risks.)
   - `task is not None and task.confidence == "low"` → same `kind="bool"` shape for `task`,
     `id="task"`.
   - `purpose is None` → `kind="free_text"`, "What is the mission's overall purpose?" (MI-4 either
     didn't run or degraded — see `synthesize.py`'s graceful-degradation note — so nothing else
     can fill this gap and there is no bool to confirm), `id="purpose"`. Mutually exclusive with
     the low-confidence-bool purpose rule above (a `None` field has no `.confidence` to be low).
   - `task is None` → same `kind="free_text"` shape, `id="task"`.
   - one question per `known_threats` item where `confidence == "low"`, `kind="bool"`, `id=
     f"threat_{index}"`, text: "Petrovich isn't sure about this: '{description}'. Is that a
     real threat?" (`True` = real, `False` = disregard).
   No question for `route`/`mission_phases`/`important_locations` — none of MI-3/MI-4's
   population logic ever leaves those at a state this plan's rules can distinguish from "correctly
   empty" (an empty route is `epistemic_status="FACT"` with `basis=("miz: group has no route",)`
   when ownship *is* resolved — a real fact, not an ambiguity).

3. **Console loop (validate the I/O mechanism).** `PlayerIntentConsole.run(understanding) ->
   MissionUnderstanding`: for each `Question` from `detect_questions`, print `question.text` (plus
   `options` inline for `kind="choice"`, e.g. "1) ... 2) ..."), read one line, and parse it per
   `question.kind` (Decision 3, resolved — typed, not free-text-only):
   - `"bool"` — accept `y`/`yes`/`true`/`1` → `True`, `n`/`no`/`false`/`0` → `False`
     (case-insensitive); anything else is a parse failure.
   - `"choice"` — accept a 1-based index into `options`, or an exact case-insensitive match of an
     option's text; anything else is a parse failure.
   - `"free_text"` — accepted verbatim, including blank (no parse failure possible).
   On a parse failure: re-prompt the same question once more (print a short "didn't understand,
   try again" line) rather than silently falling back to storing the raw string — this is the
   real content of "typed answers," not just a label on the `Question`/`PlayerAnswer` shape. If
   the second attempt also fails to parse, record it as `free_text` (the raw line) with the
   question's original `kind` preserved on `Question`, not silently promoted — a consumer reading
   `PlayerAnswer` must be able to tell "this is a real `bool`" from "this is unparsed text left
   over from a failed bool question," so `PlayerAnswer` carries `parsed: bool | str | int` (the
   typed value keyed by `Question.kind`, or the raw string on a give-up) plus `question_id` and
   `question_kind` (copied from the `Question`, not re-derived) — do not just store `str` for
   everything.
   Append a `Tagged[PlayerAnswer]` to a growing list; once every question is asked, return
   `dataclasses.replace(understanding, player_intent=tuple(answers))`. Mirrors `CrewConsole`'s
   shape (typed line in, structured field out) without importing it — this project's own small
   dataclass + function, no shared base class.

4. **Wire an entry point.** Add a `main()` (or extend an existing CLI shim if one already exists
   in this subproject — check before adding a second one) that: loads a `MissionUnderstanding`
   from wherever MI-3/MI-4's pipeline currently writes one (or accepts a JSON path — follow
   whatever MI-4's own live-integration test/CLI entry point already does, don't invent a second
   loading convention), runs `PlayerIntentConsole.run`, and prints/writes the updated
   understanding. This stage is the one most likely to need a small adjustment once the
   Implementer looks at how MI-4's pipeline is actually invoked end-to-end today (no committed
   MI-3→MI-4→MI-5 CLI chain exists yet, per ROADMAP.md) — keep it minimal, a script is enough,
   not a new subcommand framework.

5. **Refine.** Once the detector + console are proven against fixtures, revisit whether the
   `ownship` question's `kind="choice"` fallback-to-`free_text` case (when `basis` doesn't carry
   enumerable candidates) needs `_build_ownship` itself to start recording candidate ids/names —
   deliberately deferred rather than guessed now.

### Risks & Unknowns

- **Concept-doc fidelity gap (see Decision 1).** The three worked examples in
  `docs/concept/MISSION_INTERPRETER.md` are not literally reachable from today's schema. If the
  user expects MI-5 to produce those specific questions, this plan under-delivers relative to the
  doc's own text — flagged explicitly rather than silently narrowed.
- **`bool`/`choice` answers are structured, but the two genuinely open `"free_text"` questions
  (`purpose`/`task` when MI-4 produced nothing at all) still aren't parsed into anything narrower**
  — there's no schema-level way to ask "what is the mission's purpose" as anything but free text.
  MI-6 (runtime compilation) will still need to decide how to consume these two specific
  free-text answers; this plan does not solve that, it only guarantees they're captured with
  enough context (`question_text` alongside the raw `parsed: str`) to be interpretable later,
  possibly by a future model-assisted MI-6 pass. This is a materially smaller residual gap than
  the original free-text-everywhere design would have left MI-6 with.
- **One re-prompt, then give up.** A player who mistypes a `bool`/`choice` answer twice gets it
  recorded as unparsed `free_text` (with `question_kind` still correctly reflecting what was
  actually asked, so a consumer can tell this happened) rather than looping indefinitely.
  Acceptable for an MVP text console per the plan's own framing, but a silent trap if the console
  is later reused unattended (e.g. by MI-5b's automated web-form replacement) without adding a
  real validation UI.
- **Detector coverage is only as good as MI-3/MI-4's current epistemic tagging.** If a future MI-4
  change starts producing `medium`-confidence values for things that are actually highly uncertain
  (calibration, not mechanism), this detector's `"low"`-only threshold will silently under-ask.
  Not a new risk this plan introduces, but inherited from MI-4's "confidence is a placeholder
  axis, not calibrated" caveat.

### Second-order effect

`player_intent`'s new shape (`tuple[Tagged[PlayerAnswer], ...]`) is the schema surface MI-6 will
have to compile into the runtime `player_intent` block `PETROBRAIN_SYSTEM.md`/
`PETROBRAIN_RUNTIME.md` describe (`approach:`, `reporting_priority:` — structured enums). With
Decision 3 resolved to typed answers, `bool`/`choice` answers reach MI-6 already structured
(`PlayerAnswer.parsed` typed by `question_kind`) — MI-6's compaction work narrows to (a) mapping
these typed values into the runtime block's specific field names/enums, and (b) whatever
interpretation the two genuinely free-text questions (`purpose`/`task` when MI-4 produced
nothing at all) still need. Smaller MI-6 scope than the free-text-everywhere version of this plan
would have left behind.

### Decisions Requiring User Input

1. **Detector scope — resolved: schema-grounded, ship now.** User confirmed: ground the detector
   in what MI-3/MI-4 actually produce today (`UNKNOWN`/`low`-confidence signals), not the concept
   doc's three literal worked examples. Those examples' required schema fields (`task.type`,
   `protected_element`, a masking-terrain marker) are new MI-3/MI-4 scope for a future revision,
   not part of this plan.
2. **`player_intent` retype is a breaking schema change to `MissionUnderstanding` — confirmed
   safe.** Nothing else in this codebase is currently in flight against the old `Tagged[str] |
   None` shape (no concurrent branch/work targets it as of this plan).
3. **Answer shape — resolved: typed answers now, not free text.** `Question.kind` is
   `"free_text" | "bool" | "choice"` from the start (see the Implementation Plan's Stage 2/3
   updates above for the concrete parse rules, re-prompt-once-then-give-up behavior, and
   `PlayerAnswer`'s `parsed: bool | str | int` + `question_kind` fields) — avoids retrofitting
   structure once MI-6 needs it.
