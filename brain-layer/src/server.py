"""`brain-layer`'s own inbound HTTP server -- `POST /escalate`,
`GET /replies/poll`, `GET /health` (`plans/brain-layer/plan.md` D1/D2).

Structurally a direct copy of `audio-adapter/src/server.py`'s shape
(stdlib `http.server.ThreadingHTTPServer`, one handler factory closing
over its collaborators, `_respond_json`) -- **not** FastAPI, despite the
plan's own affected-modules table naming it: every other subproject in
this repo (`world-model`, `aircraft-layer`, `audio-adapter`) declares
`dependencies = []` and builds its HTTP surface on the standard library
alone, and root `CLAUDE.md`/`AGENTS.md` both treat a new dependency as an
escalation-worthy decision, not a routine implementation choice. The
plan's own Decisions (D1-D11) never argue for a specific web framework;
the table entry is one line in an affected-files list, not a Decision.
Following the established stdlib-only convention is the local, reversible
call here (`AGENTS.md`'s "pick one and proceed" rule) -- reversible later,
with cause, not by default.

**`POST /escalate` is fire-and-forget** (D2: "`handle()` returns
immediately... The brain replies into its own queue"). The handler
validates the body just enough to build a `job.Job`, submits it to the
single `JobSlot` (D3's newest-wins), starts a **daemon** worker thread that
calls the configured `Decider`, and responds `202` before that thread has
necessarily finished -- the POST itself never waits on `Decider.decide`,
which is exactly what makes an 8s `StubDecider` delay provable without
blocking anything on either side of the wire.

**The worker checks `JobSlot.is_current` immediately before publishing**
(not before calling `decide` -- a job superseded mid-decision must still
finish its own `decide()` call harmlessly rather than being killed, since
there is no cooperative-cancellation mechanism for a blocking model call;
it only must never have its answer *delivered*). This is D3's "abandoned
job's reply is discarded... when it lands," implemented at the one point
that matters.

**`Decider.decide()` runs under its own bounded timeout**
(`plans/brain-layer/plan.md`'s pre-Stage-2 prerequisite 2,
`plans/brain-layer/performance-review.md`): `_handle_escalate`'s daemon
worker thread is already unjoined and never awaited by the HTTP request
thread (the module docstring above -- `POST /escalate` has already
responded `202` before this thread necessarily runs at all), but nothing
previously bounded how long `decide()` itself could take. Stage 1's
`StubDecider` is always fast or boundedly-delayed, so this was invisible;
Stage 2's `OllamaDecider` calls a real model over HTTP, and a hung Ollama
daemon (model-load stall, OOM, daemon wedge) would otherwise leak one
permanently-blocked thread per escalated utterance across a multi-hour
sortie -- and produce exactly the wedged-server condition the client-side
fix above exists to survive.

`_run_job` now races `decide()` on a throwaway single-worker
`ThreadPoolExecutor`, bounded by `_DECIDE_TIMEOUT_S`, and **does not wait
for that executor to shut down** (`shutdown(wait=False)`) -- this is a
bound on `_run_job`'s own daemon thread (already off the HTTP request
thread, so nothing here ever blocks a caller), not a claim that a
genuinely-hung network call can be forcibly killed: Python cannot
preempt a blocked thread. The real, effective fix for an unbounded hang
is `OllamaDecider`'s own `urllib` call carrying a socket-level timeout
(so `decide()` itself reliably returns, one way or another, well inside
`_DECIDE_TIMEOUT_S`); this wrapper is the decider-agnostic backstop that
still holds even if a future `Decider` implementation forgets its own
timeout -- a timed-out `decide()` degrades to a dropped job, the same
documented behaviour `_run_job`'s `except Exception` already gives any
other decider failure."""

from __future__ import annotations

import concurrent.futures
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import TracebackType
from typing import Any, Self
from urllib.parse import urlparse

from decider import Decider
from job import Job, JobSlot, ReplyQueue

logger = logging.getLogger(__name__)

#: Loopback by default -- brain-layer is expected to run on the same box
#: as Ollama (the user's compute-topology note in root `CLAUDE.md`: Mac
#: runs both). `__main__.py` can still override `--host` for the LAN case
#: (body-layer on a different box), mirroring every other subproject's
#: server here.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7796

_ESCALATE_PATH = "/escalate"
_REPLIES_POLL_PATH = "/replies/poll"
_HEALTH_PATH = "/health"

#: Bounds one `Decider.decide()` call (module docstring's "`Decider.decide()`
#: runs under its own bounded timeout"). Generous relative to `OllamaDecider`'s
#: own per-request `urllib` timeout (`ollama_client.DEFAULT_TIMEOUT_S`,
#: 5.0s) times at most two sequential model calls (D5's classify/discriminate
#: split) plus overhead -- bounded, not tuned; Stage 4 is where real-sortie
#: numbers replace every constant like this one. Public (not `_`-prefixed)
#: since `brain_layer/__main__.py`'s `--decide-timeout-s` reads it as its
#: own default.
DEFAULT_DECIDE_TIMEOUT_S = 12.0


