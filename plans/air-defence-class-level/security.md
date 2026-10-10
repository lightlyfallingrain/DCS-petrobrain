# Security Deep Analysis — `BL-B47`: `_is_air_defence` recognises a class-level SAM

Branch `fix/air-defence-class-level`, tip `a8bf3cc935cefe1c7598804b28e1bdecd2948649`.
Diff analysed: **`153efc0..a8bf3cc`** (three commits: `eb11b7a` fix, `38d199a` review, `a8bf3cc`
docstring figure). Everything at or below `153efc0` is BL-13 and was not re-analysed.

Worktree started at `e2e2164` (`main`), a strict ancestor of the named tip with a clean tree;
fast-forwarded to `a8bf3cc` before any analysis. `body-layer/ROADMAP/BL-B47.md` absent as stated.
Input documents all present and read in full.

### Verdict

**APPROVED.** No required fixes.

One judgement call is recorded below with an explicit lapse condition rather than a severity rating,
because the honest answer to "how often does the hazard fire in healthy operation" is *not measurable
from this repo* and I decline to rate it from a failure-mode story.

### Dependency Status

No dependency change. `git diff --stat 153efc0..a8bf3cc -- '*pyproject.toml' '*requirements*' '*.lock'`
is empty. No new external input surface: the added lines contain no `subprocess`, `eval`/`exec`,
`open`, `socket`/`urllib`/`requests`, `pickle`, `__import__`, `shell=True` or `dostring` (grepped over
the `+` lines of the whole diff). Two of the three commits are prose only.

---

## 1. No-omniscience — clean, and the new path reads strictly less than the old one

**The predicate reads one field, and it is belief.** `_is_air_defence` (`speech.py:1916-1959`) is now
a single expression, `_summary_op_class(facts) in AIR_DEFENSE_OP_CLASSES`. Traced to ground:

| step | reads | truth reach |
|---|---|---|
| `_is_air_defence` (`speech.py:1959`) | nothing directly | — |
| `_summary_op_class` (`speech.py:543-549`) | `facts["classification"]["value"]` only | none |
| `classification.parent_class_of` (`classification.py:170-177`) | its `str` argument | none |
| `classification._op_class_of` (`classification.py:69-80`) | its `str` argument + `object_model`'s static keyword tables | none |

`_op_class_of` is a pure function of a string over module-level constant tables. **No field of `facts`
other than `classification` is touched, and `object_type` is never read** — which is the specific
thing the old body's own docstring promised and the new one keeps. The old body read
`facts["classification"]["value"]`; the new path reads `facts.get("classification")` and the same
`"value"`. **Same key, no new field.** The `hybrid_source.py` defect class (ground-truth-derived data
written into belief behind a cosmetic uncertainty band) has no analogue here: nothing is written at
all, and no geometry is consulted.

**Verified independently, not read:** a docstring-stripped AST comparison of `speech.py` at `153efc0`
vs `a8bf3cc` yields **exactly one hunk**, entirely inside `_is_air_defence`'s body — the old
`profile_for(value).op_class` chain and its local `ImportFrom perception` replaced by a
`_summary_op_class(facts)` call. So the whole of BL-13's pull path (`_summary_air_defence_clause`,
`_summary_air_defence_freshness_clause`, `_summary_op_class`, the word budget) is **provably
unchanged**; the three docstring rewrites are prose. This reproduces the Reviewer's claim 4 by my own
instrument rather than relying on theirs.

BL-13's security required fix 1 — the freshness qualifier, fixed at `153efc0` ("Speak freshness for a
stale SAM, not only when everything is stale") — is therefore un-weakened: its code is outside the
single hunk.

---

## 2. The widening — strict, and the candidate space is closed, not merely sampled

**Re-ran the enumeration from scratch rather than reading the figure.** Independent script, importing
from this worktree's own `src/`, resolving every candidate both ways
(`object_model.profile_for(v).op_class` against `classification.parent_class_of(v)`) and testing
`AIR_DEFENSE_OP_CLASSES` membership:

| quantity | measured |
|---|---|
| declared `op_class` values | **10** |
| `_KEYWORD_PROFILES` + `_REPORTING_NAME_KEYWORD_PROFILES` | 70 + 61 = **131** |
| `reporting_names` mapping rows | **595** (TSV is 596 lines incl. header) |
| distinct candidates | **1060** |
| verdicts **lost** | **0** |
| verdicts **gained** | **4** — `OP_LRSAM`, `OP_MRSAM`, `OP_SPAAG`, `OP_SRSAM` |

Agrees with the implementation log and the Reviewer on every figure. The corrected `131` is right.

