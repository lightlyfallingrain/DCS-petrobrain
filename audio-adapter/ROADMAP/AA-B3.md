# AA-B3 — `POST /audio/play` has no request-size cap

<!-- doc-provenance:start -->
**Topics:** #audio-playback
<!-- doc-provenance:end -->

- [ ] **AA-B3 — `POST /audio/play` has no request-size cap** #status/open (and neither do audio-adapter's own
  `/speak`/`/transcribe`/`/stop`, per the 2026-09-26 security audit's RECOMMENDED #1 — the same
  standing exemption covers them explicitly rather than by assumption) and, like every other
  endpoint on that LAN API, no auth. Same severity class as the existing overlay-text and search-trigger endpoints
  rather than a new category of exposure — recorded because the phase's security exemption may be
  revisited, not because anything here is newly wrong.
