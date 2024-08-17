#!/bin/bash

# Login to Google Cloud Services
echo "Logging into Google Cloud Services..."
gcloud auth application-default login

# Check if login was successful
if [ $? -ne 0 ]; then
    echo "Failed to login to Google Cloud Services. Exiting."
    exit 1
fi

echo "Successfully logged into Google Cloud Services."

# Create the directory for mounting the GCS bucket
echo "Creating directory for mounting GCS bucket..."
mkdir -p data

# Attempt to mount GCS bucket using gcsfuse
echo "Attempting to mount GCS bucket..."
gcsfuse --debug_gcs --debug_fuse --implicit-dirs external_validation data

# Check if mount was successful
if [ $? -ne 0 ]; then
    echo "Failed to mount GCS bucket. Please check your permissions and bucket name."
    exit 1
fi

echo "Successfully mounted GCS bucket."