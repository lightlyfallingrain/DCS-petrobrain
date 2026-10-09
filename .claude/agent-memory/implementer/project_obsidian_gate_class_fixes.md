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

### Round 2 (2026-10-06): the fix for #2 and #3 each introduced a new defect of its own

Both were caught by the Reviewer's own re-mutation, not by re-reading the diff — see
[[feedback_guard_every_statement_not_the_one_that_raised]], which this is a direct instance of.

4. **A state-machine toggle (the fence `awk` from #2) has no end-of-file concept.** An unclosed
   fence leaves `fence` true for the rest of the file, silently disabling the scan it was added to
   protect — a *false negative*, strictly worse than the false positives it replaced, because a
   clean exit now means "nothing to see" instead of "I looked and found nothing." Fix: count fence
   delimiters per file (`grep -cE '^[[:space:]]*```'`) before stripping; an odd count fails loudly
   rather than degrading silently. Apply to every consumer of the shared toggle, not just the one
   under review (there were two here, a gate and a TOC helper).
5. **The mechanical check from #3 (the `FORWARD_COUNT` grep) only tested its own true/false
   arithmetic — never the consequence of the script's own guard on the false branch.** Exiting
   non-zero after already having written the file left it modified+uncommitted, and the script's
   *own* "working tree dirty → SKIP" guard then silently skips every future run forever. The lesson
   generalizes past this one script: when a new guard's failure path leaves a side effect behind,
   check what the *rest of the same script* does with that side effect before calling the guard
   done — and enumerate every exit path reachable after the side effect happens, not only the one
   path a review happened to probe (there were four such paths here; the review found one).
