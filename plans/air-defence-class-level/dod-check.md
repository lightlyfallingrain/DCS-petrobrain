# Definition of Done — `BL-B47`: `_is_air_defence` recognises a class-level SAM

**Verdict: PASS.**

**Scoped to tip `dfbcd6efb0e51f9333a089b185e5a6bde3beb3b1`** on `fix/air-defence-class-level`. A DoD
verdict is a statement about one commit, not about a branch: if the branch moves after this, the
verdict is stale and does not carry forward across a behavioural change.

Worktree started at `e2e2164` (`main`) — a strict ancestor, clean tree — and was fast-forwarded to
`dfbcd6e` before any check ran. Diff in scope: **`153efc0..dfbcd6e`**, four commits (`eb11b7a` fix,
`38d199a` review, `a8bf3cc` docstring figure, `dfbcd6e` security). Everything at or below `153efc0`
is BL-13, which passed its own DoD at `3b1d1df`, and was not re-gated here.

Input documents: `implementation.md`, `review.md`, `security.md` all present and read in full.
`body-layer/ROADMAP/BL-B47.md` absent as stated — see §5, which is the one thing the merge has to
honour.

---

## 1. Mechanical checks — run, not trusted

Touched subprojects derived from the diff (`git diff --name-only e2e2164..HEAD`), not from memory:
**body-layer** and **audio-adapter** (the latter via the BL-13 commits this branch carries). No
other subproject appears in the diff. Run with cwd inside each subproject, using the root
checkout's venv binaries — the worktree has no `.venv` (gitignored).

| subproject | `ruff format --check` | `ruff check .` | `mypy src` | `pytest` |
|---|---|---|---|---|
| body-layer | 118 files already formatted | All checks passed | no issues in 54 source files | **1632 passed, 4 xfailed** |
| audio-adapter | 29 files already formatted | All checks passed | no issues in 15 source files | **255 passed, 1 skipped** |

Both test figures match the expected counts exactly.

- **No debug output, no `TODO`/`FIXME`/`breakpoint`/`pdb`** in the added lines
  (`git diff 153efc0..dfbcd6e -- body-layer/ | grep '^+'`, filtered: empty).
- **No error suppression introduced.** The one behavioural leniency is deliberate and analysed —
  §3, observation 2.
- **Nothing gitignored or generated committed.** The diff is 16 files: `body-layer/src/belief/
  speech.py`, `body-layer/tests/test_speech.py`, three `plans/` documents, and eleven
  `.claude/agent-memory/` files. The memory files are at the **repo-root-relative** path, not a
  subproject-relative one.
- **Clean tree** (`git status --porcelain` empty) at the start and at hand-off.

## 2. Built as intended — one line, verified by re-running the evidence

`_is_air_defence` (`speech.py:1959`) is now the single expression
`_summary_op_class(facts) in AIR_DEFENSE_OP_CLASSES`. The scope is exactly the one line plus three
docstring corrections and the tests; nothing else in the pull path moved.

**The enumeration was re-run here from scratch rather than read.** Independent script against this
worktree's own `src/`, resolving every candidate both ways (`object_model.profile_for(v).op_class`
vs `classification.parent_class_of(v)`) and testing `AIR_DEFENSE_OP_CLASSES` membership:

| quantity | measured here |
|---|---|
| declared `op_class` values (incl. `DEFAULT_OP_CLASS`) | **10** |
| `_KEYWORD_PROFILES` + `_REPORTING_NAME_KEYWORD_PROFILES` | 70 + 61 = **131** |
| `reporting_names` mapping rows | **595** |
| distinct reporting-name values | 376 |
| **distinct candidates** | **1060** |
| verdicts **lost** | **0** |
| verdicts **gained** | **4** — `OP_LRSAM`, `OP_MRSAM`, `OP_SPAAG`, `OP_SRSAM` |

This is a third independent reproduction, agreeing with the Implementer and the Reviewer on every
figure. Worth recording how the 10 is arrived at, since it is the figure easiest to get wrong:
harvesting `op_class` from the two profile tables alone yields **9** and a total of 1059 — the tenth
is `object_model.DEFAULT_OP_CLASS` (`OP_GROUPSOMETHING`), which is a declared value but appears in
neither table. The docstring's 10/1060 are correct.

**The Reviewer's required fix is closed.** The `128` → `131` correction landed in `a8bf3cc`; `131`
now stands in both `speech.py:1940` and `test_speech.py:2760`, and my own count confirms it. The two
surviving occurrences of "128" (`review.md:57`, `implementation.md:215`) are the correction's own
audit trail, not live claims.

