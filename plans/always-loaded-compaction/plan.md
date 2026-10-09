# Compacting the always-loaded instruction files

Queued 2026-10-09, by user direction, to run **after** `plans/obsidian-links-and-tags/` Stages 4–5
land and are harvested. Nothing here is started.

## What the user asked, and what they decided

The question arrived as part of an `/explore` about roadmap verbosity. Their words, in order,
because the sequence is what narrowed the work:

> *"many of the roadmap or backlog entries are **very** verbose. Can we compact them? Archive or
> forget obsolete information? Use caveman to compress old entries to very terse format? Other
> options?"*

Then, after seeing that reasoning chains are what carry the *why*:

> *"I've seen files where reasoning chains are stored. User input, analysis, then more user input,
> etc. I wonder if those could be condensed to not have the chain of thought but the outcome.
> Similarly if seen very long comment sections in code. And I wonder the same thing. Token cost is
> what I'm wondering about. As well as long prose becoming stale."*

And the decision:

> *"I'm fine keeping the chains when we split the roadmaps so not everything is read every time.
> Any chance of compacting the always loaded stuff? Without losing important information and
> guidelines. It's what you read every session, I am not a good judge on that."*

**So: the chains stay. The roadmap entries stay. The target is the always-loaded set only**, and the
user has explicitly delegated the judgement of what is safe to move, while naming the constraint —
*"without losing important information and guidelines"*.

## What the measurement found, since it is what makes this a small job rather than a large one

| what | tokens | paid when |
|---|---|---|
| `CLAUDE.md` + `AGENTS.md` | **14,200** | every session, unconditionally |
| each nested `<sub>/CLAUDE.md` | 2,000–6,900 | whenever work happens in that directory |
| all 7 `plans/*/explore-notes.md` + `decisions.md` | ~17,500 **total** | only when one is opened |
| median split roadmap entry | ~300 | only when one is opened |

The reasoning chains cost nothing unless opened, which is why they were taken off the table. The
always-loaded files cost ~14.2k before a single file is read, and that is the only prose in the repo
with a recurring unconditional cost.

### Staleness tracks tense, not length — and this is why the chains were spared

Every staleness incident this repo has recorded is a **present-tense assertion about current
state**, never a dated record of reasoning:

- `dod.md`: *"agents run without worktree isolation by default"* — false since 2026-09-21
- `todo/todo.md`: *"`main` is at `c912478`"* — ~30 commits off when the audit found it
- "three subprojects" — four separate recurrences across `CLAUDE.md`, `AGENTS.md` and four skills
- `body-layer/CLAUDE.md`: an invariant naming `BINOCULAR_RANGE_MULTIPLIER`, a constant cones 2A retired
- the 5 Hz figure — 5× wrong, asserted in five files, corrected in one

The 2026-09-27 integrity audit's diagnosis of the `dod.md` case generalises to all of them:

> *"The stale sentence justifies the right action with a premise that is now false, which makes it
> unfixable by reasoning: an agent that notices its own worktree contradicts the sentence cannot
> tell which half is current."*

A dated record — *"decided 2026-10-06, on the Reviewer's recommendation, because Y"* — cannot go
stale. It was true on that date and remains so; supersession is handled by `docs/PROCESS.md`
rule 2's pointer, not by a rewrite.

**The trap this closes:** condensing a chain to its outcome is precisely the transformation that
turns durable prose into stale-prone prose. *"User said X, I analysed Y, we chose Z because Y"*
becomes *"Z"* — the date, the evidence and the attribution are gone, and what remains is a bare
present-tense assertion, the only shape that has ever gone stale here. Measured on the
always-loaded files, only ~25% of their prose carries a date (`CLAUDE.md` 26%, `AGENTS.md` 22%);
the other ~75% is present-tense assertion. **The stale risk is concentrated in the part that is not
reasoning chain.**

## The criterion — not length, and not taste

> **A rule's evidence may move out of the always-loaded file when a hook delivers that rule at the
> point of use. It stays when only memory enforces it.**

