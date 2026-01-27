#!/bin/bash
# Boxctl DinD Test Runner
# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
#
# This script builds and runs the DinD test container with various options.
#
# Usage:
#   ./run-dind-tests.sh                    # Run all tests
#   ./run-dind-tests.sh test_full_workflow # Run specific test file
#   ./run-dind-tests.sh -k "TestPhase1"    # Run tests matching pattern
#   ./run-dind-tests.sh --with-auth        # Run with Claude/Codex auth mounted

set -e

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_step() { echo -e "${BLUE}[====]${NC} $*"; }

# Default options
IMAGE_NAME="boxctl-dind-test:latest"
CONTAINER_NAME="boxctl-dind-test-runner"
WITH_AUTH=false
BUILD_ONLY=false
REBUILD=false
REBUILD_BASE=false
INTERACTIVE=false
PRESERVE_CONTAINER=false
TEST_ARGS=""
PYTEST_ARGS="-v --tb=short"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --with-auth)
            WITH_AUTH=true
            shift
            ;;
        --build-only)
            BUILD_ONLY=true
            shift
            ;;
        --rebuild)
            REBUILD=true
            shift
            ;;
        --rebuild-base)
            REBUILD_BASE=true
            REBUILD=true
            shift
            ;;
        --interactive|-i)
            INTERACTIVE=true
            shift
            ;;
        --preserve)
            PRESERVE_CONTAINER=true
            shift
            ;;
        --all)
            TEST_ARGS="dind-tests/"
            shift
            ;;
        --workflow)
            TEST_ARGS="dind-tests/test_full_workflow.py"
            shift
            ;;
        --phase)
            TEST_ARGS="dind-tests/test_full_workflow.py -k \"TestPhase$2\""
            shift 2
            ;;
        -k)
            PYTEST_ARGS="${PYTEST_ARGS} -k \"$2\""
            shift 2
            ;;
        -x)
            PYTEST_ARGS="${PYTEST_ARGS} -x"
            shift
            ;;
        --html)
            PYTEST_ARGS="${PYTEST_ARGS} --html=/test-results/report.html --self-contained-html"
            shift
            ;;
        --help|-h)
            echo "Boxctl DinD Test Runner"
            echo ""
            echo "Usage: $0 [OPTIONS] [TEST_FILE|TEST_PATTERN]"
            echo ""
            echo "Options:"
            echo "  --with-auth      Mount Claude/Codex credentials for auth tests"
            echo "  --build-only     Only build the DinD image, don't run tests"
            echo "  --rebuild        Force rebuild the DinD image"
            echo "  --rebuild-base   Force rebuild both base and DinD images"
            echo "  --interactive    Run container interactively (shell)"
            echo "  --preserve       Don't remove container after tests"
            echo ""
            echo "Test Selection:"
            echo "  --all            Run all DinD tests"
            echo "  --workflow       Run only test_full_workflow.py"
            echo "  --phase N        Run TestPhaseN tests (e.g., --phase 1)"
            echo "  -k PATTERN       Run tests matching pattern"
            echo "  -x               Stop on first failure"
            echo "  --html           Generate HTML report"
            echo ""
            echo "Examples:"
            echo "  $0                                    # Run all tests"
            echo "  $0 --workflow                         # Run full workflow tests"
            echo "  $0 --phase 2                          # Run Phase 2 tests (Project Lifecycle)"
            echo "  $0 -k 'test_start'                    # Run tests with 'test_start' in name"
            echo "  $0 --with-auth --workflow             # Run with auth for agent tests"
            echo "  $0 --interactive                      # Interactive shell for debugging"
            echo ""
            echo "Test Phases:"
            echo "  1  - Base Image"
            echo "  2  - Project Lifecycle (init, start, stop, list, info)"
            echo "  3  - Session Management"
            echo "  4  - Workspace Mounts"
            echo "  5  - Worktree Commands"
            echo "  6  - Port Forwarding"
            echo "  7  - MCP Servers"
            echo "  8  - Skills"
            echo "  9  - Packages"
            echo "  10 - Docker Socket"
            echo "  11 - Network"
            echo "  12 - Devices"
            echo "  13 - Rebase"
            echo "  14 - Multi-Session"
            echo "  15 - Multi-Project"
            echo "  16 - Multi-Agent (help commands)"
            echo "  16b - Agent Launch (tmux sessions)"
            echo "  16c - Agent Launch with Auth"
            echo "  17 - Service Daemon"
            echo "  18 - Config Migration"
            echo "  19 - Quick Commands"
            echo "  20 - Fix-Terminal"
            echo "  21 - Cleanup"
            echo "  Integration - Full workflow scenarios"
            exit 0
            ;;
        *)
            # Treat as test file or additional pytest args
            if [[ $1 == *.py ]] || [[ $1 == Test* ]] || [[ $1 == test_* ]]; then
                TEST_ARGS="dind-tests/$1"
            else
                PYTEST_ARGS="${PYTEST_ARGS} $1"
            fi
            shift
            ;;
    esac
