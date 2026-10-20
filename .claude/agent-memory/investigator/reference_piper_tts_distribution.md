---
name: reference-piper-tts-distribution
description: Where Piper TTS actually lives now, which releases ship a real binary vs a Python wheel, and the GitHub Releases API trick for reading asset names WebFetch can't render
metadata:
  type: reference
---

Session 2026-10-19 (AA-6 Piper recon, full findings at
`audio-adapter/research/2026-10-19-piper-cross-platform-recon.md`). Worth reaching for again
rather than re-discovering, since this took several wrong turns to pin down.

**The GitHub repo split, and which half has a binary:**

- `rhasspy/piper` — the original, MIT-licensed, **C++ binary** project. **Archived 2025-10-06**,
  read-only, no further releases. Its **last release, tag `2023.11.14-2`, is still the only
  standalone-binary route** (no Python, no pip) — assets `piper_windows_amd64.zip`,
  `piper_macos_aarch64.tar.gz`, `piper_macos_x64.tar.gz`. Confirmed working on Windows this
  session (self-contained: `piper.exe` + `espeak-ng.dll` + `piper_phonemize.dll` +
  `onnxruntime*.dll` + bundled `espeak-ng-data/`, no system install needed). **macOS arm64 has a
  known, unfixed dylib-loading bug** (`rhasspy/piper#404`) — not verified fixed or broken on any
  particular Mac, just known-reported and now unfixable upstream.
- `OHF-Voice/piper1-gpl` — the actively maintained successor (Open Home Foundation,
  GPL-3.0-or-later, license change from the original MIT). **Ships ONLY as Python wheels** (`pip
  install piper-tts`) — checked the actual release assets (see trick below), confirmed zero
  binary/exe/zip assets in `v1.8.0`, only `.whl` per platform/arch plus a source tarball. If a
  future investigator is asked to re-check whether this has gained a standalone binary, that is
  the question to re-ask — it had not as of this date.

**Voice models**: `huggingface.co/rhasspy/piper-voices`, path shape
`en/en_US/<name>/<quality>/en_US-<name>-<quality>.onnx(.json)`, `resolve/main/...` works directly
with `urllib.request`. Quality tier (`low`/`medium`/`high`) determines the WAV sample rate Piper
writes (16000 Hz for `low`, 22050 Hz for every `medium`/`high` voice tested) — this is a property
of the voice file, not a CLI flag.

**The trick that actually got asset filenames**: GitHub's *releases HTML page* renders its asset
list via JS, and `WebFetch` (HTML→markdown) sees only "Loading... Uh oh! There was an error while
loading" where the list should be. **`WebFetch` the GitHub REST API URL directly instead**:
`https://api.github.com/repos/<owner>/<repo>/releases/latest` (or `/releases/tags/<tag>`, or
`/releases?per_page=N` for a list) returns real JSON with every asset's `name` and
`browser_download_url` — `WebFetch`'s own JSON-to-text handling renders it cleanly where the HTML
page fails. No `gh` CLI or auth needed, these are public repos.

**whisper.cpp's prebuilt binaries are under nightly `b<NNNN>` tags, not stable semver tags.**
Checked across the last 10 releases: every stable tag (`v1.9.5`, `v1.9.4`) had an **empty**
`assets` array; every nightly `b`-tag (`b5454`, `b5130`, `b5127`) had 13-16 assets including
`whisper-bin-x64.zip` (plain CPU Windows build, what `WhisperCliEngine` needs) and CUDA/arm64
variants. If `whisper-cli.exe` for Windows is needed again, go straight to a `b`-tag, not the
latest stable release — the stable release page will look empty and waste a round trip.
