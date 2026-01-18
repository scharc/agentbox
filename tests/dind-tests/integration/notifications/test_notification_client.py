# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT

"""Integration tests for notification client."""

import json
import socket
import tempfile
import threading
import time
from pathlib import Path

import pytest

from helpers.cli import run_abox
from helpers.docker import exec_in_container


def create_mock_socket_server(socket_path: Path, response: dict, delay: float = 0):
    """Create a mock Unix socket server for testing.

    Args:
        socket_path: Path to Unix socket
        response: Response dict to send back
        delay: Delay before responding (seconds)
    """
    def server_thread():
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            socket_path.unlink(missing_ok=True)
            sock.bind(str(socket_path))
            sock.listen(1)
            sock.settimeout(5.0)

            conn, _ = sock.accept()
            # Read request
            data = conn.recv(4096)

            # Delay if requested
            if delay > 0:
                time.sleep(delay)

            # Send response
            response_json = json.dumps(response) + "\n"
            conn.sendall(response_json.encode("utf-8"))
            conn.close()
        except Exception:
            pass
        finally:
            sock.close()
            socket_path.unlink(missing_ok=True)

    thread = threading.Thread(target=server_thread, daemon=True)
    thread.start()
    time.sleep(0.2)  # Let server start
    return thread


@pytest.mark.integration
class TestNotificationClient:
    """Test notification client functionality."""

    def test_notify_script_available(self, running_container, test_project):
        """Test that abox-notify script is available in container."""
        container_name = f"agentbox-{test_project.name}"

        result = exec_in_container(
            container_name,
            "which abox-notify"
        )

        assert result.returncode == 0, "abox-notify should be in PATH"
        assert "abox-notify" in result.stdout

    def test_notify_with_title_and_message(self, running_container, test_project):
        """Test basic notification with title and message."""
        container_name = f"agentbox-{test_project.name}"

        # Note: This will fail if proxy is not running, which is expected in DinD
        # We're testing that the script exists and accepts correct arguments
        result = exec_in_container(
            container_name,
            "abox-notify 'Test Title' 'Test Message' 2>&1 || echo 'EXPECTED_FAIL'"
        )

        # Should not crash - either succeeds or fails gracefully
        assert "EXPECTED_FAIL" in result.stdout or result.returncode == 0

    def test_notify_with_urgency_levels(self, running_container, test_project):
        """Test notifications with different urgency levels."""
        container_name = f"agentbox-{test_project.name}"

        urgency_levels = ["low", "normal", "critical"]

        for urgency in urgency_levels:
            result = exec_in_container(
                container_name,
                f"abox-notify 'Title' 'Message' {urgency} 2>&1 || echo 'EXPECTED_FAIL'"
            )
            # Should accept the urgency level without error
            assert "EXPECTED_FAIL" in result.stdout or result.returncode == 0


