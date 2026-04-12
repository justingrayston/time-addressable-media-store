# Time Addressable Media Store (TAMS) - Google Cloud Implementation

This repository contains the Google Cloud Platform (GCP) implementation of the BBC's Time Addressable Media Store (TAMS) API.

## Architecture
- **Runtime**: Google Cloud Run
- **Database**: Google Cloud Firestore
- **Storage**: Google Cloud Storage

## Getting Started

### Running Locally
To run the API locally for development:
1.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
2.  Set environment variables (if needed, e.g., for pointing to a real bucket):
    ```bash
    export BUCKET_NAME="your-bucket-name"
    ```
3.  Run Uvicorn:
    ```bash
    uvicorn app.main:app --reload
    ```

### Deployment with Terraform

We use a two-stage deployment process to handle the container image dependency.

#### Stage 1: Infrastructure Setup
1.  Navigate to the `terraform` directory:
    ```bash
    cd terraform
    ```
2.  Copy `terraform.tfvars.example` to `terraform.tfvars` and set the variables according to your environment:
    ```bash
    cp terraform.tfvars.example terraform.tfvars
    ```
3.  Initialize and apply Terraform:
    ```bash
    terraform init
    terraform apply
    ```
    *Note: This will deploy Cloud Run with a dummy image initially.*

#### Stage 2: Build and Deploy Real Image
1.  Return to the root directory and run the build script:
    ```bash
    cd ..
    ./build_and_push.sh
    ```
2.  Update the `image_name` in `terraform/terraform.tfvars` with the new image tag output by the script.
3.  Run Terraform apply again to update Cloud Run:
    ```bash
    cd terraform
    terraform apply
    ```

## License
Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.
