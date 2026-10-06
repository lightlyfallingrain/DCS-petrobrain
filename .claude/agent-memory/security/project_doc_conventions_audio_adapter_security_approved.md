---
name: doc-conventions-audio-adapter-security-approved
description: Deep analysis of the obsidian-links-and-tags/doc-conventions feature (roadmap split, two new gates, untracked .obsidian) -- APPROVED, no fixes.
metadata:
  type: project
---

Feature on `feature/doc-conventions-audio-adapter` (tip `66e7244`) changed no application source
(`audio-adapter/src` etc. all empty in the diff) -- the whole surface was shell scripts/hooks and
markdown. Checked and cleared:

- **`status-page-refresh.sh`**: `claude -p` prompts are single-quoted literals, no shell
  interpolation of repo content; `$PAGE` is a hardcoded constant so `git checkout -- "$PAGE"`
  cannot be redirected. Manual-trigger only (intended launchd job confirmed still not installed).
  Any prompt-injection attempt from a malicious roadmap entry during generation still has to pass
  through this same repo's own PreToolUse hooks (agent-memory-path-gate, destructive-command-gate,
  commit-quality-gate) on whatever Edit/Write/Bash the sub-invocation tries -- bounded blast
  radius, not a gap.
- **`roadmap-entry-consistency-gate.sh` / `roadmap-tag-vocabulary-gate.sh` / `roadmap-toc.sh`**
  (new): all constrain IDs to `^[A-Z]+-[A-Za-z0-9.]+$` before using them in any loop/grep --
  excludes `/`, `..`, whitespace, shell metacharacters. `find -maxdepth 1` bounds discovery to one
  dir. No eval, no unquoted expansion feeding a command. **Not wired into any hook or
  `.claude/settings.json` entry -- run standalone, by hand, per their own header comments.** If
  these are ever wired into `commit-quality-gate.sh` (making them automatic on every commit),
  re-review, since that changes the reachability calculus.
- **Regex widenings in 4 pre-existing automatic gates** (`commit-quality-gate.sh`,
  `push-roadmap-gate.sh` -- both PreToolUse-hooked on git commit/push; `graphify-dirty-flag.sh` --
  installed git pre-commit hook; `graph-corpus-files.sh` -- manual via `/graph-refresh`): each
  diff only OR's in a new alternative (`ROADMAP\.md` -> `ROADMAP(\.md|/[^/]+\.md)`); verified by
  inspection that the old alternative is preserved verbatim in every case, so none of these
  silently *stopped* matching something it used to catch -- the specific failure class this pass
  was told to weight most heavily turned out not to apply here.
- **`.obsidian/` untracked, 12 files, 892K, 2 plugin `main.js` blobs remain in git history**
  (commit `ac6f008`). Read every JSON config + manifest at last-tracked revision
  (`git show ac6f008^:<path>`): UI layout state with random pane ids, boolean feature toggles,
  plugin manifest metadata. No tokens, no API keys, no absolute paths, no username/hostname.
  `"sync": true` in core-plugins.json is a UI toggle, not a credential. Nothing to redact, so no
  rewrite is owed even though this project intends to go public eventually.
- **Front Matter Title plugin** (documented in `docs/DOC_CONVENTIONS.md`): reader-side
  display-only community plugin, not a build/runtime dependency of any subproject, not invoked by
  any script. Graceful degradation with no plugin installed is stated in the doc itself. No
  supply-chain obligation created. Templater (also present in the vault, capable of running
  user-defined automation) is **not** documented or required by the convention -- present but not
  endorsed, so out of scope for this feature's review.

Verdict: APPROVED, no required fixes. Full report: `plans/obsidian-links-and-tags/security.md`.
