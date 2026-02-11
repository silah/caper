#!/bin/bash
# Build script for Caper Selenium Test Builder
# This script downloads drivers, cleans old images, and builds the container
#
# Usage:
#   ./builder.sh              # Build with cache (faster)
#   ./builder.sh --no-cache   # Build without cache (clean build)

set -e  # Exit on error

# Parse arguments
BUILD_FLAGS=""
if [[ "$1" == "--no-cache" ]]; then
    BUILD_FLAGS="--no-cache"
    echo "========================================"
    echo "Caper Docker Build Script (NO CACHE)"
    echo "========================================"
elif [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
    echo "Usage: ./builder.sh [--no-cache]"
    echo ""
    echo "Options:"
    echo "  --no-cache    Build without using Docker cache (slower, clean build)"
    echo "  --help, -h    Show this help message"
    exit 0
else
    echo "========================================"
    echo "Caper Docker Build Script"
    echo "========================================"
fi
echo ""

# Step 1: Download browser drivers
echo "[1/3] Downloading browser drivers..."
python3 download_drivers.py
if [ $? -ne 0 ]; then
    echo "✗ Failed to download drivers"
    exit 1
fi
echo ""

# Step 2: Clean up old Docker images
echo "[2/3] Cleaning up old Docker images..."
echo "Stopping and removing old container..."
docker compose down 2>/dev/null || true

echo "Removing old images for caper..."
docker images | grep caper | awk '{print $3}' | xargs -r docker rmi -f 2>/dev/null || true

echo "Pruning dangling images..."
docker image prune -f

echo ""

# Step 3: Build new image
echo "[3/3] Building Docker image..."
if [[ -n "$BUILD_FLAGS" ]]; then
    echo "Using flags: $BUILD_FLAGS"
    docker compose build $BUILD_FLAGS
else
    docker compose build
fi

echo ""
echo "========================================"
echo "✓ Build completed successfully!"
echo "========================================"
echo ""
echo "To start the application, run:"
echo "  docker compose up -d"
echo ""
