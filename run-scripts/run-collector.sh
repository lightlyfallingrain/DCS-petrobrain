source ./petrobrain.env
pushd $PETROBRAIN_PATH/aircraft-layer/src && python.exe -m collector
popd
