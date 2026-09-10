---
name: project_bl4_attention_events
description: BL-4 attention-states/area-attention/event-queue milestone -- what got built, non-obvious split-commit technique, and one design deviation from the plan's literal wording.
metadata:
  type: project
---

BL-4 (`plans/bl4-attention-events/plan.md`) built on `feature/bl4-attention-events`, 3 commits,
333 tests passing (baseline 291 + 42 new). All three commits individually verified (format/lint/
mypy strict/pytest) by using `git stash push --keep-index` to isolate each commit's state before
committing, then `git stash pop` to restore the rest -- useful pattern when a single editing pass
produced a cohesive diff that needs to land as staged, independently-green commits rather than
one giant one. For commit 2 vs 3 (event-kind+cooldown vs event-queue), the queue code
(`ContactStore.unacknowledged_events`/`acknowledge_event`, `tools.list_events`/
`acknowledge_event`, console `events`/`ack`) was cleanly appended/removable since it lived in
its own new functions at file-ends, not interleaved with existing logic -- stripped it out via
Edit, committed the rest, then re-added the exact same text back in for the final commit.

Key design point not spelled out verbatim in the plan: `effective_attention`'s pure signature
had to take primitives (`Attention`, `GeoPosition`, `Sequence[AttentionArea]`), not a `Contact`,
because `belief.attention` is imported by `belief.contacts` -- a `Contact`-typed parameter would
be a circular import. The plan's prose ("`effective_attention(contact, areas, now_sim)`") was
descriptive, not a literal signature; `now_sim` was dropped too since nothing in the area model
is time-dependent (no area TTL exists in this milestone).

`Contact.last_emitted_attention` stores *effective* attention (not the raw direct mark) -- this
is what makes a contact walking into/out of a watched area (with no change to its own direct
mark) fire `CONTACT_ATTENTION_CHANGED` on its own, which is real, intended behavior, not a bug.
It changed the existing BL-2 scripted-console-session acceptance test's event count from 2 to 3
(a watch/unwatch round-trip now genuinely produces an attention-changed event) -- updating that
assertion was in-scope, not a test being loosened.

`console.py`'s `attention <id>` (no level arg) queries `tools.get_attention_state`; `attention
<id> <level>` sets it via `set_attention` -- same command name, argument-count dispatch. This
was needed to satisfy the existing structural test (`test_console_module_contains_no_belief_
logic`) that asserts every public `tools.py` function is referenced somewhere in `console.py`.

EVENT_COOLDOWN_S picked as 15.0s (provisional, undocumented-elsewhere guess, same status as
IDENTITY_HALF_LIFE_S before live tuning) -- shorter than classification.py's 30s contradiction
lockout since it's a different mechanism (event *emission* suppression vs. belief-state
re-promotion suppression); see events.py's module docstring for the full distinction, which the
plan explicitly flagged as easy to conflate.
