---
name: main-doc-describes-unmerged-branch-behaviour
description: A skill/doc on main can document behaviour that only exists on an unmerged branch; verify a card's runtime claims against the branch being flown, not against main's docs.
metadata:
  type: project
---

**A document committed on `main` can describe behaviour that exists only on an unmerged feature
branch, and an acceptance card that trusts it will send the user looking for files that are not
there.** Found 2026-10-06 while writing the card for `fix/callout-observability-gate`:
`.claude/skills/sortie-log-triage/SKILL.md` (commit `6d819de`, on `main`) states that the three
sortie logs are run-stamped `dcs-speech-<stamp>.jsonl` "since 2026-10-06" and tells the reader to
glob for the newest. The stamping is `BL-11` Stage 5 and lives on `feature/bl11-tick-cost`, which
is **not merged** — nothing in `body-layer/src` on `main` or on the branch being flown writes a
timestamp into a log path, so all three logs still append to the plain accumulating files.

**Why it happens here:** this project commits cross-cutting skill/config edits directly on `main`
(root `CLAUDE.md`'s Workflow section, deliberately, to keep feature-branch history clean) while the
code they describe lands later by merge. That is the right rule and this is its predictable cost.

**How to apply:** for any runtime fact a card asserts — a filename, a flag, a default, a port —
check it against the **branch the user will check out**, not against `main`'s documentation. The
cheap check is a `grep` in `<subproject>/src` for the mechanism (here: `strftime`/`%Y%m%d`/`stamp`),
not a read of the doc that claims it. Then say in the card which branch the claim is true of. Same
family as [[feedback_verify_roadmap_prose_claims]] — a plausible-reading prose claim about a code
artifact, taken on trust.