done

# Set default test target
if [ -z "$TEST_ARGS" ]; then
    TEST_ARGS="dind-tests/"
fi

echo ""
echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║         Boxctl DinD Test Runner                          ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Step 1: Ensure base image exists
log_step "Checking base image..."

BASE_IMAGE="boxctl-base:latest"
if [ "$REBUILD_BASE" = true ] || ! docker image inspect "$BASE_IMAGE" > /dev/null 2>&1; then
    log_info "Building base image: $BASE_IMAGE..."
    cd "$REPO_ROOT"
    docker build -f Dockerfile.base -t "$BASE_IMAGE" .
else
    log_info "Using existing base image: $BASE_IMAGE"
fi

# Step 2: Build DinD test image if needed
log_step "Checking DinD test image..."

if [ "$REBUILD" = true ] || ! docker image inspect "$IMAGE_NAME" > /dev/null 2>&1; then
    log_info "Building DinD test image (extends base image)..."
    cd "$REPO_ROOT"
    docker build -f tests/dind-tests/Dockerfile.dind -t "$IMAGE_NAME" .
else
    log_info "Using existing image: $IMAGE_NAME"
fi

if [ "$BUILD_ONLY" = true ]; then
    log_info "Build complete. Use --help to see run options."
    exit 0
fi

# Step 3: Prepare volume mounts
VOLUMES=""
VOLUMES="${VOLUMES} -v ${REPO_ROOT}/tests/dind-tests:/build/dind-tests:ro"

# Mount auth if requested
if [ "$WITH_AUTH" = true ]; then
    if [ -d "$HOME/.claude" ]; then
        VOLUMES="${VOLUMES} -v $HOME/.claude:/home/testuser/.claude:ro"
        log_info "Mounting Claude credentials"
    else
        log_warn "~/.claude not found, auth tests will be skipped"
    fi

    if [ -d "$HOME/.codex" ]; then
        VOLUMES="${VOLUMES} -v $HOME/.codex:/home/testuser/.codex:ro"
        log_info "Mounting Codex credentials"
    fi

    if [ -d "$HOME/.gemini" ]; then
        VOLUMES="${VOLUMES} -v $HOME/.gemini:/home/testuser/.gemini:ro"
        log_info "Mounting Gemini credentials"
    fi
fi

# Results directory
RESULTS_DIR="${REPO_ROOT}/tests/dind-tests/results"
mkdir -p "$RESULTS_DIR"
VOLUMES="${VOLUMES} -v ${RESULTS_DIR}:/test-results"

# Step 4: Clean up old container
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    log_info "Removing existing container..."
    docker rm -f "$CONTAINER_NAME" > /dev/null 2>&1 || true
fi

# Step 5: Run tests
log_step "Running tests..."
echo ""
echo -e "${BLUE}Test target:${NC} $TEST_ARGS"
echo -e "${BLUE}Pytest args:${NC} $PYTEST_ARGS"
echo ""

# Build Docker run command
RUN_CMD="docker run"
RUN_CMD="${RUN_CMD} --privileged"
RUN_CMD="${RUN_CMD} --name ${CONTAINER_NAME}"
RUN_CMD="${RUN_CMD} ${VOLUMES}"

if [ "$PRESERVE_CONTAINER" = false ]; then
    RUN_CMD="${RUN_CMD} --rm"
fi

if [ "$INTERACTIVE" = true ]; then
    log_info "Starting interactive shell..."
    ${RUN_CMD} -it "$IMAGE_NAME" /bin/bash
else
    # Run pytest
    ${RUN_CMD} "$IMAGE_NAME" pytest ${TEST_ARGS} ${PYTEST_ARGS}
    EXIT_CODE=$?

    echo ""
    if [ $EXIT_CODE -eq 0 ]; then
        echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║                    ALL TESTS PASSED                        ║${NC}"
        echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    else
        echo -e "${RED}╔════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${RED}║                    TESTS FAILED                            ║${NC}"
        echo -e "${RED}╚════════════════════════════════════════════════════════════╝${NC}"
    fi

    # Show results location if HTML report was generated
    if [ -f "${RESULTS_DIR}/report.html" ]; then
        echo ""
        log_info "HTML report: ${RESULTS_DIR}/report.html"
    fi

    exit $EXIT_CODE
fi
