PASSED

## Definition of Done: speech word fixes (`[[BL-B129]]`)

**Verdict scoped to:** `feature/speech-word-fixes` tip `5ec461f1` (Security deep analysis commit).
This worktree started at `59192cfa`, confirmed a strict ancestor of `5ec461f1` with a clean tree,
and fast-forwarded cleanly — no `dod-words` branch was needed. If the branch has moved since this
was written, this verdict no longer covers it.

### Acceptance boundary — what this feature's fixtures structurally cannot reach

Every phrase in the acceptance card and in this report was verified **at the text level**: typed
exactly as written, run through the real `rule_patterns`/`command_matcher` pipeline against the
real `flight.lua` rule set (not a hand-built fixture — the actual pattern strings, extracted and
compiled the same way `PUT /rules` does it), and the printed result pasted below. That proves the
matching logic is correct for that text. **It cannot prove that saying the words out loud, through
the headset, through whisper, produces that exact text** — the STT step is the one link in the
chain nothing here exercises, and it is also the step every one of this feature's defects (D1, D3,
D4, D5, D6) was originally found through, not through logic review. A fixture or a unit test
cannot close this gap by construction: it is handed already-correct text. Only a live sortie can.

### Code Quality

**Subprojects touched (from the diff, `main...5ec461f1`):** `audio-adapter`, `body-layer` (plus
`.claude/` agent-memory and `plans/`, neither a tested subproject).

