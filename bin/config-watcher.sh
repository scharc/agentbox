#!/usr/bin/env bash
# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

# Config poller for Agentbox unified + runtime configs
# Polls unified, per-agent, and runtime configs for changes and syncs them

set -euo pipefail

UNIFIED_CONFIG="/workspace/.agentbox/agentbox.config.json"
CLAUDE_RUNTIME_CONFIG="/home/abox/.claude/config.json"
CLAUDE_PROJECT_CONFIG="/workspace/.agentbox/config.json"
CODEX_RUNTIME_CONFIG="/home/abox/.codex/config.toml"
CODEX_PROJECT_CONFIG="/workspace/.agentbox/codex.toml"

GENERATE_UNIFIED_SCRIPT="/usr/local/bin/unified-config.py"
MERGE_CLAUDE_SCRIPT="/usr/local/bin/merge-config.py"
SPLIT_CLAUDE_SCRIPT="/usr/local/bin/split-config.py"
MERGE_CODEX_SCRIPT="/usr/local/bin/merge-codex-config.py"
SPLIT_CODEX_SCRIPT="/usr/local/bin/split-codex-config.py"

LOCK_FILE="/tmp/agentbox-config-sync.lock"
PID_FILE="/tmp/agentbox-config-watcher.pid"
POLL_INTERVAL="${AGENTBOX_CONFIG_POLL_INTERVAL:-5}"

get_mtime() {
    local path="$1"
    if [[ -f "$path" ]]; then
        stat -c %Y "$path" 2>/dev/null || echo 0
    else
        echo 0
    fi
}

acquire_lock() {
    for _ in $(seq 1 50); do
        if ( set -o noclobber; echo "$$" > "$LOCK_FILE" ) 2>/dev/null; then
            return
        fi
        sleep 0.1
    done
    echo "[Config Poller] Warning: lock timeout, forcing sync" >&2
    rm -f "$LOCK_FILE"
    echo "$$" > "$LOCK_FILE"
}

release_lock() {
    rm -f "$LOCK_FILE"
}

ensure_single_instance() {
    if [[ -f "$PID_FILE" ]]; then
        local existing_pid
        existing_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
        if [[ -n "$existing_pid" ]] && kill -0 "$existing_pid" 2>/dev/null; then
            echo "[Config Poller] Already running (pid $existing_pid), exiting." >&2
            exit 0
        fi
    fi
    echo "$$" > "$PID_FILE"
}

notify_conflict() {
    local message="$1"
    echo "[Config Poller] Conflict: $message" >&2
    exit 1
}

sync_project_to_runtime() {
    echo "[Config Poller] Syncing project config to runtime..." >&2
    acquire_lock
    python3 "$MERGE_CLAUDE_SCRIPT" || true
    python3 "$MERGE_CODEX_SCRIPT" || true
    release_lock
}

sync_runtime_to_project() {
    echo "[Config Poller] Syncing runtime config to project..." >&2
    acquire_lock
    python3 "$SPLIT_CLAUDE_SCRIPT" || true
    python3 "$SPLIT_CODEX_SCRIPT" || true
    release_lock
}

sync_unified_to_project() {
    echo "[Config Poller] Unified config changed, regenerating project configs..." >&2
    acquire_lock
    python3 "$GENERATE_UNIFIED_SCRIPT" generate || true
    release_lock
}

sync_project_to_unified() {
    echo "[Config Poller] Project config changed, refolding into unified config..." >&2
    acquire_lock
    python3 "$GENERATE_UNIFIED_SCRIPT" refold || true
    release_lock
}

ensure_single_instance
trap 'rm -f "$PID_FILE" "$LOCK_FILE"' EXIT

echo "[Config Poller] Starting config poller..." >&2

# Initial generate + merge on startup
if [[ -f "$UNIFIED_CONFIG" ]]; then
    echo "[Config Poller] Performing initial generation..." >&2
    sync_unified_to_project
    sync_project_to_runtime
else
    echo "[Config Poller] No unified config found at $UNIFIED_CONFIG" >&2
fi

last_unified_mtime=$(get_mtime "$UNIFIED_CONFIG")
last_claude_project_mtime=$(get_mtime "$CLAUDE_PROJECT_CONFIG")
last_claude_runtime_mtime=$(get_mtime "$CLAUDE_RUNTIME_CONFIG")
last_codex_project_mtime=$(get_mtime "$CODEX_PROJECT_CONFIG")
last_codex_runtime_mtime=$(get_mtime "$CODEX_RUNTIME_CONFIG")

