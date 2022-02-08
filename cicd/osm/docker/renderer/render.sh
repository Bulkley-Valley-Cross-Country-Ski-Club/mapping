#!/bin/bash

for ARGUMENT in "$@"
do
    KEY=$(echo $ARGUMENT | cut -f1 -d=)
    VALUE=$(echo $ARGUMENT | cut -f2 -d=)   
    case "$KEY" in
            data_dir)     DATA_DIR=${VALUE} ;;
            changes_3857) CHANGES_3857=${VALUE} ;;
            *)
    esac    
done

service postgresql start
while ! nc -z localhost 5432; do echo "postgres not yet ready"; sleep 1; done;

createdb -U postgres gis
psql -U postgres -d gis -c "CREATE EXTENSION postgis; CREATE EXTENSION hstore;"

osmium renumber -o bvnordic-loader.osm $DATA_DIR/bvnordic.osm
PGPASSWORD=postgres osm2pgsql -U postgres -d gis --hstore -G bvnordic-loader.osm

carto /code/cicd/osm/docker/renderer/styles/segments.mml > segments.xml

MAP_FILE_DIR=$PWD
pushd /code

MAPNIK_MAP_FILE=$MAP_FILE_DIR/segments.xml \
OUTPUT_DIR=$DATA_DIR \
OUTPUT_PREFIX=bvnordic.osm- \
CHANGES_3857=$CHANGES_3857 \
python3 -m cicd.osm.docker.renderer.generate_image

rm $DATA_DIR/*.aux.xml