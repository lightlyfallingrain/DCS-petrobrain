# Definition of Done — BL-13, the crew query path (Stages 1–3)

**Verdict: PASS**, scoped to one commit.

**This verdict is a statement about `3b1d1df3389b14f86a09778c4cfe490d00d008a5`** on
`feature/bl13-crew-query-path`, not about the branch. If the branch moves, the verdict is stale and
must not be carried forward across a behavioural change — that happened once on
`fix/callout-observability-gate`, where a later commit narrowed the behaviour a passed DoD report
and acceptance card had already described.

Worktree HEAD was `e2e2164` (stale, as assumed for any dispatch whose target is not `origin/main`),
a strict ancestor with a clean tree, so `git merge --ff-only 3b1d1df` was run and HEAD now equals
the named tip. All seven input documents confirmed present before reading. Feature history
`e2e2164..3b1d1df`, eleven commits.

---

## 1. Code quality

Both touched subprojects were derived from `git diff --name-only e2e2164..3b1d1df`, not from
memory: **`audio-adapter`** and **`body-layer`**. No other subproject is in the diff.

Each gate was **run here**, with the root checkout's venv binaries (`.venv` is gitignored and so
absent from the worktree) and cwd inside each subproject inside the worktree, so `mypy`'s CWD-only
config discovery and `pytest`'s `pythonpath` resolved against the reviewed tree.

| check | audio-adapter | body-layer |
|---|---|---|
| `ruff format --check src tests` | PASS — 29 files already formatted | PASS — 118 files already formatted |
| `ruff check .` | PASS — All checks passed! | PASS — All checks passed! |
| `mypy src` | PASS — no issues, 15 source files | PASS — no issues, 54 source files |
| `pytest` | PASS — **255 passed, 1 skipped** | PASS — **1611 passed, 4 xfailed** |

Both match the expected figures exactly. `ruff format .` with the dot was deliberately avoided (it
rewrites Python blocks inside Markdown and touches an unrelated research note).

- **No debug output, no leftover debug code.** `git diff e2e2164..3b1d1df -- '*.py'` contains zero
  added lines matching `print(`, `breakpoint(`, `pdb`, `TODO`, `FIXME` or `XXX`.
- **No unhandled errors in data paths.** The seam validates twice — `logger.py:1499-1505` rejects a
  `slots` payload that is not a dict of `int | str` before dispatch, and `_handle_slotted_report`
  then validates each value against the table that owns it and **drops** an unrecognised one,
  widening the answer rather than raising mid-query. The crew-text poll cycle wraps dispatch in
  `except Exception` + `logger.exception` and continues.
- **No new constant beyond the two the plan permits**: `_REPORT_BAND_BOUNDS_M`'s 2 000/5 000 and
  `REPORT_SUMMARY_MAX_WORDS = 25`. Everything else added at module level is a word table or a
  comprehension derived from one. `decay.py` is absent from the diff; `CALLOUT_GROUP_CLOCK_SPAN_HOURS`
  and `perception.gaze`'s wedge table are reused rather than duplicated.

## 2. Scope, correctness and invariants

