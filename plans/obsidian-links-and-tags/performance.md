### Performance Review

Branch `feature/doc-conventions-audio-adapter`, reviewed at tip `66e7244` (diff against `dcd3aee`).
Scope: no application code changed — `audio-adapter/src` is untouched. The cost under review is
developer-loop cost: per-commit hook time, and Session Start read cost. This is the once-per-feature
performance pass required before DoD (root `CLAUDE.md`, "Agents").

**Addressing note (AGENTS.md rule 4):** the worktree's `HEAD` was `ab18d03`, not the named tip
`66e7244`. `git merge-base --is-ancestor` showed `ab18d03` is a strict ancestor of `66e7244` with a
clean tree, so per the rule I ran `git merge --ff-only 66e7244` rather than stopping. Verified
afterward: `git rev-parse HEAD` = `66e7244`.

---

### What actually runs automatically — established first, because it decides the whole review

Checked `.claude/settings.json`'s `PreToolUse`/`Bash` hook entries directly (not inferred from
comments) and cross-referenced with `grep` for cross-calls between the scripts:

| script | automatic? | trigger |
|---|---|---|
| `commit-quality-gate.sh` | **yes** | `PreToolUse`/Bash, gated by `jq -e '.command | test("...commit...")'` — fires only when the Bash command matches `git commit` |
| `push-roadmap-gate.sh` | **yes** | `PreToolUse`/Bash, gated by `startswith("git push")` |
| `graphify-dirty-flag.sh` | **yes** | installed as the repo's git `pre-commit` hook by `install-git-hooks.sh` — runs at the actual `git commit`, outside Claude Code's hook layer entirely |
| `roadmap-entry-consistency-gate.sh` | **no** | not referenced anywhere except its own "Run standalone" docstring and `docs/DOC_CONVENTIONS.md`. Not called from `commit-quality-gate.sh`, not in `settings.json`. |
| `roadmap-tag-vocabulary-gate.sh` | **no** | same — standalone only |
| `roadmap-toc.sh` | **no** | same — standalone only, takes an explicit directory argument |

**This is the single most important fact for this review**: the three new, entry-count-scaling
scripts do not run on any commit today. Whatever their asymptotic behavior, nobody waits for them
yet. The rest of this review measures them anyway, because the plan's own stated intent is to take
this repo-wide, and that is exactly the point in time an unmeasured scaling problem would stop being
hypothetical.

`commit-quality-gate.sh` and `push-roadmap-gate.sh` (the two that *do* run on every commit/push) were
read in full: neither iterates `*/ROADMAP/*.md` or any roadmap-entry list. Their cost is bounded by
the number of **touched subprojects** and **commits in the push range**, not by total roadmap entry
count. Confirmed by reading both scripts top to bottom — no action needed, this review does not
propose touching either.

---

### Method

A synthetic `ROADMAP/` tree was generated inside this worktree (a throwaway `synth-perf-test/`
subproject with a `pyproject.toml` so the gates' own discovery loop — `for d in */pyproject.toml`
— picks it up), sized at N = 22, 50, 100, 204, 400 entries, mirroring the real structure: one `# ID
-- text` H1 per file whose first token is the filename, one `#status/open` tag, one `[[ID]]` link to
another entry in the same directory, and one index file carrying every `[[ID]]` exactly once. The
real `audio-adapter/ROADMAP/` (22 entries) stayed in place throughout, adding a constant +22-entry
contribution to every measurement. `synth-perf-test/` was deleted (`find -delete`, not `rm -rf` —
blocked in this worktree) before the final commit; `git status --porcelain` confirms nothing of it
remains.

**Harness-can-fail probe, run before trusting any timing** (per this role's own standing rule —
memory: `feedback_benchmarks_must_be_able_to_fail.md`): a dangling `[[SX-9999]]` link was planted in
a generated entry and `roadmap-entry-consistency-gate.sh` correctly failed with exit 1 and named it;
an unlisted `#nonexistenttag` was planted and `roadmap-tag-vocabulary-gate.sh` correctly failed and
named it. Both harnesses can fail, and did, before any "OK" below is reported.

All timings: 3 trials per size, `python3 subprocess` wall-clock (`time.time()` around
`subprocess.run`), warm filesystem cache (first trial at a new size sometimes ~2x slower from cold
cache; reported figures are the stable trials).

---

### Findings

#### `roadmap-entry-consistency-gate.sh` scaling

