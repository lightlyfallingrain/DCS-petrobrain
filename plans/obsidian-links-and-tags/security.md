## Security Deep Analysis: doc-conventions-audio-adapter (obsidian-links-and-tags)

**Branch:** `feature/doc-conventions-audio-adapter`, verified tip `66e7244`
(fast-forwarded into this worktree from `ab18d03` per AGENTS.md rule 4 — strict
ancestor, clean tree, confirmed with `git merge-base --is-ancestor`).
Diff base `dcd3aee`.

### Dependency Status

No dependency change. `git diff --stat dcd3aee 66e7244 -- audio-adapter/src
aircraft-layer/src body-layer/src world-model/src` is empty — no application
source changed in this feature. The entire diff is shell scripts, hooks, and
markdown (a ROADMAP split into per-entry files plus two new gates and a TOC
helper).

### What runs automatically vs. by hand

This distinction drives every severity rating below.

| script | trigger | automatic? |
|---|---|---|
| `status-page-refresh.sh` | `/status-page` skill, or by hand; intended launchd job is **not installed** (confirmed by the script's own header comment and unchanged by this feature) | manual |
| `commit-quality-gate.sh` | `.claude/settings.json` PreToolUse on `Bash`, conditional on the command matching `git commit` | automatic (every commit) |
| `push-roadmap-gate.sh` | `.claude/settings.json` PreToolUse on `Bash`, conditional on `git push` | automatic (every push) |
| `graphify-dirty-flag.sh` | installed as a **git `pre-commit` hook** by `install-git-hooks.sh` | automatic (every commit, if hooks installed) |
| `graph-corpus-files.sh` | invoked by `/graph-refresh` and by `graph-corpus-guard.sh`'s error message; not itself hooked | manual (via skill) |
| `session-start.sh` | `.claude/settings.json` UserPromptSubmit | automatic (every prompt) — this feature only changed the reminder string, no behavior |
| `roadmap-entry-consistency-gate.sh` | none — header says "Run standalone"; not referenced by any other script or `.claude/settings.json` entry (checked by grep) | **manual only** |
| `roadmap-tag-vocabulary-gate.sh` | same — "Run standalone", not wired anywhere | **manual only** |
| `roadmap-toc.sh` | same — a query helper, not a gate, not wired anywhere | **manual only** |

So the two new consistency/vocabulary gates — the most elaborate new code in
this feature — are not reachable from any hook today. They are also the
ones most worth reviewing for injection, since a future wiring into
`commit-quality-gate.sh` is plausible and would make them automatic without a
second security pass if nobody re-checks that wiring.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `status-page-refresh.sh` (whole file) | subprocess exec of `claude -p` with repo markdown as indirect input, `--permission-mode acceptEdits` | `GEN_PROMPT`/`PUB_PROMPT` are single-quoted literals — no shell interpolation of repo content into the prompt or into any `git`/`claude` argument. `$PAGE` is a hardcoded constant (`docs/status/petrobrain-status.html`), never derived from input, so `git checkout -- "$PAGE"` cannot escape to another path. Theoretical: a malicious ROADMAP entry could attempt prompt injection against the generation step to make it write outside `docs/status/` — but any resulting `Edit`/`Write`/`Bash` call from that sub-invocation still passes through this same repo's `.claude/settings.json` hooks (`agent-memory-path-gate.sh`, `destructive-command-gate.sh`, `commit-quality-gate.sh`), so the blast radius is bounded by the same gates a human session has. Manual-trigger only; launchd job confirmed not installed. | None. False-positive-adjacent: reported as a low-probability theoretical with existing mitigation, not a gap. |
| `roadmap-entry-consistency-gate.sh`, `roadmap-tag-vocabulary-gate.sh`, `roadmap-toc.sh` | filenames/IDs used in `find`, `basename`, glob expansion, and as `grep -F` targets | All three constrain IDs to `^[A-Z]+-[A-Za-z0-9.]+$` before using them as `$target`/`$id` in any loop, which excludes `/`, `..`, whitespace, and shell metacharacters — no path traversal or word-splitting hazard from a crafted ID. `find "$dir" -maxdepth 1` bounds discovery to one directory per subproject, never recurses outside it. No `eval`, no unquoted expansion feeding a command (only feeding `grep -qxF`/`grep -qF`, which treat input literally). | None. |
| `roadmap-tag-vocabulary-gate.sh` / `roadmap-toc.sh` — fence-balance check | both fail loudly (`FAIL=1`, non-zero exit) on an odd fence-delimiter count rather than silently scanning past an unterminated fence | This is itself a security-relevant fix already in this diff (round-2 review finding) — confirms the project's own "stops gating silently" failure class was caught and closed here, not introduced. | None — noting as a correctly-closed case, not a new finding. |
| `commit-quality-gate.sh`, `push-roadmap-gate.sh`, `graphify-dirty-flag.sh`, `graph-corpus-files.sh` — regex widenings | each diff adds an alternative inside an existing `grep -E` group (`ROADMAP\.md` → `ROADMAP(\.md\|/[^/]+\.md)`, etc.) | Checked each as **additive-only**: every pattern the regex matched before this diff still matches after it (verified by inspection — old alternative is preserved verbatim, new one is OR'd in). None of the four narrows a match, so none of these gates silently stopped catching something it used to catch — the specific failure mode this pass was asked to weight most heavily. | None. |
| `.gitignore` + `.obsidian/` untracking (`ac6f008`) | 12 files (892K, two plugin `main.js` blobs) untracked going forward | Read every one of the six JSON config files and both plugin manifests at their last-tracked revision (`git show ac6f008^:<path>`). Contents: UI layout state with randomly-generated pane ids, boolean feature toggles, plugin manifest metadata (author, funding URLs). **No tokens, no API keys, no absolute filesystem paths, no username/hostname, no sync credentials** — `"sync": true` in `core-plugins.json` is only a UI panel toggle, not a credential. Nothing sensitive found. | None — consistent with the task's "known-open, not findings" note that the blobs remain in history; no rewrite needed because there is nothing in them to redact. |
| `docs/DOC_CONVENTIONS.md` — Front Matter Title plugin | documents installing a third-party Obsidian community plugin | Reader-side **display-only** plugin (renders frontmatter as explorer/graph/search titles); not a build or runtime dependency of any subproject (`grep` across `pyproject.toml`/`package.json` confirms absence), not invoked by any script in this repo, and the doc itself states graceful degradation with no plugin installed (bare IDs instead of titles). The vault also carries **Templater** (community plugin capable of running user-defined JS/shell via its automation features) — but `docs/DOC_CONVENTIONS.md` does not document, require, or instruct installing it, so this feature creates no obligation around it. No supply-chain action attaches to either: nothing in the pipeline trusts, executes, or ships their code. | None. Worth a one-line note if `Templater` is ever formally adopted into the convention (it is currently just present in the committed-then-untracked vault state, not endorsed) — not a finding against this feature. |

### Verdict
APPROVED

### Required Fixes (if any)
None.

---

**Summary for the automatic-vs-manual question asked explicitly:** the only
scripts in this feature's diff that run without a human or an agent choosing
to run them are the regex widenings inside three pre-existing automatic
gates/hooks (`commit-quality-gate.sh` on every commit, `push-roadmap-gate.sh`
on every push, `graphify-dirty-flag.sh` as an installed git `pre-commit`
hook) — each checked additive-only, so no automatic gate lost coverage. The
new, more elaborate logic (the two consistency/vocabulary gates and the TOC
helper) is manual-only today, and `status-page-refresh.sh`'s `claude -p`
calls are gated behind an unintalled launchd job, so in practice also
manual. Nothing in this feature introduces an unattended, attacker-reachable
execution path.
