# BL-B21 — More frequent glances at a watched contact

- [ ] **BL-B21 — More frequent glances at a watched contact — Decision 1's third point,
  `plans/sortie-2026-09-26-fixes/decisions.md`, 2026-09-26.** #status/open The user's own framing: the durable
  fix for a watched contact staying observable is Petrovich looking at it often enough to keep the
  knowledge fresh (and learn more about it), not a longer grace window — `CALLOUT_OBSERVABILITY_
  GRACE_S` (`sortie-2026-09-26-fixes` Fix A) only covers a brief occlusion, deliberately, and must
  not be tuned as a substitute for this. The user places this under **attention-grabbing
  behaviour, which does not exist yet** in this codebase — no plan or milestone currently owns it.
  Once it exists, revisit whether `CALLOUT_OBSERVABILITY_GRACE_S` still needs to be as long as it
  is, since attention-grabbing is what is meant to make the grace window rarely matter in practice.
