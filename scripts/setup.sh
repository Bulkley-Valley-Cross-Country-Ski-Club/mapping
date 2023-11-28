#!/bin/bash

set -e

pip install -r requirements-dev.txt
pip install -r cicd/compare/requirements-pr.txt
pip install -r cicd/compare/requirements-detect.txt
pip install -r cicd/export/requirements.txt
pip install -r cicd/upload/requirements.txt
pip install -r cicd/osm/requirements.txt
pip install -r cicd/imagery/requirements.txt
pre-commit install
echo "collecting satellite imagery for Stadium"
cicd/imagery/scripts/update-all.sh