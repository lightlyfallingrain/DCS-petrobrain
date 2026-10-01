---
name: bl-b23-memory-vs-clustering-filter-pattern
description: How to check a "filter input to an O(n^2) consumer" perf fix doesn't become a memory/false-absence defect on this project
metadata:
  type: project
---

Pattern worth re-running whenever a future perf fix filters what `ContactStore.tick` hands to a
downstream consumer (grouping, salience, reporting — anything cross-contact): check two things
independently of whatever the Reviewer already wrote, because a Reviewer approval note can be
inherited uncritically otherwise.

1. **Does the unfiltered store (`ContactStore.contacts` / `_contacts`) stay untouched?** The
   filtered list must be local to the one computation that needed narrowing (here, a comprehension
   passed inline to `GroupStore.reconcile`), never a reassignment of `_contacts` itself or anything
   `describe_contact`/`get_contact_history`/crew-console/speech read from. Trace those call sites by
   hand (`belief/tools.py`'s `_find_contact` → `store.contacts`) rather than trusting a docstring's
   claim.
2. **Does the consumer's silence-on-shrink already avoid a false "departed/destroyed" claim, or
   does the fix need to add that silence itself?** `GroupStore.reconcile` already fires no event on
   membership loss, and `speech.py`'s delta taxonomy already defers to the member's own lifecycle
   event. If a future consumer does NOT already have this property, filtering its input is exactly
   the kind of change that could put a false "gone" statement in Petrovich's mouth — check for an
   explicit silent/deferred branch before approving.

See [[project_bl_b23_contact_store_pruning_security_approved]] for the specific instance this
pattern was extracted from.