**Full suites run in this worktree** (foreground, `pytest-xdist` via each subproject's own venv —
no venv exists inside this worktree, so each ran with `<repo-root>/<sub>/.venv/bin/python -m
pytest -n auto`, executing the worktree's checked-out code):

- `audio-adapter`: `ruff format --check` — pass (36 files). `ruff check` — pass. `mypy src` — pass
  (17 files). Full `pytest -n auto` (no `-m` filter, i.e. `slow` included): **564 passed, 2
  skipped** — matches `implementation.md`'s own reported full-suite count exactly.
- `body-layer`: `ruff format --check` — pass (224 files; Reviewer's "2 pre-existing unformatted
  files" are clean now). `ruff check` — pass. `mypy src` — pass (91 files). Full `pytest -n auto`:
  **3557 passed, 4 xfailed** (3530 + 27 of Reviewer's fast-set "27 deselected" — consistent: those
  27 are exactly the `slow`-marked tests the fast set skips and the full run includes).
- `tools/check_rules.py` (body-layer, `--adapter-python` pointed at the real audio-adapter venv):
  `ok: 1 rule file(s) checked` — lua syntax, declarations, wording collision check, handler dry
  run, no warnings.

No unhandled errors, panics, debug `print`/console output, or TODO/FIXME comments introduced by
this diff (`git diff ce76714c..5ec461f1` grepped for all four — zero hits).

**Trial merge vs. current `main`:** `git merge-tree --write-tree 5ec461f1 main` — clean, exit 0,
tree `44104c9a36e66f1c3981cf5ad14d884cb83e8aec`, no conflict markers. **`probe/bl16-flight-axes`**
(the dispatch named it `feature/bl16-raw-axes`; no branch by that exact name exists today — the
closest match is this one, confirmed to touch `body-layer/config/rules/flight.lua`) will also need
to merge against `main` later and touches the same file this feature edits. Not resolved here —
reporting only, per the dispatch's instruction.

### Scope & Correctness

Implementation matches `plans/speech-word-fixes/plan.md`'s D1, D3-D6 exactly, plus D2's explicit
non-ship (measured, documented, not silently dropped). No `U<n>` ids in this plan —
`accepted-items-ledger.sh plans/speech-word-fixes` returns nothing, as expected: this plan was
written directly from the user's verbatim words, not through the Architect/`U<n>` convention
(confirmed by both this run and `review.md`'s own note). All six decisions (D1-D6) are accounted
for: built with tests, or explicitly declined with a measured, documented reason. No unplanned
scope. No CLAUDE.md invariant violated — the module-independence rule (`audio-adapter` never
imports `body-layer` or vice versa) and the no-omniscience boundary are both untouched by this
diff (it is pure matcher/rule-grammar/prompt-bias code). All files staged — `git status --porcelain`
was clean immediately after the fast-forward merge, before this role's own additions.

### Testing

Core logic covered: D1 (two tests pinning the prompt-bias-vs-grammar-tolerance distinction), D3
(21 homophone tests plus a filler-conflict integration test plus the deliberately-rejected
fallback's own documentation), D4 (HVRT alias plus three free-speech non-regression pins), D5 (the
guard plus a legitimate-phrase non-regression pin), D6 (the real pattern shape, the double-heading
rejection, the bare-digits-without-verb rejection). Reviewer ran two independent mutation/
counterfactual checks directly against the real code (disabling D5's guard by hand, running
`match_pattern` against the real D6 pattern before/after) — not just reading the tests. No existing
test broken: both full-suite counts above match what Reviewer and Implementer already reported,
and I re-ran them myself rather than taking either on their word.

### Documentation

Reviewer findings: **none required** (`review.md` Verdict: APPROVED, Required Fixes: None). The
two Optional Refinements (state the 141→139 count plainly; keep the self-match blind spot on the
backlog) are both carried into this report and the roadmap entry below, not silently dropped.

**Accepted-items ledger:** empty for this plan (no `U<n>` convention used — see Scope above), so
there is nothing the ledger requires this report to account for beyond what Review/Security already
did.

**Non-obvious behaviour:** D1's two-mechanism distinction (prompt bias vs. grammar tolerance), D3's
rejected fuzzy-fallback danger, D4's global-fold danger, and D6's self-match blind spot are all
explained in code (module docstrings, per implementation.md) and now also in
`notes/voice-recognition-and-command-matching.md` (see Knowledge harvest below) — not left to be
rediscovered.

### Security

`plans/speech-word-fixes/security.md` — **APPROVED**, no required fixes. One low-risk documentation
note (the `heading` slot type's own `consume` no longer requires its own anchor word, so a *future*
rule reusing it bare would accept a stray 3-digit number as a command — not reachable today, since
`flight.lua`'s `turn_heading` is the only rule using it and always pairs it with an anchor literal).
Security deliberately did not file a backlog ID for this, reasoning that it is a one-line
documentation note that would be caught for free by `check_rules.py`'s own collision check the
moment a future rule author reuses the slot. **Listed as a backlog candidate below per the
dispatch's instruction, without minting an ID** — the user's call whether to track it.

### Deviation from the plan's written acceptance criterion — stated plainly

The plan's Acceptance section says the bench's `A_full` row should show "correct count up, WRONG
count not up." The actual result: **WRONG 1→0** (the one targeted defect, fixed) but **ok 141→139**
— down by 2, the literal opposite of "up." Fully traced in both `implementation.md` and the
research note: 3 clips are recordings of the now-retired "alt" phrasing (the direct, intended cost
of D1 — the user said to drop "alt," and these clips say it), 2 are an unrelated prompt-text-length
wash attributable to whisper's own prompt-conditioned decoding, not a defect. Reviewer accepted
this as a reasonable, evidenced judgment call rather than a required fix. I agree with that
judgment on the evidence, but the plan's own acceptance line is not literally met, and the user
should hear that in those terms rather than only "WRONG count went to zero."

### Backlog candidates surfaced (not filed, no IDs minted — the user's call)

1. **`check_rules.py`'s self-match blind spot.** A self-match check built from a rule's own stated
   primitives (a slot type's `sample()` plus the `consume` it is meant to test) cannot catch an
   error shared between them — exactly what let D6's double-"heading" defect ship undetected. Would
   need an independent oracle (the real bench corpus run through the checker) to close generally.
   Noted in `implementation.md`'s Notable Discoveries and `review.md`'s Optional Refinements; now
   also in `notes/voice-recognition-and-command-matching.md`.
2. **Bare `heading`-slot contract note.** Security's low-risk finding above — a one-line comment at
   `SLOT_TYPES["heading"]`/`_consume_heading` or `compile_rules`'s docstring, for whoever writes the
   next rule using this slot type.

### Backlog/roadmap updated

- `body-layer/ROADMAP/BL-B129.md` — marked `[x]` done, `#needs-flight`, with what was built, the
  D6 second-order note for `[[BL-17]]`'s remaining stages, the bench deviation, and the live-
  acceptance card link.
- `body-layer/ROADMAP/body-layer-backlog.md` — index line updated to "done, merged to `main`
  2026-11-18; `#needs-flight`".
- **Milestone Completion question:** does this change what the next milestone should be, or
  invalidate a downstream assumption? Yes, narrowly — `[[BL-17]]`'s own remaining stages (5-9,
  left open per the roadmap) should not trust `check_rules.py`'s self-match step alone for any new
  rule that reuses a slot type the way `heading` was reused; that stage's own plan should budget a
  bench-corpus check, not just the mechanical collision check, before shipping.

### Knowledge harvest

`/notes-harvest speech-word-fixes` surfaced six `implementation.md` Notable Discoveries, none
flagged as a duplicate of existing `notes/` content. Added four to
`notes/voice-recognition-and-command-matching.md` (the existing, clearly-fitting topic file — no
new topic file needed): the self-match blind spot, the digit-homophone-fallback-danger
measurement, the prompt-bias-vs-grammar-tolerance distinction, and the filler-vs-homophone scoping
pattern. Skipped the D4 global-fold danger and the "four test files the plan didn't name" discovery
— the former is already captured as `.claude/agent-memory/implementer/
feedback_audio_adapter_global_normalize_fold_danger.md` (a different store, role-specific lesson,
not duplicated here since notes/ serves a different reader) and the latter is process narration,
not a reusable insight.

**Recurring-fix check:** `review.md`'s Required Fixes is empty, so there is no required-fix
category to search against prior memory — nothing to report as a process signal here.

### Full test/check output, condensed

```
audio-adapter: ruff format --check pass, ruff check pass, mypy src pass (17 files)
audio-adapter: pytest -n auto (full, no -m filter): 564 passed, 2 skipped
body-layer:    ruff format --check pass, ruff check pass, mypy src pass (91 files)
body-layer:    pytest -n auto (full, no -m filter): 3557 passed, 4 xfailed
body-layer:    tools/check_rules.py --adapter-python <audio-adapter venv>: ok: 1 rule file(s) checked
merge-tree:    5ec461f1 vs main -> clean (tree 44104c9a36e66f1c3981cf5ad14d884cb83e8aec)
```

### Live acceptance — PENDING (live)

Card: https://claude.ai/artifact/PqQ7et63fDCyxYR2MU9gsp (source:
`docs/acceptance/2026-11-18-speech-word-fixes.md`/`-card.html`). Fly on `main` after merge.
`#needs-flight` set on `body-layer/ROADMAP/BL-B129.md`. Not a merge blocker — testing debt accepted
in batches per 2026-10-26/2026-11-15 user direction.
