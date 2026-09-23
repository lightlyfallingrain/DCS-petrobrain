source ./petrobrain.env
pushd $PETROBRAIN_PATH/audio-adapter/src && \
    python.exe -m audio_adapter.capture --adapter-url http://$MAC_IP:7795 --sox-binary $SOX_PATH --ptt dcs
popd

