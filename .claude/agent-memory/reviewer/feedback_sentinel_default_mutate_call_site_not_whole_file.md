---
name: feedback_sentinel_default_mutate_call_site_not_whole_file
description: When verifying a None-sentinel-default fix (production default swapped from a bare function to None, with a branch that builds an expensive/batching resource), mutate only the call-site dispatch back to the old function -- not the whole module -- so the new mechanism's own direct test stays meaningful as a control.
metadata:
  type: feedback
---

Used on `raster-chart-viewer` RC-1's performance-fix review (2026-11-16, Findings 1-2 from
`performance-review.md`, commit `32df4b38`). The fix (see also the implementer's own
`[[reference_none_sentinel_default_for_call_scoped_resource_reuse]]` memory) was: change an
injectable callable parameter's default from `discovery.read_tile_bytes` to `None`, and branch
inside the caller -- `None` means "open a fresh call-scoped `BatchZipReader`", a caller-supplied
value is used exactly as given. Three new tests existed: one testing `BatchZipReader` directly, two
testing that the *production default path* (left at `None`, no override) actually uses it.

**First instinct was to revert the whole file to its pre-fix commit** (`git show <prev-sha>:path >
path`) to "show the red." That's wrong for this shape of fix: it also deletes `BatchZipReader`
itself, so the two production-default tests fail with `ImportError: cannot import name
'batch_tile_reader'` rather than with the assertion failure (`64 == 1`) they're actually meant to
demonstrate -- a `None`-sentinel review's earlier task note already warned that this kind of
default "cannot quietly fall back to the slow path," and an `ImportError` proves nothing about
that; it just proves the mechanism doesn't exist yet, which was never in question.

**The useful mutation targets only the call-site dispatch** -- replace just the `if read_bytes is
not None: ... else: <use batch_tile_reader()>` branch's `else` arm with a direct call to the old
unbatched function, leaving the new class/function fully intact elsewhere in the file. Then:
- The two production-default tests fail for the *right* reason (open count 64/8, not 1) --
  demonstrating the default genuinely wires to the new mechanism rather than merely existing
  somewhere in the module.
- The test of the new mechanism in isolation (`BatchZipReader`/`batch_tile_reader` called
  directly, bypassing the default) stays green -- confirming it's a different test actually
  pinning a different thing, not three tests that all happen to exercise the same line.

**How to apply**: before reverting a whole file to "show the red" on a sentinel-default fix, check
whether the fix's new mechanism (the class/function the `None` branch calls) is defined in the same
file as the call site. If so, scalpel out only the dispatch line(s), not the file, or the control
test (the one exercising the new mechanism directly) loses its ability to tell "mechanism broken"
apart from "mechanism not wired to the default" -- which is exactly the distinction a sentinel-
default fix needs verified. Always restore and `sha256sum`-confirm byte-identical after, same as any
other mutation check.
