#!/bin/bash
# Container Health Check Script
#
# Checks that all required services are running:
# 1. Initialization complete (status file shows "ready")
# 2. Container client (for SSH tunnel communication)
# 3. MCP servers (for agent tools)
#
# Exit codes:
#   0 = Healthy
#   1 = Unhealthy

set -e

# Check if initialization is complete
STATUS_FILE="/tmp/container-status"
if [[ -f "${STATUS_FILE}" ]]; then
    STATUS=$(cut -d'|' -f1 < "${STATUS_FILE}")
    if [[ "${STATUS}" != "ready" ]]; then
        echo "UNHEALTHY: Container initializing (${STATUS})"
        exit 1
    fi
else
    # Status file doesn't exist yet - init hasn't started or is very early
    echo "UNHEALTHY: Container initialization not started"
    exit 1
fi

# Check container client (only required if SSH socket exists)
# The socket is mounted from host - check multiple locations
find_ssh_socket() {
    # Check env var first
    if [[ -S "${BOXCTL_SSH_SOCKET:-}" ]]; then
        echo "${BOXCTL_SSH_SOCKET}"
        return 0
    fi
    # Check user-specific runtime dir (mounted from host)
    local uid_socket
    uid_socket="/run/user/$(id -u)/boxctld/ssh.sock"
    if [[ -S "${uid_socket}" ]]; then
        echo "${uid_socket}"
        return 0
    fi
    # Check alternative mount location
    if [[ -S "/run/boxctld/ssh.sock" ]]; then
        echo "/run/boxctld/ssh.sock"
        return 0
    fi
    return 1
}

SSH_SOCKET=$(find_ssh_socket 2>/dev/null || true)
if [[ -n "${SSH_SOCKET}" ]]; then
    # SSH tunnel is available, container client should be running
    if ! pgrep -f "container_client.py" > /dev/null; then
        echo "UNHEALTHY: Container client not running"
        exit 1
    fi
fi
# If no SSH socket, container client is optional - skip check

# Check MCP servers from port mapping
PORTS_FILE="/tmp/mcp-ports.json"
if [[ -f "${PORTS_FILE}" ]]; then
    # Read port mapping and check each server
    PORTS=$(python3 -c "
import json
import sys
try:
    with open('${PORTS_FILE}') as f:
        data = json.load(f)
    for name, info in data.items():
        print(f\"{name}:{info['port']}\")
except Exception as e:
    print(f'Error reading ports: {e}', file=sys.stderr)
    sys.exit(0)  # Don't fail health check if file is malformed
" 2>/dev/null)

    for entry in ${PORTS}; do
        NAME="${entry%%:*}"
        PORT="${entry##*:}"

        # Check if port is listening
        if ! ss -tlnp 2>/dev/null | grep -q ":${PORT}" && \
           ! netstat -tlnp 2>/dev/null | grep -q ":${PORT}"; then
            echo "UNHEALTHY: MCP server '${NAME}' not listening on port ${PORT}"
            exit 1
        fi
    done
fi

echo "HEALTHY: All services running"
exit 0
