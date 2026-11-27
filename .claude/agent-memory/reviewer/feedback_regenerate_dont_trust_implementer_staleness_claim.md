---
name: regenerate-dont-trust-implementer-staleness-claim
description: When a generated config/doc file (switch-reference.md, triggers.md, defaults.toml) is touched, actually re-run its generator and diff, don't trust the implementation note's "regenerated, clean" claim
metadata:
  type: feedback
---

On BL-16 M4 (SAU channel handover, `03b67fcb`), the implementation note claimed
`switch-reference.md` and `triggers.md` were "regenerated (`tools/render_switch_reference.py
--write`)" and `defaults.toml` was correctly left unchanged. Both claims turned out true, but I
verified them myself by re-running `tools/render_switch_reference.py --write` and
`tools/render_triggers.py --write` inside the review worktree and checking `git status` showed no
diff, rather than accepting the implementer's own report of having done so.

**Why this matters:** this project's own staleness defect history (root `CLAUDE.md`'s tuning
section — "figures 4x too high, a sentence that never rendered, a backtick span that ate a space")
was caught *only* by someone regenerating and reading the output, never by reading the diff or the
implementer's claim. A generated file's own diff in the commit looks identical whether it was
produced by the generator or hand-edited to match it — the only way to tell is to run the
generator yourself.

**How to apply:** whenever a commit touches a generated file (anything with a `tools/render_*.py
--write` or `tools/generate_*.py --write` step in the implementation note, or named in a
`test_render_*.py`/`test_*_defaults_toml.py` staleness test), re-run that exact generator inside
the review worktree and confirm `git status --short <path>` is empty afterward. Costs one command;
the alternative is trusting a claim this project has specifically learned not to trust.

See also [[feedback_verify_effector_registry_against_raw_dump]] — same review, same spirit: verify
the derived artifact against its source rather than against the account of it.
