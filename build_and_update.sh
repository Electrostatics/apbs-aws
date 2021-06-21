#!/usr/bin/bash

show_help() {
    echo "SYNTAX:   ./build_and_update.sh COMMAND"
    echo ""
    echo "COMMANDS:"
    echo "    all      Builds and updates all services and containers used in deployment."
    echo ""
    echo "    changed  Builds and updates services with files modified since the last successful build."
    echo "             The files changed are determined via git diff of the correstponding commit IDs."
    echo ""
    exit 1
}

build_api_service() {
    echo "Updating Lambda function (API Service)"
    cd $CODEBUILD_SRC_DIR/lambda_services; zip -r /tmp/id.zip api_service
    aws lambda update-function-code --function-name apbs-$IMAGE_TAG-id-L  --publish --zip-file fileb:///tmp/id.zip
}

build_job_service() {
    echo "Updating Lambda function (Job Service)"
    cd $CODEBUILD_SRC_DIR/lambda_services; zip -r /tmp/job.zip job_service
    aws lambda update-function-code --function-name apbs-$IMAGE_TAG-job-L --publish --zip-file fileb:///tmp/job.zip
}

build_docker() {    
    echo "Building the Docker image..."
    docker build -t $IMAGE_REPO_NAME:main.base $CODEBUILD_SRC_DIR/src/docker
    docker tag $IMAGE_REPO_NAME:main.base    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/$IMAGE_REPO_NAME:$IMAGE_TAG

    echo Pushing the Docker image...
    docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/$IMAGE_REPO_NAME:$IMAGE_TAG
}


build_changed() {
    echo "Building services and containers modified since last successful build."
    api_service_changed=0
    job_service_changed=0
    docker_changed=0

    git diff --name-only $CODEBUILD_RESOLVED_SOURCE_VERSION $LAST_SUCCESSFUL_COMMIT_ID | while read file_path || [[ -n $file_path ]];
    do
        if [[ $file_path == src/docker/* ]] && [[ $docker_changed -ne 1 ]]
        then
            docker_changed=1
            build_docker
        fi

        if [[ $file_path == lambda_services/job_service/* ]] && [[ $job_service_changed -ne 1 ]]
        then
            job_service_changed=1
            build_job_service
        fi

        if [[ $file_path == lambda_services/api_service/* ]] && [[ $api_service_changed -ne 1 ]] # condition to check if path in ./lambda_services/api_service/ directory
        then
            api_service_changed=1
            build_api_service
        fi
    done
}

build_all() {
    echo "Building all services and containers"
    build_docker
    build_job_service
    build_api_service
}

cli_argument="$1"

if [[ -z $cli_argument ]] ; then
    echo "No argument provided."
    show_help

else
    case $cli_argument in
        all)
            build_all
            ;;
        changed)
            build_changed
            ;;
        *)
            show_help
            ;;
    esac
fi