- **Location:** per-directory loop, specifically Check 1 (`for target in $links; do ... grep -qxF
  "$target" <<< "$ids"`), which is structurally O(links × known-ids) — the shape this role exists to
  catch, since links and ids both grow with N.
- **Measurement** (total entries across both real + synthetic trees; time = mean of 3 trials):

  | N (synthetic) | total entries | time | time/entry |
  |---|---|---|---|
  | 22 | 44 | 0.77 s | 17.5 ms |
  | 50 | 72 | 1.22 s | 16.9 ms |
  | 100 | 122 | 2.10 s | 17.2 ms |
  | 204 | 226 | 3.94 s | 17.4 ms |
  | 400 | 422 | 7.43 s | 17.6 ms |

  time/entry is flat (17.4–17.6 ms) from N=22 through N=400 — **2x past the 204-file repo-wide
  target with no sign of the quadratic term dominating.** The per-file shell fork/exec cost
  (`basename`, `grep -m1`, `sed`, `awk` per file) is large enough that the O(n²) membership check is
  not yet the bottleneck at this scale. It would eventually show up at a much larger n than this
  project's roadmap will plausibly reach — not a credible risk here.
- **Risk:** none at repo scale. The gate is unused by any automatic hook today regardless.
- **Action:** MONITOR. No change needed now. If this script is ever wired into
  `commit-quality-gate.sh`, re-measure at the actual repo-wide entry count at that time, not before.

#### `roadmap-tag-vocabulary-gate.sh` scaling

- **Location:** per-file fence/tag scan; the known-tag lookup is bounded by `docs/TAGS.md`'s fixed
  vocabulary size, not N, so this was expected to be linear and measured as such.
- **Measurement:**

  | total entries | time | time/entry |
  |---|---|---|
  | 44 | ~0.4 s (extrapolated from scaling) | — |
  | 226 | 3.12 s | 13.8 ms |
  | 422 | 5.80 s | 13.7 ms |

  Flat time/entry, confirms linear. The round-3 fence-balance addition's claimed "~0.07s" marginal
  cost is not separately visible at this resolution but is consistent with the totals.
- **Risk:** none. Also unused by any automatic hook.
- **Action:** MONITOR.

#### `roadmap-toc.sh`

- **Measurement:** 204 entries → 2.69–2.71 s (~13.2 ms/entry), same linear shape as the tag gate
  (similar per-file work). Takes an explicit directory argument; never discovery-looped across the
  whole repo in one invocation.
- **Risk:** none — manual-only, one subproject at a time.
- **Action:** MONITOR.

#### Combined per-commit cost, if these were ever wired in

- **Risk:** this is the one number worth keeping on file for a future wiring decision. At the
  repo-wide target (204 entries total), if `roadmap-entry-consistency-gate.sh` +
  `roadmap-tag-vocabulary-gate.sh` were both added to `commit-quality-gate.sh`'s automatic path:
  204 × (17.4 ms + 13.8 ms) ≈ **6.4 s** added to every commit that touches a converted roadmap —
  and every commit that touches a converted roadmap is most commits in a doc-convention world,
  since roadmap edits are frequent. Add `roadmap-toc.sh` and it's ~9 s. That lands past the
  threshold the user named ("half a second is invisible, eight seconds gets disabled") —
  **not a reason to block this branch**, since nothing is wired in today, but a concrete number to
  weigh against convenience the next time someone proposes adding these to the automatic gate.
- **Action:** NOW, but scoped narrowly: **do not wire these three scripts into
  `commit-quality-gate.sh`'s automatic path without incremental scoping** (only the roadmap
  directories touched by the staged diff, not a full-repo scan) — the flat per-entry cost here is a
  property of scanning the *whole* directory every time, which is wasted work on every commit that
  touches one entry out of 204. This is a design note for whoever wires it in later, not a change
  this branch needs to make — nothing calls these scripts automatically yet, so there is nothing to
  fix on this branch.

#### Knowledge-graph corpus ceiling — the one finding that is NOW, not MONITOR

- **Location:** `.claude/scripts/graph-corpus-files.sh` (walks `*/ROADMAP/*.md` per subproject,
  added this branch) feeding `.claude/scripts/graph-corpus-guard.sh` (hard ceiling, default 200).
- **Measurement:** `graph-corpus-files.sh` itself is cheap — 0.08–0.46 s total (dominated by `find`,
  not per-file subprocess work like the gates above) — so its own runtime is a non-issue at any
  plausible scale.
