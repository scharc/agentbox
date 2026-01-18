#!/bin/bash
# Build and run Agentbox DinD tests
# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
#
# Usage:
#   ./dind-tests/build-and-run.sh              # Run all tests
#   ./dind-tests/build-and-run.sh --integration # Run integration tests only
#   ./dind-tests/build-and-run.sh -k "test_init" # Run tests matching pattern

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "${SCRIPT_DIR}")"

cd "${PROJECT_ROOT}"

echo "========================================"
echo "  Agentbox True DinD Test Suite"
echo "========================================"
echo ""

# Build the test image
echo "[STEP] Building True DinD test image..."
docker build -f dind-tests/Dockerfile.dind -t agentbox-dind-test:latest .

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

# Run the container
# shellcheck disable=SC2086
docker run --privileged --rm \
    ${MOUNT_ARGS} \
    -v "${PROJECT_ROOT}/test-results:/test-results" \
    agentbox-dind-test:latest \
    "$@"
