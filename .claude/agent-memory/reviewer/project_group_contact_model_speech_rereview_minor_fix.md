---
name: group-contact-model-speech-rereview-minor-fix
description: Re-review of feature/group-contact-speech's 3 post-approval commits (couple-of, attention-earned exact counts, speak_samples.py) — APPROVED WITH MINOR FIXES.
metadata:
  type: project
---

Re-reviewed `feature/group-contact-speech` commits `2e80dcd`/`66a856d`/`023c591` (added after the
6b7cdec approval in [[project_group_contact_model_stage4b_approved]]). Verdict: APPROVED WITH
MINOR FIXES.

Hand-verified (not just trusted the tests): the `attended and lo==hi` branch sits after the
singular guard so `attended=True` never adds a clause to (1,1); an inexact interval always hedges
regardless of `attended` (honesty condition genuinely holds); the 12-cap correctly falls through
to "several" (13-15) vs "many" (16+) rather than a numeral; `facts.get("attention") in ("watch",
"priority")` matches the real `Attention` literal and the real `"attention"` key writers in
`tools.py`.

**Only required fix**: a brand-new dev tool's own docstring usage command didn't work as written
— `body-layer/tools/speak_samples.py` said `PYTHONPATH=src python3 ...`, but actually needs
`PYTHONPATH=src:../world-model/src .venv/bin/python ...` (the world-model seam + pyproj
dependency, per `body-layer/CLAUDE.md`'s own documented failure mode for the live logger). Caught
only by actually running the command exactly as documented, not by reading it.

**Pattern worth repeating**: for any new dev-tool/acceptance-aid file with a usage docstring,
literally run the documented command(s) rather than trust that they "look right" — the seam
requirements (PYTHONPATH, venv interpreter) in this repo are non-obvious and easy for a docstring
to get wrong even when the code itself is correct.
