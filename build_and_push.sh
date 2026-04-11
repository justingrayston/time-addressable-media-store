#!/bin/bash
# This script builds and pushes the TAMS API container to Artifact Registry.

set -e

# Read variables from terraform.tfvars if it exists
if [ -f terraform/terraform.tfvars ]; then
    PROJECT_ID=$(grep project_id terraform/terraform.tfvars | cut -d'=' -f2 | tr -d ' "')
    REGION=$(grep region terraform/terraform.tfvars | cut -d'=' -f2 | tr -d ' "')
    REPO_NAME=$(grep repository_name terraform/terraform.tfvars | cut -d'=' -f2 | tr -d ' "')
fi

# Fallback to defaults if not found
PROJECT_ID=${PROJECT_ID:-$(gcloud config get-value project)}
REGION=${REGION:-"europe-west1"}
REPO_NAME=${REPO_NAME:-"tams-repo"}

echo "Using Project: $PROJECT_ID"
echo "Using Region: $REGION"
echo "Using Repo: $REPO_NAME"

IMAGE_TAG="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/tams-api:latest"

echo "Building and pushing image: $IMAGE_TAG"

gcloud builds submit --tag $IMAGE_TAG .

echo "Done! Now update image_name in terraform/terraform.tfvars to $IMAGE_TAG and run terraform apply again."
