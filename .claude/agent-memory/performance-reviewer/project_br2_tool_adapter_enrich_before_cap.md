---
name: br2-tool-adapter-enrich-before-cap
description: belief.tool_api's find_contact/get_contacts brain-tool adapters enrich every filtered/matched contact before capping to 5 for display — same root cause as report_query_enrichment_dominates, but exposed by a model's own tool-calling judgement rather than an explicit "report everything".
metadata:
  type: project
---

Measured 2026-11-13 on the BR-2 (brain tool calls) Stages 0-3 performance review
(`plans/brain-tool-calls/performance-review.md`). `belief.tool_api._find_contact_adapter`/
`_list_contacts_adapter` call `tools.find_contact`/`tools.get_contacts`, which run full
`_contact_result` (enrichment: `semantic_facts_for`/`describe_position`, never-cached
`terrain_divide_qualifier`) on **every** contact the filter/search admits — confirmed by real-code
call counting with the `test_callouts.py`/`test_tools.py` `describe_position` monkeypatch fixture
(mechanism only; see [[project_synthetic_store_calibration]] on why a synthetic store cannot give
the real absolute cost). `_cap(..., BRAIN_TOOL_LIST_CAP=5)` runs *after*, on the enriched result —
it discards the work on everything past 5, it does not avoid doing it.

**Same root cause [[project_report_query_enrichment_dominates]] already found on `crew-query-path`
(2026-10-10), filed MONITOR + Architect escalation there** because a fix was entangled with
`report`'s own shared slot-filtering/position-rendering logic. **This path has no such
entanglement** — `tool_api.py`'s two adapters are BR-2's own new code, not a shared tool several
features already depend on in different ways, so a narrower fix (an optional `limit` param on
`tools.find_contact`/`get_contacts`, applied before enrichment, `None` default preserving every
existing caller including `report_all` unchanged) is available here without waiting on that older
escalation's bigger redesign.

**What's actually new here, worth remembering as a pattern:** the risk magnitude is the same
mechanism as before (63-137 ms mean / 228-498 ms p95 per contact across three on-file real-SQLite
measurements — see [[project_report_query_enrichment_dominates]] and
[[project_bl11_measured_outcome]] for the numbers), but the *exposure* changes when a cost
previously reachable only by an explicit, rare player command becomes reachable by a model's own
tool-calling judgement on every addressed utterance. **When reviewing any brain/LLM-tool-calling
feature that wraps an existing `belief.tools`/`belief.enrichment` function, check whether the
wrapped function already has a known full-dataset-before-cap cost** — the fix may be cheap even
when the underlying cost center is old and already deferred, because the new caller is often a
narrower, unentangled surface the old escalation never had the option of using.

Related: [[project_enrichment_cache_axes]] (why `WorldEnrichmentCache`'s 50 m grid cannot close
this — it fixes across-poll staleness per contact, not across-contact bulk cost within one call),
[[project_bl11_measured_outcome]] (confirms this exact mechanism already causes ~2% of ordinary
polls to overrun 1.0 s before any brain-driven call exists).