**Tests are meaningful, not decorative.** Three parametrised groups: the positive class-level case
parametrised over `AIR_DEFENSE_OP_CLASSES` *itself* rather than a hand-copied list (so a class added
to that set is covered without anyone remembering); a type-level pin over four real entries of
`object_model`'s own keyword table, so the widening cannot be a trade; and a negative set — the
default bucket, unresolvable free text, the three non-air-defence classes — which is what makes the
gain meaningful, since a predicate widened to always-`True` would pass every positive test.

## 3. Security's two arguments — checked, and they hold

Both arguments go beyond the enumeration, and both are the actual justification for shipping, so I
verified the mechanism rather than the prose.

**(a) The candidate space is closed, so "0 lost" is total rather than a sample.** Holds.
`classification._op_class_of` (`classification.py:69-80`) early-returns any `OP_*` string that is
not the default and otherwise delegates to `profile_for`. So the *only* domain on which the two
resolvers can diverge is non-default `OP_*` strings; for everything else new ≡ old by construction,
which covers `hybrid_source`'s DCS free text without needing it enumerated. Within that domain, the
producers are bounded: `naked_eye_source._classification_for_tier` emits a reporting name, a
`profile.op_class`, or the default; `clustering.py:370` emits the default. All inside the 1060.

I probed the one shape that could lose a verdict, to confirm the mechanism is real rather than
rhetorical — an `OP_`-prefixed string that is not an `AIR_DEFENSE_OP_CLASSES` member but whose
keyword match *is* air defence:

```
OP_ZU23_EXTRA      old='OP_ZU23'           (True)  new='OP_ZU23_EXTRA' (False)  -> LOSS
OP_SHILKA          old='OP_SPAAG'          (True)  new='OP_SHILKA'     (False)  -> LOSS
OP_OSA             old='OP_SRSAM'          (True)  new='OP_OSA'        (False)  -> LOSS
```

The mechanism exists; **no producer can emit any of these today**, so it is unreachable and does not
block. This independently reproduces Security's observation 3 by a different instrument. The
operative consequence, which I agree with and restate because it is the live risk: the closure is a
property of the *current value vocabulary*, not of the code, so a future `op_class` value that is
air defence by keyword but absent from `AIR_DEFENSE_OP_CLASSES` would silently lose the verdict —
the BL-B47 failure mirrored. `BL-B51` (three copies of the set, only one with a `<=` drift guard) is
the filed home for that; `test_groups.py:368` is a literal pin, which is a change detector rather
than a guard.

**(b) The predicate is monotone in speech, so it structurally cannot lose a warning.** Holds, and it
is the strongest claim available. Both call sites (`speech.py:2496`, `:2514`) are identical in
shape:

```python
is_air_defence_repeat = not is_new_class and _is_air_defence(facts)
if is_new_class or is_air_defence_repeat:
    delta_members.append(facts)
```

The result is only ever **OR'd into an inclusion** decision — there is no third call site and no use
of the flag to suppress. Widening it can therefore only add members to `delta_members`, never remove
one, and the only downstream effect of an empty `delta_members` is `return None` (silence). So a
contact that previously spoke cannot be silenced by this change. Confirmed by `grep` over
`body-layer/src`: `_is_air_defence` has exactly two call sites.

This also makes observation 2 inert: `facts` with a missing or non-dict `classification` now answers
`False` where it raised. Both call sites `continue` on `_classification_level(facts) in ("presence",
"unknown")` *before* reaching the predicate, so the lenient branch is unreachable from production
code, and leniency in a monotone-add predicate fails in the safe direction anyway.

## 4. Security's lapse condition — preserved verbatim

Security declined to rate the callout-ratchet risk low, because the missing number is how often
group membership actually flips in a real sortie and no sortie logs exist in the worktree. **This
condition is a deliverable, not a footnote** — a standing exemption without a stated end condition
outlives its premise silently, which this project has a documented case of
(`plans/dcs-driven-los/security-deep-analysis.md:109-121`, a fallback rated low/low that the next
sortie measured carrying 77 % of admissions). Quoted exactly:

> **Recompute this rating, and treat `BL-B50` as blocking-priority rather than backlog, if either
> holds: (a) a sortie log shows group membership flipping on consecutive ticks, or (b) `BL-B48`'s
> `EAGER` infantry cohesion ships or persists into a flown build** — a 6 km-wide group is precisely
> the input that makes membership flip, which is the ratchet's only missing ingredient.

The reasoning that makes this ship-now rather than block: the ratchet is already fully reachable
with no air defence involved, at an identical 10/10 pre- and post-fix, so blocking buys zero
reduction in ratchet exposure while costing a guaranteed, every-time silence on a class-level SAM.
**The first sortie that produces logs is the trigger** — the condition is cheap to evaluate and
nothing else will prompt it.

