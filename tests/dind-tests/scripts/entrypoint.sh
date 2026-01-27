#!/bin/bash
# Boxctl DinD Test Container Entrypoint
# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
#
# This script starts the Docker daemon and then runs the provided command.
# It ensures dockerd is fully ready before proceeding.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $*"; }

echo ""
echo "========================================"
echo "  Boxctl True DinD Test Container"
echo "========================================"
echo ""

# =============================================================================
# Start Docker daemon
# =============================================================================

log_step "Starting Docker daemon..."

# Clean up any stale pid files
rm -f /var/run/docker.pid /var/run/docker/containerd/containerd.pid 2>/dev/null || true

# Start dockerd in background
dockerd > /var/log/dockerd.log 2>&1 &
DOCKERD_PID=$!

# Wait for Docker to be ready
log_step "Waiting for Docker daemon to be ready..."
if ! /usr/local/bin/wait-for-docker.sh; then
    log_error "Docker daemon failed to start!"
    log_error "dockerd log:"
    cat /var/log/dockerd.log
    exit 1
fi

log_info "Docker daemon is ready (PID: ${DOCKERD_PID})"
docker info --format '{{.ServerVersion}}' | xargs -I{} echo -e "${GREEN}[INFO]${NC} Docker version: {}"

# =============================================================================
# Pre-pull or build the boxctl base image
# =============================================================================

log_step "Checking for boxctl-base:latest image..."

# First check if we have a cached image from the host
if [ -f /cache/boxctl-base.tar ]; then
    log_info "Loading boxctl-base:latest from host cache..."
    if docker load -i /cache/boxctl-base.tar; then
        log_info "Loaded boxctl-base:latest from cache"
    else
        log_warn "Failed to load cached image, will build from source"
    fi
fi

# Check if image exists now (either loaded or already present)
if ! docker image inspect boxctl-base:latest > /dev/null 2>&1; then
    log_info "boxctl-base:latest not found, building from source..."

    # Build the base image inside the DinD container
    if [ -f /build/Dockerfile.base ]; then
        docker build -f /build/Dockerfile.base -t boxctl-base:latest /build
        log_info "Built boxctl-base:latest image"
    else
        log_warn "Dockerfile.base not found, tests requiring boxctl image may fail"
    fi
else
    log_info "boxctl-base:latest image available"
fi

# =============================================================================
# Set up test environment
# =============================================================================

log_step "Setting up test environment..."

# Ensure test directories exist and are writable
mkdir -p "${TEST_WORKSPACE}" "${TEST_RESULTS}"
chown -R testuser:testuser "${TEST_WORKSPACE}" "${TEST_RESULTS}" 2>/dev/null || true

# Check for auth files
if [ -d /home/testuser/.claude ] && [ -n "$(ls -A /home/testuser/.claude 2>/dev/null)" ]; then
    log_info "Claude credentials found"
else
    log_warn "Claude credentials not mounted - agent tests will be skipped"
    log_warn "Mount with: -v ~/.claude:/home/testuser/.claude:ro"
fi

if [ -d /home/testuser/.codex ] && [ -n "$(ls -A /home/testuser/.codex 2>/dev/null)" ]; then
    log_info "Codex credentials found"
else
    log_warn "Codex credentials not mounted - codex tests will be skipped"
fi

# =============================================================================
# Build command to run
# =============================================================================

# Default command if none provided
CMD=("$@")

# If no args or first arg looks like a test selector option, use pytest
if [[ ${#CMD[@]} -eq 0 ]]; then
    CMD=("python3" "-m" "pytest" "dind-tests/" "-v" "--tb=short")
elif [[ "${CMD[0]}" == --* ]]; then
    # Arguments like --integration, --unit, -k, etc. need to be passed to pytest
    # Map our custom options to pytest paths
    case "${CMD[0]}" in
        --integration)
            CMD=("python3" "-m" "pytest" "dind-tests/integration/" "-v" "--tb=short" "${CMD[@]:1}")
            ;;
        --unit)
            CMD=("python3" "-m" "pytest" "dind-tests/unit/" "-v" "--tb=short" "${CMD[@]:1}")
            ;;
        --chains)
            CMD=("python3" "-m" "pytest" "dind-tests/chains/" "-v" "--tb=short" "${CMD[@]:1}")
            ;;
        --e2e)
            CMD=("python3" "-m" "pytest" "dind-tests/e2e/" "-v" "--tb=short" "${CMD[@]:1}")
            ;;
        --all)
            CMD=("python3" "-m" "pytest" "dind-tests/" "-v" "--tb=short" "${CMD[@]:1}")
            ;;
        -*)
            # Other pytest options like -k, -x, etc.
            CMD=("python3" "-m" "pytest" "dind-tests/" "-v" "--tb=short" "${CMD[@]}")
            ;;
    esac
fi

log_step "Running: ${CMD[*]}"
echo ""

# Run the command as testuser for realistic testing
# (boxctl is typically run by a regular user, not root)
exec sudo -u testuser -E \
    HOME=/home/testuser \
    AGENTBOX_DIR="${AGENTBOX_DIR}" \
    TEST_WORKSPACE="${TEST_WORKSPACE}" \
    TEST_RESULTS="${TEST_RESULTS}" \
    PYTHONPATH="${PYTHONPATH}" \
    XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR}" \
    PATH="${PATH}" \
    "${CMD[@]}"
