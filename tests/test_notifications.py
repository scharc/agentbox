"""Tests for agentbox/notifications.py"""

import json
import socket
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from agentbox.notifications import send_notification


class TestSendNotification:
    """Test notification sending functionality"""

    @patch('socket.socket')
    @patch('pathlib.Path.exists')
    def test_send_notification_success(self, mock_exists, mock_socket_class):
        """Test successful notification sending"""
        mock_exists.return_value = True

        # Mock socket instance
        mock_sock = MagicMock()
        mock_socket_class.return_value.__enter__.return_value = mock_sock
        mock_sock.recv.return_value = json.dumps({"ok": True}).encode("utf-8")

        result = send_notification("Test Title", "Test Message", "normal")

        assert result is True
        mock_sock.connect.assert_called_once()
        mock_sock.sendall.assert_called_once()

        # Verify payload structure
        call_args = mock_sock.sendall.call_args[0][0]
        payload = json.loads(call_args.decode("utf-8").strip())
        assert payload["action"] == "notify"
        assert payload["title"] == "Test Title"
        assert payload["message"] == "Test Message"
        assert payload["urgency"] == "normal"

    @patch('pathlib.Path.exists')
    def test_send_notification_socket_missing(self, mock_exists):
        """Test notification when socket doesn't exist"""
        mock_exists.return_value = False

        result = send_notification("Test", "Message")

        assert result is False

    @patch('socket.socket')
    @patch('pathlib.Path.exists')
    def test_send_notification_socket_error(self, mock_exists, mock_socket_class):
        """Test notification when socket connection fails"""
        mock_exists.return_value = True
        mock_socket_class.return_value.__enter__.side_effect = ConnectionRefusedError()

        result = send_notification("Test", "Message")

        assert result is False

    @patch('socket.socket')
    @patch('pathlib.Path.exists')
    def test_send_notification_proxy_error(self, mock_exists, mock_socket_class):
        """Test notification when proxy returns error"""
        mock_exists.return_value = True

        mock_sock = MagicMock()
        mock_socket_class.return_value.__enter__.return_value = mock_sock
        mock_sock.recv.return_value = json.dumps({"ok": False, "error": "test_error"}).encode("utf-8")

        result = send_notification("Test", "Message")

        assert result is False

    @patch('socket.socket')
    @patch('pathlib.Path.exists')
    def test_send_notification_invalid_response(self, mock_exists, mock_socket_class):
        """Test notification with invalid JSON response"""
        mock_exists.return_value = True

        mock_sock = MagicMock()
        mock_socket_class.return_value.__enter__.return_value = mock_sock
        mock_sock.recv.return_value = b"invalid json"

        result = send_notification("Test", "Message")

        assert result is False

    @patch('socket.socket')
    @patch('pathlib.Path.exists')
    def test_send_notification_custom_socket_path(self, mock_exists, mock_socket_class):
        """Test notification with custom socket path"""
        mock_exists.return_value = True

        mock_sock = MagicMock()
        mock_socket_class.return_value.__enter__.return_value = mock_sock
        mock_sock.recv.return_value = json.dumps({"ok": True}).encode("utf-8")

        custom_path = "/tmp/custom.sock"
        result = send_notification("Test", "Message", socket_path=custom_path)

        assert result is True
        mock_sock.connect.assert_called_once_with(custom_path)

    @patch('socket.socket')
    @patch('pathlib.Path.exists')
    def test_send_notification_urgency_levels(self, mock_exists, mock_socket_class):
        """Test different urgency levels"""
        mock_exists.return_value = True

        mock_sock = MagicMock()
        mock_socket_class.return_value.__enter__.return_value = mock_sock
        mock_sock.recv.return_value = json.dumps({"ok": True}).encode("utf-8")

        for urgency in ["low", "normal", "critical"]:
            send_notification("Test", "Message", urgency)

            call_args = mock_sock.sendall.call_args[0][0]
            payload = json.loads(call_args.decode("utf-8").strip())
            assert payload["urgency"] == urgency

    @patch('socket.socket')
    @patch('pathlib.Path.exists')
    def test_send_notification_timeout(self, mock_exists, mock_socket_class):
        """Test notification timeout handling"""
        mock_exists.return_value = True

        mock_sock = MagicMock()
        mock_socket_class.return_value.__enter__.return_value = mock_sock
        mock_sock.recv.side_effect = socket.timeout()

        result = send_notification("Test", "Message")

        assert result is False
        mock_sock.settimeout.assert_called_once_with(2.0)


