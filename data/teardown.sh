#!/bin/bash
set -e

# Load environment variables
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
else
    echo ".env file not found"
    exit 1
fi

# Check if required variables are set
if [ -z "$MOUNT_POINT" ]; then
    echo "MOUNT_POINT is not set in .env file"
    exit 1
fi

# Function to check if the mount point is busy
is_mount_busy() {
    lsof "$MOUNT_POINT" > /dev/null 2>&1
    return $?
}

# Unmount the bucket
echo "Attempting to unmount $MOUNT_POINT..."

if mountpoint -q "$MOUNT_POINT"; then
    if is_mount_busy; then
        echo "Mount point is busy. Attempting to unmount forcefully..."
        fusermount -uz "$MOUNT_POINT"
    else
        fusermount -u "$MOUNT_POINT"
    fi

    # Check if unmount was successful
    if ! mountpoint -q "$MOUNT_POINT"; then
        echo "Bucket successfully unmounted from $MOUNT_POINT"
    else
        echo "Failed to unmount $MOUNT_POINT. You may need to close any open files or processes using this mount point."
        exit 1
    fi
else
    echo "$MOUNT_POINT is not currently mounted."
fi

# Optionally, remove the mount point directory
read -p "Do you want to remove the mount point directory? (y/n) " -n 1 -r
echo    # Move to a new line
if [[ $REPLY =~ ^[Yy]$ ]]
then
    if [ -d "$MOUNT_POINT" ]; then
        rm -rf "$MOUNT_POINT"
        echo "Mount point directory removed."
    else
        echo "Mount point directory does not exist."
    fi
fi

echo "Teardown complete."