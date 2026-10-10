# BR-1.1 — Brain layer, Stage 1 — first working slice

- [x] **BR-1 Stage 1 — Brain layer, first working slice: merged 2026-09-25 (merge `fc4e4af`,
  `feature/brain-layer`). Merged before flying, deliberately, so any correction the sortie
  produces lands on `main`; live acceptance remains outstanding.** #status/done #needs-flight body-layer's half of the first real seam to
  a new subproject, `brain-layer/` (see that subproject's own roadmap entry in root `ROADMAP.md`,
  Architecture and Status-table sections). A free-text utterance that used to produce silence now
  produces a real spoken response, end to end, over HTTP — with `StubDecider` (a configurable-
  delay stand-in) standing in for a model, proving the async wire (non-blocking handoff, stand-by-
  after-timeout, staleness revalidation, newest-wins at the job-slot level) with zero model risk.
  `body-layer/src/belief/brain_client.py` (`BrainLayerClient`, an independent `urllib`-based
  client, module-independence preserved — no import of `brain-layer/`), four new `belief.speech`
  templates (`render_unable`/`render_lost_contact`/`render_stand_by`/`render_disambiguation`), and
  `CrewConsole.drain_brain` (`--brain-client http|debug|null`, `http` requires `--brain-url`) are
  the body-layer surface. DoD verified 1220 passed/4 xfailed (body-layer) and 20 passed
  (brain-layer) against an isolated `git archive` of the branch tip, plus a live spot-check
  against a running `python -m brain_layer` process. Security's one recommended fix (`run-brain.sh`
  defaulting to `--host 0.0.0.0`, exposing `POST /escalate` to the LAN with no offsetting benefit
  in the current same-machine deployment) is applied — loopback is now the default, with the
  choice framed as a deployment fact (only `aircraft-layer` is pinned to a machine; every other
  seam here is HTTP precisely so it can move) rather than a hardcoded property of the service.
  **Two Stage 2 prerequisites measured during the perf pass, recorded not fixed** (unreachable
  under `StubDecider`, armed once Stage 2 adds a real model):
  `poll_replies()`'s 5 s poll-thread timeout (a wedged brain would cost ~83% tick loss at the 1 s
  default poll interval), and `Decider.decide()` having no bounded timeout (one unjoined daemon
  thread per `/escalate`). D10's semantic reply validator is deliberately absent — Stage 1's wire
  is structured JSON from plain code, so there is nothing yet for a validator to guard against.
  **Live acceptance outstanding** — card at `docs/acceptance/2026-09-25-crew-behaviour-sortie.md`
  block 4 (the Stage-1-only card it superseded is
  `docs/acceptance/2026-09-25-brain-layer-stage1-sortie.md`);
  with no real model behind the wire, the only judgeable things are whether the cockpit stays
  responsive while the brain "thinks," whether stand-by timing lands right, and whether hearing
  Petrovich answer at all (instead of silence) feels right.