- **Implementation matches the plan**, including five places where it deliberately diverged. Each
  is recorded in `implementation.md`, was judged by the Reviewer as a decision, and I re-checked
  the two that change shipped behaviour by running the matcher on both the base commit and the tip:

  | divergence | verdict |
  |---|---|
  | `PHRASES["report"]` carries five slotted bias phrasings, not the bare verb | **Correct.** `report_all` owns `"report"`/`"describe"` and `normalized_phrase_index` raises on a collision, so the plan's literal reading would not import. Bare `"report"` still falls through to `report_all` — measured: `report`, `describe`, `report contacts` all → `report_all`. |
  | `report east` / `report three o'clock` now resolve to the slotted token | **Correct and unavoidable.** The slot branch in front of the phrase table is what makes `report left` work at all. Measured on the tip: `report east` → `{'sector': 'east'}`, `report three o'clock` → `{'clock': 3}`. Legacy tokens remain reachable from `TOKENS`, the bench corpus, body-layer dispatch, `brain_reply.py` and `voice_commands.py`. |
  | six body-layer tests rewritten | **Correct, and does not cross `AGENTS.md`'s escalation line.** The rule covers tests that *must be rewritten rather than extended*; Decision C changed the output contract by the user's own choice, so no extension could preserve the old expectations. Each rewrite keeps the property the original existed for. |
  | the freshness marker names its own subject | **Correct.** The air-defence clause names every tier in scope *including fresh ones*, so an apposition would hedge a contact seen a second ago; and the clause is suppressed entirely when air defence is the dominant class, leaving nothing to hang an apposition on. |
  | `_summary_op_class` uses `parent_class_of`, not `object_model.profile_for` | **Correct, and load-bearing.** Re-measured here: `parent_class_of("OP_SRSAM")` → `"OP_SRSAM"` while `profile_for("OP_SRSAM").op_class` → `"OP_GROUPSOMETHING"`. A marker built on `_is_air_defence` would have been silently dead in the one scene it exists for (`BL-B47`). |

- **No unplanned scope.** Stage 4 (the `last_gazed_sim` ledger) and Stage 5 (landmark `where`) are
  absent and deliberately so. `belief/groups.py`, `decay.py`, `callouts.py`, `contacts.py`,
  `tools.py` and world-model are untouched.
- **Invariants hold.**
  - *Code owns truth; no omniscience.* The pull path reads belief only (`get_contacts`), drops
    `certainty == "lost"`, and adds no path from ground truth into speech.
  - *`contacts._callout_may_speak` is correctly NOT applied to the pull path* — re-verified by grep
    here, not read from a report: it appears in `contacts.py` (definition, one push-path call, one
    docstring) and once in `crew_console.py:1856` as the comment explaining the exclusion.
  - *Module independence.* No new cross-subproject import. The token crosses as
    `{token: "report", slots: {...}}` over the existing HTTP/JSON channel. The cost — a third
    hand-synced mirror pair across the seam — is tested literally on both sides.
  - *`world-model/data/` not committed*; no gitignored path, build artifact or `.sqlite` in the diff.
- **Agent-memory files are at the repo-root-relative path** (`.claude/agent-memory/<role>/`), not a
  subproject copy.

## 3. Testing

255 audio-adapter and 1611 body-layer tests. The tests are meaningful rather than decorative, and
the strongest evidence for that is in the review record: across three rounds the Reviewer defended
individual assertions by **mutation** — forcing `_unit_word` to `"units"` (3 failed), forcing the
fold back to plural (6 failed), gating the freshness append behind `with_deferral` (5 failed),
dropping the `AIR_DEFENSE_OP_CLASSES` membership test (3 failed), dropping one entry from
`_SINGULAR_FOLD_OPENINGS` (1 failed), and adding a fake display class (1 failed). No existing test
was weakened or deleted; round 3's diff is 612 insertions and **zero deletions anywhere**.

One thing worth keeping out of the "all green" reading: a real defect — *"One trucks"* — survived
three rounds because every existing fold test used `OP_ARMORED`/`OP_INFANTRY`, whose plural display
word *equals* the singular, so the guard asserted `"One armor"` and passed incidentally. The fix
added the inflecting-class cases and a derived exhaustiveness test, so the next `OP_*` class fails a
test rather than reaching the audio channel.

## 4. Documentation and review

- `review.md` — three rounds, all findings addressed; rounds 2 and 3 **APPROVED** with no required
  fixes. Reviewer confidence is **full read** in all three rounds, each stating that both gates were
  re-run rather than trusted.
- `security.md` — one required fix (the all-or-nothing freshness qualifier), **closed** by
  `153efc0` and verified by round 3 reproducing the finding through mutation rather than reading the
  fix.
