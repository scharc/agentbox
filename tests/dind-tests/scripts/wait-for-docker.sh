#!/bin/bash
# Wait for Docker daemon to be ready
# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT

set -e

TIMEOUT=${DOCKER_WAIT_TIMEOUT:-60}
INTERVAL=${DOCKER_WAIT_INTERVAL:-1}

elapsed=0

while ! docker info > /dev/null 2>&1; do
    if [ $elapsed -ge $TIMEOUT ]; then
        echo "ERROR: Docker daemon did not start within ${TIMEOUT} seconds" >&2
        exit 1
    fi

    sleep $INTERVAL
    elapsed=$((elapsed + INTERVAL))
done

exit 0
