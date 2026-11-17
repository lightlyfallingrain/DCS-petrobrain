"""Run the `audio-adapter` process: `POST /speak` -> TTS synthesis -> one of
two delivery targets (`plans/audio-adapter-os-independent/plan.md`
Decision 4/5).

`--target local` (no other subproject required) plays the synthesized WAV
directly on this machine -- `afplay` on macOS/Linux, `winsound` on Windows
(`local_playback.make_local_sink`'s platform dispatch, Decision 2/6). This
is both the fastest way to iterate on voice/wording quality and the
permanent guaranteed-deliverable local-dev path body-layer's crew session
(speech out is unconditional, `BL-B96`) needs to be testable without a
live Windows/DCS session, per `body-layer/CLAUDE.md`'s "testable without a
live DCS session" requirement.

`--target aircraft-layer` instead POSTs the WAV to a running aircraft-layer
collector's `POST /audio/play`, which plays it through `winsound` on the
Windows box -- the same `winsound` playback either way, this flag only
decides which machine it plays on.

Synthesis is always via `tts_engine.PiperEngine`, an HTTP client for
Piper's own long-lived `piper.http_server` process (started separately by
`run-scripts/run-piper-mac.sh`/`run-piper-windows.sh`, Decision 1/5) --
never spawned, supervised, or health-checked by this process. `--piper-url`
replaces nothing; `--piper-voice` replaces the old macOS-only `--voice`,
which has no meaning for Piper's HTTP contract.

**Inbound speech** (`plans/inbound-speech/plan.md` Stage 3): passing
`--whisper-model` also wires a `WhisperCliEngine` into the server, enabling
`POST /transcribe`/`GET /transcripts/poll`. Uses Stage 1's settled
configuration -- `--prompt` biasing (`vocabulary.to_prompt()`), never
`--grammar` (Decision 1 REVISED/Decision 4 REVISED: a grammar cannot
decline, so its failures are confident wrong commands rather than
detectable misses). Without `--whisper-model`, `POST /transcribe` answers
`503` and `GET /transcripts/poll` always drains empty -- a true no-op,
same posture as `--target aircraft-layer` requiring `--aircraft-layer-url`.

**Rules** (`plans/speech-rules/plan.md`, `[[BL-17]]`): `PUT /rules`/
`GET /transcripts/poll`'s `X-Rules-Version` header are always on (no
flag) -- body-layer pushes its loaded `config/rules/*.lua` set here,
and the whisper prompt (when `--whisper-model` is given) is rebuilt from
the active rule set's own words on every recognition, via a *provider*
callable rather than a fixed string computed once at startup.

Usage: python -m audio_adapter [--host HOST] [--port PORT] [--target local]
       [--piper-url URL] [--piper-voice VOICE] [--whisper-model PATH]
       [--whisper-binary NAME]
   or: python -m audio_adapter --target aircraft-layer --aircraft-layer-url URL
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from latency_log import LatencyLogWriter
from local_playback import make_local_sink
from rule_patterns import CachedRulePromptProvider, RuleRegistry
from server import DEFAULT_HOST, DEFAULT_PORT, AudioSink, TTSAdapterServer
from stt_engine import DEFAULT_WHISPER_BINARY, WhisperCliEngine
from tts_engine import DEFAULT_PIPER_URL, DEFAULT_PIPER_VOICE, PiperEngine
from vocabulary import to_prompt

logger = logging.getLogger(__name__)

#: whisper.cpp keeps only the last `n_text_ctx/2` = 224 prompt tokens
#: (`vocabulary.to_prompt`'s own docstring) -- the shipped vocabulary
#: measures at ~135 tokens for ~135 words (roughly one BPE token per
#: word for this short, plain-English list), so a word count is a
#: reasonable, dependency-free proxy for the runtime check above.
_WHISPER_PROMPT_WORD_CAP = 200


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--host", default=DEFAULT_HOST, help="POST /speak listener host"
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help="POST /speak listener port"
    )
    parser.add_argument(
        "--target",
        choices=("local", "aircraft-layer"),
        default="local",
        help=(
            "delivery target for synthesized audio -- 'local' (default) "
            "plays on this machine (afplay on macOS, winsound on Windows), no "
            "other subproject needed; "
            "'aircraft-layer' POSTs the WAV to a running aircraft-layer "
            "collector's /audio/play (requires --aircraft-layer-url)"
        ),
    )
    parser.add_argument(
        "--aircraft-layer-url",
        default=None,
        help=(
            "aircraft-layer LAN API base URL, e.g. http://192.168.1.50:7791 "
            "-- required when --target aircraft-layer"
        ),
    )
    parser.add_argument(
        "--piper-url",
        default=DEFAULT_PIPER_URL,
        help="Piper's piper.http_server base URL (started separately, see "
        "run-scripts/run-piper-mac.sh / run-piper-windows.sh)",
    )
    parser.add_argument(
        "--piper-voice",
        default=DEFAULT_PIPER_VOICE,
        help="Piper voice model name, sent as the 'voice' field on every "
        "/synthesize request (e.g. en_GB-northern_english_male-medium)",
    )
    parser.add_argument(
        "--whisper-binary",
        default=DEFAULT_WHISPER_BINARY,
        help=(
            "whisper-cli binary name or path, for inbound speech "
            "(POST /transcribe) -- resolved via PATH unless absolute/"
            "relative. Unused unless --whisper-model is also given."
        ),
    )
    parser.add_argument(
        "--whisper-model",
        default="",
        help=(
            "path to a whisper.cpp GGUF/GGML model file (Stage 1 settled "
            "on ggml-small.en, research/2026-09-19-whisper-model-sweep.md) "
            "-- when given, wires POST /transcribe and GET /transcripts/"
            "poll. Omitted (default): both answer as if no recogniser is "
            "configured, a true no-op."
        ),
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="log every request at DEBUG level",
    )
    parser.add_argument(
        "--latency-log",
        type=Path,
        default=None,
        help=(
            "write one JSON line per /speak and /transcribe attempt "
            "(synthesis/delivery/recognition/match durations, correlation "
            "id, outcome -- including failures) -- joined with the capture "
            "process's own --latency-log and body-layer's logs by "
            "tools/join_voice_latency.py. Omitted (default): a true no-op."
        ),
    )
    args = parser.parse_args()

    if args.target == "aircraft-layer" and args.aircraft_layer_url is None:
        parser.error("--target aircraft-layer requires --aircraft-layer-url")

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    engine = PiperEngine(base_url=args.piper_url, voice=args.piper_voice)

    sink: AudioSink
    if args.target == "aircraft-layer":
        from aircraft_client import AircraftLayerAudioSink

        sink = AircraftLayerAudioSink(base_url=args.aircraft_layer_url)
    else:
        sink = make_local_sink()

    # `[[BL-17]]` D1/D10 -- one `RuleRegistry`, shared between the server
    # (writes it on every `PUT /rules`) and the prompt provider below
    # (reads it on every recognition). `rule_prompt_provider` closes over
    # it rather than capturing a snapshot, so a rule pushed mid-sortie
    # changes the very next `/transcribe` call's prompt.
    rule_registry = RuleRegistry()

    def _build_rule_prompt(extra_words: list[str]) -> str:
        prompt = to_prompt(extra_words)
        # D10/risk R3: the shipped vocabulary's own 224-token cap is
        # tested statically (`test_vocabulary.py`); a user's own rule
        # words are not, so this is the runtime check for that case.
        # Word count, not a real BPE token count (no tokenizer
        # dependency here) -- a conservative-enough proxy for this
        # short, plain-English vocabulary.
        if len(prompt.split()) > _WHISPER_PROMPT_WORD_CAP:
            logger.warning(
                "whisper prompt is ~%d words, over the ~%d-word cap -- "
                "whisper drops the front of the prompt, so some active "
                "rule words may not be biased",
                len(prompt.split()),
                _WHISPER_PROMPT_WORD_CAP,
            )
        return prompt

    # D15: only rebuilds the prompt when `rule_registry.version` actually
    # changes (a `PUT /rules`), not on every `/transcribe` call -- see
    # `CachedRulePromptProvider`'s own docstring.
    rule_prompt_provider = CachedRulePromptProvider(rule_registry, _build_rule_prompt)

    stt_engine = (
        WhisperCliEngine(
            binary_path=args.whisper_binary,
            model_path=args.whisper_model,
            prompt=rule_prompt_provider,
        )
        if args.whisper_model
        else None
    )

    latency_log = (
        LatencyLogWriter(args.latency_log) if args.latency_log is not None else None
    )

    server = TTSAdapterServer(
        engine,
        sink,
        host=args.host,
        port=args.port,
        stt_engine=stt_engine,
        latency_log=latency_log,
        rule_registry=rule_registry,
    )
    server.open()
    logger.info(
        "audio-adapter ready (target=%s, speech-input=%s)",
        args.target,
        "on" if stt_engine is not None else "off",
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()


if __name__ == "__main__":
    main()
