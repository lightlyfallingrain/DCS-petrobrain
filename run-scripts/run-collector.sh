source ./petrobrain.env
pushd $PETROBRAIN_PATH/aircraft-layer/src && python.exe -m collector --api-host 0.0.0.0
popd