class TestNotifyEnhancedScript:
    """Integration tests for bin/abox-notify script"""

    def test_socket_connect_before_settimeout(self, tmp_path):
        """Test that connect() is called before settimeout() to avoid EAGAIN.

        Setting timeout before connect on Unix domain sockets can cause
        BlockingIOError (EAGAIN) because the socket is put in non-blocking
        mode before the connection is established.
        """
        import subprocess
        import threading
        import os

        # Create a real Unix socket server
        sock_path = tmp_path / "test.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        response_sent = threading.Event()

        def server_handler():
            conn, _ = server_sock.accept()
            conn.settimeout(5.0)
            try:
                data = conn.recv(4096)
                conn.sendall(json.dumps({"ok": True}).encode() + b"\n")
            finally:
                conn.close()
                response_sent.set()

        server_thread = threading.Thread(target=server_handler)
        server_thread.start()

        try:
            # Test the socket client code directly (extracted from abox-notify)
            # This is the pattern that was broken when settimeout was before connect
            client_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            # CORRECT ORDER: connect first, then settimeout
            client_sock.connect(str(sock_path))
            client_sock.settimeout(60.0)

            payload = {"action": "notify", "title": "Test", "message": "Test"}
            client_sock.sendall((json.dumps(payload) + "\n").encode())
            client_sock.shutdown(socket.SHUT_WR)
            response = client_sock.recv(4096)
            client_sock.close()

            assert b'"ok": true' in response.lower() or b'"ok":true' in response.lower()
        finally:
            response_sent.wait(timeout=5)
            server_sock.close()
            server_thread.join(timeout=5)

    def test_socket_settimeout_before_connect_fails(self, tmp_path):
        """Verify that settimeout before connect causes EAGAIN on Unix sockets.

        This test documents the bug that was fixed - if this test starts
        passing (no error), it means the underlying behavior changed.
        """
        import threading

        sock_path = tmp_path / "test.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        def server_handler():
            try:
                conn, _ = server_sock.accept()
                conn.close()
            except:
                pass

        server_thread = threading.Thread(target=server_handler)
        server_thread.start()

        try:
            client_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            # WRONG ORDER: settimeout before connect - this causes EAGAIN
            client_sock.settimeout(60.0)

            # This should raise BlockingIOError (EAGAIN) on most systems
            # If it doesn't, the test documents that the issue doesn't occur
            # on this system/Python version
            try:
                client_sock.connect(str(sock_path))
                # If we get here, the bug doesn't manifest on this system
                pytest.skip("settimeout before connect works on this system")
            except BlockingIOError:
                # This is the expected behavior that we fixed
                pass
            finally:
                client_sock.close()
        finally:
            server_sock.close()
            server_thread.join(timeout=5)

    def test_abox_notify_script_syntax(self):
        """Test that abox-notify script has valid bash syntax"""
        import subprocess
        from pathlib import Path

        script_path = Path(__file__).parent.parent / "bin" / "abox-notify"
        if not script_path.exists():
            pytest.skip("abox-notify script not found")

        result = subprocess.run(
            ["bash", "-n", str(script_path)],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"

    def test_abox_notify_python_code_order(self):
        """Verify the Python code in abox-notify has correct socket operation order"""
        from pathlib import Path
        import re

        script_path = Path(__file__).parent.parent / "bin" / "abox-notify"
        if not script_path.exists():
            pytest.skip("abox-notify script not found")

        content = script_path.read_text()

        # Extract the Python code block
        python_match = re.search(r"python3 <<'PYTHON_SCRIPT'(.+?)PYTHON_SCRIPT", content, re.DOTALL)
        assert python_match, "Could not find Python code block in script"

        python_code = python_match.group(1)

        # Find positions of connect and settimeout calls
        connect_match = re.search(r'sock\.connect\(', python_code)
        settimeout_match = re.search(r'sock\.settimeout\(', python_code)

        assert connect_match, "sock.connect() not found in script"
        assert settimeout_match, "sock.settimeout() not found in script"

        # Verify connect comes before settimeout
        assert connect_match.start() < settimeout_match.start(), \
            "sock.connect() must be called before sock.settimeout() to avoid EAGAIN"
