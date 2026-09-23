source ./petrobrain.env
pushd $PETROBRAIN_PATH/audio-adapter/src && \
    python.exe -m audio_adapter.capture --adapter-url http://$MAC_IP:7795 --sox-binary 'D:\sox-14-4-2\sox.exe' --ptt dcs
popd

