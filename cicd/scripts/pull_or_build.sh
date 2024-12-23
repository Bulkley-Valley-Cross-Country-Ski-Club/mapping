#!/bin/bash

for ARGUMENT in "$@"
do
    KEY=$(echo $ARGUMENT | cut -f1 -d=)
    VALUE=$(echo $ARGUMENT | cut -f2 -d=)   
    case "$KEY" in
            repo)              REPO=${VALUE} ;;
            image)             IMAGE=${VALUE} ;;
            build_dir)         BUILD_DIR=${VALUE} ;;
            context_dir)       CONTEXT_DIR=${VALUE} ;;
            upload_if_missing) UPLOAD_IF_MISSING=${VALUE} ;;
            *)   
    esac    
done

if docker pull $REPO/$IMAGE; then
    echo "$REPO/$IMAGE successfully pulled from registry"
else
    echo "$REPO/$IMAGE not available in registry, building from $BUILD_DIR"
    docker build -t $REPO/$IMAGE -f $BUILD_DIR/Dockerfile $CONTEXT_DIR
    EXIT_CODE=$?    # not important enough to fail a build if the remainder fails
    if [ "$UPLOAD_IF_MISSING" == "1" ]; then
        echo "logging in to Docker Hub"
        echo $PAT_DOCKER_HUB | docker login --username $REPO --password-stdin
        echo "pushing image"
        docker push $REPO/$IMAGE
        echo "logging out"
        docker logout
    fi
fi

exit $EXIT_CODE