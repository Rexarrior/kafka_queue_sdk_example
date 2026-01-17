#!/bin/bash
source ./scripts/common.sh

if [ -z "$1" ]; then
    echo "Busket name:"
    read userInput
    bucket_name=$userInput
else
    bucket_name=$1
fi
echo "In bucket $bucket_name on $s3_endpoint there are files:"
aws s3api create-bucket --bucket $bucket_name --endpoint=$s3_endpoint
aws s3 ls s3://$bucket_name --endpoint=$s3_endpoint --recursive --human-readable --summarize
