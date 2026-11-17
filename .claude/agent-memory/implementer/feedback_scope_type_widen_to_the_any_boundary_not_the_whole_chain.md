---
name: scope-type-widen-to-the-any-boundary-not-the-whole-chain
description: when a security/review fix asks you to widen one function's slot/field type to admit a new value shape, check whether the value is Any-typed at the point it enters mypy-checked code before cascading the widening down a shared-parameter call chain
type: feedback
---

BL-17's Required Fix 1 (`plans/speech-rules/security-stage3-4.md`) asked to widen
`body-layer/src/body.py`'s `_poll_transcripts` slot-value filter from `isinstance(value, (int,
str))` to also admit a bounded dict (a union slot's tagged table, `set_speed`'s `speed_target`).
The naive approach is to widen the type everywhere the value flows: `handle_transcript` ->
`_act_on_voice_decision` -> `handle_command` -> `_handle_rule` -> `_dispatch_rule` -> `rule_runner`
Callable -> `rules.engine.run_rule`. That cascades badly here: `handle_command`'s `slots` param is
*shared* by ~10 unrelated token handlers (`_handle_follow`, `_handle_select_target`,
`_handle_where_is_it`, ...) that never see a dict value in practice but declare the same narrow
type -- widening `handle_command`'s signature forces widening all of them too, and transitively
their own dataclass fields (`PendingPointRequest.slots`, etc.), for zero behavioural gain.

**Check first whether the value is already `Any`-typed at the point it crosses into the
mypy-checked chain.** Here `AudioAdapterClient.get_transcripts() -> tuple[list[dict[str, Any]],
...]` means `item.get("slots")` is `Any`, so assigning it to a *locally declared*,
narrowly-typed variable (`slots: dict[str, int | str] | None = None; slots = slots_raw`) was
*already* unchecked by mypy before this fix and stays unchecked after -- no `cast` needed, no
downstream signature touched. The fix was then scoped entirely to the one function that performs
the runtime validation (new `_is_bounded_slot_dict`/`_is_valid_slot_value` helpers in `body.py`),
while every typed signature downstream (`crew_console.py`, `rules/engine.py`) is left exactly as
it was -- the real invariant (no dict value ever reaches a non-rule handler) is enforced by the
token-based branching in `handle_command`, not by the type system, and that was already true
before this change.

**How to apply**: before widening a type across a call chain to satisfy a review's request, trace
where the real runtime value is actually statically typed as something narrower than `Any`. If
every hop up to the review's own target function is `Any` (a JSON/wire boundary, a `dict[str,
Any]`), the widening is local and the type-checker was never actually verifying the invariant you
are "fixing" anyway -- confirm with a quick baseline `mypy src` before and after, as evidence
rather than assumption. If a hop genuinely narrows the type (a dataclass field with a concrete
annotation, not `Any`), *that* is the point widening is unavoidable, and it should stop there
rather than being carried further than necessary.
