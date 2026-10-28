source ./petrobrain.env
pushd ../body-layer/
PYTHONPATH=src:../world-model/src .venv/bin/python -m body \
    --aircraft-layer-url http://$DCS_COLLECTOR_IP:7791 \
    --audio-adapter-url http://127.0.0.1:7795 \
    --brain-client http --brain-url http://127.0.0.1:7796 \
    --world-model-dir ~/dcs-petrobrain-world-models/ \
    $@
popd
