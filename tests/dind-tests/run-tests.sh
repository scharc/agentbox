#!/bin/bash
# Boxctl DinD Test Runner
# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
#
# This script runs pytest inside the True DinD container.
# It expects Docker to already be running (started by entrypoint.sh).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "${SCRIPT_DIR}")"
TEST_WORKSPACE="${TEST_WORKSPACE:-/test-workspace}"
TEST_RESULTS="${TEST_RESULTS:-/test-results}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $*"; }

# Check Docker is available
check_docker() {
    log_step "Checking Docker availability..."
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker is not available!"
        log_error "This script should be run inside the True DinD container."
        exit 1
    fi
    log_info "Docker is available"
}

# Clean up leftover test resources
cleanup_test_resources() {
    log_step "Cleaning up previous test resources..."

    # Remove test containers
    local containers
    containers=$(docker ps -a --filter "name=agentbox-test-" --format "{{.Names}}" 2>/dev/null || true)
    if [[ -n "$containers" ]]; then
        echo "$containers" | xargs -r docker rm -f 2>/dev/null || true
        log_info "Removed test containers"
    fi

    # Remove test networks
    local networks
    networks=$(docker network ls --filter "name=test-net-" --format "{{.Name}}" 2>/dev/null || true)
    if [[ -n "$networks" ]]; then
        echo "$networks" | xargs -r docker network rm 2>/dev/null || true
        log_info "Removed test networks"
    fi

    # Clean test workspace
    if [[ -d "${TEST_WORKSPACE}" ]]; then
        rm -rf "${TEST_WORKSPACE:?}"/* 2>/dev/null || true
        log_info "Cleaned test workspace"
    fi

    log_info "Cleanup complete"
}

# Parse arguments
parse_args() {
    local test_target=""
    local pytest_args=()

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --all)
                test_target="${SCRIPT_DIR}"
                shift
                ;;
            --unit)
                test_target="${SCRIPT_DIR}/unit"
                shift
                ;;
            --integration)
                test_target="${SCRIPT_DIR}/integration"
                shift
                ;;
            --chains)
                test_target="${SCRIPT_DIR}/chains"
                shift
                ;;
            --e2e)
                test_target="${SCRIPT_DIR}/e2e"
                shift
                ;;
            -*)
                pytest_args+=("$1")
                shift
                ;;
            *)
                test_target="$1"
                shift
                ;;
        esac
    done

    # Default to all tests
    if [[ -z "$test_target" ]]; then
        test_target="${SCRIPT_DIR}"
    fi

    echo "${test_target}|${pytest_args[*]:-}"
}

# Run tests
run_tests() {
    local test_target="$1"
    local extra_args="$2"

    log_step "Running tests: ${test_target}"

    mkdir -p "${TEST_RESULTS}"

    # Ensure helpers module is in path
    export PYTHONPATH="${PROJECT_ROOT}:${SCRIPT_DIR}:${PYTHONPATH:-}"

    local pytest_cmd=(
        python3 -m pytest
        "${test_target}"
        -v
        --tb=short
        --timeout=300
        "--junitxml=${TEST_RESULTS}/junit.xml"
        "--html=${TEST_RESULTS}/report.html"
        --self-contained-html
    )

    # Add json report if available
    if python3 -c "import pytest_json_report" 2>/dev/null; then
        pytest_cmd+=(
            --json-report
            "--json-report-file=${TEST_RESULTS}/report.json"
        )
    fi

    # Add extra args
    if [[ -n "$extra_args" ]]; then
        # shellcheck disable=SC2206
        pytest_cmd+=($extra_args)
    fi

    log_info "Command: ${pytest_cmd[*]}"
    echo ""

    "${pytest_cmd[@]}"
}

# Main
main() {
    echo ""
    echo "========================================"
    echo "  Boxctl DinD Test Runner"
    echo "========================================"
    echo ""

    check_docker
    cleanup_test_resources

    # Parse arguments
    local parsed
    parsed=$(parse_args "$@")
    local test_target="${parsed%%|*}"
    local extra_args="${parsed##*|}"

    # Trap for cleanup on exit
    trap cleanup_test_resources EXIT

    # Run tests
    local exit_code=0
    run_tests "$test_target" "$extra_args" || exit_code=$?

    echo ""
    if [[ $exit_code -eq 0 ]]; then
        log_info "========================================"
        log_info "  All tests passed!"
        log_info "========================================"
    else
        log_error "========================================"
        log_error "  Some tests failed (exit code: ${exit_code})"
        log_error "========================================"
    fi

    log_info "Test results: ${TEST_RESULTS}"

    return $exit_code
}

main "$@"
