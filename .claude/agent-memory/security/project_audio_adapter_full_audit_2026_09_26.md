---
name: audio-adapter-full-audit-2026-09-26
description: Mode 3 whole-subproject audit of audio-adapter (bd28563) — no required fixes, three low-severity recommendations
metadata:
  type: project
---

Full-subproject security scan of `audio-adapter/` (Mode 3, branch `main` HEAD `bd28563`,
2026-09-26). Report: `audio-adapter/docs/reviews/security-audit-audio-adapter.md`.

**Verdict: APPROVED, no required fixes.**

**Confirmed clean:**
- Genuinely stdlib-only — `pyproject.toml`'s `dependencies = []` cross-checked against every
  `import` in `src/`/`tools/`. No third-party supply chain surface in this subproject.
- No `shell=True` anywhere; every `say`/`afplay`/`sox`/`whisper-cli` call is an argv list.
- All `urllib.request.urlopen` call sites carry explicit timeouts (5s/30s/1s per client).
- All temp files use `tempfile.mkstemp` (atomic, mode 0600, unpredictable), removed in `finally`.
- Mic-derived transcript text and WAV bytes are never logged anywhere in `server.py` — the only
  logged text is Petrovich's own outbound TTS lines, not inbound speech.
- `data/corpus/` (recorded voice corpus) is git-ignored with an explicit comment; nothing is
  captured/kept unless the user deliberately runs `tools/record_corpus.py` themselves.

**RECOMMENDED (not blocking), for whoever picks these up next:**
1. No request-body size cap on `POST /speak`/`/transcribe`/`/stop` (`server.py:138`/`:190`) —
   the audio-adapter-side twin of the same accepted gap already recorded in
   `audio-adapter/ROADMAP.md` for aircraft-layer's `POST /audio/play`. Same standing exemption
   should just be understood to cover this side too, not treated as newly discovered elsewhere.
2. Malformed/negative `Content-Length` header isn't guarded before `int()`/`self.rfile.read()` —
   non-numeric raises (caught per-thread by `ThreadingHTTPServer`, not a crash, just a stray
   traceback); negative makes `read()` block until EOF on that one thread. Cheap fix: validate
   the header before use.
3. `mkstemp` fd is closed then the path reopened by name in `tts_engine.py`/`local_playback.py`
   instead of writing through the open fd — narrow TOCTOU, not exploitable under this project's
   single-user deployment model, only worth tightening if that assumption ever changes.

**Checked and ruled out (no finding):** text passed to `say` as a trailing argv token cannot be
split into a separate flag+value pair (no shell involved, whole string is one token) — worst case
is a synthesis failure the code already handles as `TTSSynthesisError` -> `503`.

See also [[project_aircraft_layer_full_audit_pattern]] if it exists — the aircraft-layer
2026-09-26 security/performance passes already produced the `POST /audio/play` size-cap and
`ThreadingHTTPServer`-style hardening precedent this audit's RECOMMENDED #1/#2 mirror.
