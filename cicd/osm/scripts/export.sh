#!/bin/bash

set -e

for ARGUMENT in "$@"
do
    KEY=$(echo $ARGUMENT | cut -f1 -d=)
    VALUE=$(echo $ARGUMENT | cut -f2 -d=)   
    case "$KEY" in
            local_output_dir) LOCAL_OUTPUT_DIR=${VALUE} ;;
            revision)         REVISION=${VALUE} ;;
            *)
    esac    
done

pushd $(dirname $0)/../../..

DOCKER_REPO=tomfumb
DOCKER_IMAGE=bvnordic-osm-exporter:2
DOCKER_TAG=$DOCKER_REPO/$DOCKER_IMAGE
OUT_DIR=/code/$LOCAL_OUTPUT_DIR/main
TMP_JOINED=$OUT_DIR/joined.geojson
TRANSLATIONS_DIR=/workdir/cicd/osm/translation

UPLOAD_IF_MISSING=0
if [ "$CI" == "true" ]; then
    UPLOAD_IF_MISSING=1
fi
cicd/scripts/pull_or_build.sh repo=$DOCKER_REPO image=$DOCKER_IMAGE build_dir=cicd/osm/docker/export context_dir=cicd upload_if_missing=$UPLOAD_IF_MISSING
docker run --rm -e REVISION=$REVISION -v $PWD:/code $DOCKER_TAG ogr2ogr -sql "SELECT t.geom, t.dog_friend AS dog_friend, t.lights AS lights, t.difficulty AS difficulty, COALESCE(t.closed, 0) as closed, tn.trail_name as trail_name, CASE WHEN (t.segment_end_1 IS NOT NULL AND t.segment_end_2 IS NOT NULL) THEN COALESCE(t.segment_name, tn.trail_name) || ' ' || t.segment_end_1 || ' to ' || t.segment_end_2 ELSE COALESCE(t.segment_name, tn.trail_name) END AS segment_name, COALESCE(t.classic_only, 0) as classic_only FROM trails t LEFT JOIN trail_names tn ON t.trail_id = tn.trail_id" $TMP_JOINED main-data.gpkg

docker run --rm -e REVISION=$REVISION -v $PWD:/code -e GITHUB_SHA $DOCKER_TAG ogr2osm $TMP_JOINED -f -o $OUT_DIR/bvnordic-partial.osm -t $TRANSLATIONS_DIR/nordic_tags.py
EXIT_CODE=$?

docker run --rm -e REVISION=$REVISION -v $PWD:/code $DOCKER_TAG python -m cicd.osm.routes $OUT_DIR/bvnordic-partial.osm $OUT_DIR/bvnordic.osm

exit $EXIT_CODE
