---
name: feedback_verify_the_mechanism_a_comment_claims_not_just_the_behaviour
description: A fix's code comment/docstring can describe the wrong mechanism (e.g. "Lua's single most-recent-command slot") while the behaviour change itself is correct and safe — check the claimed mechanism against the actual code, separately from checking the behaviour.
metadata:
  type: feedback
---

**Found in `plans/flight-control/review-handover-ack.md`'s Re-review (2026-11-20, BL-16 mode 1,
commit `9bf10861`).** The Required Fix itself (move the ack-timeout's self-queued release onto
its own `flight_control_system_release_pending` field, send it alone, defer any same-poll player
transition one poll) was correct, well-tested, and verified by mutation. But the docstring
justifying *why* it defers rather than sends both messages back-to-back claimed "Lua's own single
most-recent-command slot" — i.e. that Export.lua only ever acts on the latest UDP datagram and an
earlier one is overwritten/lost. That is simply false: `Petrobrain/commands.lua`'s
`poll_command_socket` drains *every* queued datagram per frame in a `while true do
command_socket:receivefrom() ... end` loop and dispatches each one through its own handler in
receipt order — there is no slot, no overwrite. The real (and still legitimate) risk is UDP
datagram *reordering* between two separate back-to-back sends on an unordered transport, not a
single-slot mechanism. The chosen fix (defer) was still the right call either way, so this was
not a behavioural defect — but a future reader who trusts the fabricated mechanism in the
docstring could reason incorrectly about this code the next time it is touched.

**How to apply**: when a fix's comment states *why* in terms of a specific mechanism in another
file/language (a queue, a buffer, a protocol guarantee, a DCS internals claim), read that
mechanism's actual code before accepting the comment — don't just verify that the resulting
behaviour change is correct. The two are separable failures: a correct fix can carry an incorrect
"why," and the "why" is what the next person touching the code will trust. This is the project's
own "Read every 'X, so Y' docstring as two claims" habit (`reviewer.md`'s mutation-testing
section), applied to a comment about a *sibling-file wire mechanism* rather than a docstring
about the same function's own logic — worth checking even when the review brief explicitly asks
you to verify the specific claim, since that is exactly what happened here and it did turn out
false.

See also [[feedback_one_shot_transition_field_clobber_window]] (the original defect this fix
closes).
