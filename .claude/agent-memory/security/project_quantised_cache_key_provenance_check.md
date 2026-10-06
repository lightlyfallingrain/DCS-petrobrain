---
name: quantised-cache-key-provenance-check
description: How to clear a quantised/memoised cache key of a provenance charge in two checks — key identity and error direction; worked on BL-11 Stage 3b and the profile_for @cache
metadata:
  type: project
---

Two caching changes landed in `BL-11` (2026-10-06) and both looked like no-omniscience risks until
traced. The **two checks that settle it** generalise to every future cache on this project:

**1. Key identity — can one subject's result be served for another?**
`WorldEnrichmentCache` is keyed on `contact.id`, and `ContactStore._new_contact_id`
(`belief/contacts.py:1440`) is a **monotonic counter, never reused within a process**. That single
fact is what makes 50 m position quantisation provenance-safe: cross-contact attribution is the
only way quantisation could put a fact on something it was not computed for, and an unrecycled key
forecloses it. **If a future cache is keyed on anything recyclable (object_id from DCS, an
observation id, a slot index), this check fails and the finding is real.**

**2. Error direction — does the staleness make him better or worse informed?**
Quantisation makes the cached position *coarser/staler* (≤70.7 m horizontal, ≤86.6 m 3D inside a
50 m cell). Omniscience is the invariant; staleness is the **opposite** failure and cannot
manufacture knowledge of an unobserved thing. So a coarsening cache is not a no-omniscience
finding, however much it looks like one. A cache that *sharpened* a value, or that survived across
a contact's loss and re-acquisition, would be.

**For a memo on a string key (`@cache` on `perception.object_model.profile_for`), the question is
narrower: who can drive the key space?** Trace every assignment, not every call site — here all
seven `classification_raw=` assignments originate in a perception source, so **no transcript, no
voice-command text and no brain/Ollama output reaches it.** That was the vector worth ruling out:
a microphone- or LLM-fed key space on an unbounded `functools.cache` *is* a memory-growth
primitive and would change the verdict. The residual (aircraft-layer LAN API supplies the strings)
is not worth defending — an actor there already owns perception entirely.

Same branch, the other half of that review:
[[project_cli_path_mkdir_degrade_policy_misses_valueerror]].
