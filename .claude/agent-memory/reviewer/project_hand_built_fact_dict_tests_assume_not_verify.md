---
name: hand-built-fact-dict-tests-assume-not-verify
description: body-layer speech tests that hand-build a dict (e.g. a SemanticFact-shaped {"text":..., "feature_id":...}) verify only that the consumer function handles that shape correctly -- they do not verify the producer actually emits that shape. Check both ends by mutation.
metadata:
  type: project
---

Found on `landmark-words-no-names` (F7, 2026-10-20), reviewing `belief/enrichment.py` →
`belief/speech.py`'s `_landmark_speech_text`.

**The pattern:** `enrichment.py`'s `semantic_facts_for` builds a `SemanticFact.feature_id` string
with an encoded format (e.g. `f"water:{label}:{name}"`). `speech.py`'s consumer
(`_landmark_speech_text`) is tested with hand-built fact dicts that assert the *consumer* parses a
given `feature_id` string correctly (`{"feature_id": "water:a river:Orontes", ...}` →
`"near a river"`). That test passes whether or not `enrichment.py` actually produces strings in
that shape — it only proves the parser is right about an input the test author typed in by hand.

**Why this matters:** for three of this plan's kinds (`settlement`'s "near" case was covered by a
pre-existing end-to-end fixture, "Jableh"), nothing connected producer to consumer. Verified by
mutation: swapping the segment order in `enrichment.py`'s actual `feature_id` construction (for
`water` and `inside_settlement`) passed the **entire** body-layer test suite with zero failures.
The bug would ship silently — every unit test for both ends stays green.

**How to apply:** when reviewing a change that adds or changes an encoded string contract between
two modules (here, `feature_id`'s colon-separated segments), don't accept "each end has its own
unit tests" as coverage. Check for at least one test that exercises the *real* producer function
and feeds its *actual* output into the real consumer (an end-to-end fixture, not two isolated
unit tests that happen to agree by construction). If none exists, mutate the producer's string
construction (reorder/rename a segment) and run the full suite — a clean pass with the mutation in
place is the tell.

This generalizes beyond `feature_id`: any encoded-string or dict-shape contract between a producer
and a consumer in different modules/files is at risk the same way, especially in this codebase's
test style, where `_FakeInfo`-shaped stand-ins and hand-built fact dicts are the norm rather than a
shared fixture module (see `.claude/agent-memory/implementer/feedback_describe_position_fake_
fixtures.md` for the sibling finding on the producer side — missing fields on fake fixtures,
rather than wrong-but-self-consistent formats).

See `plans/landmark-words-no-names/review.md` for the three concrete gaps found this way.
