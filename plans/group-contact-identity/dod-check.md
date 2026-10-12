# Definition of Done — BL-12, Group-level contact identity and continuity

**Scoped to `feature/bl12-group-contact-identity` tip `a2b761c4b47a3a9c1e6ac76fae166068cd0c957e`.**
This verdict describes that commit. If the branch moves after this report, re-run before merging.

## Acceptance boundary, stated up front

**What these fixtures structurally cannot reach**: everything here is synthetic scenes and replayed
sortie logs. A fixture can prove the mechanism (group matching, the ambiguity inversion, the
admission gate, the speech line) does what the plan says against the geometry it was given. It
cannot prove:

- that the rarity claim D5's error preference rests on ("mistaking a new group for an existing one
  is the unusual occurrence") actually holds at real DCS unit density across a real sortie — the
  `--group-trace` log exists for exactly this reason, and has not been read from a real flight yet;
- that the spoken line ("that column, now 2 o'clock, three kilometres, still moving north") reads
  right over an intercom rather than merely rendering right in a test assertion;
- that the Stage 3.5 admission gate's "repeat-incident accumulation" and "air-defence interaction"
  sub-questions (left open in the Stage 3 review, re-confirmed open in the Stage 3.5 round) don't
  surface on a real sortie's actual geometry;
- that `BL-B59`'s eviction defect — confirmed live against the real pipeline by probe, not a
  fixture artifact — doesn't suppress a real air-defence report on a real flight before it is fixed.

None of this is a defect in what was reviewed; it is the standing limit of fixture-based
verification, named so a fixture PASS is not mistaken for a flight PASS.

## Mechanical checks (body-layer, run directly in this worktree)

