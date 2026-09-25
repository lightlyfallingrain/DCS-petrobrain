source ./petrobrain.env
pushd ../body-layer/
PYTHONPATH=src:../world-model/src .venv/bin/python -m logger --console --overlay --aircraft-layer-url http://$DCS_COLLECTOR_IP:7791 --theatre Syria --world-model-db ../world-model/data/world-model/syria-full.sqlite
popd