This is testable against `.claude/settings.json` rather than argued. Applied to the largest block in
the repo — `AGENTS.md` "The four rules", 1,715 words, **41% of that file** — it splits cleanly.
Rules 2 and 3 are 87 words together and are already minimal. The other 1,628 are:

| | words | hook at the point of use? | verdict |
|---|---|---|---|
| **Rule 4** — addressing: name the tip, agent checks `rev-parse HEAD`, `--ff-only` if a strict ancestor | 937 | **yes** — `agent-worktree-reminder.sh` and `agent-sha-gate.sh` both fire `PreToolUse` on `Agent` and reprint the operative lines | evidence may move |
| **Rule 1** — harvest: commit everything, cherry-pick, verify against the file list, plain `remove`, `rev-parse` before `branch -D` | 691 | **no** — the harvest happens *after* the agent reports, which is after every dispatch hook. Nothing fires | **keep** |

Verified by reading the hook, not by assuming: `agent-worktree-reminder.sh` matches `rev-parse`
three times and `agent-memory` once, and carries nothing about cherry-picking or branch deletion.
So rule 4's narrative is redundant with a hook seen at every dispatch, while rule 1's near-miss
story is the only thing standing between the main loop and deleting an unharvested commit — the
2026-10-06 Debugger case, where a second commit arrived after the report and survived only because
`gc` had not run.

## The edit

~2,300 words out, ≈3.7k tokens, **26% of the always-loaded 14.2k**. Moved text goes **verbatim** to
`docs/`, with a one-line pointer left in place. Nothing is deleted.

| where | words out | what moves |
|---|---|---|
| `AGENTS.md` rule 4 | ~750 | the three role-table narratives, the eleven-commits-behind (`19143fa`/`dce2534`) story, the `gq.sh`/`c33af2e` aside, the `*.egg-info` history of why `--force` was once needed |
| `AGENTS.md` "Status: all four rules in force" | ~180 | a concluded trial report. **Keep one line: heredocs and `>>` are refused inside a worktree** — operative, no hook, and an agent that does not know it improvises mid-task |
| `CLAUDE.md` "Current priority" + "Subprojects" | ~200 | these state the stale-enumeration lesson **twice**, and the file says so itself — *"that is the same rule 'Current priority' states above, applied to this section"*. Collapse to one statement plus the `git ls-files '*/pyproject.toml'` check |
| `CLAUDE.md` graph sections | ~450 | the zero-queries-on-2026-09-26/27 retro, the crossing-callout debugger story. **Keep the graph-vs-`grep` table** — a decision rule in active use that no hook carries |
| `CLAUDE.md` "Session Start" | ~160 | the 67-vs-58-branches arithmetic. **Keep the 2026-09-25 double-implementation story** — no hook enforces session start, and that story is the entire reason the step exists |
| `CLAUDE.md` "Agents" | ~90 | the `dod` haiku→sonnet incident. The current fact is one line |

### Not to be cut, and the reasons are specific

- **`CLAUDE.md` "Talking to the user"** (432 words). The instruction set for every message the user
  reads, and its list of corrections that arrived only because reasoning was shown is what prevents
  reversion to status lines. No hook.
- **`CLAUDE.md` "Whose job is whose"** (371). The product test every plan must pass. Its two worked
  examples — the removed transport, the dropped F10 contact menu — are what make it usable rather
  than abstract.
- **`AGENTS.md` Effort/Value Check** (417) and `CLAUDE.md`'s flight-feedback ordering. The
  flight-feedback hooks fire but carry no *why*, and the user's verbatim words there are the
  specification.

## Risks, stated because the user cannot see them and the author is the interested party

1. **The author is being asked how much of its own instruction set to move out of sight, and the
   failure mode is invisible from the inside.** A rule that is cut and then violated does not
   announce the connection; the violation simply looks like a mistake. This repo's record is partly
   a list of rules stated briefly, ignored, and rewritten at length *because* brevity failed —
   `CLAUDE.md` says so of one of them: *"The rule was not the problem. Its trigger was."*
2. **An evidence layer differs from a split roadmap.** The roadmap split is safe because a `done`
   entry is never needed. Evidence is needed exactly when someone is about to skip a rule, which is
   the moment they are least likely to follow a pointer. The hook criterion is what narrows this
   risk, and it is the only thing that does.
