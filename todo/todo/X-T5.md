# X-T5 — Free text reaches the brain and comes back "Unable"

- [ ] **Free text reaches the brain and comes back "Unable, no such command."** #status/open User's words:
  *"'free text' is escalated to brain, but it comes back to 'unable, no such command'. While brain
  may work, we do not have sufficient command vocabulary -> no sensible speech from brain."*

  **This is the closed-set design working as specified, not a bug** — `brain-layer/src/decider.py`
  classifies against a fixed command vocabulary and returns `NO_SUCH_COMMAND` when nothing in it
  matches, and `speech.py` renders that as "Unable, no such command." So the ceiling is the
  vocabulary, exactly as the user diagnosed: the model can only ever say what the closed set lets
  it say, and a pilot speaking freely is mostly outside it.

  **DECIDED (user, 2026-09-28): let the brain answer questions about what he believes, without
  commanding anything.** Chosen over widening the command set or merely making the refusal honest.
  The tool API this needs already exists and has been frozen since [[BL-6]] (15 tools,
  `belief/tools.py`), and the brain already holds a body-side trust boundary that re-validates every
  model reply against body-owned data (D10) — so this is a new *intent class* through machinery
  that is built, not new machinery. Not started; read `plans/brain-layer/plan.md` D11 (the closed
  reason set) and D4 (contact reference resolution) before scoping, since a question about a
  contact has to resolve which contact it is about, and that resolver is the same one `follow` uses.

  Worth naming the boundary while scoping: a question answered from belief must be answerable
  *wrongly* when belief is wrong. "How many trucks?" gets the believed count, not the true one —
  the no-omniscience invariant applies to answers exactly as it applies to callouts.
