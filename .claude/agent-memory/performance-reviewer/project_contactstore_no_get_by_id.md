---
name: contactstore-no-get-by-id
description: ContactStore (body-layer) has no O(1) get-by-id; every caller resolves a contact by id with a linear scan over .contacts (a fresh list() of the backing dict each call) -- an established convention, not a per-plan risk, until contact counts or poll rate grow.
metadata:
  type: project
---

`body-layer/src/belief/contacts.py`'s `ContactStore` holds contacts in a dict keyed by id
(`self._contacts: dict[str, Contact]`) but exposes only a `contacts` property that returns
`list(self._contacts.values())` -- a fresh list, allocated on every access. There is no
`get_by_id`/dict-keyed accessor.

**Consequence:** every call site in this codebase that needs "the contact with this id" does
`next((c for c in store.contacts if c.id == target_id), None)` or an equivalent loop — one list
allocation plus an O(n) scan, n = live contact count. Confirmed call sites as of 2026-10-22:
`belief/tools.py:189`, `belief/tools.py:597/892/935`, `belief/utterance.py:204`, and
`logger.py:822-825` (added by BL-B80 v2's `look_contact` resolution in `run_once`).

**Why this is MONITOR, not NOW, for any one plan that adds another such call site**: this is this
project's established convention for contact-by-id lookup, not a pattern a given plan introduces.
Realistic contact counts (a single-aircraft engagement) are in the tens, and these lookups run at
poll rate (1-5 Hz), not per-frame — not a credible budget risk at current scale. Flagging it in one
plan's performance review while five pre-existing call sites keep the same pattern would only
relocate the cost class, not remove it.

**When this stops being MONITOR**: if `ContactStore` ever grows a `get_by_id` method (worth doing
once contact counts or poll rate materially increase, or once Petrobrain Runtime's real-time
budget phase begins — see root `CLAUDE.md`, "No hard real-time budget in this phase"), it should
replace all six-plus call sites in one pass, the same reasoning as
[[export-lua-per-frame-closures-are-established-pattern]] for Export.lua's redundant `GetDevice`
calls.
