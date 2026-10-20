---
name: piper-http-server-cli
description: piper.http_server's -m/--model argument is required (no default); --data-dir alone is not enough to start it
metadata:
  type: reference
---

`python -m piper.http_server`'s own `argparse` (confirmed by reading the installed `piper-tts`
1.8.0 package's source, `.../site-packages/piper/http_server.py`, and live-running it) requires
`-m`/`--model` — there is no default, and startup raises `ValueError` without it. `--data-dir`
only matters for *per-request* voice selection (the `"voice"` field in `/synthesize`, loaded on
first use from any `<name>.onnx` found there); it does not supply the server's own startup model.

A command of the shape `python -m piper.http_server --host 127.0.0.1 --port 7800 --data-dir
<dir>` (no `--model`) will not start. This is exactly the shape an early plan draft for AA-6
specified before implementation — caught only by reading the installed package's own source, not
by the recon (which measured the HTTP contract and latency but not every CLI flag).

`--host`/`--port`/`--data-dir`/`-m`/`--model` all exist as documented; `--host` defaults to
`0.0.0.0` (bind `127.0.0.1` explicitly for a dev box). Response to `/synthesize` is raw WAV bytes,
no JSON/base64 wrapping.

How to apply: before writing or trusting a `piper.http_server` invocation in a run script or
plan, grep the installed package's own `http_server.py` for its `argparse` block rather than
trusting a recon's prose description of "the HTTP contract" — a contract description can be
accurate about the endpoints and still omit a required startup flag.
