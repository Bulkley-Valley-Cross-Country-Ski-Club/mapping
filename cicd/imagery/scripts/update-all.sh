#!/bin/bash

pushd $(dirname $0)/../../..

cicd/imagery/scripts/update-network-overview.sh
cicd/imagery/scripts/update-stadium.sh