**Stronger than the enumeration claims: the candidate space is closed, so "0 lost" is total, not a
sample.** I traced every producer of a believed classification value:

- `naked_eye_source._classification_for_tier` (`naked_eye_source.py:1150-1179`) emits exactly
  `reporting_name_for(object_type)` (one of the 595), `profile.op_class` (one of the 10), or
  `object_model.DEFAULT_OP_CLASS`.
- `clustering.py:370` emits `_PRESENCE_CLASS_FALLBACK` = `"OP_GROUPSOMETHING"`.
- `hybrid_source.py:263` emits DCS cockpit-indication free text (`_distinct_populated_texts`).

Every one of those is inside the enumerated 1060 except the indication free text, and that is the
one case where old and new provably agree: for any string **not** beginning with `OP_`,
`_op_class_of` delegates straight to `profile_for`, so new ≡ old by construction.

**The only shape that could lose a verdict is unreachable.** A loss requires a value that starts
`OP_`, is not `OP_GROUPSOMETHING`, is *not* in `AIR_DEFENSE_OP_CLASSES`, and whose `profile_for`
keyword match *is* air defence — e.g. a hypothetical `"OP_SHILKA"` (matches the `"shilka"` keyword,
old `True`; new returns the literal, `False`). There are 19 air-defence keyword keys that could
collide this way. **No producer can emit such a value**: the `OP_*` strings come only from
`profile.op_class`, which is one of the 10 declared, all of which are either in
`AIR_DEFENSE_OP_CLASSES` or not air defence under either resolver. Recorded because it is the one
place a future `op_class` addition could make this a real trade — see observation 3.

**The fix cannot lose a warning, structurally.** Both call sites (`speech.py:2496`, `:2514`) read
`is_air_defence_repeat = not is_new_class and _is_air_defence(facts)` and then
`if is_new_class or is_air_defence_repeat:` append to `delta_members`. The predicate's result is only
ever **OR'd into** a speech decision, never used to suppress one. A widened predicate therefore
produces monotonically more speech and can never silence a contact that previously spoke. This is a
property of the call sites, not of the enumeration, and it is the strongest available answer to "is a
threat that used to be announced now not announced": **no, it cannot be.**

---

## 3. The callout ratchet (`BL-B50`) — does not block, with a stated lapse condition

I re-measured this rather than accepting either the implementation log's framing or the Reviewer's.
All probes drive the scheduler's **real** sequence, including the suppression the Reviewer's write-up
does not show being applied — `content_signature == belief_group.last_spoken_signature → continue`
(`callouts.py:1190`, re-checked at `:1221`). My first two probe attempts omitted that check and
inflated every count; the numbers below are from the corrected instrument.

| configuration (10 ticks, membership flipping every tick) | pre-fix | post-fix |
|---|---|---|
| **steady state, no membership change at all** (20 ticks) | — | **1 line, then silent for 19** |
| single oscillating class-level SAM, class already in group | 0 | **0** (speaks once at first arrival, then the snapshot retains it) |
| two oscillating contacts, two distinct classes, **no air defence anywhere** | **10 / 10** | **10 / 10** |
| oscillating SAM + oscillating armor (SAM carried by `leader_changed`) | 10 / 10 | 10 / 10 |
| **SAM-repeat as the sole carrier** (base already holds two SAMs, SAM not leading) | **1 / 10** | **10 / 10** |

Three conclusions, and the third decides it.

- **In healthy operation this fix adds nothing.** Steady state is one line then silence; a single
  oscillator is one line then silence, because `mark_group_spoken` refreshes
  `last_spoken_member_contact_ids` and a later rejoin is no longer an arrival. The ratchet needs
  **two** alternating line shapes, because each speech refreshes the snapshot without the *other*
  oscillator and re-arms it. The one-slot signature guard is powerless against that, and the
  membership snapshot is what actually suppresses the single-oscillator case.
- **The last row is real: the fix takes 1 line to 10 in the configuration where
  `is_air_defence_repeat` is the sole carrier.** Delta +9. The implementation log and the Reviewer
  are both right that this exists; I reproduced it.
- **But the ratchet is fully reachable today with no air defence involved, at the identical 10/10,
  pre-fix and post-fix.** So this fix is not what stands between the pilot and the ratchet.

**Therefore: ship it.** The asymmetry is decisive and is not a close call. Blocking buys *zero*
reduction in ratchet exposure (row 3 is unchanged at 10/10 either way) and costs a **guaranteed,
every-time silence** on a class-level SAM — which is the state a contact is in before it is
identified to type, i.e. most of the time at range, on the one class `_OP_CLASS_DISPLAY` singles out
as the difference between a threat you can fly around and one you cannot. Trading a certain missed
threat warning for no measured reduction in a pre-existing repetition hazard is the wrong trade.

