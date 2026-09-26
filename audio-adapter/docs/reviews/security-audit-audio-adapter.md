# Security Full-Subproject Audit: audio-adapter

Mode 3 (on-demand whole-subproject scan), branch `main` HEAD `bd28563`. Scope:
`audio-adapter/src/`, `audio-adapter/tools/`, `audio-adapter/pyproject.toml`.

Threat model this audit rates against (per root `CLAUDE.md` and the user's framing): single-player,
single-user, LAN-only, under active development, but **intended to be published open source** —
so a defect that is low-severity for this user's own LAN can still be a defect the moment a
stranger runs the published defaults.

## Summary

No exploitable vulnerability found that reaches real harm from real input under this threat
model. `say`/`afplay`/`sox`/`whisper-cli` are all invoked as argv lists — no `shell=True` anywhere
in `src/` or `tools/` (grepped). All outbound HTTP clients carry explicit timeouts. Temp files use
`tempfile.mkstemp` (atomic, non-predictable, mode 0600) and are removed in `finally` blocks.
Dependencies are genuinely stdlib-only (`pyproject.toml`'s `dependencies = []` confirmed against
every import in `src/`/`tools/`) — no third-party supply chain surface at all. Recorded audio and
transcripts never reach a log file or disk outside explicit, gitignored corpus tooling
(`data/corpus/`, `.gitignore` line 8-12) — mic-derived text is not logged anywhere in `server.py`.

## REQUIRED FIXES

None.

## RECOMMENDED

1. **No request-body size cap on `POST /speak` / `POST /transcribe` / `POST /stop`.**
   `src/server.py:138` and `:190` — `length = int(self.headers.get("Content-Length", "0") or "0")`
   followed by `self.rfile.read(length)`, with no upper bound. A client that sends a very large
   `Content-Length` and an equally large body forces the handler to buffer the whole thing in
   memory before any validation runs (JSON parse, base64 decode). On `--host 0.0.0.0` (which
   `CLAUDE.md`'s own "Commands" section says the capture flight needs), any LAN peer can send an
   arbitrarily large body. This is not a new category for this project — `audio-adapter/ROADMAP.md`
   already records the identical gap for `POST /audio/play` on the aircraft-layer collector as an
   accepted, standing risk for the LAN-API phase generally, and `aircraft-layer`'s own 2026-09-26
   security/performance passes covered that side. This finding is the audio-adapter-side twin of
   the same gap, not a newly-introduced one — recording it here so the same standing exemption
   covers it explicitly rather than being assumed to. Fix, if picked up: reject (413) any
   `Content-Length` above a generous ceiling (a few MB is enough for one WAV clip) before reading
   the body.

2. **Malformed `Content-Length` header raises unhandled inside `do_POST`.**
   `src/server.py:138`/`:190` — `int(self.headers.get("Content-Length", "0") or "0")` is not
   guarded. A header value that is non-numeric (e.g. `Content-Length: abc`) raises `ValueError`
   before the `try/except` around JSON parsing is reached. `ThreadingHTTPServer`'s per-thread
   `handle_error` catches it (logs a traceback to stderr, closes that one connection) — this is
   **not** a server crash or a multi-request DoS, `ThreadingHTTPServer` isolates it to the one
   connection — but it is a needless traceback for a trivially malformed request that should be a
   clean `400`, and (compounding #1) a *negative* `Content-Length` makes `self.rfile.read(length)`
   read with a negative count, which for a socket-backed file object reads until EOF rather than a
   bounded amount — on a keep-alive connection with no EOF forthcoming, that thread blocks
   indefinitely. Not a full-server DoS (each blocked thread is one `ThreadingHTTPServer` thread,
   unbounded thread creation is its own pre-existing, accepted characteristic of using
   `ThreadingHTTPServer` at all — same tradeoff `aircraft-layer`'s stdlib-based servers already
   carry), but cheap to close: parse the header defensively and reject non-numeric/negative values
   with `400` before calling `read()`.

3. **`say`/`afplay`/`whisper-cli`/`sox` argv construction is safe from shell injection, but text
   passed to `say` as a single trailing argv token could theoretically be read by `say`'s own
   getopt parser as an option if the entire string coincidentally matched one exactly** (e.g. text
   that is literally `-v` or `-o` with nothing else). `src/tts_engine.py:74-87` passes `text` as
   the last element of an argv list, never through a shell, so this is not command injection and
   cannot inject a *separate* flag+value pair (the whole string is one argv token, never split).
   Worst case is `say` misparsing a pathological single-token string as an unknown/incomplete
   option and exiting non-zero, which the code already turns into a clean `TTSSynthesisError` ->
   `503`. No real path from "text originating in body-layer output" to actual harm — `text` here is
   Petrovich's own generated speech line, not attacker-supplied free text, and even a hostile value
   only produces a synthesis failure, not execution. **No finding requiring action**; recorded
   because it was the first thing checked for exactly the injection shape the task asked about, and
   the answer is "no, and here is why."

4. **`LocalPlaybackSink.deliver` / `tts_engine.MacSayEngine.synthesize` reopen a `mkstemp`-created
   path after closing its fd** (`src/local_playback.py:197-201`, `src/tts_engine.py:71-73`) instead
   of writing through the already-open descriptor. `mkstemp` itself is safe (atomic, exclusive,
   unpredictable name, mode 0600); the reopen-by-path introduces a narrow TOCTOU window on a
   single-user machine where no other principal is expected to race it. Not exploitable under this
   project's stated single-user deployment; worth tightening (`os.fdopen(fd, "wb")` instead of
   `os.close(fd)` + `open(path, "wb")`) only if this code is ever expected to run on a shared
   multi-user host, which is out of scope for this project.

## ACCEPTED-BY-CONTEXT

- **No authentication on any endpoint** (`/speak`, `/transcribe`, `/stop`, `/transcripts/poll`).
  Already an explicit, documented decision (`audio-adapter/CLAUDE.md`: "a public release should
  not ship listening on every interface, and `/speak`/`/transcribe`/`/stop` carry no
  authentication" — default host stays loopback for exactly this reason). Consistent with every
  other LAN-API endpoint in this project. Accepted for the current phase; the `CLAUDE.md`/ROADMAP
  note already flags it for revisit rather than this audit needing to re-flag it as new.
- **Default bind is loopback (`127.0.0.1`)**, widened to `0.0.0.0` only by explicit operator flag
  for the cross-machine capture flight, with the tradeoff already documented in `CLAUDE.md`. This
  is the correct default for a project meant to be run by strangers — accepted as-is.
- **Corrupt/garbage WAV bytes to `POST /transcribe` are not format-validated before being handed to
  `whisper-cli`.** Bounded by the existing `30s` subprocess timeout and a non-zero exit -> `503`;
  no parsing happens in Python on attacker-supplied WAV content, so there is no parser to exploit
  on this side. Any interpretation of malformed input is whisper.cpp's own problem, outside this
  subproject's code.

## Focus-area findings

**1. HTTP surface (`server.py`).** Bind address defaults to loopback (see above). JSON body
parsing is exception-guarded (`json.JSONDecodeError`/`UnicodeDecodeError` -> `400`). Non-dict body,
missing/wrong-typed `text`/`urgent`/`wav_b64` fields, and invalid base64
(`base64.b64decode(..., validate=True)` catching `binascii.Error`/`ValueError`) are all explicitly
checked and answer `400`. Unknown paths answer `404`. Error response bodies echo back the
`str(exc)` of internal exceptions (e.g. `f"delivery failed: {exc}"`), which can include a local
temp-file path or subprocess stderr text — a minor internal-details leak, appropriate severity for
a LAN-only debug-adjacent tool, not treated as a finding. No request can wedge the server as a
*whole* (`ThreadingHTTPServer` isolates each connection to its own thread and `BaseServer`'s own
`handle_error` catches unhandled exceptions per-request) — the only per-request wedge risk is the
negative-`Content-Length` case above (RECOMMENDED #2), which blocks one thread, not the process.

**2. Outbound clients (`aircraft_client.py`, `transcribe_client.py`, and `ptt_source.py`'s
`DcsPTT._read`).** All three `urllib.request.urlopen` call sites carry explicit timeouts (5s for
`AircraftLayerClient`, 30s for `TranscribeClient` — deliberately longer since whisper runs
synchronously inside the request, documented in the module docstring — and 1s default for
`DcsPTT`). `base_url`/`collector_url` are operator-supplied CLI arguments, never derived from a
request or from mission/transcript data, so there is no SSRF-shaped path: nothing here builds a
URL from data that could originate off-box. Failure bodies are read and discarded
(`response.read()`) or wrapped in a typed error; no error body is echoed into logs or interpreted
as code.

**3. Subprocess execution (`say`, `afplay`, whisper-cli, `sox`, `tools/`).** Every call site
constructs an argv list and calls `subprocess.run`/`Popen` directly — grepped `src/` and `tools/`
for `shell=True`: zero hits. Text that could originate from a transcript or LLM output
(`tts_engine.MacSayEngine.synthesize`'s `text` argument) is a single argv token with no shell
parsing, so it cannot be split into a separate flag+value pair (see RECOMMENDED #3 above for the
narrow theoretical edge, which resolves to "no exploit, just a synthesis failure"). `sox`'s
driver/device arguments (`input_args`, `audio_capture.py:118`) and whisper-cli's model/binary path
are all operator-supplied CLI flags, not request- or transcript-derived, so there is no path from
inbound HTTP data to an argv position that matters as a flag or a path. `_repair_truncated_wav`
(`audio_capture.py:342`) builds its `sox --ignore-length <path> <temp>` argv from a `tempfile`-
generated `Path`, never from request data.

**4. Filesystem.** Every temp file in `src/` (`tts_engine.py`, `stt_engine.py`,
`local_playback.py`, `audio_capture.py`) is created with `tempfile.mkstemp`, which is atomic,
unpredictable, and mode-0600 on POSIX — no predictable-name or symlink-race pattern found. Every
one is removed in a `finally` block (`os.remove`/`path.unlink(missing_ok=True)`), including on the
exception paths (timeout, non-zero exit, unreadable output). No path anywhere is built from
request- or transcript-derived data — `wav_path`/`out_json_path` in `stt_engine.py` and
`tmp_path` in `tts_engine.py`/`local_playback.py` are all `tempfile`-generated, never a filename
or fragment taken from the HTTP body. `SoxRecorder.stop()` (`audio_capture.py:311`) always
`unlink`s its temp path in a `finally`, including when `CaptureError` is raised. The narrow
mkstemp-then-reopen TOCTOU noted above (RECOMMENDED #4) is the only filesystem finding, and it is
not exploitable under the project's stated single-user deployment.

**5. Privacy.** Recorded microphone audio and recognized transcripts are not logged anywhere in
`server.py` — the only `logger.warning` calls that include user-visible text (`server.py:162`,
`:169`) log the *outbound* TTS text (Petrovich's own generated speech), never inbound transcript
text or WAV bytes; a failed recognition logs only the exception message (`server.py:221`). WAV
bytes are decoded, handed to `STTEngine.transcribe`, and immediately written to a `tempfile` that
is removed in `finally` (`stt_engine.py:181`, `:256-260`) — never persisted, never returned in an
HTTP response, matching the module docstring's "body-layer never sees audio" invariant, which
inbound recognition results (`TranscriptEvent`) uphold on the wire as well (`transcript_queue.py`:
text and match metadata only, `to_dict()` carries no audio field). The one place raw audio is
deliberately and permanently kept on disk is `tools/record_corpus.py`'s corpus recorder — that is
its explicit job (building a bench corpus from the user's own voice, by the user's own hand,
locally) and the resulting directory (`data/corpus/`) is git-ignored with a comment naming exactly
why ("still audio and still belong outside the repo"). This matches what an open-source stranger
running this tool would reasonably expect: nothing is captured or kept unless they deliberately run
the corpus-recording tool themselves.

**6. Dependencies.** `pyproject.toml` declares `dependencies = []`. Cross-checked against every
`import` in `src/` and `tools/`: `http.server`, `urllib.*`, `subprocess`, `json`, `base64`,
`binascii`, `tempfile`, `wave`, `array`, `ctypes`, `argparse`, `contextlib`, `select`, `termios`,
`tty`, `msvcrt`, `platform`, `shutil`, `dataclasses`, `collections`, `typing`, `time`, `os`,
`sys`, `io`, `logging`, `pathlib` — all stdlib. No third-party package anywhere in this
subproject's own code. The stdlib-only claim in `audio-adapter/CLAUDE.md` holds. No CVE surface
to check.

## SBOM

Not regenerated as part of this pass — this subproject has no dependency manifest entries to add
to one (`dependencies = []`), so there is nothing new for `sbom.json` to record for
`audio-adapter` specifically. (`sbom.json` is a whole-repo artifact; re-running it is unnecessary
for a subproject audit that found zero new/changed dependencies.)

## Verdict

**APPROVED.** No required fixes. Four RECOMMENDED items above (three concrete, one a documented
non-finding), all low-severity under the stated LAN-only/single-user threat model, and all either
already covered by an existing accepted-risk note elsewhere in the project or cheap enough to pick
up opportunistically. Nothing here blocks DoD.
