source ./petrobrain.env
pushd $PETROBRAIN_PATH/audio-adapter/ && PYTHONPATH=src .venv/bin/python -m audio_adapter \
    --host 0.0.0.0 \
    --whisper-model ~/whisper-models/ggml-small.en.bin \
    --target aircraft-layer --aircraft-layer-url http://$DCS_COLLECTOR_IP:7791 
popd
