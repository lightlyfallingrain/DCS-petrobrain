---
name: sortie-1005-review-fixes
description: Grouped-contact suppression of watched-only callouts — a review's named helper would have reintroduced the cost it fixes, and a CalloutScheduler.tick test needs multiple ticks or it passes with the fix disabled
metadata:
  type: project
---

Two review change requests on `feature/sortie-refinements`, both applied. Three things worth
keeping.

## A review can name the right *concept* and the wrong *function*

The performance review's fix said to use "the leading contact `group_membership_state` already
computes". That function routes through `_group_member_facts`, i.e. **one `describe_contact` per
member** — which is exactly the ~51 ms `describe_position` call the finding exists to remove, and
it would have been called from the filter whose cost was the problem. Net effect would have been
O(members) describes to save O(2 × members).

**Why:** `_leading_index` needs only `Contact.classification`, so the leader is computable with
zero describes. The guard that made the describe-based version look necessary — "does this member
still resolve" — is satisfiable with `ContactStore.contact`, because `describe_contact` returns
`None` under *precisely* that condition (verified by reading it, not assumed).

**How to apply:** when a review names a helper to reuse, check what that helper *costs* before
reusing it, especially in a performance fix. The concept ("the group's leading contact") was right
and worth sharing via `_leading_index`; the entry point was not.

## A `CalloutScheduler.tick` suppression test passes with the fix disabled unless it ticks several times

`tick` speaks **at most one line per call**. So:
- one tick asserts nothing about suppressing N−1 peers;
- a later tick far enough out to be past `busy_until_sim` is also past `CALLOUT_MAX_AGE_S` (10 s),
  so the peers *expire* rather than being suppressed — same observable, different cause.

The teeth are in several ticks each past the previous line's `busy_until_sim` and **all** inside
`CALLOUT_MAX_AGE_S`. My first version used `now_sim=1.0` then `60.0` and passed with the
suppression forced false. Caught only by the revert-and-confirm pass.

**How to apply:** any test of what `tick` *does not* say needs the window asserted explicitly
(`assert all(last_tick - e.t_sim < CALLOUT_MAX_AGE_S ...)`), and needs the revert check. Related:
[[feedback_revert_test_scratch_copy]] — the revert was done on a scratch copy of the module, never
`git checkout --`.

## `_WATCHED_ONLY_KINDS`' docstring already answered the product question both reviews raised

The performance review flagged "does the surviving line become 'the group is moving'?" as needing a
product call. The constant's own docstring had already decided the opposite, years of context
attached: these kinds render through `_contact_report_text`'s `event_clause`/`lead` affixes, which
`render_group_disclosure` has no concept of, "so folding one into a group's own line would silently
drop the very fact the event exists to report."

**Why:** the suppression therefore fixes the *cardinality* (N lines → 1) while the line's wording
still names one member. That is a real residual, not a complete answer to "one line for the group".

**How to apply:** before implementing a reviewer-flagged product question, read the docstring of
the constant or function it concerns — this project writes decisions there, and two reviews missed
one that was three lines above the code they cited. See also
[[feedback_dont_improvise_scope_to_satisfy_plan_framing]]: the right move was to implement the
specified ~6 lines, record the tension in the docstring, and flag it, not to build group-level
templates.

## Incidental

`body-layer` has no `.venv` inside an agent worktree. The main checkout's
`body-layer/.venv/bin/python -m pytest` run with cwd *inside the worktree's* `body-layer/` resolves
correctly — pytest's rootdir comes from cwd, so `pyproject.toml`'s `pythonpath` points at the
worktree's own `src`. Verified by printing `belief.crew_console.__file__` rather than assuming
(the trap in `AGENTS.md` rule 4).
