---
name: plan-stage-log-unbounded-response-body
description: a plan that says "log the peer's error body" without saying "bounded" leaves the bound to chance -- ask for it explicitly at plan-review time, not just at deep-analysis time
metadata:
  type: feedback
---

AA-6's plan (Decision 3's amendment, `plans/audio-adapter-os-independent/plan.md`) specifies
logging a non-200 peer response's "status and body excerpt" on an outage, but the plan text itself
never says the excerpt must be size-bounded. The implementation happened to bound it to 200 bytes
(`tts_engine.py`), confirmed correct by the deep-analysis pass — but that was luck, not something
the plan required, and this gap wasn't caught until this retroactive plan review was written after
the code already shipped.

**Why:** "log the body" is exactly the kind of instruction that becomes "log the body, in full,
indefinitely" by default once an implementer is moving fast — the `Content-Length`/unbounded-read
pattern this role already watches for on the *request-handling* side of a server
(`docs/PROCESS.md`'s running list of real findings: "an unbounded Content-Length") has a mirror
image on the *logging* side: a noisy or malicious peer's error response, logged in full, is a
log-file DoS or a secret-leak vector depending on what the peer puts in its error body. A plan
review that only checks "is there a dependency, is there untrusted input" misses this because the
peer here is nominally trusted (loopback-only) — the risk is about the *logging sink*, not the
network boundary.

**How to apply:** at Mode 1 (plan review), whenever a plan has any server or client log an external
peer's response body/error text, check that the plan's own wording says "bounded" (a byte cap, a
line cap) rather than just "log it" or "log the body." If the plan is silent, note it as a
low-risk, non-blocking finding and move on — don't block the plan on it, but say it, so an
implementer reading the plan (not just this review) sees the expectation stated rather than
inferring it.
