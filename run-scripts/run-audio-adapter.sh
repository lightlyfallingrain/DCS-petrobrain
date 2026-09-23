source ./petrobrain.env
PYTHONPATH=src ../audio-adapter/.venv/bin/python -m audio_adapter --host 0.0.0.0 --whisper-model ~/whisper-models/ggml-small.en.bin
popd