- `performance.md` — **APPROVED — MONITOR**, no required fixes. Its one escalation is filed (below).
- `plan.md` Decision D carries a dated note recording the user's freshness decision in his own
  words, and says plainly that some stale belief is now spoken as present tense *as an accepted
  trade* — which is what lets a later reader tell a decision from a defect.
- Roadmap updated: `body-layer/ROADMAP/BL-13.md` (the entry file, **not** the four-line pointer
  `body-layer/ROADMAP.md`) and root `ROADMAP.md`'s Body Layer row.

## 5. Security sign-off

- `security-plan-review.md` is **absent, and that is expected** under the cadence root `CLAUDE.md`
  sets: `security` and `performance-reviewer` run **once per whole feature, immediately before DoD**
  (2026-09-24, user direction). A missing plan review is the current cadence, not a gap.
- `security.md` exists; its single required fix is resolved, re-reviewed and APPROVED.

## 6. Staging

`git status --porcelain` empty at the start of this pass and again after every probe. Everything
this pass wrote is committed in the worktree (sha in the handback).

---

## The acceptance boundary — what this feature's fixtures structurally cannot reach

**A fixture pass here is not a flight pass, and the gap is not "more testing".**

What 1 866 tests and the measurements in this pass *do* establish: the matcher resolves the five
slots under either verb; the slot branch sits where it is claimed to sit; the five filters narrow
the in-scope set; the summary renders the strings it renders, in the word counts it claims, with
singular agreement across every display class whose plural inflects; both seams validate; and the
freshness marker fires in the scene the security finding measured and survives both budget drops.

What they **cannot** establish, by construction:

1. **Whether a summary beats the enumeration it replaced.** This is the whole milestone, and it is
   a judgement about hearing one sentence instead of four while flying. A test can assert the
   string; nothing here can assert that it aims the pilot's eyes. He chose it from two mocks on the
   ground; this is the first time the real system says it.
2. **Whether 25 words (~10 s) is too long in a hover.** Calibrated from a mock read on the ground.
   No fixture has a hover in it.
3. **Whether the freshness marker reads naturally over an intercom**, and at the right times. The
   accepted trade — a stale truck speaks as present tense — is only judgeable by the person who
   accepted it, hearing it.
4. **Whether the spoken forms are recognised at all in a loud cockpit.** The band words are
   unbenched on this user's voice, and `close` is phonetically near `clock`, which the clock slot
   also consumes. Every measurement in this pass went through `match_transcript` on *text*; nothing
   went through a microphone.
5. **The two defect classes the 2026-09-16 F10 vocabulary sortie found the day after it passed
   DoD**, both of which this feature could reproduce in kind: code that does exactly what it says
   *against the wrong subsystem* (no fixture can detect it), and wording that is only wrong when a
   human *hears* it (correct as text in a log). The freshness marker and the summary are both
   squarely in the second category.

**This does not gate the merge.** Live verification happens in bursts and depends on the Windows
box; the milestone is recorded `#needs-flight` on its own entry file rather than held open. The
debt is **deferred, not waived** — the plan does not scope live testing out, it is simply pending
the next sortie, and it should name the sortie that clears it.

**Batching:** one sortie clears all of it, and `BL-11`'s outstanding log-visibility check as well,
since both need the same session on the same box. Card:
`docs/acceptance/2026-10-10-crew-query-path-sortie.md`.

---

## Findings this pass added, not present in any review document

All three were measured here by running the shipped matcher, on both the base commit and the tip.
None is a DoD failure: each is pre-existing or an honest degradation, and the plan explicitly
reuses `parse_descriptor` unchanged.

1. **The *what* slot accepts exactly seven singular words, and the user's own vocabulary is not
   among them.** `DESCRIPTOR_WORDS` is `armor, truck, infantry, sam, aaa, ship, group`. Measured on
   the tip: `report trucks near` → `{'band': 'near'}`, `report tanks near` → `{'band': 'near'}`,
   `report armour north` → `{'sector': 'north'}`, `report air defence near` → `{'band': 'near'}` —
   the *what* is silently dropped in every case. The degradation is honest (a wider answer, never a
   wrong one), but the user's own grammar request used *"trucks"* and *"air defence"*
   (`explore-notes.md` §7), so the gap is in the vocabulary rather than in his phrasing. **Worth a
   backlog item**; deliberately **not minted here** — see the ID note below.
