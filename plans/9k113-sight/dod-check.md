# DoD Check: BL-B64 — the 9K113 sight, perception entry

**Scoped to tip sha `f3f87dddc3620c3f3a6a88313e7f2b6dc50da93e`** (branch `feature/9k113-sight`).
This verdict is a statement about that one commit. If the branch has moved since, re-run before
trusting it.

## Address verification

Worktree created at `/Users/sg/Code/DCS-petrobrain-dod-9k113`, checked out directly from
`feature/9k113-sight` (not `origin/HEAD`, which is ~45 commits behind local `main`). `git
rev-parse HEAD` matched the named tip exactly — no merge needed. Did not work in the repo root.
All seven input documents (direction doc §1–§14, `docs/concept/9K113.md`, plan/implementation/
review/security/performance docs, four `BL-B6x` roadmap entries) present and read in full.

`body-layer/.venv` did not exist and was rebuilt with the pinned versions
(`ruff==0.16.6`, `mypy==2.3.1`, `pytest==9.1.1`, `numpy==2.4.6`, `pyproj==3.8.0`).

## Quality Gates (body-layer — the only subproject this branch touches)

Diff against merge-base `08c512f` touches `body-layer/`, `plans/`, and `.claude/agent-memory/`
only — confirmed by `git diff --name-only`, not assumed. No other subproject (`aircraft-layer`,
`world-model`, `audio-adapter`, `brain-layer`, `srs-adapter`) is touched, so none of their
commands are owed.

| Check | Status | Detail |
|---|---|---|
| `ruff format --check body-layer/src body-layer/tests` | ✓ PASS | 129 files already formatted |
| `ruff check body-layer/src body-layer/tests` | ✓ PASS | All checks passed |
| `cd body-layer && .venv/bin/mypy src` (CWD-local, per `body-layer/CLAUDE.md`) | ✓ PASS | Success: no issues found in 59 source files |
| `pytest body-layer/tests -q` | ✓ PASS | **1953 passed, 4 xfailed** — matches Reviewer Pass 6's own count exactly |
| `pytest body-layer/tests/test_tuning_defaults_toml.py -q` (staleness gate) | ✓ PASS | `config/defaults.toml` matches the generator — ran it myself, not inferred |

No unhandled errors/panics introduced: `git diff` of `body-layer/src` grepped for
`except:`/bare `except Exception:`/silent `pass` — zero hits. No debug output
(`print(`/`pdb`/`breakpoint`) or `TODO`/`FIXME`/`XXX` markers introduced — zero hits, checked
against the diff, not the whole tree.

**File size (>400 lines):** many pre-existing `body-layer/src` files already exceed 400 lines
(`crew_console.py` 3518, `optic_policy.py` 1640, `visibility.py` 993, `optics.py` 442,
`association.py` 482, `clustering.py` 430). This is a long-standing, systemic pattern in this
codebase and none of it was introduced by this feature — not treated as a new violation.

**Staging:** `git status --porcelain` is empty at every checkpoint in this review.

## Scope & Correctness

**Matches the plan and the direction document exactly.** Delivered: two sight `Optic` rows
(wide/narrow) with the measured multipliers and sourced FOV/field-of-regard; `BL-B55`'s per-optic
position sigma as this entry's own Stage 1b; the desired/actual aim field split (§15a); the
`SIGHTING` phase with inverted dwell shape (§9/§13); the 1 s hands-busy exclusivity and the
sight's own manoeuvre-rate limit; the OBSERV on/off command surface; the 20 km directional
player-bubble cone *and* the optic-aware range cap (neither alone is sufficient, confirmed by
mutation testing in Review Pass 2); field-of-regard enforcement at both the look-selection point
and in `look_sweep` (Security's required fix, closed in `aac1828`/`ccda29d`); and the
`UNAIDED_OPTIC` 90° FOV change (§14).

**No unplanned scope.** Four review passes, a performance review, and a security deep analysis
each independently confirm the diff matches its own stage's task brief with no silent additions.
Decisions 4/5 (missile word, flight-time callout) and the ASP-17 use case are correctly **not**
present — they belong to `[[BL-B67]]`/were removed entirely by direction §1.

**No invariants violated.** The no-omniscience invariant — the one Security flagged as the
feature's real risk given it roughly doubles Petrovich's perceptual reach (10 km → 20 km) and
adds a directional exemption to the bubble — was found violated once (a sight could be pointed
and admit contacts 25° past its own mechanical field of regard) and the fix is now in place and
independently re-verified (Review Pass 6: both leaks reproduced from source pre-fix, confirmed
closed post-fix, both fixes shown load-bearing by mutation). DCS-is-authoritative, code-owns-truth,
and provenance/timestamp invariants are untouched by this entry (no new external-data mixing).

**All new files staged.** `git status --porcelain` empty throughout.

## Testing

Core logic is tested directly, not just exercised incidentally: the field-of-regard enforcement,
the cone/cap pairing, the `home_phase` divergence fix, the actual-vs-desired aim split, and the
group-ranged-once invariant all have dedicated tests, and four separate review passes
independently mutation-tested the highest-risk claims (removing a guard clause and confirming the
specific test that should fail, does) rather than trusting the implementer's account. Net test
count: 1870 → 1953 passed (+83), 4 xfailed throughout, zero pre-existing tests removed or
modified in substance (only import-line reformatting). No regressions — the full suite passes
clean.

## Documentation

**Reviewer findings addressed.** Pass 2's required fix (OBSERV-off not stopping the sight because
`decide()` never read `home_phase` while `phase is SIGHTING`) — fixed in `1a3c6e8`, confirmed by
Pass 3. Security's required fix (field of regard never enforced) — fixed in `aac1828`+`ccda29d`,
confirmed by Review Pass 6. All optional refinements were judged acceptable as-is by their own
reviewing pass; none are outstanding required work.

