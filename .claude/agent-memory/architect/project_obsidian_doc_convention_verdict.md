---
name: obsidian-doc-convention-verdict
description: The per-entry-roadmap/wikilink/tag spike verdict (2026-10-06) — the three measurements that decided it, and the premise that turned out false
metadata:
  type: project
---

Verdict on the `obsidian-test` spike (per-entry roadmap files, `[[wikilinks]]`, `docs/TAGS.md`):
**adopt partially — audio-adapter + `body-layer/ROADMAP.md` + its BACKLOG; leave root
`ROADMAP.md`, aircraft-layer, mission-interpreter and `todo/backlog.md` alone.** Plan at
`plans/obsidian-links-and-tags/plan.md`.

**Why:** Three measurements, all cheap, all of which changed the shape of the answer — and two of
which contradicted the spike's own write-up.

- **The benefit is in two files, not the repo.** Measured tokens: `body-layer/ROADMAP.md` 46.5k
  (67 entries, **130 commits in 30 days** — highest-churn doc in the repo), its BACKLOG 24.7k,
  world-model 29.2k. The three *small* roadmaps together are 9.4k (6.5%) / 33 entries. Converting
  them creates files and indexes that can go stale and saves a read nobody notices.
- **The spike's founding premise is false for body-layer.** *"Every entry has a stable ID"* —
  **45 of 67** body-layer entries have no ID; they are named by branch
  (`fix/contact-report-flood`) and are mostly transient live-acceptance debt. World-model: 27 of
  42. Converting means minting ~72 permanent IDs under the never-renumber rule, for items that
  will be gone in weeks. Recommended out: filename = ID when there is one, **branch name** when
  there is not.
- **The graph benefit is already delivered.** The extractor **already** makes 185 nodes / 264
  edges from the roadmap+backlog files, including per-entry nodes (`AC-B3 — Split The Export
  Throttle`). "One node per entry instead of one giant node" is wrong. Real gain is narrower:
  closes a 13-entry gap in body-layer (54 nodes from 67 entries) and points `source_file` at a
  700-token entry instead of a 46.5k file, which is what `gq.sh`'s source list hands an agent.

**How to apply:** when a document-layout or convention change is proposed, the cost is not the
split — it is the consumers. Sweep `.claude/scripts/`, `.claude/skills/`, `.claude/agents/`,
root + subproject `CLAUDE.md`. Classify each hit by **whether its failure is loud or silent**,
not by whether the fix is hard. Here: `graphify-dirty-flag.sh` and `graph-corpus-files.sh` fail
**silently** (one-line fixes, highest value); `push-roadmap-gate.sh` and `commit-quality-gate.sh`
fail **loudly in the safe direction**. And six skills that mention `ROADMAP.md` were **not**
consumers at all — they read root `ROADMAP.md`'s status table for the subproject list only, and
root stays whole.

See [[verify-state-not-the-account-of-it]], [[find-n-in-the-repo-before-accepting-n-is-more-than-we-need]].
