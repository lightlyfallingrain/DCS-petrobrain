---
name: feedback_monkeypatch_both_module_bindings
description: when reverting/monkeypatching a function for a control experiment, patch every module's own binding of it (the defining module's global AND every importer's `from x import f` copy), not just one
metadata:
  type: feedback
---

On `BL-B104`'s follow-up round (`plans/bl-b104-ground-contacts-on-ground/`,
review.md Findings 5/6), a control-experiment revert of
`belief.association_over_time.contact_growth_rate_mps` (to prove a test
actually discriminates fixed-vs-reverted gate behaviour) initially patched
only `belief.contacts.contact_growth_rate_mps` and `belief.attack_run.
contact_growth_rate_mps` (the two `from belief.association_over_time import
contact_growth_rate_mps` importers) and observed **no behaviour change at
all** — the real spatial gate (`association_over_time._contact_covariance`,
called from `passes_gate`, defined in the *same* module as the function
being patched) resolves the bare name `contact_growth_rate_mps` from its own
module's globals (`association_over_time.__dict__`), which is a *different*
dict from the importers' own namespaces. Patching `belief.contacts.
contact_growth_rate_mps = replacement` never reaches a call made from inside
`association_over_time.py` itself.

**Why**: `from x import f` binds a new name `f` in the importing module's
`__dict__`, pointing at the same function object at import time — but it is
a *separate* binding. `setattr(importer_module, "f", replacement)` only
updates the importer's copy; any call to `f(...)` written inside `x.py`
itself still looks up `f` in `x.__dict__`, unaffected.

**How to apply**: before trusting a monkeypatch-based control experiment
(revert a gate, patch a rate function, etc.), `grep` for every call site of
the function being patched, not just its import statements, and classify
each by which module's globals the call actually resolves against (the
module the call *is written in*, not the module exporting the function).
Patch **every** such module's own binding. A first botched attempt that
patches only the importers and sees "no behaviour change" is easy to
misread as "the revert doesn't matter" rather than "the revert didn't
apply" — verify by printing/asserting the patched function is actually
being called (or, as here, by eventually getting a `FAILED` result from the
intended-to-fail run) before concluding either way.

See also [[feedback_fold_fix_claim_needs_before_after_run_not_just_pass]]
(reviewer memory) — this is the specific mechanical trap that made an
earlier before/after check meaningless on its first attempt.
