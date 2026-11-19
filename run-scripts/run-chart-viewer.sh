source ./petrobrain.env
pushd ../raster-chart-viewer/
PYTHONPATH=src .venv/bin/python -m raster_chart_viewer \
  --dcs-install "$DCS_INSTALL_PATH" \
    $@
popd

