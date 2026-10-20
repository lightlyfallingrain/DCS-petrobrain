## Security Plan Review: audio-adapter-os-independent (AA-6)

**Retroactive.** This gate normally runs after Architect, before Implementer. On this feature it
was skipped: the branch went Architect → Implementer → Reviewer → Security (deep analysis,
`plans/audio-adapter-os-independent/security-review.md`, APPROVED, tip `eb06586b`) with no
plan-stage pass in between and no such commit in the branch history. Found by the DoD agent while
checking the feature before merge. Precedent for closing this kind of gap after the fact rather
than blocking merge on it: `276acbcf` ("Retroactive Security plan review: emitter-visibility —
APPROVED").

This reconstructs the plan-stage review against `plans/audio-adapter-os-independent/plan.md` as
approved (2026-10-20), `audio-adapter/ROADMAP/AA-6.md`, and
`audio-adapter/research/2026-10-19-piper-cross-platform-recon.md` (incl. its two 2026-10-20
addenda) — the inputs Architect actually had. The code is already implemented and merged on this
branch; it is cross-checked below only where useful, not re-reviewed (that is the deep-analysis
pass's job and it already ran).

### Dependencies Checked

- **`piper-tts` (`piper1-gpl`), GPL-3.0-or-later** — a new external tool, not a new package
  dependency of `audio-adapter` itself: `git diff main...feature/audio-adapter-os-independent --
  audio-adapter/pyproject.toml` is empty, confirming `dependencies = []` is unchanged. Installed in
  its own venv, run as `piper.http_server`, a separate long-lived process reached only over
  loopback HTTP (port 7800) — the same shape this project already uses for Ollama
  (`brain-layer/src/ollama_client.py`), and the plan's Decision 1 states this explicitly rather
  than assuming it. **CLEAN** — no CVE/GHSA advisory found for `piper-tts`/`piper1-gpl` itself
  (WebSearch: `piper-tts piper1-gpl CVE vulnerability`, `site:github.com/advisories piper-tts` —
  no relevant hits for either).
- **License note, not a vulnerability finding**: the maintained successor Piper moved to is
  GPL-3.0-or-later (the archived predecessor was MIT). Run as a separate process communicated with
  over HTTP, never linked into or imported by this project's own code, so this is a process
  boundary rather than a library-linkage one — the usual basis for copyleft not propagating to the
  caller. Flagging because this project has stated public-open-source intent (prior session
  context); worth a line in `audio-adapter/CLAUDE.md` or `LICENSE`-adjacent docs for a stranger
  cloning the repo, cheap to add, not acted on here since it is a licensing/distribution question
  for the user, not a security one. **Not filed as a backlog item** — out of this role's remit;
  surfaced for the user to decide whether it needs a doc line.
- **`onnxruntime`, a transitive dependency of `piper-tts` inside Piper's own venv** (not
  `audio-adapter`'s) — **ADVISORY: CVE-2026-14647, severity high (remote OOB read / potential RCE
  via a crafted `.onnx` model file, in the `onnx` format library's shape-inference code,
  `convPoolShapeInference_opset19`), affecting `onnx` through 1.21.x, fixed in 1.22.0.** Checked
  whether this plan's design makes that model-loading path reachable by anyone but the operator:
  it does not. The only inputs that reach Piper's model loader are (a) voice `.onnx` files the
  operator fetches by hand (`python -m piper.download_voices`, from HuggingFace, per the recon's
  Finding 4 and the plan's "Settled context"), and (b) Piper's own `POST /download` endpoint, which
  fetches voices from the internet into the data dir **and which the plan explicitly binds away**
  — Decision 1/Decision 5 both call out that `piper.http_server` defaults to `0.0.0.0` and exposes
  `/download`, and direct `run-piper-mac.sh`/`run-piper-windows.sh` to bind `127.0.0.1` explicitly
  for exactly this reason. `audio_adapter`'s own `PiperEngine` never calls `/download` and never
  lets a `/speak` caller influence which voice model loads (the `"voice"` field sent to Piper is
  always the operator-set `--piper-voice` CLI flag, confirmed in the later deep-analysis pass).
  **Not reachable under this plan's design** — no path from an untrusted `/speak` caller (or
  anyone on the LAN, given the loopback bind) to a malicious `.onnx` file being loaded. Same
  "trusted, loopback-only, same-machine peer" trust model the deep-analysis pass already applied to
  Piper generally. **Not filed as a backlog item, intentionally** — filing it would suggest there
  is an exploitable path reachable from this feature's own trust boundary, and there is not; if the
  project later adds any mechanism that lets `/speak`'s caller or the LAN influence which model
  file Piper loads, this advisory should be re-checked at that point, not before.

### Design Findings

1. **Bind-address decision (Decision 1, Decision 5) — correct, and correctly reasoned at plan
   time.** The plan identifies the exact risk (Piper's own server defaults to `0.0.0.0` and exposes
   an unauthenticated internet-fetch endpoint) before any code existed, and specifies the fix
   (`--host 127.0.0.1` on both `run-piper-mac.sh`/`run-piper-windows.sh`) rather than leaving it to
   be discovered during implementation. This is exactly what a plan-stage security pass exists to
   catch, already caught by Architect/the recon. No finding.
2. **Trust boundary between `audio-adapter` and Piper is narrow by design.** Decision 4 specifies
   that `--piper-url`/`--piper-voice` are operator-set CLI flags at process launch; nothing in the
   plan routes any field from an inbound `/speak` request body into the outbound Piper request
   beyond the text to synthesize. No SSRF-style redirection or model-selection injection path is
   introduced by this design. No finding.
3. **No preflight/health-check, lazy 503-on-failure (Decision 3)** — deliberately reuses this
   server's existing failure contract (`AircraftLayerAudioSink`, `WhisperCliEngine` already work
   this way) rather than adding new code to distinguish "Piper not started yet" from "Piper died."
   Not a security concern: a `503` carries no information disclosure, and the outage-announcement
   amendment explicitly bounds what gets logged (a non-200 body excerpt) rather than logging it
   unbounded — the plan's own wording ("Piper's own status and body excerpt instead of
   'unreachable'") does not specify a size cap in the plan text itself, which is worth naming as a
   plan-stage gap even though the implementation (confirmed in the deep-analysis pass, which did
   read the code) happened to bound it to 200 bytes. **Low-risk finding, not blocking**: a plan that
   says "log the body" without saying "bounded" leaves the bound to chance; it worked out here.
   Not filed as a backlog item — the code already does the right thing and the deep-analysis pass
   already confirmed it; a future plan asking a server to log an external peer's response body
   should say "bounded" explicitly, which is now recorded in this project's security agent memory
   as a general pattern to check (see memory note below), not something this one plan needs
   retroactively amended for.
