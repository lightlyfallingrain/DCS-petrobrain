# BL-4 — Attention and events (= PB-4)

- [x] **BL-4 — Attention and events (= PB-4, done, merged 2026-09-10, `546fa93`).** #status/done
  `feature/bl4-attention-events`. Four-state `Attention` (`ignore`/`normal`/`watch`/`priority`,
  `belief/attention.py`), `AttentionArea` (center + radius + optional sector) with `area_contains`,
  `effective_attention` (direct mark vs. area membership, `ignore` always wins), a
  `CONTACT_ATTENTION_CHANGED` event wired into `ContactStore.tick` with a 15 s per-contact-per-kind
  cooldown independent of classification's own contradiction lockout. New tools:
  `set_attention`/`watch_area`/`unwatch_area`/`get_attention_state`/`list_events`
  (aliases `poll_events`)/`acknowledge_event`; seven new console commands. 333 tests (291→333),
  Reviewer approved zero required fixes across six independently cross-checked design claims.
  Console/replay-only scope — live-DCS acceptance deliberately deferred, bundled with BL-5's
  transport layer per the plan. Design note worth knowing: `effective_attention` stores *effective*
  (not direct) attention in `last_emitted_attention`, so a contact walking into/out of a watched
  area fires an event even with no change to its own direct mark — deliberate, flagged as
  reversible in the plan. Full history: `plans/bl4-attention-events/`.


**Live-acceptance debt closure note, folded in from the roadmap's former debt list:**

- [x] **BL-4's attention/events tools — CLOSED 2026-09-21 as tested and good enough** (user
  direction). `set_attention`/`watch_area`/`get_attention_state`/`list_events`/`acknowledge_event`.
  Live acceptance had been deferred as "bundled with BL-5's transport layer", and this entry existed
  because it was unclear whether BL-5's own sortie had exercised these tools at all rather than just
  `place`/`position`/`situation`.

  **Closed on the user's judgement from flying it, not on a fresh acceptance run.** That is the
  right call for a debt of this shape: the question was never "is it correct" — the code is tested —
  but "has anyone watched it work", and the person doing the watching has now flown it enough to
  say. Recorded as user judgement rather than as a passed acceptance test so the distinction stays
  visible.

