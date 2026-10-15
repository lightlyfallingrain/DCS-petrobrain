---
name: feedback_verify_the_rendered_artifact_not_the_source_comment
description: when a fix claims to make a generator render something into a committed output file (e.g. config/defaults.toml from #: comments), read the rendered file itself, not just the source diff -- a correct-looking source edit can still fail to reach the output
metadata:
  type: feedback
---

X-T26 (`plans/configurable-constants/`) fix pass 2 added three pilot-facing sentences to `#:`
comment blocks in `body-layer/src/perception/visibility.py`, intending them to reach
`config/defaults.toml` (the file the user's own brief named directly). The source diff looked
complete and correct. It was not: the sentences were the *second* sentence of each block, and
`generate_defaults.py`'s `_first_sentence()` only ever renders the first, so none of the three
sentences ever reached the file. The Reviewer and Security passes that approved fix pass 2 both
read the source comments and neither re-read the generated `config/defaults.toml` itself -- a
file-list check (both files "changed") looked complete while the mechanism that was supposed to
move information between them silently didn't.

**Why:** a diff against source prose reviews intent; it does not review effect when a generation
step sits between the edit and the artifact a human (here, the pilot) actually reads. The same
root cause this project's standing "grep for the new mechanism's own call site" rule exists for
(see this role's persistent-memory preamble, the `perturbed_bearing_range` worked example) --
except here the "call site" to check is a build step's actual output, not another source file.

**How to apply:** whenever a fix's claimed effect is "this now appears in `<generated file>`,"
open that generated file after the fix (or ask the implementer to paste the regenerated section,
then verify it against the file on disk yourself) rather than trusting that a correct-looking
source edit implies a correct render. Re-run the generator if it's cheap to do so
(`tools/generate_defaults.py --write` here) and diff the regenerated file against what's committed
to catch "forgot to regenerate" as a separate failure mode from "regenerated but still wrong."
Caught on X-T26 fix pass 3 by reading `config/defaults.toml` lines 83/88/91 directly instead of
re-reading `visibility.py`'s comments.