3. **Nested `<sub>/CLAUDE.md` files are out of scope for this pass.** They are 2.0–6.9k tokens each
   and load conditionally; `audio-adapter/CLAUDE.md` is 78% dated prose, which on the tense finding
   above is the *durable* kind. Measure before touching them.

### Safeguard

One reviewable commit on `main` — cross-cutting non-code work, so it does not belong on a feature
branch (root `CLAUDE.md` "Workflow"). Moved text lands verbatim under `docs/`, so revert is one
command. **If agent handoffs or session starts start going wrong in the following week, that is the
signal, and the change goes back.**

## Order of work

1. Stages 4–5 of `plans/obsidian-links-and-tags/` land and are harvested. (Blocking — they touch
   `docs/DOC_CONVENTIONS.md` and the gate scripts, and a concurrent `AGENTS.md` edit would be a
   needless conflict.)
2. `AGENTS.md` rule 4 and "Status" first — the clearest case, the biggest single saving, the
   strongest hook backing.
3. `CLAUDE.md`'s six items, in the table's order.
4. Re-measure the always-loaded total and record it here.

## Result, 2026-10-09 — done, 17% not 26%

| file | before | after |
|---|---|---|
| `CLAUDE.md` | 4,676 words / ~7,649 tok | 4,201 / ~6,906 |
| `AGENTS.md` | 4,100 words / ~6,707 tok | 3,194 / ~5,072 |
| **total** | **~14,357 tok** | **~11,979 tok — 17% off** |

**`AGENTS.md` hit its estimate (906 words out against ~930 planned); `CLAUDE.md` did not (475
against ~900).** The shortfall is one item: collapsing the duplicated stale-enumeration lesson was
costed as deleting ~200 words, but the two copies did not say the same thing — "Current priority"
framed it as *which subprojects exist*, "Subprojects" as *which have a nested `CLAUDE.md`*. Dropping
one wholesale would have lost half the rule, so it was **consolidated** instead: the surviving copy
was expanded to carry both, for a net saving of 43 words rather than 200. That is the criterion
working against the estimate, which is the right way round.

**Destinations**, all moved text verbatim:

| from | to |
|---|---|
| `AGENTS.md` rules 1–4 incident record, the trial frictions, the inversion account | **`docs/AGENT_WORKTREE_PROTOCOL.md`** (new) |
| `CLAUDE.md` graph-query lapse, the crossing-callout cost, the 5 Hz retro, the memory-corpus exclusion | `docs/PROCESS.md`, "Keeping the knowledge graph honest" |
| `CLAUDE.md` `dod` model change, the lapsed blanket security/performance skip | `docs/AGENT_ROLES.md` |

Verified mechanically: 18 of 18 distinctive removed passages are present in a destination file, and
every `docs/`, `plans/` or `.claude/` path referenced from the two always-loaded files resolves.

### Two corrections made in passing, both present-tense claims that had gone stale

Neither is compaction; both are the staleness class the criterion predicts, found by reading the
prose closely enough to compact it.

- **`CLAUDE.md` asserted "the rebuild order at merge is load-bearing — documents first, graph
  second, merge third".** `docs/PROCESS.md` had already revised exactly that sentence as an
  overstatement: only documents-before-graph matters, and stating it as a rigid three-step sequence
  "invited exactly the wrong trade the first time it was applied", holding up a merge for a
  twenty-minute rebuild. The always-loaded file was still carrying the retired version.
- **Session Start step 2 sent every session to `todo/todo.md` and `todo/backlog.md`**, which became
  4-line pointers earlier the same day. Now points at `todo/todo/todo-tasks.md` and
  `todo/backlog/todo-backlog.md` directly.

### What to watch, per the safeguard

Agent handoffs and session starts, for a week. The specific regressions this change could cause: a
harvest that skips the `git rev-parse` tip check before `git branch -D` (rule 1 kept its evidence
precisely because no hook fires there), and a session start that reads the roadmap without checking
`git branch -v`. If either happens, revert — moved text is verbatim, so it is one command.