**The lapse condition, stated rather than implied.** I am explicitly *not* rating this low/low, and
not borrowing the Reviewer's "reachable anyway" as acceptability without an expiry — that is the
error this role has made before (`plans/dcs-driven-los/security-deep-analysis.md:109-121`, a
silent fallback rated low/low that the next sortie measured carrying 77 % of admissions). The
missing number is **how often group membership actually flips tick-to-tick in a real sortie**, and it
is not obtainable here: no sortie logs are present in the worktree. So:

> **Recompute this rating, and treat `BL-B50` as blocking-priority rather than backlog, if either
> holds: (a) a sortie log shows group membership flipping on consecutive ticks, or (b) `BL-B48`'s
> `EAGER` infantry cohesion ships or persists into a flown build** — a 6 km-wide group is precisely
> the input that makes membership flip, which is the ratchet's only missing ingredient.

Neither hazard is dangerous alone; together they are the shape the pilot has already complained
about. I agree with the Reviewer that the fix belongs to the scheduler (suppression becoming a
history set, not a one-slot signature) and is owed regardless of this commit, and that filing it as
"SAM repeat churns" would under-scope it. `BL-B50` is already filed; not re-filed here.

---

## Observations (no action required)

| # | Location | Finding | Assessment |
|---|---|---|---|
| 1 | `belief/groups.py:234` vs `crew_console.py:264` (`BL-B51`) | Three copies of the air-defence class set; only `crew_console`'s has a `<=` drift guard, `AIR_DEFENSE_OP_CLASSES` has a literal pin (a change detector). | **Does not block.** Exposure is genuinely unchanged by this diff — the *old* predicate tested the same set, so the fix neither widens nor narrows this. Already filed; not re-filed. Worth saying that this diff raises the *consequence* of the gap: that one set is now what the push predicate, the pull clause and the freshness marker all resolve against, so a future `op_class` omission is silent in three places instead of two. The omission is not hypothetical — it already cost `OP_LRSAM` months of silence in the other copy. |
| 2 | `speech.py:1959` | Missing or non-dict `classification` now answers `False` where it raised `KeyError`/`AssertionError`. | Strictly more lenient and **fails safe in the correct direction here**: the predicate only ever adds speech, so leniency cannot silence a warning. Both call sites check `_classification_level(facts)` first, which raises there instead. Pinned by `test_is_air_defence_answers_false_for_facts_without_a_classification`. |
| 3 | `classification.py:73-76` | `_op_class_of` early-returns any non-default `OP_*` string, so a *future* `op_class` value that is air defence by keyword but absent from `AIR_DEFENSE_OP_CLASSES` would lose a verdict (see §2). | Unreachable today — no producer can emit such a value. This is the concrete mechanism by which observation 1 would become a real air-defence silence rather than a tidiness issue, which is the argument for the `<=` guard on `AIR_DEFENSE_OP_CLASSES`. |
| 4 | `speech.py:2540` | `"Now leading: <X>."` repeats verbatim on alternating ticks in the oscillation probes (pre- **and** post-fix), because the alternation defeats the one-slot signature guard. | Pre-existing, not air-defence-specific, and already inside `BL-B50`'s measured scope. Noted only so the filing is not read as being about delta clauses alone. |

### What cleared, and how

- **No-omniscience**: traced `_is_air_defence` → `_summary_op_class` → `parent_class_of` →
  `_op_class_of` to ground; one belief field read, no truth-derived field reachable, nothing written.
- **Strict widening**: enumeration re-run (0 lost / 4 gained over 1060), *plus* producer analysis
  showing the candidate space is closed, *plus* a call-site argument that the predicate can only ever
  add speech.
- **BL-13 untouched**: own docstring-stripped AST diff, one hunk, inside `_is_air_defence`.
- **Scope**: `belief/groups.py` and `decay.py` absent from the diff (`git diff --stat`); no new
  constant; `AIR_DEFENSE_OP_CLASSES` reused.
- **Ratchet**: five configurations measured through the scheduler's real suppression path, pre- and
  post-fix, after discarding two earlier probes that bypassed it.

### Checks

Run with cwd inside each subproject, using the root checkout's venv binaries (the worktree has no
`.venv`); imports confirmed to resolve to the worktree's own `src/` before any result was trusted.

| subproject | ruff check | ruff format | mypy | pytest |
|---|---|---|---|---|
| body-layer | pass | 118 files already formatted | no issues in 54 source files | **1632 passed, 4 xfailed** |
| audio-adapter | pass | — | no issues in 15 source files | **255 passed, 1 skipped** |

Both match the expected figures exactly.
