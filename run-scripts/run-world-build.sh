source ./petrobrain.env
MACOS=$(sw_vers 2>/dev/null | grep -o macOS)

if [ "$1" == "" ]
then
    echo usage $0 terrain-name
    exit 1
fi

TERRAIN="$1"

if [ "$MACOS" != "" ] 
then
    # on MAC
    pushd ../world-model/ && \
    .venv/bin/python tools/build_world_model.py $TERRAIN-full \
        --towns   data/raw/dcs/$TERRAIN/map/towns.lua \
        --beacons data/raw/dcs/$TERRAIN/beacons.lua \
        --routes  data/raw/dcs/$TERRAIN/roads/$TERRAIN.routes \
        --srtm-dir data/raw/dem/$TERRAIN-full/ \
        --osm-pbf  data/raw/osm/$TERRAIN-theatre.osm.pbf \
        2>&1 | tee $TERRAIN-full-build.log
    popd
else
    # on Windows (WSL)
    DCS="$DCS_INSTALL_PATH/Mods/terrains/$TERRAIN"
    pushd ../world-model/ && \
    .venv/bin/python tools/build_world_model.py $TERRAIN-full \
        --towns   "$DCS/map/towns.lua" \
        --beacons "$DCS/beacons.lua" \
        --routes  "$DCS/roads/$TERRAIN.routes" \
        --srtm-dir data/raw/dem/$TERRAIN-full/ \
        --osm-pbf  data/raw/osm/$TERRAIN-full/afghanistan-theatre.osm.pbf \
        2>&1 | tee $TERRAIN-full-build.log
    popd
fi



