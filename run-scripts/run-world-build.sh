source ./petrobrain.env
MACOS=$(sw_vers 2>/dev/null | grep -o macOS)

if [ "$MACOS" != "" ] 
then
    # on MAC
    pushd ../world-model/ && \
    .venv/bin/python tools/build_world_model.py syria-full \
        --towns   data/raw/dcs/syria/map/towns.lua \
        --beacons data/raw/dcs/syria/beacons.lua \
        --routes  data/raw/dcs/syria/roads/Syria.routes \
        --srtm-dir data/raw/dem/syria-full/ \
        --osm-pbf  data/raw/osm/syria-theatre.osm.pbf \
        2>&1 | tee syria-full-build.log
    popd
else
    # on Windows (WSL)
    DCS="$DCS_INSTALL_PATH/Mods/terrains/Syria"
    pushd ../world-model/ && \
    .venv/bin/python tools/build_world_model.py syria-full \
        --towns   "$DCS/map/towns.lua" \
        --beacons "$DCS/beacons.lua" \
        --routes  "$DCS/roads/Syria.routes" \
        --srtm-dir /mnt/f/dcs-world-model/syria/raw/dem/syria-full/ \
        --osm-pbf  /mnt/f/dcs-world-model/syria/raw/osm/syria-theatre.osm.pbf \
        2>&1 | tee syria-full-build.log
    popd
fi



