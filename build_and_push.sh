#!/bin/bash
# This script builds and pushes the TAMS API container to Artifact Registry.

set -e

# Initialize variables with defaults
REGION="europe-west1"
REPO_NAME="tams-repo"
PROJECT_ID=""

# Read variables from terraform/terraform.tfvars if it exists
if [ -f terraform/terraform.tfvars ]; then
    # Use || true to prevent set -e from failing if grep finds nothing
    PROJECT_ID=$(grep project_id terraform/terraform.tfvars | cut -d'=' -f2 | tr -d ' "' || true)
    
    TF_REGION=$(grep region terraform/terraform.tfvars | cut -d'=' -f2 | tr -d ' "' || true)
    [ -n "$TF_REGION" ] && REGION=$TF_REGION
    
    TF_REPO=$(grep repository_name terraform/terraform.tfvars | cut -d'=' -f2 | tr -d ' "' || true)
    [ -n "$TF_REPO" ] && REPO_NAME=$TF_REPO
fi

# Fallback for PROJECT_ID if not set in tfvars
if [ -z "$PROJECT_ID" ]; then
    PROJECT_ID=$(gcloud config get-value project)
fi

echo "Using Project: $PROJECT_ID"
echo "Using Region: $REGION"
echo "Using Repo: $REPO_NAME"

IMAGE_TAG="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/tams-api:latest"

echo "Building and pushing image: $IMAGE_TAG"

gcloud builds submit --tag $IMAGE_TAG .

echo "Done! Now update image_name in terraform/terraform.tfvars to $IMAGE_TAG and run terraform apply again."
