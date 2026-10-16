# BR-B3 — The Ollama response body is read without a byte cap

- [ ] **BR-B3 — `brain-layer/src/ollama_client.py:81` calls `response.read()` with no size limit, so
  a runaway or malfunctioning model runtime can be read into memory unbounded.** #status/open

  **This item exists because a recommendation was never filed.** It is verbatim the Stage 2 security
  review's own **Finding 2** (`plans/brain-layer/security-review.md`, 2026-09-25) — written down as
  a recommendation, never turned into a backlog item, and therefore sitting in prose for three
  weeks where nothing would ever schedule it. The 2026-10-16 whole-subproject survey
  (`brain-layer/research/2026-10-16-security-audit.md`) re-checked its probability/impact reasoning
  and found nothing to revise.

  **That is the transferable finding, and it is about process rather than bytes**: a per-feature
  review's recommendation is not tracked work unless somebody files it. `X-B8`/`X-B9`'s own framing
  — *findings to a document, and that document becomes a backlog item* — is the rule this slipped
  past.

  **Scope**: the trust boundary is a local model runtime the pilot started, so this is robustness
  against a broken or wedged Ollama rather than defence against an attacker. A cap plus a clean
  error beats an OOM in a process whose founding constraint is that it must never block anything.

  Related: `[[BR-B2]]`, `[[BR-1.2]]`.