while true; do
    sleep "$POLL_INTERVAL"

    current_unified_mtime=$(get_mtime "$UNIFIED_CONFIG")
    current_claude_project_mtime=$(get_mtime "$CLAUDE_PROJECT_CONFIG")
    current_claude_runtime_mtime=$(get_mtime "$CLAUDE_RUNTIME_CONFIG")
    current_codex_project_mtime=$(get_mtime "$CODEX_PROJECT_CONFIG")
    current_codex_runtime_mtime=$(get_mtime "$CODEX_RUNTIME_CONFIG")

    unified_changed=false
    claude_project_changed=false
    codex_project_changed=false
    claude_runtime_changed=false
    codex_runtime_changed=false

    if [[ "$current_unified_mtime" -gt "$last_unified_mtime" ]]; then
        unified_changed=true
    fi
    if [[ "$current_claude_project_mtime" -gt "$last_claude_project_mtime" ]]; then
        claude_project_changed=true
    fi
    if [[ "$current_codex_project_mtime" -gt "$last_codex_project_mtime" ]]; then
        codex_project_changed=true
    fi
    if [[ "$current_claude_runtime_mtime" -gt "$last_claude_runtime_mtime" ]]; then
        claude_runtime_changed=true
    fi
    if [[ "$current_codex_runtime_mtime" -gt "$last_codex_runtime_mtime" ]]; then
        codex_runtime_changed=true
    fi

    if $unified_changed && ( $claude_project_changed || $codex_project_changed ); then
        notify_conflict "Unified config changed alongside per-agent configs. Resolve conflicts and restart the watcher."
    fi
    if $claude_project_changed && $codex_project_changed; then
        notify_conflict "Both per-agent configs changed in the same poll cycle. Resolve conflicts and restart the watcher."
    fi

    if $unified_changed; then
        sync_unified_to_project
        sync_project_to_runtime
        current_unified_mtime=$(get_mtime "$UNIFIED_CONFIG")
        current_claude_project_mtime=$(get_mtime "$CLAUDE_PROJECT_CONFIG")
        current_codex_project_mtime=$(get_mtime "$CODEX_PROJECT_CONFIG")
        current_claude_runtime_mtime=$(get_mtime "$CLAUDE_RUNTIME_CONFIG")
        current_codex_runtime_mtime=$(get_mtime "$CODEX_RUNTIME_CONFIG")
    fi

    if $claude_runtime_changed || $codex_runtime_changed; then
        sync_runtime_to_project
        sync_project_to_unified
        sync_unified_to_project
        sync_project_to_runtime
        current_unified_mtime=$(get_mtime "$UNIFIED_CONFIG")
        current_claude_project_mtime=$(get_mtime "$CLAUDE_PROJECT_CONFIG")
        current_codex_project_mtime=$(get_mtime "$CODEX_PROJECT_CONFIG")
        current_claude_runtime_mtime=$(get_mtime "$CLAUDE_RUNTIME_CONFIG")
        current_codex_runtime_mtime=$(get_mtime "$CODEX_RUNTIME_CONFIG")
    elif $claude_project_changed || $codex_project_changed; then
        sync_project_to_unified
        sync_unified_to_project
        sync_project_to_runtime
        current_unified_mtime=$(get_mtime "$UNIFIED_CONFIG")
        current_claude_project_mtime=$(get_mtime "$CLAUDE_PROJECT_CONFIG")
        current_codex_project_mtime=$(get_mtime "$CODEX_PROJECT_CONFIG")
        current_claude_runtime_mtime=$(get_mtime "$CLAUDE_RUNTIME_CONFIG")
        current_codex_runtime_mtime=$(get_mtime "$CODEX_RUNTIME_CONFIG")
    fi

    last_unified_mtime="$current_unified_mtime"
    last_claude_project_mtime="$current_claude_project_mtime"
    last_claude_runtime_mtime="$current_claude_runtime_mtime"
    last_codex_project_mtime="$current_codex_project_mtime"
    last_codex_runtime_mtime="$current_codex_runtime_mtime"
done