**Non-obvious behaviour is explained.** The desired/actual aim split, the `home_phase` inversion,
and the cone/cap pairing are all documented in-code (docstrings) and in the plan/roadmap entries,
not left to be rediscovered. The one stale docstring Security flagged (`regard_*` fields'
"enforcement deferred" comment) was corrected as part of the required fix.

## Security

- `plans/9k113-sight/security.md` — deep analysis, verdict **NEEDS FIXES** (one required fix: the
  field-of-regard leak), both required items resolved and independently re-confirmed by Review
  Pass 6 — per `AGENTS.md`'s change-request procedure, the fix re-entered Implementer → Reviewer,
  not back to Security, and that is the correct path (not a process gap).
- No `security-plan-review.md` exists for this feature, and none is owed: per root `CLAUDE.md`'s
  "Agents" section, Security runs **once per whole feature, immediately before DoD**, not as a
  separate plan-review-then-deep-analysis pair — this project's current cadence since 2026-09-24.
  `plans/9k113-sight/security.md` is that one pass.
- `plans/9k113-sight/performance.md` — once-per-feature performance review, verdict **APPROVED**,
  plus the dedicated `performance-cone-gate.md` bench measurement (4.3 µs/candidate gate chain,
  cone net cost 0.02–0.11% of a 12.6 ms tick) that gated the cone's own design before it was wired.
  Neither needed to re-run after the security fix: the fix adds one `is_worth_a_look`-level
  predicate check and one `regard_optic` parameter to an existing sweep function, both O(1)
  branch-level work of the same shape Performance's own review already characterised and cleared
  (`decide()`'s restructuring added branches, not loop-scaled work) — Reviewer Pass 6 explicitly
  checked this ("Proceeds to DoD — performance and security have both already passed").

## Main-drift check

`main` (tip `45a1a87`) has moved since this branch's fork point — `X-T26` tuning-pattern-as-
standard-practice doc changes and several new `.claude/agent-memory/implementer/…` files.
`git merge-tree <merge-base> main feature/9k113-sight` shows **no conflicts** — every file `main`
touches since the fork point is either untouched by this branch or add-only (new agent-memory
files). Nothing on `main` invalidates an assumption this entry depends on.

## `BL-B55`

Confirmed genuinely closed, not merely touched: `naked_eye_sigma_m`/`look_sigma_m` now takes an
`optic` parameter, threaded at its one call site, with per-optic down-range coefficients
(`SIGHT_WIDE_RANGE_SIGMA_SCALE`/`SIGHT_NARROW_RANGE_SIGMA_SCALE`, both through `tuning.real(...)`
with correct bounds) and a cross-range scale by optic FOV ratio. `UNAIDED_OPTIC`/`BINOCULAR_OPTIC`
reproduce the pre-change formula exactly (pinned by test, verified by Security's own mutation
check via `dict.get(..., 1.0)` default reading). The roadmap entry for `BL-B55` is not yet marked
done — that update belongs to the merge step, together with `BL-B64`'s own.

## The acceptance boundary — what this entry's fixtures structurally cannot reach

Fixtures and mutation tests confirm the code does exactly what it says against the inputs it was
given — including, now, inputs deliberately constructed to diverge (`phase`/`home_phase`
disagreeing, a target 25° past the field of regard). They cannot and do not establish:

- **Whether the sight's detection/classification ranges and the position-sigma scales feel right
  in the air.** `SIGHT_WIDE_RANGE_SIGMA_SCALE`/`SIGHT_NARROW_RANGE_SIGMA_SCALE` (0.5/0.3) and the
  four new dwell/rate-limit constants are explicitly stated, in the plan and in
  `config/defaults.toml` itself, as judgement calls tuned from flying — a fixture can assert they
  render correctly and stay internally ordered; it cannot tell you they are the right numbers.
- **Whether the phase handover (naked eye ↔ binoculars ↔ sight) reads as a crew member choosing
  an instrument, or as thrashing.** This is the Stage 3 question the plan itself names, and it is
  a perceptual/behavioural judgement, not a thing a unit test has an opinion about.
- **Whether the 20 km cone's real-world density matches the trace-derived projection.**
  `performance-cone-gate.md`'s own measurement is explicit that it is a uniform-density
  *projection* from one recorded engagement trace with no ownship heading recorded, not a live
  measurement — narrow would need ~44× the measured p99 density to cost 5% of a tick, and that is
  a bound, not a guarantee, against whatever density a real sortie's own engagement produces.
- **Whether the command surface that actually exists today (see below) is usable in flight at
  all.** No fixture exercises the real DCS process, the real aircraft-layer HTTP seam, or the
  real crew-text REPL under load.

This is the general shape named in the worked example this role's own instructions carry (the F10
vocabulary passing DoD on fixtures, then a sortie finding `Scan` driving the wrong subsystem
entirely): a fixture pass is never a flight pass, and this entry's own highest-risk unknowns are
explicitly the kind no fixture can resolve.

