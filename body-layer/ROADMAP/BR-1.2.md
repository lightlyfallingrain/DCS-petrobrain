# BR-1.2 — Brain layer, Stage 2 — OllamaDecider

- [x] **BR-1 Stage 2 — `OllamaDecider`, a real local model behind the wire. DoD PASSED and
  merged 2026-09-25 (`4bc0df9`, from `feature/brain-layer-stage2`); unflown.** #status/done #needs-flight Replaces Stage 1's
  `StubDecider` with a real `qwen3:4b-instruct-2507-q4_K_M` call over `brain-layer/src/
  ollama_client.py`, the classify/discriminate prompt pair (`brain-layer/src/prompts.py`), and a
  new body-side D10 trust boundary (`body-layer/src/belief/brain_reply.py`) that re-validates every
  `PICK`/`CONFIRM`/`ASK`/`UNABLE` the model returns against body-owned data before anything is
  acted on or spoken — a model output can never invent a contact id or a command outside what body
  itself offered. Also lands the two non-blocking prerequisites the performance review required
  before a real model could safely sit behind the wire (`poll_replies()` off the shared poll
  thread; `Decider.decide()` under its own bounded timeout), both measured as discharged. **This
  milestone was implemented twice, independently, by two unaware sessions** — this branch and
  `feature/br1-stage2` — and folded per user direction; the episode and what was/wasn't taken is
  recorded in `plans/brain-layer/implementation.md`'s "Folding in the duplicate branch" section.
  Reviewer APPROVED across all three passes (Stage 2 proper, the fold, and the Security/Performance
  change-request fold — one required fix, addressed and taken further: an AST-based sync test now
  enforces the two mirrored vocabulary constants instead of relying on a comment). Security
  APPROVED (one recommended fix taken — the `_validate_confirm` offered-vocabulary asymmetry; one
  recommended fix explicitly deferred — no byte cap on `response.read()`, reachable only via
  operator misconfiguration of `--ollama-url`). Performance APPROVED — MONITOR: Ollama serializes
  generation, so one slow reply can chain-drop several *subsequent*, unrelated utterances, not just
  its own — reasoned from transport measurements plus D6's 32.7 s worst-case generation figure,
  never observed live. DoD gate: both subprojects' full command sets re-run from a fresh worktree
  checkout (brain-layer 45 passed, body-layer 1292 passed/4 xfailed, ruff and `mypy --strict` clean
  in both) — matching every prior role's claimed counts. **Nothing in this feature has ever talked
  to a real model** — the sandbox every agent on this branch ran in has no route to
  `127.0.0.1:11434`, so all verification (including the fold's own regression tests) ran against a
  fake HTTP server or, for the DoD gate's own live spot-check, `StubDecider` again (proving the
  live-check tool's wire mechanics, not a real model's output). **Live acceptance outstanding** —
  card at `docs/acceptance/2026-09-25-brain-layer-stage2-sortie.md`, published as its own artifact
  (https://claude.ai/artifact/VPYm5D44Z98kuEk3ErwbD1) since it needs Ollama running with the model
  pulled in addition to the usual three-process setup, a real branch checkout rather than `main`,
  and is the first flight where the pilot hears the model's own language rather than a canned
  reply. Does this change what the next milestone should be? Yes, in one respect: Stage 3's A/B
  answer leg and the D10 structured-candidate revision (`feature/d10-structured-candidates`) both
  build on the discriminate prompt's `BECAUSE` evidence, and this stage's live sortie is the first
  chance to learn whether the 7-token, no-slot `CLASSIFY_COMMAND_VOCABULARY` (deliberately narrowed
  from an alternative ~43-token version the folded-in branch had built) under-serves real
  utterances before either downstream piece is built further. This entry flips to `[x]`/merged on
  merge, per the roadmap-discipline rule below.

