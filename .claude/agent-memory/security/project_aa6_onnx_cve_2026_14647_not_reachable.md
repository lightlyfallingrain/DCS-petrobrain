---
name: aa6-onnx-cve-2026-14647-not-reachable
description: CVE-2026-14647 (onnx library OOB read/RCE via crafted .onnx model, fixed 1.22.0) exists in piper-tts's transitive onnxruntime dependency for AA-6 but is not reachable -- voice models are operator-fetched and Piper's own /download endpoint is bound away; re-check if either changes
metadata:
  type: project
---

`piper-tts` (used by `audio-adapter`'s `PiperEngine`, AA-6,
`plans/audio-adapter-os-independent/plan.md`) pulls in `onnxruntime` inside Piper's own venv (not
`audio-adapter`'s — `audio-adapter/pyproject.toml` has zero dependencies, unchanged by this
feature). `onnxruntime`'s `onnx` transitive dependency has a real, high-severity advisory,
CVE-2026-14647: an out-of-bounds read (OOB read / potential RCE class) in
`convPoolShapeInference_opset19`'s shape-inference code, triggered by loading a crafted `.onnx`
model file, affecting `onnx` through 1.21.x, fixed in 1.22.0.

**Assessed as not reachable in this project's design, not filed as a backlog item.** The only
inputs that reach Piper's model loader are (a) voice `.onnx` files the operator fetches by hand
(`python -m piper.download_voices`, from HuggingFace) and (b) Piper's own `POST /download`
endpoint — which the AA-6 plan explicitly binds away (`run-piper-mac.sh`/`run-piper-windows.sh` use
`--host 127.0.0.1` specifically because `piper.http_server` defaults to `0.0.0.0` and exposes
`/download`; see `[[aa6-piper-http-server-default-bind-download-endpoint]]`). `audio_adapter`'s own
`PiperEngine` never calls `/download` and never lets a `/speak` caller influence which voice model
loads — the `"voice"` field sent to Piper is always the operator-set `--piper-voice` CLI flag.

**Why this is worth a memory entry rather than just a line in the plan review**: the natural
instinct on finding a CVE in a transitive dependency is to treat the *package* as the unit of risk
("is `onnx`/`onnxruntime` patched"). The right unit here is the *data path* — whether anything
reachable by an attacker can get a crafted `.onnx` file loaded. A future audit of this subsystem
should re-check reachability, not just re-check the installed `onnx`/`onnxruntime` version, and
should re-open this if either of the two facts above changes: (1) anything starts calling Piper's
`/download` endpoint, or (2) the `"voice"` field (or any other value that selects which model file
loads) ever becomes influenceable by an inbound `/speak` request or anything reachable over the
LAN.

**How to apply:** when a CVE is found in a dependency that loads untrusted-format files (model
files, fonts, images, archives), ask "what controls which file gets loaded here" before asking
"is the installed version patched" — the version question matters only if the file-selection
question says yes.