**One acceptance-boundary finding that changes what the card below has to say, found only by
actually running the command surface rather than reading it:** this entry's Stage 2 (OBSERV on/off)
has **no F10 radio-menu item and no voice vocabulary wired for it yet** — both are explicitly Axis
B (`[[BL-B66]]`) work per the plan's own "Affected Modules" list (`audio-adapter/src/vocabulary.py`
for the tokens and synonyms is listed under Axis B, not this entry), and
`aircraft-layer/dcs-export/petrobrain-f10-commands-hook.lua` has no `observ_on`/`observ_off` entry
(grepped directly — zero hits). The only input surface that reaches `CrewConsole.handle_command`
for these two tokens today is the `!voice` developer test harness, typed into the `--crew-text`
REPL's stdin — confirmed by actually running it (`CrewConsole.handle_line("!voice observ_on 1.0
1.0 1 0 observ on", ...)` returns `["Observ on."]` and sets `observ_transition`/the sight phase
correctly; same for `observ_off`). **The acceptance card below says this explicitly** rather than
letting the pilot discover, mid-sortie, that there is no cockpit or spoken way to turn OBSERV on.

## Acceptance card

Published, in-cockpit-readable: https://claude.ai/artifact/A8wMyfaWCmEUto4X7twsnT

Source markdown: `docs/acceptance/2026-10-15-9k113-sight-acceptance-card.md`.

## Verdict

**PASS — clear to merge, with the acceptance sortie outstanding and named as such.**

All mechanical criteria pass. Scope matches the plan. All Reviewer and Security required fixes
are closed and independently re-verified. No regressions. `BL-B55` closes as this entry's own
stage. The one thing this entry cannot clear at the desk is whether it behaves the way the pilot
needs in the air — which is Stage 3's own stated job, not a gap in this gate.

Per root `CLAUDE.md`'s live-acceptance rule: this does not block the merge. Mark `BL-B64`'s
roadmap entry `#status/done #needs-flight` at merge time (together with `BL-B55`'s, which closes
alongside it), not `[ ]` open — the mechanism is built and reviewed; what remains is a flight, not
more engineering.

### Second-order check — does this milestone's completion change what's next?

**Yes, in one way already reflected in the roadmap and worth restating plainly: `[[BL-B66]]`
(effectors) now has a hard dependency on `[[BL-B63]]`'s selective fast lane that its own entry
did not originally carry** — a rate-commanded slew loop cannot close correctly at body-layer's
current 1 Hz poll. `BL-B63.md` and `BL-B66.md` already record this (amended 2026-10-15), so no
roadmap edit is owed here beyond what the implementer/reviewer chain already made. Nothing else
downstream is invalidated: `[[BL-B67]]`'s own entry already reflects the harder-than-expected
target-selection problem from the no-elevation-readout finding (§2).
