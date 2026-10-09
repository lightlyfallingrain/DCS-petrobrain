# BL-B35 — Unbounded `response.read()` on peer HTTP calls

- [ ] **BL-B35 — Unbounded `response.read()` on all seven peer HTTP calls.** #status/open 2026-10-05 security
  audit. A peer (aircraft-layer, audio-adapter, brain-layer) that returns an enormous body puts it
  straight into memory on the poll thread. Fix-when-public rather than fix-now: every peer is on
  the LAN and ours. One `Content-Length` check and a cap.