4. **New long-lived local process, new port (7800)** — the plan catches its own near-miss here:
   the first draft picked 7800 as "next free after 7797," which was wrong (7800/7799 were already
   in use by `aircraft-layer`'s receivers on the Windows box), corrected at harvest per the plan's
   own annotation under Decision 4. The corrected value is confirmed unused elsewhere in the repo.
   No finding — the plan shows the check was actually done, not assumed.
5. **Machine-specific paths kept out of git** (Decision 5: `$PIPER_VENV_PYTHON`/`$PIPER_VOICES_DIR`
   go in `petrobrain.env`, not hardcoded in the committed run scripts) — correct call, avoids
   leaking a local filesystem layout or any machine-identifying path into the public repo. No
   finding.
6. **Windows local-playback sink (Decision 2)** — explicitly reuses an already-live-verified
   pattern (`aircraft-layer`'s `_WinsoundPlayer`) rather than inventing new Windows IPC/file
   handling; no new file-path-from-untrusted-input surface, since the plan's own code sketch writes
   to a process-local temp file, never a path derived from request content. No finding.
7. **No untrusted input, no new deserialization path, no new auth/access-control gap** introduced
   by this plan as a whole, assessed against the four standard questions this review asks: the one
   new data flow (text → Piper → WAV bytes) carries the same trust level the existing `say`-based
   path already had: operator-configured peer, LAN exposure limited to the pre-existing `/speak`
   surface this plan does not change (`server.py` is explicitly called out as unaffected, confirmed
   by Decision/"Affected Modules" and independently by the recon's Finding 6). This project's
   stated single-user/LAN-only, no-auth posture applies unchanged; nothing in this plan implies a
   need for auth that wasn't already implied by `/speak`'s existing design.

No finding above rises to "known unpatched CVE in a directly-exercised dependency" or "high-risk
design pattern without justification." Nothing here would have stopped Implementer from starting.

### Verdict

**APPROVED**

### Would this have changed the plan, had it run on time?

**No material change.** The one risk a plan-stage dependency check adds beyond what Architect's own
recon already surfaced — CVE-2026-14647 in `onnx`/`onnxruntime`, a transitive dependency two levels
removed from this subproject's own code — is not reachable under the design as specified, for the
same reason the deep-analysis pass already treats Piper generally as a trusted, loopback-only peer.
The bind-address decision this review would most want to confirm was already made correctly in the
plan itself, before implementation. The code-level gate
(`plans/audio-adapter-os-independent/security-review.md`, APPROVED, tip `eb06586b`) is the one that
matters for what actually shipped, and this retroactive pass reaches the same conclusion from the
plan side.

### Required Fixes

None.
