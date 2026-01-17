#!/bin/bash
source ./scripts/common.sh

if [ -z "$1" ]; then
    echo "Busket name:"
    read userInput
    bucket_name=$userInput
else
    bucket_name=$1
fi
echo "Create busket $bucket_name on $s3_endpoint"
aws s3api create-bucket --bucket $bucket_name --endpoint=$s3_endpoint