## 5. Roadmap bookkeeping — a merge-order dependency, not an update I can make

**`BL-B47` cannot be marked done from this branch, and must not be filed here.** Verified rather
than assumed:

- This branch's `body-layer/ROADMAP/` maxes at **`BL-B46`**
  (`ls body-layer/ROADMAP/ | grep -oE '^BL-B[0-9]+' | sort -V | tail -1` — full prefix, `sort -V`).
- `chore/file-bl13-review-findings` holds **`BL-B47` through `BL-B54`**. Its `BL-B47.md` is this
  exact defect, still `[ ]` / `#status/open`.

So minting here would produce `BL-B47` and collide with the entry *for the very defect this branch
fixes*. **Declined** — the same call BL-13's DoD correctly made, and the second occurrence of this
situation.

**The dependency the merge has to honour.** If this branch merges alone, the trunk gets the fix
while the backlog still says the defect is open — and nothing would ever correct it, because the
entry file is where `grep '#status/done'` looks. Merge order:

1. `chore/file-bl13-review-findings` — brings `BL-B47`–`BL-B54` onto the trunk
2. `feature/bl13-crew-query-path` — BL-13's own bookkeeping and sortie card
3. `fix/air-defence-class-level` — this fix

**Then**, in its own worktree, mark `BL-B47` done **on `body-layer/ROADMAP/BL-B47.md` itself** —
`[x]`, `#status/done` replacing `#status/open`, with a done-entry recording: the one-line lattice
fix, the 1060-candidate enumeration (0 lost / 4 gained) reproduced three times independently, the
monotone-in-speech argument as the reason it could ship without live verification, and §4's lapse
condition as the open thread. Not in `body-layer/ROADMAP.md`, which is a four-line pointer — writing
there leaves the entry open, keeps `grep '#status/done'` reporting it open, and still satisfies
`push-roadmap-gate.sh` because *a* `ROADMAP.md` was touched. Resolve with
`.claude/scripts/roadmap-source.sh --dir body-layer/ROADMAP.md` if in doubt.

**Does this change what the next milestone should be?** No. It closes a backlog defect on BL-13's
push path and invalidates no downstream assumption. Its one second-order effect is on `BL-B50`: this
fix adds a new carrier for the repetition ratchet (§4), which raises `BL-B50`'s value without
changing its scope — and `BL-B51`'s value too, since one set is now what the push predicate, the
pull clause and the freshness marker all resolve against, so a future omission is silent in three
places instead of two.

## 6. The acceptance boundary — what these fixtures structurally cannot reach

**Nothing on this branch has ever talked to a live DCS session, and no agent in this project can
reach one.** Everything above is fixtures, enumeration and static call-site analysis on the Mac.

Named precisely, because a fixture pass must never be mistaken for a flight pass:

- **The verified claim is "the predicate answers `True` for a class-level SAM."** That is a
  statement about a function, and it is total over the reachable value space.
- **The unverified claim is "the pilot now hears air defence called out where he previously heard
  nothing."** Between the two sit the real contact lifecycle, the real classification levels a
  contact actually passes through at range, group reconciliation, and the scheduler's suppression —
  none of which a fixture exercises with real timing. The enumeration cannot tell a working path
  from a path that is never entered.
- **The F10-vocabulary precedent is the exact warning.** That feature passed DoD on fixtures and the
  next sortie found two defects no fixture could detect: `Scan` driving the wrong subsystem (correct
  code, wrong subsystem) and a raw task id spoken aloud (only a defect when a human *hears* it). The
  class of gap here is the same shape — this change is about what is *said*, and whether it is said
  at the right moment is only observable in a cockpit.
- **The ratchet is the specific thing to listen for**, per §4: the risk is not silence but
  repetition.

**This does not block the merge.** Live verification happens in bursts and depends on access to the
Windows box; the fix is strictly monotone in speech and cannot make anything worse than silence, so
it should merge and be flown when a sortie allows. The outstanding item belongs on `BL-B47`'s own
entry as **`#needs-flight`** (per `docs/TAGS.md`), set at the same time as `#status/done` — a tag,
not a prose note, because the tag is what makes the debt mechanically countable. This is **deferred,
not waived**: the sortie exists, it just has not happened.

**Batched:** one sortie clears this and BL-13 together. See §7.

## 7. Acceptance card — append to BL-13's, and correct its checkout line

**Decision: append a short block to the existing card**, `docs/acceptance/
2026-10-10-crew-query-path-sortie.md`, rather than write a second one. One sortie covers both, the
pilot reads one page at the controls, and the user has previously directed that cards be folded
rather than multiplied.

