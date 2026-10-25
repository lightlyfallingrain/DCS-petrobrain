### DoD Check: BL-B102 — "that"/"it" referent resolution

**Scoped to tip `2a9f2de51767c225cc3e2c18724f9ecb1e5fa0d1`** (branch `feature/that-it-referent`).
Fast-forwarded cleanly into this DoD worktree's HEAD (`21b95c83` was a strict ancestor, tree
clean). This verdict is a statement about that one commit; if the branch moves, re-run.

### Code Quality

- [x] **body-layer**: `ruff format --check src tests` — 178 files already formatted.
      `ruff check src tests` — all checks passed. `cd body-layer && mypy src` (strict) — success,
      no issues, 77 source files. `pytest tests -q` — **2686 passed, 4 xfailed** (matches the
      Reviewer's and Implementer's own reported numbers exactly).
- [x] **audio-adapter**: `ruff format --check src tests` — 31 files already formatted.
      `ruff check src tests` — all checks passed. `cd audio-adapter && mypy src` (strict) —
      success, no issues, 16 source files. `pytest tests -q` — **390 passed, 2 skipped** (matches).
      Both touched subprojects (determined from the diff: `body-layer/`, `audio-adapter/`) got
      their own commands run — no third subproject touched.
  - A fresh worktree has no `.venv` (gitignored, not shared) — ran each subproject's real `.venv`
    binaries by absolute path from the main checkout
    (`/Users/sg/Code/DCS-petrobrain/<subproject>/.venv/bin/<tool>`) with cwd inside this
    worktree's own subproject directory, per the implementer's own noted deviation and this
    project's mypy CWD-only config-discovery rule.
- [x] No unhandled errors/panics in data paths — `resolve_referent`'s failure path returns
      `render_unable("NO_REFERENT")`, never raises; `_report_scope(restrict_to_ids=...)` reuses
      existing, already-reviewed filter code.
- [x] No debug output left — grepped `print(`/`TODO`/`FIXME`/`XXX` across every touched file
      (`referent.py`, `vocabulary.py`, `command_matcher.py`, `crew_console.py`, `speech.py`,
      `callouts.py`, `body.py`): none found.
- [x] No leftover debug/TODO code introduced by this feature.

### Scope & Correctness

- [x] Implementation matches `plans/that-it-referent/plan.md` — confirmed against Reviewer's full
      read (APPROVED, no required fixes) and spot-checked independently: `REFERENT_WINDOW_S`
      declared via `tuning.real` as planned, six referent-bearing tokens wired
      (`where_is_it`/`mark_target`/`follow`/`select_target`/`engage`/`watch` family), `NO_REFERENT`
      wording **left unchanged** per this dispatch's explicit instruction (not touched — verified:
      `speech.py:492` still reads `"Unable, I don't know what you mean."`).
- [x] No unplanned scope added — Reviewer's own scope-drift check (confined to the referent
      mechanism and the six named tokens, per the ROADMAP entry's "do not build new commands"
      note) re-confirmed by reading the diff stat: only `referent.py` (new),
      `crew_console.py`/`callouts.py`/`speech.py`/`body.py` (body-layer) and
      `vocabulary.py`/`command_matcher.py` (audio-adapter) carry behavioural changes.
- [x] No CLAUDE.md invariants violated — no omniscience leak (resolution reads only `Percept`-
      derived belief via `describe_contact`/`_report_scope`, never a DCS object id or ground
      truth); world-model/body-layer-only in-process import unchanged; no new cross-subproject
      import; `belief/referent.py` is a pure query module (actions/params shaping, not an action).
- [x] All new files staged — confirmed via `git status --porcelain` (clean) after the
      fast-forward; `referent.py`/`test_referent.py`/`BL-B102.md`/all plan docs were already
      committed on the feature branch.

### Testing