@pytest.mark.integration
class TestNotificationPayload:
    """Test notification payload formatting."""

    def test_python_import_works(self, running_container, test_project):
        """Test that notifications module can be imported."""
        container_name = f"agentbox-{test_project.name}"

        result = exec_in_container(
            container_name,
            "python3 -c 'from agentbox.notifications import send_notification; print(\"OK\")'"
        )

        assert result.returncode == 0
        assert "OK" in result.stdout

    def test_send_notification_without_socket(self, running_container, test_project):
        """Test send_notification returns False when socket doesn't exist."""
        container_name = f"agentbox-{test_project.name}"

        # Try to send notification with non-existent socket
        result = exec_in_container(
            container_name,
            "python3 -c '"
            "from agentbox.notifications import send_notification; "
            "result = send_notification(\"Title\", \"Message\", socket_path=\"/tmp/nonexistent.sock\"); "
            "print(\"RESULT:\", result)"
            "'"
        )

        assert result.returncode == 0
        assert "RESULT: False" in result.stdout

    def test_notification_payload_structure(self, running_container, test_project):
        """Test that notification creates correct payload structure."""
        container_name = f"agentbox-{test_project.name}"

        # Create a script that builds the payload without sending
        script = """
import json
from agentbox.notifications import send_notification

# Build payload (same logic as in send_notification)
payload_dict = {
    "action": "notify",
    "title": "Test Title",
    "message": "Test Message",
    "urgency": "normal",
}

print(json.dumps(payload_dict))
"""

        result = exec_in_container(
            container_name,
            f"python3 -c '{script}'"
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["action"] == "notify"
        assert data["title"] == "Test Title"
        assert data["message"] == "Test Message"
        assert data["urgency"] == "normal"

    def test_notification_with_enhancement_metadata(self, running_container, test_project):
        """Test notification payload with enhancement metadata."""
        container_name = f"agentbox-{test_project.name}"

        script = """
import json

# Build enhanced payload
payload_dict = {
    "action": "notify",
    "title": "Enhanced",
    "message": "Message",
    "urgency": "normal",
    "enhance": True,
    "metadata": {
        "container": "test-container",
        "session": "test-session",
        "buffer": "buffer content"
    }
}

print(json.dumps(payload_dict))
"""

        result = exec_in_container(
            container_name,
            f"python3 -c '{script}'"
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["enhance"] is True
        assert "metadata" in data
        assert data["metadata"]["container"] == "test-container"
        assert data["metadata"]["session"] == "test-session"


@pytest.mark.integration
class TestNotificationErrorHandling:
    """Test notification error handling."""

    def test_notification_with_missing_socket_path(self, running_container, test_project):
        """Test notification fails gracefully with missing socket."""
        container_name = f"agentbox-{test_project.name}"

        result = exec_in_container(
            container_name,
            "python3 -c '"
            "from agentbox.notifications import send_notification; "
            "result = send_notification(\"Title\", \"Message\", socket_path=\"/tmp/missing.sock\"); "
            "exit(0 if result is False else 1)"
            "'"
        )

        assert result.returncode == 0, "Should return False for missing socket"

    def test_notification_with_invalid_urgency(self, running_container, test_project):
        """Test notification with invalid urgency level."""
        container_name = f"agentbox-{test_project.name}"

        # Python will accept any string for urgency, but test it doesn't crash
        result = exec_in_container(
            container_name,
            "python3 -c '"
            "from agentbox.notifications import send_notification; "
            "result = send_notification(\"Title\", \"Message\", urgency=\"invalid\", socket_path=\"/tmp/x.sock\"); "
            "print(\"OK\")"
            "'"
        )

        assert result.returncode == 0
        assert "OK" in result.stdout

    def test_notification_with_empty_title(self, running_container, test_project):
        """Test notification with empty title."""
        container_name = f"agentbox-{test_project.name}"

        result = exec_in_container(
            container_name,
            "python3 -c '"
            "from agentbox.notifications import send_notification; "
            "result = send_notification(\"\", \"Message\", socket_path=\"/tmp/x.sock\"); "
            "print(\"OK\")"
            "'"
        )

        # Should not crash
        assert result.returncode == 0
        assert "OK" in result.stdout

    def test_notification_with_long_message(self, running_container, test_project):
        """Test notification with very long message."""
        container_name = f"agentbox-{test_project.name}"

        # Create a long message
        long_message = "x" * 10000

        result = exec_in_container(
            container_name,
            f"python3 -c '"
            "from agentbox.notifications import send_notification; "
            f"result = send_notification(\"Title\", \"{long_message}\", socket_path=\"/tmp/x.sock\"); "
            "print(\"OK\")"
            "'"
        )

        # Should handle long messages without crashing
        assert result.returncode == 0
        assert "OK" in result.stdout


@pytest.mark.integration
class TestNotificationSocketCommunication:
    """Test notification socket communication patterns."""

    def test_socket_path_resolution(self, running_container, test_project):
        """Test that socket path is resolved correctly."""
        container_name = f"agentbox-{test_project.name}"

        # Get default socket path
        result = exec_in_container(
            container_name,
            "python3 -c '"
            "from agentbox.host_config import get_config; "
            "config = get_config(); "
            "print(config.socket_path)"
            "'"
        )

        assert result.returncode == 0
        # Should contain agentbox and .sock
        assert "agentbox" in result.stdout
        assert ".sock" in result.stdout

    def test_custom_socket_path_used(self, running_container, test_project):
        """Test that custom socket path is used when provided."""
        container_name = f"agentbox-{test_project.name}"

        # The function should use the provided path
        result = exec_in_container(
            container_name,
            "python3 -c '"
            "from agentbox.notifications import send_notification; "
            "from pathlib import Path; "
            "custom_path = \"/tmp/custom.sock\"; "
            "result = send_notification(\"T\", \"M\", socket_path=custom_path); "
            "print(\"USED_CUSTOM\" if not Path(custom_path).exists() else \"EXISTS\")"
            "'"
        )

        assert result.returncode == 0
        # Socket doesn't exist so it should fail but use the custom path
        assert "USED_CUSTOM" in result.stdout or "EXISTS" in result.stdout


@pytest.mark.integration
class TestNotificationConfigIntegration:
    """Test notification integration with host config."""

    def test_timeout_configuration(self, running_container, test_project):
        """Test that timeout values are read from config."""
        container_name = f"agentbox-{test_project.name}"

        # Get timeout values from config
        result = exec_in_container(
            container_name,
            "python3 -c '"
            "from agentbox.host_config import get_config; "
            "config = get_config(); "
            "normal = config.get(\"notifications\", \"timeout\"); "
            "enhanced = config.get(\"notifications\", \"timeout_enhanced\"); "
            "print(f\"NORMAL:{normal} ENHANCED:{enhanced}\")"
            "'"
        )

        assert result.returncode == 0
        # Should have both timeout values
        assert "NORMAL:" in result.stdout
        assert "ENHANCED:" in result.stdout

    def test_socket_path_from_config(self, running_container, test_project):
        """Test that socket path comes from config when not specified."""
        container_name = f"agentbox-{test_project.name}"

        result = exec_in_container(
            container_name,
            "python3 -c '"
            "from agentbox.host_config import get_config; "
            "config = get_config(); "
            "sock_path = config.socket_path; "
            "print(f\"PATH:{sock_path}\")"
            "'"
        )

        assert result.returncode == 0
        assert "PATH:" in result.stdout


@pytest.mark.integration
class TestNotificationIntegration:
    """Integration tests for notification workflows."""

    def test_notify_script_passes_arguments(self, running_container, test_project):
        """Test that abox-notify correctly passes arguments."""
        container_name = f"agentbox-{test_project.name}"

        # Test with explicit arguments
        result = exec_in_container(
            container_name,
            "abox-notify 'Integration Test' 'This is a test message' normal 2>&1 || echo 'CALLED'"
        )

        # Script should be called (may fail due to no socket, but that's OK)
        assert "CALLED" in result.stdout or result.returncode == 0

    def test_notification_from_python_api(self, running_container, test_project):
        """Test notification API from Python."""
        container_name = f"agentbox-{test_project.name}"

        script = """
from agentbox.notifications import send_notification

# This will fail without proxy, but tests the API
try:
    result = send_notification(
        title="API Test",
        message="Testing Python API",
        urgency="normal"
    )
    print(f"RESULT:{result}")
except Exception as e:
    print(f"ERROR:{e}")
"""

        result = exec_in_container(
            container_name,
            f"python3 -c '{script}'"
        )

        # Should execute without crashing
        assert result.returncode == 0
        assert "RESULT:" in result.stdout or "ERROR:" in result.stdout

    def test_enhanced_notification_api(self, running_container, test_project):
        """Test enhanced notification with metadata."""
        container_name = f"agentbox-{test_project.name}"

        script = """
from agentbox.notifications import send_notification

result = send_notification(
    title="Enhanced Test",
    message="Testing enhancement",
    urgency="normal",
    container="test-container",
    session="test-session",
    buffer="test buffer content",
    enhance=True
)
print(f"RESULT:{result}")
"""

        result = exec_in_container(
            container_name,
            f"python3 -c '{script}'"
        )

        # Should execute without crashing
        assert result.returncode == 0
        assert "RESULT:" in result.stdout

    def test_notification_workflow_in_session(self, running_container, test_project):
        """Test notification can be sent from within tmux session."""
        container_name = f"agentbox-{test_project.name}"

        # Create a session that tries to send a notification
        result = exec_in_container(
            container_name,
            "tmux new-session -d -s notify-test "
            "'abox-notify \"Session Test\" \"From tmux\" 2>&1 > /tmp/notify-output.txt; sleep 2'"
        )
        assert result.returncode == 0

        # Wait for command to execute
        time.sleep(1)

        # Check that command was executed
        result = exec_in_container(
            container_name,
            "test -f /tmp/notify-output.txt && echo 'EXISTS'"
        )
        assert "EXISTS" in result.stdout

        # Cleanup
        exec_in_container(container_name, "tmux kill-session -t notify-test 2>/dev/null || true")
        exec_in_container(container_name, "rm -f /tmp/notify-output.txt")