**It cannot be appended from this worktree** — that file does not exist here. It was added in
`dd1fb24` on `feature/bl13-crew-query-path`, which this branch forked from before. Fabricating a
copy here would mean a 263-line divergent file and a guaranteed merge conflict, so the block text is
below, to be appended after step 2 of §5's merge order (its own worktree, cross-cutting work).

**A real defect in the existing card, found by checking rather than reading.** Its checkout line
says:

```sh
cd /Users/sg/Code/DCS-petrobrain && git checkout feature/bl13-crew-query-path
```

**That branch does not contain this fix.** A pilot following the card flies BL-13 *without* the
class-level SAM behaviour and would be judging the air-defence callouts against the broken
predicate. The converse is the useful part: the three commits this branch lacks from BL-13
(`3b1d1df`, `dd1fb24`, `5c9f289`) touch **no `src/` or `tests/` file at all** — they are review
prose, the DoD report, the card and roadmap text. Verified by `git show --stat` on each. So
**`fix/air-defence-class-level` contains the whole of BL-13's code plus this fix**, and is the
single branch that can fly both. After §5's merges, `main` is the better answer.

So the card's branch line must be corrected to the branch actually being flown, per the standing
rule that naming the branch is now the only channel — the root checkout is the user's and no longer
signals what to test.

### Block to append to `docs/acceptance/2026-10-10-crew-query-path-sortie.md`

> ## Also on this sortie — `BL-B47`, a class-level SAM is now air defence
>
> **Fly this from `fix/air-defence-class-level`, not `feature/bl13-crew-query-path`** — that branch
> has all of BL-13's code *plus* this fix, and is the only single checkout that carries both. After
> both merge, `main` carries them.
>
> ```sh
> cd /Users/sg/Code/DCS-petrobrain && git checkout fix/air-defence-class-level
> ```
>
> **What you are judging:** a contact believed to be a SAM *before* it is identified to type — which
> at range is most of the time — now gets air-defence treatment in a group callout where it was
> silent. Nothing else changed; no new flag, no new process.
>
> **What nobody here could check:** everything below the ground check. Nothing on this branch has
> talked to a live DCS session. Whether the callout arrives at the right *moment* is only observable
> in the cockpit — **UNVERIFIED**.
>
> ### Ground check (real output, run on this branch)
>
> ```
> $ cd body-layer && PYTHONPATH=src:../world-model/src .venv/bin/python -c 'from belief.speech import _is_air_defence as f; from belief.groups import AIR_DEFENSE_OP_CLASSES as A; from perception.object_model import profile_for as p
> for c in sorted(A): print(c, "was", p(c).op_class in A, "now", f({"classification": {"value": c, "level": 2}}))'
> OP_LRSAM was False now True
> OP_MRSAM was False now True
> OP_SPAAG was False now True
> OP_SRSAM was False now True
> OP_ZU23 was True now True
> ```
>
> Four of the five SAM/AAA classes were invisible to the push-path predicate; `OP_ZU23` worked only
> because its literal string happened to match the keyword table's own `"zu23"` entry.
>
> ### In the air — **UNVERIFIED**
>
> 1. **A SAM seen at range, before identification.** Fly within naked-eye range of a SAM site in a
>    group with other vehicles, far enough that it is not identified to type. **Expect:** the group
>    callout names the air defence. **Before this fix it was silent on it.**
> 2. **A SAM that stays in a group you have already been told about.** **Expect:** it is still
>    mentioned when it re-arrives, where a non-air-defence repeat would not be — "more air defence
>    is always news" is the rule being tested.
> 3. **The thing to listen for, and the known risk.** **Does it repeat too much?** This fix adds a
>    new reason for a group line to be re-spoken. If you hear the same air-defence line cycling on
>    consecutive calls, that is `BL-B50` (the callout ratchet) and it is worth saying so — it is
>    already filed, and a sortie log showing membership flipping tick-to-tick is exactly the
>    evidence that makes it blocking-priority rather than backlog.
> 4. **Nothing should have gone quiet.** Structurally this change can only *add* speech, never
>    remove it. If anything you used to hear is now missing, that contradicts the analysis and is the
>    most important thing you could report.

## Verdict

**PASS**, scoped to `dfbcd6e`. No gap found in the code, the tests, the plan match, the invariants
or the security sign-off. The two conditions attached to this pass are bookkeeping and flight, not
code:

1. **§5's merge order**, so the trunk does not get the fix while `BL-B47` still reads open.
2. **§4's lapse condition**, carried verbatim, and `#needs-flight` on `BL-B47`'s entry.
