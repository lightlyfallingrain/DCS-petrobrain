source ./petrobrain.env
pushd ../body-layer/
PYTHONPATH=src:../world-model/src .venv/bin/python -m logger --aircraft-layer-url http://$DCS_COLLECTOR_IP:7791 \
    --theatre Syria \
    --world-model-db ../world-model/data/world-model/syria-full.sqlite \
    --speech-audio \
    --speech-input \
    --crew-text \
    --f10-commands \
    --audio-adapter-url http://127.0.0.1:7795 \
    --brain-client http --brain-url http://127.0.0.1:7796 \
    --speech-log logs/dcs-speech.jsonl \
    $@
popd