- **Measurement — corpus size:** 198 files today (confirmed by running the script and counting
  non-empty lines), against the task's stated 173 before this conversion — **+25**, decomposed as
  +22 roadmap entries, +1 new index file, +2 new docs (`DOC_CONVENTIONS.md`, `TAGS.md`), consistent
  with one subproject's conversion.
- **Risk:** audio-adapter alone (22 entries) pushed the corpus from 173 to 198 — **2 files short of
  the 200 ceiling**, from converting *one of seven* subprojects. The task's own repo-wide target is
  204 entry files across 7 indexes. Projecting on the same per-subproject ratio this branch just
  measured: repo-wide conversion adds roughly +204 entries and +7 new index files to the corpus (old
  single `ROADMAP.md` files become 4-line pointers that still count as a file, so there's no
  meaningful offsetting removal). That lands the corpus somewhere around **400+ files — double the
  ceiling** — and `graph-corpus-guard.sh` is designed to **fail closed**: it refuses the rebuild
  outright with a clear message rather than silently degrading, which is the right failure mode
  but means **`/graph-refresh` stops working the moment enough subprojects convert**, with no
  warning before that threshold except the guard's own error text.
- **Action: NOW** — not to fix on this branch (one subproject converting is exactly the scale the
  guard still tolerates at 198/200), but this is a hand-off to whoever plans the repo-wide rollout:
  before converting more than one more subproject, either (a) raise the ceiling deliberately with a
  stated reason (the guard's own comment names this as the intended escape hatch), or (b) reconsider
  whether every per-entry file needs to be a separate graph-corpus node versus indexing each
  subproject's index file only — a design decision, not a performance fix, so flagged for the
  Architect rather than decided here.

#### Session Start read cost — the plan's central claim, confirmed

- **Measurement:** `audio-adapter/ROADMAP.md` at `dcd3aee` (pre-conversion): 42,058 bytes
  (≈10,515 tokens at ~4 bytes/token, matching the plan's own "~10.5k tokens" claim almost exactly).
  Post-conversion: pointer (445 B) + index (4,156 B) + one representative entry (1,335 B — measured
  as the median of all 22 entries' byte sizes, not an assumed "typical" size: entries range from 201
  B to 10,887 B, so median is the right summary, not mean) ≈ 5,936 bytes ≈ **~1,484 tokens**.
- **Result: confirmed, not refuted.** ~86% reduction (10,515 → 1,484 tokens) for the common case
  (read the index to find the next milestone, read one entry to work on it). The plan's claim holds.
- **Action:** none needed — this is the benefit the conversion is for, and it measures out as
  claimed.

---

### The question that decides something

**At 204 files, does any of this become the thing a developer disables?** No, for a reason more
important than any of the measurements above: **none of the entry-count-scaling scripts are wired
into anything that runs automatically today.** The per-commit automatic gates
(`commit-quality-gate.sh`, `push-roadmap-gate.sh`) are both independent of roadmap entry count by
construction (diff/subproject-scoped, not directory-scoped), and nothing currently calls the three
new scripts except a human or an agent typing the command by hand.

If and when someone *does* wire `roadmap-entry-consistency-gate.sh` and
`roadmap-tag-vocabulary-gate.sh` into the automatic commit path at repo-wide scale, the honest
number is **~6–9 s added per relevant commit** — past the threshold where a developer starts
reaching for `--no-verify`. The mitigation at that point is incremental scoping (check only the
roadmap directories the staged diff touches, not every directory every time), which this review
flags now so it isn't rediscovered the hard way later.

The knowledge-graph corpus ceiling is the one place where "safe at 204" is actually false today:
one subproject's conversion already used up 25 of the ~27 files of headroom the 200-ceiling guard
had left. That is a real, measured, NOW-relevance finding — but it blocks a *future* rollout step,
not this branch.

---

### Verdict

**APPROVED — MONITOR**, with one explicit hand-off: before converting a second subproject's
roadmap, resolve the knowledge-graph corpus ceiling (raise it deliberately, or change what counts
as a corpus node for split roadmaps) — flagged to whoever plans that rollout step, not blocking this
branch's merge. Everything else measured (`roadmap-entry-consistency-gate.sh`,
`roadmap-tag-vocabulary-gate.sh`, `roadmap-toc.sh`) is linear in practice up to 2x the stated
repo-wide target, unused by any automatic hook, and therefore safe to take to 204 files as-is.
