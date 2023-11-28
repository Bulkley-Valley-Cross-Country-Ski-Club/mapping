#!/bin/bash

set -e

for ARGUMENT in "$@"
do
    KEY=$(echo $ARGUMENT | cut -f1 -d=)
    VALUE=$(echo $ARGUMENT | cut -f2 -d=)   
    case "$KEY" in
            before) BEFORE=${VALUE} ;;
            after)  AFTER=${VALUE} ;;
            upload) UPLOAD=${VALUE} ;;
            *)   
    esac    
done

pushd $(dirname $0)/../../..

GITHUB_SHA=$(uuidgen)

cicd/compare/scripts/check_comparable.sh before=$BEFORE after=$AFTER
. cicd/compare/scripts/create_directories.sh before=$BEFORE after=$AFTER

UPLOAD_IF_MISSING=0
if [ "$CI" == "true" ]; then
    UPLOAD_IF_MISSING=1
fi

# export map layouts from each revision for pixel comparison
cicd/scripts/pull_or_build.sh repo=tomfumb image=qgis-exporter:3 build_dir=cicd/export/docker context_dir=cicd upload_if_missing=$UPLOAD_IF_MISSING
docker run --platform linux/amd64 --rm -e REVISION=$BEFORE -v $PWD:/code -e SHORTCUT_FOR_TESTING tomfumb/qgis-exporter:3 /workdir/cicd/export/docker/generate.sh output_base=/code/$OUTPUT_BASE/$BEFORE png=1 permit_label_locks=1
docker run --platform linux/amd64 --rm -e REVISION=$AFTER  -v $PWD:/code -e SHORTCUT_FOR_TESTING tomfumb/qgis-exporter:3 /workdir/cicd/export/docker/generate.sh output_base=/code/$OUTPUT_BASE/$AFTER png=1 permit_label_locks=1

# export OSM data from each revision
GITHUB_SHA=$GITHUB_SHA cicd/osm/scripts/export.sh local_output_dir=$OUTPUT_BASE/$BEFORE revision=$BEFORE
GITHUB_SHA=$GITHUB_SHA cicd/osm/scripts/export.sh local_output_dir=$OUTPUT_BASE/$AFTER revision=$AFTER

# create a geojson file showing MBRs of all geometry differences between the two revisions
cicd/scripts/pull_or_build.sh repo=tomfumb image=bvnordic-osm-renderer:3 build_dir=cicd/osm/docker/renderer context_dir=cicd upload_if_missing=$UPLOAD_IF_MISSING
docker run --platform linux/amd64 --rm -e REVISION=$BEFORE -v $PWD:/code tomfumb/bvnordic-osm-renderer:3 ogr2ogr -f "GPKG" /code/$OUTPUT_BASE/compare.gpkg /workdir/main-data.gpkg -nln before -sql "SELECT * FROM Trails"
docker run --platform linux/amd64 --rm -e REVISION=$AFTER -v $PWD:/code tomfumb/bvnordic-osm-renderer:3 ogr2ogr -f "GPKG" /code/$OUTPUT_BASE/compare.gpkg /workdir/main-data.gpkg -nln after -update -sql "SELECT * FROM Trails"
docker run --platform linux/amd64 --rm -v $PWD:/code tomfumb/bvnordic-osm-renderer:3 ogr2ogr -f "GeoJSON" /code/$OUTPUT_BASE/parts_3857.geojson /code/$OUTPUT_BASE/compare.gpkg -nln diff -t_srs "EPSG:3857" -dialect sqlite -sql "SELECT geom FROM (SELECT ST_Envelope(ST_Transform(ST_Difference(a.geom, b.geom), 3857)) AS geom FROM after a LEFT JOIN before b ON a.fid = b.fid UNION SELECT ST_Envelope(ST_Transform(ST_Difference(b.geom, a.geom), 3857)) AS geom FROM before b LEFT JOIN after a ON b.fid = a.fid) WHERE geom IS NOT NULL"
docker run --platform linux/amd64 --rm -v $PWD:/code tomfumb/bvnordic-osm-renderer:3 ogr2ogr -f "GeoJSON" /code/$OUTPUT_BASE/diff_3857.geojson /code/$OUTPUT_BASE/parts_3857.geojson -nln diff -t_srs "EPSG:3857" -dialect sqlite -sql "SELECT ST_Union(Geometry) FROM diff"
rm $OUTPUT_BASE/compare.gpkg $OUTPUT_BASE/parts_3857.geojson


# render OSM data from each revision
docker run --platform linux/amd64 --rm -e REVISION=$BEFORE -v $PWD:/code tomfumb/bvnordic-osm-renderer:3 /workdir/cicd/osm/docker/renderer/render_changes.sh data_dir=/code/$OUTPUT_BASE/$BEFORE/main changes_3857=/code/$OUTPUT_BASE/diff_3857.geojson
docker run --platform linux/amd64 --rm -e REVISION=$AFTER -v $PWD:/code tomfumb/bvnordic-osm-renderer:3 /workdir/cicd/osm/docker/renderer/render_changes.sh data_dir=/code/$OUTPUT_BASE/$AFTER/main changes_3857=/code/$OUTPUT_BASE/diff_3857.geojson
rm -f $OUTPUT_BASE/diff_3857.geojson

# run change detection on before/after images
python -m cicd.compare.detect_changes $BEFORE $AFTER $PWD/$OUTPUT_BASE --before_after_exclude bvnordic\\.osm\\-.+

# clean up 
rm -rf $OUTPUT_BASE/$BEFORE
rm -rf $OUTPUT_BASE/$AFTER

# upload results to Google Drive if necessary
if [ "$UPLOAD" == "1" ]; then
    GDRIVE_UPLOAD_SERVICE_ACCT_INFO=$GDRIVE_PR_UPLOAD_SERVICE_ACCT_INFO python -m cicd.upload.upload $COMPARE_DIR $PWD/output
fi