| check | result |
|---|---|
| `ruff format --check` | 1 file flagged — `research/2026-10-05-security-audit.md`, pre-existing, judged by the 2026-10-05 audit, not this milestone's diff. 266/267 already formatted. |
| `ruff check` | pass, no findings |
| `mypy src --strict` (run from inside `body-layer`) | pass, 55 source files |
| `pytest -q` | **1697 passed, 4 xfailed** — matches the expected number exactly |
| `audio-adapter` | **not touched by this diff** (`git diff --name-only main...a2b761c` touches only `.claude/`, `body-layer/`, `docs/`, `plans/`) — not run; no `.venv` exists in this worktree for it. Per the diff-driven subproject rule, it is out of scope for this feature. |
| `git status --porcelain` (before this report's own edits) | clean |

## Reviewer, Performance, Security — confirmed, not accepted from the log

- **Reviewer**: 8 rounds across `plans/group-contact-identity/review.md`. Every round that required
  fixes was followed by a round that re-verified them and APPROVED (round 1→2, round 3→4, Stage 2
  round, Stage 3 round, Stage 3.5 round 7, Stage 4 round 1 NEEDS REVISION → round 2 APPROVED). No
  required fix is left unresolved across the chain.
- **Performance**: `plans/group-contact-identity/performance-review.md` — **APPROVED — MONITOR**.
  Its one change request (correct `GroupTraceLogWriter`'s docstring, which claimed "a handful of
  rows per sortie" when reconcile logs one row per active cluster every reconcile, roughly 1 Hz) is
  applied at `a2b761c` — confirmed by reading the corrected docstring directly.
- **Security**: `plans/group-contact-identity/security-review.md` — **APPROVED**, no required
  fixes. `BL-B59` is named as a known, already-disclosed defect, not re-litigated.

## Scope vs. plan (amendment A10)

Merged: Stages 0, 0a, 0b, 1, 2a, 2b, 3, 3.5, 4. Confirmed against `implementation.md`'s per-stage
commit logs and `review.md`'s per-stage rounds — no stage outside this list was built, and no stage
inside it is missing a review round.

**Stage 5 (road-following, D9) skipped entirely** — confirmed no new `describe_position` caller,
Stage 1's displacement bound stays isotropic (per the implementer's own "not done, deliberately"
notes and A10's text). **Stage 6 (shortening `OBJECT_ID_MEMORY_S`) deferred** — confirmed the
constant is untouched in the diff (`grep OBJECT_ID_MEMORY_S` finds only the pre-existing value).

A10 itself is recorded in `plan.md` and cited correctly in `BL-12.md`'s own roadmap entry (now
updated with a done-banner that restates the deferral — see below). The no-omniscience boundary is
stated honestly in both places: group identity survives losing sight up to
`GROUP_REIDENTIFY_WINDOW_S`; beyond it, object-id continuity (the ten-minute shortcut D3 forbids)
is still load-bearing until Stage 6 lands.

## User decisions landed where they are read

- **D5 (ambiguity inverts toward the remembered group)** — Stage 3's `_fold_target_for_ambiguous_
  candidates`, reviewed and approved, with the rarity counter the plan asked for.
- **D6 (air-defence carve-out)** — amendment A3's classification-lattice fix, confirmed by mutation
  in the Stage 1/3 review rounds (4 of 5 air-defence classes fail via `profile_for`, fixed by
  routing through the lattice instead).
- **D7 (spoken identity)** — Stage 4's `speech.render_group_disclosure`, the actual rendered string
  checked directly in the Stage 4 round 1 review (not just the committed test, which the review
  found could not distinguish "gated" from "never ran" for the clock/range clause — fixed in round
  2, both required fixes re-verified by mutation).
- **D8 (per-classification uncertainty growth)** — Stage 2a/2b, the growth-rate table, reviewed and
  approved; its known gap (`BL-B57`, class-level beliefs don't get the entrenched override) is
  filed, not silently absorbed.
- **Q-A/Q-B (infantry cohesion bridge)** — Stage 0a/0b, both-`EAGER` fix plus a finite mixed-pair
  cap, fixes `BL-B48` (now closed below).
- **Q-C (group-identity trace line)** — Stage 1's first commit, `--group-trace`, confirmed present
  and (after the performance-review fix) correctly documented.
- **Q5 (under-count replaces over-count, accepted trade)** — exercised directly by the Stage 3
  review's reproduction of the 2C fixture, and the Stage 3.5 admission gate's own 3-line result.

## Known defects merged, honestly disposed

- **`BL-B59`** (eviction half of the fold-drift mechanism) — user-deferred, explicitly prioritised
  next, not parked unprioritised. Filed with a reproduced probe, not reasoned about.
- **`BL-B57`** (class-level air-defence belief keeps the mobile 8.0 m/s growth rate instead of the
  entrenched 0.0) — filed by the implementer, confirmed by the Reviewer, correctly not drive-by
  patched inside a calibration commit.
- **`BL-B50`** carries a recheck note (added this stage) naming the exact condition under which it
  would reopen (`BL-B59` going live) rather than a vague "check later."
- **`BL-B51`**, **`BL-B56`** — pre-existing, untouched by this milestone, correctly left open.

## Roadmap bookkeeping done by this DoD pass

- `body-layer/ROADMAP/BL-12.md` — marked `[x]` done, done-banner added stating A10's scope, the
  open no-omniscience boundary, the known-defect list, and the milestone-completion answer.
- `body-layer/ROADMAP/BL-B48.md` — marked `[x]` done (fixed by Stage 0a/0b; the implementer had
  deliberately left its status open "until merge," per its own implementation-log note).
- `body-layer/ROADMAP/BL-B58.md` — marked `[x]` done (Stage 3.5 admission gate, Reviewer-APPROVED
  round 7; was still reading "pending Reviewer/DoD").
- `body-layer/ROADMAP/BL-B24.md`, `BL-B25.md` — recheck notes added. The plan claims BL-12
  "dissolves"/"partially supersedes" both, but neither `implementation.md` nor `review.md` ever
  re-measures against them, and neither entry's own text was touched during the milestone before
  this pass. Left **open** rather than closed on the strength of a design claim.
- `body-layer/ROADMAP/body-layer-roadmap.md` — BL-12 moved from "Ahead" into the main sequence.
- Root `ROADMAP.md`'s Body Layer status-table row — one paragraph appended summarising BL-12's
  merge, scope, and known defects.

## Milestone-completion question (root `CLAUDE.md`'s own gate)

**Yes, on both counts.** `BL-8` (memory layer) inherits the *whole* of D9 (road-following),
including the cheap anisotropic half the effort/value read recommended splitting off — the user
took it all, which enlarges `BL-8`'s first slice before that milestone starts. `BL-14` (attack run)
builds on group membership whose accuracy is a short-horizon claim only: any BL-14 design that
assumes group identity survives a ten-minute gap is assuming a boundary this milestone deliberately
left open pending Stage 6.

## Verdict

**PASS.** All mechanical checks green against the real numbers, all three review gates (Reviewer,
Performance, Security) APPROVED with their change requests applied, scope matches amendment A10
exactly, user decisions are traceable to what was built, known defects are filed honestly rather
than swept in, and roadmap bookkeeping is current as of this commit.

**Outstanding, named rather than hidden:**
- Live acceptance — entirely outstanding, see the test card below. `#needs-flight` on `BL-12.md`.
- `BL-B59` — user-prioritised next, not a blocker to this merge.
- `BL-B24`/`BL-B25` — plan claims partial supersession by BL-12; unverified, recheck notes added.
- Stage 6 — deferred by user direction, not a defect in what merged.
