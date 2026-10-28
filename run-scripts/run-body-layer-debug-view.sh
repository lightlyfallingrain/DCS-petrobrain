source ./petrobrain.env
pushd ../body-layer/
PYTHONPATH=src:../world-model/src .venv/bin/python -m body \
    --aircraft-layer-url http://$DCS_COLLECTOR_IP:7791 \
    --audio-adapter-url http://$AUDIO_ADAPTER_IP:7795 \
    --brain-client http --brain-url http://$BRAIN_CLIENT_IP:7796 \
    --theatre Kola \
    --world-model-db ~/dcs-petrobrain-world-models/kola-full.sqlite \
    --eyesight-view \
    --eyesight-view-radius-m 5000 \
    --pov-view \
    --speech-log logs/dcs-speech.jsonl \
    --slew-trace logs/dcs-slew-trace.jsonl \
    $@
popd