def _run_job(
    decider: Decider,
    job: Job,
    generation: int,
    job_slot: JobSlot,
    reply_queue: ReplyQueue,
    decide_timeout_s: float,
) -> None:
    """The worker thread body for one job: decide (under `decide_timeout_s`,
    module docstring), then publish only if still current. Any exception
    from `Decider.decide` -- including a timeout -- is logged and the job
    is dropped -- no reply is worse than a crashed server, and
    body-layer's own timeout/staleness handling (D4) already treats "no
    reply arrived" as a normal, honestly-handled case."""
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(decider.decide, job.payload)
    try:
        result = future.result(timeout=decide_timeout_s)
    except concurrent.futures.TimeoutError:
        logger.warning(
            "decider timed out after %.1fs for utterance %s (dropping job)",
            decide_timeout_s,
            job.utterance_id,
        )
        # Deliberately not `wait=True` -- see module docstring: a
        # genuinely-hung `decide()` call cannot be forced to stop, and
        # waiting for it here would reintroduce the exact unbounded block
        # this timeout exists to avoid. The executor's own worker thread
        # is abandoned, not this method's caller.
        executor.shutdown(wait=False)
        return
    except Exception:
        logger.exception("decider failed for utterance %s", job.utterance_id)
        executor.shutdown(wait=False)
        return
    executor.shutdown(wait=False)
    if not job_slot.is_current(generation):
        logger.info("discarding reply for superseded utterance %s", job.utterance_id)
        return
    reply = dict(result)
    reply["utterance_id"] = job.utterance_id
    reply["t_sim"] = job.payload.get("t_sim")
    reply_queue.push(reply)


def _make_handler(
    decider: Decider,
    job_slot: JobSlot,
    reply_queue: ReplyQueue,
    decide_timeout_s: float,
) -> type[BaseHTTPRequestHandler]:
    class BrainRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == _REPLIES_POLL_PATH:
                self._respond_json(200, reply_queue.drain_all())
                return
            if path == _HEALTH_PATH:
                self._respond_json(200, {"ok": True})
                return
            self._respond_json(404, {"error": f"not found: {path}"})

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path == _ESCALATE_PATH:
                self._handle_escalate()
                return
            self._respond_json(404, {"error": f"not found: {path}"})

        def _handle_escalate(self) -> None:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(length) if length > 0 else b""
            try:
                data = json.loads(raw_body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._respond_json(400, {"error": "body must be valid JSON"})
                return
            if not isinstance(data, dict):
                self._respond_json(400, {"error": "body must be a JSON object"})
                return

            utterance_id = data.get("utterance_id")
            if not isinstance(utterance_id, str) or not utterance_id:
                self._respond_json(
                    400, {"error": "'utterance_id' must be a non-empty string"}
                )
                return

            job = Job(utterance_id=utterance_id, payload=data)
            generation = job_slot.submit(job)
            worker = threading.Thread(
                target=_run_job,
                args=(
                    decider,
                    job,
                    generation,
                    job_slot,
                    reply_queue,
                    decide_timeout_s,
                ),
                daemon=True,
            )
            worker.start()
            # 202 Accepted -- the decision is not made yet, only queued
            # (D2: "handle() ... returns, and that is all").
            self._respond_json(202, {"ok": True})

        def _respond_json(self, status: int, body: Any) -> None:
            payload = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            logger.debug("%s - %s", self.address_string(), format % args)

    return BrainRequestHandler


class BrainLayerServer:
    """Owns the `POST /escalate` + `GET /replies/poll` + `GET /health` HTTP
    server; mirrors `audio-adapter`'s `TTSAdapterServer`/`aircraft-layer`'s
    `TelemetryAPIServer` open()/close()/serve_forever() shape."""

    def __init__(
        self,
        decider: Decider,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        job_slot: JobSlot | None = None,
        reply_queue: ReplyQueue | None = None,
        decide_timeout_s: float = DEFAULT_DECIDE_TIMEOUT_S,
    ) -> None:
        self._decider = decider
        self._host = host
        self._port = port
        self._job_slot = job_slot if job_slot is not None else JobSlot()
        self._reply_queue = reply_queue if reply_queue is not None else ReplyQueue()
        self._decide_timeout_s = decide_timeout_s
        self._httpd: ThreadingHTTPServer | None = None

    def __enter__(self) -> Self:
        self.open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    @property
    def port(self) -> int:
        """Bound port. Useful when constructed with `port=0` (OS-assigned)."""
        if self._httpd is None:
            raise RuntimeError("call open() before reading port")
        return int(self._httpd.server_address[1])

    def open(self) -> None:
        """Bind and start listening. Does not block."""
        self._httpd = ThreadingHTTPServer(
            (self._host, self._port),
            _make_handler(
                self._decider,
                self._job_slot,
                self._reply_queue,
                self._decide_timeout_s,
            ),
        )
        logger.info("brain-layer listening on %s:%d", self._host, self.port)

    def close(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None

    def serve_forever(self) -> None:
        """Serve requests until `close()` is called from another thread."""
        if self._httpd is None:
            raise RuntimeError("call open() before serve_forever()")
        self._httpd.serve_forever()