- [x] Core logic covered: `test_referent.py` (window pruning, bare-last, qualified-filter,
      target-priority, nearest-wins, group→lead-member reduction incl. the `None`-fallback,
      expired/empty→unable) plus `test_crew_console.py`'s 13 end-to-end tests and
      `test_command_matcher.py`'s 16-test `TestReferentSlots` class. Tests are meaningful — they
      assert specific resolved contact ids / rendered text, not just "doesn't crash" (confirmed
      by reading representative tests, not just the Reviewer's say-so).
- [x] No existing tests broken — net +12 body-layer / +19 audio-adapter test functions, zero
      regressions in either full suite.

### Documentation

- [x] Reviewer's required fixes: **none** — nothing to address. Three optional refinements noted
      (end-to-end lost-contact tests for the other four handlers; the undocumented
      `descriptor=="group"`+another-qualifier limitation; `NO_REFERENT`'s wording) — all
      correctly left as-is; the wording question is the one open user decision carried forward
      below, not resolved here.
- [x] Non-obvious behaviour explained: `plans/that-it-referent/{explore-notes,plan,implementation}.md`
      cover the design and deviations in full; module docstrings cited by the Reviewer
      (`_report_scope`, `group_membership_state`, `_mark_watched_with_group`) carry the rest.

### Security

- [x] `plans/that-it-referent/security-plan-review.md` — **APPROVED**.
- [x] `plans/that-it-referent/security-review.md` — **APPROVED**, no required fixes. (Performance
      review, run per this project's once-per-batch cadence since this was a single-stage-batch
      feature, also **APPROVED**, no action needed.)

### Acceptance boundary — what these fixtures structurally cannot reach

All of the above is fixture/unit-test verification. It cannot show:

- **Whether 60 s (`REFERENT_WINDOW_S`) feels right in the cockpit.** No live-sortie data exists;
  the plan and both reviews say so explicitly. A real flight may show it too short (pilot pauses,
  then says "where is it") or too long (a stale referent resurfaces unexpectedly after other
  chatter).
- **Whether "nearest wins, never ask" reads as correct or as silently wrong to the pilot**, for
  the ambiguous-bare-referent case. This is a deliberate reuse of an existing convention, not
  something a fixture can judge — only a pilot hearing it respond to a genuinely ambiguous "where
  is it?" can.
- **Whether the six worked examples in the ROADMAP entry, spoken and heard through real STT/TTS,
  actually resolve correctly end to end** — unit tests exercise `match_transcript` and
  `resolve_referent` directly with known-good transcripts; they do not exercise a real microphone,
  real whisper.cpp recognition noise, or real PTT timing. A mis-recognized "it" vs. "at" is exactly
  the class of defect no fixture here can produce.
- **The group+qualifier limitation** ("follow that 2 o'clock group" ignoring the clock) is known
  and undocumented-to-the-pilot — only a live sortie would reveal whether this is ever actually
  said in practice.

### Live acceptance — owed, not blocking

**Not merged.** Per this dispatch's instruction, this branch is fast-forwarded into the DoD
worktree for verification only — it has not been merged to `main`, and this report does not claim
it has been. Live acceptance (a DCS flight) is owed and is recorded on the ROADMAP entry itself
with `#needs-flight`, not held as a separate list, per this project's convention
(`docs/TAGS.md`).

**What to fly**, directly from the user's own worked examples (`body-layer/ROADMAP/BL-B102.md`):

1. Get Petrovich to call out a contact ("AAA, 2 o'clock, far"), then ask "Where is it?" — expect
   the positional answer about that AAA, not the attack target (unless it is the same).
2. During an active attack run on a different contact, ask "Where is it?" — expect it to still
   mean the target unless something else was mentioned more recently (Decision 1).
3. Get two groups called out ("Group 11 o'clock, armor and trucks. Group 2 o'clock, armor, moving
   east" via "Describe"), then say "Follow that moving group" — expect the 2 o'clock group, not
   11 o'clock.
4. Immediately after, say "Engage that 11 o'clock armor, missiles" — expect it to re-resolve to
   the 11 o'clock group's lead member, not stay on the moving group from the previous command.
5. Say "Target it"/"Mark it"/"Watch it" forms against a just-mentioned single contact.
6. Let ~90 s pass after a mention with nothing else said, then say "Target that" — expect
   "Unable, I don't know what you mean." (not a stale resolve).
7. Have Petrovich mention a contact that then goes `lost` (out of sight) within the window, then
   ask "Where is it?" — expect the believed positional answer, not "unable" (Decision 4).

### Open user decision — not resolved here, per instruction

`NO_REFERENT`'s wording — "Unable, I don't know what you mean." (current) vs. a terser
"Unable, no contact." (Reviewer's proposed alternative, matching the project's other
`_UNABLE_TEMPLATES` entries' style). Left unchanged in this pass; a one-line, reversible edit if
it reads oddly once flown.

### Milestone completion question

Does this change what's next, or invalidate a downstream assumption? **No invalidation; one
addition.** `belief/referent.py`'s `Mention`/`ReferentMemory` is now the one place "what was
Petrovich just talking about" lives, which the plan's own "Second-order effect" section notes as
the state param a later BL-10/SRS conversational-memory feature should read rather than reinvent
— narrows, not complicates, that later work. Nothing else downstream depends on this milestone's
specifics changing.

### Verdict

**DoD: PASSED** (mechanical checks). **Acceptance testing: OWED** (`#needs-flight`, not merged —
cannot run without the user and a live DCS session).
