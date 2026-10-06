---
name: project_obsidian_gate_class_fixes
description: Obsidian doc-convention review fixes — exactly-one-index check, code/URL stripping before tag scan, mechanical R1 check
metadata:
  type: project
---

Three review-fix patterns from `feature/doc-conventions-audio-adapter`
(`plans/obsidian-links-and-tags/review.md`):

1. **"At least one" vs "exactly one" index link** — a bash check that sets a 0/1 found-flag and
   breaks on first match cannot detect duplicates. Fix: count matches, fail on both 0 and >1.
   Invisible at a single-index shape; live the moment a second index shares the directory.
2. **Tag/anchor false positives are a class, not instances** — `#word` regexes scanning raw
   markdown will keep finding new false positives (inline code spans, URL fragments, text inside
   fenced code blocks) as prose grows. Fix the class once: `awk` fence-toggle to drop fenced
   blocks, then `sed -E 's/`[^`]*`//g'` for inline code, then `sed -E 's#https?://[^][:space:])"'\''>]*##g'`
   for URLs, piped before the tag grep. Apply identically everywhere the same regex is duplicated
   (a gate and a TOC helper both had it here).
3. **A prompt instruction inside a `claude -p` call is not a mechanical check**, however explicit
   ("assert X before publishing") — it cannot be mutation-tested without a live LLM call, and its
   reliability is exactly the run's instruction-following. Fix: split the subprocess call into
   generate-only, then a real `grep`/count over the file it produced, then a second subprocess
   call for publish/commit — gated on the grep passing. The grep-based check itself needs no LLM
   and is fully mutation-testable by stubbing the generated file directly.

See [[verify_full_suite_not_just_new_files]] and [[feedback_implementation_log_append]] for related
verification habits on this project.
