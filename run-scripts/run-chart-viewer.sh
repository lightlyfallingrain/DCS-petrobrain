source ./petrobrain.env
# Windows-side venv with Pillow, see raster-chart-viewer/README.md "Run". DCS_INSTALL_PATH is the
# WSL form (/mnt/...); the viewer is a Windows process and wants the Windows form.
pushd $PETROBRAIN_PATH/raster-chart-viewer/src && \
    ../.venv-win/Scripts/python.exe -m raster_chart_viewer \
    --dcs-install "$(wslpath -w "$DCS_INSTALL_PATH")" \
    "$@"
popd
