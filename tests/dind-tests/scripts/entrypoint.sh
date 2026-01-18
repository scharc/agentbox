#!/bin/bash
# Agentbox DinD Test Container Entrypoint
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
echo "  Agentbox True DinD Test Container"
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
# Pre-pull or build the agentbox base image
# =============================================================================

log_step "Checking for agentbox-base:latest image..."

# First try to pull from registry (if available)
if ! docker image inspect agentbox-base:latest > /dev/null 2>&1; then
    log_info "agentbox-base:latest not found, building from source..."

    # Build the base image inside the DinD container
    if [ -f /build/Dockerfile.base ]; then
        docker build -f /build/Dockerfile.base -t agentbox-base:latest /build
        log_info "Built agentbox-base:latest image"
    else
        log_warn "Dockerfile.base not found, tests requiring agentbox image may fail"
    fi
else
    log_info "agentbox-base:latest image already available"
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
# Run the provided command
# =============================================================================

log_step "Running: $*"
echo ""

# Run the command as testuser for realistic testing
# (agentbox is typically run by a regular user, not root)
exec sudo -u testuser -E \
    HOME=/home/testuser \
    AGENTBOX_DIR="${AGENTBOX_DIR}" \
    TEST_WORKSPACE="${TEST_WORKSPACE}" \
    TEST_RESULTS="${TEST_RESULTS}" \
    PYTHONPATH="${PYTHONPATH}" \
    XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR}" \
    PATH="${PATH}" \
    "$@"
