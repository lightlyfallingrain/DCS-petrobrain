---
name: aa6-piper-http-server-default-bind-download-endpoint
description: piper.http_server defaults to 0.0.0.0 and exposes POST /download (fetches voices from the internet) alongside /synthesize -- AA-6 bound it to 127.0.0.1 explicitly; check this pattern on any future long-lived third-party server this project starts.
metadata:
  type: project
---

`piper-tts`'s own `piper.http_server` (used by `audio-adapter`'s `PiperEngine`, AA-6,
`plans/audio-adapter-os-independent/plan.md`) defaults to `--host 0.0.0.0` and exposes `POST
/download` (fetches arbitrary voice models from the internet into its `--data-dir`) alongside the
`/synthesize` endpoint actually needed. The investigator's recon
(`audio-adapter/research/2026-10-19-piper-cross-platform-recon.md`, 2026-10-20 addendum) flagged
this explicitly; `run-scripts/run-piper-mac.sh`/`run-piper-windows.sh` bind it to `127.0.0.1`
explicitly, verified in the Mode 2 deep analysis (`plans/audio-adapter-os-independent/
security-review.md`, approved, `eb06586b`).

**Why:** a third-party server process this project starts (not code this project wrote) can default
to a wider bind than intended and carry endpoints beyond the one feature that needed it to exist at
all. `audio-adapter`'s own `/speak` server is *meant* to be LAN-reachable (`--host 0.0.0.0` on
Windows so body-layer on the Mac can reach it) — Piper is not: it is a purely local synthesis
backend `audio-adapter` talks to over loopback, never meant to be reachable from the LAN, and its
own `/download` is a write-and-fetch endpoint with no auth.

**How to apply:** whenever a plan introduces a new long-lived external process this project starts
(the Ollama/`run-piper-*.sh`/`whisper-cli` shape — `AGENTS.md`'s "external long-lived tool process
precedent"), check what host/port it binds *by default*, not just what this project's run script
passes, and read its endpoint list for anything beyond the one call actually used. Don't assume a
tool's default bind matches this project's intent just because the project only calls one of its
endpoints.