2. **`Petrovich, report left` loses the slots.** Measured: `token='report'`, `slots=None`, so a
   wake-word-prefixed command answers about the whole scene instead of the left wedge. Pre-existing
   routing (the wake word sends a transmission to the brain as free speech), but it is the first
   feature where the lost part is a *filter* rather than the whole command, so it is now worth
   saying out loud in the card.
3. **`report six o'clock` resolves to `report_clock_8`** — on the base commit *and* on the tip. The
   forward clock slot covers 1–4 and 8–12, so hours 5/6/7 fall through to the phrase table and
   fuzzy-match a neighbour. This is the same silent-wrong-direction shape `BL-B28` was, for the rear
   hours, and unchanged by this branch. Named in the card so the pilot can confirm he hears it
   before it is filed.

Also corrected: the roadmap entry and the plan both said a spoken `"report south of Gemerek"`
degrades to a *bare* report. Measured, it keeps `{'sector': 'south'}` — the better of the two
degradations, and now stated accurately in the card.

### Why no new backlog ID was minted from this branch

`BL-B47`, `BL-B48` and `BL-B49` exist on **`chore/file-bl13-review-findings`**, not on this branch
(this branch's directory maxes at `BL-B46`). Minting here would read `BL-B46` as the latest and
collide on `BL-B47`, which is exactly what the never-reuse rule exists to prevent. Finding 1 above
should be filed as `BL-B50` **after** that chore branch merges.

**Merge-ordering note, and it is load-bearing:** `chore/file-bl13-review-findings` holds all three
escalations from this feature's own reviews. If BL-13 merges without it, the trunk has the feature
and none of its filed consequences.

---

## Inspect-and-adapt (root `CLAUDE.md`, "Milestone Completion")

**`BL-12` should still be next, and its plan needs re-reading before it starts** — not rewriting.
Nothing BL-13 built changes BL-12's goal; two things change its premises. (1) `BL-B48`'s measured
`EAGER` infantry cohesion bridge — an infantry contact merging non-infantry contacts across 6 km —
is a premise BL-12 would otherwise inherit silently, so its redesign has to either dissolve it or
keep it as a stated decision. (2) BL-13's summary is immune to that defect by construction
(it aggregates the filtered set and never walks a group roster) while the push path's
`render_group_full_disclosure` is not, so the value of fixing group identity is now concentrated on
the push path — which should sharpen BL-12's scope rather than widen it. Separately, BL-13's slot
schema, not a new one, is what the brain layer should target when free speech arrives.

## Process signal — recurring patterns, from `.claude/agent-memory/dod/`

Two categories recurred here that memory already records, and both argue for a check earlier in the
sequence than Reviewer:

- **A guard fixture landing on a degenerate case.** `"One armor"` — where the singular and plural
  display words are identical — let a real defect pass incidentally for three rounds. Same shape as
  the already-recorded *"a benchmark must be able to fail"* discipline: a fixture that cannot
  distinguish the two outcomes is not a guard. This belongs at **Implementer**, as a habit of
  choosing the fixture value that can fail.
- **Correct conclusion, unearned reason.** Three separate comments in this feature stated a
  mechanism that does not exist (`belief.attention`'s re-export), a consumer that does not contain
  the thing (`LEGACY_F10_TOKENS`), or a state that is reachable while claiming it is not (the
  `"mostly"` hedge) — each defending a decision that was nonetheless right. This is the fifth-plus
  instance of the pattern recorded in this role's memory. **Read a comment's reason as its own
  claim**, usually one grep from falsification; it belongs at Reviewer and is being caught there,
  but the cheaper place is the Implementer writing it.
