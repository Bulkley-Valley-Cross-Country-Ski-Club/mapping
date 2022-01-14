#!/bin/bash

pushd $(dirname $0)/../../..

UPLOAD_IF_MISSING=0
if [ "$CI" == "true" ]; then
    UPLOAD_IF_MISSING=1
fi
cicd/scripts/pull_or_build.sh repo=tomfumb image=bvnordic-imagery-updater:2 build_dir=cicd/imagery/docker context_dir=cicd/imagery upload_if_missing=$UPLOAD_IF_MISSING
docker run --rm -v $PWD:/code -w /code tomfumb/bvnordic-imagery-updater:2 python3 -m cicd.imagery.stadium