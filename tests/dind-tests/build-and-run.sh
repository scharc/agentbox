#!/bin/bash
# Build and run Boxctl DinD tests
# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
#
# Usage (from project root):
#   ./tests/dind-tests/build-and-run.sh              # Run all tests
#   ./tests/dind-tests/build-and-run.sh --integration # Run integration tests only
#   ./tests/dind-tests/build-and-run.sh -k "test_init" # Run tests matching pattern

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Go up two directories: dind-tests -> tests -> project root
PROJECT_ROOT="$(dirname "$(dirname "${SCRIPT_DIR}")")"

cd "${PROJECT_ROOT}"

# =============================================================================
# Detect if running inside a container and find host path for mounts
# =============================================================================
# When running inside a container with mounted Docker socket, we need to use
# host paths for volume mounts, not container paths.
HOST_PROJECT_ROOT="${PROJECT_ROOT}"
if [ -f /proc/self/mountinfo ]; then
    # Try to find the host path for /workspace
    HOST_PATH=$(grep " ${PROJECT_ROOT} " /proc/self/mountinfo 2>/dev/null | awk '{print $4}' | head -1)
    if [ -n "${HOST_PATH}" ]; then
        HOST_PROJECT_ROOT="${HOST_PATH}"
    fi
fi

echo "========================================"
echo "  Boxctl True DinD Test Suite"
echo "========================================"
echo ""

# Build the test image
echo "[STEP] Building True DinD test image..."
docker build -f tests/dind-tests/Dockerfile.dind -t boxctl-dind-test:latest .

echo ""

# =============================================================================
# Export host's boxctl-base image to speed up DinD builds
# =============================================================================
IMAGE_CACHE_DIR="${PROJECT_ROOT}/.dind-cache"
HOST_CACHE_DIR="${HOST_PROJECT_ROOT}/.dind-cache"
IMAGE_TARBALL="${IMAGE_CACHE_DIR}/boxctl-base.tar"

# Check if we have boxctl-base:latest on the host
if docker image inspect boxctl-base:latest > /dev/null 2>&1; then
    mkdir -p "${IMAGE_CACHE_DIR}"

    # Get the image ID to check if cache is still valid
    HOST_IMAGE_ID=$(docker image inspect boxctl-base:latest --format '{{.Id}}')
    CACHE_ID_FILE="${IMAGE_CACHE_DIR}/boxctl-base.id"

    # Only re-export if image changed
    if [ -f "${CACHE_ID_FILE}" ] && [ -f "${IMAGE_TARBALL}" ]; then
        CACHED_ID=$(cat "${CACHE_ID_FILE}")
        if [ "${HOST_IMAGE_ID}" = "${CACHED_ID}" ]; then
            echo "[INFO] Using cached boxctl-base image (unchanged)"
        else
            echo "[STEP] Exporting boxctl-base:latest from host (image changed)..."
            docker save boxctl-base:latest -o "${IMAGE_TARBALL}"
            echo "${HOST_IMAGE_ID}" > "${CACHE_ID_FILE}"
        fi
    else
        echo "[STEP] Exporting boxctl-base:latest from host..."
        docker save boxctl-base:latest -o "${IMAGE_TARBALL}"
        echo "${HOST_IMAGE_ID}" > "${CACHE_ID_FILE}"
    fi
else
    echo "[INFO] No boxctl-base:latest on host, DinD will build from scratch"
fi

echo ""
echo "[STEP] Running tests..."
echo ""

# Run the tests with --privileged (required for True DinD)
# Mount credentials if available
MOUNT_ARGS=""

if [ -d "$HOME/.claude" ]; then
    MOUNT_ARGS="${MOUNT_ARGS} -v $HOME/.claude:/home/testuser/.claude:ro"
fi

if [ -d "$HOME/.codex" ]; then
    MOUNT_ARGS="${MOUNT_ARGS} -v $HOME/.codex:/home/testuser/.codex:ro"
fi

# Mount the cached image directory if it exists (use host path for Docker)
if [ -d "${IMAGE_CACHE_DIR}" ] && [ -f "${IMAGE_TARBALL}" ]; then
    MOUNT_ARGS="${MOUNT_ARGS} -v ${HOST_CACHE_DIR}:/cache:ro"
    echo "[INFO] Mounting image cache from ${HOST_CACHE_DIR}"
fi

# Run the container
# shellcheck disable=SC2086
docker run --privileged --rm \
    ${MOUNT_ARGS} \
    -v "${PROJECT_ROOT}/test-results:/test-results" \
    boxctl-dind-test:latest \
    "$@"
